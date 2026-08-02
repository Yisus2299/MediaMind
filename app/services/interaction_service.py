from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.interaction import Interaction, InteractionType
from app.models.content import Content


class InteractionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_interaction(
        self,
        user_id: int,
        content_id: int,
        interaction_type: InteractionType,
        value: Optional[float] = None,
        context: Optional[dict] = None,
    ) -> Interaction:
        interaction = Interaction(
            user_id=user_id,
            content_id=content_id,
            interaction_type=interaction_type,
            value=value,
            context=context or {},
        )
        self.db.add(interaction)
        await self.db.commit()
        await self.db.refresh(interaction)
        return interaction

    async def get_user_interactions(
        self,
        user_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Interaction]:
        stmt = (
            select(Interaction)
            .where(Interaction.user_id == user_id)
            .order_by(Interaction.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    @staticmethod
    def build_demo_interactions(user_id: int, content_ids: List[int]) -> List[dict]:
        interactions = []
        for index, content_id in enumerate(content_ids):
            if index % 3 == 0:
                interaction_type = InteractionType.LIKE
                value = None
            elif index % 3 == 1:
                interaction_type = InteractionType.RATING
                value = min(10.0, 7.0 + (index % 3))
            else:
                interaction_type = InteractionType.DISLIKE
                value = None

            interactions.append(
                {
                    "user_id": user_id,
                    "content_id": content_id,
                    "interaction_type": interaction_type,
                    "value": value,
                    "context": {"source": "demo_seed"},
                }
            )
        return interactions

    async def seed_demo_interactions(self, user_id: int, content_ids: List[int]) -> List[Interaction]:
        created = []
        for payload in self.build_demo_interactions(user_id, content_ids):
            interaction = Interaction(**payload)
            self.db.add(interaction)
            created.append(interaction)

        await self.db.commit()
        for interaction in created:
            await self.db.refresh(interaction)
        return created
