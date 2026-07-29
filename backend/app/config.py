from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
import os
import shutil
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    # App
    APP_NAME: str = "AI Video Editor API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///" + os.path.join(BASE_DIR, 'app.db').replace('\\', '/')

    # Security
    SECRET_KEY: str = Field(default="changeme-use-strong-random-key-in-production-min-32-chars", min_length=32)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # File Storage
    UPLOAD_DIR: str = os.path.join(BASE_DIR, "uploads")
    OUTPUT_DIR: str = os.path.join(BASE_DIR, "outputs")
    TEMP_DIR: str = os.path.join(BASE_DIR, "temp")
    MAX_FILE_SIZE: int = 2147483648  # 2GB
    ALLOWED_MEDIA_TYPES: List[str] = [
        "video/mp4", "video/quicktime", "video/x-msvideo", "video/x-matroska",
        "video/mpeg", "video/ogg", "video/webm", "video/x-ms-wmv", 
        "audio/mpeg", "audio/mp3", "audio/wav", "audio/x-wav", "audio/aac", "audio/ogg", "audio/flac",
        "image/jpeg", "image/png", "image/gif", "image/webp", "image/bmp", "image/svg+xml", "image/tiff", "image/x-icon",
        "text/plain", "text/csv", "application/pdf", "application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ]
    ALLOWED_EXTENSIONS: List[str] = [
        ".mp4", ".mov", ".avi", ".mkv", ".webm", ".mpe", ".mpeg", ".ogm", ".mpg", ".wmv", ".ogv", ".m4v", ".asx",
        ".mp3", ".wav", ".aac", ".flac", ".ogg", ".m4a",
        ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg", ".tiff", ".ico",
        ".txt", ".csv", ".pdf", ".doc", ".docx"
    ]

    # Google Gemini
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"

    # Google OAuth
    GOOGLE_CLIENT_ID: str = ""

    # Groq API
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama3-70b-8192"

    # Whisper
    WHISPER_MODEL: str = "base"
    WHISPER_DEVICE: str = "cpu"

    # FFmpeg (Dynamically resolve for Linux/Render support)
    FFMPEG_PATH: str = os.getenv("FFMPEG_PATH", shutil.which("ffmpeg") or "ffmpeg")
    FFPROBE_PATH: str = os.getenv("FFPROBE_PATH", shutil.which("ffprobe") or "ffprobe")

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
