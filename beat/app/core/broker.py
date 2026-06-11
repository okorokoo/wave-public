import json
from typing import Optional

import aio_pika
from aio_pika.abc import AbstractRobustConnection, AbstractRobustChannel, AbstractRobustQueue


class RabbitBroker:
    def __init__(self, url: str):
        self.url = url
        self.connection: Optional[AbstractRobustConnection] = None
        self._channel: Optional[AbstractRobustChannel] = None

    async def connect(self):
        # connect_robust сам переподключается при сбоях сети
        self.connection = await aio_pika.connect_robust(self.url)
        self._channel = await self.connection.channel()
        # Выставляем QoS, чтобы не перегружать воркер
        await self._channel.set_qos(prefetch_count=10)

    async def close(self):
        if self.connection:
            await self.connection.close()

    async def declare_queue(self, name: str) -> AbstractRobustQueue:
        return await self._channel.declare_queue(name, durable=True)

    async def publish(self, queue_name: str, body: dict):
        connection = await aio_pika.connect_robust(self.url)

        async with connection:
            channel = await connection.channel()

            # 2. Объявляем очередь (durable=True, чтобы сообщения не пропадали при перезапуске RabbitMQ)
            queue = await channel.declare_queue(queue_name, durable=True)

            # 3. Сериализуем наш словарь в байты JSON
            message_bytes = json.dumps(body).encode("utf-8")

            # 4. Публикуем сообщение в очередь
            await channel.default_exchange.publish(
                aio_pika.Message(
                    body=message_bytes,
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT  # Гарантирует сохранение на диск
                ),
                routing_key=queue_name
            )
            print(f" [x] Sent task to RabbitMQ: {body}")
