from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Any

from app.core.database import get_db
from app.core.external_apis import ExternalAPIClient
from app.models.content import Content, ContentType, ContentPlatform, Genre, ContentGenre
from app.models.content import Content as ContentModel

router = APIRouter()


def _normalize_enum_value(value: Any, enum_cls: Any) -> Any:
    if isinstance(value, enum_cls):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        try:
            return enum_cls(normalized)
        except ValueError:
            try:
                return enum_cls[normalized.upper()]
            except KeyError:
                return value
    return value


@router.get("/content")
async def get_content(
    content_type: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db)
):
    """Obtener contenido desde la base de datos."""
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
        "message": "Endpoint funcionando"
    }


@router.post("/content/import-external")
async def import_external_content(
    query: str = Query(..., min_length=1),
    content_type: Optional[str] = Query(None),
    limit: int = Query(5, ge=1, le=10),
    db: AsyncSession = Depends(get_db)
):
    """Importar contenido desde APIs externas de forma sencilla."""
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
            else:
                results = await client.search_steam(query, limit)
        except Exception as exc:
            results = []
            error_message = str(exc)
        else:
            error_message = None

    created_items = []
    for item in results:
        platform = _normalize_enum_value(item.get("platform"), ContentPlatform)
        content_type = _normalize_enum_value(item.get("content_type"), ContentType)
        external_id = item.get("external_id")
        if not platform or not external_id:
            continue

        existing = await db.scalar(
            select(ContentModel).where(
                ContentModel.platform == platform,
                ContentModel.external_id == external_id,
            )
        )
        if existing:
            created_items.append({"id": existing.id, "title": existing.title, "status": "existing"})
            continue

        content = ContentModel(
            external_id=external_id,
            platform=platform,
            content_type=content_type,
            title=item["title"],
            description=item.get("description"),
            cover_image=item.get("cover_image"),
            release_date=item.get("release_date"),
            popularity_score=item.get("popularity_score", 0.0),
            average_rating=item.get("average_rating", 0.0),
            extra_metadata=item.get("extra_metadata", {}),
        )
        db.add(content)
        await db.flush()

        genre_names = []
        metadata = item.get("extra_metadata", {}) or {}
        if isinstance(metadata, dict):
            genre_names = metadata.get("genres") or []

        for genre_name in genre_names:
            genre = await db.scalar(select(Genre).where(Genre.name == genre_name))
            if genre is None:
                genre = Genre(name=genre_name, category=content_type)
                db.add(genre)
                await db.flush()
            db.add(ContentGenre(content_id=content.id, genre_id=genre.id))

        created_items.append({"id": content.id, "title": content.title, "status": "created"})

    await db.commit()
    return {
        "query": query,
        "content_type": content_type,
        "imported": created_items,
        "message": "Importación completada" if not error_message else f"Importación parcial: {error_message}",
    }