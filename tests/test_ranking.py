import pytest

from sdm.backend.services.ranking import RankedCandidate, bm25_search, reciprocal_rank_fusion


def test_lexical_candidate_absent_from_dense_is_recovered_by_fusion():
    lexical = bm25_search(
        "маскирование", [("lexical", "маскирование"), ("dense", "прочее")], limit=8
    )
    fused = reciprocal_rank_fusion(
        {"dense": [RankedCandidate("dense", 0.9)], "bm25": lexical}, limit=8
    )
    assert {candidate.id for candidate in fused} == {"dense", "lexical"}
    lexical_hit = next(candidate for candidate in fused if candidate.id == "lexical")
    assert lexical_hit.ranks == {"bm25": 1}
    assert lexical_hit.scores["bm25"] > 0


def test_fusion_is_independent_of_score_scale_and_mapping_order():
    first = {
        "dense": [RankedCandidate("A", 0.8), RankedCandidate("B", 0.7)],
        "bm25": [RankedCandidate("B", 5), RankedCandidate("C", 4)],
    }
    scaled = {
        name: [RankedCandidate(item.id, item.score * 1000) for item in values]
        for name, values in reversed(list(first.items()))
    }
    one, two = [reciprocal_rank_fusion(ranking, limit=8) for ranking in (first, scaled)]
    assert [(item.id, item.score, item.ranks) for item in one] == [
        (item.id, item.score, item.ranks) for item in two
    ]
    assert one[0].id == "B"


def test_bm25_frequency_and_length_normalization():
    docs = [("frequent", "risk risk risk x"), ("once", "risk x x x"), ("long", "risk " + "x " * 40)]
    ranked = bm25_search("risk", docs, limit=8)
    assert [item.id for item in ranked] == ["frequent", "once", "long"]


def test_unicode_casefold_yo_and_hyphenated_ids():
    docs = [("ru", "Ёлка ВЕД-701"), ("other", "елка ВЕД-702"), ("en", "RISK")]
    assert [item.id for item in bm25_search("вед-701", docs, limit=8)] == ["ru"]
    assert {item.id for item in bm25_search("ЕЛКА", docs, limit=8)} == {"ru", "other"}
    assert [item.id for item in bm25_search("risk", docs, limit=8)] == ["en"]


def test_empty_and_zero_overlap_inputs_are_safe():
    assert bm25_search("x", [], limit=1) == []
    assert bm25_search("", [("A", "x")], limit=1) == []
    assert bm25_search("x", [("A", "")], limit=1) == []
    assert bm25_search("x", [("A", "y")], limit=1) == []
    assert reciprocal_rank_fusion({}, limit=1) == []


def test_ties_are_by_id_and_duplicate_rank_entries_do_not_contribute():
    assert [item.id for item in bm25_search("x", [("B", "x"), ("A", "x")], limit=2)] == ["A", "B"]
    candidates = [RankedCandidate("A", 1), RankedCandidate("A", 9), RankedCandidate("B", 0.5)]
    result = reciprocal_rank_fusion({"dense": candidates}, limit=3)
    assert result[0].score == pytest.approx(1 / 61)
    assert result[0].scores == {"dense": 1}
    assert result[1].ranks == {"dense": 2}
    tied = reciprocal_rank_fusion(
        {"one": [RankedCandidate("B", 5)], "two": [RankedCandidate("A", 1)]}, limit=2
    )
    assert [item.id for item in tied] == ["A", "B"]


@pytest.mark.parametrize("value", [0, -1, True, 1.5])
def test_invalid_limits_and_constants(value):
    with pytest.raises(ValueError):
        bm25_search("x", [], limit=value)
    with pytest.raises(ValueError):
        reciprocal_rank_fusion({}, limit=value)
    with pytest.raises(ValueError):
        reciprocal_rank_fusion({}, limit=1, rank_constant=value)


def test_duplicate_corpus_ids_are_rejected_even_for_empty_query():
    with pytest.raises(ValueError, match="Duplicate"):
        bm25_search("", [("A", "x"), ("A", "y")], limit=1)
