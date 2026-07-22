#!/usr/bin/env python3
"""
Iceberg 湖仓集成脚本 — 将 Parquet 数据迁移到 Apache Iceberg 格式。

支持两种运行模式:
  1. 真实模式: 使用 PyIceberg 连接到 Hive Metastore / REST Catalog
  2. 模拟模式: 生成 Iceberg 原理说明文档（当环境未就绪时）

用法:
    python iceberg_migrate.py [--mode real|simulate]
"""

import argparse
import os
import time
from datetime import datetime
from pathlib import Path


def simulate_iceberg_migration(input_path: str, output_path: str):
    """
    模拟 Iceberg 迁移 — 生成原理说明文档和脚本框架。

    当 Iceberg 环境未完整就绪时，此模式:
      1. 统计现有 Parquet 文件
      2. 生成 Iceberg DDL 脚本
      3. 输出 Iceberg 湖仓架构说明
    """
    print("=" * 60)
    print("  Apache Iceberg 湖仓集成 — 模拟模式")
    print("=" * 60)

    # 统计 Parquet 文件
    parquet_count = 0
    total_size = 0
    for root, dirs, files in os.walk(input_path):
        for f in files:
            fp = os.path.join(root, f)
            total_size += os.path.getsize(fp)
            parquet_count += 1

    size_mb = total_size / (1024 * 1024)
    print(f"\n  📊 现有 Parquet 数据")
    print(f"     文件数: {parquet_count}")
    print(f"     总大小: {size_mb:.2f} MB")
    print(f"     路径:   {input_path}")

    # 生成 DDL 脚本
    ddl = f"""
-- ==========================================
-- Apache Iceberg 湖仓 DDL
-- 将 Parquet → Iceberg 表迁移脚本
-- 生成时间: {datetime.now().isoformat()}
-- ==========================================

-- 1. 创建 Iceberg Catalog
CREATE CATALOG data_lakehouse
  USING iceberg
  WITH (
    'type'             = 'hadoop',
    'warehouse'        = '{output_path}',
    'format-version'   = '2'
  );

-- 2. 创建 Iceberg 表
CREATE TABLE data_lakehouse.raw.user_events (
    event_id      STRING,
    user_id       STRING,
    event_type    STRING,
    product_id    STRING,
    event_ts      TIMESTAMP,
    page          STRING,
    referrer      STRING,
    duration_ms   BIGINT,
    device        STRING,
    browser       STRING,
    processed_at  TIMESTAMP,
    processing_date DATE
)
USING iceberg
PARTITIONED BY (processing_date, event_type)
LOCATION '{output_path}/user_events'
TBLPROPERTIES (
    'write.format.default'  = 'parquet',
    'write.parquet.compression-codec' = 'snappy',
    'history.expire.max-snapshot-age-ms' = '604800000'
);

-- 3. 从现有 Parquet 加载数据
INSERT INTO data_lakehouse.raw.user_events
SELECT * FROM parquet.`{input_path}`;

-- 4. 时间旅行查询示例
-- SELECT * FROM data_lakehouse.raw.user_events
--   VERSION AS OF '2026-07-20 10:00:00';

-- 5. 增量读取（仅读取变更）
-- SELECT * FROM data_lakehouse.raw.user_events
--   WHERE processed_at > '2026-07-21 00:00:00';
"""

    ddl_path = os.path.join(output_path, "iceberg_migration.sql")
    os.makedirs(output_path, exist_ok=True)
    with open(ddl_path, "w") as f:
        f.write(ddl)

    print(f"\n  ✅ Iceberg DDL 脚本已生成: {ddl_path}")

    # 原理说明
    doc = """
=========================================
Apache Iceberg 湖仓架构说明
=========================================

1. 什么是 Iceberg？
   Iceberg 是一种高性能的开放表格式，用于大型分析表。
   它允许 SQL 表在数据湖（如 S3/HDFS）上像数据仓库一样工作。

2. 核心优势
   ├── 时间旅行 (Time Travel): 查询历史快照，回滚误操作
   ├── 分区演进: 可以在线修改分区策略，无需重写数据
   ├── 增量读取: 增量消费变更数据，降低处理延迟
   ├── ACID 事务: 保证读写隔离，防止脏读
   └── Schema 演进: 安全的列增删改，避免数据损坏

3. 与项目集成方式
   ┌─────────────┐     ┌──────────────┐     ┌──────────────────┐
   │ Kafka/JSONL  │ --> │ PySpark 清洗  │ --> │ Parquet 文件     │
   └─────────────┘     └──────────────┘     │                  │
                                             │  Iceberg Table   │
   ┌─────────────┐     ┌──────────────┐     │  metadata/       │
   │ DuckDB/Trino│ <-- │ 分析查询      │ <-- │  data/           │
   └─────────────┘     └──────────────┘     └──────────────────┘

4. 适用场景
   - 需要数据版本管理和审计
   - 大规模分区表频繁更新
   - 多引擎同时读写同一表
"""

    doc_path = os.path.join(output_path, "iceberg_principles.md")
    with open(doc_path, "w") as f:
        f.write(doc)
    print(f"  ✅ Iceberg 原理文档已生成: {doc_path}")

    print("\n" + "=" * 60)
    print("  Iceberg 集成模拟完成")
    print("=" * 60)


def real_iceberg_migration(input_path: str, output_path: str):
    """真实 Iceberg 迁移（需 PyIceberg + Hive Metastore）。"""
    try:
        from pyiceberg.catalog import load_catalog
        from pyiceberg.schema import Schema
        from pyiceberg.types import (
            StringType,
            LongType,
            TimestampType,
            DateType,
            NestedField,
        )

        print("=" * 60)
        print("  Apache Iceberg 湖仓集成 — 真实模式")
        print("=" * 60)

        # 定义 Schema
        schema = Schema(
            NestedField(1, "event_id", StringType(), required=True),
            NestedField(2, "user_id", StringType(), required=True),
            NestedField(3, "event_type", StringType()),
            NestedField(4, "product_id", StringType()),
            NestedField(5, "event_ts", TimestampType()),
            NestedField(6, "page", StringType()),
            NestedField(7, "referrer", StringType()),
            NestedField(8, "duration_ms", LongType()),
            NestedField(9, "device", StringType()),
            NestedField(10, "browser", StringType()),
            NestedField(11, "processed_at", TimestampType()),
            NestedField(12, "processing_date", DateType()),
        )

        # 加载 Catalog
        catalog = load_catalog(
            "data_lakehouse",
            **{
                "type": "hadoop",
                "warehouse": output_path,
            },
        )

        # 创建 Namespace
        try:
            catalog.create_namespace("raw")
        except Exception:
            pass

        # 创建表
        table = catalog.create_table_if_not_exists(
            "raw.user_events",
            schema=schema,
            location=f"{output_path}/user_events",
            partition_spec=None,
        )

        print(f"  ✅ Iceberg 表已创建: {table.identifier}")
        print(f"     Location: {table.location()}")

        # 从 PySpark DataFrame 加载数据到 Iceberg
        from pyspark.sql import SparkSession

        spark = (
            SparkSession.builder.appName("IcebergMigration")
            .config(
                "spark.sql.extensions",
                "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions",
            )
            .config("spark.sql.catalog.data_lakehouse", "org.apache.iceberg.spark.SparkCatalog")
            .config("spark.sql.catalog.data_lakehouse.type", "hadoop")
            .config("spark.sql.catalog.data_lakehouse.warehouse", output_path)
            .getOrCreate()
        )

        df = spark.read.parquet(input_path)
        count = df.count()
        df.writeTo("data_lakehouse.raw.user_events").append()
        print(f"  ✅ 已写入 {count} 行到 Iceberg 表")

        spark.stop()

    except ImportError:
        print("⚠️  PyIceberg 未安装，回退到模拟模式")
        simulate_iceberg_migration(input_path, output_path)
    except Exception as e:
        print(f"⚠️  Iceberg 迁移失败: {e}")
        print("  回退到模拟模式...")
        simulate_iceberg_migration(input_path, output_path)


def main():
    parser = argparse.ArgumentParser(description="Iceberg 湖仓集成")
    parser.add_argument(
        "--input",
        default="data/output_parquet",
        help="Parquet 输入路径",
    )
    parser.add_argument(
        "--output",
        default="data/iceberg_warehouse",
        help="Iceberg Warehouse 路径",
    )
    parser.add_argument(
        "--mode",
        choices=["real", "simulate"],
        default="simulate",
        help="运行模式: real=真实迁移, simulate=生成脚本和文档",
    )
    args = parser.parse_args()

    if args.mode == "real":
        real_iceberg_migration(args.input, args.output)
    else:
        simulate_iceberg_migration(args.input, args.output)


if __name__ == "__main__":
    main()
