from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.models.chat import ChatSession, ChatMessage
from app.schemas.chat import ChatSessionResponse, ChatSessionWithMessagesResponse, ChatSessionCreate, ChatRequest, ChatMessageResponse
from app.services.gemini_service import get_gemini_client

router = APIRouter()

@router.get("/", response_model=List[ChatSessionResponse])
async def get_chat_sessions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == current_user.id)
        .order_by(ChatSession.updated_at.desc())
    )
    return result.scalars().all()

@router.post("/", response_model=ChatSessionResponse)
async def create_chat_session(
    chat_in: ChatSessionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db_session = ChatSession(
        title=chat_in.title,
        user_id=current_user.id,
        video_id=chat_in.video_id
    )
    db.add(db_session)
    await db.commit()
    await db.refresh(db_session)
    return db_session

@router.get("/{session_id}", response_model=ChatSessionWithMessagesResponse)
async def get_chat_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
    )
    db_session = result.scalar_one_or_none()
    if not db_session:
        raise HTTPException(status_code=404, detail="Chat session not found")
        
    # Load messages
    await db.refresh(db_session, ["messages"])
    # Sort messages by created_at
    db_session.messages.sort(key=lambda x: x.created_at)
    return db_session

@router.post("/{session_id}/message", response_model=List[ChatMessageResponse])
async def send_chat_message(
    session_id: str,
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Verify session
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
    )
    db_session = result.scalar_one_or_none()
    if not db_session:
        raise HTTPException(status_code=404, detail="Chat session not found")

    # Add user message
    user_msg = ChatMessage(
        session_id=session_id,
        role="user",
        content=request.message
    )
    db.add(user_msg)
    
    # Generate AI response
    try:
        gemini = get_gemini_client()
        # TODO: Retrieve conversation history and pass to Gemini for context
        await db.refresh(db_session, ["messages"])
        history = [{"role": msg.role, "content": msg.content} for msg in db_session.messages]
        
        # Format history for Gemini (user/model)
        formatted_history = []
        for msg in history:
            role = "user" if msg["role"] == "user" else "model"
            formatted_history.append({"role": role, "parts": [msg["content"]]})
            
        chat = gemini.model.start_chat(history=formatted_history)
        ai_response = chat.send_message(request.message)
        ai_content = ai_response.text
        
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Chat AI error: {e}", exc_info=True)
        ai_content = "Sorry, I encountered an error. Please try again."
        
    # Add AI message
    ai_msg = ChatMessage(
        session_id=session_id,
        role="ai",
        content=ai_content
    )
    db.add(ai_msg)
    
    # Update session time
    db_session.updated_at = user_msg.created_at
    
    await db.commit()
    await db.refresh(user_msg)
    await db.refresh(ai_msg)
    
    return [user_msg, ai_msg]
