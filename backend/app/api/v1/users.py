from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models.user import User
from app.models.project import Project
from app.models.video import Video
from app.schemas.user import UserProfile, UserUpdate, UserStats
from app.api.deps import get_current_user
from app.services.auth_service import get_password_hash, verify_password as verify_user_password

router = APIRouter()

@router.get("/me", response_model=UserProfile)
async def get_my_profile(current_user: User = Depends(get_current_user)):
    return current_user

@router.put("/me", response_model=UserProfile)
async def update_my_profile(
    user_update: UserUpdate, 
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if user_update.full_name is not None:
        current_user.full_name = user_update.full_name
    if user_update.avatar_url is not None:
        current_user.avatar_url = user_update.avatar_url
    if user_update.password is not None:
         if not user_update.current_password:
             raise HTTPException(status_code=400, detail="Current password is required to set a new password")
         if not verify_user_password(user_update.current_password, current_user.hashed_password):
             raise HTTPException(status_code=400, detail="Current password is incorrect")
         current_user.hashed_password = get_password_hash(user_update.password)
         
    await db.commit()
    await db.refresh(current_user)
    return current_user

@router.get("/me/stats", response_model=UserStats)
async def get_my_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Get project count
    proj_stmt = select(func.count(Project.id)).where(Project.user_id == current_user.id)
    proj_result = await db.execute(proj_stmt)
    total_projects = proj_result.scalar() or 0

    # Get video stats
    vid_stmt = select(
        func.count(Video.id),
        func.sum(Video.file_size)
    ).where(Video.user_id == current_user.id)
    vid_result = await db.execute(vid_stmt)
    vid_row = vid_result.one()
    
    total_videos = vid_row[0] or 0
    storage_used = vid_row[1] or 0

    return {
        "total_projects": total_projects,
        "total_videos": total_videos,
        "total_processing_time": 0.0, # Placeholder
        "storage_used": storage_used
    }
