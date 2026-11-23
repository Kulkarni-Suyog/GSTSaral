"""Evaluate 2 RAG configurations (chunk_size / top_k) against eval/eval_set.json (15 rows)."""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

os.environ.setdefault("USE_OFFLINE_EMBED", "1")

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.rag import GSTSaralRAG

EVAL_SET_PATH = ROOT_DIR / "eval" / "eval_set.json"
RESULTS_JSON_PATH = ROOT_DIR / "eval" / "eval_results.json"

CONFIGS = [
    {
        "name": "Config A (Small Chunks / Narrow Top-K)",
        "chunk_size": 140,
        "overlap": 25,
        "top_k": 1,
    },
    {
        "name": "Config B (Full-Record Chunks / Wider Top-K)",
        "chunk_size": 350,
        "overlap": 50,
        "top_k": 3,
    },
]


def evaluate_config(cfg: Dict[str, Any], eval_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    rag = GSTSaralRAG(
        chunk_size=cfg["chunk_size"],
        overlap=cfg["overlap"],
        top_k=cfg["top_k"],
    )

    total = len(eval_rows)
    answerable_rows = [r for r in eval_rows if not r["should_abstain"]]
    abstain_rows = [r for r in eval_rows if r["should_abstain"]]

    retrieval_hits = 0
    keyword_hits = 0
    citation_hits = 0
    abstention_hits = 0
    q6_passed = False
    per_question: List[Dict[str, Any]] = []

    for row in eval_rows:
        res = rag.ask(row["question"], top_k=cfg["top_k"])
        answer_lower = res["answer"].lower()

        if row["should_abstain"]:
            ok_abstain = res["abstained"] and ("i don't know" in answer_lower)
            if ok_abstain:
                abstention_hits += 1
            if row["id"] == "Q6":
                q6_passed = ok_abstain
            per_question.append(
                {
                    "id": row["id"],
                    "passed": ok_abstain,
                    "abstained": res["abstained"],
                    "answer": res["answer"],
                }
            )
        else:
            expected_prefix = row["expected_chunk_id"] or ""
            retrieved_ids = [c["chunk_id"] for c in res["retrieved_chunks"]]
            hit_chunk = any(cid.startswith(expected_prefix) for cid in retrieved_ids)
            if hit_chunk:
                retrieval_hits += 1

            hit_kw = all(kw.lower() in answer_lower for kw in row["expected_answer_keywords"])
            if hit_kw:
                keyword_hits += 1

            has_cite = len(res["citations"]) > 0 and "[1]" in res["answer"]
            if has_cite:
                citation_hits += 1

            per_question.append(
                {
                    "id": row["id"],
                    "passed": hit_chunk and hit_kw and has_cite,
                    "hit_chunk": hit_chunk,
                    "hit_keywords": hit_kw,
                    "has_citation": has_cite,
                    "top_chunk": retrieved_ids[0] if retrieved_ids else None,
                }
            )

    passed_total = sum(1 for item in per_question if item["passed"])
    retrieval_recall = (retrieval_hits / len(answerable_rows)) * 100
    answer_accuracy = (keyword_hits / len(answerable_rows)) * 100
    citation_rate = (citation_hits / len(answerable_rows)) * 100
    abstention_accuracy = (abstention_hits / len(abstain_rows)) * 100
    overall_score = (passed_total / total) * 100

    return {
        "config": cfg,
        "total_chunks": len(rag.chunks),
        "total_questions": total,
        "passed_total": passed_total,
        "overall_score": round(overall_score, 1),
        "retrieval_recall": round(retrieval_recall, 1),
        "answer_accuracy": round(answer_accuracy, 1),
        "citation_rate": round(citation_rate, 1),
        "abstention_accuracy": round(abstention_accuracy, 1),
        "q6_idk_passed": q6_passed,
        "details": per_question,
    }


def main() -> None:
    eval_rows = json.loads(EVAL_SET_PATH.read_text(encoding="utf-8"))
    summaries = [evaluate_config(cfg, eval_rows) for cfg in CONFIGS]

    RESULTS_JSON_PATH.write_text(json.dumps(summaries, indent=2), encoding="utf-8")

    print("=" * 88)
    print(f"{'Configuration':<42} | {'Chunks':>6} | {'Recall@K':>8} | {'Ans Acc':>7} | {'Abstain':>7} | {'Overall':>7}")
    print("-" * 88)
    for s in summaries:
        cfg = s["config"]
        label = f"{cfg['name']} (cs={cfg['chunk_size']}, k={cfg['top_k']})"
        print(
            f"{label:<42} | {s['total_chunks']:>6} | {s['retrieval_recall']:>7.1f}% | "
            f"{s['answer_accuracy']:>6.1f}% | {s['abstention_accuracy']:>6.1f}% | {s['overall_score']:>6.1f}%"
        )
    print("=" * 88)

    winner = max(summaries, key=lambda x: x["overall_score"])
    print(f"Winner: {winner['config']['name']} ({winner['overall_score']}% overall pass rate, Q6 'I don't know'={winner['q6_idk_passed']})")


if __name__ == "__main__":
    main()
