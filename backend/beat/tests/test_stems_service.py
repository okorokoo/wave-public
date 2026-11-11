"""Unit tests for StemsService — authorization, format validation, license gate."""

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.services.beat import StemsService


def _make_beat(author_id=None, is_deleted=False, has_stems=False):
    beat = MagicMock()
    beat.id = uuid.uuid4()
    beat.author_id = author_id or uuid.uuid4()
    beat.is_deleted = is_deleted
    beat.audio_full_url = "beats/abc123/full_beat.wav"
    beat.cover_url = None
    beat.stems_url = "beats/abc123/stems.zip" if has_stems else None
    beat.title = "Test Beat"
    beat.bpm = 140
    beat.key = "Am"
    beat.price = Decimal("990.00")
    beat.genre = "Trap"
    beat.primary_instrument = None
    beat.description = None
    beat.tags = []
    beat.play_count = 0
    beat.author_name = "Test Author"
    beat.is_processed = True
    beat.audio_preview_url = "beats/abc123/preview.mp3"
    beat.audio_mp3_url = None
    return beat


def _make_purchase(license_type="basic"):
    p = MagicMock()
    p.license_type = license_type
    return p


def _make_upload_file(content_type="application/zip", filename="stems.zip", size=1024):
    f = MagicMock()
    f.content_type = content_type
    f.filename = filename
    f.read = AsyncMock(return_value=b"x" * size)
    f.seek = AsyncMock(return_value=None)
    return f


def _make_service():
    svc = StemsService.__new__(StemsService)
    svc.beat_repo = AsyncMock()
    svc.purchase_repo = AsyncMock()
    svc.s3 = AsyncMock()
    return svc


# ── upload_stems ───────────────────────────────────────────────────────────────


class TestUploadStems:
    async def test_beat_not_found_raises_404(self):
        svc = _make_service()
        svc.beat_repo.get_by_id.return_value = None

        with pytest.raises(HTTPException) as exc:
            await svc.upload_stems(uuid.uuid4(), uuid.uuid4(), _make_upload_file())
        assert exc.value.status_code == 404

    async def test_deleted_beat_raises_404(self):
        svc = _make_service()
        svc.beat_repo.get_by_id.return_value = _make_beat(is_deleted=True)

        with pytest.raises(HTTPException) as exc:
            await svc.upload_stems(uuid.uuid4(), uuid.uuid4(), _make_upload_file())
        assert exc.value.status_code == 404

    async def test_not_author_raises_403(self):
        svc = _make_service()
        beat = _make_beat(author_id=uuid.uuid4())
        svc.beat_repo.get_by_id.return_value = beat

        other_user = uuid.uuid4()  # different from beat.author_id
        with pytest.raises(HTTPException) as exc:
            await svc.upload_stems(beat.id, other_user, _make_upload_file())
        assert exc.value.status_code == 403

    async def test_invalid_content_type_raises_400(self):
        svc = _make_service()
        author_id = uuid.uuid4()
        beat = _make_beat(author_id=author_id)
        svc.beat_repo.get_by_id.return_value = beat

        bad_file = _make_upload_file(content_type="audio/mpeg", filename="stems.mp3")
        with pytest.raises(HTTPException) as exc:
            await svc.upload_stems(beat.id, author_id, bad_file)
        assert exc.value.status_code == 400
        assert "ZIP" in exc.value.detail

    async def test_zip_extension_accepted_despite_generic_content_type(self):
        svc = _make_service()
        author_id = uuid.uuid4()
        beat = _make_beat(author_id=author_id)
        svc.beat_repo.get_by_id.return_value = beat
        svc.beat_repo.update_stems_url = AsyncMock()
        svc.s3.upload_file.return_value = "beats/abc123/stems.zip"
        svc.s3.get_public_url = MagicMock(return_value="https://example.com/preview.mp3")

        # octet-stream + .zip extension should be accepted
        file = _make_upload_file(content_type="application/octet-stream", filename="my_stems.zip")
        result = await svc.upload_stems(beat.id, author_id, file)
        assert result.has_stems is True

    async def test_file_too_large_raises_413(self):
        svc = _make_service()
        author_id = uuid.uuid4()
        beat = _make_beat(author_id=author_id)
        svc.beat_repo.get_by_id.return_value = beat

        # Use a small limit so we don't allocate 500 MB in memory
        import app.services.beat as beat_module

        original = beat_module.MAX_STEMS_BYTES
        beat_module.MAX_STEMS_BYTES = 10

        file = _make_upload_file(size=20)  # 20 bytes > patched limit of 10
        try:
            with pytest.raises(HTTPException) as exc:
                await svc.upload_stems(beat.id, author_id, file)
            assert exc.value.status_code == 413
        finally:
            beat_module.MAX_STEMS_BYTES = original

    async def test_success_updates_beat_and_returns_response(self):
        svc = _make_service()
        author_id = uuid.uuid4()
        beat = _make_beat(author_id=author_id)
        svc.beat_repo.get_by_id.return_value = beat
        svc.beat_repo.update_stems_url = AsyncMock()
        svc.s3.upload_file.return_value = "beats/abc123/stems.zip"
        svc.s3.get_public_url = MagicMock(return_value="https://example.com/preview.mp3")

        result = await svc.upload_stems(beat.id, author_id, _make_upload_file())

        svc.beat_repo.update_stems_url.assert_called_once()
        svc.s3.upload_file.assert_called_once()
        assert result.has_stems is True


# ── get_stems_download_url ─────────────────────────────────────────────────────


class TestGetStemsDownloadUrl:
    async def test_beat_not_found_raises_404(self):
        svc = _make_service()
        svc.beat_repo.get_by_id.return_value = None

        with pytest.raises(HTTPException) as exc:
            await svc.get_stems_download_url(uuid.uuid4(), uuid.uuid4())
        assert exc.value.status_code == 404

    async def test_no_stems_raises_404(self):
        svc = _make_service()
        beat = _make_beat(has_stems=False)
        svc.beat_repo.get_by_id.return_value = beat

        with pytest.raises(HTTPException) as exc:
            await svc.get_stems_download_url(beat.id, uuid.uuid4())
        assert exc.value.status_code == 404
        assert "не загружены" in exc.value.detail

    async def test_no_purchase_raises_403(self):
        svc = _make_service()
        beat = _make_beat(has_stems=True)
        svc.beat_repo.get_by_id.return_value = beat
        svc.purchase_repo.get_by_beat_and_buyer.return_value = None

        with pytest.raises(HTTPException) as exc:
            await svc.get_stems_download_url(beat.id, uuid.uuid4())
        assert exc.value.status_code == 403
        assert "не купили" in exc.value.detail

    async def test_basic_license_raises_403(self):
        svc = _make_service()
        beat = _make_beat(has_stems=True)
        svc.beat_repo.get_by_id.return_value = beat
        svc.purchase_repo.get_by_beat_and_buyer.return_value = _make_purchase(license_type="basic")

        with pytest.raises(HTTPException) as exc:
            await svc.get_stems_download_url(beat.id, uuid.uuid4())
        assert exc.value.status_code == 403
        assert "премиум" in exc.value.detail

    async def test_premium_license_returns_stream_url(self):
        # Стемы больше не отдаются presigned S3-ссылкой — beat-service стримит их сам
        # по JWT download-токену (см. app/core/download_token.py).
        svc = _make_service()
        beat = _make_beat(has_stems=True)
        buyer_id = uuid.uuid4()
        svc.beat_repo.get_by_id.return_value = beat
        svc.purchase_repo.get_by_beat_and_buyer.return_value = _make_purchase(license_type="premium")

        result = await svc.get_stems_download_url(beat.id, buyer_id)

        assert result.stream_url.startswith(f"/beats/{beat.id}/stems/stream?token=")
        token = result.stream_url.rsplit("token=", 1)[1]
        from app.core.download_token import verify_download_token

        payload = verify_download_token(token)
        assert payload["beat_id"] == str(beat.id)
        assert payload["buyer_id"] == str(buyer_id)
        assert payload["file"] == "stems"
