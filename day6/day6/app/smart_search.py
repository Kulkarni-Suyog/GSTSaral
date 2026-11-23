"""TF-IDF + Cosine Similarity search engine for GSTSaral records."""

from typing import Any, Dict, List
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class SmartSearchEngine:
    def __init__(self, records: List[Dict[str, Any]]) -> None:
        self.records = records
        self.corpus = [self._record_to_text(r) for r in records]
        self.vectorizer = TfidfVectorizer(
            lowercase=True,
            stop_words="english",
            ngram_range=(1, 2),
        )
        self.tfidf_matrix = self.vectorizer.fit_transform(self.corpus) if self.corpus else None

    @staticmethod
    def _record_to_text(record: Dict[str, Any]) -> str:
        fields = [
            str(record.get("item_or_topic", "")),
            str(record.get("category", "")),
            str(record.get("old_rule", "")),
            str(record.get("new_rule", "")),
            str(record.get("document", "")),
        ]
        return " ".join(f for f in fields if f)

    def search(self, query: str, top_k: int = 3, min_score: float = 0.08) -> List[Dict[str, Any]]:
        cleaned_query = (query or "").strip()
        if not cleaned_query or self.tfidf_matrix is None or not self.records:
            return []

        query_vec = self.vectorizer.transform([cleaned_query])
        scores = cosine_similarity(query_vec, self.tfidf_matrix).flatten()
        ranked_indices = np.argsort(scores)[::-1]

        results: List[Dict[str, Any]] = []
        for idx in ranked_indices:
            score = float(scores[idx])
            if score < min_score:
                continue
            item = dict(self.records[int(idx)])
            item["score"] = round(score, 4)
            results.append(item)
            if len(results) >= top_k:
                break
        return results
