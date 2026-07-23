# Data Platform — Performance Benchmark Report

**Generated:** [Date]
**Python Version:** [Version]
**Platform:** [Platform]

---

## Table of Contents

1. [Methodology](#methodology)
2. [Parquet Query Performance](#parquet-query-performance)
3. [Vector Search Performance](#vector-search-performance)
4. [Embedding Throughput](#embedding-throughput)
5. [Summary & Recommendations](#summary--recommendations)

---

## Methodology

### Environment

- **CPU:** [TBD]
- **RAM:** [TBD]
- **OS:** [TBD]
- **Python:** [TBD]
- **Benchmark Script:** `benchmarks/run_benchmarks.py`

### Measurement Approach

All benchmarks use `time.perf_counter()` for high-resolution wall-clock timing.
Each benchmark includes:

1. **Warm-up runs** before timing begins (to allow JIT compilation, cache warming, etc.)
2. **Multiple iterations** (configurable, default 5) with statistical aggregation
3. **Graceful degradation** — unavailable components are skipped with clear reporting
4. **Statistical reporting:** mean, median, p95, p99, min, max, standard deviation

### Output

- **stdout:** Formatted text tables with human-readable units
- **JSON:** Detailed results saved to `benchmarks/results/benchmark_results.json`

---

## Parquet Query Performance

### Goal

Compare read, filter, aggregate, and write performance across three engines:
Pandas (CPU single-threaded), DuckDB (columnar in-process OLAP), and PySpark (distributed processing with local[*] mode).

### Configuration

- **Rows:** 100,000 (customizable via `--parquet-rows`)
- **Columns:** 15 (event_id, user_id, event_type, product_id, timestamp, event_ts, page, referrer, duration_ms, device, browser, value, category_id, processed_at, processing_date)
- **Compression:** Snappy
- **Queries:**
  - Filter + group-by: `WHERE event_type = 'purchase' GROUP BY device`
  - Complex aggregation: `GROUP BY event_type, device` with sum/count

### Expected Performance Targets

| Metric              | Pandas       | DuckDB       | PySpark (local) |
|---------------------|-------------|-------------|-----------------|
| Read (100K rows)    | < 100 ms     | < 50 ms      | < 500 ms        |
| Filter Query        | < 20 ms      | < 10 ms      | < 100 ms        |
| Aggregation         | < 50 ms      | < 20 ms      | < 200 ms        |
| Write Parquet       | < 200 ms     | N/A (reader) | < 1 s           |

### Results

> **Results will be populated after running:**
> ```bash
> cd benchmarks && python run_benchmarks.py --parquet-rows 100000
> ```

<!-- PLACEHOLDER: Parquet results table -->

### Analysis

[TBD — compare engines, identify bottlenecks, recommend deployment strategy]

---

## Vector Search Performance

### Milvus Vector Search

#### Goal

Measure query latency and QPS for vector similarity search at different dataset sizes and top_k values.

#### Configuration

- **Vector dimension:** 384 (paraphrase-multilingual-MiniLM-L12-v2)
- **Index type:** IVF_FLAT (with nlist proportional to dataset size)
- **Metric:** Inner Product (IP) — equivalent to cosine similarity for normalized vectors
- **Dataset sizes:** 100, 1,000, 10,000, 100,000
- **Top-K values:** 1, 5, 10, 50, 100
- **nprobe:** 16

#### Expected Performance Targets

| Dataset Size | Top-K=1   | Top-K=10  | Top-K=100 |
|-------------|-----------|-----------|-----------|
| 100         | < 1 ms    | < 1 ms    | < 2 ms    |
| 1,000       | < 1 ms    | < 1 ms    | < 3 ms    |
| 10,000      | < 2 ms    | < 3 ms    | < 5 ms    |
| 100,000     | < 5 ms    | < 10 ms   | < 20 ms   |

> **Results will be populated after running (requires Milvus):**
> ```bash
> cd benchmarks && python run_benchmarks.py --parquet-rows 1000
> ```

<!-- PLACEHOLDER: Milvus results table -->

### FAISS Local Search (Fallback)

When Milvus is unavailable, the benchmark suite falls back to local FAISS (IndexFlatIP) for baseline comparison.

#### Configuration

- **Index type:** IndexFlatIP (exact search, brute-force)
- **Dataset sizes:** 1,000, 10,000, 100,000

#### Expected Performance Targets

| Dataset Size | Top-K=1   | Top-K=10  | Top-K=100 |
|-------------|-----------|-----------|-----------|
| 1,000       | < 1 ms    | < 1 ms    | < 1 ms    |
| 10,000      | < 1 ms    | < 2 ms    | < 3 ms    |
| 100,000     | < 10 ms   | < 10 ms   | < 15 ms   |

> **Results will be populated after running (requires faiss-cpu):**
> ```bash
> cd benchmarks && python run_benchmarks.py
> ```

<!-- PLACEHOLDER: FAISS results table -->

### Analysis

[TBD — compare Milvus vs FAISS, assess scalability, recommend for production vs development use cases]

---

## Embedding Throughput

### Goal

Measure sentence-transformers encoding throughput (texts/second) at different batch sizes to determine the optimal configuration for production pipelines.

### Configuration

- **Model:** paraphrase-multilingual-MiniLM-L12-v2 (384 dimensions)
- **Input:** 10,000 synthetic Chinese-language user event descriptions
- **Batch sizes:** 1, 8, 32, 128, 512
- **Normalization:** L2 normalization enabled (for cosine similarity with IP metric)

### Expected Performance Targets

| Batch Size | Throughput (texts/s) | Latency (s) | GB/s     |
|-----------|---------------------|-------------|----------|
| 1         | > 10                | < 1000      | N/A      |
| 8         | > 50                | < 200       | N/A      |
| 32        | > 100               | < 100       | N/A      |
| 128       | > 200               | < 50        | > 0.02   |
| 512       | > 300               | < 35        | > 0.03   |

> **Results will be populated after running (requires sentence-transformers):**
> ```bash
> cd benchmarks && python run_benchmarks.py --embedding-texts 10000
> ```

<!-- PLACEHOLDER: Embedding throughput results table -->

### Analysis

[TBD — identify optimal batch size, compare CPU vs GPU (if available), recommend for production throughput requirements]

---

## Summary & Recommendations

### Overall Performance Summary

| Component        | Status     | Throughput        | Latency (p95)   | Notes |
|-----------------|------------|-------------------|-----------------|-------|
| Parquet (Pandas) | [TBD]      | [TBD] rows/s      | [TBD]           |       |
| Parquet (DuckDB) | [TBD]      | [TBD] rows/s      | [TBD]           |       |
| Parquet (PySpark)| [TBD]      | [TBD] rows/s      | [TBD]           |       |
| Vector Search    | [TBD]      | [TBD] QPS         | [TBD] ms        |       |
| Embedding        | [TBD]      | [TBD] texts/s     | [TBD] s         |       |

### Recommendations

1. **For Parquet queries in development:** DuckDB provides the best single-machine performance for analytical queries on local Parquet files.
2. **For production ETL:** PySpark is recommended for large-scale distributed processing (>10M rows).
3. **For vector search in production:** Milvus with IVF_FLAT or HNSW index provides scalable, low-latency similarity search.
4. **For embedding generation:** Use batch size >= 32 for optimal throughput; batch size 128-512 is recommended for production pipelines.

### Related Project Components

- **Parquet processing:** `src/spark/process_data.py`, `src/spark/query_benchmark.py`
- **Vector search:** `demo_vector/embed.py`, `demo_vector/query_api.py`
- **dbt data models:** `dbt/models/clean/` (dim_users, dim_products, fct_user_events_daily)
- **CI pipeline:** `.github/workflows/ci.yml`, `.github/workflows/vector-ci.yml`
- **Smoke test:** `scripts/ci_smoke_test.sh`

### Running Benchmarks

```bash
# Full suite
cd benchmarks && python run_benchmarks.py

# Custom configuration
python run_benchmarks.py --parquet-rows 500000 --iterations 10 --embedding-texts 50000

# Skip unavailable components
python run_benchmarks.py --skip-vector --skip-embedding

# View results
cat benchmarks/results/benchmark_results.json | python -m json.tool
```

---

*Report generated by the Data Platform Performance Benchmark Suite.*
