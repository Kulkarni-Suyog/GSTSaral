"""FastAPI backend for GSTSaral: /ask, /agent (LangGraph), and /feedback."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.graph import invoke_langgraph_agent  # noqa: E402
from app.tools import get_rag  # noqa: E402

FEEDBACK_FILE = ROOT_DIR / "data" / "feedback.jsonl"

app = FastAPI(
    title="GSTSaral API",
    description="Grounded RAG (/ask) + Old-vs-Current Rule Detector + LangGraph Approval Agent (/agent) + Feedback",
    version="1.0.0",
)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=3)
    top_k: int = Field(default=4, ge=1, le=10)


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


@app.get("/health")
def health() -> Dict[str, Any]:
    rag = get_rag()
    return {
        "status": "ok",
        "checkpoint": "checkpoint-2",
        "chunks_indexed": len(rag.chunks),
        "signature_feature": "old_vs_current_warning",
    }


@app.post("/ask")
def ask(payload: AskRequest) -> Dict[str, Any]:
    return get_rag().ask(payload.question, top_k=payload.top_k)


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
