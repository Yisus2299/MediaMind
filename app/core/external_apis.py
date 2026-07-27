import httpx
import asyncio
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from app.core.config import settings
from app.models.content import ContentType, ContentPlatform

class ExternalAPIClient:
    """
    Cliente para APIs externas con manejo de rate limiting y caché.
    """
    
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)
        self.spotify_token = None
        self.spotify_token_expires = None
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    # ============ SPOTIFY API (Música) ============
    
    async def _get_spotify_token(self) -> str:
        """Obtener token de Spotify (con refresh automático)"""
        if self.spotify_token and datetime.now() < self.spotify_token_expires:
            return self.spotify_token
        
        response = await self.client.post(
            "https://accounts.spotify.com/api/token",
            data={
                "grant_type": "client_credentials",
                "client_id": settings.SPOTIFY_CLIENT_ID,
                "client_secret": settings.SPOTIFY_CLIENT_SECRET,
            }
        )
        response.raise_for_status()
        data = response.json()
        
        self.spotify_token = data["access_token"]
        self.spotify_token_expires = datetime.now() + timedelta(seconds=data["expires_in"] - 60)
        
        return self.spotify_token
    
    async def search_spotify(self, query: str, limit: int = 10) -> List[Dict]:
        """Buscar música en Spotify"""
        token = await self._get_spotify_token()
        response = await self.client.get(
            "https://api.spotify.com/v1/search",
            params={"q": query, "type": "track", "limit": limit},
            headers={"Authorization": f"Bearer {token}"}
        )
        response.raise_for_status()
        data = response.json()
        
        tracks = []
        for track in data.get("tracks", {}).get("items", []):
            tracks.append({
                "external_id": track["id"],
                "platform": ContentPlatform.SPOTIFY,
                "content_type": ContentType.MUSIC,
                "title": track["name"],
                "description": f"Artista: {', '.join([a['name'] for a in track['artists']])}",
                "cover_image": track["album"]["images"][0]["url"] if track["album"]["images"] else None,
                "release_date": track["album"]["release_date"],
                "popularity_score": track["popularity"] / 100,
                "extra_metadata": {
                    "artist": track["artists"][0]["name"],
                    "album": track["album"]["name"],
                    "duration": track["duration_ms"] / 1000,
                    "genres": [],  # Spotify no da géneros directamente
                }
            })
        
        return tracks
    
    async def get_spotify_track(self, track_id: str) -> Dict:
        """Obtener detalles de una canción específica"""
        token = await self._get_spotify_token()
        response = await self.client.get(
            f"https://api.spotify.com/v1/tracks/{track_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        response.raise_for_status()
        track = response.json()
        
        return {
            "external_id": track["id"],
            "title": track["name"],
            "artist": track["artists"][0]["name"],
            "album": track["album"]["name"],
            "duration": track["duration_ms"] / 1000,
            "popularity": track["popularity"],
            "cover_image": track["album"]["images"][0]["url"] if track["album"]["images"] else None,
        }
    
    # ============ STEAM API (Videojuegos) ============
    
    async def search_steam(self, query: str, limit: int = 10) -> List[Dict]:
        """Buscar juegos en Steam"""
        # Primero buscar en el store
        response = await self.client.get(
            "https://api.steampowered.com/ISteamApps/GetAppList/v2/"
        )
        response.raise_for_status()
        data = response.json()
        
        # Filtrar juegos que coinciden con la búsqueda
        apps = data.get("applist", {}).get("apps", [])
        matches = [app for app in apps if query.lower() in app["name"].lower()][:limit]
        
        games = []
        for match in matches:
            # Obtener detalles del juego
            details = await self.get_steam_game_details(match["appid"])
            if details:
                games.append({
                    "external_id": str(match["appid"]),
                    "platform": ContentPlatform.STEAM,
                    "content_type": ContentType.GAME,
                    "title": match["name"],
                    "description": details.get("short_description", ""),
                    "cover_image": details.get("header_image"),
                    "release_date": details.get("release_date", {}).get("date"),
                    "popularity_score": min(1.0, details.get("metacritic", {}).get("score", 50) / 100),
                    "extra_metadata": {
                        "developer": details.get("developers", [""])[0],
                        "publisher": details.get("publishers", [""])[0],
                        "platforms": [p for p, v in details.get("platforms", {}).items() if v],
                        "genres": [g["description"] for g in details.get("genres", [])],
                        "metacritic_score": details.get("metacritic", {}).get("score"),
                    }
                })
        
        return games
    
    async def get_steam_game_details(self, app_id: int) -> Dict:
        """Obtener detalles de un juego en Steam"""
        response = await self.client.get(
            "https://store.steampowered.com/api/appdetails",
            params={"appids": app_id}
        )
        response.raise_for_status()
        data = response.json()
        
        if str(app_id) in data and data[str(app_id)].get("success"):
            return data[str(app_id)]["data"]
        return {}
    
    # ============ TMDB API (Películas) ============
    
    async def search_tmdb(self, query: str, limit: int = 10) -> List[Dict]:
        """Buscar películas en TMDB"""
        response = await self.client.get(
            "https://api.themoviedb.org/3/search/movie",
            params={
                "api_key": settings.TMDB_API_KEY,
                "query": query,
                "limit": limit
            }
        )
        response.raise_for_status()
        data = response.json()
        
        movies = []
        for movie in data.get("results", [])[:limit]:
            movies.append({
                "external_id": str(movie["id"]),
                "platform": ContentPlatform.TMDB,
                "content_type": ContentType.MOVIE,
                "title": movie["title"],
                "description": movie["overview"],
                "cover_image": f"https://image.tmdb.org/t/p/w500{movie['poster_path']}" if movie.get("poster_path") else None,
                "release_date": movie["release_date"],
                "popularity_score": min(1.0, movie.get("popularity", 0) / 100),
                "average_rating": movie.get("vote_average", 0),
                "extra_metadata": {
                    "director": [],  # Necesitamos otra llamada para créditos
                    "cast": [],
                    "duration": None,
                    "genres": [g["name"] for g in movie.get("genres", [])],
                    "original_language": movie.get("original_language"),
                }
            })
        
        return movies
    
    async def get_tmdb_movie_details(self, movie_id: int) -> Dict:
        """Obtener detalles de una película en TMDB"""
        # Obtener detalles básicos
        response = await self.client.get(
            f"https://api.themoviedb.org/3/movie/{movie_id}",
            params={"api_key": settings.TMDB_API_KEY}
        )
        response.raise_for_status()
        movie = response.json()
        
        # Obtener créditos
        credits_response = await self.client.get(
            f"https://api.themoviedb.org/3/movie/{movie_id}/credits",
            params={"api_key": settings.TMDB_API_KEY}
        )
        credits_response.raise_for_status()
        credits = credits_response.json()
        
        return {
            "title": movie["title"],
            "overview": movie["overview"],
            "release_date": movie["release_date"],
            "runtime": movie["runtime"],
            "director": [c["name"] for c in credits.get("crew", []) if c["job"] == "Director"],
            "cast": [c["name"] for c in credits.get("cast", [])[:10]],
            "genres": [g["name"] for g in movie.get("genres", [])],
            "vote_average": movie["vote_average"],
            "popularity": movie["popularity"],
            "poster_path": movie["poster_path"],
        }
    
    # ============ GOODREADS API (Libros) ============
    
    async def search_goodreads(self, query: str, limit: int = 10) -> List[Dict]:
        """Buscar libros en Goodreads (usando Google Books como alternativa)"""
        # Usamos Google Books API (más accesible)
        response = await self.client.get(
            "https://www.googleapis.com/books/v1/volumes",
            params={"q": query, "maxResults": limit}
        )
        response.raise_for_status()
        data = response.json()
        
        books = []
        for book in data.get("items", []):
            volume = book.get("volumeInfo", {})
            books.append({
                "external_id": book["id"],
                "platform": ContentPlatform.GOODREADS,
                "content_type": ContentType.BOOK,
                "title": volume.get("title", ""),
                "description": volume.get("description", ""),
                "cover_image": volume.get("imageLinks", {}).get("thumbnail"),
                "release_date": volume.get("publishedDate"),
                "popularity_score": 0.5,  # Google no da popularidad
                "extra_metadata": {
                    "author": ", ".join(volume.get("authors", [])),
                    "publisher": volume.get("publisher"),
                    "pages": volume.get("pageCount"),
                    "categories": volume.get("categories", []),
                }
            })
        
        return books
    
    # ============ BÚSQUEDA MULTIMEDIA UNIFICADA ============
    
    async def search_all(
        self,
        query: str,
        content_types: List[ContentType] = None,
        limit_per_type: int = 5
    ) -> Dict[ContentType, List[Dict]]:
        """
        Buscar en todas las APIs externas en paralelo.
        """
        results = {}
        
        # Definir qué buscar
        search_tasks = []
        
        if not content_types or ContentType.MUSIC in content_types:
            search_tasks.append(self.search_spotify(query, limit_per_type))
        else:
            search_tasks.append(asyncio.sleep(0, result=[]))
        
        if not content_types or ContentType.GAME in content_types:
            search_tasks.append(self.search_steam(query, limit_per_type))
        else:
            search_tasks.append(asyncio.sleep(0, result=[]))
        
        if not content_types or ContentType.MOVIE in content_types:
            search_tasks.append(self.search_tmdb(query, limit_per_type))
        else:
            search_tasks.append(asyncio.sleep(0, result=[]))
        
        if not content_types or ContentType.BOOK in content_types:
            search_tasks.append(self.search_goodreads(query, limit_per_type))
        else:
            search_tasks.append(asyncio.sleep(0, result=[]))
        
        # Ejecutar en paralelo
        spotify_results, steam_results, tmdb_results, goodreads_results = await asyncio.gather(
            *search_tasks, return_exceptions=True
        )
        
        # Organizar resultados
        if isinstance(spotify_results, list):
            results[ContentType.MUSIC] = spotify_results
        if isinstance(steam_results, list):
            results[ContentType.GAME] = steam_results
        if isinstance(tmdb_results, list):
            results[ContentType.MOVIE] = tmdb_results
        if isinstance(goodreads_results, list):
            results[ContentType.BOOK] = goodreads_results
        
        return results

# Singleton
external_api = ExternalAPIClient()