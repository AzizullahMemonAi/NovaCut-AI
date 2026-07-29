import os
import json
import asyncio
import re
import wave
import speech_recognition as sr
import ffmpeg

try:
    import google.generativeai as genai
except ImportError:
    genai = None

try:
    import whisper
except ImportError:
    whisper = None

from app.config import settings

# Inject FFmpeg directory into system PATH so local whisper can invoke ffmpeg.exe
ffmpeg_dir = os.path.dirname(settings.FFMPEG_PATH)
if os.path.exists(ffmpeg_dir) and ffmpeg_dir not in os.environ["PATH"]:
    os.environ["PATH"] = ffmpeg_dir + os.path.pathsep + os.environ["PATH"]

_whisper_model = None

def get_whisper_model():
    global _whisper_model
    if _whisper_model is None and whisper is not None:
        try:
            model_name = getattr(settings, "WHISPER_MODEL", "tiny")
            device = getattr(settings, "WHISPER_DEVICE", "cpu")
            _whisper_model = whisper.load_model(model_name, device=device)
        except Exception as e:
            print(f"Error loading whisper model: {e}")
            _whisper_model = None
    return _whisper_model

def configure_gemini():
    if genai and settings.GEMINI_API_KEY and settings.GEMINI_API_KEY != "your-gemini-api-key-here":
        try:
            genai.configure(api_key=settings.GEMINI_API_KEY)
        except Exception:
            pass

def _format_timestamp(seconds: float) -> str:
    """Format seconds into SRT timestamp format: HH:MM:SS,mmm"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"

def generate_srt_from_segments(segments: list) -> str:
    """Converts a list of whisper segment dicts into an SRT formatted string."""
    srt_content = []
    for i, segment in enumerate(segments, start=1):
        start_time = _format_timestamp(segment["start"])
        end_time = _format_timestamp(segment["end"])
        text = segment["text"].strip()
        srt_content.append(f"{i}\n{start_time} --> {end_time}\n{text}\n")
    return "\n".join(srt_content)

def format_chunk(word_list, min_duration=0.20):
    start = word_list[0]['start']
    end = word_list[-1]['end']
    text = " ".join([w['word'].strip() for w in word_list])
    
    # Enforce minimum readability duration
    if (end - start) < min_duration:
        end = start + min_duration
        
    # Subtract 10ms (0.01s) from end timestamp to prevent collision with next block
    end = max(start + 0.01, end - 0.01)
    
    return {
        "start": round(start, 3),
        "end": round(end, 3),
        "text": text
    }

def build_lossless_tiktok_chunks(words, max_words=3, max_cps=22.0, min_duration=0.20):
    """
    Groups word-level timestamps into short-form subtitles without ever dropping a word.
    """
    chunks = []
    current_chunk = []
    
    for word_data in words:
        word_text = word_data['word'].strip()
        if not word_text:
            continue
            
        # Try adding the word to the current bucket
        test_chunk = current_chunk + [word_data]
        test_text = " ".join([w['word'].strip() for w in test_chunk])
        
        start_time = test_chunk[0]['start']
        end_time = test_chunk[-1]['end']
        duration = max(end_time - start_time, 0.01)
        
        # Calculate CPS
        cps = len(test_text) / duration
        
        # Check if adding this word violates TikTok constraints
        words_limit_reached = len(test_chunk) > max_words
        cps_limit_reached = cps > max_cps and len(current_chunk) > 0
        
        if words_limit_reached or cps_limit_reached:
            # Commit the current chunk and start a new one with the target word
            formatted = format_chunk(current_chunk, min_duration)
            formatted["id"] = len(chunks)
            chunks.append(formatted)
            current_chunk = [word_data]
        else:
            current_chunk = test_chunk
            
    # Commit any leftovers
    if current_chunk:
        formatted = format_chunk(current_chunk, min_duration)
        formatted["id"] = len(chunks)
        chunks.append(formatted)
        
    return chunks


async def transcribe_audio(audio_path: str, language: str = "en") -> dict:
    """
    Transcribes actual audio file using Whisper, SpeechRecognition, or Gemini.
    """
    if not os.path.exists(audio_path):
        return {
            "text": "Audio file not found.",
            "language": "en",
            "segments": []
        }

    # 1. Try OpenAI Whisper (if loaded/available)
    if whisper is not None:
        try:
            def _whisper_transcribe():
                model = get_whisper_model()
                if model:
                    target_lang = language if (language and language != "auto") else "en"
                    kwargs = {"word_timestamps": True, "language": target_lang}
                    result = model.transcribe(audio_path, **kwargs)
                    
                    # Extract raw word-level timestamps without any probability/confidence filtering
                    all_words = []
                    for seg in result.get("segments", []):
                        for w in seg.get("words", []):
                            w_text = w.get("word", "").strip()
                            if w_text:
                                all_words.append({
                                    "word": w_text,
                                    "start": float(w.get("start", 0)),
                                    "end": float(w.get("end", 0))
                                })

                    segments = []
                    if all_words:
                        segments = build_lossless_tiktok_chunks(all_words, max_words=3, max_cps=22.0, min_duration=0.20)
                    else:
                        for i, seg in enumerate(result.get("segments", [])):
                            if seg.get("text", "").strip():
                                segments.append({
                                    "id": i,
                                    "start": round(float(seg["start"]), 2),
                                    "end": round(float(seg["end"]), 2),
                                    "text": seg["text"].strip()
                                })

                    return {
                        "text": result.get("text", "").strip(),
                        "language": result.get("language", language or "en"),
                        "segments": segments
                    }
                return None

            res = await asyncio.to_thread(_whisper_transcribe)
            if res and res.get("text"):
                return res
        except Exception as e:
            print(f"Whisper transcription exception: {e}")

    # Ensure we have a 16kHz PCM WAV audio file for SpeechRecognition fallback
    wav_path = audio_path
    temp_wav_created = False
    if not audio_path.lower().endswith(".wav"):
        temp_wav_path = audio_path + ".temp.wav"
        try:
            process = (
                ffmpeg
                .input(audio_path)
                .filter('highpass', f=80)
                .filter('lowpass', f=7500)
                .filter('loudnorm')
                .output(temp_wav_path, acodec="pcm_s16le", ar=16000, ac=1)
                .overwrite_output()
                .run_async(cmd=settings.FFMPEG_PATH, pipe_stdout=True, pipe_stderr=True)
            )
            await asyncio.to_thread(process.communicate)
            if os.path.exists(temp_wav_path):
                wav_path = temp_wav_path
                temp_wav_created = True
        except Exception as e:
            print(f"Error converting audio to WAV for SpeechRecognition: {e}")

    # 2. Try SpeechRecognition with audio chunking for synced subtitles
    try:
        def _sr_transcribe(wpath):
            r = sr.Recognizer()
            segments = []
            full_text_parts = []

            with wave.open(wpath, "rb") as wf:
                framerate = wf.getframerate()
                nframes = wf.getnframes()
                total_duration = nframes / float(framerate)
                sampwidth = wf.getsampwidth()
                nchannels = wf.getnchannels()

                chunk_dur = 3.0
                frames_per_chunk = int(framerate * chunk_dur)
                current_frame = 0
                seg_id = 0

                while current_frame < nframes:
                    start_time = current_frame / float(framerate)
                    wf.setpos(current_frame)
                    raw_bytes = wf.readframes(frames_per_chunk)
                    if not raw_bytes:
                        break

                    actual_frames = len(raw_bytes) // (sampwidth * nchannels)
                    end_time = min((current_frame + actual_frames) / float(framerate), total_duration)

                    audio_data = sr.AudioData(raw_bytes, framerate, sampwidth)
                    try:
                        text = r.recognize_google(audio_data)
                        clean_t = text.strip()
                        if clean_t:
                            segments.append({
                                "id": seg_id,
                                "start": round(start_time, 2),
                                "end": round(end_time, 2),
                                "text": clean_t
                            })
                            full_text_parts.append(clean_t)
                            seg_id += 1
                    except Exception:
                        pass
                    current_frame += frames_per_chunk

            if full_text_parts:
                return {
                    "text": " ".join(full_text_parts),
                    "language": "en",
                    "segments": segments
                }
            return None

        sr_res = await asyncio.to_thread(_sr_transcribe, wav_path)
        if temp_wav_created and os.path.exists(wav_path):
            try:
                os.remove(wav_path)
            except Exception:
                pass
        if sr_res:
            return sr_res
    except Exception as e:
        print(f"SpeechRecognition fallback error: {e}")
        if temp_wav_created and os.path.exists(wav_path):
            try:
                os.remove(wav_path)
            except Exception:
                pass

    # 3. Try Gemini Multimodal API if key exists
    if genai and settings.GEMINI_API_KEY and settings.GEMINI_API_KEY != "your-gemini-api-key-here":
        configure_gemini()
        prompt = """
You are an expert, high-precision verbatim English audio transcriber.
Listen to this audio track with extreme 100% accuracy.

CRITICAL INSTRUCTIONS FOR VERBATIM ACCURACY:
1. Capture EVERY SINGLE SPOKEN WORD. Do NOT drop, skip, summarize, or paraphrase short words like "hi", "I", "see", "it", "alexa", "a", "the", "and", "to".
2. Output the EXACT verbatim spoken transcript in 'full_text'.
3. Divide the spoken transcript into short, natural 3-5 word subtitle phrases with tight start and end timestamps in seconds.
4. Ensure start and end timestamps match when each word is spoken.

Respond ONLY with strict JSON matching this structure:
{
    "full_text": "hi Alexa I see it",
    "language": "en",
    "segments": [
        {"id": 0, "start": 0.3, "end": 1.5, "text": "hi Alexa"},
        {"id": 1, "start": 1.6, "end": 2.8, "text": "I see it"}
    ]
}
"""
        try:
            def _transcribe_with_gemini():
                uploaded = genai.upload_file(path=audio_path)
                model_name = settings.GEMINI_MODEL if settings.GEMINI_MODEL and "3.5" not in settings.GEMINI_MODEL else "gemini-2.0-flash"
                model = genai.GenerativeModel(
                    model_name=model_name,
                    generation_config={"response_mime_type": "application/json"}
                )
                response = model.generate_content([uploaded, prompt])
                try:
                    genai.delete_file(uploaded.name)
                except Exception:
                    pass
                return response.text

            raw_text = await asyncio.to_thread(_transcribe_with_gemini)
            cleaned = raw_text.strip()
            if "```" in cleaned:
                cleaned = re.sub(r"^```[a-zA-Z]*\n?", "", cleaned, flags=re.MULTILINE)
                cleaned = re.sub(r"```$", "", cleaned, flags=re.MULTILINE).strip()
            parsed = json.loads(cleaned)

            return {
                "text": parsed.get("full_text") or parsed.get("text") or "Audio content transcribed.",
                "language": parsed.get("language", "en"),
                "segments": parsed.get("segments", [])
            }
        except Exception as e:
            print(f"Gemini audio transcription error: {e}")

    return {
        "text": "No speech detected in audio track.",
        "language": "en",
        "segments": []
    }

