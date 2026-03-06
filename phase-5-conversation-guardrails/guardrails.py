from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


ADVICE_PATTERNS = [
    r"\bwhich\s+fund\s+should\s+i\s+buy\b",
    r"\bwhich\s+mutual\s+fund\s+should\s+i\s+buy\b",
    r"\bbest\s+mutual\s+fund\b",
    r"\bbest\s+fund\b",
    r"\brecommend\s+(a|any)\s+fund\b",
    r"\bshould\s+i\s+invest\b",
    r"\bguarantee(d)?\s+returns?\b",
    r"\bcan\s+you\s+promise\b",
]


@dataclass
class GuardrailResult:
    blocked: bool
    reason: Optional[str] = None
    message: Optional[str] = None


def check_investment_advice(query: str) -> GuardrailResult:
    q = (query or "").lower().strip()
    for pat in ADVICE_PATTERNS:
        if re.search(pat, q):
            return GuardrailResult(
                blocked=True,
                reason="investment_advice",
                message=(
                    "I can’t recommend or tell you which mutual fund to buy or guarantee returns. "
                    "I can share factual information (NAV, exit load, lock-in, AUM, returns shown on INDMoney pages) "
                    "about the specific schemes covered by this chatbot. "
                    "This is for informational purposes only—please consult a qualified advisor."
                ),
            )
    return GuardrailResult(blocked=False)


def looks_like_followup_without_scheme(query: str) -> bool:
    q = (query or "").lower()
    # Simple heuristic: pronouns + metric keywords.
    return (
        any(p in q for p in ["it", "this fund", "that fund", "the fund", "its", "this"])
        and any(k in q for k in ["nav", "exit load", "lock", "expense", "aum", "return", "holdings", "portfolio"])
    )

