from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from sdm.backend.database.session import create_async_engine_from_env, create_async_session_factory


async_engine = create_async_engine_from_env()
AsyncSessionLocal = create_async_session_factory(async_engine)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
