from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import text

from app.api.v1.endpoints import router as router_v1
from app.core.broker import RabbitBroker
from app.core.database import async_session
from app.core.logger import setup_logging
from app.core.s3 import S3Storage
from app.events.handlers import handle_user_deleted
from config import settings

setup_logging(debug=settings.DEBUG)

s3_storage = S3Storage()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await s3_storage.create_bucket_if_not_exists()

    broker = RabbitBroker(settings.rabbitmq_url)
    await broker.connect()
    app.state.broker = broker

    queue = await broker.declare_queue("user_deleted")
    tag = await queue.consume(handle_user_deleted)

    yield

    await queue.cancel(tag)
    await broker.close()


_docs = "/docs" if settings.DEBUG else None

app = FastAPI(
    description="Wave Beat Service",
    lifespan=lifespan,
    root_path="/beats",
    docs_url=_docs,
    redoc_url=_docs and "/redoc",
    openapi_url=_docs and "/openapi.json",
)

app.include_router(router_v1)
Instrumentator().instrument(app).expose(app)


@app.get("/")
async def read_root():
    return {"message": "Beat Service Working Here!"}


@app.get("/health")
async def health(response: Response):
    checks: dict[str, str] = {}

    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {exc}"

    try:
        await s3_storage.check_connection()
        checks["s3"] = "ok"
    except Exception as exc:
        checks["s3"] = f"error: {exc}"

    if not all(value == "ok" for value in checks.values()):
        response.status_code = 503

    return {"status": "ok" if response.status_code == 200 else "degraded", "checks": checks}
