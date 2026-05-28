from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.engine import Connection, make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from sdm.backend.database.models import Base
from sdm.backend.database.session import DatabaseUrl, resolve_async_database_url
from scripts.demo_schema import CSV_BOOLEAN_COLUMNS, CSV_COLUMN_LABELS, TASK_HISTORY_FIELD_LABELS


PROJECT_ROOT = Path(__file__).resolve().parents[1]


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

REVERSE_CSV_COLUMN_LABELS = {label: column for column, label in CSV_COLUMN_LABELS.items()}
REVERSE_TASK_HISTORY_FIELD_LABELS = {
    label: field for field, label in TASK_HISTORY_FIELD_LABELS.items()
}
LOCALIZED_BOOLEAN_VALUES = {
    "истина": True,
    "ложь": False,
    "true": True,
    "false": False,
    True: True,
    False: False,
}


def mask_database_url(database_url: DatabaseUrl) -> str:
    return make_url(str(database_url)).render_as_string(hide_password=True)


def load_table(data_dir: Path, table: TableSpec) -> pd.DataFrame:
    path = data_dir / table.filename
    if not path.exists():
        raise FileNotFoundError(f"Не найден файл: {path}")

    df = pd.read_csv(path, keep_default_na=False)
    df = df.rename(
        columns={column: REVERSE_CSV_COLUMN_LABELS.get(column, column) for column in df.columns}
    )
    for column in CSV_BOOLEAN_COLUMNS.intersection(df.columns):
        df[column] = df[column].map(lambda value: LOCALIZED_BOOLEAN_VALUES.get(value, value))
    if "field_changed" in df.columns:
        df["field_changed"] = df["field_changed"].map(
            lambda value: REVERSE_TASK_HISTORY_FIELD_LABELS.get(value, value)
        )
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


def prepare_schema(connection: Connection) -> None:
    Base.metadata.create_all(connection)


async def load_all_tables(
    engine: AsyncEngine,
    data_dir: Path,
    schema: str | None,
    replace_demo: bool = False,
) -> list[tuple[str, int]]:
    async with engine.begin() as connection:
        return await connection.run_sync(
            load_all_tables_sync,
            data_dir,
            schema,
            replace_demo,
        )


def load_all_tables_sync(
    connection: Connection,
    data_dir: Path,
    schema: str | None,
    replace_demo: bool = False,
) -> list[tuple[str, int]]:
    loaded: list[tuple[str, int]] = []
    if schema is None:
        prepare_schema(connection)
    if replace_demo:
        if schema is not None:
            raise ValueError("--replace-demo supports only the default schema")
        remove_demo_projects(connection)
    for table in TABLES:
        row_count = write_table(connection, data_dir, table, schema, "append")
        loaded.append((table.table_name, row_count))
    return loaded


def remove_demo_projects(connection: Connection) -> None:
    """Replace the known synthetic demo only; refuse an unrelated database.

    The caller owns the transaction. Deleting child rows before parents keeps
    constraints intact and a failed CSV import rolls the entire change back.
    """
    known_ids = [f"P{index:03}" for index in range(1, 8)]
    existing = set(connection.execute(text("SELECT id FROM projects FOR UPDATE")).scalars())
    if existing - set(known_ids):
        raise ValueError(
            "Database contains projects outside the synthetic demo; refusing replacement"
        )
    for table_name in ("project_events", "project_rag_chunks", "project_rag_chunks_v2"):
        if connection.scalar(text("SELECT to_regclass(:table_name)"), {"table_name": table_name}):
            connection.execute(
                text(f"DELETE FROM {table_name} WHERE project_id = ANY(:ids)"), {"ids": known_ids}
            )
    for table in reversed(Base.metadata.sorted_tables):
        if "project_id" in table.c:
            connection.execute(table.delete().where(table.c.project_id.in_(known_ids)))
    # All dependent rows belonged to the explicitly selected synthetic projects.
    connection.execute(
        Base.metadata.tables["projects"]
        .delete()
        .where(Base.metadata.tables["projects"].c.id.in_(known_ids))
    )
    connection.execute(Base.metadata.tables["resources"].delete())


def print_summary(items: Iterable[tuple[str, int]]) -> None:
    print("Загрузка завершена:")
    for table_name, count in items:
        print(f"- {table_name}: {count} rows")


async def main_async() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Загрузить демо-CSV в базу данных.")
    parser.add_argument(
        "--database-url", dest="database_url", default=None, help="URL подключения SQLAlchemy"
    )
    parser.add_argument(
        "--data-dir",
        dest="data_dir",
        default=str(PROJECT_ROOT / "data" / "demo"),
        help="Директория с CSV",
    )
    parser.add_argument("--schema", dest="schema", default=None, help="Опциональная схема БД")
    parser.add_argument(
        "--replace-demo",
        action="store_true",
        help="В одной транзакции заменить известные синтетические P001–P007 содержимым CSV",
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        raise FileNotFoundError(f"Не найдена директория с данными: {data_dir}")

    database_url = resolve_async_database_url(args.database_url)
    engine = create_async_engine(database_url)

    try:
        loaded = await load_all_tables(
            engine, data_dir, args.schema, replace_demo=args.replace_demo
        )
        print_summary(loaded)
        print(f"Database URL: {mask_database_url(database_url)}")
    finally:
        await engine.dispose()


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
