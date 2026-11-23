"""Run semantic search across all 10 GSTSaral questions and write eval/search_results.md."""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.chunking import build_all_chunks
from app.embed import LocalEmbeddingFunction, semantic_search_chunks

QUESTIONS = [
    "What is the new GST rate on toilet soap bars after the 56th GST Council meeting?",
    "Did the GST rate on Ultra-High Temperature (UHT) milk and packaged paneer drop to Nil (0%)?",
    "How much GST applies to school notebooks, exercise books, and pencils now?",
    "What changed in the GST slab for bicycles and bicycle parts, and from what date?",
    "What is the updated GST rate on butter, ghee, and packaged namkeens?",
    "What is the exact GST late fee penalty and interest calculation for filing GSTR-9C three months late in FY 2025-26?",
    "Are hair oil and shampoos taxed at 5% or 18% GST from September 22, 2025?",
    "Do Indian breads like packaged chapati, roti, and paratha attract any GST now?",
    "What was the old GST rate versus the new GST rate on chocolates and cornflakes?",
    "Which everyday stationery items moved from 12% GST down to 0% (Nil) GST?",
]


def main() -> None:
    chunks = build_all_chunks()
    embedder = LocalEmbeddingFunction()
    lines = [
        "# Semantic Search Evaluation Results (`eval/search_results.md`)",
        "",
        f"- **Chunks Indexed:** {len(chunks)}",
        f"- **Embedding Backend:** `{embedder.backend}`",
        "- **Metadata Preserved per Chunk:** `source`, `page`, `title`",
        "",
        "## Top-3 Semantic Hits for All 10 GSTSaral Benchmark Questions",
        "",
    ]

    for idx, q in enumerate(QUESTIONS, start=1):
        hits = semantic_search_chunks(q, chunks, embedder=embedder, top_k=3)
        lines.append(f"### Q{idx}: {q}")
        lines.append("")
        lines.append("| Rank | Score | Chunk ID | Title | Source | Page | Snippet |")
        lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
        for rank, h in enumerate(hits, start=1):
            snippet = h["text"][:110].replace("|", "/") + "..."
            lines.append(
                f"| {rank} | `{h['score']}` | `{h['chunk_id']}` | {h['title']} | {h['source']} | p.{h['page']} | {snippet} |"
            )
        lines.append("")

    out_path = ROOT_DIR / "eval" / "search_results.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote semantic search results for {len(QUESTIONS)} questions to {out_path}")


if __name__ == "__main__":
    main()
