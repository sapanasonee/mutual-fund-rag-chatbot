## RAG Mutual Fund Chatbot – Phase-wise Architecture

This document describes a phase-wise architecture for a RAG-based chatbot focused on Indian mutual fund schemes, initially sourcing data from `https://www.indmoney.com/`. Deployment is intentionally out of scope for now.

---

## Phase 0 – Foundations & Requirements

**Goals**
- Define functional scope, non-functional requirements, and core tech choices.
- Decide what lives in structured storage vs. RAG.

**Key Decisions**
- **Tech stack (example)**
  - **Backend**: Python (FastAPI) or Node.js (NestJS/Express).
  - **Vector DB**: pgvector, Qdrant, Pinecone, or Weaviate.
  - **Relational DB**: PostgreSQL/MySQL for structured mutual fund data.
  - **LLM**: Grok as the preferred LLM for generation; other models can be used only for utilities like embeddings if needed.
- **Data strategy**
  - **All chatbot answers must be grounded in retrieved content from the embeddings store.** The chatbot must not “invent” answers; it should only summarize or restate information that comes from retrieved chunks (which themselves are created from structured and unstructured data).
  - **Structured data** (NAV/price, lock-in, expense ratio, exit load, min SIP, riskometer, benchmark) is first transformed into textual fact blocks and embedded, so that even attribute-level answers are backed by embeddings.
  - **Unstructured/semi-structured data** (fund descriptions, strategy notes, FAQs, “how to download statements”) → text corpus for vector search (RAG).
- **Compliance**
  - Informational only; no personalized investment advice.
  - Always include disclaimers and data freshness notes.
  - Personal information questions (e.g., about an individual’s PAN, Aadhaar, bank details, or account-level info) are **explicitly out of scope**; such queries must be politely declined.

**Folder**
- `phase-0-foundations/`

---

## Phase 1 – Data Acquisition from indmoney.com (Ingestion Layer)

**Goals**
- Harvest mutual fund data from `https://www.indmoney.com/` and normalize into internal storage.
- Cover all fields needed by the chatbot:
  - Scheme master data (name, AMC, category, plan type, option).
  - NAV/price, lock-in period, expense ratio, exit load, minimum SIP, riskometer, benchmark.
  - Portfolio holdings and allocation.

**Main Components**
- **Ingestion Service**
  - Scrapes or uses available APIs from `indmoney.com` (respecting ToS and robots.txt).
  - Extracts data into **staging tables**, then into normalized relational schema.
  - Handles:
    - Scheme listing discovery (URLs).
    - Detail page parsing.
    - Portfolio/holdings extraction.
  - Implements retry, error logging, and basic validation.

- **Relational Data Model (core tables)**
  - `fund_schemes`  
    - `scheme_id`, `external_id/slug`, `scheme_name`, `amc`, `category`, `sub_category`,  
      `riskometer`, `benchmark`, `lock_in_period_months`, `plan_type`, `option`,  
      `expense_ratio`, `exit_load` (text/JSON), `minimum_sip_amount`, `minimum_lump_sum_amount`,  
      `is_tax_saving`, `last_updated_at`.
  - `fund_nav_history`  
    - `scheme_id`, `date`, `nav`, plus optional `aum`, `return_1y`, `return_3y`, etc.
  - `fund_portfolio_holdings`  
    - `scheme_id`, `holding_name`, `sector`, `asset_class`, `weight_percentage`, optional rating/market-cap.
  - `fund_metadata_text`  
    - `scheme_id`, `source` (objective/description/highlights), `raw_html`, `clean_text`, `last_updated_at`.
  - `faq_texts`  
    - `topic`, `source_url`, `clean_text`, `last_updated_at` for generic FAQs like “how to download statements”.

**Compliance & Scraping Hygiene**
- Honor `robots.txt` and site ToS.
- Apply rate limiting, random delays, and caching of HTML responses.

**Folder**
- `phase-1-data-acquisition/`

---

## Phase 2 – RAG & Knowledge Preparation Layer

**Goals**
- Prepare text data for retrieval-augmented generation.
- Build the vector index over scheme metadata and FAQs.

**Main Components**
- **RAG Preprocessing Service**
  - Reads from `fund_metadata_text`, `faq_texts`, and structured scheme data exported from Phase 1 (e.g., JSONL of schemes and holdings).
  - Cleans HTML and removes boilerplate.
  - Converts structured fields (expense ratio, exit load, minimum SIP, riskometer, benchmark, lock-in, portfolio snapshot, etc.) into **human-readable factual text blocks** that can be embedded and later shown verbatim.
  - Chunks text (e.g., 300–500 tokens with overlap).
  - Enriches chunks with metadata:
    - `scheme_id`, `source` (e.g., `fund_objective`, `indmoney_description`, `download_statement_help`), `source_url`, timestamps.

- **Embedding & Indexing**
  - Uses an embedding model to generate vectors for each chunk.
  - Stores in vector DB with:
    - `chunk_id`, `embedding`, `scheme_id`, metadata (topic, source, URL, etc.).
  - Supports:
    - Filter by `scheme_id` when user references a specific fund.
    - Global search for generic questions (e.g., “what is a riskometer?” or “how to download mutual fund statements?”).

- **Incremental Updates**
  - Each updated `fund_metadata_text` or `faq_texts` row is marked “dirty”.
  - Preprocessor periodically re-embeds dirty rows and upserts them into the vector index.

**Folder**
- `phase-2-rag-preparation/`

---

## Phase 3 – Backend & Frontend Chat Application

**Goals**
- Implement the main chatbot application backend and frontend.
- Expose APIs and UI for interacting with the RAG system and structured data.

### 3.1 Backend (Chat Orchestration Service)

**Responsibilities**
- Expose REST (or GraphQL) endpoints:
  - `POST /chat` – core chat endpoint with conversation history and user query.
  - `GET /funds/{scheme_id}` – raw structured data for debugging/future dashboards.
  - `GET /search-funds` – fund search by name/category.
- Implement:
  - **Intent & Query Analyzer**
    - Classifies query into:
      - `structured_lookup` (expense ratio, exit load, minimum SIP, riskometer, benchmark, lock-in).
      - `portfolio_query` (holdings, sector allocation).
      - `how_to/procedural` (e.g., how to download statements).
      - `comparative` (compare two or more schemes).
      - `general_explanation` (e.g., “what is a riskometer?”).
    - Internally can be heuristic + LLM classifier.
  - **Scheme Resolver**
    - Extracts scheme names from user text.
    - Performs exact or fuzzy matching against `fund_schemes`.
  - **Knowledge Orchestrator**
    - Based on intent:
      - Queries relational DB for structured attributes.
      - Queries vector DB for text chunks (Phase 2).
    - Combines results into a single context object for the LLM.
  - **LLM Response Generator**
    - Constructs prompts with:
      - Retrieved text chunks from the embeddings store (both those generated from structured facts and from unstructured content).
      - System instructions (no investment advice, mention data source and date).
    - Produces final user-facing answer **only by summarizing or quoting retrieved chunks**, never by introducing new facts that are not present in the retrieved context.

### 3.2 Frontend (Chat UI)

**Responsibilities**
- Provide a clean, modern chat interface.
- Allow users to:
  - Ask natural-language questions about mutual funds.
  - Click quick actions like:
    - “Show key metrics for this fund”
    - “Show portfolio holdings”
    - “Compare with another fund”
  - View structured cards for:
    - Expense ratio, exit load, minimum SIP, lock-in, riskometer, benchmark.
    - Top holdings and sector allocation.
- Integrations:
  - Calls backend `/chat` endpoint.
  - May also call `/search-funds` for auto-complete when user starts typing a scheme name.

**Tech stack (example)**
- **Frontend**: React/Next.js, Tailwind or Material UI.
- **State**: React Query/RTK Query to talk to backend.

**Folder**
- `phase-3-app-frontend-backend/`

---

## Phase 4 – Scheduler & Data Refresh Orchestration

**Goals**
- Keep scheme data and RAG index in sync with the latest information from `indmoney.com`.
- Automate periodic ingestion and downstream updates across previous phases.

**Main Components**
- **Scheduler / Orchestrator Service**
  - Runs on a schedule (e.g., cron, Airflow, Prefect).
  - Pipelines:
    - **Daily/Weekly Full Refresh**
      1. Trigger Phase 1 ingestion workflows to fetch latest scheme data, NAV, portfolio, and metadata.
      2. On completion, mark updated records (schemes, metadata, FAQs).
      3. Trigger Phase 2 RAG preprocessing for updated text.
      4. Optionally notify Phase 3 backend (e.g., via cache invalidation or message bus).
    - **Frequent Partial Refresh (NAV-only)**
      - Focused on `fund_nav_history` and any rapidly changing metrics.
  - Maintains a run log:
    - Run ID, start/end timestamps.
    - Counts of new/updated schemes and chunks.
    - Errors for observability.

- **Event Triggers (Optional)**
  - Instead of strictly linear “phase triggers”, use events:
    - `INGESTION_COMPLETED` → consumed by RAG preprocessor.
    - `RAG_INDEX_UPDATED` → consumed by backend for cache refresh.

**Data Flow**
- Phase 4 controls when Phase 1 and Phase 2 run and ensures that Phase 3 always queries the latest data and index.

**Folder**
- `phase-4-scheduler-refresh/`

---

## Phase 5 – Conversation Management & Guardrails

**Goals**
- Maintain conversation context across turns and enforce safety/compliance.

**Main Components**
- **Conversation Store**
  - Persists:
    - `conversation_id`, `user_id`, timestamps.
    - Message history with model metadata.
    - Last referenced `scheme_id`s to resolve pronouns like “it/this fund”.

- **Context Manager**
  - Determines what history to send to the LLM on each turn.
  - Infers implicit fund references when user omits the fund name in follow-up questions.

- **Safety & Compliance Layer**
  - System prompt rules:
    - No personalized investment advice.
    - Do not recommend a “best” or “right” fund to buy.
    - State disclaimers and suggest consulting a qualified advisor.
  - Content classifier:
    - Detects questions like “Which fund should I buy?” or “Guarantee me 15% returns”.
    - Responds with safe templates and high-level, neutral information only.
  - Hallucination control:
    - For numerical data, LLM is instructed to rely strictly on structured DB facts provided in the prompt.
    - If the attribute is missing, the response clearly indicates lack of data.

**Folder**
- `phase-5-conversation-guardrails/`

---

## Phase 6 – Analytics, Monitoring & Continuous Improvement

**Goals**
- Measure usage, quality, and gaps in the chatbot.
- Continuously improve ingestion, RAG coverage, and prompts.

**Main Components**
- **Usage Analytics**
  - Capture:
    - Query text, detected intent, schemes involved.
    - Whether structured data, RAG, or both were used.
    - Answer length, latency, and success flags.
  - Build dashboards (e.g., in Metabase/Grafana) for:
    - Top questions.
    - Coverage gaps (no good answer, missing scheme).

- **Feedback Loop**
  - UI: thumbs up/down or star rating.
  - When feedback is poor:
    - Trigger review pipeline to:
      - Inspect model prompts.
      - Add missing FAQs or clarify content.
      - Refine ingestion rules or RAG chunking.

- **Quality Experiments**
  - A/B testing of prompts or different embedding models.
  - Track impact on answer quality and latency.

**Folder**
- `phase-6-analytics-monitoring/`

---

## Summary of Phase Folders

- `phase-0-foundations/` – Requirements, constraints, and top-level decisions.
- `phase-1-data-acquisition/` – Ingestion from `indmoney.com` into normalized DB.
- `phase-2-rag-preparation/` – Text cleaning, chunking, embedding, and vector index.
- `phase-3-app-frontend-backend/` – Backend APIs and frontend chat UI.
- `phase-4-scheduler-refresh/` – Scheduler to refresh data and re-run pipelines.
- `phase-5-conversation-guardrails/` – Conversation state and safety controls.
- `phase-6-analytics-monitoring/` – Analytics, monitoring, and continuous improvement.

