from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User
from app.models.video import Video
from app.models.transcript import Transcript
from app.schemas.ai import AIAnalysisRequest, AIAnalysisResponse
from app.api.deps import get_current_user
from app.services.ai_provider import analyze_transcript, generate_title_description, chat_with_ai, analyze_video_media
from app.services.gemini_service import generate_visual_subtitles_with_gemini, extract_viral_shorts_with_gemini, generate_retention_plan_with_gemini
import json
import os

router = APIRouter()

@router.post("/analyze", response_model=AIAnalysisResponse)
async def run_analysis(
    req: AIAnalysisRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Verify ownership
    video_stmt = select(Video).where(Video.id == req.video_id, Video.user_id == current_user.id)
    video = (await db.execute(video_stmt)).scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    # Get transcript (optional — we can still analyze without one)
    transcript_stmt = select(Transcript).where(Transcript.video_id == req.video_id).order_by(Transcript.created_at.desc()).limit(1)
    transcript = (await db.execute(transcript_stmt)).scalar_one_or_none()

    analysis = None
    seo_data = {}

    # Try transcript text analysis first if available
    if transcript and transcript.full_text and "Whisper AI model" not in transcript.full_text and "No speech detected" not in transcript.full_text:
        analysis_text = transcript.full_text
        try:
            analysis = await analyze_transcript(analysis_text, req.prompt)
        except Exception:
            analysis = None

    # If no transcript analysis result yet, try direct multimodal video file analysis
    if not analysis and video.file_path and os.path.exists(video.file_path):
        try:
            analysis = await analyze_video_media(video.file_path, req.prompt)
            if analysis and isinstance(analysis, dict):
                seo_data = {
                    "title": analysis.get("title"),
                    "description": analysis.get("description")
                }
        except Exception as e:
            print(f"Direct video media analysis warning: {e}")

    # Fallback to local text generator if still missing
    if not analysis:
        clean_title = video.original_filename.rsplit('.', 1)[0] if video.original_filename else "Video Scene"
        clean_title = clean_title.replace('_', ' ').replace('-', ' ')
        analysis_text = (
            f"Video Title: {clean_title}\n"
            f"Duration: {video.duration or '8.0'} seconds\n"
            f"Resolution: {video.width or '?'}x{video.height or '?'}\n"
            f"Scene Details: A video scene showing {clean_title}."
        )
        analysis = await analyze_transcript(analysis_text, req.prompt)

    if not seo_data.get("title"):
        try:
            seo_data = await generate_title_description(transcript.full_text if (transcript and transcript.full_text) else video.original_filename)
        except Exception:
            seo_data = {
                "title": video.original_filename.rsplit('.', 1)[0] if video.original_filename else "Untitled Video",
                "description": analysis.get("summary", "")
            }

    # If transcript segments are missing or empty, generate timestamped visual scene subtitles
    if video.file_path and os.path.exists(video.file_path):
        has_segments = False
        if transcript and transcript.segments:
            try:
                parsed_segs = json.loads(transcript.segments) if isinstance(transcript.segments, str) else transcript.segments
                if isinstance(parsed_segs, list) and len(parsed_segs) > 0:
                    has_segments = True
            except Exception:
                pass
        
        if not has_segments:
            try:
                vis_segments = await generate_visual_subtitles_with_gemini(video.file_path)
                if vis_segments and len(vis_segments) > 0:
                    full_text = " ".join([s.get("text", "") for s in vis_segments])
                    if not transcript:
                        transcript = Transcript(
                            video_id=video.id,
                            language="en",
                            full_text=full_text,
                            segments=json.dumps(vis_segments),
                            status="completed"
                        )
                        db.add(transcript)
                    else:
                        transcript.full_text = full_text
                        transcript.segments = json.dumps(vis_segments)
                        transcript.status = "completed"
            except Exception as e:
                print(f"Visual subtitles generation warning: {e}")

    # Extract viral shorts (OpusClip feature) & retention edits
    viral_shorts = []
    retention_edits = []
    try:
        t_text = transcript.full_text if (transcript and transcript.full_text) else video.original_filename
        viral_shorts = await extract_viral_shorts_with_gemini(t_text, video.duration or 60.0)
        retention_edits = await generate_retention_plan_with_gemini(t_text, video.duration or 60.0)
    except Exception as e:
        print(f"Retention plan extraction error: {e}")

    # Update DB
    video.ai_analysis = json.dumps(analysis)
    video.ai_title = seo_data.get("title") or video.ai_title
    video.ai_description = seo_data.get("description") or video.ai_description
    await db.commit()

    return {
        "video_id": req.video_id,
        "analysis": analysis,
        "suggestions": [],
        "title": video.ai_title,
        "description": video.ai_description,
        "viral_shorts": viral_shorts,
        "retention_edits": retention_edits
    }


@router.post("/extract-shorts")
async def extract_shorts_endpoint(
    req: AIAnalysisRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    video_stmt = select(Video).where(Video.id == req.video_id, Video.user_id == current_user.id)
    video = (await db.execute(video_stmt)).scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    transcript_stmt = select(Transcript).where(Transcript.video_id == req.video_id).order_by(Transcript.created_at.desc()).limit(1)
    transcript = (await db.execute(transcript_stmt)).scalar_one_or_none()

    t_text = transcript.full_text if (transcript and transcript.full_text) else video.original_filename
    shorts = await extract_viral_shorts_with_gemini(t_text, video.duration or 60.0)
    return {"video_id": req.video_id, "viral_shorts": shorts}


@router.post("/retention-plan")
async def retention_plan_endpoint(
    req: AIAnalysisRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    video_stmt = select(Video).where(Video.id == req.video_id, Video.user_id == current_user.id)
    video = (await db.execute(video_stmt)).scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    transcript_stmt = select(Transcript).where(Transcript.video_id == req.video_id).order_by(Transcript.created_at.desc()).limit(1)
    transcript = (await db.execute(transcript_stmt)).scalar_one_or_none()

    t_text = transcript.full_text if (transcript and transcript.full_text) else video.original_filename
    edits = await generate_retention_plan_with_gemini(t_text, video.duration or 60.0)
    return {"video_id": req.video_id, "retention_edits": edits}

from app.models.chat import ChatSession, ChatMessage
from app.schemas.ai import AIChatRequest, AIChatResponse

@router.post("/chat", response_model=AIChatResponse)
async def ai_chat(
    req: AIChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    video_context = None
    if req.video_id:
        video_stmt = select(Video).where(Video.id == req.video_id, Video.user_id == current_user.id)
        video = (await db.execute(video_stmt)).scalar_one_or_none()
        if video:
            has_transcript = False
            transcript_stmt = select(Transcript).where(Transcript.video_id == req.video_id).limit(1)
            transcript = (await db.execute(transcript_stmt)).scalar_one_or_none()
            if transcript:
                has_transcript = True
                
            video_context = {
                "filename": video.original_filename,
                "duration": video.duration,
                "width": video.width,
                "height": video.height,
                "has_transcript": has_transcript
            }

    history = None
    db_session = None
    if req.session_id:
        session_stmt = select(ChatSession).where(ChatSession.id == req.session_id, ChatSession.user_id == current_user.id)
        db_session = (await db.execute(session_stmt)).scalar_one_or_none()
        if db_session:
            msg_stmt = select(ChatMessage).where(ChatMessage.session_id == req.session_id).order_by(ChatMessage.created_at.asc())
            history = (await db.execute(msg_stmt)).scalars().all()
            
            # Save user message
            user_msg = ChatMessage(session_id=req.session_id, role="user", content=req.message)
            db.add(user_msg)
            await db.commit()

    try:
        result = await chat_with_ai(req.message, video_context, history=history)
        
        # Save AI reply
        if db_session:
            ai_msg = ChatMessage(session_id=req.session_id, role="ai", content=result["reply"])
            db_session.updated_at = ai_msg.created_at
            db.add(ai_msg)
            await db.commit()
            
        return AIChatResponse(reply=result["reply"], actions=result["actions"])
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"AI chat error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="AI service error. Please try again.")
