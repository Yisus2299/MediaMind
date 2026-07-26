from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.models.user import User
from app.schemas.interaction import InteractionCreate, InteractionResponse
from app.services.interaction_service import InteractionService
from app.core.database import get_db
from app.core.security import get_current_user
from app.tasks.worker import process_user_interaction

router = APIRouter(prefix="/interactions", tags=["interactions"])

@router.post("/", response_model=InteractionResponse)
async def create_interaction(
    interaction_data: InteractionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Registrar una interacción del usuario con contenido.
    
    Tipos de interacción:
    - like, dislike, rating, watched, played, read, listened, saved, shared
    """
    service = InteractionService(db)
    
    # Crear la interacción
    interaction = await service.create_interaction(
        user_id=current_user.id,
        content_id=interaction_data.content_id,
        interaction_type=interaction_data.interaction_type,
        value=interaction_data.value,
        context=interaction_data.context
    )
    
    # Procesar en background (actualizar embeddings, métricas, etc.)
    process_user_interaction.delay(
        user_id=current_user.id,
        content_id=interaction_data.content_id,
        interaction_type=interaction_data.interaction_type.value,
        value=interaction_data.value
    )
    
    return interaction

@router.get("/user/{user_id}", response_model=List[InteractionResponse])
async def get_user_interactions(
    user_id: int,
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Obtener historial de interacciones de un usuario"""
    
    # Verificar permisos (solo el propio usuario o admin)
    if current_user.id != user_id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para ver estas interacciones"
        )
    
    service = InteractionService(db)
    return await service.get_user_interactions(user_id, limit, offset)