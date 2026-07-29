import json
from datetime import datetime, timezone
from app.config import settings
from app.services.gemini_service import analyze_transcript as gemini_analyze, generate_title_description as gemini_generate_title_description, chat_with_ai as gemini_chat, analyze_image_with_gemini, analyze_video_with_gemini
from app.services.groq_service import analyze_transcript as groq_analyze, chat_with_ai as groq_chat
from app.services.runtime_config import get_api_keys, save_cooldown, is_in_cooldown, get_cooldown_status, increment_usage, get_usage_status

PROVIDER_GEMINI = 'gemini'
PROVIDER_GROQ = 'groq'


async def analyze_video_media(video_path: str, prompt: str = None) -> dict:
    keys = get_api_keys()
    gemini_key = keys.get('gemini_api_key')

    if gemini_key:
        try:
            res = await analyze_video_with_gemini(video_path, prompt, api_key=gemini_key)
            if res and isinstance(res, dict):
                increment_usage(PROVIDER_GEMINI)
                return res
        except Exception as exc:
            print(f"Gemini video file analysis warning: {exc}")

    return {}


async def analyze_transcript(transcript: str, prompt: str = None) -> dict:
    keys = get_api_keys()
    gemini_key = keys.get('gemini_api_key')
    groq_key = keys.get('groq_api_key')

    if gemini_key:
        try:
            res = await gemini_analyze(transcript, prompt, api_key=gemini_key)
            if res and isinstance(res, dict):
                increment_usage(PROVIDER_GEMINI)
                return res
        except Exception as exc:
            print(f"Gemini provider analysis warning: {exc}")

    if groq_key:
        try:
            res = await groq_analyze(transcript, prompt, model_name=settings.GROQ_MODEL, api_key=groq_key)
            if res and isinstance(res, dict):
                increment_usage(PROVIDER_GROQ)
                return res
        except Exception as exc:
            print(f"Groq provider analysis warning: {exc}")

    # Fallback to local intelligent transcript analysis
    clean_text = transcript.strip() if transcript else ""
    words = clean_text.split()
    summary_excerpt = " ".join(words[:30]) + ("..." if len(words) > 30 else "") if words else "Video content processed."
    unique_words = list(dict.fromkeys([w.strip(".,!?\"'").capitalize() for w in words if len(w) > 4]))[:5]
    keywords = unique_words if unique_words else ["Video", "Speech", "Audio"]

    return {
        "summary": f"Video Overview: {summary_excerpt}",
        "chapters": [
            {"title": "00:00 - Main Content", "reasoning": "Speech and dialogue audio segment."}
        ],
        "keywords": keywords
    }


async def generate_image_description(image_path: str) -> dict:
    keys = get_api_keys()
    gemini_key = keys.get('gemini_api_key')

    if gemini_key:
        try:
            res = await analyze_image_with_gemini(image_path, api_key=gemini_key)
            if res and isinstance(res, dict):
                increment_usage(PROVIDER_GEMINI)
                return res
        except Exception as exc:
            print(f"Gemini image analysis warning: {exc}")

    return {
        "title": "Image Media",
        "description": "An image uploaded to the media library."
    }


async def generate_title_description(transcript: str, video_metadata: dict = None) -> dict:
    keys = get_api_keys()
    gemini_key = keys.get('gemini_api_key')
    groq_key = keys.get('groq_api_key')

    if gemini_key:
        try:
            res = await gemini_generate_title_description(transcript, video_metadata, api_key=gemini_key)
            if res and isinstance(res, dict):
                increment_usage(PROVIDER_GEMINI)
                return res
        except Exception as exc:
            print(f"Gemini title generation warning: {exc}")

    if groq_key:
        try:
            prompt = f"""
Generate an engaging, SEO-optimized title and description for a video based on its transcript.

Transcript:
{transcript}

Metadata:
{video_metadata or 'None provided'}

Respond in strict JSON format like this:
{{
  "title": "An engaging title under 60 characters",
  "description": "A compelling description containing key topics and engaging hooks."
}}
"""
            res = await groq_analyze(transcript, prompt, model_name=settings.GROQ_MODEL, api_key=groq_key)
            if res and isinstance(res, dict):
                increment_usage(PROVIDER_GROQ)
                return res
        except Exception as exc:
            print(f"Groq title generation warning: {exc}")

    clean_text = transcript.strip() if transcript else ""
    first_line = clean_text.split('.')[0] if clean_text else "Video Project"
    title = (first_line[:50] + "...") if len(first_line) > 50 else (first_line or "Untitled Video")
    description = f"Video transcript: {clean_text[:200]}" if clean_text else "Media project created with AI Video Editor."
    return {
        "title": title.capitalize(),
        "description": description
    }


async def chat_with_ai(message: str, video_context: dict = None, history: list = None) -> dict:
    keys = get_api_keys()
    gemini_key = keys.get('gemini_api_key')
    groq_key = keys.get('groq_api_key')

    if gemini_key:
        try:
            res = await gemini_chat(message, video_context, api_key=gemini_key, history=history)
            if res and isinstance(res, dict):
                increment_usage(PROVIDER_GEMINI)
                return res
        except Exception as exc:
            print(f"Gemini chat warning: {exc}")

    if groq_key:
        try:
            res = await groq_chat(message, video_context, model_name=settings.GROQ_MODEL, api_key=groq_key, history=history)
            if res and isinstance(res, dict):
                increment_usage(PROVIDER_GROQ)
                return res
        except Exception as exc:
            print(f"Groq chat warning: {exc}")

    # Fallback response for chat
    msg_lower = (message or "").lower()
    if "subtitle" in msg_lower or "caption" in msg_lower or "transcrib" in msg_lower:
        return {
            "reply": "I'll generate AI-powered captions for your video. This will analyze the audio and create subtitles automatically.",
            "actions": [{"type": "add_captions", "label": "📝 Generate Captions"}]
        }
    elif "trim" in msg_lower or "cut" in msg_lower:
        return {
            "reply": "I can help you trim your video. Specify start and end times or click trim below.",
            "actions": [{"type": "trim", "start_time": 0, "end_time": 10, "label": "✂️ Trim Video"}]
        }
    elif "summar" in msg_lower or "analyz" in msg_lower or "highlight" in msg_lower:
        return {
            "reply": "I'll analyze your video transcript and generate a summary with key insights.",
            "actions": [{"type": "analyze", "label": "✨ Run AI Analysis"}]
        }
    elif "title" in msg_lower or "description" in msg_lower:
        return {
            "reply": "I'll generate an engaging title and description for your video.",
            "actions": [{"type": "generate_title", "label": "✨ Generate Title & Description"}]
        }

    return {
        "reply": "I'm ready to help you edit your video! You can ask me to generate subtitles, trim clips, remove silence, or summarize the transcript.",
        "actions": []
    }


def get_fallback_status() -> dict:
    status = get_cooldown_status()
    keys = get_api_keys()
    return {
        'gemini_key_set': bool(keys.get('gemini_api_key')),
        'groq_key_set': bool(keys.get('groq_api_key')),
        'cooldowns': status,
        'usage': get_usage_status()
    }
