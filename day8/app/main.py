"""FastAPI service for GSTSaral RAG (POST /ask with citations & abstention)."""

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI
from pydantic import BaseModel, Field

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.rag import GSTSaralRAG

RAG_PIPELINE = GSTSaralRAG(chunk_size=300, overlap=50, top_k=3)

app = FastAPI(
    title="GSTSaral RAG API",
    description="Grounded Indian GST Question Answering with Citations and Abstention",
    version="0.4.0",
)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=3, description="User's GST question")
    top_k: int = Field(default=3, ge=1, le=10, description="Number of chunks to retrieve")


class CitationItem(BaseModel):
    ref: str
    chunk_id: str
    title: str
    source: str
    page: int
    source_url: str
    score: float


class AskResponse(BaseModel):
    question: str
    answer: str
    abstained: bool
    citations: List[CitationItem]
    retrieved_chunks: List[Dict[str, Any]]


@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service": "GSTSaral RAG",
        "chunks_indexed": len(RAG_PIPELINE.chunks),
        "chunk_size": RAG_PIPELINE.chunk_size,
        "default_top_k": RAG_PIPELINE.top_k,
    }


@app.post("/ask", response_model=AskResponse)
def ask_gstsaral(payload: AskRequest) -> AskResponse:
    """Answer GSTSaral questions from retrieved chunks with citations; says 'I don't know' when unsupported."""
    result = RAG_PIPELINE.ask(payload.question, top_k=payload.top_k)
    return AskResponse(**result)
