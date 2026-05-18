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


app = FastAPI(description="Wave Auth Service", lifespan=lifespan)

app.include_router(router_v1)


@app.get("/")
async def read_root():
    return {"message": "Hello World"}
