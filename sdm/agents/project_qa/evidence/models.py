"""Модели черновика и результатов проверки цитат."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MAX_ANSWER_CLAIMS = 4


class EvidenceQuote(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(description="Точный id одного источника из переданного каталога.")
    quote: str = Field(
        min_length=1,
        max_length=1600,
        description="Дословная цитата из data этого источника, подтверждающая тезис.",
    )


class DraftClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=1200, description="Один короткий тезис ответа.")
    evidence: list[EvidenceQuote] = Field(
        min_length=1,
        max_length=4,
        description="Подтверждения этого тезиса. Каждый элемент содержит только source_id и quote.",
    )


class AnswerDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claims: list[DraftClaim] = Field(
        max_length=MAX_ANSWER_CLAIMS,
        description="Тезисы ответа. Каждый элемент является объектом только с полями text и evidence.",
    )
    unanswered_aspects: list[str] = Field(
        max_length=4,
        description=(
            "Отдельное поле верхнего уровня рядом с claims: список непокрытых частей вопроса. "
            "Если их нет, передай пустой список. Не помещай это поле внутрь тезиса."
        ),
    )


class ClaimReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_index: int = Field(
        ge=0,
        le=MAX_ANSWER_CLAIMS - 1,
        description="Индекс проверяемого тезиса, начиная с нуля.",
    )
    verdict: Literal["supported", "unsupported", "contradicted"] = Field(
        description="Тезис подтверждён, не имеет достаточного основания или опровергнут источником."
    )


class ClaimSupport(BaseModel):
    """Отдельно проверяем числа, статус и смысл каждого утверждения."""

    model_config = ConfigDict(extra="forbid")

    entailed: bool
    all_numbers_supported: bool
    status_and_modality_supported: bool
    contradicted: bool

    @property
    def verdict(self) -> Literal["supported", "unsupported", "contradicted"]:
        if self.contradicted:
            return "contradicted"
        if self.entailed and self.all_numbers_supported and self.status_and_modality_supported:
            return "supported"
        return "unsupported"


class EvidenceSearch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(
        min_length=1, max_length=500, description="Короткий запрос для поиска недостающего факта."
    )
    entity_id: str | None = Field(
        default=None, max_length=64, description="Известный id сущности для фильтрации или null."
    )


class EvidenceReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claims: list[ClaimReview] = Field(
        max_length=MAX_ANSWER_CLAIMS,
        description="Ровно одна оценка для каждого тезиса черновика, без повторения индексов.",
    )
    missing_aspects: list[str] = Field(
        max_length=4,
        description="До четырёх непокрытых частей исходного вопроса. Пустой список, если их нет.",
    )
    searches: list[EvidenceSearch] = Field(
        max_length=3,
        description=(
            "До трёх новых поисковых запросов для устранения пробелов. "
            "Пустой список, если поиск не нужен или recovery_available=false."
        ),
    )
    context_source_ids: list[str] = Field(
        max_length=3,
        description=(
            "До трёх id из каталога для ДОПОЛНИТЕЛЬНОГО чтения соседних фрагментов. "
            "Это не перечень всех подтверждающих источников. "
            "Пустой список, если чтение не нужно или recovery_available=false."
        ),
    )


class VerifiedClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    evidence_ids: list[str]
    evidence: list[EvidenceQuote] = Field(default_factory=list)


class AnswerVerification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["passed", "partial", "abstained", "unavailable", "not_checked"]
    checked_claims: int = Field(ge=0)
    supported_claims: int = Field(ge=0)
    recovery_rounds: int = Field(ge=0)
