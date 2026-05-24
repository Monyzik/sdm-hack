from __future__ import annotations

import json
from datetime import date
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from agents.yandex_client import get_yandex_client, get_yandex_model_uri

try:
    from langgraph.graph import END, START, StateGraph
except ModuleNotFoundError:
    END = START = StateGraph = None


DEFAULT_AS_OF = "2026-06-19"


class ProjectQuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    as_of: date | None = None
    max_depth: int = Field(default=2, ge=1, le=4)


class ProjectQuestionAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str
    evidence_ids: list[str] = Field(default_factory=list)
    used_tools: list[str] = Field(default_factory=list)
    suggested_questions: list[str] = Field(default_factory=list)


class ProjectQuestionState(BaseModel):
    project_id: str
    question: str
    as_of: str
    max_depth: int = 2
    request_intent: str | None = None
    needs_project_tools: bool = True
    messages: list[dict[str, Any]] = Field(default_factory=list)
    pending_tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    used_tools: list[str] = Field(default_factory=list)
    tool_rounds: int = 0
    final_content: str | None = None


REQUEST_ROUTER_PROMPT = """
Ты роутер Q&A агента по проекту.

Верни только JSON:
{
  "intent": "small_talk | project_question | out_of_scope",
  "needs_project_tools": true | false,
  "reason": "коротко"
}

project_question означает, что пользователь спрашивает о статусе, сроках, бюджете, рисках,
задачах, блокерах, владельцах, решениях, зависимостях или других фактах выбранного проекта.
Для project_question всегда needs_project_tools=true.

small_talk и out_of_scope не должны получать проектные факты.
""".strip()


QA_SYSTEM_PROMPT = """
Ты Q&A агент AI Project Control Tower для руководителя проекта.

Если вопрос про проект, отвечай только по данным, которые получил через tools. Не выдумывай людей,
даты, суммы, причины, статусы и риски. Если данных не хватает, так и напиши.

Если пользователь просто здоровается, благодарит, проверяет связь или пишет не вопрос по проекту,
отвечай коротко без вызова project tools и без проектных фактов.

Правила:
- перед содержательным ответом по проекту вызови один или несколько tools;
- для small talk не используй project tools и не добавляй статус, бюджет, риски, задачи или evidence;
- для общих вопросов сначала вызови get_project_summary и get_problem_context;
- для уточнений используй search_tasks, search_risks, search_communications, search_decisions,
  search_dependencies или get_budget;
- финальный ответ верни только JSON-объектом ProjectQuestionAnswer;
- answer пиши по-русски, коротко, с конкретными пунктами;
- evidence_ids заполняй id фактов, на которых основан ответ;
- used_tools заполняй названиями реально использованных tools;
- suggested_questions дай 2-4 релевантных продолжения;
- не показывай внутренние рассуждения.

JSON schema:
{
  "answer": "string",
  "evidence_ids": ["string"],
  "used_tools": ["string"],
  "suggested_questions": ["string"]
}
""".strip()


QA_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_project_summary",
            "description": "Получить детерминированный summary проекта: метрики, health, сигналы и топ-сущности.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_problem_context",
            "description": "Получить контекст фактов: проблемные задачи, граф зависимостей, риски, коммуникации, решения, бюджет и ресурсы.",
            "parameters": {
                "type": "object",
                "properties": {
                    "max_depth": {"type": "integer", "minimum": 1, "maximum": 4},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_tasks",
            "description": "Найти проблемные, заблокированные и просроченные задачи по query/status/priority/assignee.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "status": {"type": "string"},
                    "priority": {"type": "string"},
                    "assignee": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 20},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_risks",
            "description": "Найти связанные и топовые риски проекта по query/status/min_score.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "status": {"type": "string"},
                    "min_score": {"type": "integer", "minimum": 0, "maximum": 25},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 20},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_communications",
            "description": "Найти просроченные или эскалированные коммуникации проекта по query/status/team.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "status": {"type": "string"},
                    "team": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 20},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_decisions",
            "description": "Найти ожидающие решения и открытые change requests.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {"type": "string"},
                    "owner": {"type": "string"},
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 20},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_dependencies",
            "description": "Найти проектные зависимости по query/status/criticality.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "status": {"type": "string"},
                    "criticality": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 20},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_budget",
            "description": "Получить бюджет проекта и влияние открытых change requests.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
]


def run_project_question(
    *,
    project_id: str,
    question: str,
    as_of: date | None = None,
    max_depth: int = 2,
    backend_api_url: str,
) -> ProjectQuestionAnswer:
    agent = ProjectQuestionAgent(backend_api_url=backend_api_url)
    return agent.answer(project_id=project_id, question=question, as_of=as_of, max_depth=max_depth)


class ProjectQuestionAgent:
    """Агент с языковой моделью и инструментами функций поверх фактов проекта."""

    def __init__(self, *, backend_api_url: str, temperature: float = 0.1) -> None:
        self.backend_api_url = backend_api_url.rstrip("/")
        self.model = get_yandex_model_uri()
        self.client = get_yandex_client()
        self.temperature = temperature

    def answer(
        self,
        *,
        project_id: str,
        question: str,
        as_of: date | None,
        max_depth: int,
    ) -> ProjectQuestionAnswer:
        as_of_value = as_of.isoformat() if as_of else DEFAULT_AS_OF
        tool_executor = ProjectFactToolExecutor(
            backend_api_url=self.backend_api_url,
            project_id=project_id,
            as_of=as_of_value,
            max_depth=max_depth,
        )
        graph = build_project_question_graph(
            client=self.client,
            model=self.model,
            tool_executor=tool_executor,
            temperature=self.temperature,
        )
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": QA_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"project_id={project_id}, as_of={as_of_value}\n"
                    f"Вопрос пользователя: {question}"
                ),
            },
        ]
        state = ProjectQuestionState(
            project_id=project_id,
            question=question,
            as_of=as_of_value,
            max_depth=max_depth,
            messages=messages,
        )
        result = graph.invoke(state.model_dump())
        return _parse_agent_answer(
            _state_value(result, "final_content", "{}") or "{}",
            _state_value(result, "used_tools", []),
            needs_project_tools=_state_value(result, "needs_project_tools", True),
        )


def build_project_question_graph(
    *,
    client: Any,
    model: str,
    tool_executor: "ProjectFactToolExecutor",
    temperature: float,
    max_tool_rounds: int = 5,
) -> Any:
    if StateGraph is None or START is None or END is None:
        raise RuntimeError("LangGraph не установлен в окружении агента.")

    graph = StateGraph(ProjectQuestionState)
    graph.add_node("route_request", route_request_node(client=client, model=model))
    graph.add_node("call_model", call_model_node(client=client, model=model, temperature=temperature))
    graph.add_node("run_tools", run_tools_node(tool_executor))
    graph.add_node("finalize", finalize_answer_node(client=client, model=model, temperature=temperature))

    graph.add_edge(START, "route_request")
    graph.add_conditional_edges(
        "route_request",
        route_after_request_router,
        {
            "model": "call_model",
            "finalize": "finalize",
        },
    )
    graph.add_conditional_edges(
        "call_model",
        route_after_model,
        {
            "tools": "run_tools",
            "done": END,
        },
    )
    graph.add_conditional_edges(
        "run_tools",
        route_after_tools(max_tool_rounds),
        {
            "model": "call_model",
            "finalize": "finalize",
        },
    )
    graph.add_edge("finalize", END)
    return graph.compile()


def route_request_node(*, client: Any, model: str) -> Any:
    def route_request(state: ProjectQuestionState | dict[str, Any]) -> dict[str, Any]:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": REQUEST_ROUTER_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"project_id={_state_value(state, 'project_id')}, "
                        f"as_of={_state_value(state, 'as_of')}\n"
                        f"Сообщение пользователя: {_state_value(state, 'question')}"
                    ),
                },
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or "{}"
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            payload = {}

        intent = str(payload.get("intent") or "project_question")
        if intent not in {"small_talk", "project_question", "out_of_scope"}:
            intent = "project_question"
        needs_project_tools = intent == "project_question" and bool(
            payload.get("needs_project_tools", True)
        )

        messages = [
            *_state_value(state, "messages", []),
            {
                "role": "assistant",
                "content": (
                    "Роутер запроса: "
                    + json.dumps(
                        {
                            "intent": intent,
                            "needs_project_tools": needs_project_tools,
                            "reason": payload.get("reason"),
                        },
                        ensure_ascii=False,
                    )
                ),
            },
        ]
        return {
            "messages": messages,
            "request_intent": intent,
            "needs_project_tools": needs_project_tools,
        }

    return route_request


def call_model_node(*, client: Any, model: str, temperature: float) -> Any:
    def call_model(state: ProjectQuestionState | dict[str, Any]) -> dict[str, Any]:
        response = client.chat.completions.create(
            model=model,
            messages=_state_value(state, "messages", []),
            tools=QA_TOOLS,
            tool_choice="required" if _state_value(state, "needs_project_tools", True) else "auto",
            temperature=temperature,
            response_format={"type": "json_object"},
        )
        message = response.choices[0].message
        tool_calls = _tool_calls_from_message(message)
        messages = [*_state_value(state, "messages", []), _assistant_message(message)]
        return {
            "messages": messages,
            "pending_tool_calls": tool_calls,
            "final_content": None if tool_calls else (message.content or "{}"),
        }

    return call_model


def run_tools_node(tool_executor: "ProjectFactToolExecutor") -> Any:
    def run_tools(state: ProjectQuestionState | dict[str, Any]) -> dict[str, Any]:
        messages = list(_state_value(state, "messages", []))
        used_tools = list(_state_value(state, "used_tools", []))

        for tool_call in _state_value(state, "pending_tool_calls", []):
            tool_name = str(tool_call.get("name") or "")
            used_tools.append(tool_name)
            arguments = _parse_tool_arguments(tool_call.get("arguments"))
            result = tool_executor.execute(tool_name, arguments)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.get("id"),
                    "name": tool_name,
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )

        return {
            "messages": messages,
            "pending_tool_calls": [],
            "used_tools": _unique(used_tools),
            "tool_rounds": int(_state_value(state, "tool_rounds", 0) or 0) + 1,
        }

    return run_tools


def finalize_answer_node(*, client: Any, model: str, temperature: float) -> Any:
    def finalize_answer(state: ProjectQuestionState | dict[str, Any]) -> dict[str, Any]:
        if _state_value(state, "needs_project_tools", True):
            final_instruction = "Сформируй финальный JSON ProjectQuestionAnswer по уже полученным tool results."
        else:
            final_instruction = (
                "Сформируй финальный JSON ProjectQuestionAnswer без проектных фактов, "
                "evidence_ids и рекомендаций по проекту."
            )
        messages = [
            *_state_value(state, "messages", []),
            {
                "role": "user",
                "content": final_instruction,
            },
        ]
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=QA_TOOLS,
            tool_choice="none",
            temperature=temperature,
            response_format={"type": "json_object"},
        )
        message = response.choices[0].message
        return {
            "messages": [*messages, _assistant_message(message)],
            "pending_tool_calls": [],
            "final_content": message.content or "{}",
        }

    return finalize_answer


def route_after_request_router(state: ProjectQuestionState | dict[str, Any]) -> str:
    if _state_value(state, "needs_project_tools", True):
        return "model"
    return "finalize"


def route_after_model(state: ProjectQuestionState | dict[str, Any]) -> str:
    if _state_value(state, "pending_tool_calls", []):
        return "tools"
    return "done"


def route_after_tools(max_tool_rounds: int) -> Any:
    def route(state: ProjectQuestionState | dict[str, Any]) -> str:
        if int(_state_value(state, "tool_rounds", 0) or 0) >= max_tool_rounds:
            return "finalize"
        return "model"

    return route


class ProjectFactToolExecutor:
    """Исполнитель инструментов, который читает факты проекта из API бэкенда."""

    def __init__(self, *, backend_api_url: str, project_id: str, as_of: str, max_depth: int) -> None:
        self.backend_api_url = backend_api_url.rstrip("/")
        self.project_id = project_id
        self.as_of = as_of
        self.max_depth = max_depth
        self._summary: dict[str, Any] | None = None
        self._context: dict[str, Any] | None = None
        self._context_depth: int | None = None

    def execute(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if tool_name == "get_project_summary":
            return self.project_summary()
        if tool_name == "get_problem_context":
            max_depth = _bounded_limit(arguments.get("max_depth"), default=self.max_depth, maximum=4)
            return self.problem_context(max_depth=max_depth)
        if tool_name == "search_tasks":
            return self.search_tasks(arguments)
        if tool_name == "search_risks":
            return self.search_risks(arguments)
        if tool_name == "search_communications":
            return self.search_communications(arguments)
        if tool_name == "search_decisions":
            return self.search_decisions(arguments)
        if tool_name == "search_dependencies":
            return self.search_dependencies(arguments)
        if tool_name == "get_budget":
            return self.budget()
        return {"error": f"Неизвестный tool: {tool_name}"}

    def project_summary(self) -> dict[str, Any]:
        if self._summary is None:
            query = urlencode({"as_of": self.as_of})
            self._summary = self._fetch_json(f"/api/v1/summaries/projects/{self.project_id}?{query}")
        return self._summary

    def problem_context(self, max_depth: int | None = None) -> dict[str, Any]:
        depth = max_depth or self.max_depth
        if self._context is None or depth != self._context_depth:
            query = urlencode({"as_of": self.as_of, "max_depth": depth})
            self._context = self._fetch_json(
                f"/api/v1/summaries/projects/{self.project_id}/problem-context?{query}"
            )
            self._context_depth = depth
        return self._context

    def search_tasks(self, arguments: dict[str, Any]) -> dict[str, Any]:
        summary = self.project_summary()
        context = self.problem_context()
        items = _dedupe_items(
            [
                *context.get("problem_tasks", []),
                *summary.get("blocked_tasks", []),
                *summary.get("overdue_tasks", []),
            ]
        )
        items = _filter_items(
            items,
            query=arguments.get("query"),
            query_fields=("title", "blocker_reason", "assignee_name", "status", "priority"),
            exact_filters={
                "status": arguments.get("status"),
                "priority": arguments.get("priority"),
                "assignee_name": arguments.get("assignee"),
            },
        )
        return _tool_result(items, arguments.get("limit"))

    def search_risks(self, arguments: dict[str, Any]) -> dict[str, Any]:
        summary = self.project_summary()
        context = self.problem_context()
        items = _dedupe_items([*context.get("linked_risks", []), *summary.get("top_risks", [])])
        min_score = _optional_int(arguments.get("min_score"))
        items = _filter_items(
            items,
            query=arguments.get("query"),
            query_fields=("risk_type", "description", "status", "owner_name"),
            exact_filters={"status": arguments.get("status")},
        )
        if min_score is not None:
            items = [item for item in items if int(item.get("score") or 0) >= min_score]
        return _tool_result(items, arguments.get("limit"))

    def search_communications(self, arguments: dict[str, Any]) -> dict[str, Any]:
        summary = self.project_summary()
        context = self.problem_context()
        items = _dedupe_items(
            [
                *context.get("linked_communications", []),
                *summary.get("delayed_communications", []),
            ]
        )
        team = arguments.get("team")
        items = _filter_items(
            items,
            query=arguments.get("query"),
            query_fields=("topic", "from_team", "to_team", "status", "importance"),
            exact_filters={"status": arguments.get("status")},
        )
        if team:
            needle = str(team).casefold()
            items = [
                item
                for item in items
                if needle in str(item.get("from_team", "")).casefold()
                or needle in str(item.get("to_team", "")).casefold()
            ]
        return _tool_result(items, arguments.get("limit"))

    def search_decisions(self, arguments: dict[str, Any]) -> dict[str, Any]:
        summary = self.project_summary()
        context = self.problem_context()
        items = _dedupe_items(
            [
                *context.get("pending_decisions", []),
                *summary.get("pending_decisions", []),
                *context.get("open_change_requests", []),
                *summary.get("open_change_requests", []),
            ]
        )
        owner = arguments.get("owner")
        items = _filter_items(
            items,
            query=arguments.get("query"),
            query_fields=("description", "decision_owner", "requested_by", "status", "change_type"),
            exact_filters={"status": arguments.get("status")},
        )
        if owner:
            needle = str(owner).casefold()
            items = [
                item
                for item in items
                if needle in str(item.get("decision_owner", "")).casefold()
                or needle in str(item.get("requested_by", "")).casefold()
            ]
        return _tool_result(items, arguments.get("limit"))

    def search_dependencies(self, arguments: dict[str, Any]) -> dict[str, Any]:
        summary = self.project_summary()
        context = self.problem_context()
        items = _dedupe_items(
            [
                *context.get("linked_project_dependencies", []),
                *summary.get("risky_dependencies", []),
            ]
        )
        items = _filter_items(
            items,
            query=arguments.get("query"),
            query_fields=("depends_on", "owner_team", "status", "criticality", "dependency_type"),
            exact_filters={
                "status": arguments.get("status"),
                "criticality": arguments.get("criticality"),
            },
        )
        return _tool_result(items, arguments.get("limit"))

    def budget(self) -> dict[str, Any]:
        summary = self.project_summary()
        context = self.problem_context()
        return {
            "budget": summary.get("budget"),
            "budget_metrics": {
                "budget_deviation_percent": summary.get("budget", {}).get("budget_deviation_percent")
                if summary.get("budget")
                else None,
                "roi_percent": summary.get("budget", {}).get("roi_percent") if summary.get("budget") else None,
                "risk_adjusted_roi_percent": summary.get("budget", {}).get("risk_adjusted_roi_percent")
                if summary.get("budget")
                else None,
                "net_change_request_impact_days": summary.get("net_change_request_impact_days"),
                "net_change_request_impact_budget": summary.get("net_change_request_impact_budget"),
                "cost_of_delay_exposure": summary.get("cost_of_delay_exposure"),
            },
            "open_change_requests": context.get("open_change_requests", []),
        }

    def _fetch_json(self, path: str) -> dict[str, Any]:
        request = Request(f"{self.backend_api_url}{path}", headers={"Accept": "application/json"})
        with urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))


def _state_value(state: ProjectQuestionState | dict[str, Any], key: str, default: Any = None) -> Any:
    if isinstance(state, ProjectQuestionState):
        return getattr(state, key)
    return state.get(key, default)


def _assistant_message(message: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"role": "assistant", "content": message.content or ""}
    tool_calls = _tool_calls_from_message(message)
    if tool_calls:
        payload["tool_calls"] = [
            {
                "id": tool_call["id"],
                "type": "function",
                "function": {
                    "name": tool_call["name"],
                    "arguments": tool_call["arguments"],
                },
            }
            for tool_call in tool_calls
        ]
    return payload


def _tool_calls_from_message(message: Any) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for tool_call in message.tool_calls or []:
        result.append(
            {
                "id": str(tool_call.id),
                "name": str(tool_call.function.name),
                "arguments": str(tool_call.function.arguments or "{}"),
            }
        )
    return result


def _parse_tool_arguments(raw_arguments: Any) -> dict[str, Any]:
    if isinstance(raw_arguments, dict):
        return raw_arguments
    if not raw_arguments:
        return {}
    try:
        parsed = json.loads(str(raw_arguments))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _parse_agent_answer(
    content: str,
    used_tools: list[Any],
    *,
    needs_project_tools: bool = True,
) -> ProjectQuestionAnswer:
    actual_tools = _unique(used_tools)
    if needs_project_tools and not actual_tools:
        raise ValueError("Q&A-агент ответил по проектному вопросу без вызова tools.")
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as error:
        text = content.strip()
        if not text:
            raise ValueError("Модель вернула пустой ответ для Q&A.") from error
        return ProjectQuestionAnswer(answer=text, used_tools=actual_tools)
    try:
        answer = ProjectQuestionAnswer.model_validate(payload)
    except ValidationError as error:
        raise ValueError("Модель вернула JSON не по контракту ProjectQuestionAnswer.") from error

    answer.used_tools = actual_tools
    answer.evidence_ids = _unique(answer.evidence_ids)[:20]
    answer.suggested_questions = _unique(answer.suggested_questions)[:4]
    return answer


def _dedupe_items(items: list[Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        item_key = item.get("id") or item.get("resource_id")
        key = str(item_key) if item_key else json.dumps(item, ensure_ascii=False, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _filter_items(
    items: list[dict[str, Any]],
    *,
    query: Any,
    query_fields: tuple[str, ...],
    exact_filters: dict[str, Any],
) -> list[dict[str, Any]]:
    filtered = list(items)
    if query:
        needle = str(query).casefold()
        filtered = [
            item
            for item in filtered
            if any(needle in str(item.get(field, "")).casefold() for field in query_fields)
        ]

    for field, expected in exact_filters.items():
        if expected is None or expected == "":
            continue
        needle = str(expected).casefold()
        filtered = [item for item in filtered if needle in str(item.get(field, "")).casefold()]
    return filtered


def _tool_result(items: list[dict[str, Any]], limit: Any) -> dict[str, Any]:
    limit_value = _bounded_limit(limit, default=10)
    return {
        "count": len(items),
        "items": items[:limit_value],
    }


def _bounded_limit(value: Any, default: int, minimum: int = 1, maximum: int = 20) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(minimum, min(maximum, number))


def _optional_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _unique(values: list[Any]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value is None:
            continue
        text = str(value)
        if text not in result:
            result.append(text)
    return result
