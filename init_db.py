#!/usr/bin/env python
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import engine, Base
import app.models

async def init_db():
    print("🔄 Creando tablas en la base de datos...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Tablas creadas exitosamente!")
    print("📊 Verifica en http://localhost:8000/docs")

if __name__ == "__main__":
    asyncio.run(init_db())