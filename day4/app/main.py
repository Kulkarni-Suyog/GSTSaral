"""FastAPI service for GSTSaral (Day 4 — Week 1 Milestone)."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.smart_search import SmartSearchEngine

DATA_JSON_PATH = ROOT_DIR / "data" / "records.json"

FALLBACK_RECORDS: List[Dict[str, Any]] = [
    {
        "id": 1,
        "category": "Personal Care",
        "item_or_topic": "Toilet soap bars",
        "old_rule": "18% GST",
        "new_rule": "5% GST",
        "effective_from": "2025-09-22",
        "document": "56th GST Council Meeting Press Release (PIB PRID 2163555)",
        "source_url": "https://www.pib.gov.in/PressReleaseDetail.aspx?PRID=2163555",
    },
    {
        "id": 2,
        "category": "Personal Care",
        "item_or_topic": "Hair oil and shampoos",
        "old_rule": "18% GST",
        "new_rule": "5% GST",
        "effective_from": "2025-09-22",
        "document": "56th GST Council Meeting Press Release (PIB PRID 2163555)",
        "source_url": "https://www.pib.gov.in/PressReleaseDetail.aspx?PRID=2163555",
    },
    {
        "id": 3,
        "category": "Dairy & Bakery",
        "item_or_topic": "Ultra-High Temperature (UHT) milk",
        "old_rule": "5% GST",
        "new_rule": "Nil (0% GST)",
        "effective_from": "2025-09-22",
        "document": "56th GST Council Meeting Press Release (PIB PRID 2163555)",
        "source_url": "https://www.pib.gov.in/PressReleaseDetail.aspx?PRID=2163555",
    },
    {
        "id": 4,
        "category": "Dairy & Bakery",
        "item_or_topic": "Pre-packaged and labelled chena or paneer",
        "old_rule": "5% GST",
        "new_rule": "Nil (0% GST)",
        "effective_from": "2025-09-22",
        "document": "56th GST Council Meeting Press Release (PIB PRID 2163555)",
        "source_url": "https://www.pib.gov.in/PressReleaseDetail.aspx?PRID=2163555",
    },
    {
        "id": 5,
        "category": "Dairy & Bakery",
        "item_or_topic": "Butter, ghee, and dairy spreads",
        "old_rule": "12% GST",
        "new_rule": "5% GST",
        "effective_from": "2025-09-22",
        "document": "56th GST Council Meeting Press Release (PIB PRID 2163555)",
        "source_url": "https://www.pib.gov.in/PressReleaseDetail.aspx?PRID=2163555",
    },
    {
        "id": 6,
        "category": "Stationery",
        "item_or_topic": "Exercise books, graph books, and notebooks",
        "old_rule": "12% GST",
        "new_rule": "Nil (0% GST)",
        "effective_from": "2025-09-22",
        "document": "56th GST Council Meeting Press Release (PIB PRID 2163555)",
        "source_url": "https://www.pib.gov.in/PressReleaseDetail.aspx?PRID=2163555",
    },
    {
        "id": 7,
        "category": "Stationery",
        "item_or_topic": "Pencils, crayons, pastels, and erasers",
        "old_rule": "12% GST",
        "new_rule": "Nil (0% GST)",
        "effective_from": "2025-09-22",
        "document": "56th GST Council Meeting Press Release (PIB PRID 2163555)",
        "source_url": "https://www.pib.gov.in/PressReleaseDetail.aspx?PRID=2163555",
    },
    {
        "id": 8,
        "category": "Household & Mobility",
        "item_or_topic": "Bicycles and bicycle parts",
        "old_rule": "12% GST",
        "new_rule": "5% GST",
        "effective_from": "2025-09-22",
        "document": "56th GST Council Meeting Press Release (PIB PRID 2163555)",
        "source_url": "https://www.pib.gov.in/PressReleaseDetail.aspx?PRID=2163555",
    },
    {
        "id": 9,
        "category": "Packaged Food",
        "item_or_topic": "Packaged namkeens, bhujia, pasta, and instant noodles",
        "old_rule": "12% GST",
        "new_rule": "5% GST",
        "effective_from": "2025-09-22",
        "document": "56th GST Council Meeting Press Release (PIB PRID 2163555)",
        "source_url": "https://www.pib.gov.in/PressReleaseDetail.aspx?PRID=2163555",
    },
    {
        "id": 10,
        "category": "Packaged Food",
        "item_or_topic": "Chocolates, sauces, jams, and cornflakes",
        "old_rule": "18% GST",
        "new_rule": "5% GST",
        "effective_from": "2025-09-22",
        "document": "56th GST Council Meeting Press Release (PIB PRID 2163555)",
        "source_url": "https://www.pib.gov.in/PressReleaseDetail.aspx?PRID=2163555",
    },
]


def load_gst_records() -> List[Dict[str, Any]]:
    """Load records from data/records.json (ensuring every record has an integer id)."""
    if DATA_JSON_PATH.exists():
        with open(DATA_JSON_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
    else:
        raw = FALLBACK_RECORDS

    normalized: List[Dict[str, Any]] = []
    for idx, rec in enumerate(raw, start=1):
        item = dict(rec)
        item.setdefault("id", idx)
        normalized.append(item)
    return normalized


RECORDS: List[Dict[str, Any]] = load_gst_records()
SEARCH_ENGINE = SmartSearchEngine(RECORDS)

app = FastAPI(
    title="GSTSaral API",
    description="Plain-language Indian GST rate & compliance API powered by TF-IDF search.",
    version="0.1.0-week1",
)


class QuestionRequest(BaseModel):
    question: str = Field(..., min_length=3, description="User's GST question")
    user_name: Optional[str] = Field(default="Anonymous", description="Optional user name")
    top_k: int = Field(default=3, ge=1, le=10, description="Number of supporting records to retrieve")


@app.get("/health")
def health_check() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service": "GSTSaral",
        "version": "week-1",
        "records_loaded": len(RECORDS),
    }


@app.get("/records")
def list_records(
    limit: int = Query(default=10, ge=1, le=500, description="Maximum number of records to return"),
) -> Dict[str, Any]:
    sliced = RECORDS[:limit]
    return {
        "total": len(RECORDS),
        "limit": limit,
        "count": len(sliced),
        "records": sliced,
    }


@app.get("/records/{record_id}")
def get_record_by_id(record_id: int) -> Dict[str, Any]:
    for r in RECORDS:
        if r.get("id") == record_id:
            return r
    raise HTTPException(status_code=404, detail=f"Record with id={record_id} not found")


@app.get("/search")
def search_records(
    q: str = Query(..., min_length=1, description="Search query string"),
    top_k: int = Query(default=5, ge=1, le=50, description="Number of ranked results"),
) -> Dict[str, Any]:
    matches = SEARCH_ENGINE.search(q, top_k=top_k)
    return {
        "query": q,
        "count": len(matches),
        "results": matches,
    }


@app.post("/questions")
def ask_question(payload: QuestionRequest) -> Dict[str, Any]:
    matches = SEARCH_ENGINE.search(payload.question, top_k=payload.top_k)
    if matches:
        top = matches[0]
        answer = (
            f"Based on {top.get('document', 'GST records')}, '{top['item_or_topic']}' "
            f"changed from {top['old_rule']} to {top['new_rule']} "
            f"(effective {top['effective_from']})."
        )
    else:
        answer = "No exact rate-change record matched your question. Try keywords like soap, milk, paneer, notebook, or bicycle."

    return {
        "question": payload.question,
        "user_name": payload.user_name,
        "answered_at": datetime.now(timezone.utc).isoformat(),
        "answer": answer,
        "supporting_records": matches,
    }
