from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, Enum, Table, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.core.database import Base

class ContentType(enum.Enum):
    MUSIC = "music"
    GAME = "game"
    MOVIE = "movie"
    BOOK = "book"
    
class Genre(Base):
    __tablename__ = "genres"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    category = Column(String, index=True)
    
    #Relationships
    
    contents = relationship("Content", secondary="content_genres", back_populates="genres")

class Content(Base):
    __tablename__ = "contents"
    
    id = Column(Integer, primary_key=True, index=True)
    external_id = Column(String, index=True) # API ID from external source
    title = Column(String, nullable=False)
    description = Column(String)
    content_type = Column(Enum(ContentType), nullable=False)
    release_date = Column(DateTime)
    average_rating = Column(Float, default=0)
    popularity_score = Column(Float, default=0)
    metadata_json = Column(JSON) # Store additional metadata as JSON
    
    # Fields specific to content types
    # Music: artist, album, duration
    # Game: platform, developer, publisher
    # Movie: director, cast, duration
    # Book: author, pages, publisher
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    #Relationships
    
    genres = relationship("Genre", secondary="content_genres", back_populates="contents")

class ContentGenre(Base):
    __tablename__ = "content_genres"
    
    content_id = Column(Integer, ForeignKey("contents.id"), primary_key=True)
    genre_id = Column(Integer, ForeignKey("genres.id"), primary_key=True)
