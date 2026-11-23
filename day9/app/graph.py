import re
from typing import Any, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt


class AgentState(TypedDict, total=False):
    current_query: str
    overrides: dict[str, Any]
    intent: str
    rate_percent: float
    amount: float
    is_interstate: bool
    inclusive: bool
    item_name: str
    rule_note: str
    approval_payload: dict[str, Any]
    approval_decision: str
    calculation_result: dict[str, Any]
    final_answer: str


GST_RATE_TABLE: list[tuple[tuple[str, ...], str, float, str]] = [
    (("soap", "bathing bar"), "Toilet soap bars", 5.0, "5% GST (reduced from 18% per 56th GST Council)."),
    (("toothpaste", "toothbrush"), "Toothpaste & Toothbrushes", 5.0, "5% GST (reduced from 18% per 56th GST Council)."),
    (("hair oil", "shampoo"), "Hair oil & Shampoo", 5.0, "5% GST (reduced from 18% per 56th GST Council)."),
    (("paneer", "uht milk", "milk"), "UHT Milk & Packaged Paneer", 0.0, "Nil (0%) GST per 56th GST Council."),
    (("butter", "ghee", "cheese"), "Butter, Ghee & Cheese", 5.0, "5% GST (reduced from 12% per 56th GST Council)."),
    (("namkeen", "bhujia"), "Packaged Namkeen & Bhujia", 5.0, "5% GST (reduced from 12% per 56th GST Council)."),
    (("bicycle",), "Bicycles & Parts", 5.0, "5% GST (reduced from 12% per 56th GST Council)."),
    (("notebook", "exercise book", "pencil"), "Notebooks & Pencils", 0.0, "Nil (0%) GST per 56th GST Council."),
    (("insurance",), "Individual Health & Life Insurance", 0.0, "Nil (0%) GST per 56th GST Council."),
    (("car", "two-wheeler", "motorcycle", "bike"), "Small Cars & Two-Wheelers (<=350cc)", 18.0, "18% GST (reduced from 28% per 56th GST Council)."),
]


def _extract_invoice_params(query: str, overrides: dict[str, Any]) -> dict[str, Any]:
    q_lower = query.lower()

    # 1. Detect item & latest GST rate
    item_name = "Standard Taxable Goods/Services"
    rate_percent = 18.0
    rule_note = "Default 18% standard GST slab applied."

    for keywords, label, rate, note in GST_RATE_TABLE:
        if any(kw in q_lower for kw in keywords):
            item_name = label
            rate_percent = rate
            rule_note = note
            break

    # Explicit rate in query (e.g., "at 12%" or "5% gst") overrides keyword guess
    rate_match = re.search(r"(\d+(?:\.\d+)?)\s*%", q_lower)
    if rate_match:
        rate_percent = float(rate_match.group(1))
        rule_note = f"Explicit {rate_percent}% GST rate specified in query."

    # 2. Extract rupee amount (ignore numbers attached to '%')
    cleaned_for_amount = re.sub(r"\d+(?:\.\d+)?\s*%", "", q_lower)
    cleaned_for_amount = cleaned_for_amount.replace(",", "")
    amount_match = re.search(r"(?:rs\.?|inr|₹)?\s*(\d+(?:\.\d+)?)", cleaned_for_amount)
    amount = float(amount_match.group(1)) if amount_match else 1000.0

    # 3. Detect inter-state vs intra-state (Maharashtra default)
    interstate_markers = ("inter-state", "interstate", "igst", "outside maharashtra", "delhi", "gujarat", "karnataka", "bengaluru", "bangalore")
    is_interstate = any(m in q_lower for m in interstate_markers)

    # 4. Detect GST-inclusive vs exclusive
    inclusive = any(w in q_lower for w in ("inclusive", "including gst", "with gst"))

    # Apply any user/reviewer overrides
    if "rate_percent" in overrides and overrides["rate_percent"] is not None:
        rate_percent = float(overrides["rate_percent"])
    if "amount" in overrides and overrides["amount"] is not None:
        amount = float(overrides["amount"])
    if "is_interstate" in overrides and overrides["is_interstate"] is not None:
        is_interstate = bool(overrides["is_interstate"])
    if "inclusive" in overrides and overrides["inclusive"] is not None:
        inclusive = bool(overrides["inclusive"])

    return {
        "item_name": item_name,
        "rate_percent": rate_percent,
        "amount": amount,
        "is_interstate": is_interstate,
        "inclusive": inclusive,
        "rule_note": rule_note,
    }


def _calculate_gst_invoice(
    amount: float,
    rate_percent: float,
    is_interstate: bool = False,
    inclusive: bool = False,
) -> dict[str, Any]:
    rate = rate_percent / 100.0
    if inclusive:
        base_amount = round(amount / (1.0 + rate), 2) if rate > 0 else round(amount, 2)
        total_tax = round(amount - base_amount, 2)
        total_amount = round(amount, 2)
    else:
        base_amount = round(amount, 2)
        total_tax = round(base_amount * rate, 2)
        total_amount = round(base_amount + total_tax, 2)

    if is_interstate:
        cgst = 0.0
        sgst = 0.0
        igst = total_tax
        supply_type = "Inter-State (IGST)"
    else:
        cgst = round(total_tax / 2.0, 2)
        sgst = round(total_tax - cgst, 2)
        igst = 0.0
        supply_type = "Intra-State Maharashtra (CGST + SGST)"

    return {
        "supply_type": supply_type,
        "inclusive_pricing": inclusive,
        "base_amount": base_amount,
        "gst_rate_percent": rate_percent,
        "cgst": cgst,
        "sgst": sgst,
        "igst": igst,
        "total_gst": total_tax,
        "grand_total": total_amount,
    }


def planner_node(state: AgentState) -> dict[str, Any]:
    query = (
        state.get("current_query")
        or state.get("query")
        or state.get("question")
        or ""
    ).strip()

    if not query:
        return {
            "intent": "invalid",
            "final_answer": "No active paused approval found for this thread_id. Send a request with a 'query' first.",
        }

    overrides = state.get("overrides") or {}
    q_lower = query.lower()
    calc_keywords = ("calculate", "invoice", "bill", "cgst", "sgst", "igst", "tax on", "worth", "price", "rs", "₹")
    is_calc = any(k in q_lower for k in calc_keywords) and bool(re.search(r"\d", q_lower))

    if is_calc:
        params = _extract_invoice_params(query, overrides)
        return {
            "intent": "invoice_calc",
            **params,
        }

    # Informational GST lookup
    params = _extract_invoice_params(query, overrides)
    return {
        "intent": "qa_lookup",
        **params,
        "final_answer": f"{params['item_name']}: {params['rule_note']}",
    }


def route_after_planner(state: AgentState) -> str:
    if state.get("intent") == "invoice_calc":
        return "approval_gate"
    return END


def approval_gate_node(state: AgentState) -> dict[str, Any]:
    proposal = {
        "action": "gst_invoice_calculator",
        "item_name": state.get("item_name", "Goods/Services"),
        "base_or_input_amount": state.get("amount", 0.0),
        "gst_rate_percent": state.get("rate_percent", 18.0),
        "is_interstate": state.get("is_interstate", False),
        "inclusive": state.get("inclusive", False),
        "rule_note": state.get("rule_note", ""),
        "message": "Approve GST invoice calculation with these parameters? Reply with decision='approve' or 'reject'.",
    }

    human_reply = interrupt(proposal)

    if isinstance(human_reply, dict):
        decision = str(human_reply.get("decision", "approve")).strip().lower()
        overrides = human_reply.get("overrides") or {}
    else:
        decision = str(human_reply).strip().lower()
        overrides = {}

    updated: dict[str, Any] = {
        "approval_payload": proposal,
        "approval_decision": decision,
    }
    if "rate_percent" in overrides and overrides["rate_percent"] is not None:
        updated["rate_percent"] = float(overrides["rate_percent"])
    if "amount" in overrides and overrides["amount"] is not None:
        updated["amount"] = float(overrides["amount"])
    if "is_interstate" in overrides and overrides["is_interstate"] is not None:
        updated["is_interstate"] = bool(overrides["is_interstate"])
    if "inclusive" in overrides and overrides["inclusive"] is not None:
        updated["inclusive"] = bool(overrides["inclusive"])

    return updated


def execute_tool_node(state: AgentState) -> dict[str, Any]:
    decision = state.get("approval_decision", "reject")
    if decision not in {"approve", "approved", "yes", "y"}:
        return {
            "final_answer": f"Invoice calculation cancelled (decision='{decision}').",
        }

    calc = _calculate_gst_invoice(
        amount=float(state.get("amount", 0.0)),
        rate_percent=float(state.get("rate_percent", 18.0)),
        is_interstate=bool(state.get("is_interstate", False)),
        inclusive=bool(state.get("inclusive", False)),
    )
    summary = (
        f"GST Invoice Breakdown for {state.get('item_name')} ({calc['supply_type']}):\n"
        f"- Taxable Base: Rs. {calc['base_amount']:,.2f}\n"
        f"- GST Rate: {calc['gst_rate_percent']}%\n"
        f"- CGST: Rs. {calc['cgst']:,.2f} | SGST: Rs. {calc['sgst']:,.2f} | IGST: Rs. {calc['igst']:,.2f}\n"
        f"- Total GST: Rs. {calc['total_gst']:,.2f}\n"
        f"- Grand Total: Rs. {calc['grand_total']:,.2f}\n"
        f"- Rule Applied: {state.get('rule_note', '')}"
    )
    return {
        "calculation_result": calc,
        "final_answer": summary,
    }


def _build_graph():
    builder = StateGraph(AgentState)
    builder.add_node("planner_node", planner_node)
    builder.add_node("approval_gate", approval_gate_node)
    builder.add_node("execute_tool", execute_tool_node)

    builder.add_edge(START, "planner_node")
    builder.add_conditional_edges(
        "planner_node",
        route_after_planner,
        {
            "approval_gate": "approval_gate",
            END: END,
        },
    )
    builder.add_edge("approval_gate", "execute_tool")
    builder.add_edge("execute_tool", END)

    return builder.compile(checkpointer=MemorySaver())


LANGGRAPH_AGENT = _build_graph()


def invoke_langgraph_agent(
    thread_id: str,
    query: str | None = None,
    decision: str | None = None,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = {"configurable": {"thread_id": thread_id}}
    snapshot = LANGGRAPH_AGENT.get_state(config)
    has_pending_interrupt = bool(snapshot and snapshot.next)

    # Ignore placeholder Swagger string "string" when no interrupt is active
    clean_decision = (
        decision.strip().lower()
        if isinstance(decision, str) and decision.strip() and decision.strip().lower() != "string"
        else None
    )

    if clean_decision is not None and has_pending_interrupt:
        result = LANGGRAPH_AGENT.invoke(
            Command(
                resume={
                    "decision": clean_decision,
                    "overrides": overrides or {},
                }
            ),
            config=config,
        )
    else:
        if not query or not str(query).strip() or str(query).strip().lower() == "string":
            return {
                "thread_id": thread_id,
                "status": "error",
                "answer": (
                    "No pending approval exists for this thread_id. "
                    "Provide a valid 'query' first (with 'decision': null)."
                ),
            }
        result = LANGGRAPH_AGENT.invoke(
            {
                "current_query": str(query).strip(),
                "overrides": overrides or {},
            },
            config=config,
        )

    post_snapshot = LANGGRAPH_AGENT.get_state(config)
    if post_snapshot and post_snapshot.next:
        interrupt_info = None
        if post_snapshot.tasks and post_snapshot.tasks[0].interrupts:
            interrupt_info = post_snapshot.tasks[0].interrupts[0].value
        return {
            "thread_id": thread_id,
            "status": "awaiting_approval",
            "interrupt": interrupt_info,
            "answer": "Approval required before running GST invoice calculation. Re-submit with the same thread_id and decision='approve'.",
        }

    return {
        "thread_id": thread_id,
        "status": "completed",
        "answer": result.get("final_answer", ""),
        "calculation": result.get("calculation_result"),
    }