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


class BeatResponse(BaseModel):
    id: uuid.UUID
    title: str
    bpm: Optional[int]
    key: Optional[str]
    price: Decimal
    genre: Optional[str]
    primary_instrument: Optional[str]
    audio_preview_url: str
    author_id: uuid.UUID

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


class BeatForm:
    def __init__(
        self,
        title: str = Form(..., min_length=1, max_length=100),
        bpm: Optional[int] = Form(None, ge=40, le=300),
        key: Optional[str] = Form(None, max_length=10),
        price: Decimal = Form(..., ge=0),
        genre: Optional[str] = Form(None),
        primary_instrument: Optional[str] = Form(None)
    ):
        self.title = title
        self.bpm = bpm
        self.key = key
        self.price = price
        self.genre = genre
        self.primary_instrument = primary_instrument
