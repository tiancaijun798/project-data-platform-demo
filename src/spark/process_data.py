#!/usr/bin/env python3
"""
PySpark 数据处理脚本 — 读取 JSONL 原始日志，清洗转换后输出 Parquet 结构化文件。

用法（本地）:
    python process_data.py --input data/input.jsonl --output data/output_parquet

用法（spark-submit）:
    spark-submit process_data.py --input data/input.jsonl --output data/output_parquet
"""

import argparse
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from pyspark.sql import SparkSession, DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import (
    StructType,
    StructField,
    StringType,
    LongType,
    TimestampType,
)


# ---- JSONL 输入 Schema ----
INPUT_SCHEMA = StructType(
    [
        StructField("event_id", StringType(), True),
        StructField("user_id", StringType(), True),
        StructField("event_type", StringType(), True),
        StructField("product_id", StringType(), True),
        StructField("timestamp", StringType(), True),
        StructField("page", StringType(), True),
        StructField("referrer", StringType(), True),
        StructField("duration_ms", LongType(), True),
        StructField("device", StringType(), True),
        StructField("browser", StringType(), True),
    ]
)


def create_spark(app_name: str = "DataPlatformDemo") -> SparkSession:
    """创建并返回 PySpark Session。"""
    return (
        SparkSession.builder.appName(app_name)
        .config("spark.sql.adaptive.enabled", "true")
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true")
        .config("spark.sql.parquet.compression.codec", "snappy")
        .config("spark.sql.sources.partitionOverwriteMode", "dynamic")
        .master("local[*]")
        .getOrCreate()
    )


def read_jsonl(spark: SparkSession, input_path: str) -> DataFrame:
    """读取 JSONL 文件为 DataFrame。"""
    print(f"  📖 读取: {input_path}")

    df = (
        spark.read.format("json")
        .option("mode", "PERMISSIVE")  # 容忍脏数据
        .option("columnNameOfCorruptRecord", "_corrupt_record")
        .schema(INPUT_SCHEMA)
        .load(input_path)
    )

    total = df.count()
    print(f"     原始行数: {total}")
    return df


def clean_data(df: DataFrame) -> DataFrame:
    """数据清洗与转换。"""
    print("  🧹 数据清洗...")

    # 1. 去除 event_id / user_id 为空的脏数据
    before = df.count()
    df = df.dropna(subset=["event_id", "user_id"])
    after_drop = df.count()
    print(f"     去空核心字段: {before} → {after_drop}（丢弃 {before - after_drop}）")

    # 2. 解析 timestamp 字符串为 TimestampType
    df = df.withColumn(
        "event_ts",
        F.to_timestamp(F.col("timestamp"), "yyyy-MM-dd'T'HH:mm:ss.SSSSSSXXX"),
    ).withColumn(
        "event_ts",
        F.coalesce(
            F.col("event_ts"),
            F.to_timestamp(F.col("timestamp"), "yyyy-MM-dd'T'HH:mm:ssXXX"),
            F.to_timestamp(F.col("timestamp"), "yyyy-MM-dd'T'HH:mm:ss"),
        ),
    )

    # 3. 统一 event_type 为小写
    df = df.withColumn("event_type", F.lower(F.col("event_type")))

    # 4. 填充 product_id 缺失值
    df = df.withColumn(
        "product_id", F.coalesce(F.col("product_id"), F.lit("unknown"))
    )

    # 5. 填充 referrer 缺失值
    df = df.withColumn(
        "referrer", F.coalesce(F.col("referrer"), F.lit("direct"))
    )

    # 6. 过滤异常 duration_ms（负值或超大值）
    before = df.count()
    df = df.filter(
        (F.col("duration_ms").isNull()) | (F.col("duration_ms") >= 0)
    )
    df = df.filter(
        (F.col("duration_ms").isNull()) | (F.col("duration_ms") <= 300_000)
    )
    print(f"     过滤异常时长: {before} → {df.count()}")

    # 7. 添加处理元数据列
    df = df.withColumn("processed_at", F.current_timestamp()).withColumn(
        "processing_date", F.current_date()
    )

    return df


def write_parquet(df: DataFrame, output_path: str) -> int:
    """写入分区 Parquet 文件。返回写入行数。"""
    print(f"  💾 写入: {output_path}")

    count = df.count()

    df.write.mode("overwrite").partitionBy("processing_date", "event_type").parquet(
        output_path
    )

    print(f"     分区字段: processing_date, event_type")
    print(f"     写入行数: {count}")

    # 统计分区数
    partition_count = (
        df.select("processing_date", "event_type").distinct().count()
    )
    print(f"     分区组合: {partition_count}")

    return count


def print_stats(raw_count: int, clean_count: int, output_path: str):
    """打印处理统计报告。"""
    print("\n" + "=" * 50)
    print("  📊 处理统计报告")
    print("=" * 50)
    print(f"  原始行数:     {raw_count}")
    print(f"  清洗后行数:   {clean_count}")
    print(f"  丢弃行数:     {raw_count - clean_count}")
    print(f"  保留率:       {clean_count / raw_count * 100:.1f}%" if raw_count else "")
    print(f"  输出路径:     {output_path}")

    # 文件大小
    total_size = 0
    file_count = 0
    for root, dirs, files in os.walk(output_path):
        for f in files:
            fp = os.path.join(root, f)
            total_size += os.path.getsize(fp)
            file_count += 1
    size_mb = total_size / (1024 * 1024)
    print(f"  输出文件数:   {file_count}")
    print(f"  输出大小:     {size_mb:.2f} MB")

    # Parquet 优势说明
    raw_estimate = clean_count * 512 / (1024 * 1024)  # rough JSONL estimate
    if raw_estimate > 0:
        print(f"  压缩比:       {size_mb / raw_estimate * 100:.1f}% (vs JSONL 估算)")
    print("=" * 50)


def main():
    parser = argparse.ArgumentParser(
        description="PySpark JSONL → Parquet 数据处理"
    )
    parser.add_argument("--input", default="data/input.jsonl", help="输入 JSONL 路径")
    parser.add_argument(
        "--output", default="data/output_parquet", help="输出 Parquet 路径"
    )
    args = parser.parse_args()

    print("=" * 50)
    print("  PySpark 数据处理 — JSONL → Parquet")
    print("=" * 50)
    print(f"  输入: {args.input}")
    print(f"  输出: {args.output}")
    print("-" * 50)

    start = time.time()

    spark = create_spark()

    try:
        df_raw = read_jsonl(spark, args.input)
        raw_count = df_raw.count()

        df_clean = clean_data(df_raw)
        clean_count = write_parquet(df_clean, args.output)

        elapsed = time.time() - start
        print(f"\n  总耗时: {elapsed:.2f}s")
        print_stats(raw_count, clean_count, args.output)

    finally:
        spark.stop()

    print("\n✅ PySpark 任务完成")


if __name__ == "__main__":
    main()
