"""Embedding generator & semantic search helper for GSTSaral chunks."""

import hashlib
import math
import os
import re
from typing import Any, Dict, List, Optional

import numpy as np

from app.chunking import DocumentChunk


class LocalEmbeddingFunction:
    """
    Dense embedding generator using sentence-transformers ('all-MiniLM-L6-v2')
    with a deterministic hashed-ngram dense fallback if offline/uninstalled.
    Compatible with ChromaDB's EmbeddingFunction protocol.
    """

    def __init__(self, model_name: Optional[str] = None, dim: int = 384) -> None:
        self.model_name = model_name or os.getenv("EMBED_MODEL", "all-MiniLM-L6-v2")
        self.dim = dim
        self._st_model = None
        self.backend = "hashed-dense-fallback"

        if os.getenv("USE_OFFLINE_EMBED", "0") != "1":
            try:
                from sentence_transformers import SentenceTransformer

                self._st_model = SentenceTransformer(self.model_name)
                self.backend = f"sentence-transformers:{self.model_name}"
            except Exception:
                self._st_model = None

    def _hashed_embed(self, texts: List[str]) -> List[List[float]]:
        vectors: List[List[float]] = []
        for text in texts:
            vec = np.zeros(self.dim, dtype=np.float32)
            tokens = re.findall(r"[a-z0-9%]+", (text or "").lower())
            ngrams = list(tokens) + [
                f"{tokens[i]}_{tokens[i + 1]}" for i in range(len(tokens) - 1)
            ]
            for tok in ngrams:
                digest = hashlib.blake2b(tok.encode("utf-8"), digest_size=8).digest()
                idx = int.from_bytes(digest[:4], "little") % self.dim
                sign = 1.0 if (digest[4] & 1) == 0 else -1.0
                vec[idx] += sign
            norm = float(np.linalg.norm(vec))
            if norm > 0:
                vec /= norm
            vectors.append(vec.tolist())
        return vectors

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        if self._st_model is not None:
            embs = self._st_model.encode(texts, normalize_embeddings=True)
            return embs.tolist()
        return self._hashed_embed(texts)

    def __call__(self, input: List[str]) -> List[List[float]]:
        """ChromaDB EmbeddingFunction interface."""
        return self.embed_texts(list(input))


def semantic_search_chunks(
    query: str,
    chunks: List[DocumentChunk],
    embedder: Optional[LocalEmbeddingFunction] = None,
    top_k: int = 3,
) -> List[Dict[str, Any]]:
    """Embed chunks & query and return top_k chunks ranked by cosine similarity."""
    if not chunks or not (query or "").strip():
        return []

    emb = embedder or LocalEmbeddingFunction()
    doc_vectors = np.array(emb.embed_texts([c.text for c in chunks]), dtype=np.float32)
    q_vector = np.array(emb.embed_texts([query])[0], dtype=np.float32)

    # Cosine similarity (vectors are L2-normalized)
    denom = np.linalg.norm(doc_vectors, axis=1) * max(float(np.linalg.norm(q_vector)), 1e-12)
    scores = np.dot(doc_vectors, q_vector) / np.maximum(denom, 1e-12)
    ranked_indices = np.argsort(scores)[::-1][:top_k]

    hits: List[Dict[str, Any]] = []
    for idx in ranked_indices:
        chunk = chunks[int(idx)]
        hits.append(
            {
                "chunk_id": chunk.chunk_id,
                "score": round(float(scores[int(idx)]), 4),
                "title": chunk.title,
                "source": chunk.source,
                "page": chunk.page,
                "source_url": chunk.source_url,
                "text": chunk.text,
            }
        )
    return hits
