from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.video import Video
from app.models.transcript import Transcript
from app.schemas.processing import VideoTrimRequest, VideoMergeRequest, BurnSubtitleRequest, AutoTrimRequest, ExportShortRequest
from app.services.ffmpeg_service import trim_video, merge_videos, burn_subtitles, auto_trim_video
from app.config import settings
from app.utils.helpers import sanitize_error
import json
import os
import uuid

router = APIRouter()


@router.post("/trim")
async def trim_video_endpoint(
    req: VideoTrimRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Video).where(Video.id == req.video_id, Video.user_id == current_user.id)
    video = (await db.execute(stmt)).scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    output_filename = req.output_filename or f"trimmed_{uuid.uuid4().hex[:8]}_{video.stored_filename}"
    output_path = os.path.join(settings.OUTPUT_DIR, output_filename)  # Save to outputs so it can be streamed from /outputs

    try:
        await trim_video(video.file_path, output_path, req.start_time, req.end_time)

        # Create new video record
        file_size = os.path.getsize(output_path)
        new_video = Video(
            user_id=current_user.id,
            original_filename=f"Trimmed: {video.original_filename}",
            stored_filename=output_filename,
            file_path=output_path,
            file_size=file_size,
            mime_type=video.mime_type,
            status="completed"
        )
        db.add(new_video)
        await db.commit()
        await db.refresh(new_video)

        # We also trigger processing in background ideally, but for now we mark it completed
        return {
            "status": "success",
            "output_filename": output_filename,
            "download_url": f"{request.base_url}outputs/{output_filename}",
            "video": {
                "id": str(new_video.id),
                "original_filename": new_video.original_filename,
                "stored_filename": new_video.stored_filename,
                "file_size": new_video.file_size
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=sanitize_error(e))


@router.post("/auto-trim")
async def auto_trim_video_endpoint(
    req: AutoTrimRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Video).where(Video.id == req.video_id, Video.user_id == current_user.id)
    video = (await db.execute(stmt)).scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    output_filename = req.output_filename or f"autotrimmed_{uuid.uuid4().hex[:8]}_{video.stored_filename}"
    output_path = os.path.join(settings.OUTPUT_DIR, output_filename)  # Save to outputs so it can be streamed from /outputs

    try:
        # If start_time and end_time are provided, use manual trim instead of auto-detect
        if req.start_time is not None and req.end_time is not None:
            # Manual time-based trim
            if req.end_time <= req.start_time:
                raise HTTPException(status_code=400, detail="end_time must be greater than start_time")
            await trim_video(video.file_path, output_path, req.start_time, req.end_time)
            trim_type = "manual"
        else:
            # Auto-detect silence and trim
            await auto_trim_video(video.file_path, output_path, req.threshold_db)
            trim_type = "auto"

        file_size = os.path.getsize(output_path)
        new_video = Video(
            user_id=current_user.id,
            original_filename=f"{'Manual Trim' if trim_type == 'manual' else 'Auto-Trimmed'}: {video.original_filename}",
            stored_filename=output_filename,
            file_path=output_path,
            file_size=file_size,
            mime_type=video.mime_type,
            status="completed"
        )
        db.add(new_video)
        await db.commit()
        await db.refresh(new_video)

        return {
            "status": "success",
            "output_filename": output_filename,
            "download_url": f"{request.base_url}outputs/{output_filename}",
            "video": {
                "id": str(new_video.id),
                "original_filename": new_video.original_filename,
                "stored_filename": new_video.stored_filename,
                "file_size": new_video.file_size
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=sanitize_error(e))


@router.post("/merge")
async def merge_videos_endpoint(
    req: VideoMergeRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Video).where(Video.id.in_(req.video_ids), Video.user_id == current_user.id)
    videos = (await db.execute(stmt)).scalars().all()
    if len(videos) != len(req.video_ids):
        raise HTTPException(status_code=404, detail="One or more videos not found")

    video_map = {str(v.id): v.file_path for v in videos}
    input_paths = [video_map[vid] for vid in req.video_ids]

    output_filename = req.output_filename or f"merged_{uuid.uuid4().hex[:8]}.mp4"
    output_path = os.path.join(settings.OUTPUT_DIR, output_filename)

    try:
        await merge_videos(input_paths, output_path)
        return {
            "status": "success",
            "output_filename": output_filename,
            "download_url": f"{request.base_url}outputs/{output_filename}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=sanitize_error(e))


@router.post("/burn-subtitles")
async def burn_subtitles_endpoint(
    req: BurnSubtitleRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Video).where(Video.id == req.video_id, Video.user_id == current_user.id)
    video = (await db.execute(stmt)).scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    if not os.path.isfile(video.file_path):
        raise HTTPException(status_code=404, detail="Source video file not found on disk")

    output_filename = req.output_filename or f"subtitled_{uuid.uuid4().hex[:8]}_{video.stored_filename}"
    output_path = os.path.join(settings.OUTPUT_DIR, output_filename)

    os.makedirs(settings.TEMP_DIR, exist_ok=True)
    os.makedirs(settings.OUTPUT_DIR, exist_ok=True)

    srt_filename = f"temp_{uuid.uuid4().hex[:8]}.srt"
    srt_path = os.path.join(settings.TEMP_DIR, srt_filename)
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write(req.subtitle_text)

    try:
        await burn_subtitles(video.file_path, srt_path, output_path)
        # Create new Video record so it appears in Media Library
        file_size = os.path.getsize(output_path)
        new_video = Video(
            user_id=current_user.id,
            original_filename=f"Subtitled: {video.original_filename}",
            stored_filename=output_filename,
            file_path=output_path,
            file_size=file_size,
            mime_type=video.mime_type,
            status="completed"
        )
        db.add(new_video)
        await db.commit()
        await db.refresh(new_video)
        return {
            "status": "success",
            "output_filename": output_filename,
            "download_url": f"{request.base_url}outputs/{output_filename}",
            "video": {
                "id": str(new_video.id),
                "original_filename": new_video.original_filename,
                "stored_filename": new_video.stored_filename,
                "file_size": new_video.file_size
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=sanitize_error(e))
    finally:
        if os.path.exists(srt_path):
            os.remove(srt_path)


@router.post("/export-short")
async def export_short_endpoint(
    req: ExportShortRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Video).where(Video.id == req.video_id, Video.user_id == current_user.id)
    video = (await db.execute(stmt)).scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    if not os.path.isfile(video.file_path):
        raise HTTPException(status_code=404, detail="Source video file not found on disk")

    if req.end_time <= req.start_time:
        raise HTTPException(status_code=400, detail="end_time must be greater than start_time")

    # 1. Trim segment first
    trimmed_filename = f"short_trim_{uuid.uuid4().hex[:8]}.mp4"
    trimmed_path = os.path.join(settings.TEMP_DIR, trimmed_filename)
    os.makedirs(settings.TEMP_DIR, exist_ok=True)
    os.makedirs(settings.OUTPUT_DIR, exist_ok=True)

    try:
        await trim_video(video.file_path, trimmed_path, req.start_time, req.end_time)
    except Exception as e:
        raise HTTPException(status_code=500, detail=sanitize_error(e))

    if not os.path.isfile(trimmed_path):
        raise HTTPException(status_code=500, detail="Failed to create trimmed video segment")

    # 2. Fetch transcript and re-base segments to start at 0.0s for trimmed short
    transcript_stmt = select(Transcript).where(Transcript.video_id == req.video_id).order_by(Transcript.created_at.desc()).limit(1)
    transcript = (await db.execute(transcript_stmt)).scalar_one_or_none()

    srt_lines = []
    if transcript and transcript.segments:
        try:
            parsed = json.loads(transcript.segments) if isinstance(transcript.segments, str) else transcript.segments
            idx = 1
            for seg in parsed:
                s = float(seg.get("start", 0))
                e = float(seg.get("end", 0))
                if e > req.start_time and s < req.end_time:
                    rel_s = max(0.0, s - req.start_time)
                    rel_e = min(req.end_time - req.start_time, e - req.start_time)
                    text = seg.get("text", "").strip()
                    if text and rel_e > rel_s:
                        s_min, s_sec = divmod(rel_s, 60)
                        s_hr, s_min = divmod(s_min, 60)
                        s_ms = int((rel_s % 1) * 1000)
                        e_min, e_sec = divmod(rel_e, 60)
                        e_hr, e_min = divmod(e_min, 60)
                        e_ms = int((rel_e % 1) * 1000)

                        str_start = f"{int(s_hr):02d}:{int(s_min):02d}:{int(s_sec):02d},{s_ms:03d}"
                        str_end = f"{int(e_hr):02d}:{int(e_min):02d}:{int(e_sec):02d},{e_ms:03d}"
                        srt_lines.append(f"{idx}\n{str_start} --> {str_end}\n{text}\n")
                        idx += 1
        except Exception as err:
            print("Short transcript parsing error:", err)

    srt_content = "\n".join(srt_lines) if srt_lines else "1\n00:00:00,000 --> 00:00:05,000\n🔥 Viral Short Highlight\n"

    srt_path = os.path.join(settings.TEMP_DIR, f"short_{uuid.uuid4().hex[:8]}.srt")
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write(srt_content)

    output_filename = req.output_filename or f"viral_short_{uuid.uuid4().hex[:6]}_{video.stored_filename}"
    output_path = os.path.join(settings.OUTPUT_DIR, output_filename)

    try:
        await burn_subtitles(trimmed_path, srt_path, output_path)
        return {
            "status": "success",
            "output_filename": output_filename,
            "download_url": f"{request.base_url}outputs/{output_filename}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=sanitize_error(e))
    finally:
        for p in [trimmed_path, srt_path]:
            if os.path.exists(p):
                os.remove(p)
