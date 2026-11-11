import json
import logging
import uuid

from aio_pika.abc import AbstractIncomingMessage
from sqlalchemy import select, update

from app.core.database import async_session
from app.core.s3 import S3Storage
from app.models.models import Beat, Purchase, UserVoiceTag

logger = logging.getLogger(__name__)

_S3_PLACEHOLDER = {"processing", "deleted", ""}


def _real_s3_keys(*urls: str | None) -> list[str]:
    return [u for u in urls if u and u not in _S3_PLACEHOLDER]


async def handle_username_changed(message: AbstractIncomingMessage):
    async with message.process(requeue=True):
        payload = json.loads(message.body)
        author_id = uuid.UUID(payload["user_id"])
        new_username = payload["new_username"]

        async with async_session() as db:
            await db.execute(update(Beat).where(Beat.author_id == author_id).values(author_name=new_username))
            await db.commit()

        logger.info("author_name updated to '%s' for user %s", new_username, author_id)


async def handle_user_deleted(message: AbstractIncomingMessage):
    async with message.process(requeue=True):
        payload = json.loads(message.body)
        author_id = uuid.UUID(payload["user_id"])

        async with async_session() as db:
            s3 = S3Storage()

            # All beats by this author (including soft-deleted)
            result = await db.execute(select(Beat).where(Beat.author_id == author_id))
            beats = result.scalars().all()

            keys_to_delete: list[str] = []

            for beat in beats:
                has_purchase = (
                    await db.execute(select(Purchase).where(Purchase.beat_id == beat.id).limit(1))
                ).scalar_one_or_none() is not None

                if has_purchase:
                    beat.author_name = None
                    db.add(beat)
                else:
                    keys_to_delete.extend(
                        _real_s3_keys(
                            beat.audio_preview_url,
                            beat.audio_full_url,
                            beat.cover_url,
                        )
                    )
                    await db.delete(beat)

            # Voice tag
            vt_result = await db.execute(select(UserVoiceTag).where(UserVoiceTag.user_id == author_id))
            vt = vt_result.scalar_one_or_none()
            if vt:
                keys_to_delete.append(vt.s3_key)
                await db.delete(vt)

            await db.commit()

            if keys_to_delete:
                try:
                    await s3.delete_objects(keys_to_delete)
                except Exception as e:
                    logger.warning("user_deleted: S3 cleanup failed for %s: %s", author_id, e)

        logger.info("Beats cleaned up for deleted user %s", author_id)
