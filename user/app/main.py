from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.endpoints import router as router_v1
from app.core.broker import RabbitBroker
from app.events.handlers import handle_user_created
from config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Инициализация брокера
    broker = RabbitBroker(settings.rabbitmq_url)
    await broker.connect()
    app.state.broker = broker

    # 2. Запуск консьюмеров
    queue = await broker.declare_queue("user_created")
    # Стартуем прослушивание (не блокирует поток)
    consumer_tag = await queue.consume(handle_user_created)

    print(" [!] RabbitMQ consumers started")

    yield  # Приложение работает

    # 3. Грациозная остановка
    await queue.cancel(consumer_tag)
    await broker.close()


app = FastAPI(description="Wave User Service", lifespan=lifespan)

app.include_router(router_v1)


@app.get("/")
async def read_root():
    return {"message": "User Service Working Here!"}
