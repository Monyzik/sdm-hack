from __future__ import annotations

import random
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

import pandas as pd


SEED = 42
random.seed(SEED)

DATA_DIR = Path("data")
LATEST_SNAPSHOT_DATE = date(2026, 6, 19)
PROJECT_COLUMNS = [
    "id",
    "name",
    "owner_name",
    "status",
    "priority",
    "start_date",
    "planned_end_date",
    "business_goal",
    "expected_result",
    "business_value",
]

TASK_COLUMNS = [
    "id",
    "project_id",
    "external_id",
    "title",
    "assignee_id",
    "assignee_name",
    "status",
    "priority",
    "planned_due_date",
    "actual_end_date",
    "estimated_hours",
    "spent_hours",
    "is_blocked",
    "blocker_reason",
]

MILESTONE_COLUMNS = [
    "id",
    "project_id",
    "name",
    "planned_start_date",
    "planned_end_date",
    "actual_start_date",
    "actual_end_date",
    "status",
    "responsible_team",
]

BUDGET_COLUMNS = [
    "id",
    "project_id",
    "planned_budget",
    "actual_spent",
    "forecast_total_spent",
    "expected_economic_effect",
    "cost_of_delay_per_day",
    "currency",
]

RISK_COLUMNS = [
    "id",
    "project_id",
    "risk_type",
    "description",
    "probability",
    "impact",
    "owner_name",
    "mitigation_plan",
    "status",
    "linked_task_id",
]

COMMUNICATION_COLUMNS = [
    "id",
    "project_id",
    "from_team",
    "to_team",
    "topic",
    "channel",
    "last_message_date",
    "expected_response_date",
    "status",
    "importance",
    "linked_task_id",
]

RESOURCE_COLUMNS = [
    "id",
    "full_name",
    "role",
    "team",
    "available_hours_per_week",
    "hour_rate",
    "seniority",
]

RESOURCE_ALLOCATION_COLUMNS = [
    "id",
    "resource_id",
    "project_id",
    "planned_hours_per_week",
    "actual_hours_per_week",
]

EVENT_COLUMNS = [
    "id",
    "project_id",
    "event_type",
    "entity_type",
    "entity_id",
    "old_value",
    "new_value",
    "event_time",
    "description",
]


def iso(value: date | None) -> str:
    return value.isoformat() if value else ""


def iso_dt(value: datetime | None) -> str:
    return value.isoformat(sep=" ", timespec="seconds") if value else ""


def d(year: int, month: int, day: int) -> date:
    return date(year, month, day)


def dt(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(d(year, month, day), time(hour, minute))


def make_projects() -> list[dict[str, Any]]:
    return [
        {
            "id": "P001",
            "name": "Скоринговый модуль МСБ",
            "owner_name": "Елена Морозова",
            "status": "red",
            "priority": "critical",
            "start_date": iso(d(2026, 5, 4)),
            "planned_end_date": iso(d(2026, 6, 30)),
            "business_goal": "Сократить время принятия решения по кредитам МСБ и повысить точность оценки риска.",
            "expected_result": "Модель PD, скоринговый API и интеграция с кредитным конвейером для пилотного сегмента.",
            "business_value": "Ускорение одобрения заявок МСБ до 15 минут и снижение ручной проверки анкет.",
        },
        {
            "id": "P002",
            "name": "Антифрод real-time",
            "owner_name": "Андрей Романов",
            "status": "red",
            "priority": "critical",
            "start_date": iso(d(2026, 4, 27)),
            "planned_end_date": iso(d(2026, 7, 10)),
            "business_goal": "Снизить потери от мошеннических операций за счет потокового скоринга транзакций.",
            "expected_result": "Real-time decisioning pipeline с задержкой до 120 мс и витриной расследований.",
            "business_value": "Сокращение fraud loss и снижение доли ручных блокировок операций.",
        },
        {
            "id": "P003",
            "name": "Мобильный банк 2.0",
            "owner_name": "Мария Громова",
            "status": "green",
            "priority": "high",
            "start_date": iso(d(2026, 5, 6)),
            "planned_end_date": iso(d(2026, 7, 3)),
            "business_goal": "Обновить ключевые пользовательские сценарии мобильного банка для розничных клиентов.",
            "expected_result": "Новый onboarding, платежи по шаблонам, push-подсказки и обновленный профиль клиента.",
            "business_value": "Рост цифровой активности и снижение обращений в контакт-центр по типовым операциям.",
        },
        {
            "id": "P004",
            "name": "Платёжный gateway",
            "owner_name": "Сергей Ковалев",
            "status": "yellow",
            "priority": "high",
            "start_date": iso(d(2026, 5, 11)),
            "planned_end_date": iso(d(2026, 7, 17)),
            "business_goal": "Объединить карточные и СБП-платежи в едином gateway для внутренних продуктов банка.",
            "expected_result": "Высокодоступный gateway, единый API и контур мониторинга для платежных операций.",
            "business_value": "Сокращение стоимости подключения новых платежных сценариев и повышение SLA.",
        },
        {
            "id": "P005",
            "name": "CRM 360",
            "owner_name": "Ольга Беляева",
            "status": "green",
            "priority": "medium",
            "start_date": iso(d(2026, 5, 13)),
            "planned_end_date": iso(d(2026, 7, 24)),
            "business_goal": "Собрать единую клиентскую карточку для продаж, сервиса и аналитики.",
            "expected_result": "Golden record, витрина клиентских событий и API профиля 360 для фронт-систем.",
            "business_value": "Рост конверсии cross-sell и снижение времени поиска клиентской информации.",
        },
    ]


def make_resources() -> list[dict[str, Any]]:
    return [
        {"id": "R001", "full_name": "Алексей Соколов", "role": "Project Manager", "team": "PMO", "available_hours_per_week": 40, "hour_rate": 4200, "seniority": "senior"},
        {"id": "R002", "full_name": "Мария Кузнецова", "role": "Business Analyst", "team": "Business Analysis", "available_hours_per_week": 40, "hour_rate": 3600, "seniority": "middle+"},
        {"id": "R003", "full_name": "Дмитрий Волков", "role": "Backend Developer", "team": "Core Platform", "available_hours_per_week": 40, "hour_rate": 4800, "seniority": "senior"},
        {"id": "R004", "full_name": "Илья Смирнов", "role": "Backend Developer", "team": "Core Platform", "available_hours_per_week": 40, "hour_rate": 4300, "seniority": "middle+"},
        {"id": "R005", "full_name": "Ольга Иванова", "role": "Backend Developer", "team": "Payments", "available_hours_per_week": 40, "hour_rate": 4100, "seniority": "middle"},
        {"id": "R006", "full_name": "Павел Никитин", "role": "Data Engineer", "team": "Data Platform", "available_hours_per_week": 40, "hour_rate": 4500, "seniority": "senior"},
        {"id": "R007", "full_name": "Наталья Федорова", "role": "Data Scientist", "team": "Risk Models", "available_hours_per_week": 40, "hour_rate": 4700, "seniority": "senior"},
        {"id": "R008", "full_name": "Сергей Лебедев", "role": "ML Engineer", "team": "Risk Models", "available_hours_per_week": 40, "hour_rate": 4600, "seniority": "middle+"},
        {"id": "R009", "full_name": "Анна Попова", "role": "QA Engineer", "team": "Quality", "available_hours_per_week": 40, "hour_rate": 3100, "seniority": "middle"},
        {"id": "R010", "full_name": "Роман Егоров", "role": "DevOps Engineer", "team": "Platform", "available_hours_per_week": 40, "hour_rate": 4400, "seniority": "senior"},
        {"id": "R011", "full_name": "Виктория Павлова", "role": "Security Engineer", "team": "Security", "available_hours_per_week": 32, "hour_rate": 5000, "seniority": "senior"},
        {"id": "R012", "full_name": "Георгий Орлов", "role": "Solution Architect", "team": "Enterprise Architecture", "available_hours_per_week": 32, "hour_rate": 5200, "seniority": "principal"},
        {"id": "R013", "full_name": "Екатерина Васильева", "role": "Frontend Developer", "team": "Mobile Web", "available_hours_per_week": 40, "hour_rate": 3900, "seniority": "middle+"},
        {"id": "R014", "full_name": "Кирилл Морозов", "role": "Android Developer", "team": "Mobile", "available_hours_per_week": 40, "hour_rate": 4200, "seniority": "middle+"},
        {"id": "R015", "full_name": "Дарья Захарова", "role": "iOS Developer", "team": "Mobile", "available_hours_per_week": 40, "hour_rate": 4300, "seniority": "middle+"},
        {"id": "R016", "full_name": "Михаил Зайцев", "role": "API Analyst", "team": "Integration", "available_hours_per_week": 40, "hour_rate": 3500, "seniority": "middle"},
        {"id": "R017", "full_name": "Татьяна Белова", "role": "QA Automation Engineer", "team": "Quality", "available_hours_per_week": 40, "hour_rate": 3600, "seniority": "middle+"},
        {"id": "R018", "full_name": "Артур Комаров", "role": "Product Owner", "team": "Digital Bank", "available_hours_per_week": 32, "hour_rate": 4700, "seniority": "senior"},
        {"id": "R019", "full_name": "Софья Андреева", "role": "UX Researcher", "team": "CX", "available_hours_per_week": 32, "hour_rate": 3300, "seniority": "middle"},
        {"id": "R020", "full_name": "Никита Новиков", "role": "Backend Developer", "team": "CRM Platform", "available_hours_per_week": 40, "hour_rate": 4000, "seniority": "middle"},
        {"id": "R021", "full_name": "Полина Соколова", "role": "Data Analyst", "team": "CRM Analytics", "available_hours_per_week": 40, "hour_rate": 3400, "seniority": "middle"},
        {"id": "R022", "full_name": "Евгений Фомин", "role": "Integration Engineer", "team": "Payments", "available_hours_per_week": 40, "hour_rate": 4300, "seniority": "senior"},
        {"id": "R023", "full_name": "Лариса Сергеева", "role": "Compliance Officer", "team": "Compliance", "available_hours_per_week": 32, "hour_rate": 3900, "seniority": "senior"},
        {"id": "R024", "full_name": "Владислав Крылов", "role": "SRE", "team": "Platform", "available_hours_per_week": 40, "hour_rate": 4500, "seniority": "middle+"},
    ]


def make_resource_allocations(resources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    templates = [
        ("R001", "P001", 16, 18),
        ("R001", "P004", 14, 14),
        ("R002", "P001", 24, 26),
        ("R002", "P005", 12, 12),
        ("R003", "P001", 30, 35),
        ("R003", "P002", 18, 23),
        ("R004", "P001", 24, 28),
        ("R004", "P004", 20, 26),
        ("R005", "P004", 28, 30),
        ("R005", "P002", 8, 8),
        ("R006", "P001", 20, 24),
        ("R006", "P005", 14, 18),
        ("R007", "P001", 28, 30),
        ("R007", "P002", 14, 18),
        ("R008", "P002", 30, 34),
        ("R008", "P001", 8, 10),
        ("R009", "P001", 18, 18),
        ("R009", "P003", 12, 12),
        ("R010", "P002", 20, 24),
        ("R010", "P004", 18, 22),
        ("R011", "P001", 12, 18),
        ("R011", "P002", 12, 16),
        ("R011", "P004", 8, 12),
        ("R012", "P001", 10, 12),
        ("R012", "P004", 10, 12),
        ("R013", "P003", 28, 30),
        ("R014", "P003", 28, 30),
        ("R015", "P003", 28, 28),
        ("R016", "P004", 24, 26),
        ("R016", "P005", 8, 8),
        ("R017", "P003", 20, 20),
        ("R017", "P004", 12, 14),
        ("R018", "P003", 18, 18),
        ("R019", "P003", 18, 16),
        ("R020", "P005", 30, 32),
        ("R021", "P005", 28, 30),
        ("R022", "P004", 30, 32),
        ("R023", "P002", 12, 14),
        ("R023", "P005", 10, 10),
        ("R024", "P002", 20, 22),
        ("R024", "P004", 10, 12),
    ]

    rows = []
    for idx, (resource_id, project_id, planned, actual) in enumerate(templates, start=1):
        rows.append(
            {
                "id": f"RA{idx:03d}",
                "resource_id": resource_id,
                "project_id": project_id,
                "planned_hours_per_week": planned,
                "actual_hours_per_week": actual,
            }
        )
    return rows


PROJECT_RESOURCE_IDS = {
    "P001": ["R001", "R002", "R003", "R004", "R006", "R007", "R008", "R009", "R011", "R012"],
    "P002": ["R003", "R005", "R007", "R008", "R010", "R011", "R023", "R024"],
    "P003": ["R009", "R013", "R014", "R015", "R017", "R018", "R019"],
    "P004": ["R001", "R004", "R005", "R010", "R011", "R012", "R016", "R017", "R022", "R024"],
    "P005": ["R002", "R006", "R016", "R020", "R021", "R023"],
}


TASK_CONFIGS = {
    "P001": {"prefix": "SMB-SCR", "count": 30, "blocked": 5, "overdue_open": 7, "done": 16},
    "P002": {"prefix": "FRAUD", "count": 28, "blocked": 4, "overdue_open": 8, "done": 12},
    "P003": {"prefix": "MB20", "count": 24, "blocked": 1, "overdue_open": 2, "done": 18},
    "P004": {"prefix": "PAYGW", "count": 26, "blocked": 2, "overdue_open": 5, "done": 15},
    "P005": {"prefix": "CRM360", "count": 22, "blocked": 1, "overdue_open": 2, "done": 16},
}

PROJECT_TASK_OBJECTS = {
    "P001": [
        "согласование Security для скорингового API",
        "витрину признаков из АБС",
        "маппинг полей CRM и кредитного конвейера",
        "валидацию модели PD",
        "endpoint расчета scorecard",
        "логирование решений модели",
        "контроль версий признаков",
        "интеграцию с DWH",
        "регламент отката модели",
        "A/B контур для пилота МСБ",
    ],
    "P002": [
        "streaming pipeline транзакций",
        "правила блокировки high-risk операций",
        "интеграцию с процессингом карт",
        "витрину расследований fraud cases",
        "feature store для real-time признаков",
        "нагрузочный профиль 120 мс",
        "алерты по всплескам отказов",
        "модель поведенческого скоринга",
        "контур ручного разбора кейсов",
        "отчетность для compliance",
    ],
    "P003": [
        "новый onboarding клиента",
        "экран платежей по шаблонам",
        "push-подсказки в профиле",
        "рефакторинг авторизации",
        "аналитику клиентских событий",
        "A/B тест главного экрана",
        "дизайн-систему мобильных компонентов",
        "регрессионный пакет автотестов",
        "интеграцию с biometric login",
        "релизные заметки для стора",
    ],
    "P004": [
        "единый payment API",
        "коннектор СБП",
        "карточный acquiring adapter",
        "маршрутизацию платежей",
        "идемпотентность операций",
        "мониторинг SLA",
        "PCI DSS checklist",
        "нагрузочные тесты gateway",
        "резервный контур обработки",
        "сверку платежных статусов",
    ],
    "P005": [
        "golden record клиента",
        "правила дедупликации контактов",
        "витрину клиентских событий",
        "API профиля 360",
        "маппинг каналов продаж",
        "историю взаимодействий",
        "качество данных по ИНН",
        "сегменты cross-sell",
        "ролевую модель доступа CRM",
        "дашборд полноты профиля",
    ],
}

TASK_ACTIONS = [
    "Разработать",
    "Настроить",
    "Проверить",
    "Согласовать",
    "Подготовить",
    "Протестировать",
    "Интегрировать",
    "Документировать",
]

BLOCKER_REASONS = {
    "P001": [
        "Ожидается заключение Security по доступу к персональным данным",
        "Нет подтверждения SLA от DWH",
        "Не выделен backend reviewer",
        "Не согласована схема маскирования данных",
        "Зависимость от кредитного конвейера перенесена на следующий спринт",
    ],
    "P002": [
        "Процессинг не подтвердил окно подключения",
        "Security запросила дополнительную модель угроз",
        "Недоступен стенд потоковой обработки",
        "Не согласованы правила false positive review",
    ],
    "P003": [
        "Ожидается финальный UX approve по onboarding",
    ],
    "P004": [
        "Вендор СБП задерживает тестовые сертификаты",
        "PCI DSS checklist возвращен на доработку",
    ],
    "P005": [
        "Не получено подтверждение владельца данных по CRM-дублям",
    ],
}

BLOCKED_DUE_DATES = {
    "P001": [d(2026, 6, 10), d(2026, 5, 27), d(2026, 6, 4), d(2026, 6, 14), d(2026, 6, 16)],
    "P002": [d(2026, 5, 29), d(2026, 6, 3), d(2026, 6, 9), d(2026, 6, 13)],
    "P003": [d(2026, 6, 16)],
    "P004": [d(2026, 6, 5), d(2026, 6, 12)],
    "P005": [d(2026, 6, 14)],
}


def make_task_title(project_id: str, number: int) -> str:
    if project_id == "P001" and number == 1:
        return "Получить согласование Security для скорингового API"
    action = TASK_ACTIONS[(number + random.randint(0, 3)) % len(TASK_ACTIONS)]
    subject = PROJECT_TASK_OBJECTS[project_id][(number - 1) % len(PROJECT_TASK_OBJECTS[project_id])]
    return f"{action} {subject}"


def make_tasks(resources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    resource_by_id = {row["id"]: row for row in resources}
    tasks: list[dict[str, Any]] = []
    next_id = 1

    for project_id, config in TASK_CONFIGS.items():
        resource_ids = PROJECT_RESOURCE_IDS[project_id]
        for number in range(1, config["count"] + 1):
            assignee_id = random.choice(resource_ids)
            assignee = resource_by_id[assignee_id]

            is_blocked = number <= config["blocked"]
            is_overdue_open = config["blocked"] < number <= config["blocked"] + config["overdue_open"]
            is_done = (
                config["blocked"] + config["overdue_open"]
                < number
                <= config["blocked"] + config["overdue_open"] + config["done"]
            )

            if is_blocked:
                status = "Blocked"
                planned_due = BLOCKED_DUE_DATES[project_id][number - 1]
                actual_end = None
                blocker_reason = BLOCKER_REASONS[project_id][(number - 1) % len(BLOCKER_REASONS[project_id])]
                priority = "critical" if number <= 2 else "high"
                spent_hours = random.randint(18, 70)
            elif is_overdue_open:
                status = random.choice(["In Progress", "Review"])
                planned_due = LATEST_SNAPSHOT_DATE - timedelta(days=random.randint(2, 24))
                actual_end = None
                blocker_reason = ""
                priority = random.choice(["high", "high", "medium"])
                spent_hours = random.randint(20, 82)
            elif is_done:
                status = "Done"
                planned_due = d(2026, 5, 12) + timedelta(days=random.randint(0, 31))
                actual_end = planned_due + timedelta(days=random.randint(-2, 6))
                if actual_end > LATEST_SNAPSHOT_DATE:
                    actual_end = LATEST_SNAPSHOT_DATE - timedelta(days=random.randint(0, 2))
                blocker_reason = ""
                priority = random.choice(["medium", "medium", "high", "low"])
                spent_hours = random.randint(12, 74)
            else:
                status = random.choice(["To Do", "In Progress"])
                planned_due = LATEST_SNAPSHOT_DATE + timedelta(days=random.randint(4, 28))
                actual_end = None
                blocker_reason = ""
                priority = random.choice(["medium", "low", "high"])
                spent_hours = random.randint(0, 24)

            estimated_hours = max(8, spent_hours + random.randint(-8, 16))
            task = {
                "id": f"T{next_id:03d}",
                "project_id": project_id,
                "external_id": f"{config['prefix']}-{number:03d}",
                "title": make_task_title(project_id, number),
                "assignee_id": assignee_id,
                "assignee_name": assignee["full_name"],
                "status": status,
                "priority": priority,
                "planned_due_date": iso(planned_due),
                "actual_end_date": iso(actual_end),
                "estimated_hours": estimated_hours,
                "spent_hours": spent_hours,
                "is_blocked": is_blocked,
                "blocker_reason": blocker_reason,
            }
            tasks.append(task)
            next_id += 1

    return tasks


def task_lookup(tasks: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for task in tasks:
        grouped[task["project_id"]].append(task)
    return grouped


def task_id(tasks_by_project: dict[str, list[dict[str, Any]]], project_id: str, number: int) -> str:
    return tasks_by_project[project_id][number - 1]["id"]


def make_milestones() -> list[dict[str, Any]]:
    milestone_templates = {
        "P001": [
            ("Discovery и требования", d(2026, 5, 4), d(2026, 5, 15), d(2026, 5, 4), d(2026, 5, 16), "Done", "Business Analysis", 1),
            ("Модель и витрина признаков", d(2026, 5, 18), d(2026, 6, 5), d(2026, 5, 19), d(2026, 6, 8), "Done", "Risk Models", 3),
            ("Security review и интеграция", d(2026, 6, 8), d(2026, 6, 12), d(2026, 6, 9), None, "Delayed", "Security", 14),
            ("Пилот в кредитном конвейере", d(2026, 6, 15), d(2026, 6, 30), None, None, "At Risk", "Core Platform", 14),
        ],
        "P002": [
            ("Архитектура streaming-контура", d(2026, 4, 27), d(2026, 5, 15), d(2026, 4, 28), d(2026, 5, 17), "Done", "Enterprise Architecture", 2),
            ("Интеграция с процессингом", d(2026, 5, 18), d(2026, 6, 5), d(2026, 5, 20), None, "Delayed", "Payments", 18),
            ("Модель fraud decisioning", d(2026, 5, 25), d(2026, 6, 19), d(2026, 5, 27), None, "At Risk", "Risk Models", 10),
            ("UAT и промышленный контур", d(2026, 6, 22), d(2026, 7, 10), None, None, "Planned", "Platform", 0),
        ],
        "P003": [
            ("UX и дизайн-система", d(2026, 5, 6), d(2026, 5, 22), d(2026, 5, 6), d(2026, 5, 21), "Done", "CX", 0),
            ("Разработка клиентских сценариев", d(2026, 5, 25), d(2026, 6, 12), d(2026, 5, 25), d(2026, 6, 12), "Done", "Mobile", 0),
            ("Регрессия и аналитика", d(2026, 6, 15), d(2026, 6, 26), d(2026, 6, 15), None, "In Progress", "Quality", 0),
            ("Pilot release", d(2026, 6, 29), d(2026, 7, 3), None, None, "Planned", "Digital Bank", 0),
        ],
        "P004": [
            ("API contract и архитектура", d(2026, 5, 11), d(2026, 5, 29), d(2026, 5, 12), d(2026, 6, 1), "Done", "Integration", 3),
            ("СБП и acquiring adapters", d(2026, 6, 1), d(2026, 6, 19), d(2026, 6, 3), None, "At Risk", "Payments", 7),
            ("PCI DSS и безопасность", d(2026, 6, 15), d(2026, 6, 26), d(2026, 6, 17), None, "At Risk", "Security", 5),
            ("Нагрузочное тестирование", d(2026, 6, 29), d(2026, 7, 17), None, None, "Planned", "Platform", 0),
        ],
        "P005": [
            ("Data discovery", d(2026, 5, 13), d(2026, 5, 29), d(2026, 5, 13), d(2026, 5, 30), "Done", "CRM Analytics", 1),
            ("Golden record", d(2026, 6, 1), d(2026, 6, 19), d(2026, 6, 1), d(2026, 6, 18), "Done", "Data Platform", 0),
            ("API профиля 360", d(2026, 6, 22), d(2026, 7, 10), None, None, "Planned", "CRM Platform", 0),
            ("Пилот с продажами", d(2026, 7, 13), d(2026, 7, 24), None, None, "Planned", "Sales", 0),
        ],
    }

    rows = []
    idx = 1
    for project_id, milestones in milestone_templates.items():
        for name, planned_start, planned_end, actual_start, actual_end, status, team, delay in milestones:
            rows.append(
                {
                    "id": f"M{idx:03d}",
                    "project_id": project_id,
                    "name": name,
                    "planned_start_date": iso(planned_start),
                    "planned_end_date": iso(planned_end),
                    "actual_start_date": iso(actual_start),
                    "actual_end_date": iso(actual_end),
                    "status": status,
                    "responsible_team": team,
                }
            )
            idx += 1
    return rows


def make_budgets() -> list[dict[str, Any]]:
    return [
        {"id": "B001", "project_id": "P001", "planned_budget": 48_000_000, "actual_spent": 41_500_000, "forecast_total_spent": 62_000_000, "expected_economic_effect": 57_000_000, "cost_of_delay_per_day": 1_250_000, "currency": "RUB"},
        {"id": "B002", "project_id": "P002", "planned_budget": 72_000_000, "actual_spent": 64_000_000, "forecast_total_spent": 88_000_000, "expected_economic_effect": 112_000_000, "cost_of_delay_per_day": 1_800_000, "currency": "RUB"},
        {"id": "B003", "project_id": "P003", "planned_budget": 42_000_000, "actual_spent": 29_500_000, "forecast_total_spent": 40_000_000, "expected_economic_effect": 76_000_000, "cost_of_delay_per_day": 650_000, "currency": "RUB"},
        {"id": "B004", "project_id": "P004", "planned_budget": 38_000_000, "actual_spent": 31_000_000, "forecast_total_spent": 43_000_000, "expected_economic_effect": 59_000_000, "cost_of_delay_per_day": 950_000, "currency": "RUB"},
        {"id": "B005", "project_id": "P005", "planned_budget": 34_000_000, "actual_spent": 22_500_000, "forecast_total_spent": 33_000_000, "expected_economic_effect": 68_000_000, "cost_of_delay_per_day": 520_000, "currency": "RUB"},
    ]


def make_risks(tasks_by_project: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    risk_specs = [
        ("P001", "Security", "Security может не согласовать обработку персональных данных для скорингового API.", 5, 5, "Виктория Павлова", "Вынести модель угроз на risk committee и подготовить маскирование полей.", "escalated", task_id(tasks_by_project, "P001", 1), d(2026, 6, 10)),
        ("P001", "Resource", "Backend lead распределен между двумя critical-проектами и работает выше доступной емкости.", 4, 5, "Елена Морозова", "Перенести часть задач на второго backend и зафиксировать WIP limit.", "active", task_id(tasks_by_project, "P001", 6), d(2026, 5, 29)),
        ("P001", "Budget", "Прогноз бюджета превышает план из-за доработок Security и интеграций.", 4, 4, "Елена Морозова", "Согласовать scope cut и отдельный резерв на compliance-доработки.", "active", task_id(tasks_by_project, "P001", 9), d(2026, 6, 12)),
        ("P001", "Dependency", "DWH не подтвердил стабильный SLA на витрину признаков МСБ.", 3, 5, "Павел Никитин", "Согласовать fallback extract и ежедневный контроль качества данных.", "mitigating", task_id(tasks_by_project, "P001", 2), d(2026, 6, 5)),
        ("P001", "Data Quality", "Исторические признаки по части заявок МСБ неполные.", 3, 4, "Наталья Федорова", "Запустить сверку с кредитным конвейером и исключить неполные сэмплы.", "active", task_id(tasks_by_project, "P001", 4), d(2026, 5, 29)),
        ("P002", "Performance", "Latency real-time decisioning превышает целевой лимит 120 мс на peak load.", 4, 5, "Сергей Лебедев", "Оптимизировать feature lookup и включить circuit breaker.", "escalated", task_id(tasks_by_project, "P002", 6), d(2026, 5, 29)),
        ("P002", "Integration", "Процессинг карт переносит окно подключения и блокирует end-to-end тесты.", 5, 4, "Евгений Фомин", "Эскалировать слот подключения и подготовить stub-контур.", "escalated", task_id(tasks_by_project, "P002", 1), d(2026, 6, 3)),
        ("P002", "Compliance", "Нужно доказать контролируемый уровень false positive для операций клиентов.", 4, 4, "Лариса Сергеева", "Подготовить отчетность по тестовой выборке и критерии ручного разбора.", "active", task_id(tasks_by_project, "P002", 8), d(2026, 6, 5)),
        ("P002", "Security", "Дополнительная модель угроз задерживает доступ к продуктивным событиям.", 3, 5, "Виктория Павлова", "Провести threat modeling workshop и согласовать read-only доступ.", "active", task_id(tasks_by_project, "P002", 2), d(2026, 6, 9)),
        ("P002", "Resource", "ML engineer перегружен задачами расследований и performance tuning.", 3, 4, "Андрей Романов", "Выделить отдельный слот на оптимизацию модели.", "mitigating", task_id(tasks_by_project, "P002", 7), d(2026, 5, 29)),
        ("P003", "Release", "Ревью в app store может занять больше стандартного окна.", 2, 3, "Артур Комаров", "Отправить build заранее и подготовить phased rollout.", "active", task_id(tasks_by_project, "P003", 10), d(2026, 6, 12)),
        ("P003", "UX", "Пользователи могут хуже проходить обновленный onboarding без подсказок.", 2, 3, "Софья Андреева", "Провести дополнительный usability test на контрольной группе.", "mitigating", task_id(tasks_by_project, "P003", 1), d(2026, 5, 29)),
        ("P003", "Dependency", "Biometric login зависит от смежного релиза авторизации.", 2, 4, "Екатерина Васильева", "Оставить feature toggle и fallback password flow.", "active", task_id(tasks_by_project, "P003", 9), d(2026, 6, 5)),
        ("P004", "Vendor", "Вендор СБП задерживает тестовые сертификаты для gateway.", 4, 4, "Сергей Ковалев", "Эскалация через vendor manager и подготовка sandbox-mock.", "active", task_id(tasks_by_project, "P004", 1), d(2026, 6, 5)),
        ("P004", "Security", "PCI DSS checklist требует дополнительного аудита хранения токенов.", 3, 5, "Виктория Павлова", "Разделить scope аудита и вынести спорные пункты на CAB.", "active", task_id(tasks_by_project, "P004", 2), d(2026, 6, 12)),
        ("P004", "Performance", "Gateway может не выдержать пиковые платежные окна без SRE-тюнинга.", 3, 4, "Владислав Крылов", "Добавить synthetic load и автоалерты по latency.", "mitigating", task_id(tasks_by_project, "P004", 8), d(2026, 6, 12)),
        ("P004", "Budget", "Дополнительные vendor-сертификаты увеличивают forecast_total_spent.", 3, 3, "Сергей Ковалев", "Зафиксировать лимит закупки и убрать часть non-critical scope.", "active", task_id(tasks_by_project, "P004", 3), d(2026, 6, 12)),
        ("P005", "Data Quality", "Дубликаты клиентов в CRM и DWH расходятся по ключевым атрибутам.", 3, 4, "Полина Соколова", "Ввести confidence score для golden record и ручную валидацию топ-сегментов.", "active", task_id(tasks_by_project, "P005", 7), d(2026, 5, 29)),
        ("P005", "Adoption", "Команды продаж могут продолжить использовать старые карточки клиентов.", 2, 3, "Ольга Беляева", "Провести пилот с двумя регионами и собрать обратную связь.", "mitigating", task_id(tasks_by_project, "P005", 5), d(2026, 6, 5)),
        ("P005", "Compliance", "Нужна проверка ролей доступа к чувствительным клиентским атрибутам.", 2, 4, "Лариса Сергеева", "Согласовать матрицу ролей до начала пилота.", "active", task_id(tasks_by_project, "P005", 9), d(2026, 6, 12)),
    ]

    rows = []
    for idx, spec in enumerate(risk_specs, start=1):
        (
            project_id,
            risk_type,
            description,
            probability,
            impact,
            owner,
            mitigation,
            status,
            linked_task_id,
            active_from,
        ) = spec
        rows.append(
            {
                "id": f"RK{idx:03d}",
                "project_id": project_id,
                "risk_type": risk_type,
                "description": description,
                "probability": probability,
                "impact": impact,
                "owner_name": owner,
                "mitigation_plan": mitigation,
                "status": status,
                "linked_task_id": linked_task_id,
                "_active_from": active_from,
            }
        )
    return rows


def make_communications(tasks_by_project: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    def row(
        idx: int,
        project_id: str,
        from_team: str,
        to_team: str,
        topic: str,
        channel: str,
        last_message_date: date,
        expected_response_date: date,
        status: str,
        importance: str,
        linked_task_id: str,
    ) -> dict[str, Any]:
        return {
            "id": f"C{idx:03d}",
            "project_id": project_id,
            "from_team": from_team,
            "to_team": to_team,
            "topic": topic,
            "channel": channel,
            "last_message_date": iso(last_message_date),
            "expected_response_date": iso(expected_response_date),
            "status": status,
            "importance": importance,
            "linked_task_id": linked_task_id,
        }

    specs = [
        ("P001", "Risk Models", "Security", "Согласование обработки ПДн для скорингового API", "Teams", d(2026, 6, 4), d(2026, 6, 5), "escalated", "critical", task_id(tasks_by_project, "P001", 1)),
        ("P001", "Data Platform", "DWH", "SLA витрины признаков МСБ", "Email", d(2026, 6, 6), d(2026, 6, 7), "delayed", "high", task_id(tasks_by_project, "P001", 2)),
        ("P001", "Core Platform", "Credit Conveyor", "Окно интеграционного тестирования скоринга", "Jira", d(2026, 6, 12), d(2026, 6, 14), "delayed", "high", task_id(tasks_by_project, "P001", 5)),
        ("P001", "PMO", "Business Owner", "Решение по scope cut после роста бюджета", "Email", d(2026, 6, 17), d(2026, 6, 18), "pending", "high", task_id(tasks_by_project, "P001", 9)),
        ("P001", "Risk Models", "Data Quality", "Сверка неполных признаков по заявкам МСБ", "Confluence", d(2026, 6, 13), d(2026, 6, 17), "responded", "medium", task_id(tasks_by_project, "P001", 4)),
        ("P002", "Fraud Platform", "Card Processing", "Окно подключения transaction stream", "Email", d(2026, 6, 1), d(2026, 6, 3), "escalated", "critical", task_id(tasks_by_project, "P002", 1)),
        ("P002", "Risk Models", "Compliance", "Критерии false positive review", "Teams", d(2026, 6, 7), d(2026, 6, 10), "delayed", "high", task_id(tasks_by_project, "P002", 8)),
        ("P002", "Platform", "SRE", "CPU profile feature lookup", "Jira", d(2026, 6, 13), d(2026, 6, 14), "responded", "medium", task_id(tasks_by_project, "P002", 6)),
        ("P002", "Security", "Fraud Platform", "Threat model для real-time событий", "Confluence", d(2026, 6, 11), d(2026, 6, 13), "pending", "high", task_id(tasks_by_project, "P002", 2)),
        ("P002", "PMO", "Business Owner", "Решение по запуску пилота без части правил", "Email", d(2026, 6, 16), d(2026, 6, 18), "pending", "high", task_id(tasks_by_project, "P002", 3)),
        ("P003", "Mobile", "CX", "Финальный approve onboarding", "Teams", d(2026, 6, 15), d(2026, 6, 16), "responded", "medium", task_id(tasks_by_project, "P003", 1)),
        ("P003", "Mobile", "Analytics", "Событийная схема для нового профиля", "Jira", d(2026, 6, 14), d(2026, 6, 17), "responded", "medium", task_id(tasks_by_project, "P003", 5)),
        ("P003", "Digital Bank", "Release Management", "Слот pilot release", "Email", d(2026, 6, 18), d(2026, 6, 19), "pending", "medium", task_id(tasks_by_project, "P003", 10)),
        ("P003", "Quality", "Mobile", "Регрессионный прогон critical flows", "Jira", d(2026, 6, 17), d(2026, 6, 18), "responded", "medium", task_id(tasks_by_project, "P003", 8)),
        ("P004", "Payments", "SBP Vendor", "Тестовые сертификаты СБП", "Email", d(2026, 6, 6), d(2026, 6, 8), "delayed", "critical", task_id(tasks_by_project, "P004", 1)),
        ("P004", "Security", "Payments", "PCI DSS token storage review", "Confluence", d(2026, 6, 11), d(2026, 6, 13), "delayed", "high", task_id(tasks_by_project, "P004", 2)),
        ("P004", "Platform", "SRE", "Нагрузочное окно gateway", "Teams", d(2026, 6, 16), d(2026, 6, 17), "responded", "medium", task_id(tasks_by_project, "P004", 8)),
        ("P004", "PMO", "Business Owner", "Перенос части merchant-сценариев", "Email", d(2026, 6, 18), d(2026, 6, 19), "pending", "medium", task_id(tasks_by_project, "P004", 3)),
        ("P005", "CRM Analytics", "Data Owners", "Правила дедупликации контактов", "Teams", d(2026, 6, 12), d(2026, 6, 14), "responded", "medium", task_id(tasks_by_project, "P005", 2)),
        ("P005", "CRM Platform", "Compliance", "Матрица доступа к профилю 360", "Confluence", d(2026, 6, 13), d(2026, 6, 17), "pending", "medium", task_id(tasks_by_project, "P005", 9)),
        ("P005", "Sales", "CRM Platform", "Сценарии пилота для регионов", "Email", d(2026, 6, 18), d(2026, 6, 19), "pending", "low", task_id(tasks_by_project, "P005", 5)),
        ("P005", "Data Platform", "CRM Analytics", "Сверка golden record после дедупликации", "Jira", d(2026, 6, 16), d(2026, 6, 18), "responded", "medium", task_id(tasks_by_project, "P005", 1)),
    ]

    return [row(idx, *spec) for idx, spec in enumerate(specs, start=1)]


def parse_date(value: str) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def find_id(rows: list[dict[str, Any]], **conditions: Any) -> str:
    for row in rows:
        if all(row.get(key) == value for key, value in conditions.items()):
            return row["id"]
    raise ValueError(f"Row not found: {conditions}")


def make_project_events(
    tasks_by_project: dict[str, list[dict[str, Any]]],
    milestones: list[dict[str, Any]],
    budgets: list[dict[str, Any]],
    risks: list[dict[str, Any]],
    communications: list[dict[str, Any]],
    allocations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    p001_security_task = task_id(tasks_by_project, "P001", 1)
    p001_milestone = find_id(milestones, project_id="P001", name="Security review и интеграция")
    p001_budget = find_id(budgets, project_id="P001")
    p001_security_risk = find_id(risks, project_id="P001", risk_type="Security")
    p001_security_comm = find_id(communications, project_id="P001", to_team="Security")
    p001_backend_allocation = find_id(allocations, project_id="P001", resource_id="R003")

    event_specs = [
        ("P001", "milestone_shifted", "milestone", p001_milestone, "planned_end_date=2026-06-12", "planned_end_date=2026-06-26", dt(2026, 6, 9, 16, 20), "Security review по скоринговому API сдвинут на 14 дней после повторного запроса модели угроз."),
        ("P001", "task_blocked", "task", p001_security_task, "status=In Progress", "status=Blocked; blocker_reason=Security approval pending", dt(2026, 6, 10, 11, 5), "Tasktracker получил blocked-задачу по согласованию Security для обработки персональных данных."),
        ("P001", "budget_forecast_changed", "budget", p001_budget, "forecast_total_spent=54000000; cost_of_delay_per_day=850000", "forecast_total_spent=62000000; cost_of_delay_per_day=1250000", dt(2026, 6, 12, 15, 30), "Прогноз бюджета и Cost of Delay выросли после переноса Security review и расширения compliance scope."),
        ("P001", "risk_score_increased", "risk", p001_security_risk, "probability=3; impact=4", "probability=5; impact=5", dt(2026, 6, 10, 18, 10), "Риск Security стал критическим: расчетный score вырос с 12 до 25 после risk committee."),
        ("P001", "communication_delayed", "communication", p001_security_comm, "status=pending", "status=escalated", dt(2026, 6, 12, 10, 45), "Ответ Security по согласованию данных просрочен и эскалирован владельцу проекта."),
        ("P001", "resource_overallocated", "resource_allocation", p001_backend_allocation, "planned_hours_per_week=30; total_allocation_percent=120", "actual_hours_per_week=35; total_allocation_percent=145", dt(2026, 6, 13, 12, 0), "Backend lead оказался распределен между P001 и P002 сверх доступной емкости."),
        ("P002", "milestone_shifted", "milestone", find_id(milestones, project_id="P002", name="Интеграция с процессингом"), "planned_end_date=2026-06-05", "planned_end_date=2026-06-23", dt(2026, 6, 6, 14, 15), "Процессинг перенес окно подключения real-time stream."),
        ("P002", "risk_score_increased", "risk", find_id(risks, project_id="P002", risk_type="Integration"), "probability=3; impact=4", "probability=5; impact=4", dt(2026, 6, 7, 9, 40), "Расчетный score интеграционного риска вырос с 12 до 20 после отмены первого end-to-end теста."),
        ("P002", "communication_delayed", "communication", find_id(communications, project_id="P002", to_team="Card Processing"), "status=pending", "status=escalated", dt(2026, 6, 8, 17, 0), "Card Processing не подтвердил новое окно подключения."),
        ("P004", "task_blocked", "task", task_id(tasks_by_project, "P004", 1), "status=In Progress", "status=Blocked; blocker_reason=vendor certificates missing", dt(2026, 6, 6, 11, 30), "Сертификаты СБП не выданы вендором, тесты gateway заблокированы."),
        ("P004", "budget_forecast_changed", "budget", find_id(budgets, project_id="P004"), "forecast_total_spent=39000000", "forecast_total_spent=43000000", dt(2026, 6, 14, 16, 10), "Прогноз бюджета gateway вырос из-за дополнительных vendor-сертификатов."),
        ("P004", "resource_overallocated", "resource_allocation", find_id(allocations, project_id="P004", resource_id="R004"), "actual_hours_per_week=20", "actual_hours_per_week=26; total_allocation_percent=135", dt(2026, 6, 15, 12, 25), "Backend-разработчик Core Platform одновременно закрывает P001 и P004."),
    ]

    rows = []
    for idx, spec in enumerate(event_specs, start=1):
        (
            project_id,
            event_type,
            entity_type,
            entity_id,
            old_value,
            new_value,
            event_time,
            description,
        ) = spec
        rows.append(
            {
                "id": f"EV{idx:03d}",
                "project_id": project_id,
                "event_type": event_type,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "old_value": old_value,
                "new_value": new_value,
                "event_time": iso_dt(event_time),
                "description": description,
            }
        )
    return rows


def write_csv(filename: str, rows: list[dict[str, Any]], columns: list[str]) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(DATA_DIR / filename, index=False)


def remove_stale_derived_files() -> None:
    for filename in ["metrics_snapshots.csv"]:
        path = DATA_DIR / filename
        if path.exists():
            path.unlink()


def validate_dataset(
    projects: list[dict[str, Any]],
    tasks: list[dict[str, Any]],
    events: list[dict[str, Any]],
    resources: list[dict[str, Any]],
    allocations: list[dict[str, Any]],
    budgets: list[dict[str, Any]],
    milestones: list[dict[str, Any]],
    risks: list[dict[str, Any]],
    communications: list[dict[str, Any]],
) -> None:
    assert 100 <= len(tasks) <= 150, f"Expected 100-150 tasks, got {len(tasks)}"
    assert sum(1 for project in projects if project["status"] == "red") >= 2
    assert any(task["is_blocked"] for task in tasks)
    assert any(
        task["status"] != "Done" and parse_date(task["planned_due_date"]) < LATEST_SNAPSHOT_DATE
        for task in tasks
    )

    availability = {resource["id"]: resource["available_hours_per_week"] for resource in resources}
    total_actual_by_resource: dict[str, float] = defaultdict(float)
    for allocation in allocations:
        total_actual_by_resource[allocation["resource_id"]] += allocation["actual_hours_per_week"]
    max_total_allocation = max(
        total_actual_by_resource[resource_id] / availability[resource_id] * 100
        for resource_id in total_actual_by_resource
    )
    assert 130 <= max_total_allocation <= 150, max_total_allocation

    required_event_types = {
        "milestone_shifted",
        "task_blocked",
        "budget_forecast_changed",
        "risk_score_increased",
        "communication_delayed",
        "resource_overallocated",
    }
    assert required_event_types <= {event["event_type"] for event in events}

    negative_roi_projects = [
        budget
        for budget in budgets
        if (budget["expected_economic_effect"] - budget["forecast_total_spent"]) / budget["forecast_total_spent"] < 0
    ]
    assert negative_roi_projects, "Expected at least one project with negative ROI"
    assert any(milestone["project_id"] == "P001" and milestone["status"] == "Delayed" for milestone in milestones)
    assert any(risk["project_id"] == "P001" and risk["probability"] * risk["impact"] >= 15 for risk in risks)
    assert any(
        communication["project_id"] == "P001" and communication["status"] == "escalated"
        for communication in communications
    )


def main() -> None:
    projects = make_projects()
    resources = make_resources()
    allocations = make_resource_allocations(resources)
    tasks = make_tasks(resources)
    tasks_by_project = task_lookup(tasks)
    milestones = make_milestones()
    budgets = make_budgets()
    risks = make_risks(tasks_by_project)
    communications = make_communications(tasks_by_project)
    events = make_project_events(tasks_by_project, milestones, budgets, risks, communications, allocations)

    validate_dataset(projects, tasks, events, resources, allocations, budgets, milestones, risks, communications)

    write_csv("projects.csv", projects, PROJECT_COLUMNS)
    write_csv("tasks.csv", tasks, TASK_COLUMNS)
    write_csv("milestones.csv", milestones, MILESTONE_COLUMNS)
    write_csv("budgets.csv", budgets, BUDGET_COLUMNS)
    write_csv("risks.csv", risks, RISK_COLUMNS)
    write_csv("communications.csv", communications, COMMUNICATION_COLUMNS)
    write_csv("resources.csv", resources, RESOURCE_COLUMNS)
    write_csv("resource_allocations.csv", allocations, RESOURCE_ALLOCATION_COLUMNS)
    write_csv("project_events.csv", events, EVENT_COLUMNS)
    remove_stale_derived_files()

    print(f"Generated demo dataset in {DATA_DIR.resolve()}")
    print(f"Projects: {len(projects)}")
    print(f"Tasks: {len(tasks)}")
    print(f"Events: {len(events)}")


if __name__ == "__main__":
    main()
