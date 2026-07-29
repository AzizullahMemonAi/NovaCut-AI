import httpx
import json
from app.config import settings

GROQ_API_URL = "https://api.groq.com/v1/models"


def _resolve_groq_key(api_key: str | None) -> str:
    return (api_key or settings.GROQ_API_KEY or "").strip()


def _extract_text_from_output(output: dict) -> str:
    content = output.get("content") or []
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "output_text":
                text_parts.append(item.get("text", ""))
        return "".join(text_parts)
    return ""


async def _call_groq(messages: list, model_name: str, api_key: str | None = None) -> str:
    key = _resolve_groq_key(api_key)
    if not key:
        raise Exception("Groq API key is not configured. Please provide a valid Groq API key.")

    url = f"{GROQ_API_URL}/{model_name}/outputs"
    payload = {
        "input": messages,
        "temperature": 0.2,
        "max_output_tokens": 1024
    }
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(url, json=payload, headers=headers)
        text = response.text
        if response.status_code >= 400:
            raise Exception(f"Groq request failed ({response.status_code}): {text}")

        data = response.json()
        outputs = data.get("outputs") or []
        if not outputs:
            raise Exception("Groq response did not contain any outputs.")

        return _extract_text_from_output(outputs[0])


async def analyze_transcript(transcript: str, prompt: str = None, model_name: str | None = None, api_key: str | None = None) -> dict:
    if not model_name:
        model_name = settings.GROQ_MODEL

    system_prompt = """
You are an intelligent video editing assistant. Analyze the transcript and return valid JSON only.
Do not include markdown or backticks.
"""

    base_prompt = prompt or f"""
Analyze the following video transcript.
Provide a comprehensive analysis including:
1. summary: A brief 2-3 sentence summary of the video.
2. chapters: A list of logical chapters/sections (each with a title and reasoning).
3. keywords: A list of key topics discussed.

Transcript:
{transcript}

Respond in strict JSON format like this:
{{
  "summary": "...",
  "chapters": [{{"title": "...", "reasoning": "..."}}],
  "keywords": ["...", "..."]
}}
"""

    prompt_text = f"{system_prompt}\n\n{base_prompt}"
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "output_text", "text": prompt_text}
            ]
        }
    ]
    response_text = await _call_groq(messages, model_name, api_key)
    return json.loads(response_text)


async def chat_with_ai(message: str, video_context: dict | None = None, model_name: str | None = None, api_key: str | None = None, history: list = None) -> dict:
    if not model_name:
        model_name = settings.GROQ_MODEL

    video_info = ""
    if video_context:
        video_info = f"""
Currently loaded video info:
- Filename: {video_context.get('filename', 'Unknown')}
- Duration: {video_context.get('duration', 'Unknown')} seconds
- Resolution: {video_context.get('width', '?')}x{video_context.get('height', '?')}
- Has transcript: {video_context.get('has_transcript', False)}
"""

    system_instruction = f"""
You are NovaCut AI, an intelligent video editing assistant. You help users edit their videos through natural language commands.

{video_info}

When the user asks you to perform an editing action, you MUST respond with valid JSON containing:
1. reply: A friendly, natural language response explaining what you'll do.
2. actions: A list of editing actions to perform. Each action has a type and relevant parameters.

Supported action types:
- trim: Trim video. Params: start_time (seconds), end_time (seconds)
- add_captions: Generate and add captions/subtitles. Params: none
- remove_silence: Detect and remove silent parts. Params: threshold_db (optional, default -30)
- analyze: Run AI analysis on the video. Params: none
- generate_title: Generate an AI title and description. Params: none

If the user is just chatting or asking a question (not requesting an edit), respond with an empty actions list.

IMPORTANT: Always respond with valid JSON. No markdown, no backticks.
"""

    messages = []
    if history:
        for msg in history:
            role = "user" if msg.role == "user" else "model"
            messages.append({
                "role": role,
                "content": [{"type": "output_text", "text": msg.content}]
            })
    
    messages.append({
        "role": "user",
        "content": [{"type": "output_text", "text": f"{system_instruction}\n\n{message}"}]
    })

    response_text = await _call_groq(messages, model_name, api_key)

    try:
        parsed = json.loads(response_text)
        return {
            "reply": parsed.get("reply", "I processed your request."),
            "actions": parsed.get("actions", [])
        }
    except json.JSONDecodeError:
        return {
            "reply": response_text or "Sorry, I had trouble understanding. Could you rephrase?",
            "actions": []
        }
