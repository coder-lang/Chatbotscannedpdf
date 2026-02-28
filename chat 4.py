"""
routers/chat.py
===============
POST   /chat              — send message, get HTML response
GET    /chat/history      — get full conversation for a user_id
GET    /chat/exists       — check if user_id has existing history
DELETE /chat/history      — clear conversation for a user_id

No JWT or auth. user_id is sent by frontend in every request.
Frontend generates and manages user_id completely.
"""
from fastapi import APIRouter, Request
from models.chat import (
    ChatRequest, ChatResponse,
    ClearRequest, HistoryResponse,
    ChatMessage, UserExistsResponse,
)
from services.chat_service import chat
from services.conversation_service import (
    clear_conversation,
    get_all_messages,
    user_exists,
)

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("", response_model=ChatResponse)
async def send_message(body: ChatRequest, request: Request):
    """
    Send a message and get a grounded HTML response.

    user_id rules:
      Same user_id → history loads and continues automatically  ✅
      New user_id  → fresh conversation starts automatically    ✅
      No registration needed — first message auto-creates user  ✅
    """
    answer, citations = chat(
        user_id=body.user_id,
        user_message=body.message,
        vectorstore=request.app.state.vectorstore,
    )
    return ChatResponse(answer=answer, sources=citations, is_html=True)


@router.get("/history", response_model=HistoryResponse)
def get_history(user_id: str):
    """
    GET /chat/history?user_id=abc-123
    Returns full conversation history for this user_id.
    """
    messages = get_all_messages(user_id)
    return HistoryResponse(
        user_id=user_id,
        messages=[ChatMessage(**m) for m in messages],
    )


@router.get("/exists", response_model=UserExistsResponse)
def check_user(user_id: str):
    """
    GET /chat/exists?user_id=abc-123
    Frontend calls this on startup to check if user has existing history.
    Use to show "Welcome back" vs "Start new conversation".
    """
    exists = user_exists(user_id)
    return UserExistsResponse(
        user_id=user_id,
        has_history=exists,
        message="Returning user — history loaded." if exists
                else "New user — fresh conversation starts.",
    )


@router.delete("/history", status_code=204)
def delete_history(body: ClearRequest):
    """
    Clear conversation history for a user_id.
    Called when user explicitly wants to reset their conversation.
    """
    clear_conversation(body.user_id)
