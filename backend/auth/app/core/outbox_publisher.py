import asyncio
import contextlib
import logging
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.database import async_session
from app.core.rabbitmq import rabbit_client
from app.models.models import OutboxEvent

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 2
MAX_BATCH = 10


async def process_outbox_batch() -> int:
    async with async_session() as session:
        query = (
            select(OutboxEvent)
            .where(OutboxEvent.published_at.is_(None))
            .order_by(OutboxEvent.created_at)
            .limit(MAX_BATCH)
        )
        result = await session.execute(query)
        events = result.scalars().all()

        for event in events:
            try:
                await rabbit_client.publish(
                    routing_key=event.routing_key,
                    body=event.payload,
                )
                event.published_at = datetime.now(UTC)
            except Exception as exc:
                event.attempts += 1
                event.last_error = str(exc)[:500]

        await session.commit()
        return sum(1 for event in events if event.published_at is not None)


async def outbox_publisher_loop(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            await process_outbox_batch()
        except Exception as exc:
            logger.error("Outbox publisher error: %s", exc)

        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop_event.wait(), timeout=POLL_INTERVAL_SECONDS)
