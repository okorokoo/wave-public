import uuid

from app.models.models import Profile
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from app.core.repo import ProfileRepo
from app.schemas.profile import ProfileUpdate


class ProfileService:
    def __init__(self, db: AsyncSession):
        self._profile_repo = ProfileRepo(db=db)

    async def create_empty_profile(self, user_id: uuid.UUID) -> Profile:
        return await self._profile_repo.create_profile(user_id=user_id)

    async def get_my_profile(self, user_id: uuid.UUID) -> Profile:
        profile = await self._profile_repo.get_by_user_id(user_id)
        if not profile:
            raise HTTPException(status_code=404, detail="Профиль не найден")
        return profile

    async def update_my_profile(self, user_id: uuid.UUID, update_schema: ProfileUpdate) -> Profile:
        profile = await self._profile_repo.get_by_user_id(user_id)
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Профиль не найден"
            )

        update_data = update_schema.model_dump(exclude_unset=True)

        if not update_data:
            return profile  # Если прислали пустой JSON, ничего не делаем

        # 3. Обновляем в БД через репозиторий
        return await self._profile_repo.update_profile(profile, update_data)
