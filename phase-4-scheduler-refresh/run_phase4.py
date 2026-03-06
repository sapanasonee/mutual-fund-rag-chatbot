"""
Phase 4 – Scheduler & Data Refresh Orchestration

Runs a single refresh cycle:
- Phase 1 ingestion (indmoney schemes + reference pages) -> data/phase1/
- Phase 2 RAG preparation (corpus + TF-IDF index) -> data/phase2/

Writes a run log entry to: data/phase4/run_log.jsonl

This is intentionally a simple, local orchestrator (no cron/Airflow/Prefect).
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class Phase4RunLog:
    run_id: str
    started_at: str
    ended_at: str
    elapsed_seconds: float
    phase1_exit_code: int
    phase2_exit_code: int
    phase1_scheme_records: int
    phase1_faq_records: int
    phase2_chunks_total: int
    phase2_chunks_scheme_facts: int
    status: str  # "success" | "failed"
    error: str | None = None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    n = 0
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                n += 1
    return n


def _phase2_chunk_counts(corpus_path: Path) -> tuple[int, int]:
    if not corpus_path.exists():
        return 0, 0
    total = 0
    scheme_facts = 0
    with corpus_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            total += 1
            try:
                rec = json.loads(line)
                if (rec.get("metadata") or {}).get("type") == "scheme_facts":
                    scheme_facts += 1
            except Exception:
                continue
    return total, scheme_facts


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    # Use the same interpreter that invoked this script (expected to be .venv python).
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    data_dir = root / "data"
    phase1_dir = data_dir / "phase1"
    phase2_dir = data_dir / "phase2"
    phase4_dir = data_dir / "phase4"
    phase4_dir.mkdir(parents=True, exist_ok=True)

    run_id = str(uuid.uuid4())
    started_at = _utc_now_iso()
    t0 = time.time()

    error: str | None = None
    status = "success"

    # Phase 1
    p1 = _run([sys.executable, "phase-1-data-acquisition/run_ingestion.py"], cwd=root)
    if p1.returncode != 0:
        status = "failed"
        error = f"Phase 1 failed. Output:\n{p1.stdout[-4000:]}"

    # Phase 2 (only if Phase 1 succeeded)
    p2 = None
    if status == "success":
        p2 = _run([sys.executable, "phase-2-rag-preparation/run_phase2.py"], cwd=root)
        if p2.returncode != 0:
            status = "failed"
            error = f"Phase 2 failed. Output:\n{p2.stdout[-4000:]}"

    ended_at = _utc_now_iso()
    elapsed = round(time.time() - t0, 3)

    schemes_path = phase1_dir / "indmoney_schemes.jsonl"
    faqs_path = phase1_dir / "reference_faqs.jsonl"
    corpus_path = phase2_dir / "corpus.jsonl"

    phase1_scheme_records = _count_jsonl(schemes_path)
    phase1_faq_records = _count_jsonl(faqs_path)
    phase2_chunks_total, phase2_chunks_scheme_facts = _phase2_chunk_counts(corpus_path)

    log = Phase4RunLog(
        run_id=run_id,
        started_at=started_at,
        ended_at=ended_at,
        elapsed_seconds=elapsed,
        phase1_exit_code=p1.returncode,
        phase2_exit_code=(p2.returncode if p2 is not None else -1),
        phase1_scheme_records=phase1_scheme_records,
        phase1_faq_records=phase1_faq_records,
        phase2_chunks_total=phase2_chunks_total,
        phase2_chunks_scheme_facts=phase2_chunks_scheme_facts,
        status=status,
        error=error,
    )

    # Use a context manager so the log entry is flushed/closed on Windows.
    run_log_path = phase4_dir / "run_log.jsonl"
    with run_log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(log), ensure_ascii=False) + "\n")

    # Also write the latest run outputs for debugging.
    (phase4_dir / "last_phase1_output.txt").write_text(p1.stdout, encoding="utf-8", errors="replace")
    if p2 is not None:
        (phase4_dir / "last_phase2_output.txt").write_text(p2.stdout, encoding="utf-8", errors="replace")

    print(json.dumps(asdict(log), indent=2, ensure_ascii=False))
    return 0 if status == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())

