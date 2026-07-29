from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import os
import uuid

from app.database import get_db
from app.models.user import User
from app.models.video import Video
from app.schemas.video import VideoResponse, VideoUploadResponse, VideoList, VideoUpdate
from app.api.deps import get_current_user
from app.services.file_service import save_upload_file, delete_file
from app.services.video_service import process_video_pipeline

router = APIRouter()

@router.post("/upload", response_model=VideoUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    project_id: str = Form(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # 1. Save file locally
    file_path, stored_filename = await save_upload_file(file)
    
    # 2. Create DB Record
    actual_file_size = os.path.getsize(file_path)
    video_id = str(uuid.uuid4())
    new_video = Video(
        id=video_id,
        user_id=current_user.id,
        project_id=project_id,
        original_filename=file.filename,
        stored_filename=stored_filename,
        file_path=file_path,
        file_size=actual_file_size,
        mime_type=file.content_type,
        status="uploaded"
    )
    
    db.add(new_video)
    await db.commit()
    await db.refresh(new_video)
    
    # 3. Trigger processing pipeline in background
    background_tasks.add_task(process_video_pipeline, video_id)
    
    return VideoUploadResponse.model_validate(new_video)

@router.get("/", response_model=VideoList)
async def list_videos(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Video).where(Video.user_id == current_user.id).order_by(Video.created_at.desc())
    result = await db.execute(stmt)
    videos = result.scalars().all()
    
    return VideoList(
        videos=[VideoResponse.from_orm_with_parsed(v) for v in videos],
        total=len(videos)
    )

@router.get("/{video_id}", response_model=VideoResponse)
async def get_video(
    video_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Video).where(Video.id == video_id, Video.user_id == current_user.id)
    video = (await db.execute(stmt)).scalar_one_or_none()
    
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
        
    return VideoResponse.from_orm_with_parsed(video)

@router.delete("/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_video(
    video_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Video).where(Video.id == video_id, Video.user_id == current_user.id)
    video = (await db.execute(stmt)).scalar_one_or_none()
    
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
        
    # Delete file from disk
    delete_file(video.file_path)
    if video.output_path:
        delete_file(video.output_path)
        
    await db.delete(video)
    await db.commit()

@router.put("/{video_id}", response_model=VideoResponse)
async def update_video(
    video_id: str,
    update_data: VideoUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Video).where(Video.id == video_id, Video.user_id == current_user.id)
    video = (await db.execute(stmt)).scalar_one_or_none()

    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    update_dict = update_data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(video, field, value)

    await db.commit()
    await db.refresh(video)
    return VideoResponse.from_orm_with_parsed(video)


@router.put("/{video_id}/rename", response_model=VideoResponse)
async def rename_video(
    video_id: str,
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Rename a video (original_filename)."""
    stmt = select(Video).where(Video.id == video_id, Video.user_id == current_user.id)
    video = (await db.execute(stmt)).scalar_one_or_none()

    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    new_name = (payload or {}).get("original_filename", "").strip()
    if not new_name:
        raise HTTPException(status_code=400, detail="original_filename is required")
    if len(new_name) > 255:
        raise HTTPException(status_code=400, detail="Filename too long (max 255 chars)")

    video.original_filename = new_name
    await db.commit()
    await db.refresh(video)
    return VideoResponse.from_orm_with_parsed(video)

from fastapi.responses import FileResponse
import os

@router.get("/{video_id}/download")
async def download_video(
    video_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Video).where(Video.id == video_id, Video.user_id == current_user.id)
    video = (await db.execute(stmt)).scalar_one_or_none()
    
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    # If it has an output path (processed video), download that. Otherwise, download the original.
    target_path = video.output_path if video.output_path else video.file_path

    if not target_path or not os.path.exists(target_path):
        raise HTTPException(status_code=404, detail="Video file not found on server")

    filename = os.path.basename(target_path)
    return FileResponse(target_path, media_type="video/mp4", filename=filename)


from app.config import settings as settings_config

@router.get("/outputs/all")
async def list_output_files(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    os.makedirs(settings_config.OUTPUT_DIR, exist_ok=True)
    files = os.listdir(settings_config.OUTPUT_DIR)

    output_files = []
    for f in files:
        if f.endswith(('.mp4', '.mov', '.webm', '.mkv')):
            try:
                full_path = os.path.join(settings_config.OUTPUT_DIR, f)
                size = os.path.getsize(full_path)
                output_files.append({
                    "filename": f,
                    "size": size,
                    "url": f"/outputs/{f}",
                    "created_at": os.path.getctime(full_path)
                })
            except OSError:
                continue

    # Also include videos with output_filename from DB for this user (newest processed)
    db_stmt = select(Video).where(Video.user_id == current_user.id, Video.output_filename.isnot(None))
    db_result = await db.execute(db_stmt)
    db_videos = db_result.scalars().all()

    seen = set(item["filename"] for item in output_files)
    for v in db_videos:
        if v.output_filename and v.output_filename not in seen:
            target_path = v.output_path or ""
            if target_path and os.path.exists(target_path):
                output_files.append({
                    "filename": v.output_filename,
                    "size": v.file_size or os.path.getsize(target_path),
                    "url": f"/outputs/{v.output_filename}",
                    "created_at": v.processed_at.timestamp() if v.processed_at else v.updated_at.timestamp(),
                    "video_id": str(v.id),
                    "original_filename": v.original_filename
                })
                seen.add(v.output_filename)

    output_files.sort(key=lambda x: x.get("created_at", 0), reverse=True)
    return {"outputs": output_files}
