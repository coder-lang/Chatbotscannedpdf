"""
models/chat.py
==============
Pydantic schemas for chat endpoints.
"""
from typing import List, Optional
from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str


class ChatMessage(BaseModel):
    role: str           # "user" | "assistant"
    content: str
    timestamp: Optional[str] = None


class ChatResponse(BaseModel):
    answer: str
    sources: Optional[List[str]] = []   # document name + page citations


class HistoryResponse(BaseModel):
    user_id: str
    messages: List[ChatMessage]
