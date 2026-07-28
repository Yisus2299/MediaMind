from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.core.database import get_db
from app.models.content import Content, ContentType

router = APIRouter()

@router.get("/content")
async def get_content(
    content_type: Optional[ContentType] = None,
    limit: int = 20,
    db: AsyncSession = Depends(get_db)
):
    """Obtener contenido"""
    # Implementación básica
    return {
        "content_type": content_type,
        "limit": limit,
        "items": [],
        "message": "Endpoint funcionando"
    }