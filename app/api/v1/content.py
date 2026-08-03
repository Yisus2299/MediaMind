from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from app.core.database import get_db
from app.core.external_apis import ExternalAPIClient
from app.models.content import Content, ContentType
from app.models.content import Content as ContentModel
from app.services.content_service import import_external_items

router = APIRouter()


@router.get("/content")
async def get_content(
    content_type: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(ContentModel).order_by(ContentModel.created_at.desc()).limit(limit)
    if content_type:
        try:
            content_enum = ContentType(content_type.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail="content_type inválido")
        stmt = stmt.where(ContentModel.content_type == content_enum)

    result = await db.execute(stmt)
    items = result.scalars().all()
    return {
        "content_type": content_type,
        "limit": limit,
        "items": [
            {
                "id": item.id,
                "title": item.title,
                "description": item.description,
                "content_type": item.content_type.value,
                "platform": item.platform.value if item.platform else None,
                "popularity_score": item.popularity_score,
                "average_rating": item.average_rating,
            }
            for item in items
        ],
    }


@router.post("/content/import-external")
async def import_external_content(
    query: str = Query(..., min_length=1),
    content_type: Optional[str] = Query(None),
    limit: int = Query(5, ge=1, le=10),
    db: AsyncSession = Depends(get_db),
):
    if content_type:
        try:
            content_enum = ContentType(content_type.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail="content_type inválido")
    else:
        content_enum = None

    async with ExternalAPIClient() as client:
        try:
            if content_enum == ContentType.MUSIC:
                results = await client.search_spotify(query, limit)
            elif content_enum == ContentType.GAME:
                results = await client.search_steam(query, limit)
            elif content_enum == ContentType.MOVIE:
                results = await client.search_tmdb(query, limit)
            elif content_enum == ContentType.SERIES:
                results = await client.search_tmdb_tv(query, limit)
            else:
                results = await client.search_steam(query, limit)
            error_message = None
        except Exception as exc:
            results = []
            error_message = str(exc)

    imported = await import_external_items(db, results)
    await db.commit()

    return {
        "query": query,
        "content_type": content_type,
        "imported": [
            {"id": content.id, "title": content.title, "status": status}
            for content, status in imported
        ],
        "message": "Importación completada" if not error_message else f"Importación parcial: {error_message}",
    }
