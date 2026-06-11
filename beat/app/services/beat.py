import uuid
from typing import Optional, List

from fastapi import HTTPException, status, UploadFile

from app.core.broker import RabbitBroker
from app.core.repo import BeatRepo, PurchaseRepo
from app.core.s3 import S3Storage
from app.models.models import Beat
from app.schemas.beat import BeatUpdate, BeatForm, BeatResponse, PurchaseResponse, DownloadResponse
from config import settings

PREVIEW_PROCESSING = "processing"


class BeatService:
    def __init__(self, db):
        self.repo = BeatRepo(db)
        self.s3 = S3Storage()
        self.rmq = RabbitBroker(url=settings.rabbitmq_url)

    async def _to_response(self, beat: Beat) -> BeatResponse:
        """Конвертирует ORM-объект в схему, подменяя S3-ключ превью на presigned URL."""
        if beat.audio_preview_url == PREVIEW_PROCESSING:
            preview_url = PREVIEW_PROCESSING
        else:
            preview_url = await self.s3.generate_presigned_url(beat.audio_preview_url)

        return BeatResponse(
            id=beat.id,
            title=beat.title,
            bpm=beat.bpm,
            key=beat.key,
            price=beat.price,
            genre=beat.genre,
            primary_instrument=beat.primary_instrument,
            audio_preview_url=preview_url,
            author_id=beat.author_id,
        )

    async def upload_beat(
            self,
            beat_form: BeatForm,
            audio_full: UploadFile,
            author_id: uuid.UUID
    ) -> BeatResponse:
        beat_folder_id = uuid.uuid4()

        full_key = await self.s3.upload_file(
            audio_full, f"beats/{beat_folder_id}/full_{audio_full.filename}"
        )

        beat_data = {
            "title": beat_form.title,
            "bpm": beat_form.bpm,
            "key": beat_form.key,
            "price": beat_form.price,
            "genre": beat_form.genre,
            "primary_instrument": beat_form.primary_instrument,
            "author_id": author_id,
            "audio_preview_url": PREVIEW_PROCESSING,
            "audio_full_url": full_key,
        }

        new_beat = await self.repo.create(beat_data)

        await self.rmq.publish(
            queue_name="beat_processing_queue",
            body={
                "beat_id": str(new_beat.id),
                "full_audio_url": full_key,
                "filename": audio_full.filename,
            },
        )

        return await self._to_response(new_beat)

    async def update_beat(
            self,
            beat_id: uuid.UUID,
            current_user_id: uuid.UUID,
            update_in: BeatUpdate
    ) -> BeatResponse:
        beat = await self.repo.get_by_id(beat_id)
        if not beat:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Бит не найден")

        if beat.author_id != current_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Вы не являетесь автором этого бита и не можете его редактировать",
            )

        update_data = update_in.model_dump(exclude_unset=True)
        if not update_data:
            return await self._to_response(beat)

        updated_beat = await self.repo.update(beat, update_data)
        return await self._to_response(updated_beat)

    async def get_catalog(
            self,
            search: Optional[str] = None,
            genre: Optional[str] = None,
            instrument: Optional[str] = None,
            min_bpm: Optional[int] = None,
            max_bpm: Optional[int] = None
    ) -> List[BeatResponse]:
        beats = await self.repo.list_beats(
            search=search,
            genre=genre,
            instrument=instrument,
            min_bpm=min_bpm,
            max_bpm=max_bpm,
        )
        return [await self._to_response(b) for b in beats]

    async def remove_beat(self, beat_id: uuid.UUID, current_user_id: uuid.UUID) -> None:
        beat = await self.repo.get_by_id(beat_id)
        if not beat:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Бит не найден")

        if beat.author_id != current_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Вы не являетесь автором этого бита и не можете его удалить",
            )

        await self.repo.delete(beat)


class PurchaseService:
    def __init__(self, db):
        self.beat_repo = BeatRepo(db)
        self.purchase_repo = PurchaseRepo(db)
        self.s3 = S3Storage()

    async def purchase_beat(self, beat_id: uuid.UUID, buyer_id: uuid.UUID) -> PurchaseResponse:
        beat = await self.beat_repo.get_by_id(beat_id)
        if not beat:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Бит не найден")

        if beat.author_id == buyer_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Нельзя купить собственный бит")

        if await self.purchase_repo.get_by_beat_and_buyer(beat_id, buyer_id):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Вы уже купили этот бит")

        purchase = await self.purchase_repo.create(beat_id, buyer_id)
        download_url = await self.s3.generate_presigned_url(beat.audio_full_url, expires_in=3600)

        return PurchaseResponse(
            id=purchase.id,
            beat_id=purchase.beat_id,
            buyer_id=purchase.buyer_id,
            license_type=purchase.license_type,
            purchased_at=purchase.purchased_at,
            download_url=download_url,
        )

    async def get_download_url(self, beat_id: uuid.UUID, buyer_id: uuid.UUID) -> DownloadResponse:
        beat = await self.beat_repo.get_by_id(beat_id)
        if not beat:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Бит не найден")

        if not await self.purchase_repo.get_by_beat_and_buyer(beat_id, buyer_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Вы не купили этот бит")

        download_url = await self.s3.generate_presigned_url(beat.audio_full_url, expires_in=3600)
        return DownloadResponse(download_url=download_url)
