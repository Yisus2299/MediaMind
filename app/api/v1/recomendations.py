from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.models.content import ContentType
from app.schemas.content import ContentResponse
from app.services.recommendation_engine import RecommendationEngine
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User

router = APIRouter()

@router.get("/recommendations", response_model=List[ContentResponse])
async def get_recommendations(
    content_type: Optional[ContentType] = Query(None, description="Content type"),
    limit: int = Query(10, ge=1, le=50),
    offset: int = Query(0, ge=0),
    use_ai: bool = Query(True, description="Use AI or traditional algorithm"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get personalized recommendations for the user.
    
    Strategies:
    1. AI: Uses Machine Learning (vectorization + cosine similarity)
    2. Hybrid: Combines popularity, genres, and novelty
    
    Parameters:
    - content_type: Filter by type (music, game, movie, book)
    - limit: Number of recommendations
    - use_ai: Use AI or traditional method
    """
    engine = RecommendationEngine(db, current_user)
    recommendations = await engine.get_recommendations(
        content_type=content_type,
        limit=limit,
        offset=offset,
        use_ai=use_ai
    )
    
    return recommendations

@router.get("/recommendations/trending", response_model=List[ContentResponse])
async def get_trending(
    content_type: Optional[ContentType] = None,
    limit: int = 10,
    db: AsyncSession = Depends(get_db)
):
    """
    Get trending (popular) content without personalization.
    """
    engine = RecommendationEngine(db)
    recommendations = await engine._get_popular_recommendations(content_type, limit)
    return recommendations

@router.get("/recommendations/explore", response_model=List[ContentResponse])
async def get_exploration(
    content_type: Optional[ContentType] = None,
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Recommendations for exploration, with a surprise factor.
    """
    engine = RecommendationEngine(db, current_user)
    recommendations = await engine._get_exploration_recommendations(content_type, limit)
    return recommendations