from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Table
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

# Junction table for playlist contents
playlist_contents = Table(
    'playlist_contents',
    Base.metadata,
    Column('playlist_id', Integer, ForeignKey('playlists.id'), primary_key=True),
    Column('content_id', Integer, ForeignKey('contents.id'), primary_key=True),
    Column('position', Integer),
    Column('added_at', DateTime(timezone=True), server_default=func.now())
)

class Playlist(Base):
    __tablename__ = "playlists"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    name = Column(String, nullable=False)
    description = Column(String)
    is_public = Column(Boolean, default=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="playlists")
    contents = relationship("Content", secondary=playlist_contents, back_populates="playlists")