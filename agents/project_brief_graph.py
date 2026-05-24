from __future__ import annotations

import json
import os
import re
from datetime import date
from typing import Any, Literal
from urllib.parse import urlencode
from urllib.request import urlopen

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from agents.yandex_client import get_yandex_client, get_yandex_model_uri

try:
    from langgraph.graph import END, START, StateGraph
except ModuleNotFoundError:
    END = START = StateGraph = None


TECHNICAL_ID_RE = re.compile(r"\b(?:T|TD|RK|C|D|DEC|CR|R|Р)\d{3}\b")


class BusinessImpact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    delay_days: int | None = Field(None, description="Оценка задержки в днях из входных метрик.")
    cost_of_delay: int | None = Field(None, description="Денежный exposure задержки из входных метрик.")
    budget_delta: int | None = Field(None, description="Отклонение или impact бюджета из входных данных.")
    impact_summary: str = Field(description="Короткое объяснение управленческого impact.")


class AgentActionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str = Field(description="Конкретное действие, которое можно поручить.")
    owner_hint: str = Field(description="Кому адресовать действие по входным фактам.")
    deadline: str = Field(description="Срок реакции человеческим языком, без выдуманной даты.")
    success_signal: str = Field(description="Как понять, что действие сработало.")


class DraftMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipient_hint: str = Field(description="Кому отправить сообщение по входным фактам.")
    subject: str = Field(description="Короткая тема сообщения.")
    body: str = Field(description="Готовый черновик сообщения без технических id.")


class FollowUpCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check_after: str = Field(description="Когда агент должен проверить изменения.")
    success_condition: str = Field(description="Какой факт во входных данных будет означать улучшение.")
    escalation_condition: str = Field(description="Что считать поводом для следующей эскалации.")


class ProjectManagerBrief(BaseModel):
    """Строгий контракт управленческой рекомендации для руководителя проекта."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["в норме", "под наблюдением", "критично"] = Field(
        description="Человеческая оценка состояния проекта."
    )
    headline: str = Field(description="Одна строка о главном управленческом выводе без технических id.")
    management_question: str = Field(description="Главный вопрос, который должен решить владелец проекта или комитет.")
    diagnosis: str = Field(description="Короткая причинно-следственная диагностика, а не пересказ метрик.")
    bottleneck: str = Field(description="Одно главное узкое место, которое сильнее всего удерживает проект.")
    critical_path: list[str] = Field(
        min_length=2,
        max_length=3,
        description="Цепочка зависимостей, объясняющая почему проблема распространяется дальше.",
    )
    recommended_move: str = Field(description="Один лучший следующий управленческий ход с ожидаемым эффектом.")
    decision_options: list["DecisionOption"] = Field(
        min_length=2,
        max_length=3,
        description="Реальные развилки решения с компромиссами.",
    )
    business_impact: BusinessImpact = Field(
        description="Перевод проблемы в срок, деньги и управленческий impact."
    )
    next_actions: list[AgentActionItem] = Field(
        min_length=1,
        max_length=3,
        description="Поручения, которые можно создать в системе по рекомендации агента.",
    )
    draft_message: DraftMessage = Field(
        description="Черновик управленческого сообщения владельцу блокера или решения."
    )
    follow_up_check: FollowUpCheck = Field(
        description="Правило последующей проверки, чтобы агент не заканчивался текстом."
    )
    watchouts: list[str] = Field(
        min_length=1,
        max_length=3,
        description="Что не стоит делать или что проверить перед решением.",
    )
    evidence_ids: list[str] = Field(
        max_length=20,
        description="Id источников из JSON problem context для трассировки. Не показывать в обычном тексте.",
    )
    missing_data: list[str] = Field(
        max_length=3,
        description="Каких данных не хватает. Вернуть пустой список, если данных достаточно.",
    )


class DecisionOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    option: str = Field(description="Короткое название управленческой опции.")
    when_to_choose: str = Field(description="Когда эту опцию стоит выбрать.")
    tradeoff: str = Field(description="Цена решения или риск компромисса.")


class ProjectBriefData(BaseModel):
    project_id: str
    as_of: date | None = None
    max_depth: int = 2
    problem_context: dict[str, Any] | None = None
    brief: dict[str, Any] | None = None


SYSTEM_PROMPT = """
Ты агент AI Project Control Tower для руководителя проектов банка.

Тебе приходит JSON problem context из backend. Используй только эти данные. Ничего не выдумывай:
не добавляй людей, даты, суммы, причины, статусы и риски, которых нет во входном JSON.

Backend не присылает готовые выводы. Он присылает факты: проблемные задачи, граф зависимостей,
связанные риски, коммуникации, решения, бюджет и ресурсы. Твоя задача не пересказать эти факты,
а помочь руководителю проекта принять решение.

Правила:
- верни только валидный JSON-объект;
- не используй markdown, заголовки, пояснения до JSON или после JSON;
- не пересчитывай метрики, которые уже есть во входном JSON;
- не вставляй технические id в обычный текст;
- технические id вида T001, RK001, DEC001, R003 разрешены только в evidence_ids;
- не используй смесь русского текста и англоязычных системных слов, если можно написать по-русски;
- не пиши длинную простыню;
- не делай список очевидных причин, которые пользователь уже видит на дашборде;
- не повторяй отдельными пунктами блокеры, бюджет, ROI и перегруз, если не связываешь их в причинную цепочку;
- сначала найди узкое место и цепочку зависимостей из problem_tasks и task_dependency_edges;
- потом сформулируй управленческую развилку: что именно надо решить, какие есть опции и цена каждой;
- recommended_move должен быть одним ходом, а не списком поручений;
- business_impact заполни только из метрик и фактов: задержка, cost of delay, бюджетный impact, краткий смысл;
- next_actions должны быть готовыми поручениями с владельцем, сроком реакции и измеримым признаком успеха;
- draft_message должен быть готовым коротким сообщением владельцу блокера, решения или зависимости;
- follow_up_check должен описывать, что агент проверит после действия и когда нужна повторная эскалация;
- watchouts используй для вещей, которые могут выглядеть правильными, но не решат проблему;
- если вывод не следует из problem_context, не пиши его;
- все использованные id положи только в поле evidence_ids;
- если данных не хватает для вывода, заполни missing_data;
- если данных достаточно, missing_data должен быть пустым списком.
""".strip()


def state_value(state: ProjectBriefData | dict[str, Any], key: str, default: Any = None) -> Any:
    if isinstance(state, ProjectBriefData):
        return getattr(state, key)
    return state.get(key, default)


def fetch_project_problem_context(
    project_id: str,
    as_of: str,
    max_depth: int,
    api_base_url: str,
) -> dict[str, Any]:
    query = urlencode({"as_of": as_of, "max_depth": max_depth})
    url = f"{api_base_url}/api/v1/summaries/projects/{project_id}/problem-context?{query}"
    with urlopen(url, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


class ProjectBriefAgent:
    """Агент, который строит управленческий brief по fact context."""

    def __init__(self, *, temperature: float = 0.2) -> None:
        self.model = get_yandex_model_uri()
        self.client = get_yandex_client()
        self.temperature = temperature

    def build(self, problem_context: dict[str, Any]) -> ProjectManagerBrief:
        first_error = ""
        try:
            return _clean_brief(self._ask_llm(problem_context), problem_context)
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            first_error = str(exc)
            try:
                return _clean_brief(self._ask_llm(problem_context, bad_response=first_error), problem_context)
            except (json.JSONDecodeError, ValidationError, ValueError) as exc:
                raise RuntimeError(
                    "LLM вернула ответ не по JSON-контракту. "
                    f"Причина: {str(exc)[:700]}"
                ) from exc

    def _ask_llm(self, problem_context: dict[str, Any], bad_response: str | None = None) -> ProjectManagerBrief:
        prompt = build_user_prompt(problem_context, bad_response)
        response = self.client.responses.parse(
            model=self.model,
            instructions=SYSTEM_PROMPT,
            input=prompt,
            temperature=self.temperature,
            text_format=ProjectManagerBrief,
        )
        if response.output_parsed is None:
            raise ValueError("LLM вернула пустой parsed response")
        return response.output_parsed


def build_user_prompt(problem_context: dict[str, Any], bad_response: str | None = None) -> str:
    retry_note = ""
    if bad_response:
        retry_note = (
            "Предыдущий ответ был отклонен, потому что он не прошел JSON-контракт. "
            "Исправь структуру. Не вставляй технические id в текстовые поля, "
            "они должны быть только в evidence_ids.\n\n"
            f"Ошибка контракта:\n{bad_response[:700]}\n\n"
        )

    return (
        retry_note
        + "Сформируй управленческую рекомендацию по JSON problem context.\n"
        + "Не пересказывай видимые метрики. Найди узкое место, цепочку зависимостей, развилку решения, "
        + "business impact, поручение, черновик сообщения и follow-up проверку.\n"
        + "Ответ будет распарсен в строгую Pydantic-схему ProjectManagerBrief.\n\n"
        + "JSON problem context:\n"
        + json.dumps(problem_context, ensure_ascii=False)
    )


def fetch_problem_context_node(backend_api_url: str) -> Any:
    def fetch_problem_context(state: ProjectBriefData | dict[str, Any]) -> dict[str, Any]:
        as_of = state_value(state, "as_of")
        problem_context = fetch_project_problem_context(
            project_id=state_value(state, "project_id"),
            as_of=as_of.isoformat() if isinstance(as_of, date) else "2026-06-19",
            max_depth=state_value(state, "max_depth", 2),
            api_base_url=backend_api_url,
        )
        return {"problem_context": problem_context}

    return fetch_problem_context


def generate_brief_node(agent: Any) -> Any:
    def generate_brief(state: ProjectBriefData | dict[str, Any]) -> dict[str, Any]:
        problem_context = state_value(state, "problem_context")
        if problem_context is None:
            raise ValueError("Нет problem_context для генерации brief")

        brief = agent.build(problem_context)
        return {"brief": brief.model_dump(mode="json")}

    return generate_brief


def build_project_brief_graph(
    backend_api_url: str | None = None,
    agent: Any | None = None,
):
    if StateGraph is None or START is None or END is None:
        raise RuntimeError("LangGraph не установлен в окружении агента.")

    backend_api_url = backend_api_url or os.getenv("BACKEND_API_URL", "http://backend:8000")
    if agent is None:
        agent = ProjectBriefAgent()

    graph = StateGraph(ProjectBriefData)
    graph.add_node("fetch_problem_context", fetch_problem_context_node(backend_api_url))
    graph.add_node("generate_brief", generate_brief_node(agent))
    graph.add_edge(START, "fetch_problem_context")
    graph.add_edge("fetch_problem_context", "generate_brief")
    graph.add_edge("generate_brief", END)
    return graph.compile()


def run_project_brief(
    project_id: str,
    as_of: date | None = None,
    max_depth: int = 2,
    backend_api_url: str | None = None,
    agent: Any | None = None,
) -> ProjectManagerBrief:
    graph = build_project_brief_graph(backend_api_url=backend_api_url, agent=agent)
    initial_state = ProjectBriefData(project_id=project_id, as_of=as_of, max_depth=max_depth)
    result = graph.invoke(initial_state.model_dump())
    return ProjectManagerBrief.model_validate(result["brief"])


def _strip_technical_ids(value: str) -> str:
    value = re.sub(r"\s*\(\s*(?:T|TD|RK|C|D|DEC|CR|R|Р)\d{3}\s*\)", "", value)
    value = TECHNICAL_ID_RE.sub("", value)
    value = re.sub(r"[/#]\d{3}\b", "", value)
    value = re.sub(r"\s*->\s*(?:->\s*)+", " -> ", value)
    value = re.sub(r"^\s*->\s*|\s*->\s*$", "", value)
    value = re.sub(r"\(\s*\)", "", value)
    value = re.sub(r"\s{2,}", " ", value)
    value = re.sub(r"\s+([,.!?;:])", r"\1", value)
    return value.strip()


def _limit_text(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    trimmed = value[: limit - 1].rsplit(" ", 1)[0]
    return f"{trimmed}..."


def _clean_brief(brief: ProjectManagerBrief, problem_context: dict[str, Any]) -> ProjectManagerBrief:
    replacements = _build_id_replacements(problem_context)
    risk_level = problem_context.get("metrics", {}).get("risk_level")
    if risk_level == "red":
        brief.status = "критично"
    elif risk_level == "yellow":
        brief.status = "под наблюдением"
    elif risk_level == "green":
        brief.status = "в норме"

    brief.headline = _limit_text(_clean_text_value(brief.headline, replacements), 160)
    brief.management_question = _limit_text(_clean_text_value(brief.management_question, replacements), 260)
    brief.diagnosis = _limit_text(_clean_text_value(brief.diagnosis, replacements), 560)
    brief.bottleneck = _limit_text(_clean_text_value(brief.bottleneck, replacements), 260)
    brief.critical_path = [_limit_text(_clean_text_value(item, replacements), 180) for item in brief.critical_path]
    brief.recommended_move = _limit_text(_clean_text_value(brief.recommended_move, replacements), 360)
    brief.watchouts = [_limit_text(_clean_text_value(item, replacements), 220) for item in brief.watchouts]
    brief.business_impact.impact_summary = _limit_text(
        _clean_text_value(brief.business_impact.impact_summary, replacements),
        260,
    )
    for action in brief.next_actions:
        action.action = _limit_text(_clean_text_value(action.action, replacements), 220)
        action.owner_hint = _limit_text(_clean_text_value(action.owner_hint, replacements), 160)
        action.deadline = _limit_text(_clean_text_value(action.deadline, replacements), 120)
        action.success_signal = _limit_text(_clean_text_value(action.success_signal, replacements), 220)
    brief.draft_message.recipient_hint = _limit_text(
        _clean_text_value(brief.draft_message.recipient_hint, replacements),
        160,
    )
    brief.draft_message.subject = _limit_text(
        _clean_text_value(brief.draft_message.subject, replacements),
        160,
    )
    brief.draft_message.body = _limit_text(_clean_text_value(brief.draft_message.body, replacements), 560)
    brief.follow_up_check.check_after = _limit_text(
        _clean_text_value(brief.follow_up_check.check_after, replacements),
        120,
    )
    brief.follow_up_check.success_condition = _limit_text(
        _clean_text_value(brief.follow_up_check.success_condition, replacements),
        220,
    )
    brief.follow_up_check.escalation_condition = _limit_text(
        _clean_text_value(brief.follow_up_check.escalation_condition, replacements),
        220,
    )
    for option in brief.decision_options:
        option.option = _limit_text(_clean_text_value(option.option, replacements), 160)
        option.when_to_choose = _limit_text(_clean_text_value(option.when_to_choose, replacements), 220)
        option.tradeoff = _limit_text(_clean_text_value(option.tradeoff, replacements), 220)
    return brief


def _clean_text_value(value: str, replacements: dict[str, str]) -> str:
    for source_id, replacement in sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True):
        pattern = _id_pattern(source_id)
        value = re.sub(pattern, replacement, value)
    return _strip_technical_ids(value)


def _id_pattern(source_id: str) -> str:
    if source_id.startswith("R"):
        return rf"\b[RР]{re.escape(source_id[1:])}\b"
    return rf"\b{re.escape(source_id)}\b"


def _build_id_replacements(problem_context: dict[str, Any]) -> dict[str, str]:
    replacements: dict[str, str] = {}
    for task in problem_context.get("problem_tasks", []):
        replacements[task["id"]] = f"«{task['title']}»"
    for edge in problem_context.get("task_dependency_edges", []):
        replacements[edge["task_id"]] = f"«{edge['task_title']}»"
        replacements[edge["depends_on_task_id"]] = f"«{edge['depends_on_task_title']}»"
        replacements[edge["id"]] = "зависимость критического пути"
    for risk in problem_context.get("linked_risks", []):
        replacements[risk["id"]] = f"риск «{risk['risk_type']}»"
    for communication in problem_context.get("linked_communications", []):
        replacements[communication["id"]] = f"коммуникация «{communication['topic']}»"
    for dependency in problem_context.get("linked_project_dependencies", []):
        replacements[dependency["id"]] = f"зависимость «{dependency['depends_on']}»"
    for decision in problem_context.get("pending_decisions", []):
        replacements[decision["id"]] = f"решение «{decision['description']}»"
    for change_request in problem_context.get("open_change_requests", []):
        replacements[change_request["id"]] = f"change request «{change_request['description']}»"
    for resource in problem_context.get("overloaded_resources", []):
        replacements[resource["resource_id"]] = resource["full_name"]
    return replacements


def _parse_json(response_text: str) -> dict[str, Any]:
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", response_text, flags=re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))
