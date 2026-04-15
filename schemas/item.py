from typing import Optional
from pydantic import BaseModel, ConfigDict
from models.item import ItemType
from schemas.audio import AudioMetadataRead


class ItemBase(BaseModel):
    title: str
    description: Optional[str] = None
    item_type: ItemType = ItemType.BEAT
    bpm: Optional[int] = None
    key: Optional[str] = None
    genre: Optional[str] = None
    price_standard: float
    price_exclusive: Optional[float] = None


class ItemCreate(ItemBase):
    # s3_original_key будет заполняться на бэкенде после загрузки файла
    pass


class ItemRead(ItemBase):
    id: int
    producer_id: int
    s3_preview_key: str  # Ссылка на превью для плеера
    is_sold_exclusive: bool
    audio_metadata: Optional[AudioMetadataRead] = None  # Вложенная схема

    model_config = ConfigDict(from_attributes=True)
