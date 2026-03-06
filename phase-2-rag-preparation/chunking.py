"""RAG preprocessing: build corpus from Phase 1, with HTML cleaning and token-based chunking."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import json

# Support running both as a module and as a standalone script
try:  # pragma: no cover - import flexibility
    from .text_utils import chunk_text, clean_html
except ImportError:
    from text_utils import chunk_text, clean_html

CHUNK_SIZE_TOKENS = 400
CHUNK_OVERLAP_TOKENS = 50


@dataclass
class Chunk:
    chunk_id: str
    text: str
    metadata: Dict[str, object]


def _load_jsonl(path: Path) -> Iterable[dict]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def _scheme_fact_block(scheme_record: dict) -> str:
    scheme = scheme_record.get("scheme", {})
    name = scheme.get("scheme_name") or "Unknown scheme"

    lines = [f"Scheme name: {name}."]

    def add_line(label: str, key: str, suffix: str = "") -> None:
        value = scheme.get(key)
        if value not in (None, ""):
            lines.append(f"{label}: {value}{suffix}.")

    add_line("AMC", "amc")
    add_line("Category", "category")
    add_line("Sub-category", "sub_category")
    add_line("Riskometer", "riskometer")
    add_line("Benchmark", "benchmark")
    add_line("Lock-in period (months)", "lock_in_period_months")
    add_line("Plan type", "plan_type")
    add_line("Option", "option")
    add_line("Expense ratio", "expense_ratio", suffix="%")
    add_line("Exit load", "exit_load")
    add_line("Minimum SIP amount", "minimum_sip_amount")
    add_line("Minimum lump sum amount", "minimum_lump_sum_amount")
    # Key numeric metrics important for Phase 1 Q&A
    add_line("Latest NAV", "last_nav")
    add_line("Assets under management (AUM, approximate)", "aum")
    add_line("1-year return (%)", "return_1y", suffix="%")
    add_line("3-year return (%)", "return_3y", suffix="%")
    add_line("5-year return (%)", "return_5y", suffix="%")

    return " ".join(lines)


def _holdings_block(scheme_record: dict, max_holdings: int = 15) -> Optional[str]:
    holdings = scheme_record.get("holdings") or []
    if not holdings:
        return None

    lines = ["Top portfolio holdings:"]
    for h in holdings[:max_holdings]:
        name = h.get("holding_name") or "Unknown"
        sector = h.get("sector")
        weight = h.get("weight_percentage")
        parts = [name]
        if sector:
            parts.append(f"sector {sector}")
        if weight is not None:
            parts.append(f"weight {weight}%")
        lines.append(" - " + ", ".join(parts))

    return "\n".join(lines)


def build_corpus_from_phase1(
    phase1_dir: Path,
) -> List[Chunk]:
    """
    Build a text corpus from Phase 1 JSONL outputs.

    - Converts structured scheme attributes into fact blocks.
    - Adds portfolio holdings summary if available.
    - Adds raw text from indmoney metadata blocks.
    - Adds FAQ/reference pages from SEBI/AMFI/AMC.
    """
    corpus: List[Chunk] = []

    schemes_path = phase1_dir / "indmoney_schemes.jsonl"
    faqs_path = phase1_dir / "reference_faqs.jsonl"

    # Schemes and holdings
    if schemes_path.exists():
        for idx, record in enumerate(_load_jsonl(schemes_path)):
            scheme = record.get("scheme", {})
            scheme_id = scheme.get("external_id") or scheme.get("scheme_id") or scheme.get("scheme_name") or str(idx)
            base_meta: Dict[str, object] = {
                "source": "indmoney_scheme",
                "scheme_id": scheme_id,
                "scheme_name": scheme.get("scheme_name"),
                "source_url": scheme.get("source_url"),
            }

            fact_text = _scheme_fact_block(record)
            corpus.append(
                Chunk(
                    chunk_id=f"scheme_facts_{idx}",
                    text=fact_text,
                    metadata={**base_meta, "type": "scheme_facts"},
                )
            )

            holdings_text = _holdings_block(record)
            if holdings_text:
                corpus.append(
                    Chunk(
                        chunk_id=f"scheme_holdings_{idx}",
                        text=holdings_text,
                        metadata={**base_meta, "type": "portfolio_holdings"},
                    )
                )

            for j, meta_block in enumerate(record.get("metadata_blocks") or []):
                raw_text = meta_block.get("clean_text") or ""
                if not raw_text.strip():
                    continue
                text = clean_html(raw_text)
                if not text.strip():
                    continue
                sub_chunks = chunk_text(text, CHUNK_SIZE_TOKENS, CHUNK_OVERLAP_TOKENS)
                for k, sub in enumerate(sub_chunks):
                    corpus.append(
                        Chunk(
                            chunk_id=f"scheme_text_{idx}_{j}_{k}",
                            text=sub,
                            metadata={
                                **base_meta,
                                "type": "scheme_page_text",
                                "source_label": meta_block.get("source"),
                            },
                        )
                    )

    # Reference FAQ pages (SEBI/AMFI/AMC) - no scheme_id (global)
    if faqs_path.exists():
        for idx, faq in enumerate(_load_jsonl(faqs_path)):
            raw_text = faq.get("clean_text") or ""
            if not raw_text.strip():
                continue
            text = clean_html(raw_text)
            if not text.strip():
                continue
            sub_chunks = chunk_text(text, CHUNK_SIZE_TOKENS, CHUNK_OVERLAP_TOKENS)
            for k, sub in enumerate(sub_chunks):
                corpus.append(
                    Chunk(
                        chunk_id=f"faq_{idx}_{k}",
                        text=sub,
                        metadata={
                            "source": faq.get("source"),
                            "topic": faq.get("topic"),
                            "source_url": faq.get("url"),
                            "type": "reference_faq",
                            "scheme_id": None,
                        },
                    )
                )

    return corpus


def save_corpus(chunks: List[Chunk], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for ch in chunks:
            record = {
                "chunk_id": ch.chunk_id,
                "text": ch.text,
                "metadata": ch.metadata,
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_corpus(path: Path) -> List[Chunk]:
    chunks: List[Chunk] = []
    for record in _load_jsonl(path):
        chunks.append(
            Chunk(
                chunk_id=record["chunk_id"],
                text=record["text"],
                metadata=record.get("metadata", {}),
            )
        )
    return chunks

