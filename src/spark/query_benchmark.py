#!/usr/bin/env python3
"""
多引擎查询性能对比 — DuckDB vs Trino vs PySpark。

在聚合查询场景下测试不同引擎的性能差异，生成对比报告。

用法:
    python query_benchmark.py [--input data/output_parquet]
"""

import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path


QUERIES = {
    "daily_event_count": """
        SELECT processing_date, COUNT(*) AS cnt
        FROM events
        GROUP BY processing_date
        ORDER BY processing_date
    """,
    "user_activity_rank": """
        SELECT user_id, COUNT(*) AS event_count
        FROM events
        GROUP BY user_id
        ORDER BY event_count DESC
        LIMIT 10
    """,
    "event_type_distribution": """
        SELECT event_type, COUNT(*) AS cnt,
               ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2) AS pct
        FROM events
        GROUP BY event_type
        ORDER BY cnt DESC
    """,
    "hourly_heatmap": """
        SELECT
            HOUR(event_ts) AS hour,
            event_type,
            COUNT(*) AS cnt
        FROM events
        WHERE event_ts IS NOT NULL
        GROUP BY HOUR(event_ts), event_type
        ORDER BY hour, event_type
    """,
}


def benchmark_pyspark(input_path: str) -> dict:
    """PySpark 查询性能测试。"""
    print("\n  🔥 PySpark 查询基准测试...")
    results = {}

    try:
        from pyspark.sql import SparkSession

        spark = (
            SparkSession.builder.appName("QueryBenchmark")
            .master("local[*]")
            .getOrCreate()
        )

        df = spark.read.parquet(input_path)
        df.createOrReplaceTempView("events")
        total_rows = df.count()
        print(f"    数据行数: {total_rows}")

        for name, query in QUERIES.items():
            start = time.time()
            result = spark.sql(query)
            row_count = result.count()  # 触达执行
            elapsed = time.time() - start
            results[name] = {"engine": "PySpark", "elapsed_s": round(elapsed, 3), "row_count": row_count}
            print(f"    {name}: {elapsed:.3f}s ({row_count} rows)")

        spark.stop()
    except ImportError:
        print("    ⚠️ PySpark 未安装")
        results = {name: {"engine": "PySpark", "elapsed_s": None, "error": "not_installed"} for name in QUERIES}
    except Exception as e:
        print(f"    ❌ PySpark 错误: {e}")
        results = {name: {"engine": "PySpark", "elapsed_s": None, "error": str(e)} for name in QUERIES}

    return results


def benchmark_duckdb(input_path: str) -> dict:
    """DuckDB 查询性能测试。"""
    print("\n  🦆 DuckDB 查询基准测试...")
    results = {}

    try:
        import duckdb

        con = duckdb.connect()
        # DuckDB 可以直接查询 Parquet
        con.execute(
            f"CREATE VIEW events AS SELECT * FROM '{input_path}/**/*.parquet'"
        )
        total_rows = con.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        print(f"    数据行数: {total_rows}")

        for name, query in QUERIES.items():
            start = time.time()
            result = con.execute(query).fetchall()
            elapsed = time.time() - start
            results[name] = {"engine": "DuckDB", "elapsed_s": round(elapsed, 3), "row_count": len(result)}
            print(f"    {name}: {elapsed:.3f}s ({len(result)} rows)")

        con.close()
    except ImportError:
        print("    ⚠️ DuckDB 未安装 (pip install duckdb)")
        results = {name: {"engine": "DuckDB", "elapsed_s": None, "error": "not_installed"} for name in QUERIES}
    except Exception as e:
        print(f"    ❌ DuckDB 错误: {e}")
        results = {name: {"engine": "DuckDB", "elapsed_s": None, "error": str(e)} for name in QUERIES}

    return results


def generate_comparison_report(pyspark_results: dict, duckdb_results: dict, output_path: str):
    """生成引擎对比报告。"""
    os.makedirs(output_path, exist_ok=True)

    # 收集所有支持的引擎结果
    all_results = {}
    for query_name in QUERIES:
        all_results[query_name] = {
            "PySpark": pyspark_results.get(query_name, {}),
            "DuckDB": duckdb_results.get(query_name, {}),
        }

    # 生成 JSON 报告
    report = {
        "timestamp": datetime.now().isoformat(),
        "queries": QUERIES,
        "results": all_results,
        "summary": {},
    }

    # 计算各引擎平均性能
    for engine in ["PySpark", "DuckDB"]:
        valid_times = [
            all_results[q][engine]["elapsed_s"]
            for q in QUERIES
            if all_results[q][engine].get("elapsed_s") is not None
        ]
        if valid_times:
            report["summary"][engine] = {
                "avg_elapsed_s": round(sum(valid_times) / len(valid_times), 3),
                "min_elapsed_s": round(min(valid_times), 3),
                "max_elapsed_s": round(max(valid_times), 3),
                "queries_run": len(valid_times),
            }

    # 保存 JSON
    json_path = os.path.join(output_path, "query_benchmark_report.json")
    with open(json_path, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\n  ✅ JSON 报告: {json_path}")

    # 生成 Markdown 报告
    md_lines = [
        "# 多引擎查询性能对比报告",
        f"\n生成时间: {datetime.now().isoformat()}",
        "\n## 测试查询",
    ]
    for name, query in QUERIES.items():
        md_lines.append(f"\n### {name}")
        md_lines.append("```sql")
        md_lines.append(query.strip())
        md_lines.append("```")

    md_lines.append("\n## 性能对比\n")
    md_lines.append("| 查询 | PySpark (s) | DuckDB (s) | 胜出 |")
    md_lines.append("|------|------------|-----------|------|")

    for q_name in QUERIES:
        ps = all_results[q_name].get("PySpark", {}).get("elapsed_s", "N/A")
        dd = all_results[q_name].get("DuckDB", {}).get("elapsed_s", "N/A")
        if isinstance(ps, (int, float)) and isinstance(dd, (int, float)):
            winner = "PySpark 🏆" if ps < dd else "DuckDB 🦆"
        else:
            winner = "—"
        md_lines.append(f"| {q_name} | {ps} | {dd} | {winner} |")

    md_lines.append("\n## 结论\n")
    if report["summary"]:
        for engine, stats in report["summary"].items():
            md_lines.append(
                f"- **{engine}**: 平均 {stats['avg_elapsed_s']}s "
                f"(min: {stats['min_elapsed_s']}s, max: {stats['max_elapsed_s']}s)"
            )

    md_lines.append("\n### DuckDB 优势场景")
    md_lines.append("- 单机分析，数据量 < 100GB")
    md_lines.append("- 零配置部署，适合开发调试")
    md_lines.append("- OLAP 聚合查询性能优异")
    md_lines.append("\n### PySpark 优势场景")
    md_lines.append("- 分布式海量数据处理")
    md_lines.append("- 需要与其他大数据组件集成")
    md_lines.append("- 生产环境高可用、高吞吐")

    md_path = os.path.join(output_path, "query_benchmark_report.md")
    with open(md_path, "w") as f:
        f.write("\n".join(md_lines))
    print(f"  ✅ Markdown 报告: {md_path}")


def main():
    parser = argparse.ArgumentParser(description="多引擎查询性能对比")
    parser.add_argument("--input", default="data/output_parquet", help="Parquet 输入路径")
    args = parser.parse_args()

    print("=" * 60)
    print("  多引擎查询性能基准测试")
    print(f"  数据源: {args.input}")
    print("=" * 60)

    pyspark_results = benchmark_pyspark(args.input)
    duckdb_results = benchmark_duckdb(args.input)

    report_dir = "data/benchmark_reports"
    generate_comparison_report(pyspark_results, duckdb_results, report_dir)

    print("\n" + "=" * 60)
    print("  ✅ 基准测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
