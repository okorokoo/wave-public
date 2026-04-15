import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import String, ForeignKey, Float, Integer, Enum, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base
from models.user import User


class ItemType(enum.Enum):
    BEAT = "beat"
    SAMPLE_PACK = "sample_pack"
    LOOP = "loop"


class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True)
    producer_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    # Основная информация
    title: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(1000))
    item_type: Mapped[ItemType] = mapped_column(Enum(ItemType), default=ItemType.BEAT)

    # Музыкальные метаданные (для фильтрации)
    bpm: Mapped[Optional[int]] = mapped_column(Integer, index=True)
    key: Mapped[Optional[str]] = mapped_column(String(20), index=True)  # Например, "Am", "C# Minor"
    genre: Mapped[Optional[str]] = mapped_column(String(50), index=True)

    # Финансы
    price_standard: Mapped[float] = mapped_column(Float, nullable=False)
    price_exclusive: Mapped[Optional[float]] = mapped_column(Float)
    is_sold_exclusive: Mapped[bool] = mapped_column(default=False)

    # Пути к файлам в S3
    s3_original_key: Mapped[str] = mapped_column(String(500), nullable=False)  # Путь к WAV
    s3_preview_key: Mapped[str] = mapped_column(String(500), nullable=False)  # Путь к MP3 с тегом

    # Служебные поля
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    is_active: Mapped[bool] = mapped_column(default=True)

    # Связи
    producer: Mapped[User] = relationship(back_populates="items")
    audio_metadata: Mapped["AudioMetadata"] = relationship(
        back_populates="item",
        uselist=False,
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Item(title={self.title}, price={self.price_standard})>"


class AudioMetadata(Base):
    __tablename__ = "audio_metadata"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(
        ForeignKey("items.id", ondelete="CASCADE"),
        unique=True,
        nullable=False
    )

    # Технические характеристики файла
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    sample_rate: Mapped[int] = mapped_column(Integer, default=44100)
    bit_depth: Mapped[int] = mapped_column(Integer, default=24)
    channels: Mapped[int] = mapped_column(Integer, default=2)  # 1 - mono, 2 - stereo

    # Связь обратно к Item
    item: Mapped["Item"] = relationship(back_populates="audio_metadata")

    def __repr__(self) -> str:
        return f"<AudioMetadata(item_id={self.item_id}, duration={self.duration_seconds}s)>"
