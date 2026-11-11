import aio_pika
from aio_pika.abc import AbstractChannel, AbstractQueue, AbstractRobustConnection


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

    async def publish(self, queue_name: str, body: bytes):
        await self.channel.default_exchange.publish(
            aio_pika.Message(body=body, delivery_mode=aio_pika.DeliveryMode.PERSISTENT), routing_key=queue_name
        )
