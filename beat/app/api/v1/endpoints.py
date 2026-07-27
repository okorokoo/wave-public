import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status, UploadFile, File

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.schemas.beat import BeatResponse, BeatUpdate, BeatForm, PurchaseResponse, DownloadResponse, MyPurchaseResponse, PaginatedBeatsResponse, PaginatedMyBeatsResponse
from app.services.beat import BeatService, PurchaseService

router = APIRouter(tags=["Beats Catalog"])


@router.post("/", response_model=BeatResponse, status_code=status.HTTP_201_CREATED)
async def upload_new_beat(
        beat_in: BeatForm = Depends(),
        audio_full: UploadFile = File(..., description="Полная версия (WAV)"),
        cover: Optional[UploadFile] = File(None, description="Обложка бита (JPEG, PNG, WebP)"),
        author_id: uuid.UUID = Depends(get_current_user_id),
        db=Depends(get_db)
):
    service = BeatService(db)
    return await service.upload_beat(
        beat_form=beat_in,
        audio_full=audio_full,
        cover=cover,
        author_id=author_id,
    )


@router.get("/my-beats", response_model=PaginatedMyBeatsResponse)
async def get_my_beats(
        limit: int = Query(20, ge=1, le=100, description="Количество битов на странице"),
        offset: int = Query(0, ge=0, description="Смещение"),
        author_id: uuid.UUID = Depends(get_current_user_id),
        db=Depends(get_db)
):
    service = BeatService(db)
    return await service.get_my_beats(author_id, limit=limit, offset=offset)


@router.get("/my-purchases", response_model=List[MyPurchaseResponse])
async def get_my_purchases(
        current_user_id: uuid.UUID = Depends(get_current_user_id),
        db=Depends(get_db)
):
    service = PurchaseService(db)
    return await service.get_my_purchases(current_user_id)


@router.patch("/{beat_id}", response_model=BeatResponse)
async def update_beat(
        beat_id: uuid.UUID,
        update_data: BeatUpdate,
        current_user_id: uuid.UUID = Depends(get_current_user_id),
        db=Depends(get_db)
):
    """
    Частичное обновление данных бита (BPM, цена, жанр и т.д.).
    Доступно только автору бита.
    """
    service = BeatService(db)
    return await service.update_beat(
        beat_id=beat_id,
        current_user_id=current_user_id,
        update_in=update_data
    )


@router.get("/", response_model=PaginatedBeatsResponse)
async def get_beats_catalog(
        search: Optional[str] = Query(None, description="Поиск по названию"),
        genre: Optional[str] = Query(None, description="Фильтр по жанру"),
        instrument: Optional[str] = Query(None, description="Фильтр по главному инструменту"),
        tag: Optional[str] = Query(None, description="Фильтр по тегу"),
        min_bpm: Optional[int] = Query(None, ge=40, le=300, description="Минимальный темп"),
        max_bpm: Optional[int] = Query(None, ge=40, le=300, description="Максимальный темп"),
        limit: int = Query(20, ge=1, le=100, description="Количество битов на странице"),
        offset: int = Query(0, ge=0, description="Смещение"),
        db=Depends(get_db)
):
    service = BeatService(db)
    return await service.get_catalog(
        search=search,
        genre=genre,
        instrument=instrument,
        tag=tag,
        min_bpm=min_bpm,
        max_bpm=max_bpm,
        limit=limit,
        offset=offset,
    )


@router.delete("/{beat_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_beat(
        beat_id: uuid.UUID,
        current_user_id: uuid.UUID = Depends(get_current_user_id),
        db=Depends(get_db)
):
    service = BeatService(db)
    await service.remove_beat(beat_id, current_user_id)
    return None


@router.post("/{beat_id}/purchase", response_model=PurchaseResponse, status_code=status.HTTP_201_CREATED)
async def purchase_beat(
        beat_id: uuid.UUID,
        buyer_id: uuid.UUID = Depends(get_current_user_id),
        db=Depends(get_db)
):
    service = PurchaseService(db)
    return await service.purchase_beat(beat_id, buyer_id)


@router.get("/{beat_id}/download", response_model=DownloadResponse)
async def download_beat(
        beat_id: uuid.UUID,
        current_user_id: uuid.UUID = Depends(get_current_user_id),
        db=Depends(get_db)
):
    service = PurchaseService(db)
    return await service.get_download_url(beat_id, current_user_id)
