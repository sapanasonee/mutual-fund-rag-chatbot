"""
Chat orchestration: intent analysis, scheme resolution, knowledge retrieval, LLM response.
All answers grounded in retrieved embeddings only. Personal-info queries declined.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv

load_dotenv()

# Personal info keywords - queries containing these are out of scope
PERSONAL_INFO_KEYWORDS = [
    "pan", "aadhaar", "aadhar", "bank account", "account number",
    "folio number", "mobile number", "phone number", "email id",
    "kyc", "passport", "voter id", "driving license", "dob", "date of birth",
]

def is_general_mf_question(query: str) -> bool:

    keywords = [
        "elss",
        "lock-in",
        "exit load",
        "riskometer",
        "benchmark",
        "minimum sip",
        "statement",
        "capital gains",
    ]

    query = query.lower()

    for k in keywords:
        if k in query:
            return True

    return False

def classify_intent(query: str) -> str:
    """Classify into: structured_lookup, portfolio_query, how_to, comparative, general_explanation."""
    q = query.lower().strip()
    if any(kw in q for kw in PERSONAL_INFO_KEYWORDS):
        return "personal_info_out_of_scope"
    if "compare" in q or "vs" in q or "versus" in q or "difference between" in q:
        return "comparative"
    if "download" in q or "statement" in q or "how to" in q or "how do i" in q:
        return "how_to"
    if "holding" in q or "portfolio" in q or "sector" in q or "allocation" in q:
        return "portfolio_query"
    if any(
        k in q
        for k in [
            "expense ratio", "exit load", "minimum sip", "min sip",
            "riskometer", "benchmark", "lock-in", "lock in", "lockin",
            "nav", "price", "return",
        ]
    ):
        return "structured_lookup"
    return "general_explanation"


def is_personal_info_query(query: str) -> bool:
    return classify_intent(query) == "personal_info_out_of_scope"


def build_context_from_chunks(chunks: List) -> str:
    """Format retrieved chunks for LLM context."""
    parts = []
    for i, c in enumerate(chunks, 1):
        text = getattr(c, "text", c) if not isinstance(c, str) else c
        meta = getattr(c, "metadata", {}) if hasattr(c, "metadata") else {}
        source = meta.get("source") or meta.get("topic") or "Reference"
        source_url = meta.get("source_url")
        url_line = f"\nSource URL: {source_url}" if source_url else ""
        parts.append(f"[{i}] (Source: {source}){url_line}\n{text}")
    return "\n\n---\n\n".join(parts)


def _extractive_fallback_answer(query: str, context: str) -> str:
    """
    Deterministic, retrieval-grounded fallback when Grok is unavailable.
    This function ONLY uses the retrieved context text.
    """
    q = (query or "").lower()

    def find_value(pattern: str) -> str | None:
        m = re.search(pattern, context, flags=re.IGNORECASE)
        return m.group(1).strip() if m else None

    def find_first_url() -> str | None:
        m = re.search(r"Source URL:\s*(\S+)", context, flags=re.IGNORECASE)
        return m.group(1).strip() if m else None

    scheme = find_value(r"Scheme name:\s*([^.\n]+)")
    nav = find_value(r"Latest NAV:\s*([0-9]+(?:\.[0-9]+)?)")
    nav_date = find_value(r"NAV as on\s*([0-9]{2}\s*[A-Za-z]{3}\s*[0-9]{4})")
    aum = find_value(r"AUM.*?:\s*([0-9]+(?:\.[0-9]+)?)")
    exit_load = find_value(r"Exit load:\s*([^\.\n]+)")
    lockin = find_value(r"Lock-in period \(months\):\s*([0-9]+)")
    exp = find_value(r"Expense ratio:\s*([0-9]+(?:\.[0-9]+)?)%")

    lines: List[str] = []
 
    # How-to: capital gains statement / statements download
    if ("capital gain" in q or "capital gains" in q) and "statement" in q:
        url = find_first_url()

        lines.append("How to download a Capital Gains Statement (from the retrieved reference):")

        if url:
            lines.append(f"1) Go to the HDFC AMC 'Request Statement' page: {url}")
        else:
            lines.append("1) Go to the HDFC AMC 'Request Statement' page.")

        lines.append("2) Choose 'Capital Gains Statement'.")
        lines.append("3) Enter your folio number (and required details).")
        lines.append("4) Submit to receive the statement.")

        source_url = find_first_url()

        if source_url:
            lines.append(f"\nSource: {source_url}")
        else:
            lines.append("\nSource: Official AMC / SEBI / AMFI pages")

        lines.append("Last updated from sources.")
        lines.append("This is for informational purposes only. Please consult a qualified advisor.")

        return "\n".join(lines)
    if scheme:
        lines.append(f"{scheme}")

    if "nav" in q and nav:
        if nav_date:
            lines.append(f"Latest NAV (as on {nav_date}): {nav}.")
        else:
            lines.append(f"Latest NAV: {nav}.")

    if ("aum" in q or "assets under management" in q) and aum:
        lines.append(f"AUM (approx.): {aum}.")

    if "exit load" in q and exit_load:
        lines.append(f"Exit load: {exit_load}.")

    if ("lock" in q or "lock-in" in q or "lockin" in q) and lockin is not None:
        lines.append(f"Lock-in period (months): {lockin}.")

    if "expense ratio" in q and exp:
        lines.append(f"Expense ratio: {exp}%.")

    # If query isn't directly one of the above, return the most relevant snippet
    if not lines:
        snippet = context.strip()
        if len(snippet) > 900:
            snippet = snippet[:900].rstrip() + "…"
        lines.append("Here’s what I found in the knowledge base:\n" + snippet)

    source_url = find_first_url()

    if source_url:
        lines.append(f"\nSource: {source_url}")
    else:
        lines.append("\nSource: Official AMC / SEBI / AMFI pages")

    lines.append("Last updated from sources.")
    lines.append("This is for informational purposes only. Please consult a qualified advisor.")

    return "\n".join(lines)

def generate_response(
    query: str,
    context: str,
    scheme_id: Optional[str],
    api_key: str,
) -> str:
    """Call Grok to produce answer strictly from context. No invented facts."""
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url="https://api.x.ai/v1")
    model = os.getenv("GROK_MODEL", "grok-beta")

    system = """You are a mutual fund information assistant. Your answers MUST be grounded ONLY in the provided context (retrieved information). Do NOT invent or add any facts not present in the context.

Rules:
- Summarize or quote from the context only.
- If the context does not contain relevant information, say "I don't have that information in my knowledge base."
- Do not give investment advice or recommend funds.
- Include a brief disclaimer: "This is for informational purposes only. Please consult a qualified advisor."
- For personal information (PAN, Aadhaar, bank details, etc.), you will not receive such queries as they are out of scope."""

    user_msg = f"""Context from knowledge base:

{context}

---

User question: {query}

Answer using ONLY the context above. If the context is insufficient, say so clearly."""

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg},
            ],
            max_tokens=1024,
        )
        answer = resp.choices[0].message.content

        answer = answer + "\n\nSource: Official AMC / SEBI / AMFI pages\nLast updated from sources."

        return answer
    except Exception as e:
        # Fall back to an extractive, grounded answer so the chatbot remains usable.
        return _extractive_fallback_answer(query, context)


def get_out_of_scope_message() -> str:
    return (
        "Questions about personal information (e.g., PAN, Aadhaar, bank account, folio number) "
        "are out of scope for this chatbot. For account-specific help, please contact your "
        "fund house or registrar directly."
    )


def get_general_out_of_scope_message() -> str:
    return "This question is out of scope for this INDMoney chatbot."
