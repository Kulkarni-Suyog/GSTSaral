"""RAG pipeline for GSTSaral with citations, 'I don't know' abstention, and Old vs Current FAQ warning."""

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
        self.dense_matrix = (
            self._embed_texts(self.texts) if self.texts else np.zeros((0, dim), dtype=np.float32)
        )

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

    def retrieve(self, query: str, top_k: int = 4) -> List[Dict[str, Any]]:
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
                    "topic_key": c.topic_key,
                    "rule_year": c.rule_year,
                    "effective_from": c.effective_from,
                    "new_rule": c.new_rule,
                    "text": c.text,
                }
            )
        return results


class GSTSaralRAG:
    """Grounded RAG pipeline with 'Old vs Current' superseding-rule detector."""

    def __init__(
        self,
        chunk_size: int = 350,
        overlap: int = 50,
        top_k: int = 4,
        min_relevance_score: float = 0.18,
        min_lexical_score: float = 0.08,
        llm_client: Optional[Any] = None,
    ) -> None:
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.top_k = top_k
        self.min_relevance_score = min_relevance_score
        self.min_lexical_score = min_lexical_score
        self.llm_client = llm_client

        self.chunks = build_chunks(chunk_size=chunk_size, overlap=overlap)
        self.retriever = HybridRetriever(self.chunks)

        self.latest_by_topic: Dict[str, DocumentChunk] = {}
        for c in self.chunks:
            if not c.topic_key:
                continue
            existing = self.latest_by_topic.get(c.topic_key)
            if existing is None or (c.rule_year, c.effective_from) > (existing.rule_year, existing.effective_from):
                self.latest_by_topic[c.topic_key] = c

    def _is_answerable(self, question: str, hits: List[Dict[str, Any]]) -> bool:
        if not hits:
            return False
        best = hits[0]
        if best["score"] < self.min_relevance_score or best["lexical_score"] < self.min_lexical_score:
            return False

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
        return len(q_tokens & chunk_tokens) >= 1

    def _detect_old_vs_current_warning(
        self, supporting: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        for hit in supporting:
            tk = hit.get("topic_key", "")
            hit_year = int(hit.get("rule_year", 2025))
            latest = self.latest_by_topic.get(tk)
            if latest and latest.rule_year > hit_year:
                old_cite = {
                    "label": "Older FAQ Citation",
                    "chunk_id": hit["chunk_id"],
                    "title": hit["title"],
                    "source": hit["source"],
                    "page": hit["page"],
                    "rule_year": hit_year,
                    "effective_from": hit.get("effective_from", ""),
                    "source_url": hit.get("source_url", ""),
                }
                new_cite = {
                    "label": "Current Rule Citation",
                    "chunk_id": latest.chunk_id,
                    "title": latest.title,
                    "source": latest.source,
                    "page": latest.page,
                    "rule_year": latest.rule_year,
                    "effective_from": latest.effective_from,
                    "source_url": latest.source_url,
                }
                era = "2017/18" if hit_year in (2017, 2018) else str(hit_year)
                banner_text = (
                    f"This FAQ is from {era} — newer rule: {latest.new_rule} "
                    f"(effective {latest.effective_from}, {latest.source}, p.{latest.page})."
                )
                return {
                    "triggered": True,
                    "banner": banner_text,
                    "old_year": hit_year,
                    "new_year": latest.rule_year,
                    "old_rule": hit.get("new_rule", hit.get("text", "")),
                    "newer_rule": latest.new_rule,
                    "effective_from": latest.effective_from,
                    "old_citation": old_cite,
                    "new_citation": new_cite,
                }
        return None

    def generate_answer(self, question: str, supporting: List[Dict[str, Any]]) -> Optional[str]:
        """Generate grounded text via injected `llm_client` (or Gemini/Groq env vars if set)."""
        context_lines = [
            f"[{i}] (chunk={h['chunk_id']}, source={h['source']}, page={h['page']}): {h['text']}"
            for i, h in enumerate(supporting, start=1)
        ]
        prompt = (
            "Answer the GST question using ONLY the numbered context chunks below. "
            "Include inline citations like [1] or [1, 2].\n\n"
            f"Context:\n{chr(10).join(context_lines)}\n\nQuestion: {question}"
        )

        if self.llm_client is not None:
            return str(self.llm_client.generate(prompt)).strip()

        provider = os.getenv("LLM_PROVIDER", "").strip().lower()
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
                "old_vs_current_warning": None,
                "retrieved_chunks": hits,
            }

        supporting = [h for h in hits if h["lexical_score"] >= 0.04] or [hits[0]]
        warning = self._detect_old_vs_current_warning(supporting)

        cite_pool = list(supporting)
        if warning is not None:
            new_cid = warning["new_citation"]["chunk_id"]
            if not any(c["chunk_id"] == new_cid for c in cite_pool):
                latest_chunk = self.latest_by_topic[supporting[0]["topic_key"]]
                cite_pool.append(
                    {
                        "chunk_id": latest_chunk.chunk_id,
                        "title": latest_chunk.title,
                        "source": latest_chunk.source,
                        "page": latest_chunk.page,
                        "source_url": latest_chunk.source_url,
                        "rule_year": latest_chunk.rule_year,
                        "score": 1.0,
                        "text": latest_chunk.text,
                    }
                )

        citations = [
            {
                "ref": f"[{idx}]",
                "chunk_id": h["chunk_id"],
                "title": h["title"],
                "source": h["source"],
                "page": h["page"],
                "rule_year": h.get("rule_year", 2025),
                "source_url": h["source_url"],
                "score": h["score"],
            }
            for idx, h in enumerate(cite_pool, start=1)
        ]

        llm_text = self.generate_answer(question, cite_pool)
        if llm_text:
            answer_text = llm_text
        elif warning is not None:
            latest_chunk = self.latest_by_topic[supporting[0]["topic_key"]]
            answer_text = (
                f"Current Rule: {latest_chunk.text} [2] "
                f"(Supersedes earlier {warning['old_year']} FAQ: {supporting[0]['text']} [1])"
            )
        else:
            statements = [f"{h['text']} [{idx}]" for idx, h in enumerate(supporting[:2], start=1)]
            answer_text = " ".join(statements)

        return {
            "question": question,
            "answer": answer_text,
            "abstained": False,
            "citations": citations,
            "old_vs_current_warning": warning,
            "retrieved_chunks": hits,
        }
