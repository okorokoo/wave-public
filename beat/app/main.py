from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.endpoints import router as router_v1
from app.core.s3 import S3Storage
from config import settings

s3_storage = S3Storage()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await s3_storage.create_bucket_if_not_exists()
    yield


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


@app.get("/")
async def read_root():
    return {"message": "Beat Service Working Here!"}
