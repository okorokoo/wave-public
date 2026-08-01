import asyncio
import uuid
from decimal import Decimal

from fastapi import HTTPException, status
from yookassa import Configuration, Payment as YooPayment
from yookassa.domain.common import SecurityHelper
from yookassa.domain.notification import WebhookNotificationEventType, WebhookNotificationFactory

from app.core.repo import BeatRepo, PurchaseRepo, PaymentRepo
from app.schemas.beat import CheckoutResponse
from config import settings


def _configure_yookassa() -> None:
    Configuration.configure(settings.YOOKASSA_SHOP_ID, settings.YOOKASSA_SECRET_KEY)


class PaymentService:
    def __init__(self, db):
        self.beat_repo = BeatRepo(db)
        self.purchase_repo = PurchaseRepo(db)
        self.payment_repo = PaymentRepo(db)

    async def create_checkout(self, beat_id: uuid.UUID, buyer_id: uuid.UUID) -> CheckoutResponse:
        beat = await self.beat_repo.get_by_id(beat_id)
        if not beat:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Бит не найден")
        if beat.author_id == buyer_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Нельзя купить собственный бит")
        if await self.purchase_repo.get_by_beat_and_buyer(beat_id, buyer_id):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Вы уже купили этот бит")

        _configure_yookassa()
        idempotency_key = str(uuid.uuid4())

        yoo_payment = await asyncio.to_thread(
            YooPayment.create,
            {
                "amount": {"value": str(beat.price), "currency": "RUB"},
                "confirmation": {
                    "type": "redirect",
                    "return_url": settings.YOOKASSA_RETURN_URL,
                },
                "capture": True,
                "description": f"Покупка бита: {beat.title}",
                "metadata": {
                    "beat_id": str(beat.id),
                    "buyer_id": str(buyer_id),
                },
            },
            idempotency_key,
        )

        await self.payment_repo.create(
            payment_id=yoo_payment.id,
            beat_id=beat_id,
            buyer_id=buyer_id,
            amount=Decimal(yoo_payment.amount.value),
        )

        return CheckoutResponse(
            payment_id=yoo_payment.id,
            confirmation_url=yoo_payment.confirmation.confirmation_url,
        )

    async def handle_webhook(self, body: dict, client_ip: str) -> None:
        if not settings.DEBUG and not SecurityHelper().is_ip_trusted(client_ip):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Untrusted IP")

        notification = WebhookNotificationFactory().create(body)
        if notification.event != WebhookNotificationEventType.PAYMENT_SUCCEEDED:
            return

        yoo_payment = notification.object
        payment = await self.payment_repo.get_by_id(yoo_payment.id)
        if not payment or payment.status != "pending":
            return

        meta = yoo_payment.metadata or {}
        beat_id = uuid.UUID(meta.get("beat_id", str(payment.beat_id)))
        buyer_id = uuid.UUID(meta.get("buyer_id", str(payment.buyer_id)))

        if not await self.purchase_repo.get_by_beat_and_buyer(beat_id, buyer_id):
            await self.purchase_repo.create(beat_id, buyer_id)

        await self.payment_repo.update_status(yoo_payment.id, "succeeded")
