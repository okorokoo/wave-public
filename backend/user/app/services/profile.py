import uuid
from typing import Optional

from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from app.core.repo import ProfileRepo
from app.core.s3 import S3Storage
from app.models.models import Profile
from app.schemas.profile import ProfileUpdate

ALLOWED_AVATAR_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_AVATAR_BYTES = 5 * 1024 * 1024  # 5 MB


class ProfileService:
    def __init__(self, db: AsyncSession):
        self._repo = ProfileRepo(db=db)
        self._s3 = S3Storage()

    async def create_empty_profile(self, user_id: uuid.UUID, username: Optional[str] = None) -> Profile:
        return await self._repo.create_profile(user_id=user_id, username=username)

    async def check_username_available(self, username: str) -> bool:
        return await self._repo.is_username_available(username)

    async def get_profile_by_username(self, username: str) -> dict:
        profile = await self._repo.get_by_username(username)
        if not profile:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        return await self._build_profile_dict(profile)

    async def _build_profile_dict(self, profile: Profile) -> dict:
        avatar_url: Optional[str] = None
        if profile.avatar_url:
            try:
                avatar_url = await self._s3.generate_presigned_url(profile.avatar_url)
            except Exception:
                avatar_url = None
        return {
            "user_id": profile.user_id,
            "username": profile.username,
            "bio": profile.bio,
            "avatar_url": avatar_url,
            "social_links": profile.social_links or {},
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

        new_username = update_data.get("username")
        if new_username and new_username != profile.username:
            if not await self._repo.is_username_available(new_username):
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Этот псевдоним уже занят")

        try:
            await self._repo.update_profile(profile, update_data)
        except IntegrityError:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Этот псевдоним уже занят")

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

        # Delete old avatar only if key changed
        if profile.avatar_url and profile.avatar_url != s3_key:
            try:
                await self._s3.delete_objects([profile.avatar_url])
            except Exception:
                pass

        await self._s3.upload_file(file, s3_key)
        await self._repo.update_profile(profile, {"avatar_url": s3_key})

        return await self._s3.generate_presigned_url(s3_key)
