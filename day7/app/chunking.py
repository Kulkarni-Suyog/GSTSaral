"""Document & record chunking for GSTSaral preserving source, page, and title metadata."""

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List

from pypdf import PdfReader

ROOT_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT_DIR / "data" / "raw"
RECORDS_JSON = ROOT_DIR / "data" / "records.json"


@dataclass
class DocumentChunk:
    chunk_id: str
    text: str
    title: str
    source: str
    page: int
    source_url: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def split_text_with_overlap(text: str, chunk_size: int = 450, overlap: int = 80) -> List[str]:
    """Split text into overlapping character windows aligned on word boundaries."""
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


def chunk_pdf_file(
    pdf_path: Path,
    title: str,
    source_url: str = "",
    chunk_size: int = 450,
    overlap: int = 80,
) -> List[DocumentChunk]:
    """Chunk a PDF page-by-page while keeping source filename, page number, and title."""
    chunks: List[DocumentChunk] = []
    if not pdf_path.exists():
        return chunks

    reader = PdfReader(str(pdf_path))
    for page_num, page in enumerate(reader.pages, start=1):
        raw_text = page.extract_text() or ""
        for idx, piece in enumerate(split_text_with_overlap(raw_text, chunk_size, overlap), start=1):
            chunks.append(
                DocumentChunk(
                    chunk_id=f"{pdf_path.stem}_p{page_num}_c{idx}",
                    text=piece,
                    title=title,
                    source=pdf_path.name,
                    page=page_num,
                    source_url=source_url,
                )
            )
    return chunks


def chunk_html_file(
    html_path: Path,
    title: str,
    page: int = 1,
    source_url: str = "",
    chunk_size: int = 450,
    overlap: int = 80,
) -> List[DocumentChunk]:
    """Chunk an HTML document keeping source filename, page number, and title."""
    chunks: List[DocumentChunk] = []
    if not html_path.exists():
        return chunks

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html_path.read_text(encoding="utf-8", errors="replace"), "html.parser")
    text = soup.get_text(" ", strip=True)
    for idx, piece in enumerate(split_text_with_overlap(text, chunk_size, overlap), start=1):
        chunks.append(
            DocumentChunk(
                chunk_id=f"{html_path.stem}_p{page}_c{idx}",
                text=piece,
                title=title,
                source=html_path.name,
                page=page,
                source_url=source_url,
            )
        )
    return chunks


def chunk_structured_records(records_path: Path = RECORDS_JSON) -> List[DocumentChunk]:
    """Convert cleaned JSON GST records into rich semantic chunks with source, page, and title."""
    if not records_path.exists():
        return []

    records = json.loads(records_path.read_text(encoding="utf-8"))
    chunks: List[DocumentChunk] = []
    for idx, r in enumerate(records, start=1):
        title = str(r.get("item_or_topic", f"GST Record {idx}")).strip()
        category = str(r.get("category", "General GST")).strip()
        old_rule = str(r.get("old_rule", "N/A")).strip()
        new_rule = str(r.get("new_rule", "N/A")).strip()
        effective = str(r.get("effective_from", "2025-09-22")).strip()
        doc = str(r.get("document", "56th GST Council Meeting Press Release")).strip()
        url = str(r.get("source_url", "")).strip()
        page_num = int(r.get("page", 1))

        rich_text = (
            f"Topic / Item: {title} (Category: {category}). "
            f"Previous GST rate: {old_rule}. Revised GST rate: {new_rule}, "
            f"effective from {effective}. Source document: {doc}."
        )
        chunks.append(
            DocumentChunk(
                chunk_id=f"rec_{r.get('id', idx):03d}",
                text=rich_text,
                title=title,
                source=doc,
                page=page_num,
                source_url=url,
            )
        )
    return chunks


def build_all_chunks() -> List[DocumentChunk]:
    """Build chunks from any raw PDF/HTML files in data/raw/ plus data/records.json."""
    all_chunks: List[DocumentChunk] = []

    if RAW_DIR.exists():
        for pdf_file in sorted(RAW_DIR.glob("*.pdf")):
            all_chunks.extend(
                chunk_pdf_file(
                    pdf_file,
                    title="56th GST Council Meeting PIB Press Release",
                    source_url="https://gstcouncil.gov.in/sites/default/files/2025-09/press_release_press_information_bureau.pdf",
                )
            )
        for html_file in sorted(RAW_DIR.glob("*.html")):
            page_match = re.search(r"page(\d+)", html_file.stem)
            page_num = int(page_match.group(1)) + 1 if page_match else 1
            all_chunks.extend(
                chunk_html_file(
                    html_file,
                    title=f"GST Council Official FAQs (Page {page_num})",
                    page=page_num,
                    source_url=f"https://gstcouncil.gov.in/en/faq?page={page_num - 1}",
                )
            )

    all_chunks.extend(chunk_structured_records(RECORDS_JSON))
    return all_chunks


if __name__ == "__main__":
    built = build_all_chunks()
    print(f"Built {len(built)} total document chunk(s).")
    for c in built[:3]:
        print(c.to_dict())
