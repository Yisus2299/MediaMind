from sqlalchemy import Column, Integer, String, Float, DateTime, Enum, ForeignKey, Boolean, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
import enum

class InteractionType(enum.Enum):
    LIKE = "like"
    DISLIKE = "dislike"
    RATING = "rating"
    WATCHED = "watched"
    PLAYED = "played"
    READ = "read"
    LISTENED = "listened"
    SAVED = "saved"
    SHARED = "shared"

class Interaction(Base):
    __tablename__ = "interactions"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content_id = Column(Integer, ForeignKey("contents.id"), nullable=False)
    interaction_type = Column(Enum(InteractionType), nullable=False)
    value = Column(Float)  # Para rating (1-10), tiempo escuchado, etc.
    
    # Contexto de la interacción
    context = Column(JSON, default={})  # {"platform": "web", "device": "mobile"}
    session_id = Column(String)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relaciones
    user = relationship("User", back_populates="interactions")
    content = relationship("Content", back_populates="interactions")