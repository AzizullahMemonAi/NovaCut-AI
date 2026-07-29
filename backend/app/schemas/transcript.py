from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class TranscriptSegment(BaseModel):
    id: int
    start: float
    end: float
    text: str
    confidence: Optional[float] = None


class TranscriptResponse(BaseModel):
    id: str
    video_id: str
    language: str
    full_text: str
    segments: List[TranscriptSegment]
    srt_path: Optional[str] = None
    vtt_path: Optional[str] = None
    duration: Optional[float] = None
    word_count: Optional[int] = None
    confidence: Optional[float] = None
    status: str
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TranscriptGenerateRequest(BaseModel):
    video_id: str
    language: Optional[str] = "en"
    model: Optional[str] = "base"  # tiny, base, small, medium, large
