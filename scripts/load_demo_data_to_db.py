from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine, make_url

from backend.app.database.models import Base
from backend.app.database.session import DatabaseUrl, resolve_database_url


@dataclass(frozen=True)
class TableSpec:
    filename: str
    table_name: str
    parse_dates: tuple[str, ...] = ()


TABLES: tuple[TableSpec, ...] = (
    TableSpec("projects.csv", "projects", ("start_date", "planned_end_date")),
    TableSpec("resources.csv", "resources"),
    TableSpec("tasks.csv", "tasks", ("planned_due_date", "actual_end_date")),
    TableSpec("task_history.csv", "task_history", ("changed_at",)),
    TableSpec("task_comments.csv", "task_comments", ("created_at",)),
    TableSpec(
        "milestones.csv",
        "milestones",
        ("planned_start_date", "planned_end_date", "actual_start_date", "actual_end_date"),
    ),
    TableSpec("budgets.csv", "budgets"),
    TableSpec("budget_line_items.csv", "budget_line_items"),
    TableSpec("risks.csv", "risks"),
    TableSpec(
        "communications.csv",
        "communications",
        ("last_message_date", "expected_response_date"),
    ),
    TableSpec("communication_messages.csv", "communication_messages", ("message_time",)),
    TableSpec("resource_allocations.csv", "resource_allocations"),
    TableSpec("task_dependencies.csv", "task_dependencies"),
    TableSpec("dependencies.csv", "dependencies", ("expected_date",)),
    TableSpec("decisions.csv", "decisions", ("decision_date",)),
    TableSpec("change_requests.csv", "change_requests", ("request_date",)),
)

LEGACY_TABLES: tuple[str, ...] = ("project_events",)


def mask_database_url(database_url: DatabaseUrl) -> str:
    return make_url(str(database_url)).render_as_string(hide_password=True)


def load_table(data_dir: Path, table: TableSpec) -> pd.DataFrame:
    path = data_dir / table.filename
    if not path.exists():
        raise FileNotFoundError(f"Не найден файл: {path}")

    df = pd.read_csv(path, keep_default_na=False)
    for column in table.parse_dates:
        if column in df.columns:
            df[column] = pd.to_datetime(df[column], errors="coerce")
    return df


def write_table(
    connection: Connection,
    data_dir: Path,
    table: TableSpec,
    schema: str | None,
    if_exists: str,
) -> int:
    df = load_table(data_dir, table)
    df.to_sql(
        table.table_name,
        connection,
        schema=schema or None,
        if_exists=if_exists,
        index=False,
        method="multi",
        chunksize=1000,
    )
    return len(df)


def prepare_schema(connection: Connection, recreate: bool) -> None:
    if recreate:
        for table_name in LEGACY_TABLES:
            connection.execute(text(f"DROP TABLE IF EXISTS {table_name} CASCADE"))
        Base.metadata.drop_all(connection)
    Base.metadata.create_all(connection)


def load_all_tables(
    engine: Engine,
    data_dir: Path,
    schema: str | None,
    append: bool = False,
) -> list[tuple[str, int]]:
    loaded: list[tuple[str, int]] = []
    if_exists = "append" if schema is None or append else "replace"
    with engine.begin() as connection:
        if schema is None:
            prepare_schema(connection, recreate=not append)
        for table in TABLES:
            row_count = write_table(connection, data_dir, table, schema, if_exists)
            loaded.append((table.table_name, row_count))
    return loaded


def print_summary(items: Iterable[tuple[str, int]]) -> None:
    print("Загрузка завершена:")
    for table_name, count in items:
        print(f"- {table_name}: {count} rows")


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Загрузить демо-CSV в базу данных.")
    parser.add_argument("--database-url", dest="database_url", default=None, help="URL подключения SQLAlchemy")
    parser.add_argument("--data-dir", dest="data_dir", default=str(PROJECT_ROOT / "data"), help="Директория с CSV")
    parser.add_argument("--schema", dest="schema", default=None, help="Опциональная схема БД")
    parser.add_argument("--append", action="store_true", help="Дозалить строки без пересоздания ORM-таблиц")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        raise FileNotFoundError(f"Не найдена директория с данными: {data_dir}")

    database_url = resolve_database_url(args.database_url)
    engine = create_engine(database_url)

    loaded = load_all_tables(engine, data_dir, args.schema, append=args.append)
    print_summary(loaded)
    print(f"Database URL: {mask_database_url(database_url)}")


if __name__ == "__main__":
    main()
