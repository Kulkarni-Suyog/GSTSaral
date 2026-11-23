"""FastAPI service for GSTSaral with persistent Chroma semantic search (/search/semantic)."""

import sys
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, Query

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.vectorstore import GSTSaralVectorStore

VECTOR_STORE = GSTSaralVectorStore()
INDEXED_COUNT = VECTOR_STORE.ensure_indexed()

app = FastAPI(
    title="GSTSaral Semantic Search API",
    description="GSTSaral FastAPI service backed by a persistent ChromaDB vector collection.",
    version="0.3.0",
)


@app.get("/health")
def health_check() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service": "GSTSaral",
        "indexed_chunks": VECTOR_STORE.collection.count(),
        "embedding_backend": VECTOR_STORE.embedder.backend,
    }


@app.post("/index/rebuild")
def rebuild_index() -> Dict[str, Any]:
    count = VECTOR_STORE.index_chunks(reset=True)
    return {"status": "rebuilt", "indexed_chunks": count}


@app.get("/search/semantic")
def semantic_search_endpoint(
    q: str = Query(..., min_length=1, description="Natural-language GST query"),
    top_k: int = Query(default=3, ge=1, le=20, description="Number of semantic hits to return"),
) -> Dict[str, Any]:
    """Search GSTSaral chunks in persistent ChromaDB using semantic vector similarity."""
    hits = VECTOR_STORE.semantic_search(q, top_k=top_k)
    return {
        "query": q,
        "count": len(hits),
        "results": hits,
    }
