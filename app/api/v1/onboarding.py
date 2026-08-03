from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.services.onboarding_service import OnboardingRequest, OnboardingService

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.get("/status")
async def onboarding_status(current_user: User = Depends(get_current_user)):
    prefs = current_user.preferences or {}
    return {"onboarding_complete": bool(prefs.get("onboarding_complete"))}


@router.post("/complete")
async def complete_onboarding(
    payload: OnboardingRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Guardar 5 juegos, 5 películas y 5 canciones como gustos iniciales."""
    prefs = current_user.preferences or {}
    if prefs.get("onboarding_complete"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Onboarding ya completado")

    service = OnboardingService(db)
    try:
        result = await service.complete_onboarding(current_user, payload.selections)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return {
        "onboarding_complete": result["onboarding_complete"],
        "interactions_created": result["interactions_created"],
        "recommendations": [
            {
                "id": item.id,
                "title": item.title,
                "content_type": item.content_type.value,
                "platform": item.platform.value if item.platform else None,
                "cover_image": item.cover_image,
                "popularity_score": item.popularity_score,
            }
            for item in result["recommendations"]
        ],
    }
