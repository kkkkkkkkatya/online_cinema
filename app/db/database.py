from app.config.dependencies import get_settings
from app.db.models.base import Base

settings = get_settings()

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from contextlib import asynccontextmanager

DATABASE_URL = settings.DATABASE_URL
engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


@asynccontextmanager
async def get_db_contextmanager() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


def reset_database():
    with engine.begin() as connection:
        Base.metadata.drop_all(bind=connection)
        Base.metadata.create_all(bind=connection)

