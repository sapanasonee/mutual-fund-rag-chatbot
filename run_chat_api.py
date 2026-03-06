"""Run Phase 3 backend. From project root: python run_chat_api.py"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PHASE3 = ROOT / "phase-3-app-frontend-backend"
sys.path.insert(0, str(PHASE3))
PHASE5 = ROOT / "phase-5-conversation-guardrails"
sys.path.insert(0, str(PHASE5))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )
