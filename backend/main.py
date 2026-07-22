"""
FastAPI application entrypoint.

Wires together configuration, logging, database initialization, and every
API router: auth, chat, tickets, knowledge base, and OCR.

Run locally with:
    uvicorn backend.main:app --reload --port 8000
"""

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api.routes_auth import router as auth_router
from backend.api.routes_chat import router as chat_router
from backend.api.routes_knowledge import router as knowledge_router
from backend.api.routes_ocr import router as ocr_router
from backend.api.routes_tickets import router as tickets_router
from backend.config.settings import get_settings
from backend.database.session import init_db
from backend.utils.exceptions import (
    AgentRoutingError,
    AuthenticationError,
    DatabaseError,
    DocumentProcessingError,
    FileValidationError,
    ITSupportAgentError,
    LLMProviderError,
    OCRProcessingError,
    PromptInjectionDetectedError,
    RateLimitExceededError,
    TicketNotFoundError,
    TicketValidationError,
)
from backend.utils.logger import get_logger, request_logger

settings = get_settings()
logger = get_logger(__name__)

# Map specific exception types to the HTTP status code they should produce.
# Anything not listed here falls back to 400 (bad request) since our
# exception hierarchy is generally raised for client-caused problems;
# true unexpected server failures surface as unhandled exceptions (500).
_EXCEPTION_STATUS_MAP: dict[type[ITSupportAgentError], int] = {
    TicketNotFoundError: 404,
    TicketValidationError: 400,
    FileValidationError: 400,
    PromptInjectionDetectedError: 400,
    AuthenticationError: 401,
    RateLimitExceededError: 429,
    LLMProviderError: 502,
    DocumentProcessingError: 502,
    OCRProcessingError: 502,
    AgentRoutingError: 502,
    DatabaseError: 500,
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup/shutdown hooks."""
    logger.info(
        "Starting %s in %s mode (debug=%s)",
        settings.APP_NAME,
        settings.ENVIRONMENT,
        settings.DEBUG,
    )
    init_db()
    if not settings.GROQ_API_KEY:
        logger.warning(
            "GROQ_API_KEY is not set. Chat/agent endpoints will fail until "
            "it is configured in .env (see .env.example)."
        )
    if not settings.ADMIN_PASSWORD_HASH:
        logger.warning(
            "ADMIN_PASSWORD_HASH is not set. Admin login is disabled until "
            "you generate one with scripts/hash_password.py."
        )
    yield
    logger.info("Shutting down %s", settings.APP_NAME)


app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    description="Enterprise-style AI IT Support Agent — chat, RAG knowledge base, "
    "ticketing, OCR, and a multi-agent LangGraph backend.",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log every request/response with latency, and audit to requests.log."""
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000

    request_logger.log(
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=round(duration_ms, 2),
        client=request.client.host if request.client else None,
    )
    logger.info(
        "%s %s -> %s (%.2f ms)",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


@app.exception_handler(ITSupportAgentError)
async def handle_app_error(request: Request, exc: ITSupportAgentError) -> JSONResponse:
    """Translate our internal exception hierarchy into clean JSON error responses with correct status codes."""
    status_code = _EXCEPTION_STATUS_MAP.get(type(exc), 400)
    log_fn = logger.error if status_code >= 500 else logger.warning
    log_fn("Handled application error on %s [%d]: %s", request.url.path, status_code, exc.message)
    return JSONResponse(
        status_code=status_code,
        content={"error": exc.__class__.__name__, "message": exc.message, "details": exc.details},
    )


app.include_router(auth_router, prefix=settings.API_PREFIX)
app.include_router(chat_router, prefix=settings.API_PREFIX)
app.include_router(tickets_router, prefix=settings.API_PREFIX)
app.include_router(knowledge_router, prefix=settings.API_PREFIX)
app.include_router(ocr_router, prefix=settings.API_PREFIX)


@app.get("/health", tags=["System"])
async def health_check() -> dict:
    """Simple liveness/readiness probe used by Docker/Render/monitoring."""
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "environment": settings.ENVIRONMENT,
        "groq_configured": bool(settings.GROQ_API_KEY),
        "admin_configured": bool(settings.ADMIN_PASSWORD_HASH),
    }


@app.get("/", tags=["System"])
async def root() -> dict:
    return {
        "message": f"{settings.APP_NAME} API is running.",
        "docs": "/docs",
        "health": "/health",
        "api_prefix": settings.API_PREFIX,
    }
# Startup event par automatically admin user banaye ga
@app.on_event("startup")
def create_default_admin():
    try:
        from database import SessionLocal
        from models.auth import User
        from api.auth_utils import get_password_hash
        
        db = SessionLocal()
        # Check karein ke admin user pehle se hai ya nahi
        existing_admin = db.query(User).filter(User.username == "admin").first()
        
        if not existing_admin:
            hashed_pwd = get_password_hash("admin123")
            admin_user = User(username="admin", password_hash=hashed_pwd, role="admin")
            db.add(admin_user)
            db.commit()
            print(">>> SUCCESS: Default admin user created (admin / admin123) <<<")
        else:
            print(">>> Admin user already exists <<<")
            
        db.close()
    except Exception as e:
        print(f">>> Could not create admin on startup: {e} <<<")