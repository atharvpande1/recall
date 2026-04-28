from fastapi import FastAPI

from src.resources.router import router as resources_router
# from src.exceptions import AppError, handle_app_error
from src.lifespan import lifespan



app = FastAPI(lifespan=lifespan)

# app.add_exception_handler(AppError, handle_app_error)

BASE_V1_PREFIX = "/api/v1"


app.include_router(router=resources_router, prefix=f"{BASE_V1_PREFIX}/resources")


@app.get("/health")
async def health_check():
    return {"status": "ok"}
