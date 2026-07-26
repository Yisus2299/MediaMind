from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Dict
from app.models.interaction import InteractionType

class InteractionCreate(BaseModel):
    content_id: int
    interaction_type: InteractionType
    value: Optional[float] = None
    context: Optional[Dict] = None

class InteractionResponse(BaseModel):
    id: int
    user_id: int
    content_id: int
    interaction_type: InteractionType
    value: Optional[float]
    context: Dict
    created_at: datetime
    
    class Config:
        from_attributes = True