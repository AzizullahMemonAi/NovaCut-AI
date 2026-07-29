from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class VideoProcessRequest(BaseModel):
    video_id: str
    operations: List[Dict[str, Any]] = Field(default_factory=list)  # trim, merge, subtitles, etc.
    output_settings: Optional[Dict[str, Any]] = None


class VideoTrimRequest(BaseModel):
    video_id: str
    start_time: float = Field(..., ge=0)
    end_time: float = Field(..., gt=0)
    output_filename: Optional[str] = None


class VideoMergeRequest(BaseModel):
    video_ids: List[str] = Field(..., min_length=2)
    output_filename: Optional[str] = None
    transition: Optional[str] = "none"  # none, fade, crossfade

class BurnSubtitleRequest(BaseModel):
    video_id: str
    subtitle_text: str  # The raw SRT content, or we could pass transcript_id. Let's accept SRT text for flexibility.
    output_filename: Optional[str] = None

class AutoTrimRequest(BaseModel):
    video_id: str
    start_time: Optional[float] = Field(None, ge=0)  # Manual trim start (optional - if not provided, uses auto-detect)
    end_time: Optional[float] = Field(None, gt=0)  # Manual trim end (optional - if not provided, uses auto-detect)
    threshold_db: int = -30  # Auto-detect threshold for silence detection
    output_filename: Optional[str] = None

class ExportShortRequest(BaseModel):
    video_id: str
    start_time: float = Field(..., ge=0)
    end_time: float = Field(..., gt=0)
    hook_title: Optional[str] = None
    output_filename: Optional[str] = None
