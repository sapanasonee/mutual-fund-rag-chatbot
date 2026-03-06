"""
Phase 3 Backend: FastAPI chat orchestration service.
Endpoints: POST /chat, GET /funds/{scheme_id}, GET /search-funds
Uses VectorStore.load(Path("data/phase2")) for RAG retrieval.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from conversation_store import ConversationStore
from guardrails import check_investment_advice, looks_like_followup_without_scheme

from .chat import (
    build_context_from_chunks,
    classify_intent,
    generate_response,
    get_general_out_of_scope_message,
    get_out_of_scope_message,
    is_personal_info_query,
)
from .rag_loader import VectorStore
from .schemes import get_all_schemes, get_scheme_by_id, resolve_scheme_id, search_schemes

# Paths relative to project root (parent of phase-3-app-frontend-backend)
ROOT = Path(__file__).resolve().parent.parent.parent
PHASE1_DIR = ROOT / "data" / "phase1"
PHASE2_DIR = ROOT / "data" / "phase2"
PHASE5_DB = ROOT / "data" / "phase5" / "conversations.sqlite"

_conv_store: Optional[ConversationStore] = None

# Load VectorStore once at startup
_vector_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore.load(PHASE2_DIR)
    return _vector_store


def get_conversation_store() -> ConversationStore:
    global _conv_store
    if _conv_store is None:
        _conv_store = ConversationStore(PHASE5_DB)
    return _conv_store


app = FastAPI(title="RAG Mutual Fund Chatbot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Request/Response models ---
class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    query: str
    conversation_id: Optional[str] = None
    conversation_history: Optional[List[ChatMessage]] = None


class ChatResponse(BaseModel):
    answer: str
    intent: Optional[str] = None
    conversation_id: Optional[str] = None


# --- Endpoints ---
@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    query = (req.query or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query is required")

    conv = get_conversation_store()
    conversation_id = req.conversation_id or conv.create_conversation()

    if is_personal_info_query(query):
        conv.add_message(conversation_id, "user", query)
        conv.add_message(conversation_id, "assistant", get_out_of_scope_message())
        return ChatResponse(
            answer=get_out_of_scope_message(),
            intent="personal_info_out_of_scope",
            conversation_id=conversation_id,
        )

    advice = check_investment_advice(query)
    if advice.blocked:
        conv.add_message(conversation_id, "user", query)
        conv.add_message(conversation_id, "assistant", advice.message or "")
        return ChatResponse(
            answer=advice.message or "This request is not supported.",
            intent="investment_advice",
            conversation_id=conversation_id,
        )

    store = get_vector_store()
    schemes = get_all_schemes(PHASE1_DIR)
    scheme_id = resolve_scheme_id(schemes, query)
    intent = classify_intent(query)

    # Phase 5: follow-up resolution. If user didn't mention a scheme but asks a follow-up,
    # reuse the last referenced scheme in the conversation.
    if scheme_id is None and looks_like_followup_without_scheme(query):
        last = conv.get_last_scheme_id(conversation_id)
        if last:
            scheme_id = last

    # Enforce product scope: if the user didn't reference a specific scheme,
    # only allow "how-to/statement download" style questions; everything else is out of scope.
    if scheme_id is None and intent not in ["how_to", "structured_lookup", "general_explanation"]:
        conv.add_message(conversation_id, "user", query)
        conv.add_message(conversation_id, "assistant", get_general_out_of_scope_message())
        return ChatResponse(
            answer=get_general_out_of_scope_message(),
            intent=intent,
            conversation_id=conversation_id,
        )

    chunks = store.search(
        query=query,
        scheme_id_filter=scheme_id,
        top_k=6,
    )

    if not chunks:
        conv.add_message(conversation_id, "user", query)
        msg = (
            "I don't have relevant information in my knowledge base for that question. Please try rephrasing or ask about the mutual fund schemes we cover (e.g., HDFC Small Cap, HDFC Flexi Cap, SBI Contra, HDFC ELSS Tax Saver)."
        )
        conv.add_message(conversation_id, "assistant", msg)
        return ChatResponse(
            answer="I don't have relevant information in my knowledge base for that question. Please try rephrasing or ask about the mutual fund schemes we cover (e.g., HDFC Small Cap, HDFC Flexi Cap, SBI Contra, HDFC ELSS Tax Saver).",
            intent=intent,
            conversation_id=conversation_id,
        )

    context = build_context_from_chunks(chunks)
    import os
    api_key = os.getenv("GROK_API_KEY", "")
    if not api_key:
        conv.add_message(conversation_id, "user", query)
        msg = "GROK_API_KEY is not configured. Please set it in your .env file."
        conv.add_message(conversation_id, "assistant", msg)
        return ChatResponse(
            answer="GROK_API_KEY is not configured. Please set it in your .env file.",
            intent=intent,
            conversation_id=conversation_id,
        )

    answer = generate_response(query, context, scheme_id, api_key)
    conv.add_message(conversation_id, "user", query)
    conv.add_message(conversation_id, "assistant", answer)
    if scheme_id is not None:
        conv.set_last_scheme_id(conversation_id, scheme_id)
    return ChatResponse(answer=answer, intent=intent, conversation_id=conversation_id)


@app.get("/funds/{scheme_id}")
def get_fund(scheme_id: str):
    rec = get_scheme_by_id(PHASE1_DIR, scheme_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Scheme not found")
    return rec


@app.get("/search-funds")
def search_funds(q: str = ""):
    return search_schemes(PHASE1_DIR, q)


@app.get("/health")
def health():
    return {"status": "ok"}
