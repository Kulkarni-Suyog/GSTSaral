# Day 7 — Chunking, Embeddings, Persistent ChromaDB & `/search/semantic`

## Folder Structure
```text
day7/
├── .gitignore
├── requirements.txt
├── README_DAY7.md
├── app/
│   ├── __init__.py
│   ├── chunking.py           # Splits PDF/HTML/JSON records into chunks keeping source, page & title
│   ├── embed.py              # Dense embeddings (sentence-transformers + offline fallback) & cosine search
│   ├── vectorstore.py        # Persistent ChromaDB collection indexer & query interface
│   └── main.py               # FastAPI app exposing GET /search/semantic?q=
├── eval/
│   ├── run_semantic_eval.py  # Re-runs semantic search across all 10 benchmark questions
│   └── search_results.md     # Recorded top-3 hits & scores for all 10 questions
└── data/
    └── records.json
```

## Run (PowerShell)
```powershell
pip install -r requirements.txt

# 1. Index all chunks into persistent ChromaDB (data/chroma_db/)
python app\vectorstore.py

# 2. Run semantic evaluation on all 10 questions -> eval/search_results.md
python eval\run_semantic_eval.py

# 3. Start FastAPI server & test GET /search/semantic
uvicorn app.main:app --reload --port 8000
# Open: http://127.0.0.1:8000/search/semantic?q=new%20GST%20rate%20on%20UHT%20milk
```
