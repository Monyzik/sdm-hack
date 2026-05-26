"""Адаптеры LLM-провайдеров."""

from agents.infrastructure.llm.adapter import LLMAdapter, get_llm_adapter

__all__ = ["LLMAdapter", "get_llm_adapter"]
