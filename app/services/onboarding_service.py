from typing import Dict, List

from pydantic import BaseModel, Field
from sqlalchemy.orm.attributes import flag_modified

from app.models.content import ContentType
from app.models.interaction import Interaction, InteractionType
from app.models.user import User
from app.services.content_service import import_external_items
from app.services.recommendation_engine import RecommendationEngine

REQUIRED_COUNTS = {
    ContentType.GAME: 5,
    ContentType.MOVIE: 5,
    ContentType.MUSIC: 5,
}


class OnboardingRequest(BaseModel):
    selections: List[Dict] = Field(..., min_length=15, max_length=15)


class OnboardingService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def complete_onboarding(self, user: User, selections: List[Dict]):
        counts = {content_type: 0 for content_type in REQUIRED_COUNTS}

        for item in selections:
            content_type_value = item.get("content_type")
            try:
                content_type = ContentType(content_type_value)
            except (ValueError, TypeError):
                raise ValueError(f"content_type inválido: {content_type_value}")
            if content_type not in REQUIRED_COUNTS:
                raise ValueError(f"tipo no permitido en onboarding: {content_type.value}")
            counts[content_type] += 1

        for content_type, required in REQUIRED_COUNTS.items():
            if counts[content_type] != required:
                raise ValueError(
                    f"se requieren {required} items de {content_type.value}, recibidos {counts[content_type]}"
                )

        imported = await import_external_items(self.db, selections)
        content_ids = []
        for content, _status in imported:
            self.db.add(
                Interaction(
                    user_id=user.id,
                    content_id=content.id,
                    interaction_type=InteractionType.LIKE,
                    context={"source": "onboarding"},
                )
            )
            content_ids.append(content.id)

        prefs = dict(user.preferences or {})
        prefs["onboarding_complete"] = True
        user.preferences = prefs
        flag_modified(user, "preferences")

        await self.db.commit()

        engine = RecommendationEngine(self.db, user)
        recommendations = await engine.get_recommendations(limit=20, strategy="hybrid")
        return {
            "onboarding_complete": True,
            "interactions_created": len(content_ids),
            "recommendations": recommendations,
        }
