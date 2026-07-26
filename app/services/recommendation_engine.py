from typing import List, Dict, Tuple, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc, func
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import redis
import json

from app.models.user import User
from app.models.content import Content, ContentType, Genre
from app.models.interaction import Interaction, InteractionType
from app.core.cache import cache
from app.core.config import settings

class RecommendationEngine:
    """
    Engine of recommendation that combines multiple strategies:
    1. Content-based filtering (genres, metadata)
    2. Collaborative filtering (similar users)
    3. Popularity and trending
    4. Novelty factor for exploration
    """
    
    def __init__(self, db: AsyncSession, user: User = None):
        self.db = db
        self.user = user
    
    async def get_recommendations(
        self,
        content_type: Optional[ContentType] = None,
        limit: int = 10,
        offset: int = 0,
        use_ai: bool = True
    ) -> List[Content]:
        """
        Get personalized recommendations based on user preferences and content attributes.
        """
        if not self.user:
            # if there is no user, return popular content
            return await self._get_popular_recommendations(content_type, limit, offset)
        
        # verify if recommendations are cached
        cache_key = f"recommendations:user:{self.user.id}:type:{content_type}:limit:{limit}"
        cached = await cache.get(cache_key)
        if cached:
            return json.loads(cached)
        
        if use_ai:
            # Main strategy: AI-based recommendations
            recommendations = await self._get_ai_recommendations(content_type, limit)
        else:
            # Alternative strategy: Hybrid recommendation
            recommendations = await self._get_hybrid_recommendations(content_type, limit)
        
        # Save recommendations in cache for 1 hour
        await cache.set(cache_key, json.dumps([c.id for c in recommendations]), 3600)
        
        return recommendations
    
    async def _get_ai_recommendations(self, content_type: Optional[ContentType], limit: int) -> List[Content]:
        """
        Use Machine Learning techniques to recommend content.
        """
        # 1. Obtain the user profile (vector of preferences)
        user_vector = await self._get_user_content_vector()
        
        # 2. Obtain all available content
        contents = await self._get_available_contents(content_type)
        
        # 3. Calculate score for each content
        scored_contents = []
        for content in contents:
            content_vector = await self._get_content_vector(content)
            
            # Cosine similarity (0 to 1)
            similarity = cosine_similarity(
                [user_vector], 
                [content_vector]
            )[0][0]
            
            # Additional factors
            popularity_score = content.popularity_score or 0.5
            novelty_score = self._calculate_novelty_score(content)
            surprise_score = self._calculate_surprise_score(content, content_vector)
            
            # Final weighting
            final_score = (
                similarity * 0.5 +
                popularity_score * 0.2 +
                novelty_score * 0.15 +
                surprise_score * 0.15
            )
            
            scored_contents.append((content, final_score))
        
        # Sort and return the best results
        scored_contents.sort(key=lambda x: x[1], reverse=True)
        return [c[0] for c in scored_contents[:limit]]
    
    async def _get_user_content_vector(self) -> np.ndarray:
        """
        Build a user preference vector based on historical interactions.
        """
        # Fetch user interactions
        interactions = await self.db.execute(
            select(Interaction)
            .where(Interaction.user_id == self.user.id)
            .where(Interaction.interaction_type.in_([InteractionType.LIKE, InteractionType.RATING]))
        )
        interactions = interactions.scalars().all()
        
        if not interactions:
            # If there are no interactions, use a default vector
            return np.zeros(50)  # 50-dimensional vector
        
        # Get liked content genres
        liked_contents = [i.content_id for i in interactions if i.interaction_type == InteractionType.LIKE]
        
        # Build a preference vector (simplified)
        genre_preferences = {}
        for content_id in liked_contents:
            content = await self.db.get(Content, content_id)
            if content:
                for genre in content.genres:
                    genre_preferences[genre.id] = genre_preferences.get(genre.id, 0) + 1
        
        # Normalize
        if genre_preferences:
            max_value = max(genre_preferences.values())
            for key in genre_preferences:
                genre_preferences[key] /= max_value
        
        # Convert to a 50-dimensional vector
        vector = np.zeros(50)
        for i, (genre_id, score) in enumerate(genre_preferences.items()):
            if i < 50:
                vector[i] = score
        
        return vector
    
    async def _get_content_vector(self, content: Content) -> np.ndarray:
        """
        Vectorize content based on its metadata.
        """
        vector = np.zeros(50)
        
        # Genre-based vector features
        for i, genre in enumerate(content.genres[:10]):
            if i < 50:
                vector[i] = 1.0
        
        # Additional factors
        if content.release_date:
            # Años recientes son más relevantes
            years_old = (datetime.now() - content.release_date).days / 365
            relevance = max(0, 1 - (years_old / 20))  # Decae después de 20 años
            vector[49] = relevance
        
        return vector
    
    def _calculate_novelty_score(self, content: Content) -> float:
        """
        Calculate how new the content is.
        """
        if not content.release_date:
            return 0.5
        
        days_old = (datetime.now() - content.release_date).days
        if days_old < 30:  # Last month
            return 0.9
        elif days_old < 90:  # Last 3 months
            return 0.7
        elif days_old < 365:  # Last year
            return 0.5
        elif days_old < 730:  # 2 years
            return 0.3
        else:
            return 0.1
    
    def _calculate_surprise_score(self, content: Content, content_vector: np.ndarray) -> float:
        """
        Calculate a surprise factor to avoid filter bubble.
        Recommends items slightly outside the comfort zone.
        """
        # Simplified: if the content does not fully match the user's main genres
        user_vector = np.zeros(50)
        # (En producción, aquí se calcularía la distancia)
        distance = np.linalg.norm(user_vector - content_vector)
        
        # Normalize distance (0 to 1)
        max_distance = np.sqrt(50)  # Maximum possible distance
        surprise = distance / max_distance
        
        return min(surprise, 0.5)  # Cap to avoid being too radical
    
    async def _get_hybrid_recommendations(self, content_type: Optional[ContentType], limit: int) -> List[Content]:
        """
        Simpler hybrid approach combining multiple strategies.
        """
        strategies = [
            await self._get_personalized_by_genre(content_type, limit // 2),
            await self._get_popular_recommendations(content_type, limit // 2),
            await self._get_exploration_recommendations(content_type, limit // 4),
        ]
        
        # Combinar y eliminar duplicados
        combined = []
        seen_ids = set()
        for strategy in strategies:
            for content in strategy:
                if content.id not in seen_ids:
                    combined.append(content)
                    seen_ids.add(content.id)
        
        return combined[:limit]
    
    async def _get_personalized_by_genre(self, content_type: Optional[ContentType], limit: int) -> List[Content]:
        """
        Recommend based on genres the user likes.
        """
        # Get the user's preferred genres
        user_genres = await self._get_user_preferred_genres()
        
        if not user_genres:
            return []
        
        # Buscar contenido en esos géneros
        stmt = (
            select(Content)
            .join(Content.genres)
            .where(Genre.id.in_([g.id for g in user_genres]))
            .order_by(desc(Content.average_rating))
            .limit(limit)
        )
        
        if content_type:
            stmt = stmt.where(Content.content_type == content_type)
        
        result = await self.db.execute(stmt)
        return result.scalars().all()
    
    async def _get_popular_recommendations(self, content_type: Optional[ContentType], limit: int) -> List[Content]:
        """
        Recommend globally popular content.
        """
        stmt = (
            select(Content)
            .order_by(desc(Content.popularity_score))
            .limit(limit)
        )
        
        if content_type:
            stmt = stmt.where(Content.content_type == content_type)
        
        result = await self.db.execute(stmt)
        return result.scalars().all()
    
    async def _get_exploration_recommendations(self, content_type: Optional[ContentType], limit: int) -> List[Content]:
        """
        Recommend random content for exploration.
        """
        stmt = (
            select(Content)
            .order_by(func.random())
            .limit(limit)
        )
        
        if content_type:
            stmt = stmt.where(Content.content_type == content_type)
        
        result = await self.db.execute(stmt)
        return result.scalars().all()
    
    async def _get_user_preferred_genres(self):
        """
        Get the user's preferred genres based on interactions.
        """
        # Fetch LIKE interactions
        interactions = await self.db.execute(
            select(Interaction)
            .where(Interaction.user_id == self.user.id)
            .where(Interaction.interaction_type == InteractionType.LIKE)
            .limit(10)  # Solo considerar los últimos 10
        )
        interactions = interactions.scalars().all()
        
        if not interactions:
            return []
        
        # Count genres
        genre_counts = {}
        for interaction in interactions:
            content = await self.db.get(Content, interaction.content_id)
            if content:
                for genre in content.genres:
                    genre_counts[genre.id] = genre_counts.get(genre.id, 0) + 1
        
        # Sort and return the top 5
        sorted_genres = sorted(genre_counts.items(), key=lambda x: x[1], reverse=True)
        top_genre_ids = [id for id, _ in sorted_genres[:5]]
        
        result = await self.db.execute(
            select(Genre).where(Genre.id.in_(top_genre_ids))
        )
        return result.scalars().all()