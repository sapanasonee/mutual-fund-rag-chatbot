"""
Load Phase 2 semantic embedding index and perform retrieval.
User question -> Embedding model -> Vector similarity search -> Top relevant chunks.
Self-contained to avoid importing from phase-2-rag-preparation (hyphen in package name).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import numpy as np


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


def _cosine_similarity_batch(query_vec: np.ndarray, embeddings: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1
    embeddings_norm = embeddings / norms
    q_norm = np.linalg.norm(query_vec)
    if q_norm == 0:
        return np.zeros(len(embeddings))
    return (embeddings_norm @ query_vec) / q_norm


class VectorStore:
    """In-memory vector store for semantic retrieval with optional scheme_id filter."""

    def __init__(self, corpus: List[dict], embeddings: np.ndarray, model: object):
        self._corpus = corpus
        self._embeddings = np.asarray(embeddings, dtype=np.float32)
        self._model = model

    @classmethod
    def load(cls, phase2_dir: Path) -> "VectorStore":
        from sentence_transformers import SentenceTransformer

        phase2_dir = Path(phase2_dir)
        corpus_path = phase2_dir / "corpus.jsonl"
        emb_path = phase2_dir / "semantic_embeddings.npy"
        meta_path = phase2_dir / "embedding_index_meta.json"

        if not corpus_path.exists() or not emb_path.exists():
            raise FileNotFoundError(
                f"Phase 2 semantic index not found. Run Phase 2 first. "
                f"Expected: {corpus_path}, {emb_path}"
            )

        corpus = _load_corpus(corpus_path)
        embeddings = np.load(emb_path)

        model_name = "all-MiniLM-L6-v2"
        if meta_path.exists():
            with meta_path.open("r", encoding="utf-8") as f:
                meta = json.load(f)
                model_name = meta.get("model", model_name)

        model = SentenceTransformer(model_name)
        return cls(corpus=corpus, embeddings=embeddings, model=model)

    def search(
        self,
        query: str,
        scheme_id_filter: Optional[str] = None,
        top_k: int = 5,
    ) -> List[RetrievedChunk]:
        q_vec = self._model.encode([query], convert_to_numpy=True)[0].astype(np.float32)
        scores = _cosine_similarity_batch(q_vec, self._embeddings)
        indices = np.argsort(scores)[::-1]

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
