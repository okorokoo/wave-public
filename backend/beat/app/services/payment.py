import asyncio
import logging
import uuid
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from yookassa import Configuration, Payment as YooPayment
from yookassa.domain.common import SecurityHelper
from yookassa.domain.notification import WebhookNotificationEventType, WebhookNotificationFactory

from app.core.repo import BeatRepo, PurchaseRepo, PaymentRepo
from app.core.s3 import S3Storage
from app.schemas.beat import CheckoutResponse, PaymentResultResponse
from config import settings

logger = logging.getLogger(__name__)

CANCELED_STATUSES = {"canceled", "expired"}


def _configure_yookassa() -> None:
    Configuration.configure(settings.YOOKASSA_SHOP_ID, settings.YOOKASSA_SECRET_KEY)


class PaymentService:
    def __init__(self, db):
        self.db = db
        self.beat_repo = BeatRepo(db)
        self.purchase_repo = PurchaseRepo(db)
        self.payment_repo = PaymentRepo(db)
        self.s3 = S3Storage()

    # ── Checkout ──────────────────────────────────────────────────────────────

    async def create_checkout(self, beat_id: uuid.UUID, buyer_id: uuid.UUID) -> CheckoutResponse:
        beat = await self.beat_repo.get_by_id(beat_id)
        if not beat or beat.is_deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Бит не найден")
        if beat.author_id == buyer_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Нельзя купить собственный бит")
        if await self.purchase_repo.get_by_beat_and_buyer(beat_id, buyer_id):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Вы уже купили этот бит")

        # Блокируем двойную оплату: у пользователя уже есть незавершённый платёж за этот бит
        existing_pending = await self.payment_repo.get_pending_by_beat_and_buyer(beat_id, buyer_id)
        if existing_pending:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"У вас уже есть незавершённый платёж. Проверьте статус: payment_id={existing_pending.id}",
            )

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

        logger.info("Checkout created: payment_id=%s beat=%s buyer=%s", yoo_payment.id, beat_id, buyer_id)

        return CheckoutResponse(
            payment_id=yoo_payment.id,
            confirmation_url=yoo_payment.confirmation.confirmation_url,
        )

    # ── Payment result (вызывается фронтом после редиректа) ──────────────────

    async def get_payment_result(self, payment_id: str, buyer_id: uuid.UUID) -> PaymentResultResponse:
        payment = await self.payment_repo.get_by_id(payment_id)
        if not payment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Платёж не найден")
        if payment.buyer_id != buyer_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа к этому платежу")

        # Если вебхук ещё не пришёл — синхронизируем с YooKassa напрямую
        if payment.status == "pending":
            yoo_status = None
            try:
                _configure_yookassa()
                yoo_payment = await asyncio.to_thread(YooPayment.find_one, payment_id)
                yoo_status = yoo_payment.status
            except Exception as exc:
                # YooKassa недоступна — продолжаем с текущим статусом
                logger.warning("YooKassa API unavailable for payment %s: %s", payment_id, exc)

            # Финализация вне try — ошибки DB не глушатся как "YooKassa unavailable"
            if yoo_status == "succeeded":
                await self._finalize_succeeded(payment_id, payment.beat_id, payment.buyer_id, payment.amount)
                payment.status = "succeeded"
            elif yoo_status in CANCELED_STATUSES:
                await self.payment_repo.update_status(payment_id, "canceled")
                payment.status = "canceled"
                logger.info("Payment %s canceled (synced from YooKassa)", payment_id)

        if payment.status == "canceled":
            raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="Платёж отменён")

        if payment.status == "pending":
            return PaymentResultResponse(status="pending")

        # succeeded — выдаём ссылку на скачивание
        beat = await self.beat_repo.get_by_id(payment.beat_id)
        if not beat:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Бит был удалён после оплаты. Обратитесь в поддержку.",
            )

        download_url = await self.s3.generate_presigned_url(
            beat.audio_full_url,
            expires_in=settings.S3_DOWNLOAD_URL_EXPIRE_SECONDS,
        )
        return PaymentResultResponse(status="succeeded", download_url=download_url)

    # ── Webhook ───────────────────────────────────────────────────────────────

    async def handle_webhook(self, body: dict, client_ip: str) -> None:
        if not settings.DEBUG and not SecurityHelper().is_ip_trusted(client_ip):
            logger.warning("Webhook rejected: untrusted IP %s", client_ip)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Untrusted IP")

        notification = WebhookNotificationFactory().create(body)

        if notification.event == WebhookNotificationEventType.PAYMENT_SUCCEEDED:
            await self._on_payment_succeeded(notification.object)
        elif notification.event == WebhookNotificationEventType.PAYMENT_CANCELED:
            await self._on_payment_canceled(notification.object)

    # ── Внутренние обработчики ────────────────────────────────────────────────

    async def _on_payment_succeeded(self, yoo_payment) -> None:
        payment = await self.payment_repo.get_by_id(yoo_payment.id)
        if not payment or payment.status != "pending":
            return

        await self._finalize_succeeded(yoo_payment.id, payment.beat_id, payment.buyer_id, payment.amount)

    async def _on_payment_canceled(self, yoo_payment) -> None:
        payment = await self.payment_repo.get_by_id(yoo_payment.id)
        if not payment or payment.status != "pending":
            return

        await self.payment_repo.update_status(yoo_payment.id, "canceled")
        logger.info("Payment %s canceled (webhook)", yoo_payment.id)

    async def _finalize_succeeded(
        self,
        payment_id: str,
        beat_id: uuid.UUID,
        buyer_id: uuid.UUID,
        amount=None,
    ) -> None:
        """
        Атомарно создаёт Purchase и переводит платёж в succeeded.
        Безопасно при конкурентном вызове: IntegrityError от unique constraint
        означает, что покупка уже создана параллельным запросом — это нормально.
        """
        try:
            await self.purchase_repo.create(beat_id, buyer_id, amount=amount)
        except IntegrityError:
            # Гонка: purchase уже создан (вебхук + get_payment_result одновременно)
            await self.db.rollback()
            logger.warning(
                "Purchase already exists (race condition): beat=%s buyer=%s — skipping",
                beat_id, buyer_id,
            )

        await self.payment_repo.update_status(payment_id, "succeeded")
        logger.info("Payment %s succeeded: beat=%s buyer=%s", payment_id, beat_id, buyer_id)