import re
from data.sample_records import SAMPLE_RECORDS


def get_all_records() -> list[dict]:
    return SAMPLE_RECORDS


def _tokenize(text: str) -> set[str]:
    stop_words = {"what", "is", "the", "for", "on", "in", "of", "to", "a", "an", "and", "gst"}
    words = set(re.findall(r"[a-z0-9]+", text.lower()))
    return words - stop_words or words


def search_records(query: str, top_k: int = 3) -> list[dict]:
    q_tokens = _tokenize(query)
    scored: list[tuple[int, int, dict]] = []

    for r in SAMPLE_RECORDS:
        text = (
            f"{r['item_or_topic']} {r['category']} "
            f"{r['old_rule']} {r['new_rule']}"
        )
        overlap = len(q_tokens & _tokenize(text))
        if overlap > 0:
            scored.append((overlap, int(r.get("rule_year", 2017)), r))

    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [item[2] for item in scored[:top_k]]