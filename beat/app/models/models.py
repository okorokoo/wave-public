import uuid
from sqlalchemy import Column, Integer, String, Numeric, Boolean, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Beat(Base):
    __tablename__ = "beats"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    bpm = Column(Integer, nullable=True)
    key = Column(String, nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    genre = Column(String, nullable=True)
    primary_instrument = Column(String, nullable=True)

    audio_preview_url = Column(String, nullable=False)
    audio_full_url = Column(String, nullable=False)
    cover_url = Column(String, nullable=True)

    author_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    is_processed = Column(Boolean, nullable=False, default=False)

    tags = relationship("BeatTag", lazy="selectin", cascade="all, delete-orphan")


class BeatTag(Base):
    __tablename__ = "beat_tags"

    beat_id = Column(UUID(as_uuid=True), ForeignKey("beats.id", ondelete="CASCADE"), primary_key=True)
    tag = Column(String(50), primary_key=True)


class Purchase(Base):
    __tablename__ = "purchases"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    beat_id = Column(UUID(as_uuid=True), ForeignKey("beats.id", ondelete="CASCADE"), nullable=False, index=True)
    buyer_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    license_type = Column(String, nullable=False, default="basic")
    purchased_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class UserVoiceTag(Base):
    __tablename__ = "user_voice_tags"

    user_id = Column(UUID(as_uuid=True), primary_key=True)
    s3_key = Column(String, nullable=False)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Payment(Base):
    __tablename__ = "payments"

    id = Column(String, primary_key=True)  # YooKassa payment UUID string
    beat_id = Column(UUID(as_uuid=True), ForeignKey("beats.id", ondelete="CASCADE"), nullable=False, index=True)
    buyer_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    amount = Column(Numeric(10, 2), nullable=False)
    status = Column(String, nullable=False, default="pending")  # pending / succeeded / canceled
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
