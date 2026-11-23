"""Retrieval-Augmented Generation (RAG) pipeline for GSTSaral with citations & abstention."""

import hashlib
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*args, **kwargs):
        return False
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.chunking import DocumentChunk, build_chunks

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")


class HybridRetriever:
    """
    Combines dense embeddings (sentence-transformers or hashed 384-d vectors)
    with TF-IDF lexical cosine similarity for reliable GST chunk retrieval.
    """

    def __init__(
        self,
        chunks: List[DocumentChunk],
        dim: int = 384,
        dense_weight: float = 0.45,
        lexical_weight: float = 0.55,
    ) -> None:
        self.chunks = chunks
        self.dim = dim
        self.dense_weight = dense_weight
        self.lexical_weight = lexical_weight
        self._st_model = None

        if os.getenv("USE_OFFLINE_EMBED", "0") != "1":
            try:
                from sentence_transformers import SentenceTransformer

                self._st_model = SentenceTransformer(os.getenv("EMBED_MODEL", "all-MiniLM-L6-v2"))
            except Exception:
                self._st_model = None

        self.texts = [f"{c.title}. {c.text}" for c in chunks]
        self.vectorizer = TfidfVectorizer(lowercase=True, stop_words="english", ngram_range=(1, 2))
        self.tfidf_matrix = self.vectorizer.fit_transform(self.texts) if self.texts else None
        self.dense_matrix = self._embed_texts(self.texts) if self.texts else np.zeros((0, dim), dtype=np.float32)

    def _hashed_embed(self, texts: List[str]) -> np.ndarray:
        mat = np.zeros((len(texts), self.dim), dtype=np.float32)
        for row_idx, text in enumerate(texts):
            tokens = re.findall(r"[a-z0-9%]+", (text or "").lower())
            ngrams = list(tokens) + [f"{tokens[i]}_{tokens[i + 1]}" for i in range(len(tokens) - 1)]
            for tok in ngrams:
                digest = hashlib.blake2b(tok.encode("utf-8"), digest_size=8).digest()
                col = int.from_bytes(digest[:4], "little") % self.dim
                sign = 1.0 if (digest[4] & 1) == 0 else -1.0
                mat[row_idx, col] += sign
            norm = float(np.linalg.norm(mat[row_idx]))
            if norm > 0:
                mat[row_idx] /= norm
        return mat

    def _embed_texts(self, texts: List[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        if self._st_model is not None:
            embs = self._st_model.encode(texts, normalize_embeddings=True)
            return np.asarray(embs, dtype=np.float32)
        return self._hashed_embed(texts)

    def retrieve(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        cleaned = (query or "").strip()
        if not cleaned or not self.chunks:
            return []

        q_vec = self._embed_texts([cleaned])[0]
        dense_scores = np.dot(self.dense_matrix, q_vec)

        q_tfidf = self.vectorizer.transform([cleaned])
        lex_scores = cosine_similarity(q_tfidf, self.tfidf_matrix).flatten()

        combined = (self.dense_weight * dense_scores) + (self.lexical_weight * lex_scores)
        ranked = np.argsort(combined)[::-1][:top_k]

        results: List[Dict[str, Any]] = []
        for idx in ranked:
            c = self.chunks[int(idx)]
            results.append(
                {
                    "chunk_id": c.chunk_id,
                    "score": round(float(combined[int(idx)]), 4),
                    "lexical_score": round(float(lex_scores[int(idx)]), 4),
                    "dense_score": round(float(dense_scores[int(idx)]), 4),
                    "title": c.title,
                    "source": c.source,
                    "page": c.page,
                    "source_url": c.source_url,
                    "text": c.text,
                }
            )
        return results


class GSTSaralRAG:
    """End-to-end RAG pipeline with strict abstention ('I don't know') and inline citations."""

    def __init__(
        self,
        chunk_size: int = 300,
        overlap: int = 50,
        top_k: int = 3,
        min_relevance_score: float = 0.18,
        min_lexical_score: float = 0.08,
    ) -> None:
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.top_k = top_k
        self.min_relevance_score = min_relevance_score
        self.min_lexical_score = min_lexical_score

        self.chunks = build_chunks(chunk_size=chunk_size, overlap=overlap)
        self.retriever = HybridRetriever(self.chunks)

    def _is_answerable(self, question: str, hits: List[Dict[str, Any]]) -> bool:
        if not hits:
            return False
        best = hits[0]
        if best["score"] < self.min_relevance_score or best["lexical_score"] < self.min_lexical_score:
            return False

        # Verify at least one domain-specific content token (excluding generic GST boilerplate words) overlaps
        stopwords = {
            "what", "which", "when", "where", "how", "does", "did", "are", "the", "for", "and",
            "from", "with", "into", "that", "this", "have", "been", "gst", "rate", "rates", "tax",
            "taxed", "slab", "rule", "rules", "new", "old", "updated", "revised", "changed",
            "meeting", "council", "date", "now", "any", "items", "item", "everyday", "exact",
            "calculation", "scheme", "limit", "threshold", "supply", "goods", "normal", "states",
        }
        q_tokens = {
            t for t in re.findall(r"[a-z0-9]+", question.lower())
            if len(t) >= 3 and t not in stopwords and not t.isdigit()
        }
        if not q_tokens:
            return True

        chunk_tokens = set(re.findall(r"[a-z0-9]+", f"{best['title']} {best['text']}".lower()))
        overlap = q_tokens & chunk_tokens
        return len(overlap) >= 1

    def _generate_with_llm_if_configured(
        self, question: str, hits: List[Dict[str, Any]]
    ) -> Optional[str]:
        provider = os.getenv("LLM_PROVIDER", "").strip().lower()
        context_lines = [
            f"[{i}] (chunk={h['chunk_id']}, source={h['source']}, page={h['page']}): {h['text']}"
            for i, h in enumerate(hits, start=1)
        ]
        joined_context = "\n".join(context_lines)
        prompt = (
            "Answer the GST question using ONLY the numbered context chunks below. "
            "Include inline citations like [1] or [1, 2] matching the chunk numbers. "
            "If the chunks do not contain the answer, reply strictly with: "
            "I don't know based on the available GSTSaral documents.\n\n"
            f"Context:\n{joined_context}\n\nQuestion: {question}"
        )

        if provider == "gemini" and os.getenv("GEMINI_API_KEY", "").strip():
            from google import genai

            client = genai.Client(api_key=os.getenv("GEMINI_API_KEY").strip())
            resp = client.models.generate_content(
                model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
                contents=prompt,
            )
            return (resp.text or "").strip()

        if provider == "groq" and os.getenv("GROQ_API_KEY", "").strip():
            from groq import Groq

            client = Groq(api_key=os.getenv("GROQ_API_KEY").strip())
            resp = client.chat.completions.create(
                model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
                temperature=0.1,
                messages=[{"role": "user", "content": prompt}],
            )
            return (resp.choices[0].message.content or "").strip()

        return None

    def ask(self, question: str, top_k: Optional[int] = None) -> Dict[str, Any]:
        """Answer a GSTSaral question from retrieved chunks with citations, or say 'I don't know'."""
        k = top_k or self.top_k
        hits = self.retriever.retrieve(question, top_k=k)

        if not self._is_answerable(question, hits):
            return {
                "question": question,
                "answer": (
                    "I don't know. The available GSTSaral documents do not contain verified "
                    "information to answer this question."
                ),
                "abstained": True,
                "citations": [],
                "retrieved_chunks": hits,
            }

        supporting = [h for h in hits if h["lexical_score"] >= 0.04] or [hits[0]]
        citations = [
            {
                "ref": f"[{idx}]",
                "chunk_id": h["chunk_id"],
                "title": h["title"],
                "source": h["source"],
                "page": h["page"],
                "source_url": h["source_url"],
                "score": h["score"],
            }
            for idx, h in enumerate(supporting, start=1)
        ]

        llm_answer = self._generate_with_llm_if_configured(question, supporting)
        if llm_answer:
            answer_text = llm_answer
        else:
            statements = []
            for idx, h in enumerate(supporting[:2], start=1):
                statements.append(f"{h['text']} [{idx}]")
            answer_text = " ".join(statements)

        return {
            "question": question,
            "answer": answer_text,
            "abstained": False,
            "citations": citations,
            "retrieved_chunks": hits,
        }
