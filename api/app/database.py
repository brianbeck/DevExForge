from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

engine: AsyncEngine | None = None
async_session_factory: async_sessionmaker[AsyncSession] | None = None


class Base(DeclarativeBase):
    pass


def init_engine(database_url: str) -> AsyncEngine:
    global engine, async_session_factory
    engine = create_async_engine(database_url, echo=False, pool_size=10, max_overflow=20)
    async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return engine


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    if async_session_factory is None:
        raise RuntimeError("Database not initialized. Call init_engine() first.")
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
