import os
import shutil
import aiofiles
from fastapi import UploadFile, HTTPException, status
from app.config import settings
import uuid
import mimetypes

# Ensure directories exist
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
os.makedirs(settings.TEMP_DIR, exist_ok=True)

async def save_upload_file(upload_file: UploadFile, directory: str = settings.UPLOAD_DIR) -> str:
    """Save an uploaded file and return the stored file path."""
    if upload_file.size is not None and upload_file.size > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Max size is {settings.MAX_FILE_SIZE / (1024 * 1024)}MB."
        )

    # Basic type checking (in production, use python-magic for true MIME detection)
    if upload_file.content_type not in settings.ALLOWED_MEDIA_TYPES:
        # Also allow if it's a generic text, image, or audio type
        content_type = upload_file.content_type or ""
        if not (content_type.startswith("image/") or content_type.startswith("audio/") or content_type.startswith("text/") or content_type.startswith("video/")):
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"Unsupported file type. Allowed types: {', '.join(settings.ALLOWED_MEDIA_TYPES)}"
            )

    ext = os.path.splitext(upload_file.filename)[1].lower()
    if not ext:
        # guess from mime type
        ext = mimetypes.guess_extension(upload_file.content_type) or ".mp4"
        
    if ext not in settings.ALLOWED_EXTENSIONS:
         raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file extension. Allowed extensions: {', '.join(settings.ALLOWED_EXTENSIONS)}"
        )

    stored_filename = f"{uuid.uuid4()}{ext}"
    file_path = os.path.join(directory, stored_filename)

    try:
        async with aiofiles.open(file_path, 'wb') as out_file:
            total_written = 0
            while content := await upload_file.read(1024 * 1024):  # 1MB chunks
                total_written += len(content)
                if total_written > settings.MAX_FILE_SIZE:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File too large. Max size is {settings.MAX_FILE_SIZE / (1024 * 1024)}MB."
                    )
                await out_file.write(content)
    except HTTPException:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Could not save file: {e}", exc_info=True)
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail="Could not save file. Please try again.")

    return file_path, stored_filename

def delete_file(file_path: str) -> bool:
    """Delete a file from the filesystem."""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
        return False
    except Exception as e:
        print(f"Error deleting file {file_path}: {e}")
        return False

def get_file_metadata(file_path: str) -> dict:
    """Get basic file metadata."""
    if not os.path.exists(file_path):
        return {}
    
    stat = os.stat(file_path)
    return {
        "size": stat.st_size,
        "created_at": stat.st_ctime,
        "modified_at": stat.st_mtime
    }
