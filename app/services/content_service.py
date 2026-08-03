from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import Content, ContentGenre, ContentPlatform, ContentType, Genre


def normalize_enum_value(value: Any, enum_cls: Any) -> Any:
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


async def import_external_item(db: AsyncSession, item: Dict) -> Tuple[Content, str]:
    platform = normalize_enum_value(item.get("platform"), ContentPlatform)
    content_type = normalize_enum_value(item.get("content_type"), ContentType)
    external_id = str(item.get("external_id", ""))
    if not platform or not external_id:
        raise ValueError("platform y external_id son requeridos")

    existing = await db.scalar(
        select(Content).where(
            Content.platform == platform,
            Content.external_id == external_id,
        )
    )
    if existing:
        return existing, "existing"

    content = Content(
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

    metadata = item.get("extra_metadata", {}) or {}
    genre_names = metadata.get("genres") if isinstance(metadata, dict) else []
    for genre_name in genre_names or []:
        genre = await db.scalar(select(Genre).where(Genre.name == genre_name))
        if genre is None:
            genre = Genre(name=genre_name, category=content_type)
            db.add(genre)
            await db.flush()
        db.add(ContentGenre(content_id=content.id, genre_id=genre.id))

    return content, "created"


async def import_external_items(db: AsyncSession, items: List[Dict]) -> List[Tuple[Content, str]]:
    imported = []
    for item in items:
        imported.append(await import_external_item(db, item))
    return imported
