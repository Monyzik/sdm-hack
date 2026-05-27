from __future__ import annotations

try:
    from langchain_core.tools import BaseTool, StructuredTool
    from langchain_core.utils.function_calling import convert_to_openai_tool
except ModuleNotFoundError:
    BaseTool = StructuredTool = None
    convert_to_openai_tool = None
