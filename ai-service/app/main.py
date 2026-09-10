"""Application entry point placeholder."""
from fastapi import FastAPI

from app.config import settings
from app.routes.chat_routes import router as chat_router

app = FastAPI(title=settings.app_name)

app.include_router(chat_router)


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": settings.app_name,
    }