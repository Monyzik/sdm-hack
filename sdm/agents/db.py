"""Общий пул соединений с БД для агентского сервиса."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from sdm.backend.database.session import create_async_engine_from_env, create_async_session_factory

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_shared_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine_from_env()
    return _engine


def get_shared_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = create_async_session_factory(get_shared_engine())
    return _session_factory


async def dispose_shared_engine() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None
