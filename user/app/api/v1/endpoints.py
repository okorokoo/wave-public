import uuid

from app.models.models import Profile
from fastapi import HTTPException, Security, APIRouter, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from app.core.database import get_db
from app.schemas.profile import ProfileRead, ProfileCreate, ProfileUpdate
from app.services.profile import ProfileService
from config import settings

router = APIRouter(prefix="/v1")

security = HTTPBearer()


async def get_current_user_id(res: HTTPAuthorizationCredentials = Security(security)):
    """
    Проверяет токен и возвращает user_id, не обращаясь к базе Auth.
    """
    try:
        payload = jwt.decode(res.credentials, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        return user_id
    except JWTError:
        raise HTTPException(status_code=401, detail="Could not validate credentials")


@router.get("/me", response_model=ProfileRead)
async def read_my_profile(
        current_user_id: str = Depends(get_current_user_id),
        db: AsyncSession = Depends(get_db)
):
    profile = await db.get(Profile, current_user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@router.post("/profiles", response_model=ProfileRead, status_code=status.HTTP_201_CREATED)
async def create_profile(
        profile_data: ProfileCreate,
        db: AsyncSession = Depends(get_db)
):
    # 1. Проверяем, не существует ли уже профиль для этого user_id
    query = select(Profile).where(Profile.user_id == profile_data.user_id)
    result = await db.execute(query)
    existing_profile = result.scalar_one_or_none()

    if existing_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Профиль для данного пользователя уже существует"
        )

    # 2. Проверяем уникальность никнейма (если он передан)
    if profile_data.username:
        username_query = select(Profile).where(Profile.username == profile_data.username)
        username_result = await db.execute(username_query)
        if username_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Этот никнейм уже занят"
            )

    # 3. Создаем новый профиль
    # Используем mode="json" для автоматической конвертации HttpUrl в str
    new_profile = Profile(**profile_data.model_dump(mode="json"))

    db.add(new_profile)
    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при сохранении в базу данных"
        )

    await db.refresh(new_profile)
    return new_profile


@router.patch("/me", response_model=ProfileRead)
async def update_profile(
    update_data: ProfileUpdate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    service = ProfileService(db)
    return await service.update_my_profile(user_id, update_data)
