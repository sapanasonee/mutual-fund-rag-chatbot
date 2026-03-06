## Phase 2 – RAG & Knowledge Preparation

Implements the RAG preprocessing and embedding index per architecture.

### Components

- **text_utils.py** – HTML cleaning, boilerplate removal; token-based chunking (300–500 tokens, overlap).
- **chunking.py** – Build corpus from Phase 1 JSONL: scheme facts, holdings, metadata blocks, reference FAQs. Applies cleaning and chunking; enriches with `scheme_id`, `source`, `source_url`.
- **build_embeddings.py** – TF-IDF vectorization; saves corpus, embeddings, vectorizer, and index metadata.
- **retrieval.py** – `VectorStore.load(phase2_dir)` and `search(query, scheme_id_filter=None, top_k=5)` for global or scheme-scoped retrieval.
- **run_phase2.py** – Main entrypoint. Run from project root: `python -m phase-2-rag-preparation.run_phase2`

### Usage

1. Ensure Phase 1 has run and `data/phase1/` exists.
2. Run: `python -m phase-2-rag-preparation.run_phase2`
3. Outputs: `data/phase2/corpus.jsonl`, `tfidf_embeddings.joblib`, `tfidf_vectorizer.joblib`, `embedding_index_meta.json`
4. Use `VectorStore.load(Path("data/phase2"))` in Phase 3 for retrieval.

