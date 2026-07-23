# 🤖 AI IT Support Agent

A full-stack, multi-agent AI IT Support System built with **FastAPI**, **LangGraph**, **ChromaDB**, and **Streamlit**. Designed for automated ticket handling, intelligent troubleshooting, OCR error screenshot diagnosis, and admin workflow management.

---

## 🌟 Features Overview

* **Multi-Agent Orchestration (LangGraph):** Supervisor routing system managing 7 specialist agents (*Windows, Networking, Printer, VPN, Email, Security, General*).
* **RAG Knowledge Base:** PDF ingestion, chunking, and similarity search powered by `ChromaDB` and `sentence-transformers`.
* **OCR Screenshot Diagnosis:** Automated error extraction from uploaded screenshots using Tesseract OCR.
* **REST API:** Robust `FastAPI` backend with JWT authentication, rate-limiting, and complete ticket lifecycle management.
* **Interactive Frontend:** Responsive `Streamlit` dashboard featuring real-time Plotly charts, ticket filtering, CSV exporting, and public chat interface.

---

## 🚀 Status & Deliverables

### ✅ Completed & Tested (Phases 1–7)

1. **Foundation:** Structured logging, custom Exception handling, unified config management.
2. **Database:** SQLite + SQLAlchemy setup for Ticket lifecycles, Chat history memory, and User preferences.
3. **Multi-Agent Core:** LangGraph-driven routing with Groq LLM integration and prompt-injection guardrails.
4. **RAG Pipeline:** Document chunking, vector embedding, and similarity retrieval.
5. **OCR Integration:** Error code parsing from images to trigger automated ticket workflows.
6. **Backend API:** Complete REST endpoints for Chat, Knowledge Base, Admin Auth, and Ticket CRUD.
7. **Streamlit Application:** Dark-themed multi-page user interface (Home Chat, Admin Dashboard, Ticket Manager, Knowledge Base, Screenshot Diagnosis).

---

## 🛠️ Setup & Local Installation

### Prerequisites

* Python **3.10+** (Recommended: Python 3.13)
* Tesseract OCR installed on the host system (for screenshot parsing)

### 1. Repository Setup

```bash
cd it-support-agent
