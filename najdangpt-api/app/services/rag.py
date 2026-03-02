"""
RAG (Retrieval Augmented Generation) service
Embeddings, chunking, and context retrieval
"""
import json
import logging
import os
import requests
import numpy as np
from sqlalchemy.orm import Session
from app.models.document import UserDocument

logger = logging.getLogger(__name__)

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")


def generate_embedding(text: str):
    """Generate embedding using free Gemini Embedding API"""
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent?key={GOOGLE_API_KEY}"
        payload = {
            "model": "models/gemini-embedding-001",
            "content": {
                "parts": [{"text": text}]
            }
        }
        response = requests.post(url, json=payload, timeout=30)
        
        if response.status_code != 200:
            logger.error(f"⚠️ Embedding API error {response.status_code}: {response.text}")
            return None
        
        data = response.json()
        return data["embedding"]["values"]
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
    return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))


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
            except:
                continue
    
    scored_docs.sort(reverse=True, key=lambda x: x[0])
    
    if not scored_docs:
        return ""
    
    context_parts = []
    for score, content, filename in scored_docs[:top_k]:
        context_parts.append(f"[From {filename}]\n{content}\n")
    
    return "\n".join(context_parts)
