from app.models.video import Video
from app.models.transcript import Transcript
from app.services.ffmpeg_service import get_video_metadata, extract_audio
from app.services.whisper_service import transcribe_audio
from app.services.ai_provider import analyze_transcript, generate_title_description, generate_image_description
from app.config import settings
from app.database import AsyncSessionLocal
import json
import os
import uuid
from datetime import datetime, timezone

async def process_video_pipeline(video_id: str, db=None):
    """Orchestrates the entire video processing pipeline in the background.
    
    Creates its own DB session to avoid issues with the request session
    being closed before the background task completes.
    """
    async with AsyncSessionLocal() as session:
        try:
            # 1. Fetch video record
            video = await session.get(Video, video_id)
            if not video:
                print(f"Video {video_id} not found for processing.")
                return

            video.status = "processing"
            await session.commit()

            # Branch by MIME type
            mime_type = video.mime_type or ""
            
            if mime_type.startswith("image/"):
                # IMAGE PIPELINE
                seo_data = await generate_image_description(video.file_path)
                video.ai_title = seo_data.get("title")
                video.ai_description = seo_data.get("description")
                
                # We can store a dummy transcript so the frontend doesn't break
                transcript = Transcript(
                    video_id=video_id,
                    language="en",
                    full_text="[Image Media]",
                    segments="[]",
                    status="completed"
                )
                session.add(transcript)
                
            elif mime_type.startswith("text/") or mime_type == "application/pdf" or mime_type.startswith("application/msword"):
                # TEXT PIPELINE
                # For basic text, we can just read it. (For PDF/DOCX we'd need libraries, so for now we just try to read as text or give a placeholder)
                try:
                    with open(video.file_path, "r", encoding="utf-8") as f:
                        text_content = f.read()
                except UnicodeDecodeError:
                    text_content = "[Binary Document Content]"
                    
                transcript = Transcript(
                    video_id=video_id,
                    language="en",
                    full_text=text_content,
                    segments="[]",
                    status="completed"
                )
                session.add(transcript)
                
                if text_content and text_content != "[Binary Document Content]":
                    analysis = await analyze_transcript(text_content)
                    video.ai_analysis = json.dumps(analysis)
                    seo_data = await generate_title_description(text_content, {})
                    video.ai_title = seo_data.get("title")
                    video.ai_description = seo_data.get("description")
                    
            else:
                # VIDEO / AUDIO PIPELINE
                # 2. Extract Metadata (works for audio/video)
                metadata = get_video_metadata(video.file_path)
                if metadata:
                    video.duration = metadata.get("duration")
                    video.width = metadata.get("width")
                    video.height = metadata.get("height")
                    video.fps = metadata.get("fps")
                    video.codec = metadata.get("codec")
                    video.bitrate = metadata.get("bitrate")
    
                # 3. Audio Extraction & Transcription
                if mime_type.startswith("audio/"):
                    # Use file directly
                    audio_path = video.file_path
                else:
                    # Extract from video
                    os.makedirs(settings.TEMP_DIR, exist_ok=True)
                    audio_path = os.path.join(settings.TEMP_DIR, f"{video_id}_audio.wav")
                    await extract_audio(video.file_path, audio_path)
    
                # 4. Transcribe Audio
                transcription_result = await transcribe_audio(audio_path)
                
                # Save transcript to DB
                transcript = Transcript(
                    video_id=video_id,
                    language=transcription_result.get("language", "en"),
                    full_text=transcription_result["text"],
                    segments=json.dumps(transcription_result["segments"]),
                    status="completed"
                )
                session.add(transcript)
                
                # Clean up temp audio if we created one
                if not mime_type.startswith("audio/") and os.path.exists(audio_path):
                    os.remove(audio_path)
    
                # 5. Analyze with AI
                if transcription_result.get("text"):
                    analysis = await analyze_transcript(transcription_result["text"])
                    video.ai_analysis = json.dumps(analysis)
    
                    seo_data = await generate_title_description(transcription_result["text"], metadata)
                    video.ai_title = seo_data.get("title")
                    video.ai_description = seo_data.get("description")

            # Finalize
            video.status = "completed"
            video.processed_at = datetime.now(timezone.utc)
            await session.commit()
            
        except Exception as e:
            print(f"Error processing video {video_id}: {str(e)}")
            try:
                video = await session.get(Video, video_id)
                if video:
                    video.status = "failed"
                    video.processing_error = str(e)
                    await session.commit()
            except Exception as inner_e:
                print(f"Failed to update error status for video {video_id}: {str(inner_e)}")

