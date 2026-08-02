import uuid
from typing import Optional

from app.models.models import Profile
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession


class ProfileRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_profile(self, user_id: uuid.UUID, username: Optional[str] = None) -> Profile:
        existing = await self.get_by_user_id(user_id)
        if existing:
            return existing

        new_profile = Profile(user_id=user_id, username=username)
        self.db.add(new_profile)
        try:
            await self.db.commit()
            await self.db.refresh(new_profile)
            return new_profile
        except Exception:
            await self.db.rollback()
            existing = await self.get_by_user_id(user_id)
            if existing:
                return existing
            raise

    async def get_by_username(self, username: str) -> Optional[Profile]:
        query = select(Profile).where(func.lower(Profile.username) == username.lower())
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def is_username_available(self, username: str) -> bool:
        return await self.get_by_username(username) is None

    async def get_by_user_id(self, user_id: uuid.UUID) -> Optional[Profile]:
        query = select(Profile).where(Profile.user_id == user_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def update_profile(self, profile: Profile, update_data: dict) -> Profile:
        # Проходимся по словарю и обновляем только измененные поля
        for key, value in update_data.items():
            setattr(profile, key, value)

        self.db.add(profile)
        await self.db.commit()
        await self.db.refresh(profile)
        return profile
