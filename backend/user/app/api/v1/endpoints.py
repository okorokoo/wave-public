import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.schemas.profile import ProfileRead, ProfileUpdate
from app.services.profile import ProfileService

router = APIRouter(prefix="/v1")


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
