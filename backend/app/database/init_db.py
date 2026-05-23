from __future__ import annotations

import argparse

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from backend.app.database.models import Base
from backend.app.database.session import DatabaseUrl, resolve_database_url

LEGACY_TABLES: tuple[str, ...] = ("project_events",)


def mask_database_url(database_url: DatabaseUrl) -> str:
    return make_url(str(database_url)).render_as_string(hide_password=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Создать ORM-таблицы для демо-БД.")
    parser.add_argument("--database-url", dest="database_url", default=None, help="URL подключения SQLAlchemy")
    parser.add_argument("--drop-existing", action="store_true", help="Удалить ORM-таблицы перед созданием")
    parser.add_argument("--echo", action="store_true", help="Печатать SQL-запросы SQLAlchemy")
    args = parser.parse_args()

    database_url = resolve_database_url(args.database_url)
    engine = create_engine(database_url, echo=args.echo)

    with engine.begin() as connection:
        if args.drop_existing:
            Base.metadata.drop_all(connection)
            for table_name in LEGACY_TABLES:
                connection.execute(text(f"DROP TABLE IF EXISTS {table_name} CASCADE"))
        Base.metadata.create_all(connection)

    table_names = ", ".join(sorted(Base.metadata.tables))
    print(f"Созданы таблицы: {table_names}")
    print(f"Database URL: {mask_database_url(database_url)}")


if __name__ == "__main__":
    main()
