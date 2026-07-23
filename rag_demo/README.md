# RAG Retrieval-Augmented Generation Demo

> Built on FAISS + sentence-transformers. Converts Parquet/dbt event data into
> a semantic knowledge base and exposes a FastAPI endpoint for retrieval and
> prompt construction.

---

## Architecture

```
┌──────────────────┐     ┌──────────────────────┐     ┌────────────────────┐
│  Parquet / dbt   │────▶│  build_knowledge_base │────▶│  FAISS Index       │
│  event data      │     │  - Chunking           │     │  (index.faiss)     │
│  (or synthetic)  │     │  - Embedding (384d)   │     │  + metadata.json   │
└──────────────────┘     └──────────────────────┘     └─────────┬──────────┘
                                                                │
                                                     ┌──────────▼──────────┐
  ┌──────────────┐                                    │  rag_server.py      │
  │  LLM / Chat  │◀──── Prompt ──────────────────────│  - /rag/query       │
  │  (external)  │                                    │  - /rag/health      │
  └──────────────┘                                    └─────────────────────┘
```

---

## Quick Start

### 1. Install dependencies

```bash
cd rag_demo
pip install -r requirements.txt
```

### 2. Build the knowledge base

```bash
# Auto-detects Parquet files, falls back to synthetic data
python build_knowledge_base.py

# Full options
python build_knowledge_base.py \
    --parquet-dir ../data/output_parquet \
    --sample-size 3000 \
    --benchmark
```

Output files:
- `knowledge_base/index.faiss` — FAISS index (IndexIDMap + IndexFlatIP)
- `knowledge_base/metadata.json` — Document chunks + metadata

### 3. Start the RAG server

```bash
uvicorn rag_server:app --host 0.0.0.0 --port 8002
```

Open http://localhost:8002/docs for interactive API docs.

### 4. Query the RAG

```bash
# Retrieve-only mode — just get relevant docs
curl -X POST http://localhost:8002/rag/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Which users purchased via mobile Chrome?",
    "top_k": 5,
    "mode": "retrieve-only"
  }'

# Prompt-builder mode — get docs + LLM-ready prompt
curl -X POST http://localhost:8002/rag/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What products are most popular on tablet devices?",
    "top_k": 5,
    "mode": "prompt-builder"
  }'
```

---

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/rag/health` | Health check — index status, vector count |
| `POST` | `/rag/query` | Retrieve docs + optional LLM prompt |

### `POST /rag/query` request body

```json
{
  "query": "Which users purchased via mobile Chrome?",
  "top_k": 5,
  "mode": "retrieve-only | prompt-builder",
  "system_prompt": "Optional custom system prompt"
}
```

### Response (retrieve-only mode)

```json
{
  "query": "...",
  "mode": "retrieve-only",
  "retrieved_docs": [
    {
      "id": 42,
      "score": 0.8921,
      "event_type": "purchase",
      "user_id": "U0015",
      "product_id": "P0123",
      "chunk": "User U0015 performed purchase on product P0123 via mobile Chrome...",
      "metadata": { "page": "checkout", "referrer": "google", ... }
    }
  ],
  "prompt": null,
  "elapsed_ms": 12.5,
  "total_in_index": 3000
}
```

### Response (prompt-builder mode)

Same as above, but `prompt` contains a fully constructed prompt string
with system instructions, context from retrieved docs, and the user question,
ready to be sent to any LLM.

---

## Performance Metrics

| Metric | Value |
|--------|-------|
| Embedding Model | `paraphrase-multilingual-MiniLM-L12-v2` |
| Vector Dimension | 384 |
| FAISS Index Type | IndexIDMap(IndexFlatIP) |
| Distance Metric | Inner Product (cosine similarity after L2 normalization) |
| Index Build Time | ~2-5s for 10K chunks (CPU) |
| Encoding Throughput | ~800-1500 chunks/s (CPU) |
| Average Retrieval Latency (top-10) | ~5-15 ms (in-memory FAISS) |
| Chunk Size | ~50-200 characters |
| Document Sources | Parquet (preferred) or synthetic fallback |

### Benchmark Results (sample)

The built-in benchmark (`--benchmark` flag) runs 8 diverse test queries and
reports:

- **Per-query latency**: Typically 3-15 ms
- **Top-5 hit rate**: The percentage of queries where the expected event type
  appears in the top-5 results
- **Recommended top_k**: 5 for prompt-building (keeps context manageable)

---

## Technical Decisions

**Why FAISS instead of Milvus?**
FAISS is lighter weight for a demo — no Docker required, index is a single
file on disk, sub-10ms latency is easy to achieve on CPU with <10K vectors.

**Why MiniLM-L12-v2?**
384-dimensional multilingual model. Supports both English and Chinese queries.
Small enough to run on CPU without GPU acceleration. Widely used in production.

**Why IndexFlatIP + L2 normalization?**
`IndexFlatIP` with L2-normalized vectors gives exact nearest-neighbor results
(no approximation). For <50K vectors this is fast enough. Larger datasets
would benefit from `IndexIVFFlat` or `IndexHNSW`.

**Chunking strategy:**
Each event row becomes a single natural-language sentence (~50-200 chars).
This keeps chunks atomic and makes retrieval intuitive. For real production
use, sliding-window or semantic chunking would be appropriate.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "FAISS index not loaded" | Run `python build_knowledge_base.py` first |
| "No module named 'faiss'" | `pip install faiss-cpu` |
| Slow encoding | Reduce `--sample-size`, or set `device='cuda'` if GPU available |
| Memory error | FAISS FlatIP stores all vectors in memory; reduce sample size |
