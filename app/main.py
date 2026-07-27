from fastapi import FastAPI

from app.api.v1.recomendations import router as recommendation_router

app = FastAPI(
    title="MediaMind API",
    version="0.1.0",
    description="MediaMind recommendation service",
)

app.include_router(recommendation_router, prefix="/api/v1", tags=["recommendations"])
