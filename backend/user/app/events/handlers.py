import json
import logging

from aio_pika.abc import AbstractIncomingMessage

from app.core.database import async_session
from app.schemas.events import UserCreatedEvent
from app.services.profile import ProfileService

logger = logging.getLogger(__name__)


async def handle_user_created(message: AbstractIncomingMessage):
    """
    Callback-функция для обработки сообщения.
    """
    async with message.process(requeue=True):  # requeue=True вернет в очередь при ошибке
        payload = json.loads(message.body)
        event = UserCreatedEvent(**payload)

        async with async_session() as db:
            # Вызываем сервисный слой
            profile_service = ProfileService(db=db)
            await profile_service.create_empty_profile(user_id=event.user_id, username=event.username)

        logger.info("Profile created for user %s", event.user_id)
