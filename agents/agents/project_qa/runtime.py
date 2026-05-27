from __future__ import annotations

try:
    from langgraph.graph import END, START, StateGraph
    from langgraph.graph.message import add_messages
    from langgraph.prebuilt import ToolNode
    from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
except ModuleNotFoundError:
    END = START = StateGraph = None
    add_messages = None
    ToolNode = None
    AIMessage = BaseMessage = HumanMessage = SystemMessage = ToolMessage = None
