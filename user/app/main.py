from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.endpoints import router as router_v1
from app.core.broker import RabbitBroker
from app.events.handlers import handle_user_created
from config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    broker = RabbitBroker(settings.rabbitmq_url)
    await broker.connect()
    app.state.broker = broker

    queue = await broker.declare_queue("user_created")
    consumer_tag = await queue.consume(handle_user_created)

    print(" [!] RabbitMQ consumers started")

    yield

    await queue.cancel(consumer_tag)
    await broker.close()


_docs = "/docs" if settings.DEBUG else None

app = FastAPI(
    description="Wave User Service",
    lifespan=lifespan,
    root_path="/users",
    docs_url=_docs,
    redoc_url=_docs and "/redoc",
    openapi_url=_docs and "/openapi.json",
)

app.include_router(router_v1)


@app.get("/")
async def read_root():
    return {"message": "User Service Working Here!"}
