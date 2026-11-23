"""Streamlit Chat UI for GSTSaral (Checkpoint 2): /ask & /agent, Citations, Thumbs Up/Down & Old-vs-Current Warning."""

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import requests
import streamlit as st

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

FEEDBACK_FILE = ROOT_DIR / "data" / "feedback.jsonl"
DEFAULT_API_URL = os.getenv("GSTSARAL_API_URL", "http://127.0.0.1:8000")

st.set_page_config(
    page_title="GSTSaral — Checkpoint 2 Live Demo",
    page_icon="🧾",
    layout="wide",
)

st.markdown(
    """
    <style>
    .old-vs-current-banner {
        background-color: #FEF3C7;
        border-left: 6px solid #D97706;
        color: #78350F;
        padding: 14px 16px;
        border-radius: 6px;
        margin: 10px 0 14px 0;
        font-size: 0.95rem;
        line-height: 1.5;
        box-shadow: 0 1px 2px rgba(0,0,0,0.06);
    }
    .old-vs-current-banner strong {
        color: #92400E;
    }
    .cite-pill {
        display: inline-block;
        background: #EFF6FF;
        border: 1px solid #BFDBFE;
        color: #1E40AF;
        padding: 3px 9px;
        border-radius: 999px;
        font-size: 0.80rem;
        margin-right: 6px;
        margin-bottom: 4px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Initialize session state
if "session_id" not in st.session_state:
    st.session_state.session_id = f"cp2-{uuid.uuid4().hex[:8]}"
if "messages" not in st.session_state:
    st.session_state.messages = []
if "feedback_votes" not in st.session_state:
    st.session_state.feedback_votes = {}
if "pending_approval" not in st.session_state:
    st.session_state.pending_approval = None


def persist_feedback_locally(record: Dict[str, Any]) -> None:
    FEEDBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
    with FEEDBACK_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def submit_feedback(api_base: str, use_direct: bool, idx: int, msg: Dict[str, Any], rating: str) -> None:
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": st.session_state.session_id,
        "turn_index": idx,
        "mode": msg.get("mode", "ask"),
        "question": msg.get("question", ""),
        "answer": msg.get("content", ""),
        "rating": rating,
    }
    st.session_state.feedback_votes[idx] = rating
    if not use_direct:
        try:
            resp = requests.post(f"{api_base.rstrip('/')}/feedback", json=record, timeout=5)
            if resp.ok:
                return
        except Exception:
            pass
    persist_feedback_locally(record)


def call_backend(
    api_base: str,
    use_direct: bool,
    mode: str,
    query: str = "",
    approve: Any = None,
    approval_note: str = "",
) -> Dict[str, Any]:
    if not use_direct:
        try:
            if mode == "ask":
                r = requests.post(
                    f"{api_base.rstrip('/')}/ask",
                    json={"question": query, "top_k": 4},
                    timeout=15,
                )
                r.raise_for_status()
                return r.json()
            else:
                body: Dict[str, Any] = {"thread_id": st.session_state.session_id}
                if approve is not None:
                    body["approve"] = approve
                    body["approval_note"] = approval_note
                else:
                    body["query"] = query
                r = requests.post(f"{api_base.rstrip('/')}/agent", json=body, timeout=20)
                r.raise_for_status()
                return r.json()
        except Exception as exc:
            st.warning(f"FastAPI server unreachable at `{api_base}` ({exc}); using built-in local fallback.")

    # Direct in-process fallback so Streamlit works standalone even before uvicorn is launched
    from app.graph import invoke_langgraph_agent
    from app.tools import get_rag

    if mode == "ask":
        return get_rag().ask(question=query, top_k=4)
    return invoke_langgraph_agent(
        thread_id=st.session_state.session_id,
        query=query if approve is None else None,
        approve=approve,
        approval_note=approval_note,
    )


def render_old_vs_current_warning(warning: Dict[str, Any]) -> None:
    if not warning or not warning.get("triggered"):
        return
    old_c = warning["old_citation"]
    new_c = warning["new_citation"]
    st.markdown(
        f"""
        <div class="old-vs-current-banner">
            <strong>⚠️ Old vs Current Rule Warning:</strong> {warning['banner']}<br/>
            <span>• <strong>Older FAQ [{old_c['rule_year']}]:</strong> {old_c['source']} (Page {old_c['page']}, <code>{old_c['chunk_id']}</code>)</span><br/>
            <span>• <strong>Current Rule [{new_c['rule_year']}]:</strong> {new_c['source']} (Page {new_c['page']}, <code>{new_c['chunk_id']}</code>)</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_citations(citations: List[Dict[str, Any]]) -> None:
    if not citations:
        return
    with st.expander(f"📚 Sources & Citations ({len(citations)})", expanded=True):
        for c in citations:
            yr = c.get("rule_year", "")
            yr_badge = f" • {yr}" if yr else ""
            url = c.get("source_url", "")
            link_part = f" — [Open Source]({url})" if url else ""
            st.markdown(
                f"**{c.get('ref', '[*]')} {c.get('title', 'GST Record')}** (`{c.get('chunk_id', '')}`{yr_badge})  \n"
                f"Document: *{c.get('source', '')}* | Page {c.get('page', 1)}{link_part}"
            )


# Sidebar Controls
with st.sidebar:
    st.title("🧾 GSTSaral Controls")
    st.caption("Checkpoint 2 • Grounded RAG + LangGraph Agent")

    mode_label = st.radio(
        "Execution Endpoint",
        options=["/ask (Grounded RAG + Old-vs-Current Detector)", "/agent (LangGraph Memory + Approval Gate)"],
        index=0,
    )
    selected_mode = "ask" if mode_label.startswith("/ask") else "agent"

    api_url = st.text_input("FastAPI Base URL", value=DEFAULT_API_URL)
    use_direct_fallback = st.checkbox("Use direct in-process Python fallback if API is offline", value=True)

    st.divider()
    st.markdown("**Quick Demo Prompts (Click to Run)**")
    demo_prompts = [
        ("🟡 Old vs Current FAQ (2017/18 Soap FAQ)", "What was the 2017 GST FAQ rate on toilet soap bars?"),
        ("🟡 Old vs Current FAQ (2017/18 UHT Milk)", "What did the 2017/18 CBIC FAQ say about UHT milk GST?"),
        ("✅ Current 56th Council Rule (Paneer)", "Is pre-packaged paneer at 0% Nil GST now?"),
        ("🚫 Out-of-Scope Abstention (Q6)", "What is the exact GST late fee penalty for filing GSTR-9C three months late in FY 2025-26?"),
        ("🧮 Agent Invoice + Approval (/agent)", "Calculate GST invoice for butter worth Rs 1050 inclusive of 5% GST within Maharashtra"),
    ]
    clicked_prompt = None
    for btn_label, prompt_text in demo_prompts:
        if st.button(btn_label, use_container_width=True):
            clicked_prompt = prompt_text
            if "/agent" in btn_label:
                selected_mode = "agent"

    st.divider()
    st.markdown(f"**Session ID:** `{st.session_state.session_id}`")
    if FEEDBACK_FILE.exists():
        fb_lines = [line for line in FEEDBACK_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]
        ups = sum(1 for line in fb_lines if '"rating": "up"' in line)
        downs = sum(1 for line in fb_lines if '"rating": "down"' in line)
        st.metric("Saved User Feedback", f"👍 {ups}  |  👎 {downs}")

    if st.button("Clear Chat & Reset Session", use_container_width=True):
        st.session_state.session_id = f"cp2-{uuid.uuid4().hex[:8]}"
        st.session_state.messages = []
        st.session_state.feedback_votes = {}
        st.session_state.pending_approval = None
        st.rerun()

# Header
st.title("🧾 GSTSaral — Indian GST Assistant & Invoice Agent")
st.caption(
    "Grounded answers with inline citations, automatic **Old (2017/18) vs Current** rule warnings, "
    "human-in-the-loop invoice approval (`/agent`), and persistent thumbs up/down feedback."
)

# Render chat history
for idx, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        if msg["role"] == "assistant":
            if msg.get("old_vs_current_warning"):
                render_old_vs_current_warning(msg["old_vs_current_warning"])
            st.markdown(msg["content"])
            if msg.get("invoice_calculation"):
                st.json(msg["invoice_calculation"])
            if msg.get("citations"):
                render_citations(msg["citations"])

            # Thumbs up / thumbs down feedback row
            col1, col2, col3 = st.columns([1, 1, 8])
            current_vote = st.session_state.feedback_votes.get(idx)
            with col1:
                if st.button("👍", key=f"up_{idx}", help="Helpful answer"):
                    submit_feedback(api_url, use_direct_fallback, idx, msg, "up")
                    st.rerun()
            with col2:
                if st.button("👎", key=f"down_{idx}", help="Needs improvement"):
                    submit_feedback(api_url, use_direct_fallback, idx, msg, "down")
                    st.rerun()
            with col3:
                if current_vote == "up":
                    st.caption("✅ Saved feedback: 👍 Helpful")
                elif current_vote == "down":
                    st.caption("⚠️ Saved feedback: 👎 Flagged for review")
        else:
            st.markdown(msg["content"])

# Human-in-the-Loop Approval Gate Banner when /agent pauses at interrupt()
if st.session_state.pending_approval is not None:
    req = st.session_state.pending_approval
    st.warning("⏸️ **LangGraph Human Approval Gate:** Review proposed `gst_invoice_calculator` parameters before execution.")
    st.json(req.get("proposed_args", {}))
    note_input = st.text_input("Reviewer Note (optional)", value="Approved by GST reviewer", key="approval_note_input")
    acol1, acol2, _ = st.columns([1.5, 1.5, 7])
    with acol1:
        if st.button("✅ Approve & Calculate", type="primary", use_container_width=True):
            res = call_backend(
                api_url,
                use_direct_fallback,
                mode="agent",
                approve=True,
                approval_note=note_input,
            )
            st.session_state.pending_approval = None
            rag_sub = res.get("rag_result") or {}
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "mode": "agent",
                    "question": "(Approved tool execution)",
                    "content": res.get("final_answer", ""),
                    "citations": rag_sub.get("citations", []),
                    "old_vs_current_warning": rag_sub.get("old_vs_current_warning"),
                    "invoice_calculation": res.get("invoice_calculation"),
                }
            )
            st.rerun()
    with acol2:
        if st.button("❌ Reject", use_container_width=True):
            res = call_backend(
                api_url,
                use_direct_fallback,
                mode="agent",
                approve=False,
                approval_note=note_input or "Rejected in UI",
            )
            st.session_state.pending_approval = None
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "mode": "agent",
                    "question": "(Rejected tool execution)",
                    "content": res.get("final_answer", "Calculation rejected."),
                    "citations": [],
                    "old_vs_current_warning": None,
                    "invoice_calculation": None,
                }
            )
            st.rerun()

# Chat Input
user_input = st.chat_input("Ask a GST rate question or request a Maharashtra GST invoice calculation...")
active_query = clicked_prompt or user_input

if active_query:
    st.session_state.messages.append({"role": "user", "content": active_query})
    response = call_backend(api_url, use_direct_fallback, mode=selected_mode, query=active_query)

    if selected_mode == "ask":
        st.session_state.messages.append(
            {
                "role": "assistant",
                "mode": "ask",
                "question": active_query,
                "content": response.get("answer", ""),
                "citations": response.get("citations", []),
                "old_vs_current_warning": response.get("old_vs_current_warning"),
                "invoice_calculation": None,
            }
        )
    else:
        if response.get("status") == "awaiting_approval":
            st.session_state.pending_approval = response.get("approval_request")
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "mode": "agent",
                    "question": active_query,
                    "content": "⏸️ Paused at LangGraph approval step. Please approve or reject the invoice calculation above.",
                    "citations": (response.get("rag_result") or {}).get("citations", []),
                    "old_vs_current_warning": (response.get("rag_result") or {}).get("old_vs_current_warning"),
                    "invoice_calculation": None,
                }
            )
        else:
            rag_sub = response.get("rag_result") or {}
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "mode": "agent",
                    "question": active_query,
                    "content": response.get("final_answer", ""),
                    "citations": rag_sub.get("citations", []),
                    "old_vs_current_warning": rag_sub.get("old_vs_current_warning"),
                    "invoice_calculation": response.get("invoice_calculation"),
                }
            )
    st.rerun()
