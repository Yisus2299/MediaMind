#!/usr/bin/env python
"""
Script para crear las tablas en la base de datos.
Ejecutar: python init_db.py
"""

import asyncio
import sys
import os

# Agregar el directorio actual al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import engine, Base
import app.models  # Esto importa todos los modelos

async def init_db():
    """Crear todas las tablas"""
    print("🔄 Creando tablas en la base de datos...")
    
    async with engine.begin() as conn:
        # Crear todas las tablas
        await conn.run_sync(Base.metadata.create_all)
    
    print("✅ Tablas creadas exitosamente!")
    
    # Mostrar las tablas creadas
    async with engine.connect() as conn:
        result = await conn.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'")
        tables = result.fetchall()
        print("📊 Tablas creadas:")
        for table in tables:
            print(f"   - {table[0]}")

if __name__ == "__main__":
    asyncio.run(init_db())