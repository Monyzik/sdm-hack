import json
import os
from typing import Literal
from urllib.parse import urlencode
from urllib.request import urlopen

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class ProjectManagerBrief(BaseModel):
    """Строгий контракт ответа LLM для руководителя проекта.

    Основной текст должен быть читаемым русским языком. Технические id нельзя
    смешивать с текстом, они нужны только в отдельном поле для трассировки.
    """

    model_config = ConfigDict(extra="forbid")

    status: Literal["в норме", "под наблюдением", "критично"] = Field(
        description="Человеческая оценка состояния проекта."
    )
    headline: str = Field(
        max_length=140,
        description="Одна строка о состоянии проекта без технических id.",
    )
    summary: str = Field(
        max_length=360,
        description="Два коротких предложения: что происходит и почему это важно.",
    )
    main_reasons: list[str] = Field(
        min_length=2,
        max_length=4,
        description="Главные причины проблемы простым русским языком, без id.",
    )
    business_impact: list[str] = Field(
        min_length=1,
        max_length=3,
        description="Влияние на сроки, бюджет, запуск, качество или бизнес-эффект.",
    )
    next_48h_actions: list[str] = Field(
        min_length=2,
        max_length=4,
        description="Конкретные действия на ближайшие 48 часов.",
    )
    decisions_required: list[str] = Field(
        max_length=3,
        description="Решения, которые должен принять владелец проекта или комитет.",
    )
    escalations: list[str] = Field(
        max_length=3,
        description="Темы для эскалации без технических id в тексте.",
    )
    evidence_ids: list[str] = Field(
        max_length=20,
        description="Id источников из JSON summary для трассировки во фронте.",
    )
    missing_data: list[str] = Field(
        max_length=3,
        description="Каких данных не хватает. Вернуть пустой список, если данных достаточно.",
    )


SYSTEM_PROMPT = """
Ты агент AI Project Control Tower для руководителя проектов банка.

Тебе приходит JSON summary из backend. Используй только эти данные. Ничего не выдумывай:
не добавляй людей, даты, суммы, причины, статусы и риски, которых нет во входном JSON.

Сделай короткий управленческий ответ на русском языке.

Правила:
- верни только валидный JSON-объект;
- первый символ ответа должен быть {, последний символ ответа должен быть };
- не используй markdown, заголовки, списки вне JSON, пояснения до JSON или после JSON;
- не пересчитывай метрики, которые уже есть во входном JSON;
- не вставляй технические id в обычный текст;
- не используй смесь русского текста и англоязычных системных слов, если можно написать по-русски;
- не пиши длинную простыню;
- в основном тексте пиши выводы, причины, влияние и действия;
- все использованные id положи только в поле evidence_ids;
- если данных не хватает для вывода, заполни missing_data;
- если данных достаточно, missing_data должен быть пустым списком.
""".strip()


def fetch_project_summary(project_id: str = "P001", as_of: str = "2026-06-19") -> dict:
    api_base_url = os.getenv("LOCAL_API_URL", "http://localhost:8000")
    query = urlencode({"as_of": as_of})
    url = f"{api_base_url}/api/v1/summaries/projects/{project_id}?{query}"
    with urlopen(url, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def build_response_format() -> dict:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "project_manager_brief",
            "strict": True,
            "schema": ProjectManagerBrief.model_json_schema(),
        },
    }


def build_user_prompt(summary: dict, bad_response: str | None = None) -> str:
    schema = json.dumps(ProjectManagerBrief.model_json_schema(), ensure_ascii=False)
    retry_note = ""
    if bad_response:
        retry_note = (
            "Предыдущий ответ был отклонён, потому что это был невалидный JSON. "
            "Исправь формат и верни только JSON по схеме.\n\n"
            f"Начало невалидного ответа:\n{bad_response[:700]}\n\n"
        )

    return (
        retry_note
        + "Сформируй краткий управленческий brief по JSON summary.\n"
        + "Ответ должен быть только JSON-объектом по схеме ниже. "
        + "Не добавляй markdown и текст вне JSON.\n\n"
        + "JSON Schema:\n"
        + schema
        + "\n\nJSON summary:\n"
        + json.dumps(summary, ensure_ascii=False)
    )


def request_brief_content(client: OpenAI, summary: dict, bad_response: str | None = None) -> str:
    response = client.chat.completions.create(
        model=os.getenv("AI_MODEL", "gpt-5.4-mini"),
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(summary, bad_response)},
        ],
        response_format=build_response_format(),
        temperature=0.2,
    )

    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("LLM вернула пустой ответ")
    return content


def validate_brief_content(content: str) -> ProjectManagerBrief:
    try:
        return ProjectManagerBrief.model_validate_json(content)
    except ValidationError as exc:
        response_start = content[:700]
        raise RuntimeError(
            "LLM вернула ответ не по JSON-контракту. "
            "Проверь, что текущие AI_URL и модель реально поддерживают response_format=json_schema strict. "
            f"Начало ответа: {response_start}"
        ) from exc


def fetch() -> ProjectManagerBrief:
    load_dotenv()

    summary = fetch_project_summary()
    client = OpenAI(
        api_key=os.getenv("AI_TOKEN"),
        base_url=os.getenv("AI_URL"),
    )

    first_content = request_brief_content(client, summary)
    try:
        return ProjectManagerBrief.model_validate_json(first_content)
    except ValidationError:
        second_content = request_brief_content(client, summary, bad_response=first_content)
        return validate_brief_content(second_content)


if __name__ == "__main__":
    brief = fetch()
    print(brief.model_dump_json(indent=2, ensure_ascii=False))
