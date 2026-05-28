"""Export the single-project synthetic scenario to CSV without touching a database."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import date, datetime
from pathlib import Path

from scripts.demo_schema import CSV_COLUMN_LABELS, TABLE_COLUMNS

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_ROOT = PROJECT_ROOT / "data" / "interview"


def _read_synthetic(root: Path, filename: str) -> dict:
    payload = json.loads((root / filename).read_text(encoding="utf-8"))
    if payload.get("synthetic") is not True or payload.get("project_id") != "P007":
        raise ValueError(f"Expected explicitly synthetic P007 data: {filename}")
    return payload


def _local_time(value: str) -> str:
    """Scenario timestamps are Moscow local time, as are demo DateTime columns."""
    timestamp = datetime.fromisoformat(value)
    if timestamp.utcoffset() is not None and timestamp.utcoffset().total_seconds() != 10800:
        raise ValueError("Scenario timestamps must use Moscow time (+03:00)")
    return timestamp.replace(tzinfo=None).isoformat()


def build_records(root: Path = DEFAULT_ROOT) -> dict[str, list[dict]]:
    scenario = _read_synthetic(root, "scenario.json")
    threads = _read_synthetic(root, "conversations.json")["threads"]
    comments = _read_synthetic(root, "task-comments.json")["comments"]
    people = {person["id"]: person for person in scenario["people"]}
    records: dict[str, list[dict]] = {table: [] for table in TABLE_COLUMNS}

    def add(table: str, *values) -> None:
        records[table].append(dict(zip(TABLE_COLUMNS[table], values, strict=True)))

    facts = scenario["facts"]
    add(
        "projects",
        "P007",
        scenario["name"],
        "активен",
        "высокий",
        scenario["start_date"],
        scenario["planned_end_date"],
        "Ответы сотрудникам по проектным данным с проверяемыми источниками.",
        "Пилот на 20 синтетических обращениях после маскирования и утверждения матрицы доступа.",
        "Цель: время проверки с 10 до 4 минут; фактический эффект не измерен.",
    )
    for index, person in enumerate(people.values(), 1):
        add(
            "resources",
            person["id"],
            person["name"],
            person["role"],
            person["team"],
            40,
            person["rate"],
            "специалист",
        )
        add("resource_allocations", f"RA70{index}", person["id"], "P007", 24, 20 + index)
    for index, task in enumerate(scenario["tasks"]):
        person = people[task["assignee"]]
        completed = task.get("completed", "")
        estimated = 8 + (index % 4) * 8
        spent = estimated if completed else max(2, estimated // 2)
        add(
            "tasks",
            task["id"],
            "P007",
            f"ВЕД-{task['id'][1:]}",
            task["title"],
            person["id"],
            person["name"],
            task["status"],
            "критический" if task.get("blocker") else "высокий",
            task["due"],
            completed,
            estimated,
            spent,
            bool(task.get("blocker")),
            task.get("blocker", ""),
        )
        add(
            "task_history",
            f"TH7{index * 2 + 1:03}",
            "P007",
            task["id"],
            "2026-06-15T09:00:00",
            "status",
            "",
            "Новая",
            person["id"],
            "Синтетический трекер",
        )
        add(
            "task_history",
            f"TH7{index * 2 + 2:03}",
            "P007",
            task["id"],
            f"{completed or '2026-06-18'}T16:00:00",
            "status",
            "Новая",
            task["status"],
            person["id"],
            "Синтетический трекер",
        )
    for comment in comments:
        person = people[comment["author_id"]]
        add(
            "task_comments",
            comment["id"],
            "P007",
            comment["task_id"],
            person["id"],
            person["name"],
            _local_time(comment["created_at"]),
            "трекер",
            comment["text"],
            0,
            "Синтетический трекер",
        )
    for thread in threads:
        times = [_local_time(message["time"]) for message in thread["messages"]]
        if times != sorted(times) or not times:
            raise ValueError(f"Messages must be chronological: {thread['id']}")
        add(
            "communications",
            thread["id"],
            "P007",
            thread["from_team"],
            thread["to_team"],
            thread["topic"],
            "проектный чат",
            times[-1][:10],
            thread["expected_response_date"],
            thread["status"],
            thread["importance"],
            thread["linked_task_id"],
        )
        for message, timestamp in zip(thread["messages"], times, strict=True):
            add(
                "communication_messages",
                message["id"],
                "P007",
                thread["id"],
                timestamp,
                message["sender_team"],
                message["recipient_team"],
                "проектный чат",
                message["message_type"],
                "доставлено",
                message["text"],
                thread["linked_task_id"],
                message["is_escalation"],
            )
    add(
        "budgets",
        "B007",
        "P007",
        facts["budget_planned_rub"],
        facts["actual_spent_rub"],
        0,
        0,
        "руб.",
    )
    for index, (name, planned, actual, team) in enumerate(
        [
            ("Подготовка и маскирование данных", 600000, 240000, "Инженерия данных"),
            ("Разработка поиска и QA", 800000, 300000, "AI-разработка"),
            ("Проверка безопасности", 400000, 100000, "Информационная безопасность"),
            ("Тестирование", 300000, 100000, "Тестирование"),
            ("Обучение и сопровождение", 300000, 60000, "Сопровождение"),
        ],
        1,
    ):
        add(
            "budget_line_items",
            f"BLI70{index}",
            "P007",
            "B007",
            "работы",
            name,
            planned,
            actual,
            team,
        )
    milestones = [
        (
            "MS701",
            "Реестр источников",
            "2026-06-15",
            "2026-06-16",
            "2026-06-16",
            "Готово",
            "Инженерия данных",
        ),
        (
            "MS702",
            "Допуск к ограниченному пилоту",
            "2026-06-17",
            "2026-06-23",
            "",
            "Заблокирована",
            "Проектный офис",
        ),
        (
            "MS703",
            "Оценка и приемка пилота",
            "2026-06-23",
            "2026-06-25",
            "",
            "Новая",
            "Тестирование",
        ),
        (
            "MS704",
            "Плановое завершение проекта",
            "2026-06-26",
            "2026-07-15",
            "",
            "Новая",
            "Проектный офис",
        ),
    ]
    for identifier, name, start, due, completed, status, team in milestones:
        add(
            "milestones",
            identifier,
            "P007",
            name,
            start,
            due,
            start if completed else "",
            completed,
            status,
            team,
        )
    for index, (task, predecessor, reason) in enumerate(
        [
            ("T701", "T704", "Закрыть два исключения перед завершением маскирования"),
            ("T702", "T701", "Маскирование — обязательное условие допуска"),
            ("T702", "T705", "Подготовленный проект матрицы требуется для согласования"),
            ("T711", "T702", "Для приемки нужен допуск к пилоту"),
            ("T711", "T706", "Нужен отчет оценки поиска"),
            ("T711", "T708", "Нужны проверки отказов и неподтвержденных утверждений"),
            ("T710", "T709", "Обучение использует согласованный FAQ"),
            ("T716", "T711", "Критерии промышленного запуска учитывают результаты приемки"),
        ],
        1,
    ):
        add(
            "task_dependencies",
            f"TD70{index}",
            "P007",
            task,
            predecessor,
            "finish_to_start",
            index <= 4,
            0,
            reason,
        )
    for index, (task, description, owner, due) in enumerate(
        [
            ("T702", "Утверждение матрицы доступа", "Информационная безопасность", "2026-06-23"),
            ("T712", "Решение по дополнительному резерву", "Проектный офис", "2026-06-23"),
            ("T711", "Итоговый отчет оценки качества", "Тестирование", "2026-06-25"),
            ("T710", "Согласованный FAQ", "Сопровождение", "2026-06-21"),
        ],
        1,
    ):
        add(
            "dependencies",
            f"DEP70{index}",
            "P007",
            "согласование",
            description,
            owner,
            due,
            "ожидает",
            "высокая",
            task,
        )
    for index, (task, description, owner, mitigation, probability, impact) in enumerate(
        [
            (
                "T701",
                "Два исключения маскирования могут задержать допуск",
                "Анна Волкова",
                "Закрыть исключения и повторить проверку",
                4,
                5,
            ),
            (
                "T702",
                "Черновик матрицы могут ошибочно принять за утверждение",
                "Марина Соколова",
                "Проверять статус решения и версию",
                3,
                5,
            ),
            (
                "T708",
                "Корректная ссылка может не подтверждать смысл ответа",
                "Денис Лебедев",
                "Ручная сверка утверждений с источниками",
                4,
                4,
            ),
            (
                "T712",
                "Запрошенный резерв могут включить в утвержденный бюджет",
                "Анна Волкова",
                "Разделять план, прогноз и согласованные изменения",
                3,
                4,
            ),
            (
                "T714",
                "Устаревший индекс может скрыть новые документы",
                "Павел Орлов",
                "Повторная индексация после изменения корпуса",
                3,
                4,
            ),
            (
                "T710",
                "Сотрудники могут принять целевой эффект за достигнутый",
                "Елена Морозова",
                "Объяснить ограничения на обучении",
                2,
                3,
            ),
        ],
        1,
    ):
        add(
            "risks",
            f"RK70{index}",
            "P007",
            "проектный",
            description,
            probability,
            impact,
            owner,
            mitigation,
            "активен",
            task,
        )
    for identifier, description, owner, status, milestone in [
        (
            "DEC701",
            "Запросить резерв 600 000 рублей; решение о выделении средств не принято",
            "Анна Волкова",
            "ожидает",
            "MS702",
        ),
        (
            "DEC702",
            "Матрица доступа подготовлена как проект и ожидает утверждения",
            "Марина Соколова",
            "ожидает",
            "MS702",
        ),
        (
            "DEC703",
            "Каждый ответ помощника утверждает сотрудник",
            "Елена Морозова",
            "принято",
            "MS702",
        ),
        (
            "DEC704",
            "Срок маскирования 22 июня не дает автоматического допуска к пилоту",
            "Анна Волкова",
            "принято",
            "MS702",
        ),
        (
            "DEC705",
            "Проект хранения журналов 30 дней ожидает согласования",
            "Марина Соколова",
            "ожидает",
            "MS703",
        ),
        (
            "DEC706",
            "Для промышленного запуска нужно отдельное подписанное решение; его пока нет",
            "Анна Волкова",
            "ожидает",
            "MS704",
        ),
    ]:
        add(
            "decisions",
            identifier,
            "P007",
            "2026-06-18",
            "организационное",
            description,
            owner,
            status,
            milestone,
        )
    add(
        "change_requests",
        "CR701",
        "P007",
        "2026-06-18",
        "Анна Волкова",
        "бюджет",
        "Запрошен, но не утвержден резерв на дополнительную проверку маскирования и доступа",
        600000,
        0,
        "на согласовании",
    )
    validate_records(records, date.fromisoformat(scenario["as_of"]))
    return records


def validate_records(records: dict[str, list[dict]], as_of: date) -> None:
    from sdm.backend.database.models import Base

    for table, rows in records.items():
        identifiers = [row["id"] for row in rows]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError(f"Duplicate IDs: {table}")
        for row in rows:
            if row.get("project_id", "P007") != "P007":
                raise ValueError("Only P007 belongs in this dataset")
            for foreign_key in Base.metadata.tables[table].foreign_keys:
                key = foreign_key.parent.name
                value = row[key]
                if value and value not in {
                    item[foreign_key.column.name] for item in records[foreign_key.column.table.name]
                }:
                    raise ValueError(f"Broken foreign key: {table}.{key}={value}")
            for field in (
                "message_time",
                "created_at",
                "changed_at",
                "decision_date",
                "request_date",
                "actual_end_date",
            ):
                if row.get(field) and date.fromisoformat(str(row[field])[:10]) > as_of:
                    raise ValueError(f"Future observed event: {table}.{row['id']}")
    for amount, budget in (("planned_amount", "planned_budget"), ("actual_amount", "actual_spent")):
        if (
            sum(row[amount] for row in records["budget_line_items"])
            != records["budgets"][0][budget]
        ):
            raise ValueError(f"Budget lines do not sum to {budget}")


def generate(output_dir: Path, *, root: Path = DEFAULT_ROOT) -> Path:
    output_dir, root = output_dir.resolve(), root.resolve()
    if output_dir == root or output_dir.is_relative_to(root) or root.is_relative_to(output_dir):
        raise ValueError("Output must be isolated from scenario sources")
    records = build_records(root)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("Output directory must be empty; refusing to overwrite")
    output_dir.mkdir(parents=True, exist_ok=True)
    for table, rows in records.items():
        columns = TABLE_COLUMNS[table]
        with (output_dir / f"{table}.csv").open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream, lineterminator="\n")
            writer.writerow([CSV_COLUMN_LABELS[column] for column in columns])
            writer.writerows(
                [
                    "истина" if value is True else "ложь" if value is False else value
                    for value in (row[column] for column in columns)
                ]
                for row in rows
            )
    return output_dir


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(generate(args.output_dir))
