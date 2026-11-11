import contextlib
import logging
import uuid

from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from app.core.repo import FollowRepo, ProfileRepo
from app.core.s3 import S3Storage
from app.models.models import Profile
from app.schemas.profile import FollowToggleResponse, ProfileUpdate

logger = logging.getLogger(__name__)

ALLOWED_AVATAR_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_AVATAR_BYTES = 5 * 1024 * 1024  # 5 MB


class ProfileService:
    def __init__(self, db: AsyncSession):
        self._repo = ProfileRepo(db=db)
        self._follow_repo = FollowRepo(db=db)
        self._s3 = S3Storage()

    async def create_empty_profile(self, user_id: uuid.UUID, username: str | None = None) -> Profile:
        return await self._repo.create_profile(user_id=user_id, username=username)

    async def check_username_available(self, username: str) -> bool:
        return await self._repo.is_username_available(username)

    async def get_profile_by_username(self, username: str, viewer_id: uuid.UUID | None = None) -> dict:
        profile = await self._repo.get_by_username(username)
        if not profile:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        return await self._build_profile_dict(profile, viewer_id=viewer_id)

    async def _build_profile_dict(self, profile: Profile, viewer_id: uuid.UUID | None = None) -> dict:
        async def _get_avatar() -> str | None:
            if not profile.avatar_url:
                return None
            try:
                return await self._s3.generate_presigned_url(profile.avatar_url)
            except Exception:
                return None

        followers_count, following_count = await self._follow_repo.get_counts(profile.user_id)
        is_following = (
            viewer_id is not None
            and viewer_id != profile.user_id
            and await self._follow_repo.is_following(viewer_id, profile.user_id)
        )
        avatar_url: str | None = await _get_avatar()

        return {
            "user_id": profile.user_id,
            "username": profile.username,
            "bio": profile.bio,
            "avatar_url": avatar_url,
            "social_links": profile.social_links or {},
            "followers_count": followers_count,
            "following_count": following_count,
            "is_following": is_following,
        }

    async def get_my_profile(self, user_id: uuid.UUID) -> dict:
        profile = await self._repo.get_by_user_id(user_id)
        if not profile:
            raise HTTPException(status_code=404, detail="Профиль не найден")
        return await self._build_profile_dict(profile)

    async def update_my_profile(self, user_id: uuid.UUID, update_schema: ProfileUpdate) -> dict:
        from sqlalchemy.exc import IntegrityError

        profile = await self._repo.get_by_user_id(user_id)
        if not profile:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Профиль не найден")

        update_data = update_schema.model_dump(exclude_unset=True)
        if not update_data:
            return await self.get_my_profile(user_id)

        new_username: str | None = update_data.get("username")
        username_changed = bool(new_username) and new_username != profile.username
        if username_changed and new_username and not await self._repo.is_username_available(new_username):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Этот псевдоним уже занят")

        try:
            await self._repo.update_profile(profile, update_data)
        except IntegrityError:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Этот псевдоним уже занят") from None

        if username_changed:
            try:
                import json

                import aio_pika

                from config import settings as _s

                async with await aio_pika.connect_robust(_s.rabbitmq_url) as conn:
                    channel = await conn.channel()
                    await channel.declare_queue("username_changed", durable=True)
                    await channel.default_exchange.publish(
                        aio_pika.Message(
                            body=json.dumps({"user_id": str(user_id), "new_username": new_username}).encode(),
                            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                        ),
                        routing_key="username_changed",
                    )
            except Exception as exc:
                logger.warning("username_changed: failed to publish event for %s: %s", user_id, exc)

        return await self.get_my_profile(user_id)

    async def upload_avatar(self, user_id: uuid.UUID, file: UploadFile) -> str:
        if file.content_type not in ALLOWED_AVATAR_TYPES:
            raise HTTPException(status_code=400, detail="Только JPEG, PNG или WebP")

        content = await file.read()
        if len(content) > MAX_AVATAR_BYTES:
            raise HTTPException(status_code=413, detail="Файл не должен превышать 5 МБ")
        await file.seek(0)

        ext = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}.get(file.content_type, "jpg")
        s3_key = f"avatars/{user_id}/avatar.{ext}"

        profile = await self._repo.get_by_user_id(user_id)
        if not profile:
            raise HTTPException(status_code=404, detail="Профиль не найден")

        if profile.avatar_url and profile.avatar_url != s3_key:
            with contextlib.suppress(Exception):
                await self._s3.delete_objects([profile.avatar_url])

        await self._s3.upload_file(file, s3_key)
        await self._repo.update_profile(profile, {"avatar_url": s3_key})

        return await self._s3.generate_presigned_url(s3_key)


class FollowService:
    def __init__(self, db: AsyncSession):
        self._repo = FollowRepo(db=db)
        self._profile_repo = ProfileRepo(db=db)

    async def toggle(self, follower_id: uuid.UUID, following_id: uuid.UUID) -> FollowToggleResponse:
        if follower_id == following_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Нельзя подписаться на себя")
        target = await self._profile_repo.get_by_user_id(following_id)
        if not target:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")
        is_following, followers_count = await self._repo.toggle(follower_id, following_id)
        return FollowToggleResponse(is_following=is_following, followers_count=followers_count)
