#!/usr/bin/env python3
"""
Performance Benchmark Suite — Data Platform Demo
=================================================

Benchmarks:
  1. Parquet Query — Pandas vs PySpark vs DuckDB (read/write throughput)
  2. Vector Search   — Milvus query latency at different dataset sizes & top_k
  3. Embedding       — sentence-transformers encoding throughput by batch size

Output:
  - Formatted text table to stdout
  - JSON results to benchmarks/results/benchmark_results.json

All benchmarks gracefully degrade: if a component is unavailable, it is skipped.
"""

import argparse
import json
import os
import random
import statistics
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# ---- Paths ----
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
RESULTS_DIR = SCRIPT_DIR / "results"
DATA_DIR = SCRIPT_DIR / "data"

# Ensure directories exist
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# Utility Functions
# ============================================================

def time_perf_counter() -> float:
    """Return high-resolution timer value."""
    return time.perf_counter()


def compute_stats(timings: list[float]) -> dict[str, float]:
    """Compute statistical summary of a list of timing measurements (in seconds)."""
    if not timings:
        return {"mean": 0, "median": 0, "min": 0, "max": 0, "p95": 0, "p99": 0}

    sorted_timings = sorted(timings)
    n = len(sorted_timings)

    return {
        "count": n,
        "mean": round(statistics.mean(timings), 6),
        "median": round(statistics.median(timings), 6),
        "min": round(min(timings), 6),
        "max": round(max(timings), 6),
        "p95": round(sorted_timings[int(n * 0.95)] if n > 1 else sorted_timings[0], 6),
        "p99": round(sorted_timings[int(n * 0.99)] if n > 1 else sorted_timings[0], 6),
        "stdev": round(statistics.stdev(timings) if n > 1 else 0.0, 6),
    }


def format_time(seconds: float) -> str:
    """Human-readable time formatting."""
    if seconds < 0.001:
        return f"{seconds * 1_000_000:.1f} us"
    elif seconds < 1.0:
        return f"{seconds * 1000:.1f} ms"
    elif seconds < 60:
        return f"{seconds:.2f} s"
    else:
        return f"{seconds / 60:.1f} min"


def format_bytes(num_bytes: float) -> str:
    """Human-readable byte formatting."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num_bytes < 1024:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} PB"


def save_results(results: dict[str, Any], output_path: Path):
    """Save benchmark results to a JSON file."""
    results["metadata"] = {
        "timestamp": datetime.now().isoformat(),
        "python_version": sys.version,
        "platform": sys.platform,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n  Results saved to: {output_path}")


def print_table_header(title: str):
    """Print a centered table header."""
    print()
    print("=" * 80)
    print(f"  {title}")
    print("=" * 80)


def print_section(title: str):
    """Print a section header."""
    print()
    print(f"  --- {title} ---")


# ============================================================
# Benchmark 1: Parquet Query Performance
# ============================================================

def generate_parquet_data(
    num_rows: int = 100_000, output_path: Optional[Path] = None
) -> Path:
    """
    Generate synthetic test data and save as a Parquet file.

    Returns the path to the generated file.
    """
    import pandas as pd

    if output_path is None:
        output_path = DATA_DIR / f"benchmark_test_{num_rows}.parquet"

    if output_path.exists():
        return output_path  # Reuse existing file

    print(f"  Generating {num_rows:,} rows of synthetic data...")

    np_random = __import__("numpy", fromlist=["random"]).random
    np_randint = __import__("numpy", fromlist=["random"]).random
    # We use the random module directly for deterministic generation
    random.seed(42)
    import numpy as np

    rng = np.random.default_rng(42)

    event_types = ["view", "click", "add_to_cart", "purchase", "search"]
    devices = ["desktop", "mobile", "tablet"]
    browsers = ["Chrome", "Firefox", "Safari", "Edge"]
    pages = ["home", "product_detail", "checkout", "search", "category"]

    user_ids = [f"U{str(i).zfill(6)}" for i in range(1, 10001)]
    product_ids = [f"P{str(i).zfill(6)}" for i in range(1, 5001)]

    df = pd.DataFrame({
        "event_id": [str(uuid.uuid4()) for _ in range(num_rows)],
        "user_id": rng.choice(user_ids, size=num_rows),
        "event_type": rng.choice(event_types, size=num_rows),
        "product_id": rng.choice(product_ids, size=num_rows),
        "timestamp": pd.date_range("2026-01-01", periods=num_rows, freq="s"),
        "page": rng.choice(pages, size=num_rows),
        "referrer": rng.choice(["google", "direct", "bing", None], size=num_rows, p=[0.4, 0.3, 0.2, 0.1]),
        "duration_ms": rng.integers(0, 300000, size=num_rows),
        "device": rng.choice(devices, size=num_rows),
        "browser": rng.choice(browsers, size=num_rows),
        "value": rng.random(size=num_rows) * 1000,
        "category_id": rng.integers(1, 100, size=num_rows),
    })

    df["event_ts"] = pd.to_datetime(df["timestamp"])
    df["processed_at"] = pd.Timestamp.now()
    df["processing_date"] = df["event_ts"].dt.date

    df.to_parquet(output_path, index=False, compression="snappy")

    file_size = os.path.getsize(output_path)
    print(f"  Saved: {format_bytes(file_size)} → {output_path}")

    return output_path


def benchmark_pandas_parquet(file_path: Path, iterations: int = 5) -> dict[str, Any]:
    """Benchmark Pandas Parquet read + query performance."""
    import pandas as pd

    print_section("Pandas Parquet Benchmark")
    print(f"  File: {file_path}")
    print(f"  Iterations: {iterations}")

    # Warm-up
    print("  Warm-up run...")
    _ = pd.read_parquet(file_path)

    read_times = []
    filter_times = []
    agg_times = []
    write_times = []

    for i in range(iterations):
        # Measure read
        t0 = time_perf_counter()
        df = pd.read_parquet(file_path)
        read_times.append(time_perf_counter() - t0)

        # Measure filter + aggregate query
        t0 = time_perf_counter()
        result = df[df["event_type"] == "purchase"].groupby("device")["value"].agg(["sum", "mean", "count"])
        filter_times.append(time_perf_counter() - t0)

        # Measure aggregation
        t0 = time_perf_counter()
        result2 = (
            df.groupby(["event_type", "device"])
            .agg(value_sum=("value", "sum"), count=("event_id", "count"))
            .reset_index()
        )
        agg_times.append(time_perf_counter() - t0)

        # Measure write
        tmp_path = DATA_DIR / f"tmp_pandas_{i}.parquet"
        t0 = time_perf_counter()
        df.to_parquet(tmp_path, index=False, compression="snappy")
        write_times.append(time_perf_counter() - t0)
        if tmp_path.exists():
            tmp_path.unlink()

        print(f"    Iteration {i + 1}/{iterations}: "
              f"read={format_time(read_times[-1])}, "
              f"filter={format_time(filter_times[-1])}, "
              f"agg={format_time(agg_times[-1])}")

    num_rows = len(df)
    file_size = os.path.getsize(file_path)

    return {
        "engine": "pandas",
        "num_rows": num_rows,
        "file_size_bytes": file_size,
        "read": compute_stats(read_times),
        "filter_query": compute_stats(filter_times),
        "aggregation": compute_stats(agg_times),
        "write": compute_stats(write_times),
        "throughput_read_rps": round(num_rows / compute_stats(read_times)["mean"], 1) if read_times else 0,
        "throughput_write_rps": round(num_rows / compute_stats(write_times)["mean"], 1) if write_times else 0,
    }


def benchmark_duckdb_parquet(file_path: Path, iterations: int = 5) -> dict[str, Any]:
    """Benchmark DuckDB Parquet query performance."""
    try:
        import duckdb
    except ImportError:
        return {"engine": "duckdb", "skipped": True, "reason": "duckdb not installed"}
    import pandas as pd

    print_section("DuckDB Parquet Benchmark")
    print(f"  File: {file_path}")
    print(f"  Iterations: {iterations}")

    # Warm-up
    print("  Warm-up run...")
    con = duckdb.connect()
    con.execute(f"SELECT count(*) FROM '{file_path}'").fetchone()

    read_times = []
    filter_times = []
    agg_times = []

    for i in range(iterations):
        # Measure full table read
        t0 = time_perf_counter()
        con = duckdb.connect()
        result = con.execute(f"SELECT * FROM '{file_path}'").fetchdf()
        read_times.append(time_perf_counter() - t0)

        # Measure filter query
        t0 = time_perf_counter()
        result = con.execute(
            f"SELECT device, SUM(value) as total_value, AVG(value) as avg_value, COUNT(*) as cnt "
            f"FROM '{file_path}' WHERE event_type = 'purchase' GROUP BY device"
        ).fetchdf()
        filter_times.append(time_perf_counter() - t0)

        # Measure complex aggregation
        t0 = time_perf_counter()
        result = con.execute(
            f"SELECT event_type, device, SUM(value) as value_sum, COUNT(*) as cnt "
            f"FROM '{file_path}' GROUP BY event_type, device ORDER BY event_type"
        ).fetchdf()
        agg_times.append(time_perf_counter() - t0)

        con.close()
        print(f"    Iteration {i + 1}/{iterations}: "
              f"read={format_time(read_times[-1])}, "
              f"filter={format_time(filter_times[-1])}, "
              f"agg={format_time(agg_times[-1])}")

    con = duckdb.connect()
    num_rows = con.execute(f"SELECT count(*) FROM '{file_path}'").fetchone()[0]
    con.close()
    file_size = os.path.getsize(file_path)

    return {
        "engine": "duckdb",
        "num_rows": num_rows,
        "file_size_bytes": file_size,
        "read": compute_stats(read_times),
        "filter_query": compute_stats(filter_times),
        "aggregation": compute_stats(agg_times),
        "throughput_read_rps": round(num_rows / compute_stats(read_times)["mean"], 1) if read_times else 0,
    }


def benchmark_pyspark_parquet(file_path: Path, iterations: int = 3) -> dict[str, Any]:
    """Benchmark PySpark Parquet query performance."""
    try:
        from pyspark.sql import SparkSession
    except ImportError:
        return {"engine": "pyspark", "skipped": True, "reason": "pyspark not installed"}

    print_section("PySpark Parquet Benchmark")
    print(f"  File: {file_path}")
    print(f"  Iterations: {iterations}")

    spark = (
        SparkSession.builder
        .appName("ParquetBenchmark")
        .config("spark.sql.adaptive.enabled", "true")
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true")
        .master("local[*]")
        .getOrCreate()
    )

    file_path_str = str(file_path).replace("\\", "/")

    # Warm-up
    print("  Warm-up run...")
    spark.read.parquet(file_path_str).count()

    read_times = []
    filter_times = []
    agg_times = []

    for i in range(iterations):
        # Measure read + count
        t0 = time_perf_counter()
        df = spark.read.parquet(file_path_str)
        num_rows = df.count()
        read_times.append(time_perf_counter() - t0)

        # Measure filter query
        t0 = time_perf_counter()
        result = (
            df.filter("event_type == 'purchase'")
            .groupBy("device")
            .agg({"value": "sum", "*": "count"})
            .collect()
        )
        filter_times.append(time_perf_counter() - t0)

        # Measure complex aggregation
        t0 = time_perf_counter()
        result = (
            df.groupBy("event_type", "device")
            .agg({"value": "sum", "event_id": "count"})
            .collect()
        )
        agg_times.append(time_perf_counter() - t0)

        print(f"    Iteration {i + 1}/{iterations}: "
              f"read={format_time(read_times[-1])}, "
              f"filter={format_time(filter_times[-1])}, "
              f"agg={format_time(agg_times[-1])}")

    spark.stop()

    file_size = os.path.getsize(file_path)

    return {
        "engine": "pyspark",
        "num_rows": num_rows,
        "file_size_bytes": file_size,
        "read": compute_stats(read_times),
        "filter_query": compute_stats(filter_times),
        "aggregation": compute_stats(agg_times),
        "throughput_read_rps": round(num_rows / compute_stats(read_times)["mean"], 1) if read_times else 0,
    }


def run_parquet_benchmarks(num_rows: int = 100_000, iterations: int = 5) -> dict[str, Any]:
    """Run all Parquet engine benchmarks."""
    print_table_header("Benchmark 1: Parquet Query Performance")

    file_path = generate_parquet_data(num_rows)

    results = {}

    # Pandas
    print_section("Engine: Pandas")
    try:
        results["pandas"] = benchmark_pandas_parquet(file_path, iterations)
    except Exception as e:
        results["pandas"] = {"engine": "pandas", "skipped": True, "reason": str(e)}
        print(f"  SKIPPED — {e}")

    # DuckDB
    print_section("Engine: DuckDB")
    try:
        results["duckdb"] = benchmark_duckdb_parquet(file_path, iterations)
    except Exception as e:
        results["duckdb"] = {"engine": "duckdb", "skipped": True, "reason": str(e)}
        print(f"  SKIPPED — {e}")

    # PySpark
    print_section("Engine: PySpark")
    try:
        results["pyspark"] = benchmark_pyspark_parquet(file_path, iterations)
    except Exception as e:
        results["pyspark"] = {"engine": "pyspark", "skipped": True, "reason": str(e)}
        print(f"  SKIPPED — {e}")

    # Summary comparison
    _print_parquet_comparison(results)

    return results


def _print_parquet_comparison(results: dict[str, Any]):
    """Print a comparison table for Parquet engine benchmarks."""
    print_section("Parquet Engine Comparison")

    engines = []
    for name, res in results.items():
        if res.get("skipped"):
            continue
        engines.append((name, res))

    if not engines:
        print("  No engines available for comparison")
        return

    # Header
    header = f"  {'Engine':<10} {'Rows':>12} {'Read Mean':>12} {'Read P95':>12} {'Filter Mean':>12} {'Agg Mean':>12} {'Read RPS':>12}"
    print(header)
    print("  " + "-" * (len(header) - 2))

    for name, res in engines:
        read_stats = res.get("read", {})
        filter_stats = res.get("filter_query", {})
        agg_stats = res.get("aggregation", {})
        throughput = res.get("throughput_read_rps", 0)

        print(
            f"  {name:<10} {res.get('num_rows', 0):>12,} "
            f"{format_time(read_stats.get('mean', 0)):>12} "
            f"{format_time(read_stats.get('p95', 0)):>12} "
            f"{format_time(filter_stats.get('mean', 0)):>12} "
            f"{format_time(agg_stats.get('mean', 0)):>12} "
            f"{throughput:>12,.1f}"
        )


# ============================================================
# Benchmark 2: Vector Search Performance (Milvus)
# ============================================================

def _check_milvus() -> bool:
    """Check if Milvus is reachable."""
    try:
        from pymilvus import connections, utility
        milvus_host = os.getenv("MILVUS_HOST", "localhost")
        milvus_port = os.getenv("MILVUS_PORT", "19530")
        connections.connect(host=milvus_host, port=milvus_port, timeout=5)
        version = utility.get_server_version()
        connections.disconnect("default")
        print(f"  Milvus available: version {version}")
        return True
    except Exception as e:
        print(f"  Milvus not available: {e}")
        return False


def _get_milvus_available() -> bool:
    """Check and cache Milvus availability."""
    if not hasattr(_get_milvus_available, "_cached"):
        _get_milvus_available._cached = _check_milvus()
    return _get_milvus_available._cached


def benchmark_milvus_search(
    dataset_sizes: list[int] | None = None,
    top_k_values: list[int] | None = None,
    iterations: int = 10,
) -> dict[str, Any]:
    """Benchmark Milvus vector search latency.

    Creates a temporary collection, inserts random vectors at different
    dataset sizes, and measures search latency for various top_k values.
    """
    if dataset_sizes is None:
        dataset_sizes = [100, 1_000, 10_000, 100_000]
    if top_k_values is None:
        top_k_values = [1, 5, 10, 50, 100]

    try:
        from pymilvus import (
            Collection,
            CollectionSchema,
            DataType,
            FieldSchema,
            connections,
            utility,
        )
        import numpy as np
    except ImportError:
        return {
            "skipped": True,
            "reason": "pymilvus not installed",
        }

    if not _get_milvus_available():
        return {
            "skipped": True,
            "reason": "Milvus not reachable",
        }

    print_table_header("Benchmark 2: Vector Search Performance (Milvus)")
    print(f"  Dataset sizes: {[f'{s:,}' for s in dataset_sizes]}")
    print(f"  Top-K values:  {top_k_values}")
    print(f"  Iterations:    {iterations}")

    milvus_host = os.getenv("MILVUS_HOST", "localhost")
    milvus_port = os.getenv("MILVUS_PORT", "19530")
    connections.connect(host=milvus_host, port=milvus_port)

    VECTOR_DIM = 384
    COLLECTION_NAME = "benchmark_search_test"
    results: dict[str, Any] = {"size_results": {}}

    for size in dataset_sizes:
        print(f"\n  Dataset size: {size:,} vectors")

        # Create collection for this size
        if utility.has_collection(COLLECTION_NAME):
            utility.drop_collection(COLLECTION_NAME)

        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=VECTOR_DIM),
            FieldSchema(name="label", dtype=DataType.VARCHAR, max_length=64),
        ]
        schema = CollectionSchema(fields, f"Benchmark collection (size={size})")
        collection = Collection(COLLECTION_NAME, schema)

        # Create index
        index_params = {
            "metric_type": "IP",
            "index_type": "IVF_FLAT",
            "params": {"nlist": min(128, max(1, size // 100))},
        }
        collection.create_index("embedding", index_params)

        # Generate and insert random vectors in batches
        batch_size = 1000
        for start in range(0, size, batch_size):
            end = min(start + batch_size, size)
            batch_count = end - start
            vectors = np.random.randn(batch_count, VECTOR_DIM).astype(np.float32)
            # L2 normalize
            norms = np.linalg.norm(vectors, axis=1, keepdims=True)
            vectors = vectors / norms

            entities = [
                vectors.tolist(),
                [f"item_{i}" for i in range(start, end)],
            ]
            collection.insert(entities)

        collection.flush()
        collection.load()
        print(f"    Inserted {collection.num_entities:,} vectors, index ready")

        size_result: dict[str, Any] = {"num_vectors": size, "top_k_results": {}}

        for top_k in top_k_values:
            if top_k > size:
                size_result["top_k_results"][f"k={top_k}"] = {
                    "skipped": True,
                    "reason": f"top_k ({top_k}) > dataset size ({size})",
                }
                continue

            latencies = []
            for i in range(iterations):
                query_vec = np.random.randn(1, VECTOR_DIM).astype(np.float32)
                norms = np.linalg.norm(query_vec, axis=1, keepdims=True)
                query_vec = query_vec / norms

                t0 = time_perf_counter()
                _ = collection.search(
                    data=query_vec.tolist(),
                    anns_field="embedding",
                    param={"metric_type": "IP", "params": {"nprobe": 16}},
                    limit=top_k,
                )
                latencies.append(time_perf_counter() - t0)

                if i == 0:
                    print(f"    top_k={top_k:<4} warmup: {format_time(latencies[-1])}")

            stats = compute_stats(latencies)
            size_result["top_k_results"][f"k={top_k}"] = {
                "latency_stats": stats,
                "latency_mean_ms": round(stats["mean"] * 1000, 3),
                "latency_p95_ms": round(stats["p95"] * 1000, 3),
            }
            print(f"    top_k={top_k:<4} mean={stats['mean']*1000:.2f}ms, "
                  f"p95={stats['p95']*1000:.2f}ms, "
                  f"qps={1/stats['mean']:.1f}")

        results["size_results"][str(size)] = size_result

        # Clean up
        collection.release()
        utility.drop_collection(COLLECTION_NAME)

    connections.disconnect("default")

    _print_milvus_summary(results)
    return results


def _print_milvus_summary(results: dict[str, Any]):
    """Print a summary table for Milvus benchmark results."""
    if results.get("skipped"):
        return

    print_section("Milvus Search Performance Summary")

    header = f"  {'Size':>10} {'K':>5} {'Mean(ms)':>10} {'P95(ms)':>10} {'QPS':>10} {'Min(ms)':>10} {'Max(ms)':>10}"
    print(header)
    print("  " + "-" * (len(header) - 2))

    for size_str, size_res in results.get("size_results", {}).items():
        size = int(size_str)
        for k_str, k_res in size_res.get("top_k_results", {}).items():
            if k_res.get("skipped"):
                continue
            stats = k_res["latency_stats"]
            qps = 1 / stats["mean"] if stats["mean"] > 0 else 0
            print(
                f"  {size:>10,} {k_str:>5} "
                f"{stats['mean']*1000:>10.2f} {stats['p95']*1000:>10.2f} "
                f"{qps:>10.1f} {stats['min']*1000:>10.2f} {stats['max']*1000:>10.2f}"
            )


# ============================================================
# Benchmark 3: Embedding Throughput
# ============================================================

def benchmark_embedding_throughput(
    batch_sizes: list[int] | None = None,
    num_texts: int = 10_000,
    iterations: int = 5,
) -> dict[str, Any]:
    """Benchmark sentence-transformers encoding throughput at different batch sizes."""
    try:
        from sentence_transformers import SentenceTransformer
        import numpy as np
    except ImportError:
        return {"skipped": True, "reason": "sentence-transformers not installed"}

    if batch_sizes is None:
        batch_sizes = [1, 8, 32, 128, 512]

    print_table_header("Benchmark 3: Embedding Throughput")
    print(f"  Model: paraphrase-multilingual-MiniLM-L12-v2")
    print(f"  Total texts: {num_texts:,}")
    print(f"  Batch sizes: {batch_sizes}")
    print(f"  Iterations:  {iterations}")

    # Generate test texts (simulating user event descriptions in Chinese + English)
    event_types_cn = ["浏览", "点击", "加入购物车", "购买", "搜索"]
    event_types_en = ["view", "click", "add_to_cart", "purchase", "search"]
    devices = ["桌面端", "移动端", "平板"]
    pages = ["首页", "商品详情", "结算页", "搜索页", "分类页"]
    referrers = ["谷歌搜索", "直接访问", "必应搜索", "社交媒体"]

    texts = []
    for i in range(num_texts):
        et = random.choice(event_types_cn)
        dev = random.choice(devices)
        pg = random.choice(pages)
        ref = random.choice(referrers)
        uid = f"U{random.randint(1, 99999):05d}"
        texts.append(f"用户{uid}在{dev}上{et}了{pg}，来源{ref}")

    print(f"  Generated {len(texts)} synthetic texts")
    print(f"  Sample text: {texts[0]}...")

    # Load model
    print("\n  Loading model...")
    model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    print(f"  Model loaded: dim={model.get_sentence_embedding_dimension()}")

    # Warm-up
    print("  Warm-up run...")
    _ = model.encode(texts[:128], batch_size=128, show_progress_bar=False)

    results: dict[str, Any] = {"model": "paraphrase-multilingual-MiniLM-L12-v2",
                                "dim": model.get_sentence_embedding_dimension(),
                                "num_texts": num_texts,
                                "batch_results": {}}

    print()
    header = f"  {'Batch':>8} {'Total(s)':>10} {'Texts/s':>12} {'Mean(s)':>10} {'P95(s)':>10} {'GB/s':>10}"
    print(header)
    print("  " + "-" * (len(header) - 2))

    for batch_size in batch_sizes:
        batch_timings = []

        for i in range(iterations):
            t0 = time_perf_counter()
            embeddings = model.encode(
                texts,
                batch_size=batch_size,
                show_progress_bar=False,
                normalize_embeddings=True,
            )
            elapsed = time_perf_counter() - t0
            batch_timings.append(elapsed)

            if i == 0:
                print(f"    Batch={batch_size}: first run {format_time(elapsed)}")

        stats = compute_stats(batch_timings)
        throughput = num_texts / stats["mean"] if stats["mean"] > 0 else 0

        # Calculate GB/s (384 dims * 4 bytes per float32 * num_texts)
        data_size_gb = (model.get_sentence_embedding_dimension() * 4 * num_texts) / (1024 ** 3)
        gb_per_sec = data_size_gb / stats["mean"] if stats["mean"] > 0 else 0

        results["batch_results"][f"batch_{batch_size}"] = {
            "batch_size": batch_size,
            "latency_stats": stats,
            "throughput_texts_per_sec": round(throughput, 1),
            "throughput_gb_per_sec": round(gb_per_sec, 2),
        }

        print(
            f"  {batch_size:>8} "
            f"{format_time(stats['mean']):>10} "
            f"{throughput:>12,.1f} "
            f"{format_time(stats['mean']):>10} "
            f"{format_time(stats['p95']):>10} "
            f"{gb_per_sec:>10.2f}"
        )

    # Clean up
    del model
    return results


# ============================================================
# FAISS Local Vector Search Benchmark (fallback)
# ============================================================

def benchmark_faiss_search(
    dataset_sizes: list[int] | None = None,
    top_k_values: list[int] | None = None,
    iterations: int = 20,
) -> dict[str, Any]:
    """
    Benchmark local FAISS vector search latency.

    This is a reliable fallback when Milvus is not available.
    """
    if dataset_sizes is None:
        dataset_sizes = [1_000, 10_000, 100_000]
    if top_k_values is None:
        top_k_values = [1, 5, 10, 50, 100]

    try:
        import faiss
        import numpy as np
    except ImportError:
        return {"skipped": True, "reason": "faiss-cpu not installed"}

    print_table_header("Benchmark 2b: FAISS Local Vector Search (Fallback)")
    print(f"  Dataset sizes: {[f'{s:,}' for s in dataset_sizes]}")
    print(f"  Top-K values:  {top_k_values}")
    print(f"  Iterations:    {iterations}")

    VECTOR_DIM = 384
    results: dict[str, Any] = {"size_results": {}}

    for size in dataset_sizes:
        print(f"\n  Dataset size: {size:,} vectors")

        # Generate random normalized vectors
        np.random.seed(42)
        vectors = np.random.randn(size, VECTOR_DIM).astype(np.float32)
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        vectors = vectors / norms

        # Create FAISS index
        index = faiss.IndexFlatIP(VECTOR_DIM)  # Inner Product
        index.add(vectors)
        print(f"    Index built: {index.ntotal:,} vectors")

        size_result: dict[str, Any] = {"num_vectors": size, "top_k_results": {}}

        for top_k in top_k_values:
            if top_k > size:
                size_result["top_k_results"][f"k={top_k}"] = {
                    "skipped": True,
                    "reason": f"top_k ({top_k}) > dataset size ({size})",
                }
                continue

            latencies = []
            for i in range(iterations):
                query_vec = np.random.randn(1, VECTOR_DIM).astype(np.float32)
                query_vec = query_vec / np.linalg.norm(query_vec)

                t0 = time_perf_counter()
                _ = index.search(query_vec, top_k)
                latencies.append(time_perf_counter() - t0)

                if i == 0:
                    print(f"    top_k={top_k:<4} warmup: {format_time(latencies[-1])}")

            stats = compute_stats(latencies)
            size_result["top_k_results"][f"k={top_k}"] = {
                "latency_stats": stats,
                "latency_mean_ms": round(stats["mean"] * 1000, 3),
                "latency_p95_ms": round(stats["p95"] * 1000, 3),
            }
            qps = 1 / stats["mean"] if stats["mean"] > 0 else 0
            print(f"    top_k={top_k:<4} mean={stats['mean']*1000:.2f}ms, "
                  f"p95={stats['p95']*1000:.2f}ms, "
                  f"qps={qps:.1f}")

        results["size_results"][str(size)] = size_result

    _print_faiss_summary(results)
    return results


def _print_faiss_summary(results: dict[str, Any]):
    """Print summary table for FAISS benchmark results."""
    if results.get("skipped"):
        return

    print_section("FAISS Search Performance Summary")

    header = f"  {'Size':>10} {'K':>5} {'Mean(ms)':>10} {'P95(ms)':>10} {'QPS':>10} {'Min(ms)':>10} {'Max(ms)':>10}"
    print(header)
    print("  " + "-" * (len(header) - 2))

    for size_str, size_res in results.get("size_results", {}).items():
        size = int(size_str)
        for k_str, k_res in size_res.get("top_k_results", {}).items():
            if k_res.get("skipped"):
                continue
            stats = k_res["latency_stats"]
            qps = 1 / stats["mean"] if stats["mean"] > 0 else 0
            print(
                f"  {size:>10,} {k_str:>5} "
                f"{stats['mean']*1000:>10.2f} {stats['p95']*1000:>10.2f} "
                f"{qps:>10.1f} {stats['min']*1000:>10.2f} {stats['max']*1000:>10.2f}"
            )


# ============================================================
# Main Entry Point
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Performance Benchmark Suite — Data Platform Demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python benchmarks/run_benchmarks.py
  python benchmarks/run_benchmarks.py --parquet-rows 50000 --iterations 3
  python benchmarks/run_benchmarks.py --skip-vector --output results/custom.json
        """,
    )
    parser.add_argument(
        "--parquet-rows",
        type=int,
        default=100_000,
        help="Number of rows for Parquet benchmark data (default: 100000)",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=5,
        help="Number of iterations per benchmark (default: 5)",
    )
    parser.add_argument(
        "--skip-parquet", action="store_true", help="Skip Parquet query benchmarks"
    )
    parser.add_argument(
        "--skip-vector", action="store_true", help="Skip vector search benchmarks"
    )
    parser.add_argument(
        "--skip-embedding", action="store_true", help="Skip embedding throughput benchmarks"
    )
    parser.add_argument(
        "--skip-faiss", action="store_true", help="Skip FAISS fallback benchmarks"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=RESULTS_DIR / "benchmark_results.json",
        help=f"Output JSON path (default: {RESULTS_DIR / 'benchmark_results.json'})",
    )
    parser.add_argument(
        "--embedding-texts",
        type=int,
        default=10_000,
        help="Number of texts for embedding benchmark (default: 10000)",
    )

    args = parser.parse_args()

    print("=" * 80)
    print("  🔬 Data Platform — Performance Benchmark Suite")
    print("=" * 80)
    print(f"  Started:        {datetime.now().isoformat()}")
    print(f"  Python:         {sys.version.split()[0]}")
    print(f"  Platform:       {sys.platform}")
    print(f"  Parquet rows:   {args.parquet_rows:,}")
    print(f"  Iterations:     {args.iterations}")
    print(f"  Output:         {args.output}")
    print("=" * 80)

    all_results: dict[str, Any] = {
        "title": "Data Platform Performance Benchmarks",
        "config": {
            "parquet_rows": args.parquet_rows,
            "iterations": args.iterations,
            "embedding_texts": args.embedding_texts,
        },
        "benchmarks": {},
    }

    # ---- Benchmark 1: Parquet Query Performance ----
    if not args.skip_parquet:
        try:
            all_results["benchmarks"]["parquet"] = run_parquet_benchmarks(
                num_rows=args.parquet_rows,
                iterations=args.iterations,
            )
        except Exception as e:
            print(f"\n  ❌ Parquet benchmark error: {e}")
            all_results["benchmarks"]["parquet"] = {"error": str(e)}
    else:
        all_results["benchmarks"]["parquet"] = {"skipped": True, "reason": "--skip-parquet"}
        print("\n  Parquet benchmarks skipped (--skip-parquet)")

    # ---- Benchmark 2: Vector Search (Milvus) ----
    if not args.skip_vector:
        try:
            all_results["benchmarks"]["milvus_search"] = benchmark_milvus_search(
                iterations=min(args.iterations, 20),
            )
        except Exception as e:
            print(f"\n  ❌ Milvus benchmark error: {e}")
            all_results["benchmarks"]["milvus_search"] = {"error": str(e)}
    else:
        all_results["benchmarks"]["milvus_search"] = {"skipped": True, "reason": "--skip-vector"}
        print("\n  Vector search benchmarks skipped (--skip-vector)")

    # ---- Benchmark 2b: FAISS Local Search (Fallback) ----
    if not args.skip_vector and not args.skip_faiss:
        try:
            all_results["benchmarks"]["faiss_search"] = benchmark_faiss_search(
                iterations=min(args.iterations, 20),
            )
        except Exception as e:
            print(f"\n  ❌ FAISS benchmark error: {e}")
            all_results["benchmarks"]["faiss_search"] = {"error": str(e)}
    elif args.skip_faiss:
        all_results["benchmarks"]["faiss_search"] = {"skipped": True, "reason": "--skip-faiss"}

    # ---- Benchmark 3: Embedding Throughput ----
    if not args.skip_embedding:
        try:
            all_results["benchmarks"]["embedding"] = benchmark_embedding_throughput(
                num_texts=args.embedding_texts,
                iterations=args.iterations,
            )
        except Exception as e:
            print(f"\n  ❌ Embedding benchmark error: {e}")
            all_results["benchmarks"]["embedding"] = {"error": str(e)}
    else:
        all_results["benchmarks"]["embedding"] = {"skipped": True, "reason": "--skip-embedding"}
        print("\n  Embedding benchmarks skipped (--skip-embedding)")

    # ---- Save Results ----
    save_results(all_results, args.output)

    # ---- Final Summary ----
    print()
    print("=" * 80)
    print("  ✅ Benchmark Suite Complete")
    print("=" * 80)

    # Summary of what ran
    for name, bm in all_results["benchmarks"].items():
        if bm.get("error"):
            print(f"  ❌ {name}: ERROR — {bm['error']}")
        elif bm.get("skipped"):
            reason = bm.get("reason", "unknown")
            print(f"  ⚠️  {name}: SKIPPED — {reason}")
        else:
            print(f"  ✅ {name}: COMPLETED")

    print(f"\n  Results: {args.output}")
    print("=" * 80)


if __name__ == "__main__":
    main()
