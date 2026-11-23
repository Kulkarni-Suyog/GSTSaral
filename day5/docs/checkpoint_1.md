# Checkpoint 1 — FastAPI Verification, `/docs`, Function Walkthrough & Git Tag

## 1. Run the FastAPI Server
From your project folder (`day4/` or repo root containing `app/main.py`):

```powershell
# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Start FastAPI with live reload
uvicorn app.main:app --reload --port 8000
```

## 2. Verify Interactive `/docs` (Swagger UI)
1. Open your browser to **`http://127.0.0.1:8000/docs`**.
2. You will see all 5 GSTSaral endpoints listed under **default**:
   - `GET /health` — Confirms server status and count of loaded GST records.
   - `GET /records` — Lists records with `?limit=` pagination.
   - `GET /records/{record_id}` — Fetches a single record or returns HTTP `404`.
   - `GET /search` — Runs TF-IDF + cosine similarity ranking for `?q=`.
   - `POST /questions` — Accepts a JSON question, retrieves supporting records, and returns a plain-language answer.
3. Click **`GET /search` -> Try it out**, enter `q = milk`, and click **Execute** to verify ranked JSON results (`score` + record fields).

## 3. Code Walkthrough: Explaining One Function (`SmartSearchEngine.search`)

Located in `app/smart_search.py`:

```python
def search(self, query: str, top_k: int = 5, min_score: float = 0.05) -> List[Dict[str, Any]]:
    cleaned_query = (query or "").strip()
    if not cleaned_query or self.tfidf_matrix is None or not self.records:
        return []

    query_vec = self.vectorizer.transform([cleaned_query])
    scores = cosine_similarity(query_vec, self.tfidf_matrix).flatten()
    ranked_indices = np.argsort(scores)[::-1]
```

**How it works (step by step):**
- **Input guard:** Strips whitespace and exits early with `[]` if the query is blank or no records are loaded.
- **Vectorization:** `self.vectorizer.transform([cleaned_query])` converts the user's search text into a TF-IDF vector using the exact vocabulary learned from the GST records at startup.
- **Cosine similarity & ranking:** `cosine_similarity(...)` computes an angle-based similarity score between `0.0` and `1.0` against every GST record, and `np.argsort(scores)[::-1]` sorts record indices from highest similarity to lowest.
- **Thresholding & fallback:** It keeps records scoring at least `min_score` (attaching `"score"` to each returned dictionary) up to `top_k` items, and falls back to a case-insensitive substring check if rare words had zero TF-IDF overlap.

## 4. Commit & Tag `checkpoint-1`

```powershell
git add docs/how_llms_work.md docs/checkpoint_1.md
git commit -m "Docs: Add how_llms_work.md with diagram, 10 user questions, and Checkpoint 1 guide"
git tag -a checkpoint-1 -m "Checkpoint 1: FastAPI /docs verified, LLM notes, and 10 GSTSaral test questions"
git push origin main --tags
```
