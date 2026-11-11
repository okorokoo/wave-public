"""Unit tests for PaymentService — business logic only, no DB/S3/YooKassa."""

import uuid
from datetime import UTC
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.services.payment import PaymentService


def _make_beat(author_id=None, is_deleted=False, price=Decimal("990.00"), title="Test Beat"):
    beat = MagicMock()
    beat.id = uuid.uuid4()
    beat.author_id = author_id or uuid.uuid4()
    beat.is_deleted = is_deleted
    beat.price = price
    beat.title = title
    beat.audio_full_url = "beats/folder/full_test.wav"
    beat.cover_url = None
    beat.stems_url = None
    return beat


def _make_payment(buyer_id=None, status="pending", beat_id=None):
    p = MagicMock()
    p.id = "pay_" + str(uuid.uuid4()).replace("-", "")
    p.buyer_id = buyer_id or uuid.uuid4()
    p.beat_id = beat_id or uuid.uuid4()
    p.status = status
    p.amount = Decimal("990.00")
    return p


def _make_service():
    svc = PaymentService.__new__(PaymentService)
    svc.db = MagicMock()
    svc.beat_repo = AsyncMock()
    svc.purchase_repo = AsyncMock()
    svc.payment_repo = AsyncMock()
    svc.s3 = AsyncMock()
    return svc


# ── create_checkout ────────────────────────────────────────────────────────────


class TestCreateCheckout:
    async def test_beat_not_found_raises_404(self):
        svc = _make_service()
        svc.beat_repo.get_by_id.return_value = None

        with pytest.raises(HTTPException) as exc:
            await svc.create_checkout(uuid.uuid4(), uuid.uuid4())
        assert exc.value.status_code == 404

    async def test_deleted_beat_raises_404(self):
        svc = _make_service()
        svc.beat_repo.get_by_id.return_value = _make_beat(is_deleted=True)

        with pytest.raises(HTTPException) as exc:
            await svc.create_checkout(uuid.uuid4(), uuid.uuid4())
        assert exc.value.status_code == 404

    async def test_own_beat_raises_400(self):
        svc = _make_service()
        buyer_id = uuid.uuid4()
        beat = _make_beat(author_id=buyer_id)
        svc.beat_repo.get_by_id.return_value = beat

        with pytest.raises(HTTPException) as exc:
            await svc.create_checkout(beat.id, buyer_id)
        assert exc.value.status_code == 400
        assert "собственный" in exc.value.detail

    async def test_already_purchased_raises_400(self):
        svc = _make_service()
        beat = _make_beat()
        svc.beat_repo.get_by_id.return_value = beat
        svc.purchase_repo.get_by_beat_and_buyer.return_value = MagicMock()  # existing purchase

        with pytest.raises(HTTPException) as exc:
            await svc.create_checkout(beat.id, uuid.uuid4())
        assert exc.value.status_code == 400
        assert "уже купили" in exc.value.detail

    async def test_pending_payment_exists_raises_409(self):
        svc = _make_service()
        beat = _make_beat()
        svc.beat_repo.get_by_id.return_value = beat
        svc.purchase_repo.get_by_beat_and_buyer.return_value = None
        svc.payment_repo.get_pending_by_beat_and_buyer.return_value = _make_payment()

        with pytest.raises(HTTPException) as exc:
            await svc.create_checkout(beat.id, uuid.uuid4())
        assert exc.value.status_code == 409


# ── get_payment_result ─────────────────────────────────────────────────────────


class TestGetPaymentResult:
    async def test_payment_not_found_raises_404(self):
        svc = _make_service()
        svc.payment_repo.get_by_id.return_value = None

        with pytest.raises(HTTPException) as exc:
            await svc.get_payment_result("pay_123", uuid.uuid4())
        assert exc.value.status_code == 404

    async def test_wrong_buyer_raises_403(self):
        svc = _make_service()
        payment = _make_payment(buyer_id=uuid.uuid4())
        svc.payment_repo.get_by_id.return_value = payment

        with pytest.raises(HTTPException) as exc:
            await svc.get_payment_result(payment.id, uuid.uuid4())  # different buyer
        assert exc.value.status_code == 403

    async def test_canceled_payment_raises_402(self):
        svc = _make_service()
        buyer_id = uuid.uuid4()
        payment = _make_payment(buyer_id=buyer_id, status="canceled")
        svc.payment_repo.get_by_id.return_value = payment

        with pytest.raises(HTTPException) as exc:
            await svc.get_payment_result(payment.id, buyer_id)
        assert exc.value.status_code == 402

    async def test_pending_when_yookassa_unavailable(self):
        svc = _make_service()
        buyer_id = uuid.uuid4()
        payment = _make_payment(buyer_id=buyer_id, status="pending")
        svc.payment_repo.get_by_id.return_value = payment

        with patch("app.services.payment.YooPayment") as mock_yoo, patch("app.services.payment._configure_yookassa"):
            mock_yoo.find_one.side_effect = Exception("YooKassa down")
            result = await svc.get_payment_result(payment.id, buyer_id)

        assert result.status == "pending"
        assert result.beat_id is None

    async def test_succeeded_payment_returns_beat_info(self):
        # Ссылку на скачивание PaymentResultResponse больше не содержит — фронт
        # запрашивает свежий stream-токен отдельно через GET /beats/{id}/download.
        svc = _make_service()
        buyer_id = uuid.uuid4()
        beat = _make_beat()
        payment = _make_payment(buyer_id=buyer_id, status="succeeded", beat_id=beat.id)
        svc.payment_repo.get_by_id.return_value = payment
        svc.beat_repo.get_by_id.return_value = beat

        result = await svc.get_payment_result(payment.id, buyer_id)

        assert result.status == "succeeded"
        assert result.beat_id == str(beat.id)
        assert result.beat_title == beat.title

    async def test_succeeded_but_beat_deleted_raises_404(self):
        svc = _make_service()
        buyer_id = uuid.uuid4()
        payment = _make_payment(buyer_id=buyer_id, status="succeeded")
        svc.payment_repo.get_by_id.return_value = payment
        svc.beat_repo.get_by_id.return_value = None

        with pytest.raises(HTTPException) as exc:
            await svc.get_payment_result(payment.id, buyer_id)
        assert exc.value.status_code == 404


# ── get_pending_payments ───────────────────────────────────────────────────────


class TestGetPendingPayments:
    async def test_empty_returns_empty_list(self):
        svc = _make_service()
        svc.payment_repo.get_pending_by_buyer.return_value = []

        result = await svc.get_pending_payments(uuid.uuid4())
        assert result == []

    async def test_returns_response_for_each_pending(self):
        svc = _make_service()
        buyer_id = uuid.uuid4()

        payment = _make_payment(buyer_id=buyer_id)
        beat = _make_beat()
        beat.cover_url = None
        beat.author_name = "DJ Test"

        from datetime import datetime

        payment.created_at = datetime.now(UTC)

        svc.payment_repo.get_pending_by_buyer.return_value = [(payment, beat)]

        result = await svc.get_pending_payments(buyer_id)

        assert len(result) == 1
        assert result[0].payment_id == payment.id
        assert result[0].beat_title == beat.title
        assert result[0].beat_author_name == beat.author_name
        assert result[0].beat_cover_url is None
