import asyncio
import sys
import os
from datetime import datetime, timedelta

from sqlalchemy import select

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import AsyncSessionLocal
from app.models.content import Content, ContentType, Genre, ContentGenre
from app.models.user import User
from passlib.hash import pbkdf2_sha256

async def add_sample_data():
    print("🔄 Agregando datos de prueba...")
    
    async with AsyncSessionLocal() as db:
        # 1. Crear géneros
        genres_data = [
            ("Rock", ContentType.MUSIC),
            ("Pop", ContentType.MUSIC),
            ("RPG", ContentType.GAME),
            ("Acción", ContentType.GAME),
            ("Sci-Fi", ContentType.MOVIE),
            ("Drama", ContentType.MOVIE),
            ("Fantasía", ContentType.BOOK),
            ("Novela", ContentType.BOOK),
        ]
        
        genres = {}
        for name, category in genres_data:
            existing_genre = await db.scalar(select(Genre).where(Genre.name == name))
            if existing_genre is None:
                genre = Genre(name=name, category=category)
                db.add(genre)
                await db.flush()
                genres[name] = genre
            else:
                genres[name] = existing_genre
        
        print("   ✅ Géneros listos")
        
        # 2. Contenido de prueba
        sample_content = [
            # Música
            {"title": "Bohemian Rhapsody", "description": "Clásico de Queen", 
             "content_type": ContentType.MUSIC, "popularity_score": 0.95, 
             "genres": ["Rock"], "metadata": {"artist": "Queen"}},
            {"title": "Shape of You", "description": "Éxito de Ed Sheeran", 
             "content_type": ContentType.MUSIC, "popularity_score": 0.90, 
             "genres": ["Pop"], "metadata": {"artist": "Ed Sheeran"}},
            {"title": "Stairway to Heaven", "description": "Clásico de Led Zeppelin", 
             "content_type": ContentType.MUSIC, "popularity_score": 0.88, 
             "genres": ["Rock"], "metadata": {"artist": "Led Zeppelin"}},
            # Videojuegos
            {"title": "The Witcher 3", "description": "RPG de mundo abierto", 
             "content_type": ContentType.GAME, "popularity_score": 0.95, 
             "genres": ["RPG"], "metadata": {"developer": "CD Projekt"}},
            {"title": "Zelda: Tears of the Kingdom", "description": "Aventura épica", 
             "content_type": ContentType.GAME, "popularity_score": 0.92, 
             "genres": ["Acción"], "metadata": {"developer": "Nintendo"}},
            {"title": "Cyberpunk 2077", "description": "RPG futurista", 
             "content_type": ContentType.GAME, "popularity_score": 0.75, 
             "genres": ["RPG"], "metadata": {"developer": "CD Projekt"}},
            # Películas
            {"title": "Inception", "description": "Sueños dentro de sueños", 
             "content_type": ContentType.MOVIE, "popularity_score": 0.93, 
             "genres": ["Sci-Fi"], "metadata": {"director": "Nolan"}},
            {"title": "The Dark Knight", "description": "Batman vs Joker", 
             "content_type": ContentType.MOVIE, "popularity_score": 0.94, 
             "genres": ["Drama"], "metadata": {"director": "Nolan"}},
            {"title": "Interstellar", "description": "Viaje espacial", 
             "content_type": ContentType.MOVIE, "popularity_score": 0.89, 
             "genres": ["Sci-Fi"], "metadata": {"director": "Nolan"}},
            # Libros
            {"title": "El Señor de los Anillos", "description": "Fantasía épica", 
             "content_type": ContentType.BOOK, "popularity_score": 0.96, 
             "genres": ["Fantasía"], "metadata": {"author": "Tolkien"}},
            {"title": "1984", "description": "Distopía clásica", 
             "content_type": ContentType.BOOK, "popularity_score": 0.92, 
             "genres": ["Ciencia Ficción"], "metadata": {"author": "Orwell"}},
            {"title": "Harry Potter", "description": "Magia y aventura", 
             "content_type": ContentType.BOOK, "popularity_score": 0.94, 
             "genres": ["Fantasía"], "metadata": {"author": "Rowling"}},
        ]
        
        # Crear contenido y asociar géneros
        for item in sample_content:
            content = Content(
                title=item["title"],
                description=item["description"],
                content_type=item["content_type"],
                popularity_score=item["popularity_score"],
                metadata=item["metadata"],
                release_date=datetime.now() - timedelta(days=365)
            )
            db.add(content)
            await db.flush()
            
            for genre_name in item["genres"]:
                if genre_name in genres:
                    db.add(
                        ContentGenre(
                            content_id=content.id,
                            genre_id=genres[genre_name].id,
                        )
                    )
        
        print(f"   ✅ {len(sample_content)} contenidos creados")
        
        # 3. Usuario de prueba
        existing_user = await db.scalar(select(User).where(User.email == "test@test.com"))
        if existing_user is None:
            test_user = User(
                email="test@test.com",
                username="testuser",
                hashed_password=pbkdf2_sha256.hash("123456"),
                full_name="Usuario Test",
                is_active=True,
                is_verified=True
            )
            db.add(test_user)
        
        await db.commit()
        print("✅ DATOS DE PRUEBA AGREGADOS EXITOSAMENTE!")
        print("📧 test@test.com")
        print("🔑 123456")
        print("🌐 http://localhost:8000/docs")

if __name__ == "__main__":
    asyncio.run(add_sample_data())