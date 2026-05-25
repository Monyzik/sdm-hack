from __future__ import annotations

import json
from datetime import date
from typing import Annotated, Any, Callable, TypedDict
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from agents.yandex_client import get_yandex_client, get_yandex_model_uri

try:
    from langgraph.graph import END, START, StateGraph
    from langgraph.graph.message import add_messages
    from langgraph.prebuilt import ToolNode
    from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
    from langchain_core.tools import BaseTool, StructuredTool
    from langchain_core.utils.function_calling import convert_to_openai_tool
except ModuleNotFoundError:
    END = START = StateGraph = None
    add_messages = None
    ToolNode = None
    AIMessage = BaseMessage = HumanMessage = SystemMessage = ToolMessage = None
    BaseTool = StructuredTool = None
    convert_to_openai_tool = None


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


class ProjectQuestionState(TypedDict, total=False):
    project_id: str
    question: str
    as_of: str
    max_depth: int
    request_intent: str | None
    needs_project_tools: bool
    messages: Annotated[list[Any], add_messages]
    used_tools: list[str]
    tool_rounds: int
    final_content: str | None


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


class NoArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProblemContextArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_depth: int | None = Field(default=None, ge=1, le=4)


class SearchTasksArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str | None = None
    status: str | None = None
    priority: str | None = None
    assignee: str | None = None
    limit: int | None = Field(default=None, ge=1, le=20)


class SearchRisksArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str | None = None
    status: str | None = None
    min_score: int | None = Field(default=None, ge=0, le=25)
    limit: int | None = Field(default=None, ge=1, le=20)


class SearchCommunicationsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str | None = None
    status: str | None = None
    team: str | None = None
    limit: int | None = Field(default=None, ge=1, le=20)


class SearchDecisionsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str | None = None
    status: str | None = None
    owner: str | None = None
    limit: int | None = Field(default=None, ge=1, le=20)


class SearchDependenciesArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str | None = None
    status: str | None = None
    criticality: str | None = None
    limit: int | None = Field(default=None, ge=1, le=20)


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
        messages = [
            SystemMessage(content=QA_SYSTEM_PROMPT),
            HumanMessage(
                content=(
                    f"project_id={project_id}, as_of={as_of_value}\n"
                    f"Вопрос пользователя: {question}"
                )
            ),
        ]
        state: ProjectQuestionState = {
            "project_id": project_id,
            "question": question,
            "as_of": as_of_value,
            "max_depth": max_depth,
            "messages": messages,
            "used_tools": [],
            "tool_rounds": 0,
        }
        result = graph.invoke(state)
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
    max_tool_rounds: int = 3,
) -> Any:
    if (
        StateGraph is None
        or START is None
        or END is None
        or ToolNode is None
        or StructuredTool is None
        or convert_to_openai_tool is None
    ):
        raise RuntimeError("LangGraph не установлен в окружении агента.")

    tools = build_project_tools(tool_executor)
    tool_specs = [convert_to_openai_tool(tool) for tool in tools]

    graph = StateGraph(ProjectQuestionState)
    graph.add_node("route_request", route_request_node(client=client, model=model))
    graph.add_node(
        "call_model",
        call_model_node(client=client, model=model, tools=tool_specs, temperature=temperature),
    )
    graph.add_node("run_tools", run_tools_node(tools))
    graph.add_node(
        "finalize",
        finalize_answer_node(client=client, model=model, tools=tool_specs, temperature=temperature),
    )

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

        return {
            "request_intent": intent,
            "needs_project_tools": needs_project_tools,
        }

    return route_request


def call_model_node(*, client: Any, model: str, tools: list[dict[str, Any]], temperature: float) -> Any:
    def call_model(state: ProjectQuestionState | dict[str, Any]) -> dict[str, Any]:
        needs_project_tools = _state_value(state, "needs_project_tools", True)
        used_tools = _state_value(state, "used_tools", [])
        response = client.chat.completions.create(
            model=model,
            messages=_messages_to_openai(_state_value(state, "messages", [])),
            tools=tools,
            tool_choice="required" if needs_project_tools and not used_tools else "auto",
            temperature=temperature,
            response_format={"type": "json_object"},
        )
        message = response.choices[0].message
        ai_message = _ai_message_from_openai(message)
        return {
            "messages": [ai_message],
            "final_content": None if ai_message.tool_calls else (message.content or "{}"),
        }

    return call_model


def run_tools_node(tools: list[Any]) -> Any:
    tool_node = ToolNode(tools)

    def run_tools(state: ProjectQuestionState | dict[str, Any]) -> dict[str, Any]:
        used_tools = list(_state_value(state, "used_tools", []))
        result = tool_node.invoke(state)
        tool_messages = _state_value(result, "messages", [])
        used_tools.extend(_tool_names_from_messages(tool_messages))

        return {
            "messages": tool_messages,
            "used_tools": _unique(used_tools),
            "tool_rounds": int(_state_value(state, "tool_rounds", 0) or 0) + 1,
        }

    return run_tools


def finalize_answer_node(*, client: Any, model: str, tools: list[dict[str, Any]], temperature: float) -> Any:
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
            HumanMessage(content=final_instruction),
        ]
        response = client.chat.completions.create(
            model=model,
            messages=_messages_to_openai(messages),
            tools=tools,
            tool_choice="none",
            temperature=temperature,
            response_format={"type": "json_object"},
        )
        message = response.choices[0].message
        return {
            "messages": [HumanMessage(content=final_instruction), _ai_message_from_openai(message)],
            "final_content": message.content or "{}",
        }

    return finalize_answer


def route_after_request_router(state: ProjectQuestionState | dict[str, Any]) -> str:
    if _state_value(state, "needs_project_tools", True):
        return "model"
    return "finalize"


def route_after_model(state: ProjectQuestionState | dict[str, Any]) -> str:
    last_message = _last_message(_state_value(state, "messages", []))
    if getattr(last_message, "tool_calls", None):
        return "tools"
    return "done"


def route_after_tools(max_tool_rounds: int) -> Any:
    def route(state: ProjectQuestionState | dict[str, Any]) -> str:
        if int(_state_value(state, "tool_rounds", 0) or 0) >= max_tool_rounds:
            return "finalize"
        return "model"

    return route


def build_project_tools(tool_executor: "ProjectFactToolExecutor") -> list[BaseTool]:
    """Create request-scoped LangChain tools for LangGraph ToolNode."""

    def get_project_summary() -> dict[str, Any]:
        return _compact_project_summary(tool_executor.project_summary())

    def get_problem_context(max_depth: int | None = None) -> dict[str, Any]:
        depth = _bounded_limit(max_depth, default=tool_executor.max_depth, maximum=4)
        return _compact_problem_context(tool_executor.problem_context(max_depth=depth))

    def search_tasks(
        query: str | None = None,
        status: str | None = None,
        priority: str | None = None,
        assignee: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        result = tool_executor.search_tasks(
            {
                "query": query,
                "status": status,
                "priority": priority,
                "assignee": assignee,
                "limit": limit,
            }
        )
        return _compact_search_result(result, TASK_FIELDS)

    def search_risks(
        query: str | None = None,
        status: str | None = None,
        min_score: int | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        result = tool_executor.search_risks(
            {
                "query": query,
                "status": status,
                "min_score": min_score,
                "limit": limit,
            }
        )
        return _compact_search_result(result, RISK_FIELDS)

    def search_communications(
        query: str | None = None,
        status: str | None = None,
        team: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        result = tool_executor.search_communications(
            {
                "query": query,
                "status": status,
                "team": team,
                "limit": limit,
            }
        )
        return _compact_search_result(result, COMMUNICATION_FIELDS)

    def search_decisions(
        query: str | None = None,
        status: str | None = None,
        owner: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        result = tool_executor.search_decisions(
            {
                "query": query,
                "status": status,
                "owner": owner,
                "limit": limit,
            }
        )
        return _compact_search_result(result, DECISION_FIELDS + CHANGE_REQUEST_FIELDS)

    def search_dependencies(
        query: str | None = None,
        status: str | None = None,
        criticality: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        result = tool_executor.search_dependencies(
            {
                "query": query,
                "status": status,
                "criticality": criticality,
                "limit": limit,
            }
        )
        return _compact_search_result(result, DEPENDENCY_FIELDS)

    def get_budget() -> dict[str, Any]:
        return _compact_budget_result(tool_executor.budget())

    def make_tool(
        *,
        name: str,
        description: str,
        args_schema: type[BaseModel],
        func: Callable[..., dict[str, Any]],
    ) -> BaseTool:
        return StructuredTool.from_function(
            func=func,
            name=name,
            description=description,
            args_schema=args_schema,
        )

    return [
        make_tool(
            name="get_project_summary",
            description="Получить детерминированный summary проекта: метрики, health, сигналы и топ-сущности.",
            args_schema=NoArgs,
            func=get_project_summary,
        ),
        make_tool(
            name="get_problem_context",
            description=(
                "Получить контекст фактов: проблемные задачи, граф зависимостей, риски, "
                "коммуникации, решения, бюджет и ресурсы."
            ),
            args_schema=ProblemContextArgs,
            func=get_problem_context,
        ),
        make_tool(
            name="search_tasks",
            description="Найти проблемные, заблокированные и просроченные задачи по query/status/priority/assignee.",
            args_schema=SearchTasksArgs,
            func=search_tasks,
        ),
        make_tool(
            name="search_risks",
            description="Найти связанные и топовые риски проекта по query/status/min_score.",
            args_schema=SearchRisksArgs,
            func=search_risks,
        ),
        make_tool(
            name="search_communications",
            description="Найти просроченные или эскалированные коммуникации проекта по query/status/team.",
            args_schema=SearchCommunicationsArgs,
            func=search_communications,
        ),
        make_tool(
            name="search_decisions",
            description="Найти ожидающие решения и открытые change requests.",
            args_schema=SearchDecisionsArgs,
            func=search_decisions,
        ),
        make_tool(
            name="search_dependencies",
            description="Найти проектные зависимости по query/status/criticality.",
            args_schema=SearchDependenciesArgs,
            func=search_dependencies,
        ),
        make_tool(
            name="get_budget",
            description="Получить бюджет проекта и влияние открытых change requests.",
            args_schema=NoArgs,
            func=get_budget,
        ),
    ]


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
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


def _messages_to_openai(messages: list[Any]) -> list[dict[str, Any]]:
    return [_message_to_openai(message) for message in messages]


def _message_to_openai(message: Any) -> dict[str, Any]:
    if isinstance(message, dict):
        return message

    if SystemMessage is not None and isinstance(message, SystemMessage):
        return {"role": "system", "content": _message_content(message.content)}

    if HumanMessage is not None and isinstance(message, HumanMessage):
        return {"role": "user", "content": _message_content(message.content)}

    if AIMessage is not None and isinstance(message, AIMessage):
        payload: dict[str, Any] = {"role": "assistant", "content": _message_content(message.content)}
        if message.tool_calls:
            payload["tool_calls"] = [
                {
                    "id": str(tool_call.get("id")),
                    "type": "function",
                    "function": {
                        "name": str(tool_call.get("name")),
                        "arguments": json.dumps(tool_call.get("args") or {}, ensure_ascii=False),
                    },
                }
                for tool_call in message.tool_calls
            ]
        return payload

    if ToolMessage is not None and isinstance(message, ToolMessage):
        payload = {
            "role": "tool",
            "tool_call_id": message.tool_call_id,
            "content": _message_content(message.content),
        }
        if message.name:
            payload["name"] = message.name
        return payload

    role = getattr(message, "type", "user")
    return {"role": "assistant" if role == "ai" else role, "content": _message_content(message.content)}


def _ai_message_from_openai(message: Any) -> Any:
    tool_calls = []
    for tool_call in message.tool_calls or []:
        tool_calls.append(
            {
                "id": str(tool_call.id),
                "name": str(tool_call.function.name),
                "args": _parse_tool_arguments(tool_call.function.arguments),
            }
        )
    return AIMessage(content=message.content or "", tool_calls=tool_calls)


def _last_message(messages: list[Any]) -> Any | None:
    return messages[-1] if messages else None


def _tool_names_from_messages(messages: list[Any]) -> list[str]:
    names: list[str] = []
    for message in messages:
        name = getattr(message, "name", None)
        if name:
            names.append(str(name))
    return names


def _message_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(str(part) for part in content)
    return json.dumps(content, ensure_ascii=False) if isinstance(content, dict) else str(content)


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


SUMMARY_FIELDS = (
    "project_id",
    "project_name",
    "owner_name",
    "status",
    "priority",
    "as_of_date",
    "completion_percent",
    "total_tasks_count",
    "completed_tasks_count",
    "overdue_tasks_count",
    "delayed_milestones_count",
    "blocked_tasks_count",
    "high_risk_count",
    "dependency_risk_count",
    "pending_decision_count",
    "open_change_request_count",
    "dependency_sla_breach_count",
    "milestone_slip_days",
    "critical_path_delay_days",
    "blocked_age_days",
    "decision_age_days",
    "net_change_request_impact_days",
    "net_change_request_impact_budget",
    "scope_churn_rate",
    "burn_rate_percent",
    "schedule_variance_percent",
    "stale_tasks_count",
    "max_status_age_days",
    "estimate_overrun_percent",
    "workload_imbalance_index",
    "key_person_dependency_percent",
    "critical_task_silence_days",
    "communication_silence_days",
    "data_freshness_days",
    "cost_of_delay_exposure",
    "risk_trend",
    "resource_overload_percent",
    "max_communication_delay_days",
    "project_health_score",
    "risk_level",
    "executive_summary",
)
PROJECT_FIELDS = (
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
)
METRIC_FIELDS = tuple(
    field
    for field in SUMMARY_FIELDS
    if field
    not in {
        "project_id",
        "project_name",
        "owner_name",
        "status",
        "priority",
        "as_of_date",
        "executive_summary",
    }
)
BUDGET_FIELDS = (
    "planned_budget",
    "actual_spent",
    "forecast_total_spent",
    "expected_economic_effect",
    "cost_of_delay_per_day",
    "currency",
    "budget_deviation_percent",
    "roi_percent",
    "risk_adjusted_roi_percent",
)
TASK_FIELDS = (
    "id",
    "external_id",
    "title",
    "assignee_name",
    "status",
    "priority",
    "planned_due_date",
    "actual_end_date",
    "estimated_hours",
    "spent_hours",
    "is_blocked",
    "blocker_reason",
    "overdue_days",
    "problem_flags",
)
TASK_EDGE_FIELDS = (
    "id",
    "root_task_id",
    "direction",
    "depth",
    "task_id",
    "task_title",
    "depends_on_task_id",
    "depends_on_task_title",
    "dependency_type",
    "is_critical_path",
    "lag_days",
    "reason",
)
RISK_FIELDS = (
    "id",
    "risk_type",
    "description",
    "probability",
    "impact",
    "score",
    "status",
    "owner_name",
    "linked_task_id",
)
COMMUNICATION_FIELDS = (
    "id",
    "from_team",
    "to_team",
    "topic",
    "status",
    "importance",
    "expected_response_date",
    "delay_days",
    "linked_task_id",
)
DEPENDENCY_FIELDS = (
    "id",
    "dependency_type",
    "depends_on",
    "owner_team",
    "expected_date",
    "status",
    "criticality",
    "linked_task_id",
    "delay_days",
)
DECISION_FIELDS = ("id", "decision_type", "description", "decision_owner", "status", "decision_date")
CHANGE_REQUEST_FIELDS = ("id", "change_type", "requested_by", "status", "impact_budget", "impact_days", "description")
RESOURCE_FIELDS = (
    "resource_id",
    "full_name",
    "role",
    "team",
    "available_hours_per_week",
    "project_actual_hours_per_week",
    "total_actual_hours_per_week",
    "total_allocation_percent",
    "overload_percent",
)
HISTORY_FIELDS = ("id", "task_id", "changed_at", "field_changed", "old_value", "new_value", "changed_by")
COMMENT_FIELDS = ("id", "task_id", "author_name", "created_at", "channel", "text", "mentions_count")


def _compact_project_summary(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        **_pick(summary, SUMMARY_FIELDS),
        "key_signals": _compact_list(summary.get("key_signals", []), limit=8),
        "budget": _pick(summary.get("budget"), BUDGET_FIELDS),
        "blocked_tasks": _compact_items(summary.get("blocked_tasks", []), TASK_FIELDS, limit=6),
        "overdue_tasks": _compact_items(summary.get("overdue_tasks", []), TASK_FIELDS, limit=6),
        "delayed_milestones": _compact_items(
            summary.get("delayed_milestones", []),
            ("id", "name", "status", "planned_end_date", "delay_days", "responsible_team"),
            limit=6,
        ),
        "top_risks": _compact_items(summary.get("top_risks", []), RISK_FIELDS, limit=6),
        "delayed_communications": _compact_items(
            summary.get("delayed_communications", []),
            COMMUNICATION_FIELDS,
            limit=6,
        ),
        "overloaded_resources": _compact_items(
            summary.get("overloaded_resources", []),
            RESOURCE_FIELDS,
            limit=6,
        ),
        "risky_dependencies": _compact_items(
            summary.get("risky_dependencies", []),
            DEPENDENCY_FIELDS,
            limit=6,
        ),
        "pending_decisions": _compact_items(summary.get("pending_decisions", []), DECISION_FIELDS, limit=6),
        "open_change_requests": _compact_items(
            summary.get("open_change_requests", []),
            CHANGE_REQUEST_FIELDS,
            limit=6,
        ),
    }


def _compact_problem_context(context: dict[str, Any]) -> dict[str, Any]:
    return {
        "project": _pick(context.get("project"), PROJECT_FIELDS),
        "as_of_date": context.get("as_of_date"),
        "metrics": _pick(context.get("metrics"), METRIC_FIELDS),
        "budget": _pick(context.get("budget"), BUDGET_FIELDS),
        "problem_tasks": _compact_items(context.get("problem_tasks", []), TASK_FIELDS, limit=8),
        "task_dependency_edges": _compact_items(
            context.get("task_dependency_edges", []),
            TASK_EDGE_FIELDS,
            limit=12,
        ),
        "linked_risks": _compact_items(context.get("linked_risks", []), RISK_FIELDS, limit=8),
        "linked_communications": _compact_items(
            context.get("linked_communications", []),
            COMMUNICATION_FIELDS,
            limit=8,
        ),
        "linked_project_dependencies": _compact_items(
            context.get("linked_project_dependencies", []),
            DEPENDENCY_FIELDS,
            limit=8,
        ),
        "pending_decisions": _compact_items(context.get("pending_decisions", []), DECISION_FIELDS, limit=8),
        "open_change_requests": _compact_items(
            context.get("open_change_requests", []),
            CHANGE_REQUEST_FIELDS,
            limit=8,
        ),
        "overloaded_resources": _compact_items(
            context.get("overloaded_resources", []),
            RESOURCE_FIELDS,
            limit=8,
        ),
        "recent_task_history": _compact_items(context.get("recent_task_history", []), HISTORY_FIELDS, limit=6),
        "recent_task_comments": _compact_items(context.get("recent_task_comments", []), COMMENT_FIELDS, limit=6),
    }


def _compact_search_result(result: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    return {
        "count": result.get("count", 0),
        "items": _compact_items(result.get("items", []), fields, limit=10),
    }


def _compact_budget_result(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "budget": _pick(result.get("budget"), BUDGET_FIELDS),
        "budget_metrics": _compact_value(result.get("budget_metrics", {})),
        "open_change_requests": _compact_items(
            result.get("open_change_requests", []),
            CHANGE_REQUEST_FIELDS,
            limit=8,
        ),
    }


def _compact_items(items: Any, fields: tuple[str, ...], *, limit: int) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    return [_pick(item, fields) for item in items[:limit] if isinstance(item, dict)]


def _pick(item: Any, fields: tuple[str, ...]) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {}
    result: dict[str, Any] = {}
    for field in fields:
        if field not in item or item[field] is None:
            continue
        result[field] = _compact_value(item[field])
    return result


def _compact_list(items: Any, *, limit: int) -> list[Any]:
    if not isinstance(items, list):
        return []
    return [_compact_value(item) for item in items[:limit]]


def _compact_value(value: Any) -> Any:
    if isinstance(value, str):
        return _limit_text(value, 260)
    if isinstance(value, list):
        return [_compact_value(item) for item in value[:12]]
    if isinstance(value, dict):
        return {key: _compact_value(item) for key, item in value.items() if item is not None}
    return value


def _limit_text(value: str, limit: int) -> str:
    text = " ".join(value.split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


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
