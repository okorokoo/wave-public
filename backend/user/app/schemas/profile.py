from typing import Optional, Dict
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


ALLOWED_SOCIAL_KEYS = {"soundcloud", "instagram", "youtube", "vk", "telegram", "twitter", "website"}


class ProfileUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=30)
    bio: Optional[str] = Field(None, max_length=500)
    social_links: Optional[Dict[str, str]] = Field(None, description="Ключи: soundcloud, instagram, youtube, vk, telegram, twitter, website")


class ProfileRead(BaseModel):
    user_id: UUID
    username: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    social_links: Dict[str, str] = Field(default_factory=dict)
    followers_count: int = 0
    following_count: int = 0
    is_following: bool = False

    model_config = ConfigDict(from_attributes=True)


class AvatarResponse(BaseModel):
    avatar_url: str


class FollowToggleResponse(BaseModel):
    is_following: bool
    followers_count: int
