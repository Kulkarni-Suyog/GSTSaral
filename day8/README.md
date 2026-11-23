# Day 8 — Grounded RAG (`POST /ask` with Citations & `"I don't know"`) + 15-Row Evaluation

## Folder Structure
```text
day8/
├── README.md
├── requirements.txt
├── .gitignore
├── app/
│   ├── __init__.py
│   ├── chunking.py      # Configurable text/record chunker preserving source, page & title
│   ├── rag.py           # Hybrid retriever + grounded generator with citations & "I don't know" abstention
│   └── main.py          # FastAPI service exposing POST /ask and GET /health
├── eval/
│   ├── eval_set.json    # 15 benchmark questions (13 answerable + 2 out-of-scope including Q6)
│   ├── run_eval.py      # Evaluates 2 configs (chunk_size / top_k) and writes eval_results.json
│   └── eval_results.json# Full per-question evaluation metrics for both configs
└── data/
    └── records.json     # 15 structured GSTSaral records
```

## RAG Evaluation Winner Table (`eval/run_eval.py` on 15-Question `eval_set.json`)

| Configuration | `chunk_size` | `top_k` | Total Chunks | Retrieval Recall@K | Answer Keyword Accuracy | Citation Rate | Out-of-Scope Abstention (`Q6` & `Q15`) | Overall Pass Rate | Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Config A (Small Chunks / Narrow Top-K)** | `140` | `1` | 36 | 92.3% | 38.5% | 100.0% | 100.0% (`Q6` = `True`) | **46.7%** (7/15) | Runner-up |
| **Config B (Full-Record Chunks / Wider Top-K)** | `350` | `3` | 17 | 100.0% | 100.0% | 100.0% | 100.0% (`Q6` = `True`) | **100.0%** (15/15) | **WINNER** |

### Why `Config B (Full-Record Chunks / Wider Top-K)` Won
- **Zero Mid-Rule Splitting (`chunk_size=350`):** Keeping each GST rate rule intact in a single chunk preserves both `old_rule` and `new_rule` together, whereas `chunk_size=140` splits a single rule across multiple fragments and drops critical rate tokens when `top_k=1`.
- **Higher Multi-Item Coverage (`top_k=3`) + Strict Abstention:** Retrieving top-3 chunks captures multi-item questions with 100% recall and citations while enforcing domain-token and relevance grounding so out-of-scope queries like **Q6** (GSTR-9C late fees) cleanly return `"I don't know"`.

## How to Run (PowerShell)
```powershell
pip install -r requirements.txt

# 1. Run 2-config evaluation on the 15-row eval_set.json
python eval\run_eval.py

# 2. Start FastAPI server & test POST /ask
uvicorn app.main:app --reload --port 8000

# Answerable query (returns answer with [1] citations):
Invoke-RestMethod -Uri "http://127.0.0.1:8000/ask" -Method Post -ContentType "application/json" -Body '{"question": "What is the new GST rate on toilet soap bars?"}'

# Out-of-scope Q6 query (returns "I don't know" with abstained=true):
Invoke-RestMethod -Uri "http://127.0.0.1:8000/ask" -Method Post -ContentType "application/json" -Body '{"question": "What is the exact GST late fee penalty and interest calculation for filing GSTR-9C three months late in FY 2025-26?"}'
```
