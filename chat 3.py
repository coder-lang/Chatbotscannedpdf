"""
models/chat.py
==============
Pydantic schemas for chat endpoints.
answer field contains HTML — render with innerHTML on frontend.
"""
from typing import List, Optional
from pydantic import BaseModel


class ChatRequest(BaseModel):
    user_id: str    # Frontend-generated UUID — owns the conversation
    message: str


class ClearRequest(BaseModel):
    user_id: str


class ChatMessage(BaseModel):
    role:      str            # "user" | "assistant"
    content:   str            # HTML string for assistant messages
    timestamp: Optional[str] = None


class ChatResponse(BaseModel):
    answer:  str              # HTML string — use innerHTML on frontend
    sources: Optional[List[str]] = []
    is_html: bool = True      # flag so frontend knows to render as HTML


class HistoryResponse(BaseModel):
    user_id:  str
    messages: List[ChatMessage]


class UserExistsResponse(BaseModel):
    user_id:     str
    has_history: bool
    message:     str
