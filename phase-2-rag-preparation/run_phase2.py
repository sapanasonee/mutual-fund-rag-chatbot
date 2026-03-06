"""
Phase 2 pipeline: RAG preprocessing and embedding index build.
Run from project root: python -m phase_2_rag_preparation.run_phase2

Or: python -m phase-2-rag-preparation.run_phase2  (if package name allows hyphens)
"""
from __future__ import annotations

from pathlib import Path

# Support running both as a module and as a standalone script
try:  # pragma: no cover - import flexibility
    from .build_embeddings import build_and_save_embeddings
except ImportError:
    from build_embeddings import build_and_save_embeddings


def main() -> None:
    base = Path(__file__).resolve().parent.parent
    data_dir = base / "data"
    phase1_dir = data_dir / "phase1"
    phase2_dir = data_dir / "phase2"

    phase2_dir.mkdir(parents=True, exist_ok=True)
    corpus_output = phase2_dir / "corpus.jsonl"
    embeddings_output = phase2_dir / "tfidf_embeddings.joblib"
    vectorizer_output = phase2_dir / "tfidf_vectorizer.joblib"
    index_metadata_output = phase2_dir / "embedding_index_meta.json"

    build_and_save_embeddings(
        phase1_dir=phase1_dir,
        corpus_output=corpus_output,
        embeddings_output=embeddings_output,
        vectorizer_output=vectorizer_output,
        index_metadata_output=index_metadata_output,
    )
    print(f"Phase 2 complete. Index at {phase2_dir}")


if __name__ == "__main__":
    main()
