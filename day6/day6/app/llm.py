import json
import os
import re
from pathlib import Path
from typing import Any
from dotenv import load_dotenv
from groq import Groq

# Load .env from day6\day6, day6, or top-level GSTSaral root
APP_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(APP_ROOT / ".env")
load_dotenv(APP_ROOT.parent / ".env")
load_dotenv(APP_ROOT.parent.parent / ".env")


class GSTSaralLLM:
    def __init__(self, model: str | None = None, temperature: float = 0.2) -> None:
        self.api_key = os.getenv("GROQ_API_KEY", "").strip()
        env_provider = os.getenv("LLM_PROVIDER", "groq").strip().lower()
        if self.api_key and not os.getenv("GEMINI_API_KEY", "").strip():
            self.provider = "groq"
        else:
            self.provider = env_provider or "groq"

        self.model = (
            model
            or os.getenv("GROQ_MODEL", "openai/gpt-oss-120b").strip()
        )
        self.temperature = temperature
        self.client = Groq(api_key=self.api_key) if self.api_key else None

    def _format_context(self, context: Any) -> str:
        if isinstance(context, str):
            return context
        if isinstance(context, list):
            lines = []
            for idx, r in enumerate(context, start=1):
                if isinstance(r, dict):
                    topic = r.get("item_or_topic") or r.get("title") or f"Record {idx}"
                    new_rule = r.get("new_rule") or r.get("text") or r.get("content") or ""
                    old_rule = r.get("old_rule", "")
                    source = r.get("source", "CBIC / GST Council")
                    lines.append(
                        f"[{idx}] {topic} (Source: {source})\n"
                        f"    Current Rule: {new_rule}\n"
                        f"    Previous Rule: {old_rule or 'N/A'}"
                    )
                else:
                    lines.append(f"[{idx}] {r}")
            return "\n\n".join(lines)
        return str(context or "")

    def generate(self, prompt: str, system_prompt: str | None = None, fallback_context: str = "") -> str:
        if not self.client:
            if fallback_context:
                return (
                    "[Offline Fallback - GROQ_API_KEY missing]\n"
                    f"Relevant GST Context:\n{fallback_context}"
                )
            return "GROQ_API_KEY is missing. Add GROQ_API_KEY=gsk_... to your .env file."

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        models_to_try = list(
            dict.fromkeys(
                [
                    self.model,
                    "openai/gpt-oss-120b",
                    "llama-3.3-70b-versatile",
                    "llama-3.1-8b-instant",
                ]
            )
        )

        last_error = ""
        for model_name in models_to_try:
            try:
                client_resp = self.client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    temperature=self.temperature,
                    timeout=20.0,
                )
                content = client_resp.choices[0].message.content
                if content:
                    return content.strip()
            except Exception as exc:
                last_error = f"{model_name}: {exc}"

        if fallback_context:
            return (
                f"[Offline Fallback - Upstream LLM unavailable: {last_error}]\n\n"
                f"Grounded GST Records:\n{fallback_context}"
            )
        raise RuntimeError(f"Groq API call failed. Last error -> {last_error}")

    @staticmethod
    def _parse_structured_response(raw_text: str, has_context: bool) -> dict[str, Any]:
        cleaned = raw_text.strip()
        # Strip markdown code fences if present
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE).strip()
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict):
                return {
                    "answer": str(parsed.get("answer", raw_text)),
                    "confidence": str(parsed.get("confidence", "high" if has_context else "low")),
                    "follow_up": str(
                        parsed.get(
                            "follow_up",
                            "Would you like to calculate GST on an invoice for this item?",
                        )
                    ),
                }
        except Exception:
            pass

        return {
            "answer": raw_text,
            "confidence": "high" if has_context and "I don't know" not in raw_text else "low",
            "follow_up": "Would you like to check CGST/SGST vs. IGST or calculate an invoice?",
        }

    def generate_chat_response(
        self,
        question: str,
        context: Any = "",
        prompt_version: str = "v2",
    ) -> dict[str, Any]:
        context_text = self._format_context(context)
        has_context = bool(context_text.strip())

        json_instruction = (
            'Return ONLY valid JSON with exactly three string keys: '
            '"answer", "confidence" ("high", "medium", or "low"), and "follow_up".'
        )

        if prompt_version == "v1":
            system_prompt = (
                "You are a helpful Indian GST assistant. Answer the user's question concisely. "
                + json_instruction
            )
        else:
            system_prompt = (
                "You are GSTSaral, an Indian GST compliance assistant for MSMEs and freelancers. "
                "Answer strictly from the provided GST context with inline citations like [1], [2]. "
                "If an older rule (e.g., 2017/18) conflicts with a newer rule, explicitly state that "
                "the latest rule wins and cite both. If the answer is not in the context, set "
                'answer to "I don\'t know based on the available GST records." and confidence to "low". '
                + json_instruction
            )

        user_prompt = (
            f"Context:\n{context_text}\n\nQuestion: {question}"
            if has_context
            else f"Question: {question}"
        )

        raw_output = self.generate(
            prompt=user_prompt,
            system_prompt=system_prompt,
            fallback_context=context_text,
        )
        return self._parse_structured_response(raw_output, has_context=has_context)

    def ask(self, prompt: str, system_prompt: str | None = None) -> str:
        return self.generate(prompt=prompt, system_prompt=system_prompt)

    def chat(self, prompt: str, system_prompt: str | None = None) -> str:
        return self.generate(prompt=prompt, system_prompt=system_prompt)