"""Parse and clean downloaded GST Council HTML & PDF files into data/records.json."""

import json
import logging
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

from bs4 import BeautifulSoup
from pypdf import PdfReader

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.fetch import SOURCES, fetch_all
from app.models import Record

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

RAW_DIR = ROOT_DIR / "data" / "raw"
OUTPUT_JSON = ROOT_DIR / "data" / "records.json"

RATE_PATTERN = re.compile(
    r"\b(Nil|0%|5%|12%|18%|28%|40%|exempt)\b",
    re.IGNORECASE,
)


def parse_html_faqs(html_path: Path, document: str, source_url: str) -> List[Record]:
    """Extract Q&A / rule rows from GST Council FAQ HTML pages."""
    records: List[Record] = []
    if not html_path.exists():
        logger.warning("Missing HTML file: %s", html_path)
        return records

    html_text = html_path.read_text(encoding="utf-8", errors="replace")
    soup = BeautifulSoup(html_text, "html.parser")

    # GST Council Drupal FAQ views commonly use .views-row, accordion items, or table rows
    blocks = soup.select(".views-row, .accordion-item, article, table tr")
    if not blocks:
        blocks = soup.find_all(["li", "p"])

    for idx, block in enumerate(blocks, start=1):
        try:
            # Try structured question/answer selectors first
            q_el = block.select_one(
                ".views-field-title, .field-content strong, h2, h3, h4, .accordion-button, td:first-child"
            )
            a_el = block.select_one(
                ".views-field-body, .accordion-body, .field--name-body, td:nth-child(2)"
            )

            if q_el and a_el:
                question = " ".join(q_el.get_text(" ", strip=True).split())
                answer = " ".join(a_el.get_text(" ", strip=True).split())
            else:
                text = " ".join(block.get_text(" ", strip=True).split())
                if len(text) < 25 or "?" not in text:
                    continue
                parts = text.split("?", 1)
                question = parts[0].strip() + "?"
                answer = parts[1].strip()

            if len(question) < 10 or len(answer) < 10:
                continue

            rec = Record(
                item_or_topic=question[:300],
                old_rule="Prior GST FAQ / Not applicable",
                new_rule=answer[:600],
                effective_from="2017-07-01",
                document=document,
                source_url=source_url,
            )
            records.append(rec)
        except Exception as exc:
            logger.warning("Skipping bad HTML row #%d in %s: %s", idx, html_path.name, exc)

    return records


def parse_pdf_rate_changes(pdf_path: Path, document: str, source_url: str) -> List[Record]:
    """Extract rate-change table rows or bullet entries from the 56th Council PIB PDF."""
    records: List[Record] = []
    if not pdf_path.exists():
        logger.warning("Missing PDF file: %s", pdf_path)
        return records

    reader = PdfReader(str(pdf_path))
    full_lines: List[str] = []
    for page_num, page in enumerate(reader.pages, start=1):
        try:
            page_text = page.extract_text() or ""
            for line in page_text.splitlines():
                cleaned = " ".join(line.split()).strip()
                if cleaned:
                    full_lines.append(cleaned)
        except Exception as exc:
            logger.warning("Failed reading page %d of %s: %s", page_num, pdf_path.name, exc)

    for idx, line in enumerate(full_lines, start=1):
        try:
            rates = RATE_PATTERN.findall(line)
            # Look for lines containing at least two tax rates (e.g., "18% ... 5%" or "12% ... Nil")
            if len(rates) < 2:
                continue

            old_rate = rates[0]
            new_rate = rates[1]
            if old_rate.lower() == new_rate.lower():
                continue

            # Strip leading serial numbers and trailing rate columns to isolate item description
            item_text = re.sub(r"^\d+[\.\)]?\s*", "", line)
            first_rate_pos = re.search(RATE_PATTERN, item_text)
            if first_rate_pos and first_rate_pos.start() > 3:
                item_name = item_text[: first_rate_pos.start()].strip(" :-|•")
            else:
                item_name = item_text[:200]

            if len(item_name) < 3:
                continue

            rec = Record(
                item_or_topic=item_name[:250],
                old_rule=f"{old_rate} GST" if "%" in old_rate else old_rate,
                new_rule=f"{new_rate} GST" if "%" in new_rate else new_rate,
                effective_from="2025-09-22",
                document=document,
                source_url=source_url,
            )
            records.append(rec)
        except Exception as exc:
            logger.warning("Skipping bad PDF row #%d in %s: %s", idx, pdf_path.name, exc)

    return records


def deduplicate(records: List[Record]) -> List[Record]:
    seen = set()
    unique: List[Record] = []
    for r in records:
        key = (r.item_or_topic.lower(), r.new_rule.lower(), r.source_url)
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique


def run_ingest(auto_fetch: bool = True) -> List[Dict[str, Any]]:
    """Run full ingestion from data/raw/ and write cleaned records to data/records.json."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    if auto_fetch:
        missing = [s for s in SOURCES if not (RAW_DIR / s["name"]).exists()]
        if missing:
            logger.info("%d raw file(s) missing locally; running fetch_all()...", len(missing))
            fetch_all()

    all_records: List[Record] = []
    for src in SOURCES:
        file_path = RAW_DIR / src["name"]
        try:
            if file_path.suffix.lower() == ".html":
                parsed = parse_html_faqs(file_path, src["document"], src["url"])
            elif file_path.suffix.lower() == ".pdf":
                parsed = parse_pdf_rate_changes(file_path, src["document"], src["url"])
            else:
                logger.warning("Unsupported file type: %s", file_path.name)
                parsed = []

            logger.info("Extracted %d valid record(s) from %s", len(parsed), file_path.name)
            all_records.extend(parsed)
        except Exception as exc:
            logger.error("Error processing %s: %s", file_path.name, exc)

    unique_records = deduplicate(all_records)
    serialized = [r.to_dict() for r in unique_records]

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(serialized, f, indent=2, ensure_ascii=False)

    logger.info("Saved %d cleaned record(s) to %s", len(serialized), OUTPUT_JSON)
    return serialized


if __name__ == "__main__":
    run_ingest(auto_fetch=True)
