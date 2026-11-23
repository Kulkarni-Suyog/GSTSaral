# Day 9 — GST Invoice Calculator Tool, Hand-Written ReAct Agent & LangGraph Approval Agent (`POST /agent`)

## Folder Structure
```text
day9/
├── README.md
├── requirements.txt
├── .gitignore
├── app/
│   ├── __init__.py
│   ├── chunking.py      # Document/record chunker preserving source, page, and title
│   ├── rag.py           # Hybrid retriever + grounded generator with citations & "I don't know" abstention
│   ├── tools.py         # S1: `gst_invoice_calculator` (CGST+SGST / IGST + inclusive back-calc) & `rag_search_tool`
│   ├── agent_loop.py    # S1: Hand-written Thought -> Action -> Observation agent chaining RAG + calculator
│   ├── graph.py         # S2: LangGraph StateGraph with `MemorySaver` + 1 human approval `interrupt()` step
│   └── main.py          # FastAPI app exposing `POST /agent`, `POST /agent/loop`, `POST /ask`, and `/tools/gst-invoice-calculator`
└── data/
    └── records.json     # 15 structured GSTSaral records
```

## Key Features
- **S1 (`app/tools.py` — `gst_invoice_calculator`):**
  - Accepts `price`, `gst_rate`, `within_maharashtra` (`True` = `CGST + SGST` 50/50 split; `False` = `IGST`), and `price_inclusive_of_gst` (`True` = back-calculates $\text{Taxable Value} = \frac{\text{Price}}{1 + r}$).
- **S1 (`app/agent_loop.py` — `HandWrittenGSTAgent`):**
  - Explicit `Thought -> Action -> Observation` loop that calls `rag_search`, `gst_invoice_calculator`, or chains both automatically when an item + price is given without an explicit GST percentage.
- **S2 (`app/graph.py` & `POST /agent` — LangGraph with Memory + 1 Approval Step):**
  - Uses `MemorySaver` keyed by `thread_id` so multi-turn context (such as inter-state/intra-state supply preference) persists across turns.
  - Pauses at `approval_gate_node` via LangGraph `interrupt()` before executing `gst_invoice_calculator`, returning `status="awaiting_approval"` with the proposed tool arguments, and resumes when `POST /agent` receives `{"thread_id": "...", "approve": true}` (with optional `overrides` or `approval_note`).

## How to Run (PowerShell)
```powershell
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 1. Test S1 Hand-Written Agent Loop (chains rag_search -> gst_invoice_calculator):
Invoke-RestMethod -Uri "http://127.0.0.1:8000/agent/loop" -Method Post -ContentType "application/json" -Body '{"query": "What is the new GST rate on toilet soap bars, and calculate an invoice in Maharashtra for Rs 525 inclusive of GST?"}'

# 2. Test S2 LangGraph POST /agent (Step 1 — pauses at approval gate):
Invoke-RestMethod -Uri "http://127.0.0.1:8000/agent" -Method Post -ContentType "application/json" -Body '{"thread_id": "demo-mh-01", "query": "Calculate GST invoice for butter worth Rs 1050 inclusive of 5% GST within Maharashtra"}'

# 3. Test S2 LangGraph POST /agent (Step 2 — approve & resume from MemorySaver checkpoint):
Invoke-RestMethod -Uri "http://127.0.0.1:8000/agent" -Method Post -ContentType "application/json" -Body '{"thread_id": "demo-mh-01", "approve": true, "approval_note": "Verified by tax reviewer"}'
```
