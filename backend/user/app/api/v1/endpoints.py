import uuid
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from app.core.database import get_db
from app.core.security import get_current_user_id, get_optional_user_id
from app.schemas.profile import ProfileRead, ProfileUpdate, AvatarResponse, FollowToggleResponse
from app.services.profile import ProfileService, FollowService

router = APIRouter(prefix="/v1")

USERNAME_RE = re.compile(r'^[a-zA-Z0-9_]{3,30}$')


@router.get("/profile/{username}", response_model=ProfileRead)
async def get_public_profile(
    username: str,
    viewer_id: Optional[uuid.UUID] = Depends(get_optional_user_id),
    db: AsyncSession = Depends(get_db)
):
    service = ProfileService(db)
    return await service.get_profile_by_username(username, viewer_id=viewer_id)


@router.post("/profile/{user_id}/follow", response_model=FollowToggleResponse)
async def toggle_follow(
    user_id: uuid.UUID,
    current_user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    service = FollowService(db)
    return await service.toggle(current_user_id, user_id)


@router.get("/check-username")
async def check_username(
    username: str = Query(..., min_length=3, max_length=30),
    db: AsyncSession = Depends(get_db)
):
    if not USERNAME_RE.match(username):
        return {"available": False, "error": "Только латиница, цифры и подчёркивание, 3–30 символов"}
    service = ProfileService(db)
    available = await service.check_username_available(username)
    return {"available": available}


@router.get("/me", response_model=ProfileRead)
async def read_my_profile(
    current_user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    service = ProfileService(db)
    return await service.get_my_profile(current_user_id)


@router.patch("/me", response_model=ProfileRead)
async def update_profile(
    update_data: ProfileUpdate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    service = ProfileService(db)
    return await service.update_my_profile(user_id, update_data)


@router.post("/avatar", response_model=AvatarResponse)
async def upload_avatar(
    file: UploadFile = File(..., description="Аватар (JPEG, PNG или WebP, до 5 МБ)"),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    service = ProfileService(db)
    avatar_url = await service.upload_avatar(user_id, file)
    return {"avatar_url": avatar_url}
