import os
import uuid
import shutil
import asyncio
from pathlib import Path
from typing import Optional, Tuple
from datetime import timedelta

from app.config import settings


def format_duration(seconds: float) -> str:
    """Format duration in seconds to HH:MM:SS.mmm"""
    td = timedelta(seconds=seconds)
    hours, remainder = divmod(td.total_seconds(), 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{int(hours):02d}:{int(minutes):02d}:{seconds:06.3f}"


def format_file_size(bytes_size: int) -> str:
    """Format file size in human readable format."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} PB"


def generate_unique_filename(original_filename: str, prefix: str = "") -> str:
    """Generate a unique filename preserving extension."""
    ext = Path(original_filename).suffix.lower()
    unique_id = uuid.uuid4().hex[:12]
    prefix_part = f"{prefix}_" if prefix else ""
    return f"{prefix_part}{unique_id}{ext}"


def ensure_dir(path: str) -> Path:
    """Ensure directory exists."""
    path_obj = Path(path)
    path_obj.mkdir(parents=True, exist_ok=True)
    return path_obj


def safe_delete_file(filepath: str) -> bool:
    """Safely delete a file if it exists."""
    try:
        path = Path(filepath)
        if path.exists() and path.is_file():
            path.unlink()
            return True
    except Exception:
        pass
    return False


async def run_async_command(cmd: list, cwd: Optional[str] = None) -> Tuple[int, str, str]:
    """Run command asynchronously and return (returncode, stdout, stderr)."""
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
    )
    stdout, stderr = await proc.communicate()
    return proc.returncode, stdout.decode(), stderr.decode()


def sanitize_error(e: Exception) -> str:
    """Return a generic error message, logging the full detail server-side."""
    import logging
    logger = logging.getLogger(__name__)
    logger.error(f"Internal error: {e}", exc_info=True)
    return "An internal error occurred. Please try again later."


def parse_ffprobe_output(output: str) -> dict:
    """Parse ffprobe JSON output."""
    import json
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        return {}


async def get_video_duration(filepath: str) -> Optional[float]:
    """Get video duration using ffprobe."""
    cmd = [
        settings.FFPROBE_PATH, "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        filepath
    ]
    returncode, stdout, stderr = await run_async_command(cmd)
    if returncode == 0:
        try:
            return float(stdout.strip())
        except ValueError:
            pass
    return None
