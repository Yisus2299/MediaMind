from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List, Dict
from app.models.content import ContentType, ContentPlatform

class GenreResponse(BaseModel):
    id: int
    name: str
    category: ContentType
    
    class Config:
        from_attributes = True

class ContentBase(BaseModel):
    title: str
    description: Optional[str] = None
    content_type: ContentType
    platform: Optional[ContentPlatform] = None
    external_id: Optional[str] = None

class ContentCreate(ContentBase):
    extra_metadata: Optional[Dict] = None

class ContentResponse(ContentBase):
    id: int
    cover_image: Optional[str] = None
    release_date: Optional[datetime] = None
    average_rating: float
    popularity_score: float
    genres: List[GenreResponse]
    extra_metadata: Dict
    created_at: datetime
    
    class Config:
        from_attributes = True