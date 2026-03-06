## Phase 4 – Scheduler & Data Refresh

This folder is for:
- Scheduler/orchestrator code (cron jobs, Airflow/Prefect flows, etc.).
- Pipelines that:
  - Trigger Phase 1 ingestion to pull latest data from `https://www.indmoney.com/`.
  - Trigger Phase 2 RAG preprocessing to refresh embeddings and index.
  - Optionally signal Phase 3 backend to invalidate caches or reload metadata.
- Run logs, monitoring hooks, and error handling for refresh cycles.

