from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import uuid
import json

from app.database import get_db
from app.models.user import User
from app.models.project import Project
from app.models.video import Video
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse, ProjectList
from app.api.deps import get_current_user

router = APIRouter()

@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_in: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    settings_str = json.dumps(project_in.settings) if project_in.settings else None
    
    new_project = Project(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        name=project_in.name,
        description=project_in.description,
        settings=settings_str,
        status="draft"
    )
    db.add(new_project)
    await db.commit()
    await db.refresh(new_project)
    
    return ProjectResponse.from_orm_with_count(new_project, 0)

@router.get("/", response_model=ProjectList)
async def list_projects(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Get total count
    count_stmt = select(func.count(Project.id)).where(Project.user_id == current_user.id)
    total = (await db.execute(count_stmt)).scalar() or 0

    # Get projects
    stmt = select(Project).where(Project.user_id == current_user.id).order_by(Project.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    projects = result.scalars().all()
    
    # We should normally join with videos to get counts, but keeping simple for now
    projects_out = [ProjectResponse.from_orm_with_count(p, 0) for p in projects]
    
    return {
        "projects": projects_out,
        "total": total,
        "page": (skip // limit) + 1,
        "page_size": limit,
        "total_pages": (total + limit - 1) // limit if total > 0 else 0
    }

@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Project).where(Project.id == project_id, Project.user_id == current_user.id)
    project = (await db.execute(stmt)).scalar_one_or_none()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    # Get video count
    vid_count_stmt = select(func.count(Video.id)).where(Video.project_id == project_id)
    video_count = (await db.execute(vid_count_stmt)).scalar() or 0
        
    return ProjectResponse.from_orm_with_count(project, video_count)

@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    project_in: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Project).where(Project.id == project_id, Project.user_id == current_user.id)
    project = (await db.execute(stmt)).scalar_one_or_none()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    update_data = project_in.model_dump(exclude_unset=True)
    if "settings" in update_data and update_data["settings"] is not None:
        update_data["settings"] = json.dumps(update_data["settings"])
        
    for field, value in update_data.items():
        setattr(project, field, value)
        
    await db.commit()
    await db.refresh(project)
    
    # Get video count
    vid_count_stmt = select(func.count(Video.id)).where(Video.project_id == project_id)
    video_count = (await db.execute(vid_count_stmt)).scalar() or 0
        
    return ProjectResponse.from_orm_with_count(project, video_count)

@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Project).where(Project.id == project_id, Project.user_id == current_user.id)
    project = (await db.execute(stmt)).scalar_one_or_none()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    await db.delete(project)
    await db.commit()
