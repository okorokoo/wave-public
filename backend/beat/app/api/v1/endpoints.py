import uuid

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile, status
from fastapi.responses import StreamingResponse

from app.core.database import get_db
from app.core.download_token import verify_download_token
from app.core.repo import BeatRepo, PurchaseRepo
from app.core.s3 import S3Storage
from app.core.security import get_current_user_id, get_current_user_username, get_optional_user_id
from app.schemas.beat import (
    BeatForm,
    BeatResponse,
    BeatUpdate,
    CheckoutResponse,
    DownloadResponse,
    LikeToggleResponse,
    MyPurchaseResponse,
    PaginatedBeatsResponse,
    PaginatedMyBeatsResponse,
    PaymentResultResponse,
    PendingPaymentResponse,
    PlayCountResponse,
    PurchaseStatusResponse,
    StemsDownloadResponse,
    VoiceTagResponse,
)
from app.services.beat import BeatService, LikeService, PlayService, PurchaseService, StemsService, VoiceTagService
from app.services.payment import PaymentService

router = APIRouter(tags=["Beats Catalog"])


# ─── Статичные маршруты (должны быть выше /{beat_id}) ────────────────────────


@router.post("/", response_model=BeatResponse, status_code=status.HTTP_201_CREATED)
async def upload_new_beat(
    beat_in: BeatForm = Depends(),
    audio_full: UploadFile = File(..., description="Полная версия (WAV)"),
    cover: UploadFile | None = File(None, description="Обложка бита (JPEG, PNG, WebP)"),
    stems: UploadFile | None = File(None, description="Стемы проекта (ZIP)"),
    author_id: uuid.UUID = Depends(get_current_user_id),
    author_name: str = Depends(get_current_user_username),
    db=Depends(get_db),
):
    service = BeatService(db)
    return await service.upload_beat(
        beat_form=beat_in,
        audio_full=audio_full,
        cover=cover,
        stems=stems,
        author_id=author_id,
        author_name=author_name,
    )


@router.get("/", response_model=PaginatedBeatsResponse)
async def get_beats_catalog(
    search: str | None = Query(None, description="Поиск по названию"),
    genre: str | None = Query(None, description="Фильтр по жанру"),
    instrument: str | None = Query(None, description="Фильтр по главному инструменту"),
    tag: str | None = Query(None, description="Фильтр по тегу"),
    min_bpm: int | None = Query(None, ge=40, le=300, description="Минимальный темп"),
    max_bpm: int | None = Query(None, ge=40, le=300, description="Максимальный темп"),
    author_id: uuid.UUID | None = Query(None, description="Фильтр по автору"),
    limit: int = Query(20, ge=1, le=100, description="Количество битов на странице"),
    offset: int = Query(0, ge=0, description="Смещение"),
    user_id: uuid.UUID | None = Depends(get_optional_user_id),
    db=Depends(get_db),
):
    service = BeatService(db)
    return await service.get_catalog(
        search=search,
        genre=genre,
        instrument=instrument,
        tag=tag,
        min_bpm=min_bpm,
        max_bpm=max_bpm,
        author_id=author_id,
        limit=limit,
        offset=offset,
        user_id=user_id,
    )


@router.get("/liked", response_model=PaginatedBeatsResponse)
async def get_liked_beats(current_user_id: uuid.UUID = Depends(get_current_user_id), db=Depends(get_db)):
    service = LikeService(db)
    return await service.get_liked_beats(current_user_id)


@router.get("/my-beats", response_model=PaginatedMyBeatsResponse)
async def get_my_beats(
    limit: int = Query(20, ge=1, le=100, description="Количество битов на странице"),
    offset: int = Query(0, ge=0, description="Смещение"),
    author_id: uuid.UUID = Depends(get_current_user_id),
    db=Depends(get_db),
):
    service = BeatService(db)
    return await service.get_my_beats(author_id, limit=limit, offset=offset)


@router.get("/my-purchases", response_model=list[MyPurchaseResponse])
async def get_my_purchases(current_user_id: uuid.UUID = Depends(get_current_user_id), db=Depends(get_db)):
    service = PurchaseService(db)
    return await service.get_my_purchases(current_user_id)


@router.post("/voice-tag", response_model=VoiceTagResponse, status_code=status.HTTP_201_CREATED)
async def upload_voice_tag(
    file: UploadFile = File(..., description="Войс-тег (MP3 или WAV, до 10 МБ)"),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
    db=Depends(get_db),
):
    service = VoiceTagService(db)
    return await service.upload(file, current_user_id)


@router.get("/voice-tag", response_model=VoiceTagResponse)
async def get_voice_tag(current_user_id: uuid.UUID = Depends(get_current_user_id), db=Depends(get_db)):
    service = VoiceTagService(db)
    return await service.get(current_user_id)


@router.delete("/voice-tag", status_code=status.HTTP_204_NO_CONTENT)
async def delete_voice_tag(current_user_id: uuid.UUID = Depends(get_current_user_id), db=Depends(get_db)):
    service = VoiceTagService(db)
    await service.delete(current_user_id)
    return None


@router.get("/payment/pending", response_model=list[PendingPaymentResponse])
async def get_pending_payments(current_user_id: uuid.UUID = Depends(get_current_user_id), db=Depends(get_db)):
    service = PaymentService(db)
    return await service.get_pending_payments(current_user_id)


@router.get("/payment/{payment_id}/result", response_model=PaymentResultResponse)
async def get_payment_result(
    payment_id: str, current_user_id: uuid.UUID = Depends(get_current_user_id), db=Depends(get_db)
):
    service = PaymentService(db)
    return await service.get_payment_result(payment_id, current_user_id)


@router.post("/webhook/payment", status_code=status.HTTP_200_OK)
async def yookassa_webhook(request: Request, db=Depends(get_db)):
    body = await request.json()
    client_ip = request.headers.get("X-Real-IP") or (request.client.host if request.client else "")
    service = PaymentService(db)
    await service.handle_webhook(body, client_ip)
    return {"status": "ok"}


# ─── Параметрические маршруты /{beat_id} ─────────────────────────────────────


@router.get("/{beat_id}/stream")
async def stream_beat_file(
    beat_id: uuid.UUID,
    token: str = Query(...),
    db=Depends(get_db),
):
    payload = verify_download_token(token)
    if str(beat_id) != payload["beat_id"]:
        from fastapi import HTTPException

        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Токен не соответствует биту")

    beat = await BeatRepo(db).get_by_id(beat_id)
    if not beat or beat.is_deleted:
        from fastapi import HTTPException

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Бит не найден")

    s3 = S3Storage()
    info = await s3.get_object_info(beat.audio_full_url)
    safe_title = beat.title.replace('"', '\\"')
    headers = {
        "Content-Disposition": f'attachment; filename="{safe_title}.wav"',
        "Content-Length": str(info["ContentLength"]),
        "Cache-Control": "no-store",
    }
    return StreamingResponse(s3.stream_object(beat.audio_full_url), media_type="audio/wav", headers=headers)


@router.get("/{beat_id}/stems/stream")
async def stream_stems_file(
    beat_id: uuid.UUID,
    token: str = Query(...),
    db=Depends(get_db),
):
    payload = verify_download_token(token)
    if str(beat_id) != payload["beat_id"] or payload.get("file") != "stems":
        from fastapi import HTTPException

        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Токен не соответствует файлу")

    beat = await BeatRepo(db).get_by_id(beat_id)
    if not beat or not beat.stems_url:
        from fastapi import HTTPException

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Стемы не найдены")

    s3 = S3Storage()
    info = await s3.get_object_info(beat.stems_url)
    safe_title = beat.title.replace('"', '\\"')
    headers = {
        "Content-Disposition": f'attachment; filename="{safe_title}_stems.zip"',
        "Content-Length": str(info["ContentLength"]),
        "Cache-Control": "no-store",
    }
    return StreamingResponse(s3.stream_object(beat.stems_url), media_type="application/zip", headers=headers)


@router.get("/{beat_id}/purchase-status", response_model=PurchaseStatusResponse)
async def get_purchase_status(
    beat_id: uuid.UUID,
    user_id: uuid.UUID | None = Depends(get_optional_user_id),
    db=Depends(get_db),
):
    if not user_id:
        return PurchaseStatusResponse(is_purchased=False)
    purchase = await PurchaseRepo(db).get_by_beat_and_buyer(beat_id, user_id)
    return PurchaseStatusResponse(is_purchased=purchase is not None)


@router.post("/{beat_id}/stems", response_model=BeatResponse)
async def upload_beat_stems(
    beat_id: uuid.UUID,
    stems: UploadFile = File(..., description="Архив стемов (ZIP)"),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
    db=Depends(get_db),
):
    service = StemsService(db)
    return await service.upload_stems(beat_id, current_user_id, stems)


@router.get("/{beat_id}/stems/download", response_model=StemsDownloadResponse)
async def download_beat_stems(
    beat_id: uuid.UUID, current_user_id: uuid.UUID = Depends(get_current_user_id), db=Depends(get_db)
):
    service = StemsService(db)
    return await service.get_stems_download_url(beat_id, current_user_id)


@router.post("/{beat_id}/play", response_model=PlayCountResponse)
async def record_play(beat_id: uuid.UUID, db=Depends(get_db)):
    service = PlayService(db)
    return await service.record_play(beat_id)


@router.post("/{beat_id}/like", response_model=LikeToggleResponse)
async def toggle_like(
    beat_id: uuid.UUID, current_user_id: uuid.UUID = Depends(get_current_user_id), db=Depends(get_db)
):
    service = LikeService(db)
    return await service.toggle(beat_id, current_user_id)


@router.get("/{beat_id}/download", response_model=DownloadResponse)
async def download_beat(
    beat_id: uuid.UUID, current_user_id: uuid.UUID = Depends(get_current_user_id), db=Depends(get_db)
):
    service = PurchaseService(db)
    return await service.get_download_url(beat_id, current_user_id)


@router.post("/{beat_id}/checkout", response_model=CheckoutResponse, status_code=status.HTTP_201_CREATED)
async def checkout_beat(beat_id: uuid.UUID, buyer_id: uuid.UUID = Depends(get_current_user_id), db=Depends(get_db)):
    service = PaymentService(db)
    return await service.create_checkout(beat_id, buyer_id)


@router.patch("/{beat_id}", response_model=BeatResponse)
async def update_beat(
    beat_id: uuid.UUID,
    update_data: BeatUpdate,
    current_user_id: uuid.UUID = Depends(get_current_user_id),
    db=Depends(get_db),
):
    service = BeatService(db)
    return await service.update_beat(beat_id=beat_id, current_user_id=current_user_id, update_in=update_data)


@router.delete("/{beat_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_beat(
    beat_id: uuid.UUID, current_user_id: uuid.UUID = Depends(get_current_user_id), db=Depends(get_db)
):
    service = BeatService(db)
    await service.remove_beat(beat_id, current_user_id)
    return None
