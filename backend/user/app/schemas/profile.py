from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

ALLOWED_SOCIAL_KEYS = {"soundcloud", "instagram", "youtube", "vk", "telegram", "twitter", "website"}


class ProfileUpdate(BaseModel):
    username: str | None = Field(None, min_length=3, max_length=30)
    bio: str | None = Field(None, max_length=500)
    social_links: dict[str, str] | None = Field(
        None, description="Ключи: soundcloud, instagram, youtube, vk, telegram, twitter, website"
    )


class ProfileRead(BaseModel):
    user_id: UUID
    username: str | None = None
    bio: str | None = None
    avatar_url: str | None = None
    social_links: dict[str, str] = Field(default_factory=dict)
    followers_count: int = 0
    following_count: int = 0
    is_following: bool = False

    model_config = ConfigDict(from_attributes=True)


class AvatarResponse(BaseModel):
    avatar_url: str


class FollowToggleResponse(BaseModel):
    is_following: bool
    followers_count: int
