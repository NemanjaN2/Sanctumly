"""
Business logic services
"""
from app.services.rag import generate_embedding, chunk_text, retrieve_relevant_context, cosine_similarity
from app.services.memory import get_conversation_memory, update_conversation_memory
from app.services.search import search_web, fetch_url, extract_urls

__all__ = [
    "generate_embedding",
    "chunk_text",
    "retrieve_relevant_context",
    "cosine_similarity",
    "get_conversation_memory",
    "update_conversation_memory",
    "search_web",
    "fetch_url",
    "extract_urls",
]
