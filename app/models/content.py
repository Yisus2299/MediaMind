from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, Enum, Table, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
import enum

class ContentType(enum.Enum):
    MUSIC = "music"
    GAME = "game"
    MOVIE = "movie"
    BOOK = "book"

class ContentPlatform(enum.Enum):
    SPOTIFY = "spotify"
    STEAM = "steam"
    TMDB = "tmdb"
    GOODREADS = "goodreads"
    MANUAL = "manual"

class Genre(Base):
    __tablename__ = "genres"
    
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    category = Column(Enum(ContentType))
    description = Column(String)
    
    # Relaciones
    contents = relationship("Content", secondary="content_genres", back_populates="genres")

class Content(Base):
    __tablename__ = "contents"
    
    id = Column(Integer, primary_key=True)
    external_id = Column(String, index=True)  # ID en plataforma externa
    platform = Column(Enum(ContentPlatform))
    content_type = Column(Enum(ContentType), nullable=False)
    
    title = Column(String, nullable=False)
    description = Column(String)
    cover_image = Column(String)
    release_date = Column(DateTime)
    
    # Métricas
    average_rating = Column(Float, default=0)
    popularity_score = Column(Float, default=0)
    total_interactions = Column(Integer, default=0)
    recommendation_score = Column(Float, default=0)
    
    # Embedding del contenido
    content_embedding = Column(JSON)  # Vector de 50 dimensiones
    
    # Metadatos específicos por tipo
    metadata = Column(JSON, default={})
    # Música: {"artist": "...", "album": "...", "duration": 180}
    # Juego: {"developer": "...", "publisher": "...", "platforms": ["PC"]}
    # Película: {"director": "...", "cast": ["..."], "duration": 120}
    # Libro: {"author": "...", "pages": 300, "publisher": "..."}
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    genres = relationship("Genre", secondary="content_genres", back_populates="contents")
    interactions = relationship("Interaction", back_populates="content", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="content", cascade="all, delete-orphan")
    playlists = relationship("Playlist", secondary="playlist_contents", back_populates="contents")

class ContentGenre(Base):
    __tablename__ = "content_genres"
    
    content_id = Column(Integer, ForeignKey("contents.id"), primary_key=True)
    genre_id = Column(Integer, ForeignKey("genres.id"), primary_key=True)