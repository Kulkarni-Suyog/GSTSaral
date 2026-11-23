"""Configurable document & record chunker for GSTSaral preserving source, page, title, topic_key & rule_year."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List

ROOT_DIR = Path(__file__).resolve().parent.parent
RECORDS_JSON = ROOT_DIR / "data" / "records.json"


@dataclass
class DocumentChunk:
    chunk_id: str
    text: str
    title: str
    source: str
    page: int
    source_url: str = ""
    topic_key: str = ""
    rule_year: int = 2025
    effective_from: str = ""
    new_rule: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def split_text_with_overlap(text: str, chunk_size: int = 350, overlap: int = 50) -> List[str]:
    cleaned = " ".join((text or "").split()).strip()
    if not cleaned:
        return []
    if len(cleaned) <= chunk_size:
        return [cleaned]

    chunks: List[str] = []
    start = 0
    while start < len(cleaned):
        end = min(len(cleaned), start + chunk_size)
        if end < len(cleaned):
            space_idx = cleaned.rfind(" ", start + chunk_size // 2, end)
            if space_idx != -1:
                end = space_idx
        segment = cleaned[start:end].strip()
        if segment:
            chunks.append(segment)
        if end >= len(cleaned):
            break
        start = max(end - overlap, start + 1)
    return chunks


def build_chunks(
    chunk_size: int = 350,
    overlap: int = 50,
    records_path: Path = RECORDS_JSON,
) -> List[DocumentChunk]:
    all_chunks: List[DocumentChunk] = []
    if not records_path.exists():
        return all_chunks

    records = json.loads(records_path.read_text(encoding="utf-8"))
    for idx, r in enumerate(records, start=1):
        title = str(r.get("item_or_topic", f"GST Record {idx}")).strip()
        category = str(r.get("category", "General GST")).strip()
        old_rule = str(r.get("old_rule", "N/A")).strip()
        new_rule = str(r.get("new_rule", "N/A")).strip()
        effective = str(r.get("effective_from", "2025-09-22")).strip()
        doc = str(r.get("document", "56th GST Council Meeting Press Release")).strip()
        url = str(r.get("source_url", "")).strip()
        page_num = int(r.get("page", 1))
        topic_key = str(r.get("topic_key", f"topic_{idx}")).strip()
        rule_year = int(r.get("rule_year", int(effective[:4]) if effective[:4].isdigit() else 2025))

        rich_text = (
            f"Topic / Item: {title} (Category: {category}). "
            f"Previous GST rate: {old_rule}. Revised GST rate: {new_rule}, "
            f"effective from {effective}. Source document: {doc}."
        )
        pieces = split_text_with_overlap(rich_text, chunk_size=chunk_size, overlap=overlap)
        for p_idx, piece in enumerate(pieces, start=1):
            cid = f"rec_{r.get('id', idx):03d}" if len(pieces) == 1 else f"rec_{r.get('id', idx):03d}_c{p_idx}"
            all_chunks.append(
                DocumentChunk(
                    chunk_id=cid,
                    text=piece,
                    title=title,
                    source=doc,
                    page=page_num,
                    source_url=url,
                    topic_key=topic_key,
                    rule_year=rule_year,
                    effective_from=effective,
                    new_rule=new_rule,
                )
            )
    return all_chunks
