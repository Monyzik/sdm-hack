from __future__ import annotations

import os

from dotenv import load_dotenv
from sqlalchemy import URL
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine


DatabaseUrl = str | URL


def resolve_database_url(cli_value: str | None = None) -> DatabaseUrl:
    load_dotenv()

    if cli_value:
        return cli_value

    env_value = os.getenv("DATABASE_URL")
    if env_value:
        return env_value

    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    db_name = os.getenv("POSTGRES_DB", "sdm_hack")
    user = os.getenv("POSTGRES_USER", "sdm_hack")
    password = os.getenv("POSTGRES_PASSWORD", "sdm_hack_password")
    return URL.create(
        "postgresql",
        username=user,
        password=password,
        host=host,
        port=int(port),
        database=db_name,
    )


def resolve_async_database_url(cli_value: str | None = None) -> DatabaseUrl:
    return _async_driver_url(resolve_database_url(cli_value))


def create_async_engine_from_env(database_url: str | None = None, echo: bool = False) -> AsyncEngine:
    return create_async_engine(resolve_async_database_url(database_url), echo=echo)


def create_async_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def _async_driver_url(database_url: DatabaseUrl) -> DatabaseUrl:
    url = database_url if isinstance(database_url, URL) else make_url(database_url)
    if url.drivername in {"postgresql", "postgresql+psycopg2", "postgresql+psycopg"}:
        return url.set(drivername="postgresql+asyncpg")
    if url.drivername == "sqlite":
        return url.set(drivername="sqlite+aiosqlite")
    return url
