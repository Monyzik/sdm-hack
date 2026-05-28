"""Offline checks for evaluation leakage and broken evidence labels."""

import hashlib
import json
from collections import Counter
from pathlib import Path

from sdm.backend.services.document_evidence import load_document_evidence, load_manifest
from sdm.evaluation.runner import corpus_catalog, load_cases

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data/interview"


def test_splits_are_frozen_disjoint_and_cover_the_dataset():
    catalog, _ = corpus_catalog(ROOT, CORPUS)
    manifest = json.loads((CORPUS / "eval_splits.json").read_text())
    combined = load_cases(CORPUS / "eval_cases.jsonl", catalog)
    split_cases = []
    for split in manifest["splits"].values():
        path = ROOT / split["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == split["sha256"]
        cases = load_cases(path, catalog)
        assert [case.id for case in cases] == split["case_ids"]
        split_cases.extend(cases)
    assert split_cases == combined
    assert len({case.id for case in combined}) == len(combined)
    assert len({case.question.casefold().strip() for case in combined}) == len(combined)

    families = manifest["topic_families"]
    assert set(families["development"]).isdisjoint(families["heldout"])
    development = load_cases(ROOT / manifest["splits"]["development"]["path"], catalog)
    for case in development:
        gold_families = {
            source.split(":v")[0]
            for group in case.required_evidence_groups
            for source in group
        }
        assert gold_families.isdisjoint(families["heldout"]), case.id


def test_document_gold_is_available_at_case_date_and_within_entity_filter():
    catalog, _ = corpus_catalog(ROOT, CORPUS)
    chunks = {item.source_id: item for item in load_document_evidence("P007")}
    for case in load_cases(CORPUS / "eval_cases.jsonl", catalog):
        for group in case.required_evidence_groups:
            for source in group:
                if source not in chunks:
                    continue
                item = chunks[source]
                assert item.occurred_at.date() <= case.as_of, (case.id, source)
                if case.entity_id:
                    assert case.entity_id in {item.entity_id, item.source_id}, (case.id, source)


def test_authored_documents_do_not_repeat_padding_paragraphs():
    paragraphs = Counter()
    for document in load_manifest(CORPUS):
        if not document["path"].startswith(("expanded/", "collection/")):
            continue
        text = (CORPUS / document["path"]).read_text()
        paragraphs.update(
            " ".join(paragraph.split())
            for paragraph in text.split("\n\n")
            if len(paragraph.strip()) > 110
        )
    assert paragraphs
    assert not [paragraph for paragraph, count in paragraphs.items() if count > 1]


def test_collection_gold_quotes_still_match_the_actual_chunks():
    """Detect content changes that leave a valid source ID with stale gold labels."""
    catalog, _ = corpus_catalog(ROOT, CORPUS)
    cases = {case.id: case for case in load_cases(CORPUS / "eval_cases.jsonl", catalog)}
    chunks = {item.source_id: item for item in load_document_evidence("P007")}
    evidence_map = json.loads((CORPUS / "collection/evidence_map.json").read_text())
    for entry in evidence_map["cases"]:
        mapped_groups = []
        for group in entry["support_groups"]:
            sources = set()
            for anchor in group:
                assert anchor["quote"].strip(), entry["case_id"]
                assert anchor["source_ids"], entry["case_id"]
                for identifier in anchor["source_ids"]:
                    assert chunks[identifier].entity_id == anchor["document_id"]
                    assert anchor["quote"] in chunks[identifier].text, entry["case_id"]
                    sources.add(identifier)
            mapped_groups.append(sources)
        assert mapped_groups == [
            set(group) for group in cases[entry["case_id"]].required_evidence_groups
        ]
