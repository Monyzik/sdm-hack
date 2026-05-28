"""Independent lexical ranking and rank-only fusion for small evidence corpora.

BM25: https://www.elastic.co/blog/practical-bm25-part-2-the-bm25-algorithm-and-its-variables
RRF: https://cormack.uwaterloo.ca/cormacksigir09-rrf.pdf
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

_TOKEN = re.compile(r"[^\W_]+(?:-[^\W_]+)*", re.UNICODE)


@dataclass(frozen=True)
class RankedCandidate:
    id: str
    score: float


@dataclass(frozen=True)
class FusedCandidate:
    id: str
    score: float
    ranks: dict[str, int]
    scores: dict[str, float]


def _positive_integer(value: int, name: str) -> None:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{name} must be a positive integer")


def _tokens(text: str) -> list[str]:
    return _TOKEN.findall(text.casefold().replace("ё", "е"))


def bm25_search(
    query: str, documents: Sequence[tuple[str, str]], *, limit: int
) -> list[RankedCandidate]:
    """Okapi BM25, k1=1.5/b=.75, positive IDF, no unrelated zero-score hits."""
    _positive_integer(limit, "limit")
    identifiers = [identifier for identifier, _ in documents]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("Duplicate corpus IDs")
    terms = set(_tokens(query))
    if not documents or not terms:
        return []
    frequencies = [Counter(_tokens(text)) for _, text in documents]
    lengths = [sum(frequency.values()) for frequency in frequencies]
    average_length = sum(lengths) / len(documents)
    if average_length == 0:
        return []
    document_frequency = Counter(term for frequency in frequencies for term in frequency)
    idf = {
        term: math.log(
            1 + (len(documents) - document_frequency[term] + 0.5) / (document_frequency[term] + 0.5)
        )
        for term in sorted(terms)
    }
    results = []
    for identifier, frequency, length in zip(identifiers, frequencies, lengths, strict=True):
        normalization = 1.5 * (1 - 0.75 + 0.75 * length / average_length)
        score = sum(
            weight * (frequency[term] * 2.5) / (frequency[term] + normalization)
            for term, weight in idf.items()
            if frequency[term]
        )
        if score > 0:
            results.append(RankedCandidate(identifier, score))
    return sorted(results, key=lambda candidate: (-candidate.score, candidate.id))[:limit]


def reciprocal_rank_fusion(
    rankings: Mapping[str, Sequence[RankedCandidate]], *, limit: int, rank_constant: int = 60
) -> list[FusedCandidate]:
    """Fuse unique ranked lists using sum(1/(rank_constant+rank)); scores are audit data."""
    _positive_integer(limit, "limit")
    _positive_integer(rank_constant, "rank_constant")
    ranks: dict[str, dict[str, int]] = {}
    scores: dict[str, dict[str, float]] = {}
    for name in sorted(rankings):
        seen = set()
        rank = 0
        for candidate in rankings[name]:
            if candidate.id in seen:
                continue
            seen.add(candidate.id)
            rank += 1
            ranks.setdefault(candidate.id, {})[name] = rank
            scores.setdefault(candidate.id, {})[name] = candidate.score
    fused = [
        FusedCandidate(
            identifier,
            sum(1 / (rank_constant + rank) for rank in positions.values()),
            positions,
            scores[identifier],
        )
        for identifier, positions in ranks.items()
    ]
    return sorted(fused, key=lambda candidate: (-candidate.score, candidate.id))[:limit]
