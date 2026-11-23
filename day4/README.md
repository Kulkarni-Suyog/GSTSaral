# GSTSaral — Week 1 Milestone (FastAPI + TF-IDF Search + Pandas Exploration)

**GSTSaral** is an AI-powered Goods and Services Tax (GST) assistant that simplifies Indian GST rate lookups and compliance rules in plain language.

## Project Structure
```text
day4/
├── README.md
├── requirements.txt
├── app/
│   ├── __init__.py
│   ├── main.py           # FastAPI endpoints (/health, /records, /records/{id}, /search, /questions)
│   └── smart_search.py   # TF-IDF + cosine similarity ranking engine
├── analysis/
│   └── explore.py        # Prints 3 dataset facts using pandas
└── data/
    └── records.json      # Cleaned GST records store
```

## How to run

### 1. Create & activate virtual environment (PowerShell)
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Run Pandas Exploratory Analysis (S2)
```powershell
python analysis\explore.py
```

### 3. Start the FastAPI Server (S1)
```powershell
uvicorn app.main:app --reload --port 8000
```

### 4. Test Endpoints
- **Health Check:** `GET http://127.0.0.1:8000/health`
- **List Records:** `GET http://127.0.0.1:8000/records?limit=5`
- **Single Record (404 if missing):** `GET http://127.0.0.1:8000/records/1`
- **TF-IDF Smart Search:** `GET http://127.0.0.1:8000/search?q=milk%20paneer`
- **Ask Question:** `POST http://127.0.0.1:8000/questions` with JSON body `{"question": "What is the new GST rate on soap?"}`
- **Interactive Swagger UI:** `http://127.0.0.1:8000/docs`

### 5. Commit & Tag `week-1`
```powershell
git add .
git commit -m "Day 4: Add FastAPI service, TF-IDF smart search, and pandas exploration"
git tag -a week-1 -m "Week 1 milestone: ingestion, FastAPI endpoints, TF-IDF search, pandas EDA"
git push origin main --tags
```
