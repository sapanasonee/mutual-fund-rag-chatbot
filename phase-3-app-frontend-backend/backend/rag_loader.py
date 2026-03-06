"""
Load Phase 2 embedding index and perform retrieval.
Self-contained to avoid importing from phase-2-rag-preparation (hyphen in package name).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional

import joblib


@dataclass
class RetrievedChunk:
    chunk_id: str
    text: str
    metadata: dict
    score: float


def _load_corpus(corpus_path: Path) -> List[dict]:
    chunks = []
    with corpus_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            chunks.append(json.loads(line))
    return chunks


class VectorStore:
    """In-memory vector store for TF-IDF retrieval with optional scheme_id filter."""

    def __init__(self, corpus: List[dict], embeddings: Any, vectorizer: Any):
        self._corpus = corpus
        self._embeddings = embeddings
        self._vectorizer = vectorizer

    @classmethod
    def load(cls, phase2_dir: Path) -> "VectorStore":
        phase2_dir = Path(phase2_dir)
        corpus_path = phase2_dir / "corpus.jsonl"
        emb_path = phase2_dir / "tfidf_embeddings.joblib"
        vec_path = phase2_dir / "tfidf_vectorizer.joblib"
        if not corpus_path.exists() or not emb_path.exists() or not vec_path.exists():
            raise FileNotFoundError(
                f"Phase 2 index not found. Run Phase 2 first. "
                f"Expected: {corpus_path}, {emb_path}, {vec_path}"
            )
        corpus = _load_corpus(corpus_path)
        embeddings = joblib.load(emb_path)
        vectorizer = joblib.load(vec_path)
        return cls(corpus=corpus, embeddings=embeddings, vectorizer=vectorizer)

    def search(
        self,
        query: str,
        scheme_id_filter: Optional[str] = None,
        top_k: int = 5,
    ) -> List[RetrievedChunk]:
        from sklearn.metrics.pairwise import cosine_similarity

        q_vec = self._vectorizer.transform([query])
        scores = cosine_similarity(q_vec, self._embeddings, dense_output=True)[0]

        indices = scores.argsort()[::-1]
        def to_chunk(i: int) -> RetrievedChunk:
            meta = self._corpus[i].get("metadata", {})
            return RetrievedChunk(
                chunk_id=self._corpus[i]["chunk_id"],
                text=self._corpus[i]["text"],
                metadata=dict(meta),
                score=float(scores[i]),
            )

        results: List[RetrievedChunk] = []

        if scheme_id_filter is None:
            for i in indices:
                if len(results) >= top_k:
                    break
                if float(scores[i]) <= 0:
                    continue
                results.append(to_chunk(i))
            return results

        # Prefer scheme-specific chunks first when a scheme is referenced.
        scheme_hits: List[int] = []
        global_hits: List[int] = []
        for i in indices:
            if float(scores[i]) <= 0:
                continue
            meta = self._corpus[i].get("metadata", {})
            chunk_scheme_id = meta.get("scheme_id")
            if chunk_scheme_id == scheme_id_filter:
                scheme_hits.append(i)
            elif chunk_scheme_id is None:
                global_hits.append(i)

        for i in scheme_hits[:top_k]:
            results.append(to_chunk(i))
        if len(results) < top_k:
            for i in global_hits:
                if len(results) >= top_k:
                    break
                results.append(to_chunk(i))

        return results
