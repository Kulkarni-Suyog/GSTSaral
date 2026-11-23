"""Production guardrails for GSTSaral: request latency & token logging, TTL cache, input limits & prompt-injection check."""

import hashlib
import logging
import re
import time
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple

MAX_QUESTION_CHARS = 1000
MAX_TOP_K = 10
DEFAULT_CACHE_TTL_SECONDS = 300.0
DEFAULT_CACHE_MAX_SIZE = 256

logger = logging.getLogger("gstsaral.prod")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

_INJECTION_PATTERNS: Tuple[re.Pattern[str], ...] = (
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions", re.IGNORECASE),
    re.compile(r"disregard\s+(your\s+)?(system\s+)?(prompt|rules|instructions)", re.IGNORECASE),
    re.compile(r"reveal\s+(your\s+)?(system\s+prompt|hidden\s+instructions|api\s+key|secret)", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(in\s+)?(developer|jailbreak|dan|admin)\s+mode", re.IGNORECASE),
    re.compile(r"<\s*/?\s*system\s*>", re.IGNORECASE),
)


def estimate_tokens(text: str) -> int:
    """Estimate token count cleanly (~4 chars per token for English/GST queries & answers)."""
    cleaned = (text or "").strip()
    if not cleaned:
        return 0
    return max(1, (len(cleaned) + 3) // 4)


def check_prompt_injection(text: str) -> Optional[str]:
    """Return a matched reason string if prompt-injection phrasing is detected, else None."""
    for pat in _INJECTION_PATTERNS:
        match = pat.search(text or "")
        if match:
            return f"Blocked potential prompt-injection pattern: '{match.group(0)}'"
    return None


def validate_ask_inputs(question: str, top_k: int) -> Tuple[str, int]:
    """Enforce input length and top_k bounds before hitting retrieval or cache."""
    if not isinstance(question, str) or not question.strip():
        raise ValueError("Question must be non-empty.")
    trimmed = question.strip()
    if len(trimmed) > MAX_QUESTION_CHARS:
        raise ValueError(f"Question exceeds maximum allowed length of {MAX_QUESTION_CHARS} characters.")
    if not isinstance(top_k, int) or top_k < 1 or top_k > MAX_TOP_K:
        raise ValueError(f"top_k must be between 1 and {MAX_TOP_K}.")
    return trimmed, top_k


class SimpleTTLCache:
    """Lightweight bounded LRU + TTL cache for repeated /ask queries."""

    def __init__(self, max_size: int = DEFAULT_CACHE_MAX_SIZE, ttl_seconds: float = DEFAULT_CACHE_TTL_SECONDS) -> None:
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._store: "OrderedDict[str, Tuple[float, Dict[str, Any]]]" = OrderedDict()
        self.hits = 0
        self.misses = 0

    @staticmethod
    def make_key(question: str, top_k: int) -> str:
        norm = " ".join(question.lower().split())
        digest = hashlib.sha256(f"{top_k}:{norm}".encode("utf-8")).hexdigest()[:16]
        return digest

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        now = time.monotonic()
        entry = self._store.get(key)
        if entry is None:
            self.misses += 1
            return None
        expires_at, payload = entry
        if expires_at < now:
            del self._store[key]
            self.misses += 1
            return None
        self._store.move_to_end(key)
        self.hits += 1
        return payload

    def set(self, key: str, value: Dict[str, Any]) -> None:
        now = time.monotonic()
        if key in self._store:
            del self._store[key]
        while len(self._store) >= self.max_size:
            self._store.popitem(last=False)
        self._store[key] = (now + self.ttl_seconds, value)

    def clear(self) -> None:
        self._store.clear()

    def stats(self) -> Dict[str, int]:
        return {
            "entries": len(self._store),
            "hits": self.hits,
            "misses": self.misses,
        }


class RequestTelemetryLogger:
    """Records per-request latency (ms), prompt/completion tokens, and cache hit status."""

    def __init__(self, max_events: int = 500) -> None:
        self.max_events = max_events
        self.events: List[Dict[str, Any]] = []

    def record(
        self,
        endpoint: str,
        question: str,
        answer: str,
        latency_ms: float,
        cached: bool,
        status: str = "ok",
    ) -> Dict[str, Any]:
        prompt_tokens = estimate_tokens(question)
        completion_tokens = estimate_tokens(answer)
        entry = {
            "endpoint": endpoint,
            "status": status,
            "cached": cached,
            "latency_ms": round(latency_ms, 2),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        }
        self.events.append(entry)
        if len(self.events) > self.max_events:
            self.events.pop(0)
        logger.info(
            "endpoint=%s status=%s cached=%s latency_ms=%.2f prompt_tokens=%d completion_tokens=%d total_tokens=%d",
            endpoint,
            status,
            cached,
            entry["latency_ms"],
            prompt_tokens,
            completion_tokens,
            entry["total_tokens"],
        )
        return entry
