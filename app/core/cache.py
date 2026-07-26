import redis.asyncio as redis
import json
from typing import Optional, Any
from app.core.config import settings

class RedisCache:
    def __init__(self):
        self.client = None
    
    async def connect(self):
        """Conectar a Redis"""
        if not self.client:
            self.client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    
    async def get(self, key: str) -> Optional[Any]:
        """Obtener valor del caché"""
        await self.connect()
        value = await self.client.get(key)
        if value:
            try:
                return json.loads(value)
            except:
                return value
        return None
    
    async def set(self, key: str, value: Any, ttl: int = 3600):
        """Guardar en caché"""
        await self.connect()
        if not isinstance(value, str):
            value = json.dumps(value)
        await self.client.setex(key, ttl, value)
    
    async def delete(self, key: str):
        """Eliminar del caché"""
        await self.connect()
        await self.client.delete(key)
    
    async def clear_pattern(self, pattern: str):
        """Eliminar todas las keys que coinciden con un patrón"""
        await self.connect()
        keys = await self.client.keys(pattern)
        if keys:
            await self.client.delete(*keys)

cache = RedisCache()