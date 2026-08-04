import uuid
from typing import Optional, List

from fastapi import HTTPException, status, UploadFile

from app.core.broker import RabbitBroker
from app.core.repo import BeatRepo, PurchaseRepo, UserVoiceTagRepo, LikeRepo
from app.core.s3 import S3Storage
from app.models.models import Beat
from app.schemas.beat import BeatUpdate, BeatForm, BeatResponse, PurchaseResponse, DownloadResponse, MyPurchaseResponse, PaginatedBeatsResponse, MyBeatResponse, PaginatedMyBeatsResponse, VoiceTagResponse, LikeToggleResponse, PlayCountResponse
from config import settings

PREVIEW_PROCESSING = "processing"
BEAT_DELETED = "deleted"
ALLOWED_AUDIO_CONTENT_TYPES = {
    "audio/wav",
    "audio/x-wav",
    "audio/wave",
    "audio/vnd.wave",
}
ALLOWED_VOICE_TAG_CONTENT_TYPES = {
    "audio/mpeg",
    "audio/mp3",
    "audio/wav",
    "audio/x-wav",
    "audio/wave",
}
MAX_VOICE_TAG_BYTES = 10 * 1024 * 1024  # 10 MB


class BeatService:
    def __init__(self, db):
        self.repo = BeatRepo(db)
        self.purchase_repo = PurchaseRepo(db)
        self.voice_tag_repo = UserVoiceTagRepo(db)
        self.like_repo = LikeRepo(db)
        self.s3 = S3Storage()
        self.rmq = RabbitBroker(url=settings.rabbitmq_url)

    async def _to_response(self, beat: Beat, likes_count: int = 0, is_liked: bool = False) -> BeatResponse:
        if beat.audio_preview_url in (PREVIEW_PROCESSING, BEAT_DELETED):
            preview_url = beat.audio_preview_url
        else:
            preview_url = await self.s3.generate_presigned_url(beat.audio_preview_url)

        cover_url = await self.s3.generate_presigned_url(beat.cover_url) if beat.cover_url else None

        return BeatResponse(
            id=beat.id,
            title=beat.title,
            bpm=beat.bpm,
            key=beat.key,
            price=beat.price,
            genre=beat.genre,
            primary_instrument=beat.primary_instrument,
            audio_preview_url=preview_url,
            cover_url=cover_url,
            tags=[bt.tag for bt in beat.tags],
            author_id=beat.author_id,
            author_name=beat.author_name,
            likes_count=likes_count,
            is_liked=is_liked,
            play_count=beat.play_count,
        )

    async def upload_beat(
            self,
            beat_form: BeatForm,
            audio_full: UploadFile,
            author_id: uuid.UUID,
            author_name: str = "",
            cover: Optional[UploadFile] = None,
    ) -> BeatResponse:
        filename = audio_full.filename or ""
        if (
            audio_full.content_type not in ALLOWED_AUDIO_CONTENT_TYPES
            and not filename.lower().endswith(".wav")
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Аудиофайл должен быть в формате WAV",
            )

        audio_content = await audio_full.read()
        if len(audio_content) > settings.MAX_AUDIO_UPLOAD_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Размер WAV-файла превышает допустимый лимит",
            )
        await audio_full.seek(0)

        beat_folder_id = uuid.uuid4()

        full_key = await self.s3.upload_file(
            audio_full, f"beats/{beat_folder_id}/full_{audio_full.filename}"
        )

        cover_key = None
        if cover:
            allowed = {"image/jpeg", "image/png", "image/webp"}
            if cover.content_type not in allowed:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Обложка должна быть в формате JPEG, PNG или WebP",
                )
            cover_key = await self.s3.upload_file(
                cover, f"beats/{beat_folder_id}/cover_{cover.filename}"
            )

        beat_data = {
            "title": beat_form.title,
            "bpm": beat_form.bpm,
            "key": beat_form.key,
            "price": beat_form.price,
            "genre": beat_form.genre,
            "primary_instrument": beat_form.primary_instrument,
            "author_id": author_id,
            "author_name": author_name or None,
            "audio_preview_url": PREVIEW_PROCESSING,
            "audio_full_url": full_key,
            "cover_url": cover_key,
            "tags": beat_form.tags,
        }

        new_beat = await self.repo.create(beat_data)

        user_tag = await self.voice_tag_repo.get_by_user(author_id)
        await self.rmq.publish(
            queue_name="beat_processing_queue",
            body={
                "beat_id": str(new_beat.id),
                "full_audio_url": full_key,
                "filename": audio_full.filename,
                "voice_tag_key": user_tag.s3_key if user_tag else None,
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
        if not beat or beat.is_deleted:
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
            max_bpm: Optional[int] = None,
            tag: Optional[str] = None,
            author_id: Optional[uuid.UUID] = None,
            limit: int = 20,
            offset: int = 0,
            user_id: Optional[uuid.UUID] = None,
    ) -> PaginatedBeatsResponse:
        total = await self.repo.count_beats(search=search, genre=genre, instrument=instrument, min_bpm=min_bpm, max_bpm=max_bpm, tag=tag, author_id=author_id)
        beats = await self.repo.list_beats(search=search, genre=genre, instrument=instrument, min_bpm=min_bpm, max_bpm=max_bpm, tag=tag, author_id=author_id, limit=limit, offset=offset)

        beat_ids = [b.id for b in beats]
        counts = await self.like_repo.get_counts(beat_ids)
        liked_set = await self.like_repo.get_liked_set(user_id, beat_ids) if user_id else set()

        items = [
            await self._to_response(b, likes_count=counts.get(b.id, 0), is_liked=b.id in liked_set)
            for b in beats
        ]
        return PaginatedBeatsResponse(items=items, total=total, limit=limit, offset=offset)

    async def get_my_beats(
            self,
            author_id: uuid.UUID,
            limit: int = 20,
            offset: int = 0,
    ) -> PaginatedMyBeatsResponse:
        total = await self.repo.count_by_author(author_id)
        rows = await self.repo.list_by_author(author_id, limit=limit, offset=offset)
        items = []
        for beat, sales_count in rows:
            base = await self._to_response(beat)
            items.append(MyBeatResponse(**base.model_dump(), sales_count=sales_count))
        return PaginatedMyBeatsResponse(items=items, total=total, limit=limit, offset=offset)

    async def remove_beat(self, beat_id: uuid.UUID, current_user_id: uuid.UUID) -> None:
        beat = await self.repo.get_by_id(beat_id)
        if not beat or beat.is_deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Бит не найден")

        if beat.author_id != current_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Вы не являетесь автором этого бита и не можете его удалить",
            )

        has_purchases = await self.purchase_repo.exists_for_beat(beat_id)

        if has_purchases:
            # Покупатели существуют — мягкое удаление.
            # WAV-файл остаётся в S3, доступ покупателей сохраняется.
            # Превью и обложка удаляются — они больше не нужны.
            keys_to_delete = []
            if beat.audio_preview_url and beat.audio_preview_url not in (PREVIEW_PROCESSING, BEAT_DELETED):
                keys_to_delete.append(beat.audio_preview_url)
            if beat.cover_url:
                keys_to_delete.append(beat.cover_url)
            if keys_to_delete:
                await self.s3.delete_objects(keys_to_delete)
            await self.repo.soft_delete(beat)
        else:
            # Покупок нет — жёсткое удаление, всё чистим.
            keys = [beat.audio_full_url]
            if beat.audio_preview_url and beat.audio_preview_url not in (PREVIEW_PROCESSING, BEAT_DELETED):
                keys.append(beat.audio_preview_url)
            if beat.cover_url:
                keys.append(beat.cover_url)
            await self.s3.delete_objects(keys)
            await self.repo.delete(beat)


class LikeService:
    def __init__(self, db):
        self.like_repo = LikeRepo(db)
        self.beat_repo = BeatRepo(db)
        self.s3 = S3Storage()

    async def toggle(self, beat_id: uuid.UUID, user_id: uuid.UUID) -> LikeToggleResponse:
        beat = await self.beat_repo.get_by_id(beat_id)
        if not beat or beat.is_deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Бит не найден")
        liked, count = await self.like_repo.toggle(beat_id, user_id)
        return LikeToggleResponse(liked=liked, likes_count=count)

    async def get_liked_beats(self, user_id: uuid.UUID) -> PaginatedBeatsResponse:
        beats = await self.like_repo.get_liked_beats(user_id)
        beat_ids = [b.id for b in beats]
        counts = await self.like_repo.get_counts(beat_ids)
        beat_service = BeatService.__new__(BeatService)
        beat_service.s3 = self.s3
        items = [
            await beat_service._to_response(b, likes_count=counts.get(b.id, 0), is_liked=True)
            for b in beats
        ]
        return PaginatedBeatsResponse(items=items, total=len(items), limit=len(items), offset=0)


class VoiceTagService:
    def __init__(self, db):
        self.repo = UserVoiceTagRepo(db)
        self.s3 = S3Storage()

    async def upload(self, file: UploadFile, user_id: uuid.UUID) -> VoiceTagResponse:
        filename = file.filename or ""
        if (
            file.content_type not in ALLOWED_VOICE_TAG_CONTENT_TYPES
            and not filename.lower().endswith((".mp3", ".wav"))
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Войс-тег должен быть в формате MP3 или WAV",
            )

        content = await file.read()
        if len(content) > MAX_VOICE_TAG_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Файл войс-тега не должен превышать 10 МБ",
            )
        await file.seek(0)

        ext = "mp3" if "mp3" in (file.content_type or "") or filename.lower().endswith(".mp3") else "wav"
        s3_key = f"voice_tags/{user_id}/voice_tag.{ext}"
        await self.s3.upload_file(file, s3_key)

        record = await self.repo.upsert(user_id, s3_key)
        url = await self.s3.generate_presigned_url(s3_key)
        return VoiceTagResponse(url=url, uploaded_at=record.uploaded_at)

    async def get(self, user_id: uuid.UUID) -> VoiceTagResponse:
        record = await self.repo.get_by_user(user_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Войс-тег не найден")
        url = await self.s3.generate_presigned_url(record.s3_key)
        return VoiceTagResponse(url=url, uploaded_at=record.uploaded_at)

    async def delete(self, user_id: uuid.UUID) -> None:
        s3_key = await self.repo.delete(user_id)
        if not s3_key:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Войс-тег не найден")
        await self.s3.delete_objects([s3_key])


class PlayService:
    def __init__(self, db):
        self.repo = BeatRepo(db)

    async def record_play(self, beat_id: uuid.UUID) -> PlayCountResponse:
        beat = await self.repo.get_by_id(beat_id)
        if not beat or beat.is_deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Бит не найден")
        new_count = await self.repo.increment_play_count(beat_id)
        return PlayCountResponse(play_count=new_count)


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
        download_url = await self.s3.generate_presigned_url(
            beat.audio_full_url,
            expires_in=settings.S3_DOWNLOAD_URL_EXPIRE_SECONDS,
        )

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

        download_url = await self.s3.generate_presigned_url(
            beat.audio_full_url,
            expires_in=settings.S3_DOWNLOAD_URL_EXPIRE_SECONDS,
        )
        return DownloadResponse(download_url=download_url)

    async def get_my_purchases(self, buyer_id: uuid.UUID) -> List[MyPurchaseResponse]:
        rows = await self.purchase_repo.get_by_buyer(buyer_id)
        result = []
        for purchase, beat in rows:
            if beat.audio_preview_url in (PREVIEW_PROCESSING, BEAT_DELETED):
                preview_url = beat.audio_preview_url
            else:
                preview_url = await self.s3.generate_presigned_url(beat.audio_preview_url)

            beat_response = BeatResponse(
                id=beat.id,
                title=beat.title,
                bpm=beat.bpm,
                key=beat.key,
                price=beat.price,
                genre=beat.genre,
                primary_instrument=beat.primary_instrument,
                audio_preview_url=preview_url,
                cover_url=await self.s3.generate_presigned_url(beat.cover_url) if beat.cover_url else None,
                tags=[bt.tag for bt in beat.tags],
                author_id=beat.author_id,
            )
            download_url = await self.s3.generate_presigned_url(
                beat.audio_full_url,
                expires_in=settings.S3_DOWNLOAD_URL_EXPIRE_SECONDS,
            )
            result.append(MyPurchaseResponse(
                id=purchase.id,
                license_type=purchase.license_type,
                purchased_at=purchase.purchased_at,
                download_url=download_url,
                beat=beat_response,
            ))
        return result
