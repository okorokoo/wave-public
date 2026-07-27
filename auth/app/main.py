import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from sqlalchemy import text

from app.api.v1.endpoints import router as router_v1
from app.core.database import async_session
from app.core.outbox_publisher import outbox_publisher_loop
from app.core.rabbitmq import rabbit_client
from config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    await rabbit_client.connect(settings.rabbitmq_url)
    stop_event = asyncio.Event()
    publisher_task = asyncio.create_task(outbox_publisher_loop(stop_event))
    yield
    stop_event.set()
    await publisher_task
    await rabbit_client.connection.close()


_docs = "/docs" if settings.DEBUG else None

app = FastAPI(
    description="Wave Auth Service",
    lifespan=lifespan,
    root_path="/auth",
    docs_url=_docs,
    redoc_url=_docs and "/redoc",
    openapi_url=_docs and "/openapi.json",
)

app.include_router(router_v1)


@app.get("/")
async def read_root():
    return {"message": "Hello World"}


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
        if rabbit_client.connection and not rabbit_client.connection.is_closed:
            checks["rabbitmq"] = "ok"
        else:
            checks["rabbitmq"] = "error: not connected"
    except Exception as exc:
        checks["rabbitmq"] = f"error: {exc}"

    if not all(value == "ok" for value in checks.values()):
        response.status_code = 503

    return {"status": "ok" if response.status_code == 200 else "degraded", "checks": checks}
