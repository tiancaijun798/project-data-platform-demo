#!/usr/bin/env python3
"""
rag_server.py — FastAPI RAG (Retrieval Augmented Generation) server.

Loads a FAISS knowledge base at startup and exposes endpoints for:
    - Semantic document retrieval (retrieve-only mode)
    - Prompt construction for downstream LLMs (prompt-builder mode)
    - Health check

Endpoints:
    POST /rag/query   — Retrieve relevant docs + optional LLM-ready prompt
    GET  /rag/health  — Service health & index status

Usage:
    # 1. Build the knowledge base first
    python build_knowledge_base.py

    # 2. Start the RAG server
    uvicorn rag_server:app --host 0.0.0.0 --port 8002

    # Or with reload during development
    uvicorn rag_server:app --host 0.0.0.0 --port 8002 --reload
"""

import json
import os
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Fix Windows console encoding for emoji/Unicode output
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Configuration (all via environment variables)
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_INDEX_DIR = SCRIPT_DIR / "knowledge_base"

INDEX_PATH = Path(os.getenv("RAG_INDEX_PATH", DEFAULT_INDEX_DIR / "index.faiss"))
META_PATH = Path(os.getenv("RAG_META_PATH", DEFAULT_INDEX_DIR / "metadata.json"))
EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2"
)
DEFAULT_TOP_K = int(os.getenv("RAG_DEFAULT_TOP_K", "5"))
MAX_TOP_K = int(os.getenv("RAG_MAX_TOP_K", "50"))
SERVER_PORT = int(os.getenv("RAG_SERVER_PORT", "8002"))

# ---------------------------------------------------------------------------
# Global state — loaded at startup
# ---------------------------------------------------------------------------
model = None       # SentenceTransformer
index = None       # FAISS index
metadata = None    # list[dict] — document metadata keyed by FAISS internal id
meta_lookup = None # dict[int, dict] — fast id-based lookup

# ---------------------------------------------------------------------------
# Startup / shutdown
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load the embedding model, FAISS index, and metadata at startup."""
    global model, index, metadata, meta_lookup

    import faiss
    from sentence_transformers import SentenceTransformer

    print("=" * 50)
    print("  🚀 Starting RAG Server")
    print("=" * 50)

    # 1. Load embedding model
    print(f"  🤖 Loading model: {EMBEDDING_MODEL}")
    model = SentenceTransformer(EMBEDDING_MODEL)
    dim = model.get_sentence_embedding_dimension()
    print(f"     Dimension: {dim}")

    # 2. Load FAISS index
    if INDEX_PATH.exists():
        print(f"  🔍 Loading FAISS index: {INDEX_PATH}")
        index = faiss.read_index(str(INDEX_PATH))
        print(f"     Vectors: {index.ntotal}, dim={index.d}")
    else:
        print(f"  ⚠️  FAISS index not found at {INDEX_PATH}")
        print(f"     Run 'python build_knowledge_base.py' first to create it.")

    # 3. Load metadata
    if META_PATH.exists():
        print(f"  📋 Loading metadata: {META_PATH}")
        with open(META_PATH, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        meta_lookup = {m["id"]: m for m in metadata}
        print(f"     {len(metadata)} documents loaded")
    else:
        print(f"  ⚠️  Metadata not found at {META_PATH}")

    if index is not None and metadata is not None:
        print(f"  ✅ RAG server ready — {index.ntotal} documents indexed")
    else:
        print(f"  ⚠️  RAG server started in degraded mode (no index/metadata)")

    yield

    # Cleanup
    print("  👋 RAG server shutting down")


# ── FastAPI app ──────────────────────────────────────────────────────
app = FastAPI(
    title="Data Platform — RAG Demo API",
    version="0.3.0",
    description=(
        "Retrieval-Augmented Generation demo on top of Parquet/dbt data. "
        "Supports retrieve-only mode and prompt-builder mode."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Pydantic models ──────────────────────────────────────────────────
class RAGQueryRequest(BaseModel):
    """Request body for /rag/query."""

    query: str = Field(
        ...,
        description="Natural language question, e.g. 'Which users purchased "
                    "via mobile Chrome?'",
        min_length=1,
        max_length=500,
        examples=["Which users purchased via mobile Chrome?"],
    )
    top_k: int = Field(
        DEFAULT_TOP_K,
        ge=1,
        le=MAX_TOP_K,
        description="Number of documents to retrieve",
    )
    mode: str = Field(
        "retrieve-only",
        description="'retrieve-only' returns just the relevant docs. "
                    "'prompt-builder' also constructs a full prompt for an LLM.",
        pattern="^(retrieve-only|prompt-builder)$",
    )
    system_prompt: Optional[str] = Field(
        None,
        description="Custom system prompt for prompt-builder mode. "
                    "If not provided, a default analytics-focused prompt is used.",
    )


class RetrievedDoc(BaseModel):
    """A single retrieved document with relevance score."""

    id: int
    score: float
    event_type: str
    user_id: str
    product_id: str
    chunk: str
    metadata: dict


class RAGQueryResponse(BaseModel):
    """Response from /rag/query."""

    query: str
    mode: str
    retrieved_docs: list[RetrievedDoc]
    prompt: Optional[str] = None
    elapsed_ms: float
    total_in_index: int


# ── Helper functions ─────────────────────────────────────────────────
def encode_query(query: str) -> np.ndarray:
    """Encode a natural-language query into a normalized embedding vector."""
    if model is None:
        raise HTTPException(status_code=503, detail="Embedding model not loaded")
    vec = model.encode([query], normalize_embeddings=True)
    return vec.astype(np.float32)


def retrieve(query: str, top_k: int) -> list[dict]:
    """Retrieve the top-k most semantically relevant documents.

    Returns a list of dicts with keys: id, score, chunk, and all metadata fields.
    """
    if index is None:
        raise HTTPException(
            status_code=503,
            detail="FAISS index not loaded. Run 'python build_knowledge_base.py' first.",
        )
    if meta_lookup is None:
        raise HTTPException(
            status_code=503,
            detail="Metadata not loaded. Run 'python build_knowledge_base.py' first.",
        )

    q_vec = encode_query(query)
    distances, ids = index.search(q_vec, top_k)

    results = []
    for doc_id, score in zip(ids[0], distances[0]):
        if doc_id < 0:  # FAISS returns -1 for empty slots
            continue
        meta = meta_lookup.get(int(doc_id), {})
        results.append({
            "id": int(doc_id),
            "score": round(float(score), 4),
            "event_type": meta.get("event_type", "?"),
            "user_id": meta.get("user_id", "?"),
            "product_id": meta.get("product_id", ""),
            "chunk": meta.get("chunk", ""),
            "metadata": {
                k: v for k, v in meta.items()
                if k not in ("id", "chunk")
            },
        })

    return results


def build_prompt(query: str, docs: list[dict],
                 system_prompt: Optional[str] = None) -> str:
    """Construct a ready-to-use prompt for an LLM by combining
    context (retrieved docs) with the user query.

    The prompt follows the standard RAG template:
        [System instruction]
        [Context from retrieved documents]
        [User question]
    """
    if system_prompt is None:
        system_prompt = (
            "You are a data analytics assistant. "
            "Use the retrieved user event data below to answer the user's question. "
            "If the data does not contain enough information, say so clearly. "
            "Provide specific user IDs, event types, and patterns where possible."
        )

    # Build context block from top docs
    context_entries = []
    for i, doc in enumerate(docs, 1):
        entry = (
            f"{i}. [Event: {doc['event_type']} | "
            f"User: {doc['user_id']} | "
            f"Product: {doc['product_id'] or 'N/A'}]\n"
            f"   {doc['chunk']}"
        )
        context_entries.append(entry)

    context_block = "\n".join(context_entries)

    prompt = f"""{system_prompt}

## Context (retrieved from data platform)
{context_block}

## User Question
{query}

## Answer
"""
    return prompt.strip()


# ── Endpoints ────────────────────────────────────────────────────────
@app.get("/rag/health")
async def health():
    """Health check — reports index status and configuration."""
    return {
        "status": "healthy" if index is not None else "degraded",
        "index_loaded": index is not None,
        "metadata_loaded": metadata is not None,
        "vectors_in_index": index.ntotal if index else 0,
        "vector_dimension": index.d if index else 0,
        "embedding_model": EMBEDDING_MODEL,
        "default_top_k": DEFAULT_TOP_K,
    }


@app.post("/rag/query", response_model=RAGQueryResponse)
async def rag_query(body: RAGQueryRequest):
    """Retrieve relevant documents for a natural-language query.

    Two modes:
    - **retrieve-only**: Returns the top-k most relevant documents
      from the knowledge base (FAISS index).
    - **prompt-builder**: Also constructs a full prompt with context
      that can be sent directly to an LLM (e.g., Claude, GPT).
    """
    t0 = time.time()

    # Retrieve
    docs = retrieve(body.query, body.top_k)
    elapsed_ms = round((time.time() - t0) * 1000, 1)

    # Build prompt if requested
    prompt = None
    if body.mode == "prompt-builder":
        prompt = build_prompt(body.query, docs, body.system_prompt)

    return RAGQueryResponse(
        query=body.query,
        mode=body.mode,
        retrieved_docs=[RetrievedDoc(**d) for d in docs],
        prompt=prompt,
        elapsed_ms=elapsed_ms,
        total_in_index=index.ntotal if index else 0,
    )


# ── Direct run ───────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    print(f"Starting RAG server on port {SERVER_PORT}...")
    print(f"API docs: http://localhost:{SERVER_PORT}/docs")
    uvicorn.run(app, host="0.0.0.0", port=SERVER_PORT)
