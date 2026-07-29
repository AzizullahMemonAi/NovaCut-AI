from fastapi import APIRouter, Depends, HTTPException
from app.schemas.ai import AIConfigRequest, AIStatusResponse
from app.services.runtime_config import save_api_keys
from app.services.ai_provider import get_fallback_status
from app.api.deps import get_current_user

router = APIRouter()

@router.post("/ai-config", response_model=AIStatusResponse)
async def save_ai_config_endpoint(
    config: AIConfigRequest,
    current_user = Depends(get_current_user)
):
    if config.gemini_api_key is None and config.groq_api_key is None:
        raise HTTPException(status_code=400, detail="At least one API key must be provided.")

    save_api_keys(config.gemini_api_key or "", config.groq_api_key or "")
    return get_fallback_status()

@router.get("/ai-status", response_model=AIStatusResponse)
async def get_ai_status_endpoint(current_user = Depends(get_current_user)):
    return get_fallback_status()
