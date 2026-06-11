"""AI Workbench — FastAPI application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import router
from src.storage.database import init_db
from src.utils.config import load_config


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database and config on startup."""
    load_config()
    init_db()
    yield


app = FastAPI(
    title="AI Workbench",
    description="Local multi-agent development orchestrator",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
