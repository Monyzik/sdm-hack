from __future__ import annotations

import argparse

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

from backend.database.models import Base
from backend.database.session import DatabaseUrl, resolve_database_url


def mask_database_url(database_url: DatabaseUrl) -> str:
    return make_url(str(database_url)).render_as_string(hide_password=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create ORM tables for the demo database.")
    parser.add_argument("--database-url", dest="database_url", default=None, help="SQLAlchemy database URL")
    parser.add_argument("--drop-existing", action="store_true", help="Drop ORM tables before creating them")
    parser.add_argument("--echo", action="store_true", help="Print SQL emitted by SQLAlchemy")
    args = parser.parse_args()

    database_url = resolve_database_url(args.database_url)
    engine = create_engine(database_url, echo=args.echo)

    if args.drop_existing:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    table_names = ", ".join(sorted(Base.metadata.tables))
    print(f"Created tables: {table_names}")
    print(f"Database URL: {mask_database_url(database_url)}")


if __name__ == "__main__":
    main()
