from __future__ import annotations

from typing import Any

from sdm.agents.llm import LLMAdapter
from sdm.agents.tools.project_facts import ProjectFactToolExecutor, build_project_tools
from sdm.agents.tools.runtime import StructuredTool, convert_to_openai_tool

from .nodes.final import finalize_answer_node
from .nodes.model import call_model_node, route_after_model
from .nodes.router import route_after_request_router, route_request_node
from .nodes.tool_call import route_after_tools, run_tools_node
from .runtime import END, START, StateGraph, ToolNode
from .state import ProjectQuestionState


def build_project_question_graph(
    *,
    llm: LLMAdapter,
    tool_executor: ProjectFactToolExecutor,
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
