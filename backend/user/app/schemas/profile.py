from typing import Optional, Dict
from uuid import UUID

from pydantic import BaseModel, Field


class ProfileUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=30)
    bio: Optional[str] = Field(None, max_length=500)


class ProfileRead(BaseModel):
    user_id: UUID
    username: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    social_links: Dict[str, str] = Field(default_factory=dict)

    class Config:
        from_attributes = True


class AvatarResponse(BaseModel):
    avatar_url: str
