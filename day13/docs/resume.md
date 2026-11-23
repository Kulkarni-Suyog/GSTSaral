# Resume Bullets — GSTSaral (Grounded Indian GST Assistant & Invoice Agent)

* Architected **GSTSaral**, a grounded Retrieval-Augmented Generation (RAG) and invoice calculation system in Python, FastAPI, and Streamlit over 20 structured Indian GST records (56th GST Council press release, registration thresholds, and 2017/18 CBIC FAQs), enforcing inline source citations and explicit `"I don't know"` abstention on out-of-scope queries.
* Built a temporal **Old vs. Current Rule Detector** (`2017/18` vs. `2025` rules) paired with a LangGraph `MemorySaver` agent and human-in-the-loop approval gate (`interrupt`) for intra-state (`CGST + SGST`) and inter-state (`IGST`) GST invoice calculations.
* Hardened the service for production with an automated 13-test `pytest` suite, `ruff` linting, GitHub Actions CI (`ruff`, `pytest`, `docker build`), Docker containerization, TTL caching, input validation, prompt-injection filtering, and per-request latency/token telemetry.
