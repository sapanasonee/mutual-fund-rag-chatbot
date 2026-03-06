from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List

import json
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer

# Support running both as a module and as a standalone script
try:  # pragma: no cover - import flexibility
    from .chunking import Chunk, build_corpus_from_phase1, save_corpus
except ImportError:
    from chunking import Chunk, build_corpus_from_phase1, save_corpus


@dataclass
class EmbeddingIndexMetadata:
    n_chunks: int
    vector_dim: int
    corpus_path: str


def build_and_save_embeddings(
    phase1_dir: Path,
    corpus_output: Path,
    embeddings_output: Path,
    vectorizer_output: Path,
    index_metadata_output: Path,
) -> None:
    """
    Build TF-IDF embeddings for all chunks derived from Phase 1 outputs.

    This implementation deliberately uses a local TF-IDF model so that
    the chatbot can later perform similarity search purely based on
    embeddings, without inventing new facts.
    """
    chunks = build_corpus_from_phase1(phase1_dir)
    if not chunks:
        raise RuntimeError(
            f"No chunks produced. Ensure Phase 1 has run and {phase1_dir} contains indmoney_schemes.jsonl and reference_faqs.jsonl."
        )
    save_corpus(chunks, corpus_output)

    texts = [c.text for c in chunks]

    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),
        max_features=5000,
        stop_words="english",
    )
    matrix = vectorizer.fit_transform(texts)

    embeddings_output.parent.mkdir(parents=True, exist_ok=True)
    vectorizer_output.parent.mkdir(parents=True, exist_ok=True)
    index_metadata_output.parent.mkdir(parents=True, exist_ok=True)

    # Save sparse matrix and vectorizer
    joblib.dump(matrix, embeddings_output)
    joblib.dump(vectorizer, vectorizer_output)

    meta = EmbeddingIndexMetadata(
        n_chunks=len(chunks),
        vector_dim=matrix.shape[1],
        corpus_path=str(corpus_output),
    )
    with index_metadata_output.open("w", encoding="utf-8") as f:
        json.dump(asdict(meta), f, indent=2)


def main() -> None:
    base = Path("data")
    phase1_dir = base / "phase1"
    phase2_dir = base / "phase2"

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


if __name__ == "__main__":
    main()

