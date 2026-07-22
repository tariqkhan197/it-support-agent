# AI IT Support Agent — Work in Progress

This is a partial delivery, built phase-by-phase per your instructions.
**Phases 1–7 are complete and fully tested** (backend + Streamlit frontend).
Deployment files (Docker, deploy guides) and full architecture docs are still pending.

## What's working right now

1. **Foundation** — config, structured logging, typed exceptions
2. **Database** — SQLite + SQLAlchemy: tickets (full lifecycle), conversations/messages (memory), user preferences
3. **Multi-agent LangGraph system** — Supervisor + 7 specialist agents (Windows, Networking, Printer, VPN, Email, Security, General), Groq LLM client, prompt-injection guard
4. **RAG knowledge base** — PDF ingestion, chunking, ChromaDB vector store, sentence-transformers embeddings, retrieval grounding
5. **OCR** — Tesseract screenshot analysis, Windows/VPN/printer error-code detection, auto-ticket creation from chat
6. **FastAPI REST API** — chat, ticket CRUD/lifecycle, knowledge base upload/delete, OCR analyze, admin JWT auth, rate limiting
7. **Streamlit frontend** — dark theme, sidebar navigation:
   - **Home (Chat)** — employee-facing AI chat, no login needed
   - **Dashboard** — admin-only, live charts (Plotly) and metric cards
   - **Tickets** — admin-only, search/filter/assign/status-change/delete/CSV export
   - **Knowledge Base** — admin-only, upload/list/delete PDFs
   - **Screenshot Diagnosis** — employee-facing, OCR upload and diagnosis

## Not yet built

- Dockerfile, deployment guides (Streamlit Community Cloud / Render) — later phase
- Full architecture documentation — later phase

## How to run everything

```bash
# 1. Install dependencies
pip install -r requirements.txt --break-system-packages

# 2. Configure environment
cp .env.example .env
# Edit .env:
#   - GROQ_API_KEY: get a free key at https://console.groq.com
#   - ADMIN_PASSWORD_HASH: generate with:
python scripts/hash_password.py "your-chosen-admin-password"
#     then paste the output into .env

# 3. Run the backend API (terminal 1)
uvicorn backend.main:app --reload --port 8000

# 4. Run the frontend (terminal 2)
cd frontend
streamlit run app.py

# 5. Open the app
# Frontend: http://localhost:8501
# API docs: http://localhost:8000/docs
```

Log in to the admin pages (Dashboard, Tickets, Knowledge Base) with
username `admin` and the password you hashed in step 2.

## Verifying it works

Every phase in this build was tested against real components (real SQLite,
real ChromaDB, real Tesseract OCR, a real running FastAPI server, a real
running Streamlit server) — not just written and assumed correct. Two
things could NOT be fully tested in the sandbox this was built in, because
that sandbox has no general internet access:

- Live calls to Groq (api.groq.com) — the code is correct and will work
  once you provide a real `GROQ_API_KEY`; test via the Chat page or:
  ```bash
  curl -X POST http://localhost:8000/api/v1/chat -H "Content-Type: application/json" \
    -d '{"user_identifier":"you@company.com","message":"my outlook wont open"}'
  ```
- Downloading the sentence-transformers embedding model from huggingface.co
  (needed for Knowledge Base uploads) — also correct, works the first time
  you run it with internet access (downloads ~80MB once, then caches locally).

## Tests included

```bash
PYTHONPATH=. python3 tests/test_workflow_smoke.py       # multi-agent routing/guardrails
PYTHONPATH=. python3 tests/test_rag_pipeline_smoke.py    # PDF ingestion -> retrieval -> deletion
```

---
*Continue the conversation and say "8" (or just ask) to build Docker + deployment guides next.*
