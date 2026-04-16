from fastapi import FastAPI

from app.api.v1.endpoints import router as router_v1

app = FastAPI(description="Wave User Service")

app.include_router(router_v1)


@app.get("/")
async def read_root():
    return {"message": "User Service Working Here!"}

