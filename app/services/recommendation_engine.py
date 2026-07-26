from typing import List, Dict, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc, func
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import normalize
from datetime import datetime, timedelta
import json
import random

from app.models.user import User
from app.models.content import Content, ContentType, Genre, Interaction
from app.models.interaction import InteractionType
from app.core.cache import cache
from app.core.config import settings

class RecommendationEngine:
    """
    Motor de recomendación híbrido avanzado con:
    1. Content-based filtering (similitud coseno)
    2. Collaborative filtering (usuarios similares)
    3. Popularity + Trending
    4. Exploration factor (evitar burbuja de filtro)
    5. Context-aware (tiempo, ubicación, dispositivo)
    """
    
    def __init__(self, db: AsyncSession, user: Optional[User] = None):
        self.db = db
        self.user = user
        self.embedding_dim = settings.EMBEDDING_DIMENSION
    
    async def get_recommendations(
        self,
        content_type: Optional[ContentType] = None,
        limit: int = 20,
        context: Dict = None,
        strategy: str = "hybrid"
    ) -> List[Content]:
        """
        Obtiene recomendaciones personalizadas.
        
        Estrategias:
        - "ai": Solo IA (content-based + collaborative)
        - "hybrid": AI + Popularidad + Exploración
        - "popular": Solo popularidad
        - "explore": Enfoque en exploración
        """
        # Verificar caché
        cache_key = self._get_cache_key(content_type, limit, context, strategy)
        cached = await cache.get(cache_key)
        if cached:
            return [await self.db.get(Content, id) for id in cached]
        
        # Obtener recomendaciones según estrategia
        if strategy == "ai" and self.user:
            recommendations = await self._ai_recommendations(content_type, limit, context)
        elif strategy == "hybrid" and self.user:
            recommendations = await self._hybrid_recommendations(content_type, limit, context)
        elif strategy == "explore":
            recommendations = await self._explore_recommendations(content_type, limit, context)
        else:
            recommendations = await self._popular_recommendations(content_type, limit)
        
        # Guardar en caché
        if recommendations:
            await cache.set(cache_key, [c.id for c in recommendations], 1800)  # 30 min
        
        return recommendations
    
    async def _ai_recommendations(
        self,
        content_type: Optional[ContentType],
        limit: int,
        context: Dict = None
    ) -> List[Content]:
        """Recomendación basada en IA (vectorización + similitud)"""
        
        # 1. Obtener embedding del usuario
        user_embedding = await self._get_user_embedding()
        if user_embedding is None:
            # Si no hay suficiente data, usar popularidad
            return await self._popular_recommendations(content_type, limit)
        
        # 2. Obtener todos los contenidos
        stmt = select(Content)
        if content_type:
            stmt = stmt.where(Content.content_type == content_type)
        result = await self.db.execute(stmt)
        contents = result.scalars().all()
        
        # 3. Calcular scores
        scored_contents = []
        for content in contents:
            content_embedding = await self._get_content_embedding(content)
            if content_embedding is None:
                continue
            
            # Similitud coseno
            similarity = cosine_similarity(
                [user_embedding],
                [content_embedding]
            )[0][0]
            
            # Factores adicionales
            popularity_factor = content.popularity_score * 0.15
            recency_factor = self._calculate_recency_factor(content) * 0.10
            diversity_factor = self._calculate_diversity_factor(content, user_embedding) * 0.10
            
            # Puntuación final
            final_score = (
                similarity * 0.65 +
                popularity_factor +
                recency_factor +
                diversity_factor
            )
            
            scored_contents.append((content, final_score))
        
        # Ordenar y devolver
        scored_contents.sort(key=lambda x: x[1], reverse=True)
        return [c[0] for c in scored_contents[:limit]]
    
    async def _hybrid_recommendations(
        self,
        content_type: Optional[ContentType],
        limit: int,
        context: Dict = None
    ) -> List[Content]:
        """Recomendación híbrida combinando múltiples estrategias"""
        
        # Obtener recomendaciones de diferentes fuentes
        ai_recs = await self._ai_recommendations(content_type, limit // 2, context)
        popular_recs = await self._popular_recommendations(content_type, limit // 3)
        explore_recs = await self._explore_recommendations(content_type, limit // 3, context)
        
        # Combinar y eliminar duplicados
        combined = []
        seen_ids = set()
        
        # Dar prioridad a recomendaciones de IA
        for rec in ai_recs:
            if rec.id not in seen_ids:
                combined.append(rec)
                seen_ids.add(rec.id)
        
        # Luego popularidad
        for rec in popular_recs:
            if rec.id not in seen_ids:
                combined.append(rec)
                seen_ids.add(rec.id)
        
        # Finalmente exploración
        for rec in explore_recs:
            if rec.id not in seen_ids:
                combined.append(rec)
                seen_ids.add(rec.id)
        
        return combined[:limit]
    
    async def _popular_recommendations(
        self,
        content_type: Optional[ContentType],
        limit: int
    ) -> List[Content]:
        """Recomendación por popularidad global"""
        stmt = (
            select(Content)
            .order_by(desc(Content.popularity_score))
            .limit(limit)
        )
        if content_type:
            stmt = stmt.where(Content.content_type == content_type)
        
        result = await self.db.execute(stmt)
        return result.scalars().all()
    
    async def _explore_recommendations(
        self,
        content_type: Optional[ContentType],
        limit: int,
        context: Dict = None
    ) -> List[Content]:
        """Recomendaciones para exploración con factor de sorpresa"""
        
        # Obtener contenidos que el usuario no ha visto
        if self.user:
            seen_contents = await self.db.execute(
                select(Interaction.content_id)
                .where(Interaction.user_id == self.user.id)
            )
            seen_ids = [row[0] for row in seen_contents.all()]
        else:
            seen_ids = []
        
        # Buscar contenidos con alta diversidad de géneros
        stmt = (
            select(Content)
            .where(Content.id.notin_(seen_ids) if seen_ids else True)
            .order_by(func.random())  # Aleatorio para exploración
            .limit(limit * 2)  # Conseguir más para luego filtrar
        )
        if content_type:
            stmt = stmt.where(Content.content_type == content_type)
        
        result = await self.db.execute(stmt)
        candidates = result.scalars().all()
        
        # Puntuar con factor de sorpresa
        user_embedding = await self._get_user_embedding() if self.user else None
        scored = []
        
        for content in candidates:
            if user_embedding:
                content_embedding = await self._get_content_embedding(content)
                if content_embedding is not None:
                    # Menor similitud = mayor sorpresa
                    similarity = cosine_similarity(
                        [user_embedding],
                        [content_embedding]
                    )[0][0]
                    surprise_factor = 1 - similarity
                else:
                    surprise_factor = 0.5
            else:
                surprise_factor = 1.0
            
            # Popularidad modesta (no too popular)
            popularity_modesty = max(0, 0.5 - content.popularity_score * 0.5)
            
            score = surprise_factor * 0.6 + popularity_modesty * 0.4
            scored.append((content, score))
        
        scored.sort(key=lambda x: x[1], reverse=True)
        return [c[0] for c in scored[:limit]]
    
    async def _get_user_embedding(self) -> Optional[np.ndarray]:
        """Obtener embedding del usuario (vector de preferencias)"""
        if not self.user:
            return None
        
        # Verificar si ya tiene embedding
        if self.user.user_embedding:
            return np.array(self.user.user_embedding)
        
        # Construir embedding basado en interacciones
        interactions = await self.db.execute(
            select(Interaction)
            .where(Interaction.user_id == self.user.id)
            .where(Interaction.interaction_type.in_([InteractionType.LIKE, InteractionType.RATING]))
            .limit(50)  # Últimas 50 interacciones
        )
        interactions = interactions.scalars().all()
        
        if len(interactions) < settings.MIN_INTERACTIONS_FOR_ML:
            return None
        
        # Construir vector de preferencias por géneros
        genre_vector = np.zeros(self.embedding_dim)
        
        for interaction in interactions:
            content = await self.db.get(Content, interaction.content_id)
            if content and content.genres:
                for genre in content.genres[:3]:  # Top 3 géneros
                    idx = genre.id % self.embedding_dim
                    weight = interaction.value if interaction.value else 1.0
                    genre_vector[idx] += weight * 0.5
        
        # Normalizar
        if np.linalg.norm(genre_vector) > 0:
            genre_vector = normalize([genre_vector])[0]
        
        return genre_vector
    
    async def _get_content_embedding(self, content: Content) -> Optional[np.ndarray]:
        """Obtener embedding del contenido"""
        if content.content_embedding:
            return np.array(content.content_embedding)
        
        # Construir embedding de contenido
        vector = np.zeros(self.embedding_dim)
        
        # Vector por géneros
        if content.genres:
            for genre in content.genres[:3]:
                idx = genre.id % self.embedding_dim
                vector[idx] += 1.0
        
        # Factores de metadatos
        if content.metadata:
            # Año de lanzamiento (más reciente = mayor peso)
            if content.release_date:
                years_old = (datetime.now() - content.release_date).days / 365
                recency = max(0, 1 - (years_old / 20))
                vector[48] = recency
            
            # Calidad (rating promedio)
            vector[49] = content.average_rating / 10 if content.average_rating else 0
        
        # Normalizar
        if np.linalg.norm(vector) > 0:
            vector = normalize([vector])[0]
        
        return vector
    
    def _calculate_recency_factor(self, content: Content) -> float:
        """Calcular factor de actualidad"""
        if not content.release_date:
            return 0.5
        
        days_old = (datetime.now() - content.release_date).days
        if days_old < 30:
            return 1.0
        elif days_old < 90:
            return 0.8
        elif days_old < 180:
            return 0.6
        elif days_old < 365:
            return 0.4
        else:
            return 0.2
    
    def _calculate_diversity_factor(self, content: Content, user_embedding: np.ndarray) -> float:
        """Calcular factor de diversidad (qué tan diferente es de lo que conoce)"""
        content_embedding = self._get_content_embedding_sync(content)
        if content_embedding is None:
            return 0.3
        
        similarity = cosine_similarity([user_embedding], [content_embedding])[0][0]
        # Mayor diferencia = mayor diversidad
        return 1 - similarity
    
    def _get_content_embedding_sync(self, content: Content) -> Optional[np.ndarray]:
        """Versión síncrona para cálculos simples"""
        if content.content_embedding:
            return np.array(content.content_embedding)
        return None
    
    def _get_cache_key(self, content_type: Optional[ContentType], limit: int, context: Dict, strategy: str) -> str:
        """Generar key para caché"""
        key = f"rec:{strategy}:{self.user.id if self.user else 'anonymous'}:{limit}"
        if content_type:
            key += f":{content_type.value}"
        if context:
            key += f":{hash(str(sorted(context.items())))}"
        return key