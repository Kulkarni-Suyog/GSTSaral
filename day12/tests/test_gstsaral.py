"""Comprehensive pytest suite (10 tests) for GSTSaral records, search, API, fake LLM & agent tools."""

import json
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ["USE_OFFLINE_EMBED"] = "1"

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.agent_loop import HandWrittenGSTAgent  # noqa: E402
from app.chunking import build_chunks  # noqa: E402
from app.main import app  # noqa: E402
from app.rag import GSTSaralRAG  # noqa: E402
from app.tools import get_rag, gst_invoice_calculator  # noqa: E402


class FakeLLM:
    """Deterministic fake LLM client for offline unit testing of /ask."""

    def __init__(self, canned_reply: str) -> None:
        self.canned_reply = canned_reply
        self.prompts_seen: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts_seen.append(prompt)
        return self.canned_reply


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def test_01_records_schema_and_count() -> None:
    """Verify data/records.json contains 20 valid records with required schema fields."""
    records_path = ROOT_DIR / "data" / "records.json"
    assert records_path.exists(), "data/records.json must exist"
    records = json.loads(records_path.read_text(encoding="utf-8"))
    assert len(records) == 20
    required_keys = {"id", "category", "item_or_topic", "old_rule", "new_rule", "effective_from", "document"}
    for rec in records:
        assert required_keys.issubset(rec.keys())


def test_02_chunking_preserves_metadata() -> None:
    """Verify build_chunks preserves source, page, title, topic_key, and rule_year."""
    chunks = build_chunks(chunk_size=350, overlap=50)
    assert len(chunks) >= 20
    sample = chunks[0]
    assert sample.title
    assert sample.source
    assert sample.page >= 1
    assert sample.topic_key == "toilet_soap"
    assert sample.rule_year == 2025


def test_03_hybrid_search_retrieves_relevant_gst_chunk() -> None:
    """Verify hybrid search retrieves the 56th GST Council paneer Nil-rate chunk."""
    rag = GSTSaralRAG()
    hits = rag.retriever.retrieve("What is the GST rate on pre-packaged paneer?", top_k=3)
    assert len(hits) == 3
    assert "paneer" in hits[0]["title"].lower()
    assert "Nil (0% GST)" in hits[0]["text"]


def test_04_old_vs_current_warning_on_2017_faq() -> None:
    """Verify querying a 2017/18 FAQ triggers the Old vs Current warning with both citations."""
    rag = GSTSaralRAG()
    res = rag.ask("What was the 2017 GST FAQ rate on toilet soap bars?")
    assert res["abstained"] is False
    warning = res["old_vs_current_warning"]
    assert warning is not None
    assert warning["triggered"] is True
    assert "This FAQ is from 2017/18" in warning["banner"]
    assert warning["old_citation"]["rule_year"] == 2017
    assert warning["new_citation"]["rule_year"] == 2025


def test_05_health_endpoint(client: TestClient) -> None:
    """Verify GET /health returns status ok and indexed chunk count."""
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["chunks_indexed"] >= 20


def test_06_ask_endpoint_with_fake_llm(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify POST /ask invokes the injected fake LLM with grounded context and returns citations."""
    rag = get_rag()
    fake_llm = FakeLLM("FakeLLM Answer: UHT milk is taxed at Nil (0% GST) effective 2025-09-22 [1].")
    monkeypatch.setattr(rag, "llm_client", fake_llm)

    resp = client.post("/ask", json={"question": "What is the GST rate on UHT milk?", "top_k": 3})
    assert resp.status_code == 200
    data = resp.json()
    assert data["abstained"] is False
    assert data["answer"].startswith("FakeLLM Answer:")
    assert len(fake_llm.prompts_seen) == 1
    assert "Ultra-High Temperature (UHT) milk" in fake_llm.prompts_seen[0]
    assert len(data["citations"]) >= 1


def test_07_ask_endpoint_abstains_on_out_of_scope_query(client: TestClient) -> None:
    """Verify POST /ask abstains with 'I don't know' when question is outside the corpus."""
    resp = client.post(
        "/ask",
        json={"question": "What is the late fee penalty for GSTR-9C three months overdue in FY 2025-26?"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["abstained"] is True
    assert data["answer"].lower().startswith("i don't know")
    assert data["citations"] == []


def test_08_gst_invoice_calculator_intra_state_maharashtra_inclusive() -> None:
    """Verify intra-state Maharashtra CGST+SGST split and GST-inclusive back-calculation."""
    result = gst_invoice_calculator(
        price=1050.0,
        gst_rate=5.0,
        within_maharashtra=True,
        price_inclusive_of_gst=True,
    )
    assert result["taxable_value"] == 1000.0
    assert result["cgst_rate_percent"] == 2.5
    assert result["cgst_amount"] == 25.0
    assert result["sgst_rate_percent"] == 2.5
    assert result["sgst_amount"] == 25.0
    assert result["igst_amount"] == 0.0
    assert result["total_invoice_amount"] == 1050.0


def test_09_gst_invoice_calculator_inter_state_igst_exclusive() -> None:
    """Verify inter-state (outside Maharashtra) IGST calculation on GST-exclusive base price."""
    result = gst_invoice_calculator(
        price=2000.0,
        gst_rate=18.0,
        within_maharashtra=False,
        price_inclusive_of_gst=False,
    )
    assert result["taxable_value"] == 2000.0
    assert result["cgst_amount"] == 0.0
    assert result["sgst_amount"] == 0.0
    assert result["igst_rate_percent"] == 18.0
    assert result["igst_amount"] == 360.0
    assert result["total_invoice_amount"] == 2360.0


def test_10_handwritten_agent_chains_rag_and_calculator() -> None:
    """Verify HandWrittenGSTAgent chains rag_search -> gst_invoice_calculator when rate is omitted."""
    agent = HandWrittenGSTAgent()
    out = agent.run(
        "What is the revised GST rate on toilet soap bars, and calculate an invoice in Maharashtra for Rs 525 inclusive of GST?"
    )
    actions = [step["action"] for step in out["steps"]]
    assert actions == ["rag_search", "gst_invoice_calculator"]
    assert out["invoice_calculation"]["taxable_value"] == 500.0
    assert out["invoice_calculation"]["cgst_amount"] == 12.5
    assert out["invoice_calculation"]["sgst_amount"] == 12.5
