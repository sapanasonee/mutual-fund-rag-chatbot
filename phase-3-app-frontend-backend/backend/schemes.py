"""
Load scheme data from Phase 1 JSONL for /funds and /search-funds endpoints.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional


def _load_schemes(phase1_dir: Path) -> List[dict]:
    path = Path(phase1_dir) / "indmoney_schemes.jsonl"
    if not path.exists():
        return []
    schemes = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            scheme = record.get("scheme", {})
            schemes.append({
                "scheme": scheme,
                "holdings": record.get("holdings", []),
                "metadata_blocks": record.get("metadata_blocks", []),
            })
    return schemes


def get_all_schemes(phase1_dir: Path) -> List[dict]:
    return _load_schemes(phase1_dir)


def get_scheme_by_id(phase1_dir: Path, scheme_id: str) -> Optional[dict]:
    """Match by scheme_name, external_id, or index."""
    schemes = _load_schemes(phase1_dir)
    scheme_id_lower = str(scheme_id).lower()
    for rec in schemes:
        s = rec.get("scheme", {})
        name = (s.get("scheme_name") or "").lower()
        ext = (s.get("external_id") or "").lower()
        if scheme_id_lower in name or scheme_id_lower == ext:
            return rec
    return None


def search_schemes(phase1_dir: Path, q: str) -> List[dict]:
    """Fuzzy search by scheme name, AMC, category."""
    schemes = _load_schemes(phase1_dir)
    q_lower = q.lower().strip()
    if not q_lower:
        return [{"scheme": r["scheme"], "holdings": r["holdings"]} for r in schemes]
    results = []
    for rec in schemes:
        s = rec.get("scheme", {})
        name = (s.get("scheme_name") or "").lower()
        amc = (s.get("amc") or "").lower()
        cat = (s.get("category") or "").lower()
        if q_lower in name or q_lower in amc or q_lower in cat:
            results.append({"scheme": s, "holdings": rec.get("holdings", [])})
    return results


def resolve_scheme_id(schemes: List[dict], user_text: str) -> Optional[str]:
    """
    Extract best-matching scheme_id from user text.

    IMPORTANT: Phase 2 corpus uses `scheme_id` derived primarily from Phase 1 `external_id`,
    so we prefer returning `external_id` for correct retrieval filtering.
    """
    user_lower = user_text.lower()
    best: Optional[str] = None
    best_score = 0
    for rec in schemes:
        s = rec.get("scheme", {})
        name = (s.get("scheme_name") or "").lower()
        scheme_id = s.get("external_id") or s.get("scheme_name")
        if not name or not scheme_id:
            continue
        if name in user_lower:
            if len(name) > best_score:
                best = scheme_id
                best_score = len(name)
        elif user_lower in name:
            if len(user_lower) > best_score:
                best = scheme_id
                best_score = len(user_lower)
        else:
            words = [w for w in name.split() if len(w) > 2]
            matches = sum(1 for w in words if w in user_lower)
            if matches >= 2 and matches > best_score:
                best = scheme_id
                best_score = matches
    return best
