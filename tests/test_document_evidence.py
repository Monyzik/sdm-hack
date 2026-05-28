import csv
import json
from datetime import date
from zipfile import ZipFile

import pytest

from scripts.generate_interview_data import generate
from sdm.backend.services.document_evidence import (
    DEFAULT_ROOT,
    _windows,
    load_document_evidence,
    load_manifest,
    read_document,
)


def test_corpus_stable_and_scoped():
    first = load_document_evidence("P007", as_of=date(2026, 6, 19))
    assert first == load_document_evidence("P007")
    manifest = load_manifest(DEFAULT_ROOT)
    assert {item.entity_id for item in first} == {item["id"] for item in manifest}
    assert {(item.entity_id, item.metadata["version"]) for item in first} == {
        (item["id"], item["version"]) for item in manifest
    }
    assert load_document_evidence("P001") == []
    assert load_document_evidence("P007", as_of=date(2026, 6, 14)) == []
    assert all(len(item.text) <= 1200 and len(item.source_id) <= 64 for item in first)
    assert all(item.metadata["locator"] and item.metadata["synthetic"] for item in first)


@pytest.mark.parametrize("text", ["слово " * 800, "x" * 2401, "abc\n\n" * 800])
def test_chunk_coverage_bounds(text):
    windows = list(_windows(text, 120, 15))
    assert windows[0][0] == 0 and windows[-1][1] == len(text)
    assert all(0 < end - start <= 120 for start, end in windows)
    assert all(b[0] <= a[1] and b[0] > a[0] for a, b in zip(windows, windows[1:]))
    covered = set().union(*(set(range(a, b)) for a, b in windows))
    assert len(covered) == len(text)


def test_docx_order_and_sections(tmp_path):
    path = tmp_path / "test.docx"
    xml = """<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>
    <w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Раздел</w:t></w:r></w:p>
    <w:p><w:r><w:t>До таблицы</w:t></w:r></w:p>
    <w:tbl><w:tr><w:tc><w:p><w:r><w:t>Ячейка 1</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Ячейка 2</w:t></w:r></w:p></w:tc></w:tr></w:tbl>
    <w:p><w:r><w:t>После таблицы</w:t></w:r></w:p></w:body></w:document>"""
    with ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", xml)
    blocks = read_document(path)
    assert [b.text for b in blocks] == [
        "Раздел",
        "До таблицы",
        "Ячейка 1 | Ячейка 2",
        "После таблицы",
    ]
    assert all(b.section == ("Раздел",) for b in blocks)


def test_markdown_sections_and_chunk_locators(tmp_path):
    content = "# Document\n\nIntro\n\n## First\n\n" + "word " * 100 + "\n\n## Second\n\nTail"
    (tmp_path / "sample.md").write_text(content)
    (tmp_path / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "documents": [
                    {
                        "id": "D1",
                        "path": "sample.md",
                        "project_id": "P007",
                        "version": "1",
                        "title": "Sample",
                        "published_at": "2026-06-18",
                        "synthetic": True,
                    }
                ],
            }
        )
    )
    blocks = read_document(tmp_path / "sample.md")
    assert [b.section for b in blocks][-2:] == [("Document", "Second")] * 2
    chunks = load_document_evidence("P007", tmp_path, max_chars=80, overlap_chars=10)
    assert all(len(c.text) <= 80 for c in chunks)
    first_chunks = [c for c in chunks if c.metadata["section"] == "Document / First"]
    expected = "First\n\n" + ("word " * 100).strip()
    restored = [None] * len(expected)
    for chunk in first_chunks:
        start, end = chunk.metadata["char_start"], chunk.metadata["char_end"]
        restored[start:end] = chunk.text
        assert chunk.metadata["block_start"] <= chunk.metadata["block_end"]
    assert "".join(restored) == expected


@pytest.mark.parametrize("change", ["traversal", "duplicate", "date", "synthetic"])
def test_invalid_manifest(tmp_path, change):
    manifest = json.loads((DEFAULT_ROOT / "manifest.json").read_text())
    for doc in manifest["documents"]:
        path = tmp_path / doc["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("test")
    if change == "traversal":
        manifest["documents"][0]["path"] = "../outside.md"
    elif change == "duplicate":
        manifest["documents"].append(manifest["documents"][0])
    elif change == "date":
        manifest["documents"][0]["published_at"] = "2026-02-30"
    else:
        manifest["documents"][0]["synthetic"] = False
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        load_manifest(tmp_path)


def test_document_versions_keep_provenance_and_respect_snapshot(tmp_path):
    documents = []
    for version, published_at in [("1", "2026-06-16"), ("2", "2026-06-18")]:
        path = f"version-{version}.md"
        (tmp_path / path).write_text(f"# Decision\n\nRevision {version}.")
        documents.append(
            {
                "id": "D1",
                "path": path,
                "project_id": "P007",
                "version": version,
                "title": "Decision",
                "published_at": published_at,
                "synthetic": True,
            }
        )
    (tmp_path / "manifest.json").write_text(
        json.dumps({"schema_version": 1, "documents": documents})
    )
    current = load_document_evidence("P007", tmp_path)
    historical = load_document_evidence("P007", tmp_path, as_of=date(2026, 6, 17))
    assert {item.entity_id for item in current} == {"D1"}
    assert {item.metadata["version"] for item in current} == {"1", "2"}
    assert len({item.source_id for item in current}) == len(current)
    assert historical == [item for item in current if item.metadata["version"] == "1"]


def test_generation_isolated_deterministic_and_single_project(tmp_path):
    original = (DEFAULT_ROOT.parent / "demo" / "projects.csv").read_bytes()
    full = generate(tmp_path / "full")
    new = generate(tmp_path / "new")
    with (full / "projects.csv").open() as stream:
        full_rows = list(csv.DictReader(stream))
    with (new / "projects.csv").open() as stream:
        new_rows = list(csv.DictReader(stream))
    assert len(full_rows) == 1
    assert [r["идентификатор"] for r in new_rows] == ["P007"]
    assert (DEFAULT_ROOT.parent / "demo" / "projects.csv").read_bytes() == original
    assert all(path.read_bytes() == (new / path.name).read_bytes() for path in full.glob("*.csv"))
    with pytest.raises(ValueError):
        generate(DEFAULT_ROOT)
    with pytest.raises(ValueError):
        generate(full)
