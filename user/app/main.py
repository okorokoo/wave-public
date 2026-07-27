from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from sqlalchemy import text

from app.api.v1.endpoints import router as router_v1
from app.core.broker import RabbitBroker
from app.core.database import async_session
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


@app.get("/health")
async def health(request: Request, response: Response):
    checks: dict[str, str] = {}

    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {exc}"

    try:
        broker: RabbitBroker = request.app.state.broker
        if broker.connection and not broker.connection.is_closed:
            checks["rabbitmq"] = "ok"
        else:
            checks["rabbitmq"] = "error: not connected"
    except Exception as exc:
        checks["rabbitmq"] = f"error: {exc}"

    if not all(value == "ok" for value in checks.values()):
        response.status_code = 503

    return {"status": "ok" if response.status_code == 200 else "degraded", "checks": checks}
