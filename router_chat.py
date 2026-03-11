# """
# routers/chat.py
# ===============
# POST   /chat              — send message, get HTML response
# GET    /chat/history      — get full conversation for a user_id
# GET    /chat/exists       — check if user_id has existing history
# DELETE /chat/history      — clear conversation for a user_id

# No JWT or auth. user_id is sent by frontend in every request.
# Frontend generates and manages user_id completely.
# """
# from fastapi import APIRouter, Request
# from models.chat import (
#     ChatRequest, ChatResponse,
#     ClearRequest, HistoryResponse,
#     ChatMessage, UserExistsResponse, GrievanceRequest, GrievanceResponse
# )
# from services.chat_service import chat
# from services.conversation_service import (
#     clear_conversation,
#     get_all_messages,
#     user_exists,
# )

# router = APIRouter(prefix="/chat", tags=["Chat"])


# @router.post("", response_model=ChatResponse)
# async def send_message(body: ChatRequest, request: Request):
#     """
#     Send a message and get a grounded HTML response.

#     user_id rules:
#       Same user_id → history loads and continues automatically  ✅
#       New user_id  → fresh conversation starts automatically    ✅
#       No registration needed — first message auto-creates user  ✅
#     """
#     answer, citations = chat(
#         user_id=body.user_id,
#         user_message=body.message,
#         vectorstore=request.app.state.vectorstore,
#     )
#     return ChatResponse(answer=answer, sources=citations, is_html=True)


# @router.get("/history", response_model=HistoryResponse)
# def get_history(user_id: str):
#     """
#     GET /chat/history?user_id=abc-123
#     Returns full conversation history for this user_id.
#     """
#     messages = get_all_messages(user_id)
#     return HistoryResponse(
#         user_id=user_id,
#         messages=[ChatMessage(**m) for m in messages],
#     )


# @router.get("/exists", response_model=UserExistsResponse)
# def check_user(user_id: str):
#     """
#     GET /chat/exists?user_id=abc-123
#     Frontend calls this on startup to check if user has existing history.
#     Use to show "Welcome back" vs "Start new conversation".
#     """
#     exists = user_exists(user_id)
#     return UserExistsResponse(
#         user_id=user_id,
#         has_history=exists,
#         message="Returning user — history loaded." if exists
#                 else "New user — fresh conversation starts.",
#     )


# @router.delete("/history", status_code=204)
# def delete_history(body: ClearRequest):
#     """
#     Clear conversation history for a user_id.
#     Called when user explicitly wants to reset their conversation.
#     """
#     clear_conversation(body.user_id)


# @router.post("/grievance", response_model=GrievanceResponse)
# async def create_grievance(body: GrievanceRequest, request: Request):
#     """
#     POST /chat/grievance
#     Runs the Grievance Assistant pipeline and returns normalized output.
#     """
#     assistant = getattr(request.app.state, "grievance_assistant", None)
#     if assistant is None:
#         raise HTTPException(status_code=500, detail="Grievance assistant not initialized")

#     # For higher throughput, you can offload to a thread:
#     # from fastapi.concurrency import run_in_threadpool
#     # result_text = await run_in_threadpool(assistant.process_user_input, body.message)

#     result_text = assistant.process_user_input(body.message, body.user_id)

#     # Normalize to {status, message, grievance_id}
#     status = "failure"
#     grievance_id = None
#     txt = (result_text or "").lower()

#     if "grievance has been registered" in txt:
#         status = "success"
#         # Try to extract ticket id after "track it with ..."
#         import re
#         m = re.search(r"track it with\s+([A-Za-z0-9\-]+)", result_text, flags=re.IGNORECASE)
#         if m:
#             grievance_id = m.group(1)
#     elif "already submited" in txt:
#         status = "duplicate"

#     return GrievanceResponse(
#         status=status,
#         message=result_text,
#         grievance_id=grievance_id,
#     )

# routers/chat.py
# ===============
# POST   /chat              — send message, get HTML response
# GET    /chat/history      — get full conversation for a user_id
# GET    /chat/exists       — check if user_id has existing history
# DELETE /chat/history      — clear conversation for a user_id
# POST   /chat/grievance    — grievance assistant
# POST   /chat/stream       — (NEW) chunked streaming response (plain text)
#
# No JWT or auth. user_id is sent by frontend in every request.
# Frontend generates and manages user_id completely.

# routers/chat.py
# ===============
# POST   /chat              — send message, get HTML response
# GET    /chat/history      — get full conversation for a user_id
# GET    /chat/exists       — check if user_id has existing history
# DELETE /chat/history      — clear conversation for a user_id
# POST   /chat/grievance    — grievance assistant
# POST   /chat/stream       — (NEW) chunked streaming response (plain text)
#
# No JWT or auth. user_id is sent by frontend in every request.
# Frontend generates and manages user_id completely.

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse
from models.chat import (
    ChatRequest, ChatResponse,
    ClearRequest, HistoryResponse,
    ChatMessage, UserExistsResponse, GrievanceRequest, GrievanceResponse
)
from services.chat_service import chat
from services.conversation_service import (
    clear_conversation,
    get_all_messages,
    user_exists,
)
import asyncio
import re

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

@router.post("/grievance", response_model=GrievanceResponse)
async def create_grievance(body: GrievanceRequest, request: Request):
    """
    POST /chat/grievance
    Runs the Grievance Assistant pipeline and returns normalized output.
    """
    assistant = getattr(request.app.state, "grievance_assistant", None)
    if assistant is None:
        raise HTTPException(status_code=500, detail="Grievance assistant not initialized")

    # If heavy, consider: from fastapi.concurrency import run_in_threadpool
    result_text = assistant.process_user_input(body.message, body.user_id)

    # Normalize to {status, message, grievance_id}
    status = "failure"
    grievance_id = None
    txt = (result_text or "").lower()

    if "grievance has been registered" in txt:
        status = "success"
        m = re.search(r"track it with\s+([A-Za-z0-9\-]+)", result_text, flags=re.IGNORECASE)
        if m:
            grievance_id = m.group(1)
    elif "already submited" in txt:
        status = "duplicate"

    return GrievanceResponse(
        status=status,
        message=result_text,
        grievance_id=grievance_id,
    )

# -------------------- NEW: Simple streaming endpoint --------------------
@router.post("/stream")
async def stream_chat(body: ChatRequest, request: Request):
    """
    Streams plain-text chunks for the assistant reply (chunked transfer).
    Minimal-change approach:
      - Calls your existing chat() once (same logic as /chat)
      - Streams the final HTML in chunks so frontend renders progressively.
    NOTE: This is not token-level model streaming yet, but gives a live UX.
    """
    user_id = body.user_id
    user_msg = body.message
    vectorstore = request.app.state.vectorstore

    async def generate():
        # Quick preface so UI shows activity immediately
        yield "⏳ Working on your request...\n"

        # Run blocking chat() in a worker thread to avoid blocking the event loop
        def run_chat_sync():
            answer, citations = chat(
                user_id=user_id,
                user_message=user_msg,
                vectorstore=vectorstore,
            )
            return answer  # HTML string

        answer_html = await asyncio.to_thread(run_chat_sync)

        # Stream the HTML in small chunks
        CHUNK_SIZE = 512
        for i in range(0, len(answer_html), CHUNK_SIZE):
            yield answer_html[i:i + CHUNK_SIZE]
            await asyncio.sleep(0)  # let event loop schedule other tasks

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",   # hint to proxies (e.g., nginx) not to buffer
    }
    return StreamingResponse(generate(), media_type="text/plain", headers=headers)
