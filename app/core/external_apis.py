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
        """Buscar juegos en Steam usando la API de detalles del store."""
        response = await self.client.get(
            "https://store.steampowered.com/search/",
            params={"term": query, "category1": "998", "supportedlang": "english"},
            headers={"User-Agent": "Mozilla/5.0"},
        )
        response.raise_for_status()

        html = response.text
        search_results = self._extract_steam_search_results(html, limit)
        games = []

        for item in search_results:
            app_id = item["id"]
            details = await self.get_steam_game_details(int(app_id))
            title = item.get("title") or details.get("name") or ""
            if not title or title.startswith("Steam App"):
                title = await self._get_steam_title_from_store(int(app_id)) or title
            if not title or title.startswith("Steam App"):
                title = f"Steam App {app_id}"
            description = details.get("short_description") or item.get("description") or ""
            cover_image = details.get("header_image") or item.get("cover_image")

            games.append({
                "external_id": app_id,
                "platform": ContentPlatform.STEAM,
                "content_type": ContentType.GAME,
                "title": title,
                "description": description,
                "cover_image": cover_image,
                "release_date": None,
                "popularity_score": 0.5,
                "extra_metadata": {
                    "genres": [],
                    "source": "steam_store_search",
                },
            })

        return games

    def _extract_steam_search_results(self, html: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Extrae resultados de búsqueda de Steam con id, título y descripción desde el HTML."""
        import re

        results: List[Dict[str, Any]] = []
        seen = set()

        for match in re.finditer(
            r'data-ds-appid="(?P<app_id>\d+)"',
            html,
        ):
            app_id = match.group("app_id")
            if app_id in seen:
                continue
            seen.add(app_id)

            start = max(0, match.start() - 200)
            end = min(len(html), match.end() + 1200)
            block = html[start:end]
            title = self._extract_steam_title(block, app_id)
            description = self._extract_steam_description(block)

            results.append({"id": app_id, "title": title, "description": description, "cover_image": None})
            if len(results) >= limit:
                return results

        if results:
            return results

        for pattern in [r'app/(\d+)/']:
            for app_id in re.findall(pattern, html):
                if app_id not in seen:
                    seen.add(app_id)
                    results.append({"id": app_id, "title": f"Steam App {app_id}", "description": "", "cover_image": None})
                    if len(results) >= limit:
                        return results

        return results

    def _extract_steam_title(self, block: str, app_id: str) -> str:
        """Extrae el título del bloque HTML de Steam."""
        import re

        title_patterns = [
            r'<span[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</span>',
            r'<div[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</div>',
            r'<h4[^>]*>(.*?)</h4>',
            r'<h3[^>]*>(.*?)</h3>',
            r'<a[^>]*>(.*?)</a>',
        ]

        for pattern in title_patterns:
            title_match = re.search(pattern, block, re.S | re.I)
            if title_match:
                title = re.sub(r'<[^>]+>', '', title_match.group(1))
                title = re.sub(r'\s+', ' ', title).strip()
                if title:
                    return title

        return f"Steam App {app_id}"

    def _extract_steam_description(self, block: str) -> str:
        """Extrae una descripción breve del bloque HTML de Steam."""
        import re

        description_patterns = [
            r'<div[^>]*class="[^"]*search_review_summary[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*class="[^"]*search_review_summary[^"]*"[^>]*>(.*?)</span>',
            r'<div[^>]*class="[^"]*search_price[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*class="[^"]*search_desc[^"]*"[^>]*>(.*?)</div>',
        ]

        for pattern in description_patterns:
            description_match = re.search(pattern, block, re.S | re.I)
            if description_match:
                description = re.sub(r'<[^>]+>', '', description_match.group(1))
                description = re.sub(r'\s+', ' ', description).strip()
                if description:
                    return description

        return ""
    
    async def get_steam_game_details(self, app_id: int) -> Dict:
        """Obtener detalles de un juego en Steam"""
        response = await self.client.get(
            "https://store.steampowered.com/api/appdetails",
            params={"appids": app_id, "l": "english"},
            headers={"User-Agent": "Mozilla/5.0"},
        )
        response.raise_for_status()
        data = response.json()

        if str(app_id) in data and data[str(app_id)].get("success"):
            return data[str(app_id)]["data"]
        return {}

    async def _get_steam_title_from_store(self, app_id: int) -> str:
        import re

        response = await self.client.get(
            f"https://store.steampowered.com/app/{app_id}/",
            headers={"User-Agent": "Mozilla/5.0"},
            follow_redirects=True,
        )
        response.raise_for_status()
        html = response.text
        for pattern in [
            r'<meta property="og:title" content="([^"]+)"',
            r'<title>([^<]+?)\s+on Steam',
        ]:
            match = re.search(pattern, html, re.I)
            if match:
                title = match.group(1).strip()
                if title and not title.startswith("Steam App"):
                    return title
        return ""
    
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

    async def search_tmdb_tv(self, query: str, limit: int = 10) -> List[Dict]:
        """Buscar series en TMDB"""
        response = await self.client.get(
            "https://api.themoviedb.org/3/search/tv",
            params={"api_key": settings.TMDB_API_KEY, "query": query},
        )
        response.raise_for_status()
        data = response.json()

        series = []
        for show in data.get("results", [])[:limit]:
            series.append({
                "external_id": str(show["id"]),
                "platform": ContentPlatform.TMDB,
                "content_type": ContentType.SERIES,
                "title": show["name"],
                "description": show.get("overview", ""),
                "cover_image": f"https://image.tmdb.org/t/p/w500{show['poster_path']}" if show.get("poster_path") else None,
                "release_date": show.get("first_air_date"),
                "popularity_score": min(1.0, show.get("popularity", 0) / 100),
                "average_rating": show.get("vote_average", 0),
                "extra_metadata": {"genres": []},
            })
        return series
    
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

        if not content_types or ContentType.SERIES in content_types:
            search_tasks.append(self.search_tmdb_tv(query, limit_per_type))
        else:
            search_tasks.append(asyncio.sleep(0, result=[]))
        
        if not content_types or ContentType.BOOK in content_types:
            search_tasks.append(self.search_goodreads(query, limit_per_type))
        else:
            search_tasks.append(asyncio.sleep(0, result=[]))
        
        # Ejecutar en paralelo
        spotify_results, steam_results, tmdb_results, tmdb_tv_results, goodreads_results = await asyncio.gather(
            *search_tasks, return_exceptions=True
        )
        
        # Organizar resultados
        if isinstance(spotify_results, list):
            results[ContentType.MUSIC] = spotify_results
        if isinstance(steam_results, list):
            results[ContentType.GAME] = steam_results
        if isinstance(tmdb_results, list):
            results[ContentType.MOVIE] = tmdb_results
        if isinstance(tmdb_tv_results, list):
            results[ContentType.SERIES] = tmdb_tv_results
        if isinstance(goodreads_results, list):
            results[ContentType.BOOK] = goodreads_results
        
        return results

# Singleton
external_api = ExternalAPIClient()