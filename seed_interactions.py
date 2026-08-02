import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import AsyncSessionLocal
from app.models.user import User
from app.models.content import Content
from app.services.interaction_service import InteractionService
from sqlalchemy import select


async def seed_interactions():
    print("🔄 Creando interacciones de prueba...")
    async with AsyncSessionLocal() as db:
        user = await db.scalar(select(User).where(User.email == "test@test.com"))
        if user is None:
            print("❌ No existe el usuario test@test.com")
            return

        contents = (await db.execute(select(Content).limit(8))).scalars().all()
        if not contents:
            print("❌ No hay contenido para interactuar")
            return

        service = InteractionService(db)
        created = await service.seed_demo_interactions(user.id, [c.id for c in contents])
        await db.commit()
        print(f"✅ {len(created)} interacciones creadas para recomendaciones")


if __name__ == "__main__":
    asyncio.run(seed_interactions())
