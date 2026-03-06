"""
Build semantic embeddings using sentence-transformers.
Replaces TF-IDF with vector similarity search for better semantic retrieval.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List

import numpy as np

# Support running both as a module and as a standalone script
try:
    from .chunking import Chunk, build_corpus_from_phase1, save_corpus
except ImportError:
    from chunking import Chunk, build_corpus_from_phase1, save_corpus


EMBEDDING_MODEL = "all-MiniLM-L6-v2"


def build_and_save_semantic_embeddings(
    phase1_dir: Path,
    corpus_output: Path,
    embeddings_output: Path,
    index_metadata_output: Path,
) -> None:
    """
    Build semantic embeddings for all chunks using sentence-transformers.
    User question -> Embedding model -> Vector similarity search -> Top chunks -> LLM.
    """
    from sentence_transformers import SentenceTransformer

    chunks = build_corpus_from_phase1(phase1_dir)
    if not chunks:
        raise RuntimeError(
            f"No chunks produced. Ensure Phase 1 has run and {phase1_dir} contains "
            "indmoney_schemes.jsonl and reference_faqs.jsonl."
        )
    save_corpus(chunks, corpus_output)

    texts = [c.text for c in chunks]
    model = SentenceTransformer(EMBEDDING_MODEL)
    embeddings = model.encode(texts, show_progress_bar=True, convert_to_numpy=True)

    embeddings_output.parent.mkdir(parents=True, exist_ok=True)
    index_metadata_output.parent.mkdir(parents=True, exist_ok=True)

    np.save(embeddings_output, embeddings.astype(np.float32))

    meta = {
        "n_chunks": len(chunks),
        "vector_dim": int(embeddings.shape[1]),
        "corpus_path": str(corpus_output),
        "model": EMBEDDING_MODEL,
    }
    with index_metadata_output.open("w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)


def main() -> None:
    base = Path(__file__).resolve().parent.parent
    phase1_dir = base / "data" / "phase1"
    phase2_dir = base / "data" / "phase2"
    phase2_dir.mkdir(parents=True, exist_ok=True)

    build_and_save_semantic_embeddings(
        phase1_dir=phase1_dir,
        corpus_output=phase2_dir / "corpus.jsonl",
        embeddings_output=phase2_dir / "semantic_embeddings.npy",
        index_metadata_output=phase2_dir / "embedding_index_meta.json",
    )
    print("Semantic embeddings built successfully.")


if __name__ == "__main__":
    main()
