import json

import aio_pika


class RabbitClient:
    def __init__(self):
        self.connection = None
        self.channel = None

    async def connect(self, url: str):
        self.connection = await aio_pika.connect_robust(url)
        self.channel = await self.connection.channel()
        # Сразу объявим очередь, чтобы она создалась при старте
        await self.channel.declare_queue("user_created", durable=True)

    async def publish(self, routing_key: str, body: dict):
        if not self.channel:
            raise RuntimeError("RabbitMQ connection not established")

        await self.channel.default_exchange.publish(
            aio_pika.Message(
                body=json.dumps(body).encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key=routing_key,
        )


rabbit_client = RabbitClient()
