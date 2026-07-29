from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime
import json


class ProjectBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    settings: Optional[dict] = None


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    status: Optional[str] = Field(None, pattern="^(draft|processing|completed|failed)$")
    settings: Optional[dict] = None


class ProjectResponse(ProjectBase):
    id: str
    user_id: str
    status: str
    settings: Optional[dict] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    video_count: int = 0

    class Config:
        from_attributes = True

    @field_validator('settings', mode='before')
    @classmethod
    def parse_settings(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, ValueError, TypeError):
                return None
        return v

    @classmethod
    def from_orm_with_count(cls, obj, video_count: int = 0):
        data = cls.model_validate(obj)
        data.video_count = video_count
        return data


class ProjectList(BaseModel):
    projects: List[ProjectResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
