from fastapi import APIRouter, Query
from typing import Optional, List
from app.models.content import ContentType

router = APIRouter()

@router.get("/search")
async def search(
    q: str = Query(..., description="Término de búsqueda"),
    content_type: Optional[ContentType] = Query(None, description="Filtrar por tipo")
):
    """Buscar contenido multimedia"""
    # Implementación básica
    return {
        "query": q,
        "content_type": content_type,
        "results": [],
        "message": "Búsqueda funcionando"
    }