import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from fastapi import Form
from pydantic import BaseModel, Field


class BeatCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=100, examples=["Type Beat 2026"])
    bpm: Optional[int] = Field(None, ge=40, le=300, description="Темп в ударах в минуту")
    key: Optional[str] = Field(None, max_length=10, examples=["Am", "C# Min"])
    price: Decimal = Field(..., ge=0, decimal_places=2)
    genre: Optional[str] = Field(None, min_length=1, max_length=100)
    primary_instrument: Optional[str] = Field(None, min_length=1, max_length=100)


class BeatUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=100)
    bpm: Optional[int] = Field(None, ge=40, le=300)
    key: Optional[str] = Field(None, max_length=10)
    price: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    genre: Optional[str] = Field(None, min_length=1, max_length=100)
    primary_instrument: Optional[str] = Field(None, min_length=1, max_length=100)
    tags: Optional[List[str]] = None


class BeatResponse(BaseModel):
    id: uuid.UUID
    title: str
    bpm: Optional[int]
    key: Optional[str]
    price: Decimal
    genre: Optional[str]
    primary_instrument: Optional[str]
    audio_preview_url: str
    cover_url: Optional[str] = None
    tags: List[str] = []
    author_id: uuid.UUID
    author_name: Optional[str] = None
    likes_count: int = 0
    is_liked: bool = False

    class Config:
        from_attributes = True


class PurchaseResponse(BaseModel):
    id: uuid.UUID
    beat_id: uuid.UUID
    buyer_id: uuid.UUID
    license_type: str
    purchased_at: datetime
    download_url: str


class DownloadResponse(BaseModel):
    download_url: str


class CheckoutResponse(BaseModel):
    payment_id: str
    confirmation_url: str


class VoiceTagResponse(BaseModel):
    url: str
    uploaded_at: datetime


class PaymentResultResponse(BaseModel):
    status: str  # pending | succeeded | canceled
    download_url: Optional[str] = None


class MyPurchaseResponse(BaseModel):
    id: uuid.UUID
    license_type: str
    purchased_at: datetime
    download_url: str
    beat: BeatResponse


class PaginatedBeatsResponse(BaseModel):
    items: List[BeatResponse]
    total: int
    limit: int
    offset: int


class LikeToggleResponse(BaseModel):
    liked: bool
    likes_count: int


class MyBeatResponse(BeatResponse):
    sales_count: int


class PaginatedMyBeatsResponse(BaseModel):
    items: List[MyBeatResponse]
    total: int
    limit: int
    offset: int


class BeatForm:
    def __init__(
        self,
        title: str = Form(..., min_length=1, max_length=100),
        bpm: Optional[int] = Form(None, ge=40, le=300),
        key: Optional[str] = Form(None, max_length=10),
        price: Decimal = Form(..., ge=0),
        genre: Optional[str] = Form(None),
        primary_instrument: Optional[str] = Form(None),
        tags: List[str] = Form(default=[]),
        artist_name: Optional[str] = Form(None, max_length=60),
    ):
        self.title = title
        self.bpm = bpm
        self.key = key
        self.price = price
        self.genre = genre
        self.primary_instrument = primary_instrument
        self.tags = tags
        self.artist_name = artist_name
