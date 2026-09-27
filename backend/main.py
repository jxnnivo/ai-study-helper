"""
FastAPI application entry point.

Goal: wire together the upload, query, and quiz routers into one app, with
CORS enabled so the React/Vite frontend can call it during local
development. This file stays thin — app setup only, no business logic —
per the project's own routers/services/main separation.

NOTE: if you already have content in main.py (app-level exception
handlers, other routers, startup events), merge this in rather than
replacing the whole file — the pieces that matter are load_dotenv(), the
CORSMiddleware block, and the three include_router() calls.
"""

from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()  # makes GROQ_API_KEY (and anything else in .env) available
# before any request handler runs

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import quiz, query, upload

app = FastAPI(title="RAG Study Notes Assistant")

# Vite's default dev server runs on 5173. Add any other frontend origins
# here (e.g. a deployed URL) as the project grows -- CORS is an allowlist,
# not a wildcard, so every origin that needs to call this API must be
# listed explicitly.
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router)
app.include_router(query.router)
app.include_router(quiz.router)


@app.get("/")
async def health_check() -> dict:
    """Liveness check — hit this first when debugging to confirm the
    server itself is up before chasing a specific endpoint."""
    return {"status": "ok", "service": "rag-study-assistant-backend"}
