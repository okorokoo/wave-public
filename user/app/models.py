import uuid

from sqlalchemy import String, UUID, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase


class Base(DeclarativeBase):
    pass


class Profile(Base):
    __tablename__ = "profiles"

    # Это тот же ID, что и в auth-service
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    username: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=True)
    bio: Mapped[str] = mapped_column(Text, nullable=True)
    avatar_url: Mapped[str] = mapped_column(String, nullable=True)
    social_links: Mapped[dict] = mapped_column(JSON, default={})  # {"soundcloud": "...", "instagram": "..."}
