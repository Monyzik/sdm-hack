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

TASK_HISTORY_COLUMNS = [
    "id",
    "project_id",
    "task_id",
    "changed_at",
    "field_changed",
    "old_value",
    "new_value",
    "changed_by",
    "source_system",
]

TASK_COMMENT_COLUMNS = [
    "id",
    "project_id",
    "task_id",
    "author_id",
    "author_name",
    "created_at",
    "channel",
    "text",
    "mentions_count",
    "source_system",
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

TASK_DEPENDENCY_COLUMNS = [
    "id",
    "project_id",
    "task_id",
    "depends_on_task_id",
    "dependency_type",
    "is_critical_path",
    "lag_days",
    "reason",
]

BUDGET_ITEM_COLUMNS = [
    "id",
    "project_id",
    "budget_id",
    "category",
    "item_name",
    "planned_amount",
    "actual_amount",
    "forecast_amount",
    "owner_team",
]

COMMUNICATION_MESSAGE_COLUMNS = [
    "id",
    "project_id",
    "communication_id",
    "message_time",
    "sender_team",
    "recipient_team",
    "channel",
    "message_type",
    "status",
    "summary",
    "linked_task_id",
    "is_escalation",
]

DEPENDENCY_COLUMNS = [
    "id",
    "project_id",
    "dependency_type",
    "depends_on",
    "owner_team",
    "expected_date",
    "status",
    "criticality",
    "linked_task_id",
]

DECISION_COLUMNS = [
    "id",
    "project_id",
    "decision_date",
    "decision_type",
    "description",
    "decision_owner",
    "status",
    "linked_milestone_id",
]

CHANGE_REQUEST_COLUMNS = [
    "id",
    "project_id",
    "request_date",
    "requested_by",
    "change_type",
    "description",
    "impact_scope",
    "impact_budget",
    "impact_days",
    "status",
]

TASK_DEPENDENCY_COLUMNS = [
    "id",
    "project_id",
    "task_id",
    "depends_on_task_id",
    "dependency_type",
    "is_critical_path",
    "lag_days",
    "reason",
]

BUDGET_ITEM_COLUMNS = [
    "id",
    "project_id",
    "budget_id",
    "category",
    "item_name",
    "planned_amount",
    "actual_amount",
    "forecast_amount",
    "owner_team",
]

COMMUNICATION_MESSAGE_COLUMNS = [
    "id",
    "project_id",
    "communication_id",
    "message_time",
    "sender_team",
    "recipient_team",
    "channel",
    "message_type",
    "status",
    "summary",
    "linked_task_id",
    "is_escalation",
]

DEPENDENCY_COLUMNS = [
    "id",
    "project_id",
    "dependency_type",
    "depends_on",
    "owner_team",
    "expected_date",
    "status",
    "criticality",
    "linked_task_id",
]

DECISION_COLUMNS = [
    "id",
    "project_id",
    "decision_date",
    "decision_type",
    "description",
    "decision_owner",
    "status",
    "linked_milestone_id",
]

CHANGE_REQUEST_COLUMNS = [
    "id",
    "project_id",
    "request_date",
    "requested_by",
    "change_type",
    "description",
    "impact_scope",
    "impact_budget",
    "impact_days",
    "status",
]


def iso(value: date | None) -> str:
    return value.isoformat() if value else ""


def iso_dt(value: datetime | None) -> str:
    return value.isoformat(sep=" ", timespec="seconds") if value else ""


def d(year: int, month: int, day: int) -> date:
    return date(year, month, day)


def dt(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(d(year, month, day), time(hour, minute))


class DatasetValidationError(ValueError):
    pass


def ensure(condition: bool, message: str) -> None:
    if not condition:
        raise DatasetValidationError(message)


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
        {"id": "R001", "full_name": "Алексей Соколов", "role": "Project Manager", "team": "PMO",
         "available_hours_per_week": 40, "hour_rate": 4200, "seniority": "senior"},
        {"id": "R002", "full_name": "Мария Кузнецова", "role": "Business Analyst", "team": "Business Analysis",
         "available_hours_per_week": 40, "hour_rate": 3600, "seniority": "middle+"},
        {"id": "R003", "full_name": "Дмитрий Волков", "role": "Backend Developer", "team": "Core Platform",
         "available_hours_per_week": 40, "hour_rate": 4800, "seniority": "senior"},
        {"id": "R004", "full_name": "Илья Смирнов", "role": "Backend Developer", "team": "Core Platform",
         "available_hours_per_week": 40, "hour_rate": 4300, "seniority": "middle+"},
        {"id": "R005", "full_name": "Ольга Иванова", "role": "Backend Developer", "team": "Payments",
         "available_hours_per_week": 40, "hour_rate": 4100, "seniority": "middle"},
        {"id": "R006", "full_name": "Павел Никитин", "role": "Data Engineer", "team": "Data Platform",
         "available_hours_per_week": 40, "hour_rate": 4500, "seniority": "senior"},
        {"id": "R007", "full_name": "Наталья Федорова", "role": "Data Scientist", "team": "Risk Models",
         "available_hours_per_week": 40, "hour_rate": 4700, "seniority": "senior"},
        {"id": "R008", "full_name": "Сергей Лебедев", "role": "ML Engineer", "team": "Risk Models",
         "available_hours_per_week": 40, "hour_rate": 4600, "seniority": "middle+"},
        {"id": "R009", "full_name": "Анна Попова", "role": "QA Engineer", "team": "Quality",
         "available_hours_per_week": 40, "hour_rate": 3100, "seniority": "middle"},
        {"id": "R010", "full_name": "Роман Егоров", "role": "DevOps Engineer", "team": "Platform",
         "available_hours_per_week": 40, "hour_rate": 4400, "seniority": "senior"},
        {"id": "R011", "full_name": "Виктория Павлова", "role": "Security Engineer", "team": "Security",
         "available_hours_per_week": 32, "hour_rate": 5000, "seniority": "senior"},
        {"id": "R012", "full_name": "Георгий Орлов", "role": "Solution Architect", "team": "Enterprise Architecture",
         "available_hours_per_week": 32, "hour_rate": 5200, "seniority": "principal"},
        {"id": "R013", "full_name": "Екатерина Васильева", "role": "Frontend Developer", "team": "Mobile Web",
         "available_hours_per_week": 40, "hour_rate": 3900, "seniority": "middle+"},
        {"id": "R014", "full_name": "Кирилл Морозов", "role": "Android Developer", "team": "Mobile",
         "available_hours_per_week": 40, "hour_rate": 4200, "seniority": "middle+"},
        {"id": "R015", "full_name": "Дарья Захарова", "role": "iOS Developer", "team": "Mobile",
         "available_hours_per_week": 40, "hour_rate": 4300, "seniority": "middle+"},
        {"id": "R016", "full_name": "Михаил Зайцев", "role": "API Analyst", "team": "Integration",
         "available_hours_per_week": 40, "hour_rate": 3500, "seniority": "middle"},
        {"id": "R017", "full_name": "Татьяна Белова", "role": "QA Automation Engineer", "team": "Quality",
         "available_hours_per_week": 40, "hour_rate": 3600, "seniority": "middle+"},
        {"id": "R018", "full_name": "Артур Комаров", "role": "Product Owner", "team": "Digital Bank",
         "available_hours_per_week": 32, "hour_rate": 4700, "seniority": "senior"},
        {"id": "R019", "full_name": "Софья Андреева", "role": "UX Researcher", "team": "CX",
         "available_hours_per_week": 32, "hour_rate": 3300, "seniority": "middle"},
        {"id": "R020", "full_name": "Никита Новиков", "role": "Backend Developer", "team": "CRM Platform",
         "available_hours_per_week": 40, "hour_rate": 4000, "seniority": "middle"},
        {"id": "R021", "full_name": "Полина Соколова", "role": "Data Analyst", "team": "CRM Analytics",
         "available_hours_per_week": 40, "hour_rate": 3400, "seniority": "middle"},
        {"id": "R022", "full_name": "Евгений Фомин", "role": "Integration Engineer", "team": "Payments",
         "available_hours_per_week": 40, "hour_rate": 4300, "seniority": "senior"},
        {"id": "R023", "full_name": "Лариса Сергеева", "role": "Compliance Officer", "team": "Compliance",
         "available_hours_per_week": 32, "hour_rate": 3900, "seniority": "senior"},
        {"id": "R024", "full_name": "Владислав Крылов", "role": "SRE", "team": "Platform",
         "available_hours_per_week": 40, "hour_rate": 4500, "seniority": "middle+"},
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
        blocked_count = int(config["blocked"])
        overdue_open_count = int(config["overdue_open"])
        done_count = int(config["done"])
        for number in range(1, config["count"] + 1):
            assignee_id = random.choice(resource_ids)
            assignee = resource_by_id[assignee_id]

            is_blocked = number <= blocked_count
            is_overdue_open = blocked_count < number <= blocked_count + overdue_open_count
            is_done = (
                    blocked_count + overdue_open_count
                    < number
                    <= blocked_count + overdue_open_count + done_count
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
            ("Discovery и требования", d(2026, 5, 4), d(2026, 5, 15), d(2026, 5, 4), d(2026, 5, 16), "Done",
             "Business Analysis", 1),
            ("Модель и витрина признаков", d(2026, 5, 18), d(2026, 6, 5), d(2026, 5, 19), d(2026, 6, 8), "Done",
             "Risk Models", 3),
            ("Security review и интеграция", d(2026, 6, 8), d(2026, 6, 12), d(2026, 6, 9), None, "Delayed", "Security",
             14),
            ("Пилот в кредитном конвейере", d(2026, 6, 15), d(2026, 6, 30), None, None, "At Risk", "Core Platform", 14),
        ],
        "P002": [
            ("Архитектура streaming-контура", d(2026, 4, 27), d(2026, 5, 15), d(2026, 4, 28), d(2026, 5, 17), "Done",
             "Enterprise Architecture", 2),
            ("Интеграция с процессингом", d(2026, 5, 18), d(2026, 6, 5), d(2026, 5, 20), None, "Delayed", "Payments",
             18),
            ("Модель fraud decisioning", d(2026, 5, 25), d(2026, 6, 19), d(2026, 5, 27), None, "At Risk", "Risk Models",
             10),
            ("UAT и промышленный контур", d(2026, 6, 22), d(2026, 7, 10), None, None, "Planned", "Platform", 0),
        ],
        "P003": [
            ("UX и дизайн-система", d(2026, 5, 6), d(2026, 5, 22), d(2026, 5, 6), d(2026, 5, 21), "Done", "CX", 0),
            ("Разработка клиентских сценариев", d(2026, 5, 25), d(2026, 6, 12), d(2026, 5, 25), d(2026, 6, 12), "Done",
             "Mobile", 0),
            ("Регрессия и аналитика", d(2026, 6, 15), d(2026, 6, 26), d(2026, 6, 15), None, "In Progress", "Quality",
             0),
            ("Pilot release", d(2026, 6, 29), d(2026, 7, 3), None, None, "Planned", "Digital Bank", 0),
        ],
        "P004": [
            ("API contract и архитектура", d(2026, 5, 11), d(2026, 5, 29), d(2026, 5, 12), d(2026, 6, 1), "Done",
             "Integration", 3),
            ("СБП и acquiring adapters", d(2026, 6, 1), d(2026, 6, 19), d(2026, 6, 3), None, "At Risk", "Payments", 7),
            ("PCI DSS и безопасность", d(2026, 6, 15), d(2026, 6, 26), d(2026, 6, 17), None, "At Risk", "Security", 5),
            ("Нагрузочное тестирование", d(2026, 6, 29), d(2026, 7, 17), None, None, "Planned", "Platform", 0),
        ],
        "P005": [
            ("Data discovery", d(2026, 5, 13), d(2026, 5, 29), d(2026, 5, 13), d(2026, 5, 30), "Done", "CRM Analytics",
             1),
            ("Golden record", d(2026, 6, 1), d(2026, 6, 19), d(2026, 6, 1), d(2026, 6, 18), "Done", "Data Platform", 0),
            ("API профиля 360", d(2026, 6, 22), d(2026, 7, 10), None, None, "Planned", "CRM Platform", 0),
            ("Пилот с продажами", d(2026, 7, 13), d(2026, 7, 24), None, None, "Planned", "Sales", 0),
        ],
    }

    rows = []
    idx = 1
    for project_id, milestones in milestone_templates.items():
        for name, planned_start, planned_end, actual_start, actual_end, status, team, _delay_days in milestones:
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
        {"id": "B001", "project_id": "P001", "planned_budget": 48_000_000, "actual_spent": 41_500_000,
         "forecast_total_spent": 62_000_000, "expected_economic_effect": 57_000_000, "cost_of_delay_per_day": 1_250_000,
         "currency": "RUB"},
        {"id": "B002", "project_id": "P002", "planned_budget": 72_000_000, "actual_spent": 64_000_000,
         "forecast_total_spent": 88_000_000, "expected_economic_effect": 112_000_000,
         "cost_of_delay_per_day": 1_800_000, "currency": "RUB"},
        {"id": "B003", "project_id": "P003", "planned_budget": 42_000_000, "actual_spent": 29_500_000,
         "forecast_total_spent": 40_000_000, "expected_economic_effect": 76_000_000, "cost_of_delay_per_day": 650_000,
         "currency": "RUB"},
        {"id": "B004", "project_id": "P004", "planned_budget": 38_000_000, "actual_spent": 31_000_000,
         "forecast_total_spent": 43_000_000, "expected_economic_effect": 59_000_000, "cost_of_delay_per_day": 950_000,
         "currency": "RUB"},
        {"id": "B005", "project_id": "P005", "planned_budget": 34_000_000, "actual_spent": 22_500_000,
         "forecast_total_spent": 33_000_000, "expected_economic_effect": 68_000_000, "cost_of_delay_per_day": 520_000,
         "currency": "RUB"},
    ]


def make_risks(tasks_by_project: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    risk_specs = [
        ("P001", "Security", "Security может не согласовать обработку персональных данных для скорингового API.", 5, 5,
         "Виктория Павлова", "Вынести модель угроз на risk committee и подготовить маскирование полей.", "escalated",
         task_id(tasks_by_project, "P001", 1), d(2026, 6, 10)),
        ("P001", "Resource",
         "Backend lead распределен между двумя critical-проектами и работает выше доступной емкости.", 4, 5,
         "Елена Морозова", "Перенести часть задач на второго backend и зафиксировать WIP limit.", "active",
         task_id(tasks_by_project, "P001", 6), d(2026, 5, 29)),
        ("P001", "Budget", "Прогноз бюджета превышает план из-за доработок Security и интеграций.", 4, 4,
         "Елена Морозова", "Согласовать scope cut и отдельный резерв на compliance-доработки.", "active",
         task_id(tasks_by_project, "P001", 9), d(2026, 6, 12)),
        ("P001", "Dependency", "DWH не подтвердил стабильный SLA на витрину признаков МСБ.", 3, 5, "Павел Никитин",
         "Согласовать fallback extract и ежедневный контроль качества данных.", "mitigating",
         task_id(tasks_by_project, "P001", 2), d(2026, 6, 5)),
        ("P001", "Data Quality", "Исторические признаки по части заявок МСБ неполные.", 3, 4, "Наталья Федорова",
         "Запустить сверку с кредитным конвейером и исключить неполные сэмплы.", "active",
         task_id(tasks_by_project, "P001", 4), d(2026, 5, 29)),
        ("P002", "Performance", "Latency real-time decisioning превышает целевой лимит 120 мс на peak load.", 4, 5,
         "Сергей Лебедев", "Оптимизировать feature lookup и включить circuit breaker.", "escalated",
         task_id(tasks_by_project, "P002", 6), d(2026, 5, 29)),
        ("P002", "Integration", "Процессинг карт переносит окно подключения и блокирует end-to-end тесты.", 5, 4,
         "Евгений Фомин", "Эскалировать слот подключения и подготовить stub-контур.", "escalated",
         task_id(tasks_by_project, "P002", 1), d(2026, 6, 3)),
        ("P002", "Compliance", "Нужно доказать контролируемый уровень false positive для операций клиентов.", 4, 4,
         "Лариса Сергеева", "Подготовить отчетность по тестовой выборке и критерии ручного разбора.", "active",
         task_id(tasks_by_project, "P002", 8), d(2026, 6, 5)),
        ("P002", "Security", "Дополнительная модель угроз задерживает доступ к продуктивным событиям.", 3, 5,
         "Виктория Павлова", "Провести threat modeling workshop и согласовать read-only доступ.", "active",
         task_id(tasks_by_project, "P002", 2), d(2026, 6, 9)),
        ("P002", "Resource", "ML engineer перегружен задачами расследований и performance tuning.", 3, 4,
         "Андрей Романов", "Выделить отдельный слот на оптимизацию модели.", "mitigating",
         task_id(tasks_by_project, "P002", 7), d(2026, 5, 29)),
        ("P003", "Release", "Ревью в app store может занять больше стандартного окна.", 2, 3, "Артур Комаров",
         "Отправить build заранее и подготовить phased rollout.", "active", task_id(tasks_by_project, "P003", 10),
         d(2026, 6, 12)),
        ("P003", "UX", "Пользователи могут хуже проходить обновленный onboarding без подсказок.", 2, 3,
         "Софья Андреева", "Провести дополнительный usability test на контрольной группе.", "mitigating",
         task_id(tasks_by_project, "P003", 1), d(2026, 5, 29)),
        ("P003", "Dependency", "Biometric login зависит от смежного релиза авторизации.", 2, 4, "Екатерина Васильева",
         "Оставить feature toggle и fallback password flow.", "active", task_id(tasks_by_project, "P003", 9),
         d(2026, 6, 5)),
        ("P004", "Vendor", "Вендор СБП задерживает тестовые сертификаты для gateway.", 4, 4, "Сергей Ковалев",
         "Эскалация через vendor manager и подготовка sandbox-mock.", "active", task_id(tasks_by_project, "P004", 1),
         d(2026, 6, 5)),
        ("P004", "Security", "PCI DSS checklist требует дополнительного аудита хранения токенов.", 3, 5,
         "Виктория Павлова", "Разделить scope аудита и вынести спорные пункты на CAB.", "active",
         task_id(tasks_by_project, "P004", 2), d(2026, 6, 12)),
        ("P004", "Performance", "Gateway может не выдержать пиковые платежные окна без SRE-тюнинга.", 3, 4,
         "Владислав Крылов", "Добавить synthetic load и автоалерты по latency.", "mitigating",
         task_id(tasks_by_project, "P004", 8), d(2026, 6, 12)),
        ("P004", "Budget", "Дополнительные vendor-сертификаты увеличивают forecast_total_spent.", 3, 3,
         "Сергей Ковалев", "Зафиксировать лимит закупки и убрать часть non-critical scope.", "active",
         task_id(tasks_by_project, "P004", 3), d(2026, 6, 12)),
        ("P005", "Data Quality", "Дубликаты клиентов в CRM и DWH расходятся по ключевым атрибутам.", 3, 4,
         "Полина Соколова", "Ввести confidence score для golden record и ручную валидацию топ-сегментов.", "active",
         task_id(tasks_by_project, "P005", 7), d(2026, 5, 29)),
        ("P005", "Adoption", "Команды продаж могут продолжить использовать старые карточки клиентов.", 2, 3,
         "Ольга Беляева", "Провести пилот с двумя регионами и собрать обратную связь.", "mitigating",
         task_id(tasks_by_project, "P005", 5), d(2026, 6, 5)),
        ("P005", "Compliance", "Нужна проверка ролей доступа к чувствительным клиентским атрибутам.", 2, 4,
         "Лариса Сергеева", "Согласовать матрицу ролей до начала пилота.", "active",
         task_id(tasks_by_project, "P005", 9), d(2026, 6, 12)),
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
            _active_from,
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
        ("P001", "Risk Models", "Security", "Согласование обработки ПДн для скорингового API", "Teams", d(2026, 6, 4),
         d(2026, 6, 5), "escalated", "critical", task_id(tasks_by_project, "P001", 1)),
        ("P001", "Data Platform", "DWH", "SLA витрины признаков МСБ", "Email", d(2026, 6, 6), d(2026, 6, 7), "delayed",
         "high", task_id(tasks_by_project, "P001", 2)),
        ("P001", "Core Platform", "Credit Conveyor", "Окно интеграционного тестирования скоринга", "Jira",
         d(2026, 6, 12), d(2026, 6, 14), "delayed", "high", task_id(tasks_by_project, "P001", 5)),
        ("P001", "PMO", "Business Owner", "Решение по scope cut после роста бюджета", "Email", d(2026, 6, 17),
         d(2026, 6, 18), "pending", "high", task_id(tasks_by_project, "P001", 9)),
        ("P001", "Risk Models", "Data Quality", "Сверка неполных признаков по заявкам МСБ", "Confluence",
         d(2026, 6, 13), d(2026, 6, 17), "responded", "medium", task_id(tasks_by_project, "P001", 4)),
        ("P002", "Fraud Platform", "Card Processing", "Окно подключения transaction stream", "Email", d(2026, 6, 1),
         d(2026, 6, 3), "escalated", "critical", task_id(tasks_by_project, "P002", 1)),
        ("P002", "Risk Models", "Compliance", "Критерии false positive review", "Teams", d(2026, 6, 7), d(2026, 6, 10),
         "delayed", "high", task_id(tasks_by_project, "P002", 8)),
        ("P002", "Platform", "SRE", "CPU profile feature lookup", "Jira", d(2026, 6, 13), d(2026, 6, 14), "responded",
         "medium", task_id(tasks_by_project, "P002", 6)),
        ("P002", "Security", "Fraud Platform", "Threat model для real-time событий", "Confluence", d(2026, 6, 11),
         d(2026, 6, 13), "pending", "high", task_id(tasks_by_project, "P002", 2)),
        ("P002", "PMO", "Business Owner", "Решение по запуску пилота без части правил", "Email", d(2026, 6, 16),
         d(2026, 6, 18), "pending", "high", task_id(tasks_by_project, "P002", 3)),
        ("P003", "Mobile", "CX", "Финальный approve onboarding", "Teams", d(2026, 6, 15), d(2026, 6, 16), "responded",
         "medium", task_id(tasks_by_project, "P003", 1)),
        ("P003", "Mobile", "Analytics", "Событийная схема для нового профиля", "Jira", d(2026, 6, 14), d(2026, 6, 17),
         "responded", "medium", task_id(tasks_by_project, "P003", 5)),
        ("P003", "Digital Bank", "Release Management", "Слот pilot release", "Email", d(2026, 6, 18), d(2026, 6, 19),
         "pending", "medium", task_id(tasks_by_project, "P003", 10)),
        ("P003", "Quality", "Mobile", "Регрессионный прогон critical flows", "Jira", d(2026, 6, 17), d(2026, 6, 18),
         "responded", "medium", task_id(tasks_by_project, "P003", 8)),
        ("P004", "Payments", "SBP Vendor", "Тестовые сертификаты СБП", "Email", d(2026, 6, 6), d(2026, 6, 8), "delayed",
         "critical", task_id(tasks_by_project, "P004", 1)),
        ("P004", "Security", "Payments", "PCI DSS token storage review", "Confluence", d(2026, 6, 11), d(2026, 6, 13),
         "delayed", "high", task_id(tasks_by_project, "P004", 2)),
        ("P004", "Platform", "SRE", "Нагрузочное окно gateway", "Teams", d(2026, 6, 16), d(2026, 6, 17), "responded",
         "medium", task_id(tasks_by_project, "P004", 8)),
        ("P004", "PMO", "Business Owner", "Перенос части merchant-сценариев", "Email", d(2026, 6, 18), d(2026, 6, 19),
         "pending", "medium", task_id(tasks_by_project, "P004", 3)),
        ("P005", "CRM Analytics", "Data Owners", "Правила дедупликации контактов", "Teams", d(2026, 6, 12),
         d(2026, 6, 14), "responded", "medium", task_id(tasks_by_project, "P005", 2)),
        ("P005", "CRM Platform", "Compliance", "Матрица доступа к профилю 360", "Confluence", d(2026, 6, 13),
         d(2026, 6, 17), "pending", "medium", task_id(tasks_by_project, "P005", 9)),
        ("P005", "Sales", "CRM Platform", "Сценарии пилота для регионов", "Email", d(2026, 6, 18), d(2026, 6, 19),
         "pending", "low", task_id(tasks_by_project, "P005", 5)),
        ("P005", "Data Platform", "CRM Analytics", "Сверка golden record после дедупликации", "Jira", d(2026, 6, 16),
         d(2026, 6, 18), "responded", "medium", task_id(tasks_by_project, "P005", 1)),
    ]

    return [row(idx, *spec) for idx, spec in enumerate(specs, start=1)]


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def find_id(rows: list[dict[str, Any]], **conditions: Any) -> str:
    for row in rows:
        if all(row.get(key) == value for key, value in conditions.items()):
            return row["id"]
    raise ValueError(f"Row not found: {conditions}")


def make_task_dependencies(tasks_by_project: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    specs = [
        ("P001", 5, 1, "blocks", True, 1, "Security approval is required before integration and pilot activities."),
        ("P001", 6, 2, "blocks", True, 0, "DWH SLA confirmation is needed before feature validation."),
        ("P001", 9, 4, "requires", False, 2, "Rollback procedure depends on validated model documentation."),
        ("P002", 4, 1, "blocks", True, 1, "Integration testing waits for the processing window."),
        ("P002", 5, 2, "blocks", True, 1, "Feature store tuning depends on threat model approval."),
        ("P002", 6, 4, "blocks", True, 0, "Latency optimization depends on a stable processing adapter."),
        ("P003", 6, 1, "related", False, 1, "Mobile onboarding should align with UX approval."),
        ("P003", 8, 6, "blocks", False, 0, "Regression package depends on the stabilized client flow."),
        ("P004", 4, 1, "blocks", True, 1, "Payment routing depends on vendor certificate delivery."),
        ("P004", 8, 2, "blocks", True, 2, "Load testing depends on a completed PCI DSS checklist."),
        ("P005", 4, 1, "blocks", True, 1, "Golden record mapping depends on deduplication rules."),
        ("P005", 8, 4, "related", False, 0, "Cross-sell segments depend on stable profile quality."),
    ]

    rows = []
    for idx, (project_id, task_number, depends_on_number, dependency_type, is_critical, lag_days, reason) in enumerate(
            specs, start=1):
        rows.append(
            {
                "id": f"TD{idx:03d}",
                "project_id": project_id,
                "task_id": task_id(tasks_by_project, project_id, task_number),
                "depends_on_task_id": task_id(tasks_by_project, project_id, depends_on_number),
                "dependency_type": dependency_type,
                "is_critical_path": is_critical,
                "lag_days": lag_days,
                "reason": reason,
            }
        )
    return rows


def make_budget_line_items(budgets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    budget_id = {row["project_id"]: row["id"] for row in budgets}
    specs = [
        ("P001", "Engineering", "Model development", "Risk Models", 10_000_000, 8_500_000, 11_000_000),
        ("P001", "Integration", "Core Platform integration", "Core Platform", 14_000_000, 12_000_000, 18_000_000),
        ("P001", "Compliance", "Security and approvals", "Security", 16_000_000, 13_000_000, 20_000_000),
        ("P001", "Testing", "Pilot rollout", "PMO", 8_000_000, 8_000_000, 13_000_000),
        ("P002", "Engineering", "Streaming core", "Fraud Platform", 20_000_000, 18_000_000, 24_000_000),
        ("P002", "Integration", "Card processing adapter", "Payments", 18_000_000, 16_000_000, 20_000_000),
        ("P002", "Modeling", "Feature store and scoring", "Risk Models", 20_000_000, 14_000_000, 22_000_000),
        ("P002", "Compliance", "UAT and sign-off", "Compliance", 14_000_000, 16_000_000, 22_000_000),
        ("P003", "UX", "Mobile UX and design", "Mobile", 10_000_000, 8_000_000, 9_000_000),
        ("P003", "Product", "Client scenarios", "Mobile", 10_000_000, 7_000_000, 8_000_000),
        ("P003", "Analytics", "Event tracking", "CRM Analytics", 12_000_000, 9_000_000, 12_000_000),
        ("P003", "Release", "Stabilization", "Quality", 10_000_000, 5_500_000, 11_000_000),
        ("P004", "Engineering", "Gateway core", "Payments", 10_000_000, 9_000_000, 11_000_000),
        ("P004", "Integration", "SBP and acquiring adapters", "Payments", 12_000_000, 8_000_000, 13_000_000),
        ("P004", "Security", "PCI DSS workstream", "Security", 8_000_000, 7_000_000, 9_000_000),
        ("P004", "Observability", "Load testing and monitoring", "Platform", 8_000_000, 7_000_000, 10_000_000),
        ("P005", "Data Quality", "Golden record and dedupe", "CRM Analytics", 9_000_000, 6_000_000, 8_000_000),
        ("P005", "Engineering", "CRM profile API", "CRM Platform", 9_000_000, 6_000_000, 8_000_000),
        ("P005", "Governance", "Data quality controls", "Data Platform", 8_000_000, 5_000_000, 8_000_000),
        ("P005", "Rollout", "Pilot rollout", "Sales", 8_000_000, 5_500_000, 9_000_000),
    ]

    rows = []
    for idx, (project_id, category, item_name, owner_team, planned_amount, actual_amount, forecast_amount) in enumerate(specs, start=1):
        rows.append(
            {
                "id": f"BI{idx:03d}",
                "project_id": project_id,
                "budget_id": budget_id[project_id],
                "category": category,
                "item_name": item_name,
                "planned_amount": planned_amount,
                "actual_amount": actual_amount,
                "forecast_amount": forecast_amount,
                "owner_team": owner_team,
            }
        )
    return rows


def make_communication_messages(communications: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    next_id = 1
    for communication in communications:
        project_id = communication["project_id"]
        comm_id = communication["id"]
        topic = communication["topic"]
        channel = communication["channel"]
        from_team = communication["from_team"]
        to_team = communication["to_team"]
        last_date = parse_date(communication["last_message_date"])
        response_date = parse_date(communication["expected_response_date"])
        linked_task_id = communication["linked_task_id"]
        ensure(last_date is not None, f"Communication {comm_id} has no last_message_date")
        ensure(response_date is not None, f"Communication {comm_id} has no expected_response_date")

        rows.append(
            {
                "id": f"CM{next_id:03d}",
                "project_id": project_id,
                "communication_id": comm_id,
                "message_time": iso_dt(dt(last_date.year, last_date.month, last_date.day, 9, 15)),
                "sender_team": from_team,
                "recipient_team": to_team,
                "channel": channel,
                "message_type": "request",
                "status": "sent",
                "summary": f"Первичный запрос по теме: {topic}",
                "linked_task_id": linked_task_id,
                "is_escalation": False,
            }
        )
        next_id += 1

        if communication["status"] == "responded":
            sender_team, recipient_team, message_type, status, summary, escalation = (
                to_team,
                from_team,
                "response",
                "replied",
                f"Ответ по теме: {topic}",
                False,
            )
        elif communication["status"] == "escalated":
            sender_team, recipient_team, message_type, status, summary, escalation = (
                "PMO",
                to_team,
                "escalation",
                "escalated",
                f"Эскалация по теме: {topic}",
                True,
            )
        elif communication["status"] == "delayed":
            sender_team, recipient_team, message_type, status, summary, escalation = (
                from_team,
                to_team,
                "reminder",
                "waiting",
                f"Напоминание по теме: {topic}",
                False,
            )
        else:
            sender_team, recipient_team, message_type, status, summary, escalation = (
                from_team,
                to_team,
                "follow_up",
                "waiting",
                f"Фоллоу-ап по теме: {topic}",
                False,
            )

        rows.append(
            {
                "id": f"CM{next_id:03d}",
                "project_id": project_id,
                "communication_id": comm_id,
                "message_time": iso_dt(dt(response_date.year, response_date.month, response_date.day, 15, 30)),
                "sender_team": sender_team,
                "recipient_team": recipient_team,
                "channel": channel,
                "message_type": message_type,
                "status": status,
                "summary": summary,
                "linked_task_id": linked_task_id,
                "is_escalation": escalation,
            }
        )
        next_id += 1

    return rows


def make_task_history(tasks_by_project: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    specs = [
        ("P001", 1, dt(2026, 6, 10, 11, 5), "status", "In Progress", "Blocked", "R011"),
        ("P001", 1, dt(2026, 6, 10, 11, 6), "blocker_reason", "", "Security approval pending", "R011"),
        ("P001", 2, dt(2026, 6, 7, 10, 20), "planned_due_date", "2026-06-03", "2026-06-07", "R006"),
        ("P001", 5, dt(2026, 6, 12, 15, 40), "status", "To Do", "Blocked", "R003"),
        ("P001", 6, dt(2026, 6, 13, 12, 15), "assignee_id", "R004", "R003", "R001"),
        ("P002", 1, dt(2026, 6, 3, 14, 10), "status", "In Progress", "Blocked", "R022"),
        ("P002", 4, dt(2026, 6, 6, 16, 30), "planned_due_date", "2026-06-05", "2026-06-23", "R001"),
        ("P002", 6, dt(2026, 6, 12, 18, 0), "spent_hours", "46", "72", "R010"),
        ("P003", 8, dt(2026, 6, 18, 10, 20), "planned_due_date", "2026-06-26", "2026-06-30", "R017"),
        ("P003", 10, dt(2026, 6, 18, 16, 5), "status", "To Do", "In Progress", "R018"),
        ("P004", 1, dt(2026, 6, 6, 11, 30), "status", "In Progress", "Blocked", "R022"),
        ("P004", 2, dt(2026, 6, 12, 13, 10), "status", "Review", "Blocked", "R011"),
        ("P004", 8, dt(2026, 6, 15, 12, 25), "assignee_id", "R024", "R004", "R001"),
        ("P005", 2, dt(2026, 6, 14, 9, 50), "status", "In Progress", "Review", "R021"),
        ("P005", 7, dt(2026, 6, 17, 13, 20), "estimated_hours", "32", "48", "R021"),
        ("P005", 9, dt(2026, 6, 18, 11, 0), "status", "To Do", "In Progress", "R023"),
    ]

    rows = []
    for idx, (project_id, task_number, changed_at, field, old_value, new_value, changed_by) in enumerate(specs, start=1):
        rows.append(
            {
                "id": f"TH{idx:03d}",
                "project_id": project_id,
                "task_id": task_id(tasks_by_project, project_id, task_number),
                "changed_at": iso_dt(changed_at),
                "field_changed": field,
                "old_value": old_value,
                "new_value": new_value,
                "changed_by": changed_by,
                "source_system": "tasktracker",
            }
        )
    return rows


def make_task_comments(
    tasks_by_project: dict[str, list[dict[str, Any]]],
    resources: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    resource_name = {resource["id"]: resource["full_name"] for resource in resources}
    specs = [
        ("P001", 1, "R007", dt(2026, 6, 4, 10, 30), "Teams", "@Security нужна дата согласования модели угроз по скоринговому API.", 1),
        ("P001", 1, "R011", dt(2026, 6, 5, 17, 10), "Teams", "Нужны дополнительные материалы по маскированию ПДн, без них approve не дадим.", 0),
        ("P001", 1, "R001", dt(2026, 6, 10, 11, 10), "Jira", "Блокер зафиксирован, выношу вопрос на steering committee.", 0),
        ("P001", 2, "R006", dt(2026, 6, 7, 12, 0), "Email", "DWH пока не подтверждает SLA на витрину признаков, нужен fallback extract.", 0),
        ("P001", 9, "R001", dt(2026, 6, 12, 16, 0), "Jira", "Нужен выбор: scope cut или резерв на compliance-доработки?", 0),
        ("P002", 1, "R022", dt(2026, 6, 3, 15, 20), "Email", "Окно процессинга перенесено, end-to-end тесты не стартуют.", 0),
        ("P002", 6, "R010", dt(2026, 6, 12, 18, 20), "Jira", "Latency выше целевого лимита, feature lookup требует оптимизации.", 0),
        ("P002", 8, "R023", dt(2026, 6, 10, 14, 15), "Teams", "Критерии false positive требуют отдельного отчета для compliance.", 0),
        ("P003", 8, "R017", dt(2026, 6, 18, 10, 35), "Jira", "Регрессия расширена на критические платежные сценарии, релизное окно под риском.", 0),
        ("P003", 10, "R018", dt(2026, 6, 18, 16, 10), "Email", "Ждем подтверждение release slot, вопрос открытый до конца дня.", 0),
        ("P004", 1, "R022", dt(2026, 6, 6, 12, 0), "Email", "Вендор не выдал тестовые сертификаты СБП, gateway-тесты заблокированы.", 0),
        ("P004", 2, "R011", dt(2026, 6, 12, 13, 30), "Confluence", "PCI DSS checklist возвращен на доработку по хранению токенов.", 0),
        ("P004", 8, "R024", dt(2026, 6, 15, 12, 40), "Jira", "Для нагрузочного окна нужен дополнительный backend support.", 0),
        ("P005", 2, "R021", dt(2026, 6, 14, 10, 5), "Teams", "Дедупликация контактов дала спорные пары, нужна ручная проверка топ-сегментов.", 0),
        ("P005", 7, "R021", dt(2026, 6, 17, 13, 30), "Jira", "Оценка выросла из-за дополнительного data quality контроля.", 0),
        ("P005", 9, "R023", dt(2026, 6, 18, 11, 20), "Confluence", "Матрица доступа готовится к compliance review.", 0),
    ]

    rows = []
    for idx, (project_id, task_number, author_id, created_at, channel, text, mentions_count) in enumerate(specs, start=1):
        rows.append(
            {
                "id": f"TC{idx:03d}",
                "project_id": project_id,
                "task_id": task_id(tasks_by_project, project_id, task_number),
                "author_id": author_id,
                "author_name": resource_name[author_id],
                "created_at": iso_dt(created_at),
                "channel": channel,
                "text": text,
                "mentions_count": mentions_count,
                "source_system": "tasktracker",
            }
        )
    return rows


def make_dependencies(tasks_by_project: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    specs = [
        (
            "P001",
            "internal_system",
            "DWH feature mart",
            "Data Platform",
            d(2026, 6, 7),
            "delayed",
            "high",
            task_id(tasks_by_project, "P001", 2),
        ),
        (
            "P001",
            "approval",
            "Security approval",
            "Security",
            d(2026, 6, 5),
            "blocked",
            "critical",
            task_id(tasks_by_project, "P001", 1),
        ),
        (
            "P001",
            "management_decision",
            "Scope cut decision",
            "PMO",
            d(2026, 6, 18),
            "pending",
            "high",
            task_id(tasks_by_project, "P001", 9),
        ),
        (
            "P002",
            "internal_system",
            "Card processing stream",
            "Card Processing",
            d(2026, 6, 3),
            "blocked",
            "critical",
            task_id(tasks_by_project, "P002", 1),
        ),
        (
            "P002",
            "approval",
            "False positive criteria",
            "Compliance",
            d(2026, 6, 10),
            "delayed",
            "high",
            task_id(tasks_by_project, "P002", 8),
        ),
        (
            "P003",
            "release_window",
            "Pilot release slot",
            "Release Management",
            d(2026, 6, 19),
            "pending",
            "medium",
            task_id(tasks_by_project, "P003", 10),
        ),
        (
            "P004",
            "vendor",
            "SBP test certificates",
            "SBP Vendor",
            d(2026, 6, 8),
            "delayed",
            "critical",
            task_id(tasks_by_project, "P004", 1),
        ),
        (
            "P004",
            "approval",
            "PCI DSS token storage review",
            "Security",
            d(2026, 6, 13),
            "delayed",
            "high",
            task_id(tasks_by_project, "P004", 2),
        ),
        (
            "P005",
            "data_owner",
            "CRM duplicate ownership",
            "Data Owners",
            d(2026, 6, 14),
            "responded",
            "medium",
            task_id(tasks_by_project, "P005", 2),
        ),
        (
            "P005",
            "approval",
            "Profile 360 access matrix",
            "Compliance",
            d(2026, 6, 17),
            "pending",
            "medium",
            task_id(tasks_by_project, "P005", 9),
        ),
    ]

    rows = []
    for idx, (project_id, dependency_type, depends_on, owner_team, expected_date, status, criticality, linked_task_id) in enumerate(
        specs,
        start=1,
    ):
        rows.append(
            {
                "id": f"D{idx:03d}",
                "project_id": project_id,
                "dependency_type": dependency_type,
                "depends_on": depends_on,
                "owner_team": owner_team,
                "expected_date": iso(expected_date),
                "status": status,
                "criticality": criticality,
                "linked_task_id": linked_task_id,
            }
        )
    return rows


def make_decisions(milestones: list[dict[str, Any]]) -> list[dict[str, Any]]:
    specs = [
        (
            "P001",
            d(2026, 6, 12),
            "scope_change",
            "Перенести часть интеграции в post-pilot, чтобы разблокировать Security review.",
            "Елена Морозова",
            "pending",
            find_id(milestones, project_id="P001", name="Security review и интеграция"),
        ),
        (
            "P001",
            d(2026, 6, 13),
            "budget_reserve",
            "Согласовать дополнительный резерв на compliance-доработки или сократить scope пилота.",
            "Steering Committee",
            "pending",
            find_id(milestones, project_id="P001", name="Пилот в кредитном конвейере"),
        ),
        (
            "P002",
            d(2026, 6, 7),
            "pilot_scope",
            "Запускать пилот fraud decisioning без части правил до завершения интеграции с процессингом.",
            "Андрей Романов",
            "pending",
            find_id(milestones, project_id="P002", name="Интеграция с процессингом"),
        ),
        (
            "P003",
            d(2026, 6, 18),
            "release_go",
            "Подтвердить окно pilot release после расширенного регрессионного прогона.",
            "Артур Комаров",
            "approved",
            find_id(milestones, project_id="P003", name="Pilot release"),
        ),
        (
            "P004",
            d(2026, 6, 14),
            "vendor_escalation",
            "Эскалировать задержку сертификатов СБП через vendor manager.",
            "Сергей Ковалев",
            "approved",
            find_id(milestones, project_id="P004", name="СБП и acquiring adapters"),
        ),
        (
            "P005",
            d(2026, 6, 17),
            "data_governance",
            "Зафиксировать владельца правил дедупликации и критерии качества golden record.",
            "Ольга Беляева",
            "approved",
            find_id(milestones, project_id="P005", name="Golden record"),
        ),
    ]

    rows = []
    for idx, (project_id, decision_date, decision_type, description, owner, status, milestone_id) in enumerate(
        specs,
        start=1,
    ):
        rows.append(
            {
                "id": f"DEC{idx:03d}",
                "project_id": project_id,
                "decision_date": iso(decision_date),
                "decision_type": decision_type,
                "description": description,
                "decision_owner": owner,
                "status": status,
                "linked_milestone_id": milestone_id,
            }
        )
    return rows


def make_change_requests() -> list[dict[str, Any]]:
    specs = [
        (
            "P001",
            d(2026, 6, 12),
            "Security",
            "compliance_scope",
            "Добавить расширенную модель угроз и дополнительные проверки маскирования данных.",
            "medium",
            8_000_000,
            14,
            "under_review",
        ),
        (
            "P001",
            d(2026, 6, 13),
            "Core Platform",
            "integration_scope",
            "Перенести часть интеграционных сценариев кредитного конвейера в post-pilot.",
            "high",
            -3_000_000,
            -6,
            "proposed",
        ),
        (
            "P002",
            d(2026, 6, 7),
            "Fraud Platform",
            "performance_tuning",
            "Добавить отдельный спринт на оптимизацию feature lookup до целевых 120 мс.",
            "medium",
            4_000_000,
            8,
            "under_review",
        ),
        (
            "P004",
            d(2026, 6, 14),
            "Payments",
            "vendor_scope",
            "Закупить дополнительные vendor-сертификаты и расширить sandbox-mock для gateway.",
            "low",
            4_000_000,
            5,
            "approved",
        ),
        (
            "P005",
            d(2026, 6, 17),
            "CRM Analytics",
            "data_quality",
            "Добавить ручную проверку топ-сегментов после дедупликации golden record.",
            "low",
            1_000_000,
            2,
            "approved",
        ),
    ]

    rows = []
    for idx, (project_id, request_date, requested_by, change_type, description, scope, budget, days, status) in enumerate(
        specs,
        start=1,
    ):
        rows.append(
            {
                "id": f"CR{idx:03d}",
                "project_id": project_id,
                "request_date": iso(request_date),
                "requested_by": requested_by,
                "change_type": change_type,
                "description": description,
                "impact_scope": scope,
                "impact_budget": budget,
                "impact_days": days,
                "status": status,
            }
        )
    return rows


def make_task_dependencies(tasks_by_project: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    specs = [
        ("P001", 5, 1, "blocks", True, 1, "Security approval is required before integration and pilot activities."),
        ("P001", 6, 2, "blocks", True, 0, "DWH SLA confirmation is needed before feature validation."),
        ("P001", 9, 4, "requires", False, 2, "Rollback procedure depends on validated model documentation."),
        ("P002", 4, 1, "blocks", True, 1, "Integration testing waits for the processing window."),
        ("P002", 5, 2, "blocks", True, 1, "Feature store tuning depends on threat model approval."),
        ("P002", 6, 4, "blocks", True, 0, "Latency optimization depends on a stable processing adapter."),
        ("P003", 6, 1, "related", False, 1, "Mobile onboarding should align with UX approval."),
        ("P003", 8, 6, "blocks", False, 0, "Regression package depends on the stabilized client flow."),
        ("P004", 4, 1, "blocks", True, 1, "Payment routing depends on vendor certificate delivery."),
        ("P004", 8, 2, "blocks", True, 2, "Load testing depends on a completed PCI DSS checklist."),
        ("P005", 4, 1, "blocks", True, 1, "Golden record mapping depends on deduplication rules."),
        ("P005", 8, 4, "related", False, 0, "Cross-sell segments depend on stable profile quality."),
    ]

    rows = []
    for idx, (project_id, task_number, depends_on_number, dependency_type, is_critical, lag_days, reason) in enumerate(
            specs, start=1):
        rows.append(
            {
                "id": f"TD{idx:03d}",
                "project_id": project_id,
                "task_id": task_id(tasks_by_project, project_id, task_number),
                "depends_on_task_id": task_id(tasks_by_project, project_id, depends_on_number),
                "dependency_type": dependency_type,
                "is_critical_path": is_critical,
                "lag_days": lag_days,
                "reason": reason,
            }
        )
    return rows


def make_budget_line_items(budgets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    budget_id = {row["project_id"]: row["id"] for row in budgets}
    specs = [
        ("P001", "Engineering", "Model development", "Risk Models", 10_000_000, 8_500_000, 11_000_000),
        ("P001", "Integration", "Core Platform integration", "Core Platform", 14_000_000, 12_000_000, 18_000_000),
        ("P001", "Compliance", "Security and approvals", "Security", 16_000_000, 13_000_000, 20_000_000),
        ("P001", "Testing", "Pilot rollout", "PMO", 8_000_000, 8_000_000, 13_000_000),
        ("P002", "Engineering", "Streaming core", "Fraud Platform", 20_000_000, 18_000_000, 24_000_000),
        ("P002", "Integration", "Card processing adapter", "Payments", 18_000_000, 16_000_000, 20_000_000),
        ("P002", "Modeling", "Feature store and scoring", "Risk Models", 20_000_000, 14_000_000, 22_000_000),
        ("P002", "Compliance", "UAT and sign-off", "Compliance", 14_000_000, 16_000_000, 22_000_000),
        ("P003", "UX", "Mobile UX and design", "Mobile", 10_000_000, 8_000_000, 9_000_000),
        ("P003", "Product", "Client scenarios", "Mobile", 10_000_000, 7_000_000, 8_000_000),
        ("P003", "Analytics", "Event tracking", "CRM Analytics", 12_000_000, 9_000_000, 12_000_000),
        ("P003", "Release", "Stabilization", "Quality", 10_000_000, 5_500_000, 11_000_000),
        ("P004", "Engineering", "Gateway core", "Payments", 10_000_000, 9_000_000, 11_000_000),
        ("P004", "Integration", "SBP and acquiring adapters", "Payments", 12_000_000, 8_000_000, 13_000_000),
        ("P004", "Security", "PCI DSS workstream", "Security", 8_000_000, 7_000_000, 9_000_000),
        ("P004", "Observability", "Load testing and monitoring", "Platform", 8_000_000, 7_000_000, 10_000_000),
        ("P005", "Data Quality", "Golden record and dedupe", "CRM Analytics", 9_000_000, 6_000_000, 8_000_000),
        ("P005", "Engineering", "CRM profile API", "CRM Platform", 9_000_000, 6_000_000, 8_000_000),
        ("P005", "Governance", "Data quality controls", "Data Platform", 8_000_000, 5_000_000, 8_000_000),
        ("P005", "Rollout", "Pilot rollout", "Sales", 8_000_000, 5_500_000, 9_000_000),
    ]

    rows = []
    for idx, (project_id, category, item_name, owner_team, planned_amount, actual_amount, forecast_amount) in enumerate(specs, start=1):
        rows.append(
            {
                "id": f"BI{idx:03d}",
                "project_id": project_id,
                "budget_id": budget_id[project_id],
                "category": category,
                "item_name": item_name,
                "planned_amount": planned_amount,
                "actual_amount": actual_amount,
                "forecast_amount": forecast_amount,
                "owner_team": owner_team,
            }
        )
    return rows


def make_communication_messages(communications: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    next_id = 1
    for communication in communications:
        project_id = communication["project_id"]
        comm_id = communication["id"]
        topic = communication["topic"]
        channel = communication["channel"]
        from_team = communication["from_team"]
        to_team = communication["to_team"]
        last_date = parse_date(communication["last_message_date"])
        response_date = parse_date(communication["expected_response_date"])
        linked_task_id = communication["linked_task_id"]
        ensure(last_date is not None, f"Communication {comm_id} has no last_message_date")
        ensure(response_date is not None, f"Communication {comm_id} has no expected_response_date")

        rows.append(
            {
                "id": f"CM{next_id:03d}",
                "project_id": project_id,
                "communication_id": comm_id,
                "message_time": iso_dt(dt(last_date.year, last_date.month, last_date.day, 9, 15)),
                "sender_team": from_team,
                "recipient_team": to_team,
                "channel": channel,
                "message_type": "request",
                "status": "sent",
                "summary": f"Первичный запрос по теме: {topic}",
                "linked_task_id": linked_task_id,
                "is_escalation": False,
            }
        )
        next_id += 1

        if communication["status"] == "responded":
            sender_team, recipient_team, message_type, status, summary, escalation = (
                to_team,
                from_team,
                "response",
                "replied",
                f"Ответ по теме: {topic}",
                False,
            )
        elif communication["status"] == "escalated":
            sender_team, recipient_team, message_type, status, summary, escalation = (
                "PMO",
                to_team,
                "escalation",
                "escalated",
                f"Эскалация по теме: {topic}",
                True,
            )
        elif communication["status"] == "delayed":
            sender_team, recipient_team, message_type, status, summary, escalation = (
                from_team,
                to_team,
                "reminder",
                "waiting",
                f"Напоминание по теме: {topic}",
                False,
            )
        else:
            sender_team, recipient_team, message_type, status, summary, escalation = (
                from_team,
                to_team,
                "follow_up",
                "waiting",
                f"Фоллоу-ап по теме: {topic}",
                False,
            )

        rows.append(
            {
                "id": f"CM{next_id:03d}",
                "project_id": project_id,
                "communication_id": comm_id,
                "message_time": iso_dt(dt(response_date.year, response_date.month, response_date.day, 15, 30)),
                "sender_team": sender_team,
                "recipient_team": recipient_team,
                "channel": channel,
                "message_type": message_type,
                "status": status,
                "summary": summary,
                "linked_task_id": linked_task_id,
                "is_escalation": escalation,
            }
        )
        next_id += 1

    return rows


def make_dependencies(tasks_by_project: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    specs = [
        (
            "P001",
            "internal_system",
            "DWH feature mart",
            "Data Platform",
            d(2026, 6, 7),
            "delayed",
            "high",
            task_id(tasks_by_project, "P001", 2),
        ),
        (
            "P001",
            "approval",
            "Security approval",
            "Security",
            d(2026, 6, 5),
            "blocked",
            "critical",
            task_id(tasks_by_project, "P001", 1),
        ),
        (
            "P001",
            "management_decision",
            "Scope cut decision",
            "PMO",
            d(2026, 6, 18),
            "pending",
            "high",
            task_id(tasks_by_project, "P001", 9),
        ),
        (
            "P002",
            "internal_system",
            "Card processing stream",
            "Card Processing",
            d(2026, 6, 3),
            "blocked",
            "critical",
            task_id(tasks_by_project, "P002", 1),
        ),
        (
            "P002",
            "approval",
            "False positive criteria",
            "Compliance",
            d(2026, 6, 10),
            "delayed",
            "high",
            task_id(tasks_by_project, "P002", 8),
        ),
        (
            "P003",
            "release_window",
            "Pilot release slot",
            "Release Management",
            d(2026, 6, 19),
            "pending",
            "medium",
            task_id(tasks_by_project, "P003", 10),
        ),
        (
            "P004",
            "vendor",
            "SBP test certificates",
            "SBP Vendor",
            d(2026, 6, 8),
            "delayed",
            "critical",
            task_id(tasks_by_project, "P004", 1),
        ),
        (
            "P004",
            "approval",
            "PCI DSS token storage review",
            "Security",
            d(2026, 6, 13),
            "delayed",
            "high",
            task_id(tasks_by_project, "P004", 2),
        ),
        (
            "P005",
            "data_owner",
            "CRM duplicate ownership",
            "Data Owners",
            d(2026, 6, 14),
            "responded",
            "medium",
            task_id(tasks_by_project, "P005", 2),
        ),
        (
            "P005",
            "approval",
            "Profile 360 access matrix",
            "Compliance",
            d(2026, 6, 17),
            "pending",
            "medium",
            task_id(tasks_by_project, "P005", 9),
        ),
    ]

    rows = []
    for idx, (project_id, dependency_type, depends_on, owner_team, expected_date, status, criticality, linked_task_id) in enumerate(
        specs,
        start=1,
    ):
        rows.append(
            {
                "id": f"D{idx:03d}",
                "project_id": project_id,
                "dependency_type": dependency_type,
                "depends_on": depends_on,
                "owner_team": owner_team,
                "expected_date": iso(expected_date),
                "status": status,
                "criticality": criticality,
                "linked_task_id": linked_task_id,
            }
        )
    return rows


def make_decisions(milestones: list[dict[str, Any]]) -> list[dict[str, Any]]:
    specs = [
        (
            "P001",
            d(2026, 6, 12),
            "scope_change",
            "Перенести часть интеграции в post-pilot, чтобы разблокировать Security review.",
            "Елена Морозова",
            "pending",
            find_id(milestones, project_id="P001", name="Security review и интеграция"),
        ),
        (
            "P001",
            d(2026, 6, 13),
            "budget_reserve",
            "Согласовать дополнительный резерв на compliance-доработки или сократить scope пилота.",
            "Steering Committee",
            "pending",
            find_id(milestones, project_id="P001", name="Пилот в кредитном конвейере"),
        ),
        (
            "P002",
            d(2026, 6, 7),
            "pilot_scope",
            "Запускать пилот fraud decisioning без части правил до завершения интеграции с процессингом.",
            "Андрей Романов",
            "pending",
            find_id(milestones, project_id="P002", name="Интеграция с процессингом"),
        ),
        (
            "P003",
            d(2026, 6, 18),
            "release_go",
            "Подтвердить окно pilot release после расширенного регрессионного прогона.",
            "Артур Комаров",
            "approved",
            find_id(milestones, project_id="P003", name="Pilot release"),
        ),
        (
            "P004",
            d(2026, 6, 14),
            "vendor_escalation",
            "Эскалировать задержку сертификатов СБП через vendor manager.",
            "Сергей Ковалев",
            "approved",
            find_id(milestones, project_id="P004", name="СБП и acquiring adapters"),
        ),
        (
            "P005",
            d(2026, 6, 17),
            "data_governance",
            "Зафиксировать владельца правил дедупликации и критерии качества golden record.",
            "Ольга Беляева",
            "approved",
            find_id(milestones, project_id="P005", name="Golden record"),
        ),
    ]

    rows = []
    for idx, (project_id, decision_date, decision_type, description, owner, status, milestone_id) in enumerate(
        specs,
        start=1,
    ):
        rows.append(
            {
                "id": f"DEC{idx:03d}",
                "project_id": project_id,
                "decision_date": iso(decision_date),
                "decision_type": decision_type,
                "description": description,
                "decision_owner": owner,
                "status": status,
                "linked_milestone_id": milestone_id,
            }
        )
    return rows


def make_change_requests() -> list[dict[str, Any]]:
    specs = [
        (
            "P001",
            d(2026, 6, 12),
            "Security",
            "compliance_scope",
            "Добавить расширенную модель угроз и дополнительные проверки маскирования данных.",
            "medium",
            8_000_000,
            14,
            "under_review",
        ),
        (
            "P001",
            d(2026, 6, 13),
            "Core Platform",
            "integration_scope",
            "Перенести часть интеграционных сценариев кредитного конвейера в post-pilot.",
            "high",
            -3_000_000,
            -6,
            "proposed",
        ),
        (
            "P002",
            d(2026, 6, 7),
            "Fraud Platform",
            "performance_tuning",
            "Добавить отдельный спринт на оптимизацию feature lookup до целевых 120 мс.",
            "medium",
            4_000_000,
            8,
            "under_review",
        ),
        (
            "P004",
            d(2026, 6, 14),
            "Payments",
            "vendor_scope",
            "Закупить дополнительные vendor-сертификаты и расширить sandbox-mock для gateway.",
            "low",
            4_000_000,
            5,
            "approved",
        ),
        (
            "P005",
            d(2026, 6, 17),
            "CRM Analytics",
            "data_quality",
            "Добавить ручную проверку топ-сегментов после дедупликации golden record.",
            "low",
            1_000_000,
            2,
            "approved",
        ),
    ]

    rows = []
    for idx, (project_id, request_date, requested_by, change_type, description, scope, budget, days, status) in enumerate(
        specs,
        start=1,
    ):
        rows.append(
            {
                "id": f"CR{idx:03d}",
                "project_id": project_id,
                "request_date": iso(request_date),
                "requested_by": requested_by,
                "change_type": change_type,
                "description": description,
                "impact_scope": scope,
                "impact_budget": budget,
                "impact_days": days,
                "status": status,
            }
        )
    return rows


def write_csv(filename: str, rows: list[dict[str, Any]], columns: list[str]) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(DATA_DIR / filename, index=False)


def remove_stale_derived_files() -> None:
    for filename in ["metrics_snapshots.csv", "project_events.csv"]:
        path = DATA_DIR / filename
        if path.exists():
            path.unlink()


def validate_dataset(
    projects: list[dict[str, Any]],
    tasks: list[dict[str, Any]],
    task_dependencies: list[dict[str, Any]],
    budget_line_items: list[dict[str, Any]],
    communication_messages: list[dict[str, Any]],
    task_history: list[dict[str, Any]],
    task_comments: list[dict[str, Any]],
    dependencies: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    change_requests: list[dict[str, Any]],
    resources: list[dict[str, Any]],
    allocations: list[dict[str, Any]],
    budgets: list[dict[str, Any]],
    milestones: list[dict[str, Any]],
    risks: list[dict[str, Any]],
    communications: list[dict[str, Any]],
) -> None:
    ensure(100 <= len(tasks) <= 150, f"Expected 100-150 tasks, got {len(tasks)}")
    ensure(sum(1 for project in projects if project["status"] == "red") >= 2, "Expected at least two red projects")
    ensure(any(task["is_blocked"] for task in tasks), "Expected at least one blocked task")

    has_overdue_open_task = False
    for task in tasks:
        planned_due = parse_date(task["planned_due_date"])
        if task["status"] != "Done" and planned_due is not None and planned_due < LATEST_SNAPSHOT_DATE:
            has_overdue_open_task = True
            break
    ensure(has_overdue_open_task, "Expected at least one overdue open task")

    availability = {resource["id"]: resource["available_hours_per_week"] for resource in resources}
    total_actual_by_resource: dict[str, float] = defaultdict(float)
    for allocation in allocations:
        total_actual_by_resource[allocation["resource_id"]] += allocation["actual_hours_per_week"]
    ensure(bool(total_actual_by_resource), "Expected resource allocations")

    max_total_allocation = max(
        total_actual_by_resource[resource_id] / availability[resource_id] * 100
        for resource_id in total_actual_by_resource
    )
    ensure(
        130 <= max_total_allocation <= 150,
        f"Expected max resource allocation between 130 and 150%, got {max_total_allocation:.1f}%",
    )

    valid_project_ids = {project["id"] for project in projects}
    valid_task_ids = {task["id"] for task in tasks}
    invalid_dependencies = [
        dep["id"]
        for dep in task_dependencies
        if dep["task_id"] not in valid_task_ids or dep["depends_on_task_id"] not in valid_task_ids
    ]
    self_dependencies = [
        dep["id"]
        for dep in task_dependencies
        if dep["task_id"] == dep["depends_on_task_id"]
    ]
    ensure(len(task_dependencies) >= 10, "Expected at least 10 task dependencies")
    ensure(not invalid_dependencies, f"Dependencies with invalid task ids: {invalid_dependencies}")
    ensure(not self_dependencies, f"Dependencies cannot point to the same task: {self_dependencies}")

    budget_totals: dict[str, dict[str, int]] = defaultdict(lambda: {"planned": 0, "actual": 0, "forecast": 0})
    for item in budget_line_items:
        budget_totals[item["project_id"]]["planned"] += item["planned_amount"]
        budget_totals[item["project_id"]]["actual"] += item["actual_amount"]
        budget_totals[item["project_id"]]["forecast"] += item["forecast_amount"]
    for budget in budgets:
        project_id = budget["project_id"]
        totals = budget_totals[budget["project_id"]]
        ensure(
            totals["planned"] == budget["planned_budget"],
            f"Budget planned mismatch for {project_id}: {totals['planned']} != {budget['planned_budget']}",
        )
        ensure(
            totals["actual"] == budget["actual_spent"],
            f"Budget actual mismatch for {project_id}: {totals['actual']} != {budget['actual_spent']}",
        )
        ensure(
            totals["forecast"] == budget["forecast_total_spent"],
            f"Budget forecast mismatch for {project_id}: {totals['forecast']} != {budget['forecast_total_spent']}",
        )

    valid_communication_ids = {communication["id"] for communication in communications}
    invalid_message_ids = [
        message["id"]
        for message in communication_messages
        if message["communication_id"] not in valid_communication_ids
    ]
    ensure(
        len(communication_messages) == len(communications) * 2,
        f"Expected two messages per communication, got {len(communication_messages)} messages",
    )
    ensure(not invalid_message_ids, f"Messages with invalid communication ids: {invalid_message_ids}")

    invalid_history_ids = [
        item["id"]
        for item in task_history
        if item["project_id"] not in valid_project_ids or item["task_id"] not in valid_task_ids
    ]
    ensure(len(task_history) >= 15, "Expected at least 15 task history records")
    ensure(not invalid_history_ids, f"Task history records with invalid references: {invalid_history_ids}")
    ensure(
        any(
            item["project_id"] == "P001"
            and item["task_id"] == task_id(task_lookup(tasks), "P001", 1)
            and item["field_changed"] == "status"
            and item["new_value"] == "Blocked"
            for item in task_history
        ),
        "Expected task history to include P001 Security task blocking",
    )

    invalid_comment_ids = [
        item["id"]
        for item in task_comments
        if item["project_id"] not in valid_project_ids or item["task_id"] not in valid_task_ids
    ]
    ensure(len(task_comments) >= 15, "Expected at least 15 task comments")
    ensure(not invalid_comment_ids, f"Task comments with invalid references: {invalid_comment_ids}")
    ensure(
        any(item["project_id"] == "P001" and "Security" in item["text"] for item in task_comments),
        "Expected task comments to include P001 Security discussion",
    )

    negative_roi_projects = [
        budget
        for budget in budgets
        if (budget["expected_economic_effect"] - budget["forecast_total_spent"]) / budget["forecast_total_spent"] < 0
    ]
    ensure(bool(negative_roi_projects), "Expected at least one project with negative ROI")
    ensure(
        any(milestone["project_id"] == "P001" and milestone["status"] == "Delayed" for milestone in milestones),
        "Expected a delayed milestone for P001",
    )
    ensure(
        any(risk["project_id"] == "P001" and risk["probability"] * risk["impact"] >= 15 for risk in risks),
        "Expected a high-risk item for P001",
    )
    ensure(
        any(
            communication["project_id"] == "P001" and communication["status"] == "escalated"
            for communication in communications
        ),
        "Expected an escalated communication for P001",
    )

    valid_milestone_ids = {milestone["id"] for milestone in milestones}

    ensure(len(dependencies) >= 8, "Expected at least 8 project dependencies")
    ensure(
        any(
            dep["project_id"] == "P001"
            and dep["criticality"] == "critical"
            and dep["status"] in {"blocked", "delayed"}
            for dep in dependencies
        ),
        "Expected a critical blocked or delayed dependency for P001",
    )
    ensure(
        all(dep["project_id"] in valid_project_ids and dep["linked_task_id"] in valid_task_ids for dep in dependencies),
        "Dependencies must reference existing projects and tasks",
    )

    ensure(len(decisions) >= 5, "Expected at least 5 project decisions")
    ensure(
        any(decision["project_id"] == "P001" and decision["status"] == "pending" for decision in decisions),
        "Expected a pending decision for P001",
    )
    ensure(
        all(
            decision["project_id"] in valid_project_ids
            and decision["linked_milestone_id"] in valid_milestone_ids
            for decision in decisions
        ),
        "Decisions must reference existing projects and milestones",
    )

    ensure(len(change_requests) >= 5, "Expected at least 5 change requests")
    ensure(
        any(
            request["project_id"] == "P001"
            and request["impact_budget"] > 0
            and request["impact_days"] > 0
            for request in change_requests
        ),
        "Expected a positive budget and timeline impact change request for P001",
    )
    ensure(
        all(request["project_id"] in valid_project_ids for request in change_requests),
        "Change requests must reference existing projects",
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
    task_dependencies = make_task_dependencies(tasks_by_project)
    budget_line_items = make_budget_line_items(budgets)
    communication_messages = make_communication_messages(communications)
    task_history = make_task_history(tasks_by_project)
    task_comments = make_task_comments(tasks_by_project, resources)
    dependencies = make_dependencies(tasks_by_project)
    decisions = make_decisions(milestones)
    change_requests = make_change_requests()

    validate_dataset(
        projects,
        tasks,
        task_dependencies,
        budget_line_items,
        communication_messages,
        task_history,
        task_comments,
        dependencies,
        decisions,
        change_requests,
        resources,
        allocations,
        budgets,
        milestones,
        risks,
        communications,
    )

    write_csv("projects.csv", projects, PROJECT_COLUMNS)
    write_csv("tasks.csv", tasks, TASK_COLUMNS)
    write_csv("task_history.csv", task_history, TASK_HISTORY_COLUMNS)
    write_csv("task_comments.csv", task_comments, TASK_COMMENT_COLUMNS)
    write_csv("task_dependencies.csv", task_dependencies, TASK_DEPENDENCY_COLUMNS)
    write_csv("milestones.csv", milestones, MILESTONE_COLUMNS)
    write_csv("budgets.csv", budgets, BUDGET_COLUMNS)
    write_csv("budget_line_items.csv", budget_line_items, BUDGET_ITEM_COLUMNS)
    write_csv("risks.csv", risks, RISK_COLUMNS)
    write_csv("communications.csv", communications, COMMUNICATION_COLUMNS)
    write_csv("communication_messages.csv", communication_messages, COMMUNICATION_MESSAGE_COLUMNS)
    write_csv("dependencies.csv", dependencies, DEPENDENCY_COLUMNS)
    write_csv("decisions.csv", decisions, DECISION_COLUMNS)
    write_csv("change_requests.csv", change_requests, CHANGE_REQUEST_COLUMNS)
    write_csv("resources.csv", resources, RESOURCE_COLUMNS)
    write_csv("resource_allocations.csv", allocations, RESOURCE_ALLOCATION_COLUMNS)
    remove_stale_derived_files()

    print(f"Generated demo dataset in {DATA_DIR.resolve()}")
    print(f"Projects: {len(projects)}")
    print(f"Tasks: {len(tasks)}")
    print(f"Task history records: {len(task_history)}")
    print(f"Task comments: {len(task_comments)}")
    print(f"Dependencies: {len(dependencies)}")
    print(f"Decisions: {len(decisions)}")
    print(f"Change requests: {len(change_requests)}")


if __name__ == "__main__":
    main()
