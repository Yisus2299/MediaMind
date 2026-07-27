from sqlalchemy.ext.asyncio import AsyncSession


class ContentService:
    def __init__(self, db: AsyncSession):
        self.db = db
