from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class AIAnalysisRequest(BaseModel):
    video_id: str
    prompt: Optional[str] = None
    analysis_type: str = "comprehensive"  # comprehensive, highlights, chapters, summary


class AIAnalysisResponse(BaseModel):
    video_id: str
    analysis: Dict[str, Any]
    suggestions: List[Dict[str, Any]]
    title: Optional[str] = None
    description: Optional[str] = None
    viral_shorts: Optional[List[Dict[str, Any]]] = None
    retention_edits: Optional[List[Dict[str, Any]]] = None


class AISuggestionsResponse(BaseModel):
    video_id: str
    suggestions: List[Dict[str, Any]]


class AIChatRequest(BaseModel):
    message: str
    video_id: Optional[str] = None
    session_id: Optional[str] = None


class AIChatResponse(BaseModel):
    reply: str
    actions: List[Dict[str, Any]] = Field(default_factory=list)


class AIConfigRequest(BaseModel):
    gemini_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None


class AIStatusResponse(BaseModel):
    gemini_key_set: bool
    groq_key_set: bool
    cooldowns: Dict[str, Any]
    usage: Dict[str, Any]
