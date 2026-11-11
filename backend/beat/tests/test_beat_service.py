"""Unit tests for BeatService — upload validation and delete logic."""

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.constants import PREVIEW_PROCESSING
from app.services.beat import BeatService


def _make_beat(
    author_id=None,
    is_deleted=False,
    has_cover=False,
    has_preview=True,
    has_stems=False,
):
    beat = MagicMock()
    beat.id = uuid.uuid4()
    beat.author_id = author_id or uuid.uuid4()
    beat.is_deleted = is_deleted
    beat.audio_full_url = "beats/folder/full.wav"
    beat.audio_preview_url = "beats/folder/preview.mp3" if has_preview else PREVIEW_PROCESSING
    beat.audio_mp3_url = None
    beat.cover_url = "beats/folder/cover.jpg" if has_cover else None
    beat.stems_url = "beats/folder/stems.zip" if has_stems else None
    beat.title = "Test Beat"
    beat.bpm = 120
    beat.key = "Cm"
    beat.price = Decimal("990.00")
    beat.genre = "Trap"
    beat.primary_instrument = None
    beat.tags = []
    beat.play_count = 0
    beat.author_name = "Tester"
    return beat


def _make_upload_file(content_type="audio/wav", filename="beat.wav", size=1024):
    f = MagicMock()
    f.content_type = content_type
    f.filename = filename
    f.read = AsyncMock(return_value=b"R" * size)  # fake WAV content
    f.seek = AsyncMock(return_value=None)
    return f


def _make_service():
    svc = BeatService.__new__(BeatService)
    svc.repo = AsyncMock()
    svc.purchase_repo = AsyncMock()
    svc.voice_tag_repo = AsyncMock()
    svc.like_repo = AsyncMock()
    svc.s3 = AsyncMock()
    svc.rmq = AsyncMock()
    return svc


# ── upload_beat ────────────────────────────────────────────────────────────────


class TestUploadBeat:
    async def test_mp3_file_raises_400(self):
        svc = _make_service()
        bad_file = _make_upload_file(content_type="audio/mpeg", filename="beat.mp3")

        from app.schemas.beat import BeatForm

        form = MagicMock(spec=BeatForm)
        form.title = "My Beat"
        form.bpm = 140
        form.key = "Am"
        form.price = Decimal("990")
        form.genre = "Trap"
        form.primary_instrument = None
        form.tags = []

        with pytest.raises(HTTPException) as exc:
            await svc.upload_beat(
                beat_form=form,
                audio_full=bad_file,
                author_id=uuid.uuid4(),
            )
        assert exc.value.status_code == 400
        assert "WAV" in exc.value.detail

    async def test_wav_file_too_large_raises_413(self):
        svc = _make_service()

        import app.services.beat as beat_module

        original = beat_module.settings.MAX_AUDIO_UPLOAD_BYTES
        beat_module.settings.MAX_AUDIO_UPLOAD_BYTES = 10

        big_file = _make_upload_file(size=20)

        from app.schemas.beat import BeatForm

        form = MagicMock(spec=BeatForm)
        form.title = "Big Beat"
        form.bpm = 140
        form.key = "Am"
        form.price = Decimal("990")
        form.genre = "Trap"
        form.primary_instrument = None
        form.tags = []

        try:
            with pytest.raises(HTTPException) as exc:
                await svc.upload_beat(
                    beat_form=form,
                    audio_full=big_file,
                    author_id=uuid.uuid4(),
                )
            assert exc.value.status_code == 413
        finally:
            beat_module.settings.MAX_AUDIO_UPLOAD_BYTES = original


# ── remove_beat ────────────────────────────────────────────────────────────────


class TestRemoveBeat:
    async def test_beat_not_found_raises_404(self):
        svc = _make_service()
        svc.repo.get_by_id.return_value = None

        with pytest.raises(HTTPException) as exc:
            await svc.remove_beat(uuid.uuid4(), uuid.uuid4())
        assert exc.value.status_code == 404

    async def test_deleted_beat_raises_404(self):
        svc = _make_service()
        svc.repo.get_by_id.return_value = _make_beat(is_deleted=True)

        with pytest.raises(HTTPException) as exc:
            await svc.remove_beat(uuid.uuid4(), uuid.uuid4())
        assert exc.value.status_code == 404

    async def test_not_author_raises_403(self):
        svc = _make_service()
        beat = _make_beat(author_id=uuid.uuid4())
        svc.repo.get_by_id.return_value = beat

        with pytest.raises(HTTPException) as exc:
            await svc.remove_beat(beat.id, uuid.uuid4())  # different user
        assert exc.value.status_code == 403

    async def test_soft_delete_when_purchases_exist(self):
        svc = _make_service()
        author_id = uuid.uuid4()
        beat = _make_beat(author_id=author_id, has_cover=True, has_preview=True)
        svc.repo.get_by_id.return_value = beat
        svc.purchase_repo.exists_for_beat.return_value = True

        await svc.remove_beat(beat.id, author_id)

        svc.repo.soft_delete.assert_called_once_with(beat)
        svc.repo.delete.assert_not_called()
        # Preview + cover deleted, full audio kept for existing buyers
        deleted_keys = svc.s3.delete_objects.call_args[0][0]
        assert beat.audio_preview_url in deleted_keys
        assert beat.cover_url in deleted_keys
        assert beat.audio_full_url not in deleted_keys

    async def test_hard_delete_when_no_purchases(self):
        svc = _make_service()
        author_id = uuid.uuid4()
        beat = _make_beat(author_id=author_id, has_cover=True, has_preview=True)
        svc.repo.get_by_id.return_value = beat
        svc.purchase_repo.exists_for_beat.return_value = False

        await svc.remove_beat(beat.id, author_id)

        svc.repo.delete.assert_called_once_with(beat)
        svc.repo.soft_delete.assert_not_called()
        deleted_keys = svc.s3.delete_objects.call_args[0][0]
        assert beat.audio_full_url in deleted_keys
        assert beat.audio_preview_url in deleted_keys
        assert beat.cover_url in deleted_keys

    async def test_hard_delete_includes_stems_when_present(self):
        svc = _make_service()
        author_id = uuid.uuid4()
        beat = _make_beat(author_id=author_id, has_stems=True)
        svc.repo.get_by_id.return_value = beat
        svc.purchase_repo.exists_for_beat.return_value = False

        await svc.remove_beat(beat.id, author_id)

        deleted_keys = svc.s3.delete_objects.call_args[0][0]
        assert beat.stems_url in deleted_keys

    async def test_hard_delete_no_stems_key_excluded(self):
        svc = _make_service()
        author_id = uuid.uuid4()
        beat = _make_beat(author_id=author_id, has_stems=False)
        svc.repo.get_by_id.return_value = beat
        svc.purchase_repo.exists_for_beat.return_value = False

        await svc.remove_beat(beat.id, author_id)

        deleted_keys = svc.s3.delete_objects.call_args[0][0]
        assert None not in deleted_keys
