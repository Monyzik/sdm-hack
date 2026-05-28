"""Deterministic, section-aware local document evidence (no provider calls)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET

from sdm.backend.services.project_evidence import EvidenceCandidate

DEFAULT_ROOT = Path(__file__).resolve().parents[3] / "data" / "interview"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _paragraph_text(element: ET.Element) -> str:
    return "".join(
        node.text or "" if node.tag == f"{W}t" else "\t" if node.tag == f"{W}tab" else "\n"
        for node in element.iter()
        if node.tag in {f"{W}t", f"{W}tab", f"{W}br", f"{W}cr"}
    )


@dataclass(frozen=True)
class DocumentBlock:
    section: tuple[str, ...]
    ordinal: int
    text: str


def read_document(path: Path) -> list[DocumentBlock]:
    """Read visible paragraphs/table rows in order; headings define sections."""
    blocks: list[DocumentBlock] = []
    headings: list[str] = []

    def add(text: str, level: int = 0) -> None:
        text = text.strip()
        if not text:
            return
        if level:
            del headings[level - 1 :]
            headings.append(text)
        blocks.append(DocumentBlock(tuple(headings), len(blocks) + 1, text))

    if path.suffix.lower() == ".md":
        paragraph: list[str] = []
        for line in path.read_text(encoding="utf-8").splitlines() + [""]:
            heading = re.match(r"^(#{1,6})\s+(.+)$", line)
            if heading or not line.strip():
                add("\n".join(paragraph))
                paragraph = []
                if heading:
                    add(heading[2], len(heading[1]))
            else:
                paragraph.append(line)
    elif path.suffix.lower() == ".docx":
        with ZipFile(path) as archive:
            body = ET.fromstring(archive.read("word/document.xml")).find(f"{W}body")
        if body is None:
            raise ValueError("DOCX has no document body")
        for element in body:
            if element.tag == f"{W}p":
                style = element.find(f"{W}pPr/{W}pStyle")
                name = style.get(f"{W}val", "") if style is not None else ""
                match = re.fullmatch(r"Heading([1-6])", name, re.I)
                add(_paragraph_text(element), int(match[1]) if match else 0)
            elif element.tag == f"{W}tbl":
                for row in element.findall(f"{W}tr"):
                    add(
                        " | ".join(
                            "\n".join(_paragraph_text(p) for p in cell.iter(f"{W}p"))
                            for cell in row.findall(f"{W}tc")
                        )
                    )
    else:
        raise ValueError(f"Unsupported document extension: {path.suffix}")
    return blocks


def load_manifest(root: Path) -> list[dict]:
    root = Path(root).resolve()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema_version") != 1
        or not isinstance(manifest.get("documents"), list)
    ):
        raise ValueError("Expected manifest schema_version=1 and documents array")
    seen_versions, seen_paths = set(), set()
    for doc in manifest["documents"]:
        if not isinstance(doc, dict):
            raise ValueError("Each document must be a metadata object")
        for key in ("id", "path", "project_id", "title", "published_at", "version"):
            if not isinstance(doc.get(key), str) or not doc[key].strip():
                raise ValueError(f"Missing/invalid document {key}")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", doc["id"]) or not re.fullmatch(
            r"[A-Za-z0-9_-]{1,12}", doc["version"]
        ):
            raise ValueError("Invalid document id/version")
        if doc.get("synthetic") is not True:
            raise ValueError("Interview documents must be explicitly synthetic")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", doc["published_at"]):
            raise ValueError("published_at must be ISO date")
        date.fromisoformat(doc["published_at"])
        relative = Path(doc["path"])
        path = (root / relative).resolve()
        if relative.is_absolute() or ".." in relative.parts or not path.is_relative_to(root):
            raise ValueError("Document path escapes corpus root")
        if path.suffix.lower() not in {".md", ".docx"} or not path.is_file():
            raise ValueError("Document must be an existing MD or DOCX file")
        identity = (doc["id"], doc["version"])
        if identity in seen_versions or path in seen_paths:
            raise ValueError("Duplicate document id/version or path")
        seen_versions.add(identity)
        seen_paths.add(path)
    return manifest["documents"]


def _windows(text: str, max_chars: int, overlap_chars: int):
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            boundary = text.rfind("\n\n", start + max_chars // 2, end)
            if boundary < 0:
                boundary = max(
                    text.rfind(" ", start + max_chars // 2, end),
                    text.rfind("\n", start + max_chars // 2, end),
                )
            if boundary > start:
                end = boundary + 1
        yield start, end
        if end == len(text):
            break
        next_start = max(start + 1, end - overlap_chars)
        # Preserve coverage; reduce overlap to start at a word boundary when possible.
        while next_start < end and next_start > 0 and not text[next_start - 1].isspace():
            next_start += 1
        start = next_start


def load_document_evidence(
    project_id: str,
    root: Path = DEFAULT_ROOT,
    *,
    max_chars: int = 1200,
    overlap_chars: int = 150,
    as_of: date | None = None,
) -> list[EvidenceCandidate]:
    if max_chars < 2 or not 0 <= overlap_chars < max_chars:
        raise ValueError("Require max_chars >= 2 and 0 <= overlap_chars < max_chars")
    root = Path(root)
    candidates = []
    for doc in load_manifest(root):
        published = date.fromisoformat(doc["published_at"])
        if doc["project_id"] != project_id or (as_of is not None and published > as_of):
            continue
        blocks = read_document(root / doc["path"])
        sections: list[list[DocumentBlock]] = []
        for block in blocks:
            if not sections or sections[-1][-1].section != block.section:
                sections.append([])
            sections[-1].append(block)
        ordinal = 0
        for section in sections:
            text = "\n\n".join(block.text for block in section)
            spans, offset = [], 0
            for block in section:
                spans.append((offset, offset + len(block.text), block.ordinal))
                offset += len(block.text) + 2
            for start, end in _windows(text, max_chars, overlap_chars):
                ordinal += 1
                touched = [n for a, b, n in spans if a < end and b > start]
                if not touched:
                    continue
                section_name = " / ".join(section[0].section) or "Документ"
                candidates.append(
                    EvidenceCandidate(
                        project_id=project_id,
                        source_table="documents",
                        source_id=f"{doc['id']}:v{doc['version']}:c{ordinal:04d}",
                        entity_type="document",
                        entity_id=doc["id"],
                        title=f"{doc['title']} — {section_name}",
                        text=text[start:end],
                        occurred_at=datetime.combine(published, time(hour=12)),
                        metadata={
                            "document_id": doc["id"],
                            "version": doc["version"],
                            "file": doc["path"],
                            "section": section_name,
                            "block_start": min(touched),
                            "block_end": max(touched),
                            "published_at": doc["published_at"],
                            "synthetic": True,
                            "char_start": start,
                            "char_end": end,
                            "locator": f"{doc['path']}#{section_name}; blocks {min(touched)}-{max(touched)}",
                        },
                    )
                )
    return candidates
