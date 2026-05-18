from typing import Optional, Dict
from uuid import UUID

from pydantic import BaseModel, HttpUrl, Field, field_validator


class ProfileBase(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=30, description="Уникальный никнейм артиста")
    bio: Optional[str] = Field(None, max_length=500, description="Информация о себе/студии")
    avatar_url: Optional[HttpUrl] = None
    social_links: Dict[str, str] = Field(default_factory=dict, description="Ссылки: {'soundcloud': 'url', ...}")

    @field_validator("avatar_url")
    @classmethod
    def validate_url(cls, v: Optional[str]):
        if v is None:
            return v
        return str(v)


class ProfileCreate(ProfileBase):
    user_id: UUID
    username: str  # При создании никнейм обязателен


class ProfileUpdate(BaseModel):
    username: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None


class ProfileRead(ProfileBase):
    user_id: UUID

    class Config:
        from_attributes = True  # Позволяет Pydantic работать с моделями SQLAlchemy
