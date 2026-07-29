import google.generativeai as genai
from app.config import settings
import json
import asyncio
import re

def configure_gemini(api_key: str | None = None):
    key = (api_key or settings.GEMINI_API_KEY or "").strip()
    if key and key != "your-gemini-api-key-here":
        genai.configure(api_key=key)

# Call on import with environment key if available
configure_gemini()


def parse_json_from_llm(text: str) -> dict:
    if not text:
        return {}
    cleaned = text.strip()
    # Strip markdown code fences if present
    if "```" in cleaned:
        cleaned = re.sub(r"^```[a-zA-Z]*\n?", "", cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r"```$", "", cleaned, flags=re.MULTILINE).strip()
    
    try:
        return json.loads(cleaned)
    except Exception:
        # Extract content between first { and last }
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            raw_json = match.group(0)
            try:
                return json.loads(raw_json)
            except Exception:
                # Repair trailing commas before closing braces/brackets
                fixed_json = re.sub(r",\s*([\}\]])", r"\1", raw_json)
                try:
                    return json.loads(fixed_json)
                except Exception:
                    pass
        raise


async def analyze_transcript(transcript: str, prompt: str = None, api_key: str | None = None) -> dict:
    """Analyze a transcript using Gemini and return structured JSON."""
    effective_key = (api_key or settings.GEMINI_API_KEY or "").strip()
    if not effective_key or effective_key == "your-gemini-api-key-here":
        raise Exception("Gemini API key is not configured. Please set it in Settings.")
    configure_gemini(effective_key)

    system_instruction = """
    You are an AI video editing assistant. Your task is to analyze the provided video transcript and extract useful information.
    Please respond ONLY with valid JSON matching the requested structure. Do not include markdown formatting or backticks around the JSON.
    """

    default_prompt = f"""
    Analyze the following video transcript.
    Provide a comprehensive analysis including:
    1. 'summary': A brief 2-3 sentence summary of the video.
    2. 'chapters': A list of logical chapters/sections (each with a 'title' and 'reasoning').
    3. 'keywords': A list of key topics discussed.
    
    Transcript:
    {transcript}
    
    Respond in strict JSON format like this:
    {{
        "summary": "...",
        "chapters": [{{"title": "...", "reasoning": "..."}}],
        "keywords": ["...", "..."]
    }}
    """
    
    final_prompt = prompt or default_prompt

    try:
        def _call_gemini():
            model = genai.GenerativeModel(
                model_name=settings.GEMINI_MODEL,
                system_instruction=system_instruction,
                generation_config={"response_mime_type": "application/json"}
            )
            response = model.generate_content(final_prompt)
            return response.text

        result_text = await asyncio.to_thread(_call_gemini)
        return parse_json_from_llm(result_text)
    except Exception as e:
        print(f"Gemini transcript analysis warning (using fallback): {e}")
        clean_text = transcript.strip() if transcript else "Video Audio Content"
        snippet = clean_text[:60] if len(clean_text) > 60 else clean_text
        return {
            "summary": f"Transcript Summary: {clean_text[:120]}",
            "chapters": [{"title": snippet, "reasoning": clean_text}],
            "keywords": [w for w in clean_text.split() if len(w) > 3][:5]
        }


async def generate_title_description(transcript: str, video_metadata: dict = None, api_key: str | None = None) -> dict:
    """Generate SEO-optimized title and description for a video."""
    effective_key = (api_key or settings.GEMINI_API_KEY or "").strip()
    if effective_key and effective_key != "your-gemini-api-key-here":
        configure_gemini(effective_key)

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

    try:
        def _call_gemini():
            model = genai.GenerativeModel(
                model_name=settings.GEMINI_MODEL,
                generation_config={"response_mime_type": "application/json"}
            )
            response = model.generate_content(prompt)
            return response.text

        result_text = await asyncio.to_thread(_call_gemini)
        return parse_json_from_llm(result_text)
    except Exception as e:
        print(f"Gemini title generation warning (using fallback): {e}")
        clean_text = transcript.strip() if transcript else ""
        first_line = clean_text.split('.')[0] if clean_text else "Video Editing Project"
        title = (first_line[:50] + "...") if len(first_line) > 50 else (first_line or "Untitled Video")
        description = f"Video transcript: {clean_text[:200]}" if clean_text else "Media project generated with AI Editor."
        return {
            "title": title.capitalize(),
            "description": description
        }


async def chat_with_ai(message: str, video_context: dict = None, api_key: str | None = None, history: list = None) -> dict:
    """Chat with AI for video editing commands. Returns a reply and optional actions."""
    effective_key = (api_key or settings.GEMINI_API_KEY or "").strip()
    if not effective_key or effective_key == "your-gemini-api-key-here":
        raise Exception("Gemini API key is not configured. Please add your Gemini API key in the Settings page.")
    configure_gemini(effective_key)

    video_info = ""
    if video_context:
        video_info = f"""
Currently loaded video info:
- Filename: {video_context.get('filename', 'Unknown')}
- Duration: {video_context.get('duration', 'Unknown')} seconds
- Resolution: {video_context.get('width', '?')}x{video_context.get('height', '?')}
- Has transcript: {video_context.get('has_transcript', False)}
"""

    system_instruction = f"""You are NovaCut AI, an intelligent video editing assistant. You help users edit their videos through natural language commands.

{video_info}

When the user asks you to perform an editing action, you MUST respond with valid JSON containing:
1. "reply": A friendly, natural language response explaining what you'll do.
2. "actions": A list of editing actions to perform. Each action has a "type" and relevant parameters.

Supported action types:
- "trim": Trim video. Params: "start_time" (seconds), "end_time" (seconds)
- "add_captions": Generate and add captions/subtitles. Params: none
- "remove_silence": Detect and remove silent parts. Params: "threshold_db" (optional, default -30)
- "analyze": Run AI analysis on the video. Params: none
- "generate_title": Generate an AI title and description. Params: none

If the user is just chatting or asking a question (not requesting an edit), respond with an empty actions list.

IMPORTANT: Always respond with valid JSON. No markdown, no backticks.

Example response for "trim from 5 to 15 seconds":
{{
    "reply": "I'll trim your video to keep only the segment from 0:05 to 0:15. Click the action button below to apply this edit.",
    "actions": [{{"type": "trim", "start_time": 5.0, "end_time": 15.0, "label": "✂️ Trim 0:05 → 0:15"}}]
}}

Example response for "add subtitles":
{{
    "reply": "I'll generate AI-powered captions for your video. This will analyze the audio and create subtitles automatically.",
    "actions": [{{"type": "add_captions", "label": "📝 Generate Captions"}}]
}}

Example response for "hello":
{{
    "reply": "Hello! I'm NovaCut AI, your video editing assistant. I can help you trim videos, add captions, remove silence, and more. Just tell me what you'd like to do!",
    "actions": []
}}
"""

    try:
        def _call_gemini():
            model = genai.GenerativeModel(
                model_name=settings.GEMINI_MODEL,
                system_instruction=system_instruction,
                generation_config={"response_mime_type": "application/json"}
            )
            if history and len(history) > 0:
                chat = model.start_chat(history=history)
                response = chat.send_message(message)
            else:
                response = model.generate_content(message)
            return response.text
            
        result_text = await asyncio.to_thread(_call_gemini)
        parsed = parse_json_from_llm(result_text)
        return {
            "reply": parsed.get("reply", "I processed your request."),
            "actions": parsed.get("actions", [])
        }
    except Exception as e:
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


async def analyze_image_with_gemini(image_path: str, api_key: str | None = None) -> dict:
    """Analyze an image using Gemini Vision to generate a title and description."""
    effective_key = (api_key or settings.GEMINI_API_KEY or "").strip()
    if not effective_key or effective_key == "your-gemini-api-key-here":
        raise Exception("Gemini API key is not configured. Please add your Gemini API key in the Settings page.")
    configure_gemini(effective_key)
    
    prompt = """
    Analyze this image. Generate an engaging, SEO-optimized title and description for it.
    
    Respond in strict JSON format like this:
    {
        "title": "An engaging title under 60 characters",
        "description": "A compelling description containing key visual details and engaging hooks."
    }
    """
    
    try:
        def _call_gemini():
            uploaded_file = genai.upload_file(path=image_path)
            model = genai.GenerativeModel(
                model_name=settings.GEMINI_MODEL,
                generation_config={"response_mime_type": "application/json"}
            )
            response = model.generate_content([uploaded_file, prompt])
            try:
                genai.delete_file(uploaded_file.name)
            except:
                pass
            return response.text
            
        result_text = await asyncio.to_thread(_call_gemini)
        return parse_json_from_llm(result_text)
    except Exception as e:
        raise Exception(f"Gemini image analysis failed: {str(e)}")


async def analyze_video_with_gemini(video_path: str, prompt: str = None, api_key: str | None = None) -> dict:
    """Analyze a video file directly using Gemini Multimodal Vision API."""
    effective_key = (api_key or settings.GEMINI_API_KEY or "").strip()
    if not effective_key or effective_key == "your-gemini-api-key-here":
        raise Exception("Gemini API key is not configured. Please add your Gemini API key in Settings.")
    configure_gemini(effective_key)

    system_prompt = """
    You are an expert AI video editor and analyst.
    Watch and analyze this video file carefully.
    Provide a comprehensive analysis including:
    1. 'summary': A brief 2-3 sentence overview of what happens in the video.
    2. 'chapters': A list of logical visual scenes or chapters (each with 'title' and 'reasoning').
    3. 'keywords': Key topics, visual elements, and objects present in the video.
    4. 'title': An engaging, SEO-friendly video title.
    5. 'description': A compelling description summarizing the video.

    Respond ONLY in strict JSON format like this:
    {
        "summary": "...",
        "chapters": [{"title": "...", "reasoning": "..."}],
        "keywords": ["...", "..."],
        "title": "...",
        "description": "..."
    }
    """

    final_prompt = prompt or system_prompt

    try:
        def _call_gemini_video():
            import time
            uploaded_file = genai.upload_file(path=video_path)
            # Wait for file processing if state is PROCESSING
            while getattr(uploaded_file, "state", None) and getattr(uploaded_file.state, "name", "") == "PROCESSING":
                time.sleep(2)
                uploaded_file = genai.get_file(uploaded_file.name)

            model_name = settings.GEMINI_MODEL if settings.GEMINI_MODEL else "gemini-2.0-flash"
            model = genai.GenerativeModel(
                model_name=model_name,
                generation_config={"response_mime_type": "application/json"}
            )
            response = model.generate_content([uploaded_file, final_prompt])
            try:
                genai.delete_file(uploaded_file.name)
            except Exception:
                pass
            return response.text

        result_text = await asyncio.to_thread(_call_gemini_video)
        return parse_json_from_llm(result_text)
    except Exception as e:
        print(f"Gemini video file analysis warning: {e}")
        raise


async def generate_visual_subtitles_with_gemini(video_path: str, api_key: str | None = None) -> list:
    """Generate timestamped visual scene subtitles using Gemini Multimodal Vision API."""
    effective_key = (api_key or settings.GEMINI_API_KEY or "").strip()
    if not effective_key or effective_key == "your-gemini-api-key-here":
        return []
    configure_gemini(effective_key)

    prompt = """
    Watch this video carefully.
    Generate timestamped subtitle segments covering the video timeline from start to finish.
    1. If spoken speech or dialogue is present, transcribe the spoken words with start/end timestamps.
    2. If no spoken speech is present, generate clean lower-third descriptive captions of what visually occurs.

    Respond ONLY in strict JSON format matching this structure:
    {
        "segments": [
            {"id": 0, "start": 0.0, "end": 4.0, "text": "Emma, a cheerful girl with blonde pigtails, smiles at the camera."},
            {"id": 1, "start": 4.0, "end": 8.0, "text": "She poses happily with a joyful expression."}
        ]
    }
    """

    try:
        def _call_gemini_subtitles():
            import time
            uploaded_file = genai.upload_file(path=video_path)
            while getattr(uploaded_file, "state", None) and getattr(uploaded_file.state, "name", "") == "PROCESSING":
                time.sleep(2)
                uploaded_file = genai.get_file(uploaded_file.name)

            model_name = settings.GEMINI_MODEL if settings.GEMINI_MODEL else "gemini-2.0-flash"
            model = genai.GenerativeModel(
                model_name=model_name,
                generation_config={"response_mime_type": "application/json"}
            )
            response = model.generate_content([uploaded_file, prompt])
            try:
                genai.delete_file(uploaded_file.name)
            except Exception:
                pass
            return response.text

        result_text = await asyncio.to_thread(_call_gemini_subtitles)
        parsed = parse_json_from_llm(result_text)
        return parsed.get("segments", [])
    except Exception as e:
        print(f"Gemini visual subtitles generation error: {e}")
async def extract_viral_shorts_with_gemini(transcript_text: str, duration: float = 60.0, api_key: str | None = None) -> list:
    """Extract top 3 viral short segments using Gemini 2.0 Flash (OpusClip Style)."""
    effective_key = (api_key or settings.GEMINI_API_KEY or "").strip()
    if not effective_key or effective_key == "your-gemini-api-key-here":
        dur = max(5.0, float(duration or 60.0))
        return [
            {
                "viral_hook_title": "🔥 Top Highlight Hook",
                "start_time": 0.0,
                "end_time": round(min(15.0, dur), 2),
                "virality_score": 95,
                "reason": "Opening video hook and introduction segment."
            }
        ]
    configure_gemini(effective_key)

    prompt = f"""
    You are an expert social media growth strategist (OpusClip style AI editor).
    Analyze this transcript and video duration ({duration:.1f} seconds).
    Identify the top 3 most engaging, self-contained 10-to-60 second segments that would go viral on TikTok, Shorts, or Instagram Reels.

    Transcript:
    {transcript_text}

    Respond ONLY in strict JSON matching this structure:
    {{
        "viral_shorts": [
            {{
                "viral_hook_title": "Why Alexa Responded Instantly!",
                "start_time": 0.0,
                "end_time": 8.0,
                "virality_score": 98,
                "reason": "High emotional engagement and fast pacing."
            }}
        ]
    }}
    """

    try:
        def _call_gemini():
            model_name = settings.GEMINI_MODEL if (settings.GEMINI_MODEL and "3.5" not in settings.GEMINI_MODEL) else "gemini-2.0-flash"
            model = genai.GenerativeModel(
                model_name=model_name,
                generation_config={"response_mime_type": "application/json"}
            )
            response = model.generate_content(prompt)
            return response.text

        result_text = await asyncio.to_thread(_call_gemini)
        parsed = parse_json_from_llm(result_text)
        shorts = parsed.get("viral_shorts", [])
        if not shorts and isinstance(parsed, list):
            shorts = parsed
        return shorts if shorts else [
            {
                "viral_hook_title": "🔥 Best Scene Highlight",
                "start_time": 0.0,
                "end_time": round(min(15.0, float(duration or 60.0)), 2),
                "virality_score": 92,
                "reason": "Primary scene highlight segment."
            }
        ]
    except Exception as e:
        print(f"Gemini viral shorts extraction warning: {e}")
        return [
            {
                "viral_hook_title": "🔥 Featured Clip",
                "start_time": 0.0,
                "end_time": round(min(15.0, float(duration or 60.0)), 2),
                "virality_score": 88,
                "reason": "Key video highlight."
            }
        ]

from app.services.stock_service import fetch_stock_video

async def generate_retention_plan_with_gemini(transcript_text: str, duration: float = 60.0, api_key: str | None = None) -> list:
    """Analyze timestamped transcript and generate AI Retention B-roll & Zoom edit triggers."""
    effective_key = (api_key or settings.GEMINI_API_KEY or "").strip()
    dur = float(duration or 60.0)

    prompt = f"""
    You are an expert Hollywood video retention editor.
    Analyze this timestamped transcript (Video duration: {dur:.1f}s).
    Identify 2 to 4 concrete visual nouns or concepts where B-roll stock footage should cut in to illustrate the story.
    Also identify 1 to 2 high-impact emotional statements where a quick 1.2x punch-in zoom should occur.
    Return exact start and end timestamps matching the spoken words.

    Transcript:
    {transcript_text}

    Respond ONLY in strict JSON like this:
    {{
        "edits": [
            {{
                "type": "b_roll",
                "start": 2.0,
                "end": 5.5,
                "search_query": "business laptop working",
                "reasoning": "Illustrates modern productivity"
            }},
            {{
                "type": "zoom_in",
                "start": 6.0,
                "end": 7.5,
                "scale": 1.25,
                "reasoning": "Emphasizes dramatic statement"
            }}
        ]
    }}
    """

    edits = []
    if effective_key and effective_key != "your-gemini-api-key-here":
        configure_gemini(effective_key)
        try:
            def _call_gemini():
                model_name = settings.GEMINI_MODEL if (settings.GEMINI_MODEL and "3.5" not in settings.GEMINI_MODEL) else "gemini-2.0-flash"
                model = genai.GenerativeModel(
                    model_name=model_name,
                    generation_config={"response_mime_type": "application/json"}
                )
                return model.generate_content(prompt).text

            res_text = await asyncio.to_thread(_call_gemini)
            parsed = parse_json_from_llm(res_text)
            edits = parsed.get("edits", []) if isinstance(parsed, dict) else (parsed if isinstance(parsed, list) else [])
        except Exception as e:
            print(f"Gemini retention plan warning: {e}")

    # Heuristic fallback if empty
    if not edits:
        edits = [
            {
                "type": "b_roll",
                "start": round(min(2.0, dur * 0.2), 2),
                "end": round(min(5.5, dur * 0.6), 2),
                "search_query": "business technology laptop",
                "reasoning": "Visual scene overlay to maintain viewer retention."
            }
        ]

    # Resolve stock video URLs for all b_roll edits
    for item in edits:
        if item.get("type") == "b_roll" and item.get("search_query"):
            stock_data = await fetch_stock_video(item["search_query"])
            item["video_url"] = stock_data.get("video_url")
            item["source"] = stock_data.get("source")

    return edits


class GeminiClient:
    def __init__(self):
        self.model = genai.GenerativeModel(model_name=settings.GEMINI_MODEL)

def get_gemini_client():
    configure_gemini()
    return GeminiClient()
