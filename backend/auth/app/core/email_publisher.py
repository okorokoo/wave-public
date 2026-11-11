import asyncio
import contextlib
import logging
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.database import async_session
from app.core.email import send_email
from app.models.models import EmailOutbox

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 5
MAX_BATCH = 10
MAX_ATTEMPTS = 10


async def process_email_batch() -> None:
    async with async_session() as session:
        query = (
            select(EmailOutbox)
            .where(EmailOutbox.sent_at.is_(None))
            .where(EmailOutbox.attempts < MAX_ATTEMPTS)
            .order_by(EmailOutbox.created_at)
            .limit(MAX_BATCH)
        )
        result = await session.execute(query)
        emails = result.scalars().all()

        for email in emails:
            try:
                await send_email(
                    to_email=email.to_email,
                    subject=email.subject,
                    body_plain=email.body_plain,
                    body_html=email.body_html,
                )
                email.sent_at = datetime.now(UTC)
            except Exception as exc:
                email.attempts += 1
                email.last_error = str(exc)[:500]
                logger.warning("Failed to send email to %s (attempt %d): %s", email.to_email, email.attempts, exc)

        await session.commit()


async def email_publisher_loop(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            await process_email_batch()
        except Exception as exc:
            logger.error("Email publisher error: %s", exc)

        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop_event.wait(), timeout=POLL_INTERVAL_SECONDS)
