## Phase 3 – Chat Application (Backend & Frontend)

### Backend
- **backend/main.py** – FastAPI app with `POST /chat`, `GET /funds/{scheme_id}`, `GET /search-funds`
- **backend/rag_loader.py** – Loads `VectorStore.load(Path("data/phase2"))` for RAG retrieval
- **backend/schemes.py** – Loads Phase 1 JSONL for scheme data
- **backend/chat.py** – Intent classifier, scheme resolver, Grok LLM; answers grounded in embeddings only; personal-info queries declined

### Frontend
- **frontend/** – React + Vite + Tailwind chat UI with quick actions
- Proxy to backend (port 8000) via Vite config

### Run
1. Ensure Phase 1 and Phase 2 have run; `data/phase1/` and `data/phase2/` exist.
2. Set `GROK_API_KEY` in `.env`.
3. Backend: from project root: `python run_chat_api.py` (or `uvicorn` with path to backend).
4. Frontend: `cd phase-3-app-frontend-backend/frontend && npm install && npm run dev`
5. Open http://localhost:5173

