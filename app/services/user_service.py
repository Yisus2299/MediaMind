from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from passlib.context import CryptContext

from app.models.user import User
from app.schemas.user import UserCreate
from app.core.security import get_password_hash

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_user_by_email(self, email: str):
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: int):
        return await self.db.get(User, user_id)

    async def create_user(self, user_data: UserCreate) -> User:
        user = User(
            email=user_data.email,
            username=user_data.username,
            full_name=user_data.full_name,
            bio=user_data.bio,
            avatar_url=user_data.avatar_url,
            hashed_password=get_password_hash(user_data.password),
            is_active=True,
            is_verified=False,
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user
