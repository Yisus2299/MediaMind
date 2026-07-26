from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.models.user import User
from app.models.content import ContentType
from app.schemas.content import ContentResponse
from app.services.recommendation_engine import RecommendationEngine
from app.core.database import get_db
from app.core.security import get_current_user

router = APIRouter(prefix="/recommendations", tags=["recommendations"])

@router.get("/", response_model=List[ContentResponse])
async def get_recommendations(
    content_type: Optional[ContentType] = Query(None, description="Filtrar por tipo"),
    limit: int = Query(20, ge=1, le=50),
    strategy: str = Query("hybrid", regex="^(ai|hybrid|popular|explore)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Obtener recomendaciones personalizadas.
    
    Estrategias:
    - **ai**: Solo IA (más precisas)
    - **hybrid**: Híbrida (balance)
    - **popular**: Tendencia global
    - **explore**: Exploración (mayor variedad)
    """
    engine = RecommendationEngine(db, current_user)
    recommendations = await engine.get_recommendations(
        content_type=content_type,
        limit=limit,
        strategy=strategy
    )
    return recommendations

@router.get("/trending", response_model=List[ContentResponse])
async def get_trending(
    content_type: Optional[ContentType] = None,
    limit: int = 10,
    db: AsyncSession = Depends(get_db)
):
    """Obtener contenido en tendencia (sin personalización)"""
    engine = RecommendationEngine(db)
    recommendations = await engine._popular_recommendations(content_type, limit)
    return recommendations

@router.get("/explore", response_model=List[ContentResponse])
async def explore(
    content_type: Optional[ContentType] = None,
    limit: int = 15,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Explorar contenido nuevo (factor sorpresa)"""
    engine = RecommendationEngine(db, current_user)
    recommendations = await engine.get_recommendations(
        content_type=content_type,
        limit=limit,
        strategy="explore"
    )
    return recommendations