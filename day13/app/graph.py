"""LangGraph rebuild of the GSTSaral agent with MemorySaver + one human approval interrupt step."""

import operator
from typing import Annotated, Any, Dict, List, Optional, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from app.agent_loop import HandWrittenGSTAgent
from app.tools import gst_invoice_calculator, rag_search_tool


class GSTAgentState(TypedDict, total=False):
    thread_id: str
    messages: Annotated[List[Dict[str, str]], operator.add]
    current_query: str
    needs_rag: bool
    needs_calc: bool
    rag_result: Optional[Dict[str, Any]]
    proposed_calc_args: Optional[Dict[str, Any]]
    approval_status: str  # "pending" | "approved" | "rejected" | "not_required"
    approval_note: str
    invoice_calculation: Optional[Dict[str, Any]]
    final_answer: str


_HELPER = HandWrittenGSTAgent()


def planner_node(state: GSTAgentState) -> Dict[str, Any]:
    """Inspect user message + conversation memory and plan tool calls."""
    query = state["current_query"]
    need_rag = _HELPER._needs_rag(query)
    need_calc = _HELPER._needs_calculator(query)
    return {
        "needs_rag": need_rag,
        "needs_calc": need_calc,
        "rag_result": None,
        "proposed_calc_args": None,
        "invoice_calculation": None,
        "approval_status": "pending" if need_calc else "not_required",
        "approval_note": "",
    }


def route_after_planner(state: GSTAgentState) -> str:
    if state.get("needs_rag"):
        return "rag_node"
    if state.get("needs_calc"):
        return "prepare_calc_node"
    return "respond_node"


def rag_node(state: GSTAgentState) -> Dict[str, Any]:
    """Retrieve grounded GST chunks and citations."""
    res = rag_search_tool(question=state["current_query"], top_k=3)
    return {"rag_result": res}


def route_after_rag(state: GSTAgentState) -> str:
    if state.get("needs_calc"):
        return "prepare_calc_node"
    return "respond_node"


def prepare_calc_node(state: GSTAgentState) -> Dict[str, Any]:
    """Extract invoice calculator parameters (using RAG-discovered GST rate and conversation memory)."""
    discovered_rate: Optional[float] = None
    rag_res = state.get("rag_result")
    if rag_res and not rag_res.get("abstained"):
        discovered_rate = _HELPER._extract_rate_from_rag_text(rag_res.get("answer", ""))

    combined_context = state["current_query"]
    for msg in state.get("messages", [])[-4:]:
        if msg.get("role") == "user" and msg.get("content") != state["current_query"]:
            if "outside maharashtra" in msg["content"].lower() and "maharashtra" not in combined_context.lower():
                combined_context += " outside maharashtra"

    args = _HELPER._extract_invoice_params(combined_context, discovered_rate=discovered_rate)
    return {"proposed_calc_args": args}


def approval_gate_node(state: GSTAgentState) -> Dict[str, Any]:
    """
    Human-in-the-Loop approval gate before generating an official GST invoice calculation.
    Pauses execution via LangGraph `interrupt(...)` and resumes when POST /agent receives `approve=true/false`.
    """
    decision = interrupt(
        {
            "type": "invoice_calculation_approval",
            "message": "Approval required before executing gst_invoice_calculator.",
            "proposed_tool": "gst_invoice_calculator",
            "proposed_args": state.get("proposed_calc_args"),
        }
    )

    approved = bool(decision.get("approved", True)) if isinstance(decision, dict) else bool(decision)
    note = decision.get("note", "") if isinstance(decision, dict) else ""
    overrides = decision.get("overrides") if isinstance(decision, dict) else None

    updated_args = dict(state.get("proposed_calc_args") or {})
    if isinstance(overrides, dict):
        for k in ("price", "gst_rate", "within_maharashtra", "price_inclusive_of_gst"):
            if k in overrides and overrides[k] is not None:
                updated_args[k] = overrides[k]

    return {
        "approval_status": "approved" if approved else "rejected",
        "approval_note": note,
        "proposed_calc_args": updated_args,
    }


def route_after_approval(state: GSTAgentState) -> str:
    if state.get("approval_status") == "approved":
        return "calculator_node"
    return "respond_node"


def calculator_node(state: GSTAgentState) -> Dict[str, Any]:
    """Execute gst_invoice_calculator after approval."""
    args = state["proposed_calc_args"] or {}
    calc_out = gst_invoice_calculator(**args)
    return {"invoice_calculation": calc_out}


def respond_node(state: GSTAgentState) -> Dict[str, Any]:
    """Synthesize final answer and append assistant turn into persistent LangGraph memory."""
    parts: List[str] = []
    rag_res = state.get("rag_result")
    calc_out = state.get("invoice_calculation")

    if rag_res is not None:
        parts.append(rag_res["answer"])

    if state.get("approval_status") == "rejected":
        reason = f" ({state['approval_note']})" if state.get("approval_note") else ""
        parts.append(f"Invoice calculation was rejected at the approval step{reason}.")
    elif calc_out is not None:
        if calc_out["within_maharashtra"]:
            tax_split = (
                f"CGST ({calc_out['cgst_rate_percent']}%): Rs. {calc_out['cgst_amount']:.2f} + "
                f"SGST ({calc_out['sgst_rate_percent']}%): Rs. {calc_out['sgst_amount']:.2f}"
            )
        else:
            tax_split = f"IGST ({calc_out['igst_rate_percent']}%): Rs. {calc_out['igst_amount']:.2f}"
        mode_label = "GST-Inclusive Back-Calculation" if calc_out["price_inclusive_of_gst"] else "GST-Exclusive"
        parts.append(
            f"Approved Invoice Breakdown ({calc_out['supply_type']}, {mode_label}): "
            f"Taxable Value = Rs. {calc_out['taxable_value']:.2f}, "
            f"{tax_split}, Total Invoice = Rs. {calc_out['total_invoice_amount']:.2f}."
        )

    final_text = " ".join(parts).strip()
    return {
        "final_answer": final_text,
        "messages": [{"role": "assistant", "content": final_text}],
    }


def build_gstsaral_graph():
    builder = StateGraph(GSTAgentState)

    builder.add_node("planner_node", planner_node)
    builder.add_node("rag_node", rag_node)
    builder.add_node("prepare_calc_node", prepare_calc_node)
    builder.add_node("approval_gate_node", approval_gate_node)
    builder.add_node("calculator_node", calculator_node)
    builder.add_node("respond_node", respond_node)

    builder.add_edge(START, "planner_node")
    builder.add_conditional_edges(
        "planner_node",
        route_after_planner,
        {
            "rag_node": "rag_node",
            "prepare_calc_node": "prepare_calc_node",
            "respond_node": "respond_node",
        },
    )
    builder.add_conditional_edges(
        "rag_node",
        route_after_rag,
        {
            "prepare_calc_node": "prepare_calc_node",
            "respond_node": "respond_node",
        },
    )
    builder.add_edge("prepare_calc_node", "approval_gate_node")
    builder.add_conditional_edges(
        "approval_gate_node",
        route_after_approval,
        {
            "calculator_node": "calculator_node",
            "respond_node": "respond_node",
        },
    )
    builder.add_edge("calculator_node", "respond_node")
    builder.add_edge("respond_node", END)

    memory = MemorySaver()
    return builder.compile(checkpointer=memory)


LANGGRAPH_AGENT = build_gstsaral_graph()


def invoke_langgraph_agent(
    thread_id: str,
    query: Optional[str] = None,
    approve: Optional[bool] = None,
    approval_note: str = "",
    overrides: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Start a new turn or resume an interrupted approval checkpoint for `thread_id`.
    - When `approve` is None: runs `query` and either completes or pauses at `approval_gate_node`.
    - When `approve` is True/False: resumes the paused checkpoint with the user's approval decision.
    """
    config = {"configurable": {"thread_id": thread_id}}

    if approve is not None:
        result = LANGGRAPH_AGENT.invoke(
            Command(
                resume={
                    "approved": approve,
                    "note": approval_note,
                    "overrides": overrides or {},
                }
            ),
            config=config,
        )
    else:
        if not query or not query.strip():
            raise ValueError("`query` is required when `approve` is not provided.")
        result = LANGGRAPH_AGENT.invoke(
            {
                "thread_id": thread_id,
                "current_query": query.strip(),
                "messages": [{"role": "user", "content": query.strip()}],
            },
            config=config,
        )

    snapshot = LANGGRAPH_AGENT.get_state(config)
    pending_interrupts = []
    for task in snapshot.tasks:
        for intr in getattr(task, "interrupts", ()):
            pending_interrupts.append(intr.value)

    if pending_interrupts:
        return {
            "status": "awaiting_approval",
            "thread_id": thread_id,
            "approval_request": pending_interrupts[0],
            "rag_result": result.get("rag_result"),
            "invoice_calculation": None,
            "final_answer": None,
            "memory_turn_count": len(snapshot.values.get("messages", [])),
        }

    return {
        "status": "completed",
        "thread_id": thread_id,
        "approval_status": result.get("approval_status", "not_required"),
        "rag_result": result.get("rag_result"),
        "invoice_calculation": result.get("invoice_calculation"),
        "final_answer": result.get("final_answer", ""),
        "memory_turn_count": len(snapshot.values.get("messages", [])),
    }
