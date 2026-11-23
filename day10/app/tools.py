"""Agent tools for GSTSaral: GST Invoice Calculator & Grounded RAG Search."""

from typing import Any, Dict, Optional

from app.rag import GSTSaralRAG

_SHARED_RAG: Optional[GSTSaralRAG] = None


def get_rag() -> GSTSaralRAG:
    global _SHARED_RAG
    if _SHARED_RAG is None:
        _SHARED_RAG = GSTSaralRAG(chunk_size=350, overlap=50, top_k=3)
    return _SHARED_RAG


def gst_invoice_calculator(
    price: float,
    gst_rate: float,
    within_maharashtra: bool = True,
    price_inclusive_of_gst: bool = False,
) -> Dict[str, Any]:
    """
    Calculate Indian GST invoice breakdown (taxable value, CGST+SGST or IGST split, and total).
    Supports both GST-exclusive base price and 'price inclusive of GST' back-calculation.
    """
    if price < 0:
        raise ValueError("price must be non-negative")
    if gst_rate < 0:
        raise ValueError("gst_rate must be non-negative")

    rate_decimal = gst_rate / 100.0

    if price_inclusive_of_gst:
        taxable_value = round(price / (1.0 + rate_decimal), 2) if rate_decimal > 0 else round(price, 2)
        total_gst = round(price - taxable_value, 2)
        total_amount = round(price, 2)
    else:
        taxable_value = round(price, 2)
        total_gst = round(taxable_value * rate_decimal, 2)
        total_amount = round(taxable_value + total_gst, 2)

    if within_maharashtra:
        half_rate = round(gst_rate / 2.0, 2)
        cgst = round(total_gst / 2.0, 2)
        sgst = round(total_gst - cgst, 2)
        igst = 0.0
        supply_type = "Intra-State (Within Maharashtra)"
    else:
        half_rate = 0.0
        cgst = 0.0
        sgst = 0.0
        igst = total_gst
        supply_type = "Inter-State (Outside Maharashtra)"

    return {
        "supply_type": supply_type,
        "within_maharashtra": within_maharashtra,
        "price_inclusive_of_gst": price_inclusive_of_gst,
        "input_price": round(price, 2),
        "gst_rate_percent": round(gst_rate, 2),
        "taxable_value": taxable_value,
        "cgst_rate_percent": half_rate,
        "cgst_amount": cgst,
        "sgst_rate_percent": half_rate,
        "sgst_amount": sgst,
        "igst_rate_percent": round(gst_rate, 2) if not within_maharashtra else 0.0,
        "igst_amount": igst,
        "total_gst_amount": total_gst,
        "total_invoice_amount": total_amount,
    }


def rag_search_tool(question: str, top_k: int = 3) -> Dict[str, Any]:
    """Query the grounded GSTSaral RAG index and return answer + citations."""
    return get_rag().ask(question=question, top_k=top_k)


TOOL_REGISTRY = {
    "gst_invoice_calculator": gst_invoice_calculator,
    "rag_search": rag_search_tool,
}
