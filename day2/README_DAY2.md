# Day 2 — 56th GST Council Rate Changes & Modular CLI

## Folder Structure
```text
day2/
├── .gitignore
├── requirements.txt
├── README_DAY2.md
├── data/
│   └── sample_records.py
└── app/
    ├── __init__.py
    ├── records.py
    └── cli.py
```

## Setup `.venv` & Run (PowerShell)
```powershell
# 1. Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run S1 standalone data script
python data\sample_records.py

# 4. Run S2 modular CLI
python app\cli.py
```
