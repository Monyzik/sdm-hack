from __future__ import annotations

from collections.abc import Generator

from sqlalchemy.orm import Session

from backend.app.database.session import create_engine_from_env, create_session_factory


engine = create_engine_from_env()
SessionLocal = create_session_factory(engine)


def get_session() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session
