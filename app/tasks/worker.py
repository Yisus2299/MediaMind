from celery import Celery
from celery.schedules import crontab
import asyncio
from datetime import datetime, timedelta

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.content import Content, ContentType
from app.models.user import User
from app.services.recommendation_engine import RecommendationEngine
from app.core.external_apis import external_api
from app.services.content_service import ContentService

# Configurar Celery
celery_app = Celery(
    "mediamind",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.worker"]
)

# Configuración de Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutos
    task_soft_time_limit=25 * 60,  # 25 minutos
    worker_prefetch_multiplier=1,
    worker_concurrency=4,
)

# Tareas programadas
celery_app.conf.beat_schedule = {
    # Actualizar populares cada 6 horas
    "update-popularity-scores": {
        "task": "app.tasks.worker.update_popularity_scores",
        "schedule": crontab(minute=0, hour="*/6"),
    },
    # Actualizar embeddings cada 24 horas
    "update-user-embeddings": {
        "task": "app.tasks.worker.update_user_embeddings",
        "schedule": crontab(minute=0, hour=2),
    },
    # Sincronizar contenido externo cada 12 horas
    "sync-external-content": {
        "task": "app.tasks.worker.sync_external_content",
        "schedule": crontab(minute=0, hour="*/12"),
    },
    # Limpiar caché viejo cada hora
    "clean-cache": {
        "task": "app.tasks.worker.clean_cache",
        "schedule": crontab(minute=0),
    },
}

# ============ TAREAS DE ACTUALIZACIÓN ============

@celery_app.task
def update_popularity_scores():
    """Actualizar scores de popularidad basados en interacciones recientes"""
    asyncio.run(_update_popularity_scores())

async def _update_popularity_scores():
    async with AsyncSessionLocal() as db:
        # Calcular popularidad basada en interacciones de los últimos 30 días
        from sqlalchemy import select, func
        from app.models.interaction import Interaction
        
        # Contar interacciones por contenido
        thirty_days_ago = datetime.now() - timedelta(days=30)
        stmt = (
            select(
                Interaction.content_id,
                func.count(Interaction.id).label("interaction_count"),
                func.avg(Interaction.value).label("avg_rating"),
            )
            .where(Interaction.created_at >= thirty_days_ago)
            .group_by(Interaction.content_id)
        )
        
        result = await db.execute(stmt)
        stats = result.all()
        
        # Actualizar contenidos
        for stat in stats:
            content = await db.get(Content, stat.content_id)
            if content:
                # Fórmula: (interacciones * 0.7) + (rating promedio * 0.3)
                interaction_score = min(1.0, stat.interaction_count / 100)
                rating_score = stat.avg_rating / 10 if stat.avg_rating else 0
                content.popularity_score = (interaction_score * 0.7) + (rating_score * 0.3)
                content.total_interactions = stat.interaction_count
        
        await db.commit()

@celery_app.task
def update_user_embeddings():
    """Actualizar embeddings de todos los usuarios"""
    asyncio.run(_update_user_embeddings())

async def _update_user_embeddings():
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select
        
        # Obtener todos los usuarios
        result = await db.execute(select(User))
        users = result.scalars().all()
        
        for user in users:
            engine = RecommendationEngine(db, user)
            embedding = await engine._get_user_embedding()
            if embedding is not None:
                user.user_embedding = embedding.tolist()
        
        await db.commit()

@celery_app.task
def sync_external_content():
    """Sincronizar contenido de APIs externas"""
    asyncio.run(_sync_external_content())

async def _sync_external_content():
    """Buscar contenido popular de APIs externas y guardarlo localmente"""
    async with AsyncSessionLocal() as db:
        content_service = ContentService(db)
        
        # Lista de búsquedas populares
        popular_queries = [
            "billie eilish", "drake", "pink floyd",  # Música
            "cyberpunk", "zelda", "god of war",  # Juegos
            "inception", "interstellar", "avatar",  # Películas
            "harry potter", "el señor de los anillos",  # Libros
        ]
        
        # Buscar y guardar cada categoría
        with external_api as client:
            for query in popular_queries:
                results = await client.search_all(query, limit_per_type=3)
                
                for content_type, items in results.items():
                    for item in items:
                        # Verificar si ya existe
                        existing = await db.execute(
                            select(Content).where(
                                Content.external_id == item["external_id"],
                                Content.platform == item["platform"]
                            )
                        )
                        if not existing.scalar_one_or_none():
                            # Crear nuevo contenido
                            new_content = Content(**item)
                            db.add(new_content)
        
        await db.commit()

@celery_app.task
def clean_cache():
    """Limpiar caché viejo (ejecutado cada hora)"""
    import redis
    r = redis.from_url(settings.REDIS_URL)
    
    # Eliminar keys con TTL expirado (Redis lo hace automáticamente)
    # Pero podemos eliminar patrones específicos
    pattern = "rec:*"  # Recomendaciones en caché
    keys = r.keys(pattern)
    
    # Mantener solo las últimas 1000 keys
    if len(keys) > 1000:
        keys_to_delete = sorted(keys)[:-1000]
        if keys_to_delete:
            r.delete(*keys_to_delete)

# ============ TAREAS DE USUARIO ============

@celery_app.task
def process_user_interaction(user_id: int, content_id: int, interaction_type: str, value: float = None):
    """Procesar interacción de usuario de forma asíncrona"""
    asyncio.run(_process_user_interaction(user_id, content_id, interaction_type, value))

async def _process_user_interaction(user_id: int, content_id: int, interaction_type: str, value: float = None):
    async with AsyncSessionLocal() as db:
        from app.models.interaction import Interaction, InteractionType
        
        # Crear la interacción
        interaction = Interaction(
            user_id=user_id,
            content_id=content_id,
            interaction_type=InteractionType(interaction_type),
            value=value
        )
        db.add(interaction)
        
        # Actualizar métricas del contenido
        content = await db.get(Content, content_id)
        if content:
            # Recalcular rating promedio
            from sqlalchemy import func
            stmt = select(func.avg(Interaction.value)).where(
                Interaction.content_id == content_id,
                Interaction.interaction_type == InteractionType.RATING
            )
            result = await db.execute(stmt)
            avg_rating = result.scalar()
            
            if avg_rating:
                content.average_rating = avg_rating
            
            # Incrementar total de interacciones
            content.total_interactions += 1
        
        await db.commit()
        
        # Si hay suficientes interacciones, actualizar embedding del usuario
        from sqlalchemy import select
        count_stmt = select(func.count(Interaction.id)).where(Interaction.user_id == user_id)
        count_result = await db.execute(count_stmt)
        interaction_count = count_result.scalar()
        
        if interaction_count and interaction_count % 10 == 0:  # Cada 10 interacciones
            # Actualizar embedding del usuario en background
            update_user_embeddings.delay()

@celery_app.task
def generate_user_recommendations(user_id: int):
    """Pre-generar recomendaciones para un usuario"""
    asyncio.run(_generate_user_recommendations(user_id))

async def _generate_user_recommendations(user_id: int):
    async with AsyncSessionLocal() as db:
        user = await db.get(User, user_id)
        if not user:
            return
        
        engine = RecommendationEngine(db, user)
        
        # Pre-generar para cada tipo
        for content_type in ContentType:
            recommendations = await engine.get_recommendations(
                content_type=content_type,
                limit=10,
                strategy="hybrid"
            )
            
            # Guardar en caché
            from app.core.cache import cache
            cache_key = f"pregen:{user_id}:{content_type.value}"
            await cache.set(cache_key, [c.id for c in recommendations], 3600)  # 1 hora