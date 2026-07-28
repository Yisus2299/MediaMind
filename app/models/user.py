from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, Float, Table, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
from datetime import datetime

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String)
    bio = Column(String)
    avatar_url = Column(String)
    
    # Preferencias del usuario
    preferences = Column(JSON, default={})  # {"music_genres": ["rock", "pop"], "game_genres": ["rpg"]}
    
    # Embedding del usuario (vector de gustos)
    user_embedding = Column(JSON)  # Vector de 50 dimensiones
    
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    is_admin = Column(Boolean, default=False)
    last_active = Column(DateTime(timezone=True), onupdate=func.now())
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relaciones
    interactions = relationship("Interaction", back_populates="user", cascade="all, delete-orphan")
    playlists = relationship("Playlist", back_populates="user", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="user", cascade="all, delete-orphan")