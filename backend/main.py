"""
InfoSec Questionnaire AI Agent - FastAPI Backend
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(override=True)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import documents, questionnaire

BASE_DIR = Path(__file__).parent
for d in ["uploads", "exports"]:
    (BASE_DIR / "data" / d).mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="InfoSec Questionnaire AI Agent",
    description="AI-powered agent that answers InfoSec questionnaires using your knowledge base",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:5174").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents.router, prefix="/api/documents", tags=["Documents"])
app.include_router(questionnaire.router, prefix="/api/questionnaire", tags=["Questionnaire"])


@app.get("/api/health")
async def health_check():
    from services.rag_engine import get_usage_stats, get_provider_info
    usage = get_usage_stats()
    providers = get_provider_info()
    primary = providers[0] if providers else None
    return {
        "status": "healthy",
        "provider": primary["name"] if primary else "none",
        "model": primary["model"] if primary else "none",
        "embeddings": os.getenv("EMBEDDING_PROVIDER", "local"),
        "providers": providers,
        "usage": {
            "requests_today": usage["requests"],
            "tokens_today": usage["tokens"],
            "cost_usd": round(usage["cost"], 6),
            "last_provider": usage["last_provider"],
            "limit_rpd": primary["free_rpd"] if primary else 0,
            "limit_tpm": primary["free_tpm"] if primary else 0,
        },
    }
