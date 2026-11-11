import json
import logging

import aio_pika
from aio_pika.abc import AbstractChannel, AbstractQueue, AbstractRobustConnection

logger = logging.getLogger(__name__)


class RabbitBroker:
    def __init__(self, url: str):
        self.url = url
        self.connection: AbstractRobustConnection | None = None
        self._channel: AbstractChannel | None = None

    async def connect(self):
        # connect_robust сам переподключается при сбоях сети
        self.connection = await aio_pika.connect_robust(self.url)
        self._channel = await self.connection.channel()
        # Выставляем QoS, чтобы не перегружать воркер
        await self._channel.set_qos(prefetch_count=10)

    @property
    def channel(self) -> AbstractChannel:
        if self._channel is None:
            raise RuntimeError("RabbitBroker is not connected: call connect() first")
        return self._channel

    async def close(self):
        if self.connection:
            await self.connection.close()

    async def declare_queue(self, name: str) -> AbstractQueue:
        return await self.channel.declare_queue(name, durable=True)

    async def publish(self, queue_name: str, body: dict):
        connection = await aio_pika.connect_robust(self.url)

        async with connection:
            channel = await connection.channel()

            # 2. Объявляем очередь (durable=True, чтобы сообщения не пропадали при перезапуске RabbitMQ)
            await channel.declare_queue(queue_name, durable=True)

            # 3. Сериализуем наш словарь в байты JSON
            message_bytes = json.dumps(body).encode("utf-8")

            # 4. Публикуем сообщение в очередь
            await channel.default_exchange.publish(
                aio_pika.Message(
                    body=message_bytes,
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT,  # Гарантирует сохранение на диск
                ),
                routing_key=queue_name,
            )
            logger.debug("Published task to RabbitMQ queue '%s': %s", queue_name, body)
