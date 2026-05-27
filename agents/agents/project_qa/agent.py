from __future__ import annotations

from datetime import date

from agents.core.text import limit_text
from agents.infrastructure.llm import get_llm_adapter
from agents.tools.project_facts import ProjectFactToolExecutor

from .graph import build_project_question_graph
from .message_utils import _parse_agent_answer, _state_value
from .prompts import QA_SYSTEM_PROMPT
from .runtime import HumanMessage, SystemMessage
from .schemas import DEFAULT_AS_OF, ProjectConversationMessage, ProjectQuestionAnswer
from .state import ProjectQuestionState


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


def _format_conversation_context(
    conversation_context: list[ProjectConversationMessage] | None,
) -> str:
    if not conversation_context:
        return ""

    lines: list[str] = []
    total_chars = 0
    for message in conversation_context[-8:]:
        content = limit_text(message.content, 800)
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
