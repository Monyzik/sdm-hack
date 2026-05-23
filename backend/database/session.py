from __future__ import annotations

import os

from dotenv import load_dotenv
from sqlalchemy import URL, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


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
        "postgresql+psycopg2",
        username=user,
        password=password,
        host=host,
        port=int(port),
        database=db_name,
    )


def create_engine_from_env(database_url: str | None = None, echo: bool = False) -> Engine:
    return create_engine(resolve_database_url(database_url), echo=echo)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
