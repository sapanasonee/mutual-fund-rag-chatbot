"""
Retrieval over the embedding index.
Supports global search and filter-by-scheme_id per architecture.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import joblib
from scipy.sparse import csr_matrix

# Support running both as a module and as a standalone script
try:  # pragma: no cover - import flexibility
    from .chunking import Chunk, load_corpus
except ImportError:
    from chunking import Chunk, load_corpus


@dataclass
class RetrievedChunk:
    chunk_id: str
    text: str
    metadata: dict
    score: float


class VectorStore:
    """In-memory vector store for TF-IDF retrieval with optional scheme_id filter."""

    def __init__(
        self,
        corpus: List[Chunk],
        embeddings: csr_matrix,
        vectorizer: object,
    ):
        self.corpus = corpus
        self.embeddings = embeddings
        self.vectorizer = vectorizer

    @classmethod
    def load(cls, phase2_dir: Path) -> "VectorStore":
        phase2_dir = Path(phase2_dir)
        corpus_path = phase2_dir / "corpus.jsonl"
        emb_path = phase2_dir / "tfidf_embeddings.joblib"
        vec_path = phase2_dir / "tfidf_vectorizer.joblib"
        if not corpus_path.exists() or not emb_path.exists() or not vec_path.exists():
            raise FileNotFoundError(
                f"Phase 2 index not found. Run build_embeddings first. "
                f"Expected: {corpus_path}, {emb_path}, {vec_path}"
            )
        corpus = load_corpus(corpus_path)
        embeddings = joblib.load(emb_path)
        vectorizer = joblib.load(vec_path)
        return cls(corpus=corpus, embeddings=embeddings, vectorizer=vectorizer)

    def search(
        self,
        query: str,
        scheme_id_filter: Optional[str] = None,
        top_k: int = 5,
    ) -> List[RetrievedChunk]:
        """
        Retrieve top_k chunks most similar to query.
        If scheme_id_filter is set, only return chunks for that scheme (or reference_faq chunks with scheme_id=None).
        """
        from sklearn.metrics.pairwise import cosine_similarity

        q_vec = self.vectorizer.transform([query])
        scores = cosine_similarity(q_vec, self.embeddings, dense_output=True)[0]

        indices = scores.argsort()[::-1]
        results: List[RetrievedChunk] = []
        for i in indices:
            if len(results) >= top_k:
                break
            meta = self.corpus[i].metadata
            chunk_scheme_id = meta.get("scheme_id")
            if scheme_id_filter is not None:
                if chunk_scheme_id != scheme_id_filter and chunk_scheme_id is not None:
                    continue
            score = float(scores[i])
            if score <= 0:
                continue
            results.append(
                RetrievedChunk(
                    chunk_id=self.corpus[i].chunk_id,
                    text=self.corpus[i].text,
                    metadata=dict(meta),
                    score=score,
                )
            )
        return results
