"""
RAG (Retrieval Augmented Generation) service
Embeddings, chunking, and context retrieval
MIGRATED: From Gemini Embedding API to local sentence-transformers (all-MiniLM-L6-v2)
NO API KEY REQUIRED - runs fully local on Railway
"""
import json
import logging
import numpy as np
from sqlalchemy.orm import Session
from app.models.document import UserDocument

logger = logging.getLogger(__name__)

# Load model once at startup — not on every request
_embedding_model = None

def _get_model():
    global _embedding_model
    if _embedding_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            logger.info("⏳ Loading sentence-transformers model...")
            _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("✅ sentence-transformers model loaded (all-MiniLM-L6-v2)")
        except Exception as e:
            logger.error(f"❌ Failed to load embedding model: {e}")
            _embedding_model = None
    return _embedding_model


def generate_embedding(text: str):
    """Generate one embedding using the local sentence-transformers model."""
    try:
        model = _get_model()
        if model is None:
            logger.warning("Embedding model not available, skipping RAG")
            return None
        embedding = model.encode(text, convert_to_numpy=True, show_progress_bar=False)
        return embedding.tolist()
    except Exception as e:
        logger.error("Embedding error: %s", type(e).__name__)
        return None


def generate_embeddings(texts: list[str], batch_size: int = 32) -> list[list[float] | None]:
    """Embed document chunks in small batches to reduce per-chunk CPU overhead."""
    if not texts:
        return []
    try:
        model = _get_model()
        if model is None:
            logger.warning("Embedding model not available, storing chunks without vectors")
            return [None] * len(texts)
        vectors = model.encode(
            texts,
            batch_size=max(1, min(int(batch_size), 32)),
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return [vector.tolist() for vector in vectors]
    except Exception as e:
        logger.error("Batch embedding error: %s", type(e).__name__)
        return [None] * len(texts)


def chunk_text(text: str, chunk_size: int = 1000):
    """Split text into chunks for embedding"""
    words = text.split()
    chunks = []
    current_chunk = []
    current_length = 0

    for word in words:
        current_chunk.append(word)
        current_length += len(word) + 1

        if current_length >= chunk_size:
            chunks.append(' '.join(current_chunk))
            current_chunk = []
            current_length = 0

    if current_chunk:
        chunks.append(' '.join(current_chunk))

    return chunks


def cosine_similarity(vec1, vec2):
    """Calculate cosine similarity between two vectors"""
    vec1 = np.array(vec1)
    vec2 = np.array(vec2)
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return np.dot(vec1, vec2) / (norm1 * norm2)


def retrieve_relevant_context(query: str, session_id: str, db: Session, top_k: int = 3) -> str:
    """RAG: Retrieve relevant document chunks for a query.

    Check for indexed documents before invoking the local embedding model. Most
    free-tier conversations have no uploads; skipping needless model inference
    reduces Railway CPU and memory pressure on ordinary text chats.
    """
    documents = db.query(UserDocument).filter(
        UserDocument.session_id == session_id,
        UserDocument.embedding.isnot(None),
    ).all()
    if not documents:
        return ""

    query_embedding = generate_embedding(query)
    if not query_embedding:
        return ""

    scored_docs = []
    for doc in documents:
        if doc.embedding:
            try:
                doc_embedding = json.loads(doc.embedding)
                similarity = cosine_similarity(query_embedding, doc_embedding)
                scored_docs.append((similarity, doc.content, doc.filename))
            except Exception:
                continue

    if not scored_docs:
        return ""

    scored_docs.sort(reverse=True, key=lambda x: x[0])

    context_parts = []
    for score, content, filename in scored_docs[:top_k]:
        if score > 0.3:  # Only include actually relevant chunks
            context_parts.append(f"[From {filename}]\n{content}\n")

    return "\n".join(context_parts)
