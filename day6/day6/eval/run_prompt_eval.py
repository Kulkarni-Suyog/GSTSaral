"""Run Prompt v1 vs Prompt v2 across all 10 GSTSaral benchmark questions."""

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.llm import GSTSaralLLM
from app.main import SEARCH_ENGINE

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
    llm = GSTSaralLLM()
    print(f"Running 10-question comparison using provider={llm.provider}, model={llm.model}\n")

    for idx, q in enumerate(QUESTIONS, start=1):
        ctx = SEARCH_ENGINE.search(q, top_k=3)
        res_v1 = llm.generate_chat_response(q, ctx, prompt_version="v1")
        res_v2 = llm.generate_chat_response(q, ctx, prompt_version="v2")
        print(f"=== Q{idx}: {q} ===")
        print("v1:", json.dumps({k: res_v1[k] for k in ("answer", "confidence", "follow_up")}, ensure_ascii=False))
        print("v2:", json.dumps({k: res_v2[k] for k in ("answer", "confidence", "follow_up")}, ensure_ascii=False))
        print()


if __name__ == "__main__":
    main()
