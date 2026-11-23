# Day 6 — LLM Wrapper (`Groq` / `Gemini`), Structured `/chat`, & Prompt Evaluation

## Folder Structure
```text
day6/
├── .env.example              # Safe template committed to Git (.env is gitignored)
├── .gitignore                # Explicitly ignores .env while keeping .env.example
├── requirements.txt
├── README_DAY6.md
├── app/
│   ├── __init__.py
│   ├── llm.py                # Groq & Gemini provider wrapper returning {answer, confidence, follow_up}
│   ├── smart_search.py       # TF-IDF context retriever
│   └── main.py               # FastAPI app with POST /chat
├── prompts/
│   ├── system.txt            # GSTSaral system prompt with grounding & abstention rules
│   ├── task_v1_concise.txt   # Prompt v1: concise 1-2 sentence lookup
│   └── task_v2_structured.txt# Prompt v2: structured Verdict / Before-After / Source breakdown
├── eval/
│   ├── run_prompt_eval.py    # Script to run both prompt versions across the 10 questions
│   └── prompt_compare.md     # Full comparison table & analysis across all 10 questions
└── data/
    └── records.json
```

## Setup & Run (PowerShell)
```powershell
# 1. Create local .env from .env.example (DO NOT commit .env)
Copy-Item .env.example .env
# Edit .env and paste your GEMINI_API_KEY or GROQ_API_KEY

# 2. Install packages
pip install -r requirements.txt

# 3. Start FastAPI server
uvicorn app.main:app --reload --port 8000

# 4. Test POST /chat
Invoke-RestMethod -Uri "http://127.0.0.1:8000/chat" -Method Post -ContentType "application/json" -Body '{"question": "What is the new GST rate on UHT milk?", "prompt_version": "v2"}'

# 5. Run 10-question prompt comparison script
python eval\run_prompt_eval.py
```
