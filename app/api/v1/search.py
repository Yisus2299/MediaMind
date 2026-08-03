from fastapi import APIRouter, Query, HTTPException
from typing import Optional

from app.core.external_apis import ExternalAPIClient
from app.models.content import ContentType

router = APIRouter()


async def _search_by_type(client: ExternalAPIClient, query: str, content_type: ContentType, limit: int):
    if content_type == ContentType.MUSIC:
        return await client.search_spotify(query, limit)
    if content_type == ContentType.GAME:
        return await client.search_steam(query, limit)
    if content_type == ContentType.MOVIE:
        return await client.search_tmdb(query, limit)
    if content_type == ContentType.SERIES:
        return await client.search_tmdb_tv(query, limit)
    if content_type == ContentType.BOOK:
        return await client.search_goodreads(query, limit)
    raise HTTPException(status_code=400, detail="content_type inválido")


@router.get("/search")
async def search(
    q: str = Query(..., description="Término de búsqueda"),
    content_type: Optional[ContentType] = Query(None, description="Filtrar por tipo"),
    limit: int = Query(10, ge=1, le=20),
):
    """Buscar contenido en APIs externas."""
    async with ExternalAPIClient() as client:
        try:
            if content_type:
                results = await _search_by_type(client, q, content_type, limit)
                return {"query": q, "content_type": content_type.value, "results": results}

            all_results = await client.search_all(q, limit_per_type=min(limit, 5))
            flat = []
            for items in all_results.values():
                flat.extend(items)
            return {"query": q, "content_type": None, "results": flat[:limit]}
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Error en búsqueda externa: {exc}")
