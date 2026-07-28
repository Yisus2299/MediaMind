from app.models.user import User
from app.models.content import Content, Genre, ContentType
from app.models.interaction import Interaction, InteractionType
from app.models.review import Review
from app.models.playlist import Playlist

# Exportar todo para Alembic o create_all
__all__ = [
    "User", 
    "Content", 
    "Genre", 
    "ContentType",
    "Interaction", 
    "InteractionType",
    "Review",
    "Playlist"
]