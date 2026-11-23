"""FastAPI backend for GSTSaral: /ask, /agent (LangGraph), /feedback, and /metrics."""

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.graph import invoke_langgraph_agent  # noqa: E402
from app.observability import (  # noqa: E402
    MAX_QUESTION_CHARS,
    MAX_TOP_K,
    RequestTelemetryLogger,
    SimpleTTLCache,
    check_prompt_injection,
    validate_ask_inputs,
)
from app.tools import get_rag  # noqa: E402

FEEDBACK_FILE = ROOT_DIR / "data" / "feedback.jsonl"
ASK_CACHE = SimpleTTLCache()
TELEMETRY = RequestTelemetryLogger()

app = FastAPI(
    title="GSTSaral API",
    description="Grounded RAG (/ask) + Old-vs-Current Rule Detector + LangGraph Approval Agent (/agent) + Feedback",
    version="1.2.0",
)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=MAX_QUESTION_CHARS)
    top_k: int = Field(default=4, ge=1, le=MAX_TOP_K)


class GraphAgentRequest(BaseModel):
    thread_id: str = Field(default="checkpoint-2-session", min_length=1)
    query: Optional[str] = Field(default=None)
    approve: Optional[bool] = Field(default=None)
    approval_note: str = Field(default="")
    overrides: Optional[Dict[str, Any]] = Field(default=None)


class FeedbackRequest(BaseModel):
    session_id: str = Field(default="default")
    turn_index: int = Field(..., ge=0)
    mode: str = Field(..., description="ask or agent")
    question: str
    answer: str
    rating: str = Field(..., pattern="^(up|down)$", description="'up' for thumbs up, 'down' for thumbs down")
    comment: str = Field(default="")


@app.get("/")
def root() -> Dict[str, Any]:
    return {
        "service": "GSTSaral",
        "status": "live",
        "endpoints": ["/health", "/ask", "/agent", "/feedback", "/metrics", "/docs"],
    }


@app.get("/health")
def health() -> Dict[str, Any]:
    rag = get_rag()
    return {
        "status": "ok",
        "checkpoint": "checkpoint-2",
        "chunks_indexed": len(rag.chunks),
        "signature_feature": "old_vs_current_warning",
    }


@app.get("/metrics")
def metrics() -> Dict[str, Any]:
    return {
        "cache": ASK_CACHE.stats(),
        "recent_requests": TELEMETRY.events[-20:],
        "limits": {
            "max_question_chars": MAX_QUESTION_CHARS,
            "max_top_k": MAX_TOP_K,
        },
    }


@app.post("/ask")
def ask(payload: AskRequest) -> Dict[str, Any]:
    start = time.perf_counter()
    try:
        clean_q, clean_k = validate_ask_inputs(payload.question, payload.top_k)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    injection_reason = check_prompt_injection(clean_q)
    if injection_reason:
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        refusal = (
            "I cannot process requests containing prompt-injection or instruction-override patterns. "
            "Please ask a factual Indian GST rate, threshold, or rule question."
        )
        TELEMETRY.record(
            endpoint="/ask",
            question=clean_q,
            answer=refusal,
            latency_ms=elapsed_ms,
            cached=False,
            status="blocked_injection",
        )
        raise HTTPException(status_code=400, detail=injection_reason)

    cache_key = ASK_CACHE.make_key(clean_q, clean_k)
    cached_resp = ASK_CACHE.get(cache_key)
    if cached_resp is not None:
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        out = dict(cached_resp)
        out["telemetry"] = TELEMETRY.record(
            endpoint="/ask",
            question=clean_q,
            answer=out.get("answer", ""),
            latency_ms=elapsed_ms,
            cached=True,
            status="cache_hit",
        )
        return out

    result = get_rag().ask(clean_q, top_k=clean_k)
    ASK_CACHE.set(cache_key, result)
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    out = dict(result)
    out["telemetry"] = TELEMETRY.record(
        endpoint="/ask",
        question=clean_q,
        answer=out.get("answer", ""),
        latency_ms=elapsed_ms,
        cached=False,
        status="ok",
    )
    return out


@app.post("/agent")
def run_agent(payload: GraphAgentRequest) -> Dict[str, Any]:
    try:
        return invoke_langgraph_agent(
            thread_id=payload.thread_id,
            query=payload.query,
            approve=payload.approve,
            approval_note=payload.approval_note,
            overrides=payload.overrides,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/feedback")
def save_feedback(payload: FeedbackRequest) -> Dict[str, Any]:
    FEEDBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **payload.model_dump(),
    }
    with FEEDBACK_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return {"saved": True, "file": str(FEEDBACK_FILE), "record": record}


@app.get("/feedback")
def list_feedback() -> Dict[str, Any]:
    if not FEEDBACK_FILE.exists():
        return {"count": 0, "items": []}
    items = [
        json.loads(line)
        for line in FEEDBACK_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return {"count": len(items), "items": items}
