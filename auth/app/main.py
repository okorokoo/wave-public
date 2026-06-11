from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.endpoints import router as router_v1
from app.core.rabbitmq import rabbit_client
from config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    await rabbit_client.connect(settings.rabbitmq_url)
    yield
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
