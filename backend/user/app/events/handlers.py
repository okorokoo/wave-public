import json
import logging
import uuid

from aio_pika.abc import AbstractIncomingMessage

from app.core.database import async_session
from app.core.s3 import S3Storage
from app.schemas.events import UserCreatedEvent
from app.services.profile import ProfileService

logger = logging.getLogger(__name__)


async def handle_user_created(message: AbstractIncomingMessage):
    async with message.process(requeue=True):
        payload = json.loads(message.body)
        event = UserCreatedEvent(**payload)

        async with async_session() as db:
            profile_service = ProfileService(db=db)
            await profile_service.create_empty_profile(user_id=event.user_id, username=event.username)

        logger.info("Profile created for user %s", event.user_id)


async def handle_user_deleted(message: AbstractIncomingMessage):
    async with message.process(requeue=True):
        payload = json.loads(message.body)
        user_id = uuid.UUID(payload["user_id"])

        async with async_session() as db:
            profile_service = ProfileService(db=db)
            profile = await profile_service._repo.get_by_user_id(user_id)
            if not profile:
                logger.warning("user_deleted: profile not found for %s", user_id)
                return

            if profile.avatar_url:
                try:
                    await S3Storage().delete_objects([profile.avatar_url])
                except Exception as e:
                    logger.warning("user_deleted: failed to delete avatar for %s: %s", user_id, e)

            await db.delete(profile)
            await db.commit()

        logger.info("Profile deleted for user %s", user_id)
