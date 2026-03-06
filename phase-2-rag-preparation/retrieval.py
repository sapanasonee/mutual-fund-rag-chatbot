"""
Retrieval over the semantic embedding index.
User question -> Embedding model -> Vector similarity search -> Top relevant chunks.
Supports global search and filter-by-scheme_id.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import numpy as np

# Support running both as a module and as a standalone script
try:
    from .chunking import Chunk, load_corpus
except ImportError:
    from chunking import Chunk, load_corpus


@dataclass
class RetrievedChunk:
    chunk_id: str
    text: str
    metadata: dict
    score: float


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

    def __init__(
        self,
        corpus: List[Chunk],
        embeddings: np.ndarray,
        model: object,
    ):
        self.corpus = corpus
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

        corpus = load_corpus(corpus_path)
        embeddings = np.load(emb_path)

        model_name = "all-MiniLM-L6-v2"
        if meta_path.exists():
            import json
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
        """
        Retrieve top_k chunks most similar to query via vector similarity.
        If scheme_id_filter is set, only return chunks for that scheme (or reference_faq chunks).
        """
        q_vec = self._model.encode([query], convert_to_numpy=True)[0].astype(np.float32)
        scores = _cosine_similarity_batch(q_vec, self._embeddings)
        indices = np.argsort(scores)[::-1]

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
