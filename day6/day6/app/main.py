import json
import re
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

from app.llm import GSTSaralLLM

app = FastAPI(title="GSTSaral API (Day 6)", version="0.6.0")
llm = GSTSaralLLM()

APP_ROOT = Path(__file__).resolve().parents[1]


def _load_records() -> list[dict[str, Any]]:
    for base in [APP_ROOT, APP_ROOT.parent, APP_ROOT.parent.parent]:
        for filename in ["chunks.json", "records.json", "gst_records.json"]:
            candidate = base / "data" / filename
            if candidate.exists():
                data = json.loads(candidate.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    return data

    try:
        from data.sample_records import SAMPLE_RECORDS

        return SAMPLE_RECORDS
    except Exception:
        return []


RECORDS = _load_records()


def _tokenize(text: str) -> set[str]:
    stop_words = {"what", "is", "the", "for", "on", "in", "of", "to", "a", "an", "and", "gst"}
    words = set(re.findall(r"[a-z0-9]+", text.lower()))
    return words - stop_words or words


def retrieve(query: str, top_k: int = 3) -> list[dict[str, Any]]:
    q_tokens = _tokenize(query)
    scored: list[tuple[int, int, dict[str, Any]]] = []

    for r in RECORDS:
        searchable = " ".join(
            str(r.get(k, ""))
            for k in ("item_or_topic", "title", "category", "old_rule", "new_rule", "text", "content")
        )
        overlap = len(q_tokens & _tokenize(searchable))
        if overlap > 0:
            year = int(r.get("rule_year") or r.get("year") or 2017)
            scored.append((overlap, year, r))

    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [item[2] for item in scored[:top_k]]


class SimpleSearchEngine:
    """Compatibility wrapper expected by eval/run_prompt_eval.py."""

    def __init__(self, records: list[dict[str, Any]]) -> None:
        self.records = records

    def search(self, query: str, top_k: int = 3) -> list[dict[str, Any]]:
        return retrieve(query=query, top_k=top_k)

    def retrieve(self, query: str, top_k: int = 3) -> list[dict[str, Any]]:
        return retrieve(query=query, top_k=top_k)

    def query(self, query: str, top_k: int = 3) -> list[dict[str, Any]]:
        return retrieve(query=query, top_k=top_k)


SEARCH_ENGINE = SimpleSearchEngine(RECORDS)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)
    top_k: int = Field(default=3, ge=1, le=10)


@app.get("/")
def root() -> dict[str, Any]:
    return {
        "service": "GSTSaral API",
        "status": "running",
        "records_loaded": len(RECORDS),
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "records_loaded": len(RECORDS),
        "model": llm.model,
        "api_key_configured": bool(llm.api_key),
    }


@app.post("/chat")
def chat(req: ChatRequest) -> dict[str, Any]:
    results = SEARCH_ENGINE.search(req.message, top_k=req.top_k)

    if not results:
        return {
            "answer": "I don't know based on the current GST knowledge base.",
            "sources": [],
            "rule_conflict_warning": None,
        }

    context_lines = []
    has_rule_change = False
    for idx, r in enumerate(results, start=1):
        topic = r.get("item_or_topic") or r.get("title") or f"Record {idx}"
        new_rule = r.get("new_rule") or r.get("text") or r.get("content") or ""
        old_rule = r.get("old_rule", "")
        source = r.get("source", "CBIC / GST Council")

        if old_rule and old_rule != new_rule:
            has_rule_change = True

        context_lines.append(
            f"[{idx}] {topic} (Source: {source})\n"
            f"    Current Rule: {new_rule}\n"
            f"    Previous Rule: {old_rule or 'N/A'}"
        )

    context_text = "\n\n".join(context_lines)
    system_prompt = (
        "You are GSTSaral, an Indian GST compliance assistant. Answer strictly using the "
        "provided GST context with inline citations like [1], [2]. If an older rule differs "
        "from the current rule, clearly state that the latest rule wins."
    )
    user_prompt = f"Context:\n{context_text}\n\nQuestion: {req.message}"

    answer = llm.generate(
        prompt=user_prompt,
        system_prompt=system_prompt,
        fallback_context=context_text,
    )

    warning = (
        "Latest rule wins: One or more matched topics had an older GST rate/rule that was superseded."
        if has_rule_change
        else None
    )

    return {
        "answer": answer,
        "rule_conflict_warning": warning,
        "sources": results,
    }