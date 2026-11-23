"""FastAPI service exposing POST /agent (LangGraph with memory + approval) & POST /ask."""

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.agent_loop import HandWrittenGSTAgent
from app.graph import invoke_langgraph_agent
from app.tools import get_rag, gst_invoice_calculator

HANDWRITTEN_AGENT = HandWrittenGSTAgent()

app = FastAPI(
    title="GSTSaral Agent API (Day 9)",
    description="GST Invoice Calculator Tool + Hand-Written Agent Loop + LangGraph Memory & Approval Endpoint",
    version="0.5.0",
)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=3)
    top_k: int = Field(default=3, ge=1, le=10)


class AgentLoopRequest(BaseModel):
    query: str = Field(..., min_length=3, description="User query for the hand-written ReAct agent loop")


class GraphAgentRequest(BaseModel):
    thread_id: str = Field(default="default-session", min_length=1, description="Conversation memory thread ID")
    query: Optional[str] = Field(default=None, description="User question or invoice request")
    approve: Optional[bool] = Field(
        default=None,
        description="Set to true/false to resume an awaiting_approval checkpoint on this thread_id",
    )
    approval_note: str = Field(default="", description="Optional reviewer note when approving/rejecting")
    overrides: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional parameter overrides (price, gst_rate, within_maharashtra, price_inclusive_of_gst)",
    )


class InvoiceCalcRequest(BaseModel):
    price: float = Field(..., ge=0)
    gst_rate: float = Field(..., ge=0)
    within_maharashtra: bool = Field(default=True)
    price_inclusive_of_gst: bool = Field(default=False)


@app.get("/health")
def health() -> Dict[str, Any]:
    rag = get_rag()
    return {
        "status": "ok",
        "service": "GSTSaral Day 9 Agent",
        "chunks_indexed": len(rag.chunks),
        "tools": ["rag_search", "gst_invoice_calculator"],
        "langgraph_checkpointer": "MemorySaver",
        "approval_gate": "enabled",
    }


@app.post("/ask")
def ask(payload: AskRequest) -> Dict[str, Any]:
    return get_rag().ask(payload.question, top_k=payload.top_k)


@app.post("/tools/gst-invoice-calculator")
def run_invoice_calculator(payload: InvoiceCalcRequest) -> Dict[str, Any]:
    return gst_invoice_calculator(
        price=payload.price,
        gst_rate=payload.gst_rate,
        within_maharashtra=payload.within_maharashtra,
        price_inclusive_of_gst=payload.price_inclusive_of_gst,
    )


@app.post("/agent/loop")
def run_handwritten_agent(payload: AgentLoopRequest) -> Dict[str, Any]:
    """Run S1 hand-written ReAct agent loop (rag_search + gst_invoice_calculator)."""
    return HANDWRITTEN_AGENT.run(payload.query)


@app.post("/agent")
def run_langgraph_agent(payload: GraphAgentRequest) -> Dict[str, Any]:
    """
    S2 LangGraph endpoint with MemorySaver + 1 human-in-the-loop approval step:
    1) Send {"thread_id": "t1", "query": "Calculate GST invoice for Rs 1050 inclusive of 5% GST in Maharashtra"}
       -> returns status="awaiting_approval" with proposed tool arguments.
    2) Send {"thread_id": "t1", "approve": true}
       -> resumes checkpoint and returns approved CGST+SGST / IGST invoice breakdown.
    """
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
