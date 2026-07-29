from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
import json


class VideoMetadata(BaseModel):
    duration: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[float] = None
    codec: Optional[str] = None
    bitrate: Optional[int] = None


class VideoUploadResponse(BaseModel):
    id: str
    original_filename: str
    stored_filename: str
    file_size: int
    mime_type: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class VideoResponse(BaseModel):
    id: str
    user_id: str
    project_id: Optional[str] = None
    original_filename: str
    stored_filename: str
    file_size: int
    mime_type: str
    duration: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[float] = None
    codec: Optional[str] = None
    bitrate: Optional[int] = None
    status: str
    processing_error: Optional[str] = None
    output_path: Optional[str] = None
    output_filename: Optional[str] = None
    ai_analysis: Optional[Dict[str, Any]] = None
    ai_suggestions: Optional[Dict[str, Any]] = None
    ai_title: Optional[str] = None
    ai_description: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    processed_at: Optional[datetime] = None

    class Config:
        from_attributes = True

    @field_validator('ai_analysis', 'ai_suggestions', mode='before')
    @classmethod
    def parse_json_fields(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, ValueError, TypeError):
                return None
        return v

    @classmethod
    def from_orm_with_parsed(cls, obj):
        return cls.model_validate(obj)


class VideoUpdate(BaseModel):
    original_filename: Optional[str] = None

    class Config:
        from_attributes = True


class VideoList(BaseModel):
    videos: List[VideoResponse]
    total: int
