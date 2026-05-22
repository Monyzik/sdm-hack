from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Connection, Engine, make_url

from backend.database.models import Base
from backend.database.session import DatabaseUrl, resolve_database_url


@dataclass(frozen=True)
class TableSpec:
    filename: str
    table_name: str
    parse_dates: tuple[str, ...] = ()


TABLES: tuple[TableSpec, ...] = (
    TableSpec("projects.csv", "projects", ("start_date", "planned_end_date")),
    TableSpec("resources.csv", "resources"),
    TableSpec("tasks.csv", "tasks", ("planned_due_date", "actual_end_date")),
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
    TableSpec("project_events.csv", "project_events", ("event_time",)),
)


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

    parser = argparse.ArgumentParser(description="Load demo CSV tables into a database.")
    parser.add_argument("--database-url", dest="database_url", default=None, help="SQLAlchemy database URL")
    parser.add_argument("--data-dir", dest="data_dir", default="data", help="Directory with CSV files")
    parser.add_argument("--schema", dest="schema", default=None, help="Optional database schema")
    parser.add_argument("--append", action="store_true", help="Append rows without recreating ORM tables")
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
