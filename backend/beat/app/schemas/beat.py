import uuid
from datetime import datetime
from decimal import Decimal

from fastapi import Form
from pydantic import BaseModel, ConfigDict, Field


class BeatCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=100, examples=["Type Beat 2026"])
    bpm: int | None = Field(None, ge=40, le=300, description="Темп в ударах в минуту")
    key: str | None = Field(None, max_length=10, examples=["Am", "C# Min"])
    price: Decimal = Field(..., ge=0, decimal_places=2)
    genre: str | None = Field(None, min_length=1, max_length=100)
    primary_instrument: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)


class BeatUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=100)
    bpm: int | None = Field(None, ge=40, le=300)
    key: str | None = Field(None, max_length=10)
    price: Decimal | None = Field(None, ge=0, decimal_places=2)
    genre: str | None = Field(None, min_length=1, max_length=100)
    primary_instrument: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    tags: list[str] | None = None


class BeatResponse(BaseModel):
    id: uuid.UUID
    title: str
    bpm: int | None
    key: str | None
    price: Decimal
    genre: str | None
    primary_instrument: str | None
    audio_preview_url: str
    cover_url: str | None = None
    tags: list[str] = []
    author_id: uuid.UUID
    author_name: str | None = None
    description: str | None = None
    likes_count: int = 0
    is_liked: bool = False
    play_count: int = 0
    has_stems: bool = False

    model_config = ConfigDict(from_attributes=True)


class PurchaseResponse(BaseModel):
    id: uuid.UUID
    beat_id: uuid.UUID
    buyer_id: uuid.UUID
    license_type: str
    purchased_at: datetime
    download_url: str


class DownloadResponse(BaseModel):
    stream_url: str


class StemsDownloadResponse(BaseModel):
    stream_url: str


class CheckoutResponse(BaseModel):
    payment_id: str
    confirmation_url: str


class VoiceTagResponse(BaseModel):
    url: str
    uploaded_at: datetime


class PaymentResultResponse(BaseModel):
    status: str  # pending | succeeded | canceled
    beat_id: str | None = None
    beat_title: str | None = None


class PendingPaymentResponse(BaseModel):
    payment_id: str
    beat_id: uuid.UUID
    beat_title: str
    beat_cover_url: str | None = None
    beat_author_name: str | None = None
    amount: Decimal
    created_at: datetime


class MyPurchaseResponse(BaseModel):
    id: uuid.UUID
    license_type: str
    purchased_at: datetime
    stream_url: str
    beat: BeatResponse


class PurchaseStatusResponse(BaseModel):
    is_purchased: bool


class PaginatedBeatsResponse(BaseModel):
    items: list[BeatResponse]
    total: int
    limit: int
    offset: int


class LikeToggleResponse(BaseModel):
    liked: bool
    likes_count: int


class PlayCountResponse(BaseModel):
    play_count: int


class MyBeatResponse(BeatResponse):
    sales_count: int


class PaginatedMyBeatsResponse(BaseModel):
    items: list[MyBeatResponse]
    total: int
    limit: int
    offset: int


class BeatForm:
    def __init__(
        self,
        title: str = Form(..., min_length=1, max_length=100),
        bpm: int | None = Form(None, ge=40, le=300),
        key: str | None = Form(None, max_length=10),
        price: Decimal = Form(..., ge=0),
        genre: str | None = Form(None),
        primary_instrument: str | None = Form(None),
        tags: list[str] = Form(default=[]),
        artist_name: str | None = Form(None, max_length=60),
        description: str | None = Form(None, max_length=500),
    ):
        self.title = title
        self.bpm = bpm
        self.key = key
        self.price = price
        self.genre = genre
        self.primary_instrument = primary_instrument
        self.tags = tags
        self.artist_name = artist_name
        self.description = description
