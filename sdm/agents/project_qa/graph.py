from __future__ import annotations

from langchain_core.tools import BaseTool
from langchain_core.utils.function_calling import convert_to_openai_tool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from sdm.agents.llm import LLMAdapter

from .nodes.context import request_project_context
from .nodes.draft import draft_answer_node
from .nodes.final import finalize_answer_node
from .nodes.model import call_model_node, route_after_model
from .nodes.recovery import request_evidence_recovery, route_after_review
from .nodes.router import route_after_request_router, route_request_node
from .nodes.tool_call import route_after_tools, run_tools_node
from .nodes.verify import verify_answer_node
from .recovery import MAX_RECOVERY_ROUNDS
from .state import ProjectQuestionState


def build_project_question_graph(
    *,
    llm: LLMAdapter,
    tools: list[BaseTool],
    temperature: float,
    max_tool_rounds: int = 3,
    verify_claims: bool = True,
) -> CompiledStateGraph:
    if max_tool_rounds < 1:
        raise ValueError("max_tool_rounds must be at least 1")

    tools_by_name = {tool.name: tool for tool in tools}
    tool_specs = [convert_to_openai_tool(tool) for tool in tools]
    answer_node = "draft_answer" if verify_claims else "finalize"

    graph = StateGraph(ProjectQuestionState)
    graph.add_node("route_request", route_request_node(llm=llm))
    graph.add_node("request_project_context", request_project_context(tools_by_name))
    graph.add_node(
        "call_model",
        call_model_node(llm=llm, tools=tool_specs, temperature=temperature),
    )
    graph.add_node("run_tools", run_tools_node(tools))
    if verify_claims:
        graph.add_node("draft_answer", draft_answer_node(llm=llm, temperature=temperature))
        graph.add_node("verify_answer", verify_answer_node(llm=llm))
        graph.add_node("recover_evidence", request_evidence_recovery)
        graph.add_node(
            "run_recovery_tools",
            run_tools_node(tools, stage="run_recovery_tools", tolerate_errors=True),
        )
    graph.add_node(
        "finalize",
        finalize_answer_node(llm=llm, temperature=temperature, verify_claims=verify_claims),
    )

    graph.add_edge(START, "route_request")
    graph.add_conditional_edges(
        "route_request",
        route_after_request_router,
        {
            "context": "request_project_context",
            "finalize": "finalize",
        },
    )
    # Загрузка контекста считается первым раундом инструментов.
    # При max_tool_rounds=1 сразу готовим ответ выбранным способом.
    graph.add_conditional_edges(
        "request_project_context",
        route_after_tools(max_tool_rounds),
        {
            "model": "call_model",
            "finalize": answer_node,
        },
    )
    graph.add_conditional_edges(
        "call_model",
        route_after_model,
        {
            "tools": "run_tools",
            "finalize": answer_node,
        },
    )
    graph.add_conditional_edges(
        "run_tools",
        route_after_tools(max_tool_rounds),
        {
            "model": "call_model",
            "finalize": answer_node,
        },
    )
    if verify_claims:
        graph.add_edge("draft_answer", "verify_answer")
        graph.add_conditional_edges(
            "verify_answer",
            route_after_review,
            {"recover": "recover_evidence", "finalize": "finalize"},
        )
        graph.add_edge("recover_evidence", "run_recovery_tools")
        graph.add_edge("run_recovery_tools", "draft_answer")
    graph.add_edge("finalize", END)
    # Лимит учитывает выбор маршрута, загрузку контекста, вызовы и проверку ответа.
    return graph.compile(name="project_question").with_config(
        recursion_limit=2 * max_tool_rounds + 6 + (4 * MAX_RECOVERY_ROUNDS if verify_claims else 0)
    )
