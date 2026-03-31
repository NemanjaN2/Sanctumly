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
    """Generate embedding using local sentence-transformers model"""
    try:
        model = _get_model()
        if model is None:
            logger.warning("⚠️ Embedding model not available, skipping RAG")
            return None
        embedding = model.encode(text, convert_to_numpy=True)
        return embedding.tolist()
    except Exception as e:
        logger.error(f"⚠️ Embedding error: {e}")
        return None


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
    """RAG: Retrieve relevant document chunks for a query"""
    query_embedding = generate_embedding(query)
    if not query_embedding:
        return ""

    documents = db.query(UserDocument).filter_by(session_id=session_id).all()

    if not documents:
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
