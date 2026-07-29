from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import os
import re
import json

from app.database import get_db
from app.models.user import User
from app.models.transcript import Transcript
from app.models.video import Video
from app.schemas.transcript import TranscriptResponse
from app.api.deps import get_current_user

router = APIRouter()

@router.get("/video/{video_id}", response_model=List[TranscriptResponse])
async def get_video_transcripts(
    video_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Check if video belongs to user
    video_stmt = select(Video).where(Video.id == video_id, Video.user_id == current_user.id)
    video = (await db.execute(video_stmt)).scalar_one_or_none()
    
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    stmt = select(Transcript).where(Transcript.video_id == video_id)
    result = await db.execute(stmt)
    transcripts = result.scalars().all()
    
    # Parse the segments JSON string before returning and clean foreign script hallucinations
    res = []
    for t in transcripts:
        t_dict = t.__dict__.copy()
        if isinstance(t_dict.get("segments"), str):
            try:
                raw_segs = json.loads(t_dict["segments"])
                clean_segs = []
                for s in raw_segs:
                    if isinstance(s, dict):
                        txt = s.get("text", "")
                        clean_txt = re.sub(r'[\u3000-\u9fff\uac00-\ud7af]', '', txt).strip()
                        s["text"] = clean_txt if clean_txt else "speech"
                        clean_segs.append(s)
                t_dict["segments"] = clean_segs
            except (json.JSONDecodeError, ValueError, TypeError):
                t_dict["segments"] = []
        res.append(TranscriptResponse.model_validate(t_dict))
        
    return res

@router.get("/{transcript_id}", response_model=TranscriptResponse)
async def get_transcript(
    transcript_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Transcript).join(Video).where(
        Transcript.id == transcript_id,
        Video.user_id == current_user.id
    )
    transcript = (await db.execute(stmt)).scalar_one_or_none()
    
    if not transcript:
        raise HTTPException(status_code=404, detail="Transcript not found")
        
    t_dict = transcript.__dict__.copy()
    if isinstance(t_dict.get("segments"), str):
        try:
            t_dict["segments"] = json.loads(t_dict["segments"])
        except (json.JSONDecodeError, ValueError, TypeError):
            t_dict["segments"] = []
            
    return TranscriptResponse.model_validate(t_dict)


from app.services.whisper_service import transcribe_audio
from app.services.ffmpeg_service import extract_audio
from app.config import settings
import re

@router.post("/retranscribe/{video_id}", response_model=TranscriptResponse)
async def retranscribe_video(
    video_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    video_stmt = select(Video).where(Video.id == video_id, Video.user_id == current_user.id)
    video = (await db.execute(video_stmt)).scalar_one_or_none()
    if not video or not video.file_path or not os.path.exists(video.file_path):
        raise HTTPException(status_code=404, detail="Video file not found")

    os.makedirs(settings.TEMP_DIR, exist_ok=True)
    audio_path = os.path.join(settings.TEMP_DIR, f"{video_id}_audio.wav")
    await extract_audio(video.file_path, audio_path)

    res = await transcribe_audio(audio_path, language="en")
    if os.path.exists(audio_path):
        os.remove(audio_path)

    clean_text = re.sub(r'[\u3000-\u9fff\uac00-\ud7af]', '', res.get("text", "")).strip()

    stmt = select(Transcript).where(Transcript.video_id == video_id)
    transcript = (await db.execute(stmt)).scalars().first()
    if not transcript:
        transcript = Transcript(video_id=video_id)

    transcript.language = "en"
    transcript.full_text = clean_text or "speech audio"
    transcript.segments = json.dumps(res.get("segments", []))
    transcript.status = "completed"
    
    db.add(transcript)
    await db.commit()
    await db.refresh(transcript)

    t_dict = transcript.__dict__.copy()
    t_dict["segments"] = res.get("segments", [])
    return TranscriptResponse.model_validate(t_dict)
