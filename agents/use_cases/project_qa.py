from __future__ import annotations

import json
from datetime import date
from typing import Annotated, Any, Awaitable, Callable, Literal, TypedDict
from urllib.parse import urlencode

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from agents.infrastructure.llm import LLMAdapter, get_llm_adapter
from backend.app.schemas.project_summary import ProjectMetricsFact, ProjectSummary

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
TOOL_ARGUMENT_ALIASES = {
    "assignee_in": "assignee",
    "criticality_in": "criticality",
    "limit_in": "limit",
    "min_score_gte": "min_score",
    "owner_in": "owner",
    "priority_in": "priority",
    "status_in": "status",
    "team_in": "team",
}


class ProjectConversationMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=800)


class ProjectQuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    as_of: date | None = None
    max_depth: int = Field(default=2, ge=1, le=4)
    conversation_context: list[ProjectConversationMessage] = Field(default_factory=list, max_length=8)


class ProjectQuestionAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str
    evidence_ids: list[str] = Field(default_factory=list)
    used_tools: list[str] = Field(default_factory=list)
    suggested_questions: list[str] = Field(default_factory=list)


class RequestRoute(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: Literal["small_talk", "project_question", "out_of_scope"] = "project_question"
    needs_project_tools: bool = True
    reason: str = ""


class ToolArgsModel(BaseModel):
    model_config = ConfigDict(extra="ignore")

    @model_validator(mode="before")
    @classmethod
    def normalize_tool_arguments(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value

        normalized = dict(value)
        for source, target in TOOL_ARGUMENT_ALIASES.items():
            if target in normalized or source not in normalized:
                continue
            normalized[target] = _first_argument_value(normalized[source])
        return normalized


class ProjectQuestionState(TypedDict, total=False):
    project_id: str
    question: str
    as_of: str
    max_depth: int
    conversation_context: str
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
  search_dependencies, get_budget, get_resource_rates, get_task_dependency_graph или calculate_delay_cost;
- для вопросов "почему", "что обсуждали", "какая история", "что уже решили", "кто писал" и
  "почему заблокировано" обязательно используй search_project_evidence вместе со структурными tools;
- для вопросов с расчетами используй calculate_delay_cost или другой подходящий tool; не считай арифметику в тексте самостоятельно;
- финальный ответ верни только JSON-объектом ProjectQuestionAnswer;
- answer пиши по-русски, коротко, с конкретными пунктами;
- если сравниваешь несколько задач, рисков, ресурсов, сроков, сумм или вариантов, используй markdown-таблицу;
- перед таблицей дай короткий вывод в 1-2 предложения, что важно увидеть руководителю;
- таблицу всегда пиши отдельными строками: строка заголовков, строка `|---|---|`, затем строки данных;
- не вставляй markdown-таблицу внутрь одного абзаца и не склеивай её в одну строку;
- перед таблицей и после таблицы оставляй пустую строку;
- первая строка таблицы должна начинаться с символа `|`, без текста перед ним;
- таблицы делай компактными: до 5 колонок, короткие заголовки, без широких текстовых полотен;
- деньги, дни и проценты в таблицах форматируй понятно: "30 млн ₽", "24 дня", "27,1%";
- не называй передачу вопроса наверх отдельным процессом; пиши "вынести на комитет", "зафиксировать решение" или "назначить владельца и срок";
- отвечай максимально русскими словами, но сохраняй общепринятые названия метрик, систем и команд из входных данных;
- не используй английские статусы и служебные слова из входных данных; переводи их на русский;
- избегай лишних англицизмов в обычном тексте: если это не название метрики, команды или системы, пиши по-русски;
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


class NoArgs(ToolArgsModel):
    pass


class ProblemContextArgs(ToolArgsModel):
    max_depth: int | None = Field(default=None, ge=1, le=4)


class CriticalTasksArgs(ToolArgsModel):
    limit: int | None = Field(default=None, ge=1, le=20)


class SearchTasksArgs(ToolArgsModel):
    query: str | None = None
    status: str | None = None
    priority: str | None = None
    assignee: str | None = None
    limit: int | None = Field(default=None, ge=1, le=20)


class SearchRisksArgs(ToolArgsModel):
    query: str | None = None
    status: str | None = None
    min_score: int | None = Field(default=None, ge=0, le=25)
    limit: int | None = Field(default=None, ge=1, le=20)


class SearchCommunicationsArgs(ToolArgsModel):
    query: str | None = None
    status: str | None = None
    team: str | None = None
    limit: int | None = Field(default=None, ge=1, le=20)


class SearchDecisionsArgs(ToolArgsModel):
    query: str | None = None
    status: str | None = None
    owner: str | None = None
    limit: int | None = Field(default=None, ge=1, le=20)


class SearchDependenciesArgs(ToolArgsModel):
    query: str | None = None
    status: str | None = None
    criticality: str | None = None
    limit: int | None = Field(default=None, ge=1, le=20)


class EvidenceSearchArgs(ToolArgsModel):
    query: str = Field(min_length=1, max_length=500)
    entity_id: str | None = Field(default=None, max_length=64)
    limit: int | None = Field(default=None, ge=1, le=20)


class CalculateDelayCostArgs(ToolArgsModel):
    delay_days: int = Field(ge=0, le=365)
    include_resource_burn: bool = True


async def run_project_question(
    *,
    project_id: str,
    question: str,
    as_of: date | None = None,
    max_depth: int = 2,
    conversation_context: list[ProjectConversationMessage] | None = None,
    backend_api_url: str,
) -> ProjectQuestionAnswer:
    agent = ProjectQuestionAgent(backend_api_url=backend_api_url)
    return await agent.answer(
        project_id=project_id,
        question=question,
        as_of=as_of,
        max_depth=max_depth,
        conversation_context=conversation_context,
    )


class ProjectQuestionAgent:
    """Агент с языковой моделью и инструментами функций поверх фактов проекта."""

    def __init__(self, *, backend_api_url: str, temperature: float = 0.1) -> None:
        self.backend_api_url = backend_api_url.rstrip("/")
        self.llm = get_llm_adapter()
        self.temperature = temperature

    async def answer(
        self,
        *,
        project_id: str,
        question: str,
        as_of: date | None,
        max_depth: int,
        conversation_context: list[ProjectConversationMessage] | None = None,
    ) -> ProjectQuestionAnswer:
        as_of_value = as_of.isoformat() if as_of else DEFAULT_AS_OF
        tool_executor = ProjectFactToolExecutor(
            backend_api_url=self.backend_api_url,
            project_id=project_id,
            as_of=as_of_value,
            max_depth=max_depth,
        )
        graph = build_project_question_graph(
            llm=self.llm,
            tool_executor=tool_executor,
            temperature=self.temperature,
        )
        conversation_context_text = _format_conversation_context(conversation_context)
        messages = [
            SystemMessage(content=QA_SYSTEM_PROMPT),
            HumanMessage(
                content=(
                    f"project_id={project_id}, as_of={as_of_value}\n"
                    f"{conversation_context_text}"
                    f"Вопрос пользователя: {question}"
                )
            ),
        ]
        state: ProjectQuestionState = {
            "project_id": project_id,
            "question": question,
            "as_of": as_of_value,
            "max_depth": max_depth,
            "conversation_context": conversation_context_text,
            "messages": messages,
            "used_tools": [],
            "tool_rounds": 0,
        }
        result = await graph.ainvoke(state)
        return _parse_agent_answer(
            _state_value(result, "final_content", "{}") or "{}",
            _state_value(result, "used_tools", []),
            needs_project_tools=_state_value(result, "needs_project_tools", True),
        )


def build_project_question_graph(
    *,
    llm: LLMAdapter,
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
    graph.add_node("route_request", route_request_node(llm=llm))
    graph.add_node(
        "call_model",
        call_model_node(llm=llm, tools=tool_specs, temperature=temperature),
    )
    graph.add_node("run_tools", run_tools_node(tools))
    graph.add_node(
        "finalize",
        finalize_answer_node(llm=llm, temperature=temperature),
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
            "finalize": "finalize",
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


def _format_conversation_context(
    conversation_context: list[ProjectConversationMessage] | None,
) -> str:
    if not conversation_context:
        return ""

    lines: list[str] = []
    total_chars = 0
    for message in conversation_context[-8:]:
        content = _limit_text(message.content, 800)
        if not content:
            continue
        role = "Пользователь" if message.role == "user" else "Агент"
        line = f"{role}: {content}"
        if total_chars + len(line) > 3000:
            break
        lines.append(line)
        total_chars += len(line)

    context = "\n".join(lines).strip()
    if not context:
        return ""
    return (
        "Короткий контекст предыдущих реплик. Используй его только для понимания уточнений, "
        "но факты по проекту всё равно проверяй через tools:\n"
        f"{context}\n\n"
    )


def route_request_node(*, llm: LLMAdapter) -> Any:
    async def route_request(state: ProjectQuestionState | dict[str, Any]) -> dict[str, Any]:
        route = await llm.parse_pydantic(
            response_model=RequestRoute,
            system_prompt=REQUEST_ROUTER_PROMPT,
            user_prompt=(
                f"project_id={_state_value(state, 'project_id')}, "
                f"as_of={_state_value(state, 'as_of')}\n"
                f"{_state_value(state, 'conversation_context', '')}"
                f"Сообщение пользователя: {_state_value(state, 'question')}"
            ),
            temperature=0,
        )

        intent = route.intent
        if intent not in {"small_talk", "project_question", "out_of_scope"}:
            intent = "project_question"
        needs_project_tools = intent == "project_question" and bool(route.needs_project_tools)

        return {
            "request_intent": intent,
            "needs_project_tools": needs_project_tools,
        }

    return route_request


def call_model_node(*, llm: LLMAdapter, tools: list[dict[str, Any]], temperature: float) -> Any:
    async def call_model(state: ProjectQuestionState | dict[str, Any]) -> dict[str, Any]:
        needs_project_tools = _state_value(state, "needs_project_tools", True)
        used_tools = _state_value(state, "used_tools", [])
        response = await llm.chat_completion(
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

    async def run_tools(state: ProjectQuestionState | dict[str, Any]) -> dict[str, Any]:
        used_tools = list(_state_value(state, "used_tools", []))
        result = await tool_node.ainvoke(state)
        tool_messages = _state_value(result, "messages", [])
        used_tools.extend(_tool_names_from_messages(tool_messages))

        return {
            "messages": tool_messages,
            "used_tools": _unique(used_tools),
            "tool_rounds": int(_state_value(state, "tool_rounds", 0) or 0) + 1,
        }

    return run_tools


def finalize_answer_node(*, llm: LLMAdapter, temperature: float) -> Any:
    async def finalize_answer(state: ProjectQuestionState | dict[str, Any]) -> dict[str, Any]:
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
        final_prompt = (
            f"{final_instruction}\n\n"
            "История сообщений и результатов инструментов:\n"
            f"{json.dumps(_messages_to_openai(messages), ensure_ascii=False, default=str)}"
        )
        answer = await llm.parse_pydantic(
            response_model=ProjectQuestionAnswer,
            system_prompt=QA_SYSTEM_PROMPT,
            user_prompt=final_prompt,
            temperature=temperature,
        )
        content = answer.model_dump_json()
        return {
            "messages": [HumanMessage(content=final_instruction), AIMessage(content=content)],
            "final_content": content,
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
    return "finalize"


def route_after_tools(max_tool_rounds: int) -> Any:
    def route(state: ProjectQuestionState | dict[str, Any]) -> str:
        if int(_state_value(state, "tool_rounds", 0) or 0) >= max_tool_rounds:
            return "finalize"
        return "model"

    return route


def build_project_tools(tool_executor: "ProjectFactToolExecutor") -> list[BaseTool]:
    """Создает инструменты LangChain на время одного запроса."""

    async def get_project_summary() -> dict[str, Any]:
        return _compact_project_summary(await tool_executor.project_summary())

    async def get_problem_context(max_depth: int | None = None) -> dict[str, Any]:
        depth = _bounded_limit(max_depth, default=tool_executor.max_depth, maximum=4)
        return _compact_problem_context(await tool_executor.problem_context(max_depth=depth))

    async def get_critical_tasks(limit: int | None = None) -> dict[str, Any]:
        result = await tool_executor.critical_tasks({"limit": limit})
        return _compact_search_result(result, TASK_FIELDS)

    async def search_tasks(
        query: str | None = None,
        status: str | None = None,
        priority: str | None = None,
        assignee: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        result = await tool_executor.search_tasks(
            {
                "query": query,
                "status": status,
                "priority": priority,
                "assignee": assignee,
                "limit": limit,
            }
        )
        return _compact_search_result(result, TASK_FIELDS)

    async def search_risks(
        query: str | None = None,
        status: str | None = None,
        min_score: int | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        result = await tool_executor.search_risks(
            {
                "query": query,
                "status": status,
                "min_score": min_score,
                "limit": limit,
            }
        )
        return _compact_search_result(result, RISK_FIELDS)

    async def search_communications(
        query: str | None = None,
        status: str | None = None,
        team: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        result = await tool_executor.search_communications(
            {
                "query": query,
                "status": status,
                "team": team,
                "limit": limit,
            }
        )
        return _compact_search_result(result, COMMUNICATION_FIELDS)

    async def search_decisions(
        query: str | None = None,
        status: str | None = None,
        owner: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        result = await tool_executor.search_decisions(
            {
                "query": query,
                "status": status,
                "owner": owner,
                "limit": limit,
            }
        )
        return _compact_search_result(result, DECISION_FIELDS + CHANGE_REQUEST_FIELDS)

    async def search_dependencies(
        query: str | None = None,
        status: str | None = None,
        criticality: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        result = await tool_executor.search_dependencies(
            {
                "query": query,
                "status": status,
                "criticality": criticality,
                "limit": limit,
            }
        )
        return _compact_search_result(result, DEPENDENCY_FIELDS)

    async def search_project_evidence(
        query: str,
        entity_id: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        result = await tool_executor.search_project_evidence(
            {
                "query": query,
                "entity_id": entity_id,
                "limit": limit,
            }
        )
        return _compact_retrieval_result(result)

    async def get_budget() -> dict[str, Any]:
        return _compact_budget_result(await tool_executor.budget())

    async def get_resource_rates() -> dict[str, Any]:
        context = await tool_executor.problem_context()
        resources = context.get("project_resources", [])
        return {
            "count": len(resources) if isinstance(resources, list) else 0,
            "items": _compact_items(resources, RESOURCE_COST_FIELDS, limit=20),
        }

    async def get_task_dependency_graph() -> dict[str, Any]:
        context = await tool_executor.problem_context()
        graph = context.get("task_dependency_graph", [])
        return {
            "count": len(graph) if isinstance(graph, list) else 0,
            "items": _compact_items(graph, TASK_GRAPH_FIELDS, limit=60),
        }

    async def calculate_delay_cost(delay_days: int, include_resource_burn: bool = True) -> dict[str, Any]:
        return await tool_executor.calculate_delay_cost(
            delay_days=delay_days,
            include_resource_burn=include_resource_burn,
        )

    def make_tool(
        *,
        name: str,
        description: str,
        args_schema: type[BaseModel],
        func: Callable[..., Awaitable[dict[str, Any]]],
    ) -> BaseTool:
        return StructuredTool.from_function(
            coroutine=func,
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
            name="get_critical_tasks",
            description=(
                "Получить задачи, которые сильнее всего мешают проекту: заблокированные, "
                "просроченные и задачи критического пути."
            ),
            args_schema=CriticalTasksArgs,
            func=get_critical_tasks,
        ),
        make_tool(
            name="search_tasks",
            description="Найти проблемные, заблокированные и просроченные задачи по тексту, статусу, приоритету или исполнителю.",
            args_schema=SearchTasksArgs,
            func=search_tasks,
        ),
        make_tool(
            name="search_risks",
            description="Найти связанные и топовые риски проекта по тексту, статусу или минимальному баллу.",
            args_schema=SearchRisksArgs,
            func=search_risks,
        ),
        make_tool(
            name="search_communications",
            description="Найти просроченные коммуникации и темы, требующие решения, по тексту, статусу или команде.",
            args_schema=SearchCommunicationsArgs,
            func=search_communications,
        ),
        make_tool(
            name="search_decisions",
            description="Найти ожидающие решения и открытые запросы на изменение.",
            args_schema=SearchDecisionsArgs,
            func=search_decisions,
        ),
        make_tool(
            name="search_dependencies",
            description="Найти проектные зависимости по тексту, статусу или критичности.",
            args_schema=SearchDependenciesArgs,
            func=search_dependencies,
        ),
        make_tool(
            name="search_project_evidence",
            description=(
                "RAG-поиск по текстовому следу проекта: комментарии задач, сообщения коммуникаций, "
                "риски, решения, запросы на изменение, причины зависимостей и историю изменений. "
                "Используй для вопросов о причинах, истории обсуждения и уже согласованных действиях."
            ),
            args_schema=EvidenceSearchArgs,
            func=search_project_evidence,
        ),
        make_tool(
            name="get_budget",
            description="Получить бюджет проекта и влияние открытых запросов на изменение.",
            args_schema=NoArgs,
            func=get_budget,
        ),
        make_tool(
            name="get_resource_rates",
            description="Получить ресурсы проекта, часовые ставки и недельную стоимость их работы на проекте.",
            args_schema=NoArgs,
            func=get_resource_rates,
        ),
        make_tool(
            name="get_task_dependency_graph",
            description="Получить граф зависимостей задач проекта: какая задача от какой зависит и что на критическом пути.",
            args_schema=NoArgs,
            func=get_task_dependency_graph,
        ),
        make_tool(
            name="calculate_delay_cost",
            description=(
                "Посчитать стоимость сдвига срока на заданное число дней. "
                "Возвращает стоимость задержки по бюджету и, опционально, стоимость ресурсо-дней."
            ),
            args_schema=CalculateDelayCostArgs,
            func=calculate_delay_cost,
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

    async def project_summary(self) -> dict[str, Any]:
        if self._summary is None:
            query = urlencode({"as_of": self.as_of})
            self._summary = await self._fetch_json(f"/api/v1/summaries/projects/{self.project_id}?{query}")
        return self._summary

    async def problem_context(self, max_depth: int | None = None) -> dict[str, Any]:
        depth = max_depth or self.max_depth
        if self._context is None or depth != self._context_depth:
            query = urlencode({"as_of": self.as_of, "max_depth": depth})
            self._context = await self._fetch_json(
                f"/api/v1/summaries/projects/{self.project_id}/problem-context?{query}"
            )
            self._context_depth = depth
        return self._context

    async def critical_tasks(self, arguments: dict[str, Any]) -> dict[str, Any]:
        summary = await self.project_summary()
        context = await self.problem_context()
        items = _dedupe_items(
            [
                *context.get("problem_tasks", []),
                *summary.get("blocked_tasks", []),
                *summary.get("overdue_tasks", []),
            ]
        )
        items = sorted(items, key=_task_criticality_key, reverse=True)
        return _tool_result(items, arguments.get("limit"))

    async def search_tasks(self, arguments: dict[str, Any]) -> dict[str, Any]:
        summary = await self.project_summary()
        context = await self.problem_context()
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

    async def search_risks(self, arguments: dict[str, Any]) -> dict[str, Any]:
        summary = await self.project_summary()
        context = await self.problem_context()
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

    async def search_communications(self, arguments: dict[str, Any]) -> dict[str, Any]:
        summary = await self.project_summary()
        context = await self.problem_context()
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

    async def search_decisions(self, arguments: dict[str, Any]) -> dict[str, Any]:
        summary = await self.project_summary()
        context = await self.problem_context()
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

    async def search_dependencies(self, arguments: dict[str, Any]) -> dict[str, Any]:
        summary = await self.project_summary()
        context = await self.problem_context()
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

    async def search_project_evidence(self, arguments: dict[str, Any]) -> dict[str, Any]:
        limit_value = _bounded_limit(arguments.get("limit"), default=8, maximum=20)
        query = urlencode(
            {
                "query": arguments.get("query") or "",
                "as_of": self.as_of,
                "limit": limit_value,
                **({"entity_id": arguments["entity_id"]} if arguments.get("entity_id") else {}),
            }
        )
        return await self._fetch_json(
            f"/api/v1/summaries/projects/{self.project_id}/retrieval-context?{query}"
        )

    async def budget(self) -> dict[str, Any]:
        summary = await self.project_summary()
        context = await self.problem_context()
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

    async def calculate_delay_cost(self, *, delay_days: int, include_resource_burn: bool = True) -> dict[str, Any]:
        context = await self.problem_context()
        budget = context.get("budget") or {}
        resources = context.get("project_resources") or []
        cost_of_delay_per_day = int(budget.get("cost_of_delay_per_day") or 0)
        delay_cost = delay_days * cost_of_delay_per_day

        daily_resource_cost = 0
        if include_resource_burn and isinstance(resources, list):
            daily_resource_cost = sum(int(resource.get("daily_project_cost") or 0) for resource in resources)

        resource_burn_cost = delay_days * daily_resource_cost
        return {
            "delay_days": delay_days,
            "cost_of_delay_per_day": cost_of_delay_per_day,
            "delay_opportunity_cost": delay_cost,
            "daily_resource_cost": daily_resource_cost if include_resource_burn else None,
            "resource_burn_cost": resource_burn_cost if include_resource_burn else None,
            "total_cost": delay_cost + resource_burn_cost,
            "currency": budget.get("currency"),
            "formula": {
                "delay_opportunity_cost": "дни сдвига * цена задержки за день",
                "resource_burn_cost": "дни сдвига * сумма дневной стоимости ресурсов проекта",
            },
            "assumption": (
                "resource_burn_cost считает текущую дневную стоимость ресурсов проекта по фактическим часам в неделю / 5; "
                "это оценка текущего сдвига, а не новая смета после перепланирования."
            ),
        }

    async def _fetch_json(self, path: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{self.backend_api_url}{path}", headers={"Accept": "application/json"})
            response.raise_for_status()
            return response.json()


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
        raise ValueError("Q&A-агент ответил по проектному вопросу без вызова инструментов.")
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

    answer.answer = _humanize_agent_text(answer.answer)
    answer.used_tools = actual_tools
    answer.evidence_ids = _unique(answer.evidence_ids)[:20]
    answer.suggested_questions = _unique(
        [_humanize_agent_text(question) for question in answer.suggested_questions]
    )[:4]
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


def _first_argument_value(value: Any) -> Any:
    if isinstance(value, list):
        for item in value:
            if item is not None and item != "":
                return item
        return None
    return value


def _task_criticality_key(item: dict[str, Any]) -> tuple[int, int, str]:
    status = str(item.get("status") or "").casefold()
    priority = str(item.get("priority") or "").casefold()
    blocker_reason = str(item.get("blocker_reason") or "").strip()
    problem_flags = item.get("problem_flags") if isinstance(item.get("problem_flags"), list) else []
    flags_text = " ".join(str(flag).casefold() for flag in problem_flags)
    overdue_days = max(0, _optional_int(item.get("overdue_days")) or 0)

    score = overdue_days
    if item.get("is_blocked") or blocker_reason or "blocked" in status or "заблок" in status:
        score += 1000
    if "critical" in priority or "крит" in priority:
        score += 200
    if "critical" in flags_text or "крит" in flags_text:
        score += 100
    score += len(problem_flags) * 10
    return score, overdue_days, str(item.get("id") or "")


def _tool_result(items: list[dict[str, Any]], limit: Any) -> dict[str, Any]:
    limit_value = _bounded_limit(limit, default=10)
    return {
        "count": len(items),
        "items": items[:limit_value],
    }


HUMAN_VALUE_LABELS = {
    "active": "активен",
    "approved": "согласовано",
    "blocked": "заблокировано",
    "closed": "закрыто",
    "completed": "завершено",
    "critical": "критичный",
    "delayed": "задержано",
    "done": "готово",
    "escalated": "требует решения",
    "green": "зелёная зона",
    "high": "высокий",
    "in_progress": "в работе",
    "low": "низкий",
    "medium": "средний",
    "mitigating": "снижается",
    "open": "открыто",
    "pending": "ожидает решения",
    "proposed": "предложено",
    "red": "красная зона",
    "resolved": "решено",
    "under_review": "на рассмотрении",
    "warning": "важно",
    "yellow": "жёлтая зона",
}


SUMMARY_NESTED_FIELDS = {
    "budget",
    "key_signals",
    "blocked_tasks",
    "overdue_tasks",
    "delayed_milestones",
    "top_risks",
    "delayed_communications",
    "overloaded_resources",
    "risky_dependencies",
    "pending_decisions",
    "open_change_requests",
    "owner_action_load",
}
SUMMARY_FIELDS = tuple(
    field
    for field in ProjectSummary.model_fields
    if field not in SUMMARY_NESTED_FIELDS
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
METRIC_FIELDS = tuple(ProjectMetricsFact.model_fields)
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
EVIDENCE_FIELDS = (
    "id",
    "source_table",
    "source_id",
    "entity_type",
    "entity_id",
    "title",
    "text",
    "occurred_at",
    "linked_task_id",
    "score",
    "metadata",
)
DECISION_FIELDS = ("id", "decision_type", "description", "decision_owner", "status", "decision_date")
CHANGE_REQUEST_FIELDS = ("id", "change_type", "requested_by", "status", "impact_budget", "impact_days", "description")
RESOURCE_FIELDS = (
    "resource_id",
    "full_name",
    "role",
    "team",
    "hour_rate",
    "available_hours_per_week",
    "project_actual_hours_per_week",
    "total_actual_hours_per_week",
    "total_allocation_percent",
    "overload_percent",
)
RESOURCE_COST_FIELDS = (
    "resource_id",
    "full_name",
    "role",
    "team",
    "seniority",
    "hour_rate",
    "available_hours_per_week",
    "project_planned_hours_per_week",
    "project_actual_hours_per_week",
    "weekly_project_cost",
    "daily_project_cost",
)
TASK_GRAPH_FIELDS = (
    "id",
    "task_id",
    "task_title",
    "depends_on_task_id",
    "depends_on_task_title",
    "dependency_type",
    "is_critical_path",
    "lag_days",
    "reason",
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
        "project_resources": _compact_items(
            context.get("project_resources", []),
            RESOURCE_COST_FIELDS,
            limit=12,
        ),
        "task_dependency_graph": _compact_items(
            context.get("task_dependency_graph", []),
            TASK_GRAPH_FIELDS,
            limit=30,
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


def _compact_retrieval_result(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "query": _compact_value(result.get("query", "")),
        "count": result.get("count", 0),
        "items": _compact_items(result.get("items", []), EVIDENCE_FIELDS, limit=10),
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
        normalized = value.strip().casefold()
        return HUMAN_VALUE_LABELS.get(normalized, _humanize_agent_text(_limit_text(value, 260)))
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


def _humanize_agent_text(value: str) -> str:
    replacements = {
        "pending change request": "запрос на изменение, ожидающий решения",
        "open change request": "открытый запрос на изменение",
        "blocked task": "заблокированная задача",
        "pending": "ожидает решения",
        "open": "открыт",
        "blocked": "заблокирован",
        "critical path": "критический путь",
        "critical": "критичный",
        "high": "высокий",
        "medium": "средний",
        "low": "низкий",
        "change request": "запрос на изменение",
        "follow-up": "последующая проверка",
        "status": "статус",
    }
    value = re_sub(r"\bпакет\s+эскалаци[ия]\b", "набор материалов для решения", value)
    value = re_sub(r"\bэскалаци\w*\b", "решение на уровне комитета", value)
    value = re_sub(r"\bescalat\w*\b", "решение на уровне комитета", value)
    for source, replacement in replacements.items():
        value = re_sub(rf"\b{source}\b", replacement, value)
    return " ".join(value.split())


def re_sub(pattern: str, replacement: str, value: str) -> str:
    import re

    return re.sub(pattern, replacement, value, flags=re.IGNORECASE)


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
