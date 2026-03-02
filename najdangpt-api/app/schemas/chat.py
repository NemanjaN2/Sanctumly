"""
Chat schemas
"""

from pydantic import BaseModel
from typing import Optional


class ChatRequest(BaseModel):
    message: str
    session_id: str
    username: str
    personality: Optional[str] = "default"
    image: Optional[str] = None  # Base64-encoded image data


class ChatResponse(BaseModel):
    response: str
    session_id: str
    had_rag_context: Optional[bool] = False
    had_memory: Optional[bool] = False


class FileUploadResponse(BaseModel):
    success: bool
    filename: str
    chunks: int
    size: int
