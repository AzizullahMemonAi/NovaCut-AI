import os
import magic
from pathlib import Path
from typing import BinaryIO
from app.config import settings
from app.core.exceptions import ValidationException


def validate_video_file(file: BinaryIO, filename: str) -> bool:
    """Validate video file by extension and MIME type."""
    # Check extension
    ext = Path(filename).suffix.lower()
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise ValidationException(
            f"Invalid file extension: {ext}. Allowed: {settings.ALLOWED_EXTENSIONS}"
        )

    # Check MIME type using python-magic
    file.seek(0)
    mime_type = magic.from_buffer(file.read(2048), mime=True)
    file.seek(0)

    if mime_type not in settings.ALLOWED_MEDIA_TYPES:
        raise ValidationException(
            f"Invalid file type: {mime_type}. Allowed: {settings.ALLOWED_MEDIA_TYPES}"
        )

    return True


def validate_file_size(file: BinaryIO) -> bool:
    """Validate file size."""
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)

    if size > settings.MAX_FILE_SIZE:
        raise ValidationException(
            f"File size {size} bytes exceeds maximum allowed {settings.MAX_FILE_SIZE} bytes"
        )

    if size == 0:
        raise ValidationException("File is empty")

    return True


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe storage."""
    # Remove path components
    filename = os.path.basename(filename)
    # Replace dangerous characters
    filename = "".join(c for c in filename if c.isalnum() or c in "._- ")
    # Limit length
    name, ext = os.path.splitext(filename)
    if len(name) > 200:
        name = name[:200]
    return f"{name}{ext}"
