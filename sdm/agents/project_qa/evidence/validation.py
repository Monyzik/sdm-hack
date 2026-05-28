"""Проверки источников и буквальных цитат без обращения к модели."""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import Field, create_model

from .models import (
    MAX_ANSWER_CLAIMS,
    AnswerDraft,
    DraftClaim,
    EvidenceQuote,
    EvidenceReview,
    VerifiedClaim,
)


def evidence_catalog(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Собирает последние версии источников по их точным идентификаторам.

    Для проверки берём полные данные из data. Короткий excerpt нужен только интерфейсу.
    """
    records = {}
    for source in sources:
        if source.get("id") and source.get("data"):
            records[source["id"]] = {
                key: source.get(key) for key in ("id", "reference", "title", "data")
            }
    return list(records.values())


def grounded_draft_model(sources: list[dict[str, Any]]) -> type[AnswerDraft]:
    allowed_ids = tuple(source["id"] for source in evidence_catalog(sources))
    if not allowed_ids:
        raise ValueError("Cannot draft project facts without evidence artifacts")
    quote_model = create_model(
        "ObservedEvidenceQuote",
        __base__=EvidenceQuote,
        source_id=(
            Literal.__getitem__(allowed_ids),
            Field(description=EvidenceQuote.model_fields["source_id"].description),
        ),
    )
    claim_model = create_model(
        "GroundedDraftClaim",
        __base__=DraftClaim,
        evidence=(
            list[quote_model],
            Field(
                min_length=1,
                max_length=4,
                description=DraftClaim.model_fields["evidence"].description,
            ),
        ),
    )
    return create_model(
        "GroundedAnswerDraft",
        __base__=AnswerDraft,
        claims=(
            list[claim_model],
            Field(
                max_length=MAX_ANSWER_CLAIMS,
                description=AnswerDraft.model_fields["claims"].description,
            ),
        ),
    )


def verification_evidence(draft: AnswerDraft, sources: list[dict[str, Any]]) -> dict[str, Any]:
    """Отделяет цитируемые источники каждого утверждения от возможных противоречий.

    Число из чужого источника не должно подтверждать утверждение, которое на него
    не ссылается.
    """
    catalog = {source["id"]: source for source in evidence_catalog(sources)}
    cited_ids = {citation.source_id for claim in draft.claims for citation in claim.evidence}
    retrieved_ids = {
        source["id"]
        for source in sources
        if source.get("tool") in {"search_project_evidence", "get_evidence_context"}
    }
    return {
        "claim_evidence": [
            {
                "claim_index": index,
                "sources": [
                    catalog[source_id]
                    for source_id in dict.fromkeys(item.source_id for item in claim.evidence)
                    if source_id in catalog
                ],
            }
            for index, claim in enumerate(draft.claims)
        ],
        "other_retrieved_sources": [
            source
            for source_id, source in catalog.items()
            if source_id in retrieved_ids and source_id not in cited_ids
        ],
    }


def _source_texts(data: Any):
    if isinstance(data, str):
        yield data
    elif isinstance(data, dict):
        # Инструменты возвращают и JSON, поэтому цитата может быть его фрагментом.
        yield json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        yield json.dumps(data, ensure_ascii=False)
        yield json.dumps(data, ensure_ascii=False, sort_keys=True)
        for value in data.values():
            yield from _source_texts(value)
    elif isinstance(data, list):
        for value in data:
            yield from _source_texts(value)


def invalid_quote_indices(draft: AnswerDraft, sources: list[dict[str, Any]]) -> set[int]:
    # Для каждого источника один раз готовим текст; меняем только пробелы.
    by_id = {
        source["id"]: tuple(" ".join(text.split()) for text in _source_texts(source["data"]))
        for source in evidence_catalog(sources)
    }
    invalid = set()
    for index, claim in enumerate(draft.claims):
        for citation in claim.evidence:
            quote = " ".join(citation.quote.split())
            if (
                not quote
                or citation.source_id not in by_id
                or not any(quote in text for text in by_id[citation.source_id])
            ):
                invalid.add(index)
    return invalid


def validate_review(
    review: EvidenceReview, draft: AnswerDraft, sources: list[dict[str, Any]]
) -> EvidenceReview:
    """Проверяет, что оценено каждое утверждение, а цитаты встречаются в источниках."""
    indices = [claim.claim_index for claim in review.claims]
    if sorted(indices) != list(range(len(draft.claims))):
        raise ValueError("Evidence review must cover every claim exactly once")
    invalid = invalid_quote_indices(draft, sources)
    claims = [
        claim.model_copy(update={"verdict": "unsupported"})
        if claim.claim_index in invalid and claim.verdict == "supported"
        else claim
        for claim in review.claims
    ]
    return review.model_copy(update={"claims": claims})


def supported_claims(draft: AnswerDraft, review: EvidenceReview) -> list[VerifiedClaim]:
    supported = {claim.claim_index for claim in review.claims if claim.verdict == "supported"}
    return [
        VerifiedClaim(
            text=claim.text.strip(),
            evidence_ids=list(dict.fromkeys(citation.source_id for citation in claim.evidence)),
            evidence=claim.evidence,
        )
        for index, claim in enumerate(draft.claims)
        if index in supported
    ]
