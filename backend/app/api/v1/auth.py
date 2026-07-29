from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timezone, timedelta
from collections import defaultdict
import uuid

from app.database import get_db
from app.models.user import User
from app.schemas.auth import Token, UserCreate, UserResponse, RefreshTokenRequest
from app.services.auth_service import verify_password, get_password_hash, create_access_token, create_refresh_token, decode_token
from app.config import settings

router = APIRouter()

# NOTE: Rate limiting is in-memory only and resets on server restart.
# For production, use Redis or similar distributed store.
_login_attempts = defaultdict(list)

def _check_rate_limit(key: str, max_attempts: int = 10, window_seconds: int = 60):
    now = datetime.now(timezone.utc)
    timestamps = _login_attempts[key]
    cutoff = now - timedelta(seconds=window_seconds)
    _login_attempts[key] = [t for t in timestamps if t > cutoff]
    if len(_login_attempts[key]) >= max_attempts:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Please try again later."
        )
    _login_attempts[key].append(now)

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_in: UserCreate, request: Request, db: AsyncSession = Depends(get_db)):
    _check_rate_limit(f"register:{request.client.host}", max_attempts=5, window_seconds=300)
    normalized_email = user_in.email.strip().lower()
    stmt = select(User).where(func.lower(User.email) == normalized_email)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    
    new_user = User(
        id=str(uuid.uuid4()),
        email=normalized_email,
        hashed_password=get_password_hash(user_in.password),
        full_name=user_in.full_name
    )
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user

@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), request: Request = None, db: AsyncSession = Depends(get_db)):
    client_ip = request.client.host if request else "unknown"
    _check_rate_limit(f"login:ip:{client_ip}", max_attempts=10, window_seconds=60)
    _check_rate_limit(f"login:user:{form_data.username.strip().lower()}", max_attempts=5, window_seconds=300)
    normalized_email = form_data.username.strip().lower()
    stmt = select(User).where(func.lower(User.email) == normalized_email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
         raise HTTPException(status_code=400, detail="Inactive user")

    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    access_token = create_access_token(subject=user.id)
    refresh_token = create_refresh_token(subject=user.id)
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": 1800 # 30 mins defaults
    }

@router.post("/refresh", response_model=Token)
async def refresh_token(request: RefreshTokenRequest, http_request: Request, db: AsyncSession = Depends(get_db)):
    _check_rate_limit(f"refresh:{http_request.client.host}", max_attempts=20, window_seconds=60)
    payload = decode_token(request.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")
        
    user_id = payload.get("sub")
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    access_token = create_access_token(subject=user.id)
    new_refresh_token = create_refresh_token(subject=user.id)
    
    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
        "expires_in": 1800
    }

from pydantic import BaseModel
from google.oauth2 import id_token
from google.auth.transport import requests

class GoogleTokenRequest(BaseModel):
    token: str

GOOGLE_CLIENT_ID = settings.GOOGLE_CLIENT_ID or ""

@router.post("/google", response_model=Token)
async def login_google(body: GoogleTokenRequest, http_request: Request, db: AsyncSession = Depends(get_db)):
    _check_rate_limit(f"google:{http_request.client.host}", max_attempts=10, window_seconds=300)
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=501, detail="Google login not configured")

    try:
        id_info = id_token.verify_oauth2_token(
            body.token, requests.Request(), GOOGLE_CLIENT_ID
        )
        email = id_info.get("email")
        full_name = id_info.get("name")
        
        if not email:
            raise HTTPException(status_code=400, detail="Google token missing email")

        stmt = select(User).where(User.email == email)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            user = User(
                id=str(uuid.uuid4()),
                email=email,
                hashed_password=get_password_hash(str(uuid.uuid4())),
                full_name=full_name
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)

        if not user.is_active:
             raise HTTPException(status_code=400, detail="Inactive user")

        user.last_login_at = datetime.now(timezone.utc)
        await db.commit()

        access_token = create_access_token(subject=user.id)
        refresh_token = create_refresh_token(subject=user.id)
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": 1800
        }

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google token",
            headers={"WWW-Authenticate": "Bearer"},
        )
