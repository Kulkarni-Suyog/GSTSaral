"""Hand-written ReAct agent loop capable of calling rag_search and gst_invoice_calculator."""

import json
import os
import re
from typing import Any, Dict, List, Optional

from app.tools import TOOL_REGISTRY, gst_invoice_calculator, rag_search_tool


class HandWrittenGSTAgent:
    """
    Explicit Thought -> Action -> Observation loop (no framework magic) that:
    1. Routes GST rate/rule queries to `rag_search`
    2. Routes invoice tax/split/inclusive-price queries to `gst_invoice_calculator`
    3. Chains `rag_search` -> `gst_invoice_calculator` when the user gives an item + price without a GST rate!
    """

    def __init__(self, max_steps: int = 4) -> None:
        self.max_steps = max_steps

    def _extract_invoice_params(self, query: str, discovered_rate: Optional[float] = None) -> Dict[str, Any]:
        q_lower = query.lower()

        inclusive = any(
            phrase in q_lower
            for phrase in ("inclusive", "including gst", "with gst", "mrp", "back-calc", "back calc")
        )

        outside_mh = any(
            phrase in q_lower
            for phrase in ("outside maharashtra", "inter-state", "interstate", "inter state", "to delhi", "to gujarat", "to karnataka")
        )
        within_mh = not outside_mh

        rate_match = re.search(r"(\d+(?:\.\d+)?)\s*%", q_lower)
        if rate_match:
            gst_rate = float(rate_match.group(1))
        elif discovered_rate is not None:
            gst_rate = discovered_rate
        elif "nil" in q_lower or "0%" in q_lower:
            gst_rate = 0.0
        else:
            gst_rate = 5.0

        price = 1000.0
        cleaned_for_price = re.sub(r"\d+(?:\.\d+)?\s*%", " ", q_lower)
        currency_match = re.search(
            r"(?:rs\.?|inr|₹|price\s*(?:of|is|=)?|for|amount\s*(?:of|is|=)?|worth)\s*(\d+(?:,\d{3})*(?:\.\d+)?)",
            cleaned_for_price,
        )
        if currency_match:
            price = float(currency_match.group(1).replace(",", ""))
        else:
            nums = [float(n.replace(",", "")) for n in re.findall(r"\b\d+(?:,\d{3})*(?:\.\d+)?\b", cleaned_for_price)]
            if nums:
                price = max(nums)

        return {
            "price": price,
            "gst_rate": gst_rate,
            "within_maharashtra": within_mh,
            "price_inclusive_of_gst": inclusive,
        }

    def _extract_rate_from_rag_text(self, text: str) -> Optional[float]:
        rev = re.search(r"revised gst rate:\s*(?:nil\s*\()?(\d+(?:\.\d+)?)\s*%", text.lower())
        if rev:
            return float(rev.group(1))
        if "revised gst rate: nil" in text.lower():
            return 0.0
        any_rate = re.search(r"(\d+(?:\.\d+)?)\s*%", text.lower())
        return float(any_rate.group(1)) if any_rate else None

    def _needs_calculator(self, query: str) -> bool:
        q = query.lower()
        calc_terms = (
            "invoice", "calculate", "calculator", "cgst", "sgst", "igst",
            "taxable value", "inclusive", "split", "maharashtra", "bill", "total price",
        )
        has_calc_word = any(w in q for w in calc_terms)
        has_money = bool(re.search(r"(?:rs\.?|inr|₹|\bprice\b|\bamount\b|\bworth\b)", q))
        return has_calc_word or has_money

    def _needs_rag(self, query: str) -> bool:
        q = query.lower()
        has_explicit_rate = bool(re.search(r"\d+(?:\.\d+)?\s*%", q))
        if not self._needs_calculator(query):
            return True
        return not has_explicit_rate

    def _llm_decide_next_action(
        self, query: str, trace: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Optional Gemini/Groq planner hook; falls back to deterministic policy when offline."""
        provider = os.getenv("LLM_PROVIDER", "").strip().lower()
        if provider not in {"gemini", "groq"}:
            return None

        sys_prompt = (
            "You are a GSTSaral tool-using agent. Available tools:\n"
            "1) rag_search: args={\"question\": str}\n"
            "2) gst_invoice_calculator: args={\"price\": float, \"gst_rate\": float, "
            "\"within_maharashtra\": bool, \"price_inclusive_of_gst\": bool}\n"
            "Respond strictly in JSON: {\"thought\": str, \"action\": \"rag_search\"|\"gst_invoice_calculator\"|\"finish\", "
            "\"action_input\": dict, \"final_answer\": str}\n"
            f"User query: {query}\nPrevious steps: {json.dumps(trace)}"
        )

        try:
            if provider == "gemini" and os.getenv("GEMINI_API_KEY", "").strip():
                from google import genai

                client = genai.Client(api_key=os.getenv("GEMINI_API_KEY").strip())
                resp = client.models.generate_content(
                    model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
                    contents=sys_prompt,
                )
                raw = (resp.text or "").strip().strip("`").removeprefix("json").strip()
                return json.loads(raw)

            if provider == "groq" and os.getenv("GROQ_API_KEY", "").strip():
                from groq import Groq

                client = Groq(api_key=os.getenv("GROQ_API_KEY").strip())
                resp = client.chat.completions.create(
                    model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
                    temperature=0.0,
                    messages=[{"role": "user", "content": sys_prompt}],
                )
                raw = (resp.choices[0].message.content or "").strip().strip("`").removeprefix("json").strip()
                return json.loads(raw)
        except Exception:
            return None
        return None

    def run(self, query: str) -> Dict[str, Any]:
        """Execute the multi-step Thought -> Action -> Observation loop."""
        trace: List[Dict[str, Any]] = []
        rag_obs: Optional[Dict[str, Any]] = None
        calc_obs: Optional[Dict[str, Any]] = None
        discovered_rate: Optional[float] = None

        need_rag = self._needs_rag(query)
        need_calc = self._needs_calculator(query)

        for step in range(1, self.max_steps + 1):
            llm_step = self._llm_decide_next_action(query, trace)
            if llm_step and llm_step.get("action") in {"rag_search", "gst_invoice_calculator", "finish"}:
                action = llm_step["action"]
                thought = llm_step.get("thought", "")
                action_input = llm_step.get("action_input", {})
                if action == "finish":
                    return {
                        "query": query,
                        "final_answer": llm_step.get("final_answer", ""),
                        "steps": trace,
                        "rag_result": rag_obs,
                        "invoice_calculation": calc_obs,
                    }
                tool_fn = TOOL_REGISTRY[action]
                observation = tool_fn(**action_input)
                if action == "rag_search":
                    rag_obs = observation
                elif action == "gst_invoice_calculator":
                    calc_obs = observation
                trace.append(
                    {
                        "step": step,
                        "thought": thought,
                        "action": action,
                        "action_input": action_input,
                        "observation": observation,
                    }
                )
                continue

            if need_rag and rag_obs is None:
                thought = "I should search the GSTSaral knowledge base to verify the applicable GST rule/rate."
                action_input = {"question": query, "top_k": 3}
                rag_obs = rag_search_tool(**action_input)
                if not rag_obs.get("abstained"):
                    discovered_rate = self._extract_rate_from_rag_text(rag_obs["answer"])
                trace.append(
                    {
                        "step": step,
                        "thought": thought,
                        "action": "rag_search",
                        "action_input": action_input,
                        "observation": rag_obs,
                    }
                )
                continue

            if need_calc and calc_obs is None:
                params = self._extract_invoice_params(query, discovered_rate=discovered_rate)
                thought = (
                    f"Calculating GST invoice split for price={params['price']}, "
                    f"gst_rate={params['gst_rate']}%, within_maharashtra={params['within_maharashtra']}, "
                    f"inclusive={params['price_inclusive_of_gst']}."
                )
                calc_obs = gst_invoice_calculator(**params)
                trace.append(
                    {
                        "step": step,
                        "thought": thought,
                        "action": "gst_invoice_calculator",
                        "action_input": params,
                        "observation": calc_obs,
                    }
                )
                continue

            break

        parts: List[str] = []
        if rag_obs is not None:
            parts.append(rag_obs["answer"])
        if calc_obs is not None:
            if calc_obs["within_maharashtra"]:
                tax_split = (
                    f"CGST ({calc_obs['cgst_rate_percent']}%): Rs. {calc_obs['cgst_amount']:.2f} + "
                    f"SGST ({calc_obs['sgst_rate_percent']}%): Rs. {calc_obs['sgst_amount']:.2f}"
                )
            else:
                tax_split = f"IGST ({calc_obs['igst_rate_percent']}%): Rs. {calc_obs['igst_amount']:.2f}"
            mode_label = "GST-Inclusive Back-Calculation" if calc_obs["price_inclusive_of_gst"] else "GST-Exclusive"
            parts.append(
                f"Invoice Breakdown ({calc_obs['supply_type']}, {mode_label}): "
                f"Taxable Value = Rs. {calc_obs['taxable_value']:.2f}, "
                f"{tax_split}, Total Invoice = Rs. {calc_obs['total_invoice_amount']:.2f}."
            )

        return {
            "query": query,
            "final_answer": " ".join(parts).strip(),
            "steps": trace,
            "rag_result": rag_obs,
            "invoice_calculation": calc_obs,
        }
