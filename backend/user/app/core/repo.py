import uuid
from typing import Optional

from app.models.models import Profile, Follow
from sqlalchemy import select, func, and_
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


class FollowRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def toggle(self, follower_id: uuid.UUID, following_id: uuid.UUID) -> tuple[bool, int]:
        existing = await self.db.execute(
            select(Follow).where(and_(Follow.follower_id == follower_id, Follow.following_id == following_id))
        )
        follow = existing.scalar_one_or_none()
        if follow:
            await self.db.delete(follow)
            is_following = False
        else:
            self.db.add(Follow(follower_id=follower_id, following_id=following_id))
            is_following = True
        await self.db.commit()
        followers_count = await self._count_followers(following_id)
        return is_following, followers_count

    async def _count_followers(self, user_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(Follow).where(Follow.following_id == user_id)
        )
        return result.scalar_one()

    async def _count_following(self, user_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(Follow).where(Follow.follower_id == user_id)
        )
        return result.scalar_one()

    async def get_counts(self, user_id: uuid.UUID) -> tuple[int, int]:
        followers = await self._count_followers(user_id)
        following = await self._count_following(user_id)
        return followers, following

    async def is_following(self, follower_id: uuid.UUID, following_id: uuid.UUID) -> bool:
        result = await self.db.execute(
            select(Follow).where(and_(Follow.follower_id == follower_id, Follow.following_id == following_id))
        )
        return result.scalar_one_or_none() is not None
