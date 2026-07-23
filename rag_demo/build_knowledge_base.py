#!/usr/bin/env python3
"""
build_knowledge_base.py — Build a local FAISS knowledge base from the data platform.

Sources (auto-detected, in order of priority):
    1. Parquet files in ../data/output_parquet/
    2. Synthetic demo data (fallback — always works without dependencies)

Process:
    1. Read event rows (from Parquet or synthetic generator)
    2. Convert each row into a ~50-200 character natural-language chunk
    3. Encode chunks with sentence-transformers (MiniLM-L12-v2, 384d)
    4. Build a FAISS IndexIDMap(IndexFlatIP) with L2-normalized vectors
    5. Save index to disk (.faiss) + metadata (.json)
    6. Run a retrieval benchmark

Output:
    rag_demo/knowledge_base/index.faiss   — FAISS index file
    rag_demo/knowledge_base/metadata.json — document text + metadata

Usage:
    python build_knowledge_base.py
    python build_knowledge_base.py --parquet-dir ../data/output_parquet
    python build_knowledge_base.py --sample-size 2000 --benchmark
"""

import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Optional

import numpy as np

# Fix Windows console encoding for emoji/Unicode output
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DEFAULT_PARQUET_DIR = PROJECT_ROOT / "data" / "output_parquet"
DEFAULT_OUTPUT_DIR = SCRIPT_DIR / "knowledge_base"


# ---------------------------------------------------------------------------
# 1.  Synthetic data generator (fallback)
# ---------------------------------------------------------------------------
def generate_synthetic_events(n: int = 1500) -> list[dict]:
    """Generate realistic-looking synthetic user events for the fallback path.

    The distribution matches the real data generator in scripts/generate_real_data.py.
    """
    import random
    random.seed(42)

    event_types = ["view", "click", "search", "add_to_cart", "purchase", "logout"]
    event_weights = [0.40, 0.25, 0.15, 0.10, 0.06, 0.04]
    devices = ["desktop", "mobile", "tablet"]
    device_weights = [0.35, 0.50, 0.15]
    browsers = ["Chrome", "Safari", "Edge", "Firefox"]
    browser_weights = [0.55, 0.22, 0.13, 0.10]
    referrers = ["direct", "google", "wechat", "facebook", "twitter", "email"]
    referrer_weights = [0.35, 0.30, 0.15, 0.10, 0.05, 0.05]
    pages = ["home", "product_detail", "search_results", "cart", "checkout", "profile"]
    categories = ["Electronics", "Clothing", "Food", "Home", "Sports", "Books", "Beauty"]

    events = []
    for i in range(n):
        et = random.choices(event_types, weights=event_weights)[0]
        events.append({
            "event_id": str(uuid.uuid4()),
            "user_id": f"U{random.randint(1, 500):04d}",
            "event_type": et,
            "product_id": f"P{random.randint(1, 300):04d}" if random.random() < 0.7 else None,
            "product_category": random.choice(categories) if random.random() < 0.7 else None,
            "timestamp": f"2026-07-{random.randint(1,28):02d}T{random.randint(0,23):02d}:{random.randint(0,59):02d}:{random.randint(0,59):02d}",
            "page": random.choice(pages),
            "referrer": random.choices(referrers, weights=referrer_weights)[0],
            "device": random.choices(devices, weights=device_weights)[0],
            "browser": random.choices(browsers, weights=browser_weights)[0],
            "duration_ms": random.randint(100, 120000) if et in ("view", "click", "search") else 0,
        })

    random.shuffle(events)
    return events


# ---------------------------------------------------------------------------
# 2.  Read Parquet data
# ---------------------------------------------------------------------------
def read_parquet_events(parquet_dir: Path, max_rows: int = 5000) -> list[dict]:
    """Read event records from a directory of Parquet files.

    Returns a list of dicts, or an empty list if no Parquet files are found.
    """
    if not parquet_dir.exists():
        print(f"[INFO]  Parquet directory not found: {parquet_dir}")
        return []

    # Collect all .parquet files
    pq_files = []
    for root, _dirs, files in os.walk(parquet_dir):
        for f in files:
            if f.endswith(".parquet"):
                pq_files.append(os.path.join(root, f))

    if not pq_files:
        print(f"[INFO]  No .parquet files found in {parquet_dir}")
        return []

    # Read and concat
    import pandas as pd
    import pyarrow.parquet as pq

    dfs = []
    for fp in pq_files:
        try:
            tbl = pq.read_table(fp)
            df = tbl.to_pandas()
            dfs.append(df)
        except Exception as exc:
            print(f"[WARN]  Skipping {fp}: {exc}")

    if not dfs:
        return []

    df = pd.concat(dfs, ignore_index=True)
    if len(df) > max_rows:
        df = df.sample(n=max_rows, random_state=42)
        print(f"[INFO]  Sampled {max_rows} rows from {len(df)} total")

    records = []
    for _, row in df.iterrows():
        d = row.to_dict()
        # Normalize keys: the Parquet may have snake_case or camelCase
        record = {}
        for key, val in d.items():
            if isinstance(val, float) and np.isnan(val):
                val = None
            record[key.lower()] = val
        records.append(record)

    return records


# ---------------------------------------------------------------------------
# 3.  Chunking — convert event row to natural-language text
# ---------------------------------------------------------------------------
def row_to_chunk(row: dict) -> str:
    """Convert a single event row into a ~50-200 char natural-language chunk.

    Format: "User {uid} performed {event_type} on product {pid} from {referrer}
    via {device} {browser}"

    This produces semantically searchable text that a multilingual embedding
    model can encode meaningfully.
    """
    uid = row.get("user_id", "?")
    event = row.get("event_type", "?")
    pid = row.get("product_id")
    ref = row.get("referrer", "direct")
    dev = row.get("device", "")
    brw = row.get("browser", "")
    page = row.get("page", "")
    dur = row.get("duration_ms")
    cat = row.get("product_category", "")

    parts = [f"User {uid} performed {event}"]

    if pid and str(pid) not in ("None", "nan", "unknown", ""):
        parts.append(f"on product {pid}")

    if cat and str(cat) not in ("None", "nan", ""):
        parts.append(f"(category: {cat})")

    if ref and str(ref) not in ("None", "nan", "direct", ""):
        parts.append(f"from {ref}")

    if page and str(page) not in ("None", "nan", ""):
        parts.append(f"on page {page}")

    if dev or brw:
        dev_str = f" {dev}" if dev else ""
        brw_str = f" {brw}" if brw else ""
        parts.append(f"via{dev_str}{brw_str}")

    if dur and dur > 0:
        parts.append(f"duration {dur}ms")

    return " ".join(parts)


# ---------------------------------------------------------------------------
# 4.  FAISS index build + save
# ---------------------------------------------------------------------------
def build_faiss_index(
    chunks: list[str],
    metadata: list[dict],
    model,
    output_dir: Path,
) -> dict:
    """Encode chunks, build a FAISS index, and save everything to disk.

    Returns a stats dict with timing and size information.
    """
    import faiss

    output_dir.mkdir(parents=True, exist_ok=True)

    total = len(chunks)
    print(f"\n  📝 {total} chunks ready for embedding")

    # Encode with progress indication
    print(f"  🧮 Encoding with sentence-transformers...")
    t0 = time.time()
    embeddings = model.encode(
        chunks,
        batch_size=128,
        show_progress_bar=True,
        normalize_embeddings=True,  # L2-normalize => inner product = cosine sim
    )
    encode_time = time.time() - t0
    print(f"     Encoded {total} chunks in {encode_time:.2f}s "
          f"({total / encode_time:.0f} chunks/s)")

    dim = embeddings.shape[1]
    print(f"     Vector dimension: {dim}")

    # Build FAISS index: IndexIDMap wrapping IndexFlatIP
    print(f"  🔍 Building FAISS IndexIDMap(IndexFlatIP)...")
    t0 = time.time()
    base_index = faiss.IndexFlatIP(dim)
    index = faiss.IndexIDMap(base_index)

    # Assign sequential IDs (int64)
    ids = np.arange(total, dtype=np.int64)
    index.add_with_ids(embeddings.astype(np.float32), ids)
    build_time = time.time() - t0
    print(f"     Index built in {build_time:.2f}s ({index.ntotal} vectors)")

    # Save index
    index_path = output_dir / "index.faiss"
    meta_path = output_dir / "metadata.json"

    faiss.write_index(index, str(index_path))
    print(f"  💾 FAISS index saved → {index_path} "
          f"({os.path.getsize(index_path) / 1024:.1f} KB)")

    # Save metadata
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    print(f"  💾 Metadata saved → {meta_path} "
          f"({os.path.getsize(meta_path) / 1024:.1f} KB)")

    return {
        "total_vectors": index.ntotal,
        "vector_dim": dim,
        "encode_time_s": round(encode_time, 2),
        "encode_speed": round(total / encode_time, 0),
        "build_time_s": round(build_time, 2),
        "index_size_kb": round(os.path.getsize(index_path) / 1024, 1),
        "metadata_size_kb": round(os.path.getsize(meta_path) / 1024, 1),
    }


# ---------------------------------------------------------------------------
# 5.  Retrieval benchmark
# ---------------------------------------------------------------------------
def run_benchmark(output_dir: Path):
    """Load the FAISS index and run a retrieval latency benchmark."""
    import faiss
    from sentence_transformers import SentenceTransformer

    index_path = output_dir / "index.faiss"
    meta_path = output_dir / "metadata.json"

    if not index_path.exists():
        print("[SKIP] No FAISS index found for benchmark")
        return

    print(f"\n{'='*50}")
    print("  📊 Retrieval Latency Benchmark")
    print(f"{'='*50}")

    model_name = os.getenv(
        "EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2"
    )
    model = SentenceTransformer(model_name)
    index = faiss.read_index(str(index_path))
    print(f"  Index: {index.ntotal} vectors, dim={index.d}")

    test_queries = [
        "Which users purchased products via mobile Chrome?",
        "Find purchase events from google search traffic",
        "Users who added items to cart but did not buy",
        "High-value users with many page views",
        "Search events on product detail pages",
        "Desktop users clicking from email campaigns",
        "What products are most viewed on tablet devices?",
        "Find add_to_cart events from wechat referrals",
    ]

    print(f"\n  {'#':<3s} {'Query':<55s} {'Top-1':<15s} {'Latency(ms)':<12s} {'Top-5':<10s}")
    print(f"  {'-'*3} {'-'*55} {'-'*15} {'-'*12} {'-'*10}")

    total_latency = 0
    top5_hit_rates = []

    for i, query in enumerate(test_queries, 1):
        # Encode query
        q_vec = model.encode([query], normalize_embeddings=True).astype(np.float32)

        # Search
        t0 = time.time()
        k = 10
        distances, ids = index.search(q_vec, k)
        latency_ms = (time.time() - t0) * 1000
        total_latency += latency_ms

        # Get top-1 event type from metadata
        top1_type = "N/A"
        top5_types = set()
        if index_path and meta_path.exists():
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            meta_lookup = {m["id"]: m for m in meta}
            for doc_id in ids[0]:
                if doc_id in meta_lookup:
                    et = meta_lookup[doc_id].get("event_type", "?")
                    if not top1_type or top1_type == "N/A":
                        top1_type = et
                    top5_types.add(et)

        # Check if top-5 contains the expected event type (rough check)
        expected_map = {
            0: "purchase", 1: "purchase", 2: "add_to_cart",
            3: "view", 4: "search", 5: "click",
            6: "view", 7: "add_to_cart",
        }
        expected = expected_map.get(i - 1, "view")
        hit = expected in top5_types if top5_types else False
        top5_hit_rates.append(hit)

        short_q = query[:54] + ("..." if len(query) > 54 else "")
        print(f"  {i:<3d} {short_q:<55s} {top1_type:<15s} {latency_ms:<12.1f} "
              f"{'HIT  ' if hit else 'MISS':<10s}")

    avg_latency = total_latency / len(test_queries)
    hit_rate = sum(top5_hit_rates) / len(top5_hit_rates) * 100

    print(f"\n  📊 Average retrieval latency: {avg_latency:.1f} ms")
    print(f"  📊 Top-5 hit rate:            {hit_rate:.0f}% "
          f"({sum(top5_hit_rates)}/{len(top5_hit_rates)})")
    print(f"  📊 Queries run:               {len(test_queries)}")

    # Recommend k for RAG
    print(f"\n  💡 Recommendation: Use top_k=5 for prompt-building "
          f"(avg latency ~{avg_latency:.1f} ms)")


# ---------------------------------------------------------------------------
# 6.  Main entry point
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Build a local FAISS knowledge base from Parquet/dbt data"
    )
    parser.add_argument(
        "--parquet-dir",
        type=Path,
        default=DEFAULT_PARQUET_DIR,
        help="Directory containing .parquet files (default: ../data/output_parquet)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for FAISS index + metadata (default: knowledge_base/)",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=5000,
        help="Max rows to embed (default: 5000)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=os.getenv("EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2"),
        help="Sentence-transformer model name (default: paraphrase-multilingual-MiniLM-L12-v2)",
    )
    parser.add_argument(
        "--benchmark",
        action="store_true",
        default=True,
        help="Run retrieval benchmark after building (default: true)",
    )
    parser.add_argument(
        "--no-benchmark",
        action="store_true",
        help="Skip the benchmark",
    )
    args = parser.parse_args()

    print("=" * 50)
    print("  🧬 FAISS Knowledge Base Builder")
    print("=" * 50)
    print(f"  Output:      {args.output_dir}")
    print(f"  Parquet dir: {args.parquet_dir}")
    print(f"  Max rows:    {args.sample_size}")
    print(f"  Model:       {args.model}")
    print()

    # Import lazy dependencies here so --help works even without them
    from sentence_transformers import SentenceTransformer

    # ── Load embedding model ──
    print(f"  🤖 Loading model: {args.model} ...")
    model = SentenceTransformer(args.model)
    dim = model.get_sentence_embedding_dimension()
    print(f"     Dimension: {dim}")

    # ── Load data ──
    records = read_parquet_events(args.parquet_dir, args.sample_size)
    using_synthetic = False

    if not records:
        print(f"\n  ⚠️  No Parquet data found. Falling back to synthetic demo data.")
        records = generate_synthetic_events(args.sample_size)
        using_synthetic = True

    print(f"  📖 {len(records)} records loaded "
          f"({'synthetic' if using_synthetic else 'parquet'})")

    # ── Chunking ──
    chunks: list[str] = []
    metadata: list[dict] = []

    for i, rec in enumerate(records):
        chunk = row_to_chunk(rec)
        chunk_len = len(chunk)
        # Ensure chunks stay in the 50-200 character range
        if chunk_len < 20:
            chunk = f"Event {rec.get('event_id', i)}: {chunk}"
        if chunk_len > 200:
            chunk = chunk[:197] + "..."

        chunks.append(chunk)
        metadata.append({
            "id": i,
            "event_id": str(rec.get("event_id", f"evt_{i}")),
            "user_id": str(rec.get("user_id", "?")),
            "event_type": str(rec.get("event_type", "?")),
            "product_id": str(rec.get("product_id", "")),
            "product_category": str(rec.get("product_category", "")),
            "page": str(rec.get("page", "")),
            "referrer": str(rec.get("referrer", "")),
            "device": str(rec.get("device", "")),
            "browser": str(rec.get("browser", "")),
            "duration_ms": rec.get("duration_ms", 0),
            "chunk": chunk,
        })

    # Quick chunk-length stats
    lens = [len(c) for c in chunks]
    print(f"\n  📏 Chunk length stats: "
          f"min={min(lens)}, max={max(lens)}, "
          f"avg={sum(lens)//len(lens):.0f}, "
          f"median={sorted(lens)[len(lens)//2]:.0f}")

    # ── Build & save FAISS index ──
    stats = build_faiss_index(chunks, metadata, model, args.output_dir)

    # ── Summary ──
    print(f"\n{'='*50}")
    print("  ✅ Knowledge base built successfully!")
    print(f"{'='*50}")
    print(json.dumps(stats, indent=2, ensure_ascii=False))
    print(f"\n  📁 Files:")
    print(f"     {args.output_dir / 'index.faiss'}")
    print(f"     {args.output_dir / 'metadata.json'}")

    # ── Benchmark ──
    if args.benchmark and not args.no_benchmark:
        run_benchmark(args.output_dir)

    print(f"\n[DONE]  Ready to serve. Start the RAG server with:")
    print(f"        uvicorn rag_server:app --host 0.0.0.0 --port 8002")


if __name__ == "__main__":
    main()
