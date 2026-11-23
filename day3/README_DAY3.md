# Day 3 — Real Data Fetch & Ingestion Pipeline

## Structure
```text
day3/
├── .gitignore
├── requirements.txt
├── README_DAY3.md
├── app/
│   ├── __init__.py
│   ├── models.py     # Record dataclass with field validation
│   ├── fetch.py      # Downloads 4 GST Council sources into data/raw/ with retries & timeouts
│   └── ingest.py     # Parses HTML & PDF into cleaned Record dicts -> data/records.json
└── data/
    └── raw/          # Raw downloaded HTML & PDF files
```

## Run (PowerShell)
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Step 1: Download raw documents into data/raw/
python app\fetch.py

# Step 2: Clean & normalize into data/records.json
python app\ingest.py
```
