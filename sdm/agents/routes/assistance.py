from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from sdm.agents.llm import IncompleteOutputError, StructuredOutputError
from sdm.agents.project_qa.agent import ProjectQuestionAgent
from sdm.agents.project_qa.schemas import (
    ProjectQuestionAnswer,
    ProjectQuestionRequest,
)

router = APIRouter(prefix="/api/v1/agents/projects", tags=["assistance"])
logger = logging.getLogger(__name__)

INCOMPLETE_OUTPUT_MESSAGE = "Модель не смогла завершить генерацию ответа. Повторите запрос."
BUDGET_EXCEEDED_MESSAGE = "Превышен лимит времени на ответ агента. Повторите запрос."
INVALID_OUTPUT_MESSAGE = (
    "Модель не смогла подготовить ответ по заданной структуре после повторной попытки. "
    "Повторите запрос."
)


@router.post("/{project_id}/ask", response_model=ProjectQuestionAnswer)
async def ask_project_agent(
    project_id: str,
    payload: ProjectQuestionRequest,
) -> ProjectQuestionAnswer:
    try:
        return await ProjectQuestionAgent().answer(
            project_id=project_id,
            question=payload.question,
            as_of=payload.as_of,
            max_depth=payload.max_depth,
            conversation_context=payload.conversation_context,
            verify_claims=payload.verify_claims,
        )
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail=BUDGET_EXCEEDED_MESSAGE) from exc
    except IncompleteOutputError as exc:
        raise HTTPException(status_code=502, detail=INCOMPLETE_OUTPUT_MESSAGE) from exc
    except StructuredOutputError as exc:
        raise HTTPException(status_code=502, detail=INVALID_OUTPUT_MESSAGE) from exc
    except (ValueError, RuntimeError) as exc:
        logger.exception("Q&A service unavailable")
        raise HTTPException(status_code=503, detail="Сервис ответов временно недоступен.") from exc
    except Exception as exc:
        logger.exception("Q&A run failed")
        raise HTTPException(
            status_code=502, detail="Не удалось получить ответ агента. Повторите запрос."
        ) from exc


@router.post("/{project_id}/ask/stream")
async def stream_project_agent_answer(
    project_id: str,
    payload: ProjectQuestionRequest,
) -> StreamingResponse:
    async def events():
        try:
            async for item in ProjectQuestionAgent().answer_stream(
                project_id=project_id,
                question=payload.question,
                as_of=payload.as_of,
                max_depth=payload.max_depth,
                conversation_context=payload.conversation_context,
                verify_claims=payload.verify_claims,
            ):
                yield _sse_event(item)
        except IncompleteOutputError:
            yield _sse_event({"event": "error", "data": {"message": INCOMPLETE_OUTPUT_MESSAGE}})
        except StructuredOutputError:
            yield _sse_event({"event": "error", "data": {"message": INVALID_OUTPUT_MESSAGE}})
        except Exception:
            logger.exception("Streaming Q&A run failed")
            yield _sse_event(
                {
                    "event": "error",
                    "data": {"message": "Не удалось получить ответ агента. Повторите запрос."},
                }
            )

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


def _sse_event(item: dict[str, Any]) -> str:
    payload = json.dumps(item["data"], ensure_ascii=False)
    return f"event: {item['event']}\ndata: {payload}\n\n"
