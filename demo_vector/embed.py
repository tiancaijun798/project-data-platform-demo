#!/usr/bin/env python3
"""
Embedding 生成脚本 — 从 Parquet/dbt 数据生成文本 embedding 并写入 Milvus。

数据源:
    1. Parquet 用户事件数据 (data/output_parquet/)
    2. dbt 维度表 (dim_users, dim_products) → PostgreSQL 读取

输出:
    - Milvus Collection: user_events_vectors (用户事件语义向量)
    - Milvus Collection: product_vectors (商品语义向量)

用法:
    python embed.py --source parquet --input data/output_parquet
    python embed.py --source postgres --limit 5000
    python embed.py --all
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    connections,
    utility,
)
from sentence_transformers import SentenceTransformer


# ---- 配置 ----
MILVUS_HOST = os.getenv("MILVUS_HOST", "localhost")
MILVUS_PORT = os.getenv("MILVUS_PORT", "19530")
EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2"
)
BATCH_SIZE = 128
VECTOR_DIM = 384  # MiniLM-L12-v2 输出维度


# ---- Milvus Collection Schema ----
def create_event_collection() -> Collection:
    """创建用户事件向量集合。"""
    collection_name = "user_events_vectors"

    if utility.has_collection(collection_name):
        print(f"  ⚠️  集合 '{collection_name}' 已存在，将删除重建...")
        utility.drop_collection(collection_name)

    fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="event_id", dtype=DataType.VARCHAR, max_length=64),
        FieldSchema(name="user_id", dtype=DataType.VARCHAR, max_length=32),
        FieldSchema(name="event_type", dtype=DataType.VARCHAR, max_length=32),
        FieldSchema(name="product_id", dtype=DataType.VARCHAR, max_length=64),
        FieldSchema(name="text_content", dtype=DataType.VARCHAR, max_length=1024),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=VECTOR_DIM),
        FieldSchema(name="event_ts", dtype=DataType.INT64),  # Unix timestamp
    ]

    schema = CollectionSchema(fields, description="用户事件语义向量集合")
    collection = Collection(collection_name, schema)

    # 创建向量索引 (IVF_FLAT)
    index_params = {
        "metric_type": "IP",  # Inner Product (cosine similarity after normalization)
        "index_type": "IVF_FLAT",
        "params": {"nlist": 128},
    }
    collection.create_index("embedding", index_params)
    print(f"  ✅ 集合 '{collection_name}' 创建完成 (IVF_FLAT, nlist=128)")

    return collection


def create_product_collection() -> Collection:
    """创建商品向量集合。"""
    collection_name = "product_vectors"

    if utility.has_collection(collection_name):
        print(f"  ⚠️  集合 '{collection_name}' 已存在，将删除重建...")
        utility.drop_collection(collection_name)

    fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="product_id", dtype=DataType.VARCHAR, max_length=64),
        FieldSchema(name="text_content", dtype=DataType.VARCHAR, max_length=1024),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=VECTOR_DIM),
        FieldSchema(name="total_views", dtype=DataType.INT64),
        FieldSchema(name="total_purchases", dtype=DataType.INT64),
    ]

    schema = CollectionSchema(fields, description="商品语义向量集合")
    collection = Collection(collection_name, schema)

    index_params = {
        "metric_type": "IP",
        "index_type": "IVF_FLAT",
        "params": {"nlist": 128},
    }
    collection.create_index("embedding", index_params)
    print(f"  ✅ 集合 '{collection_name}' 创建完成 (IVF_FLAT, nlist=128)")

    return collection


# ---- 文本构造 ----
def build_event_text(row: dict) -> str:
    """将事件行构造为可语义检索的自然语言文本。"""
    parts = []
    parts.append(f"事件类型: {row.get('event_type', 'unknown')}")
    parts.append(f"用户: {row.get('user_id', 'unknown')}")
    if row.get("product_id") and row["product_id"] != "unknown":
        parts.append(f"商品: {row['product_id']}")
    if row.get("page"):
        parts.append(f"页面: {row['page']}")
    if row.get("referrer") and row["referrer"] != "direct":
        parts.append(f"来源: {row['referrer']}")
    if row.get("device"):
        parts.append(f"设备: {row['device']}")
    if row.get("browser"):
        parts.append(f"浏览器: {row['browser']}")
    return "，".join(parts)


def build_product_text(row: dict) -> str:
    """将商品行构造为可语义检索的自然语言文本。"""
    parts = [f"商品ID: {row.get('product_id', 'unknown')}"]
    if row.get("total_views"):
        parts.append(f"浏览次数: {row['total_views']}")
    if row.get("total_purchases"):
        parts.append(f"购买次数: {row['total_purchases']}")
    if row.get("conversion_rate_pct"):
        parts.append(f"转化率: {row['conversion_rate_pct']}%")
    return "，".join(parts)


# ---- Embedding 生成 & 写入 ----
class EmbeddingPipeline:
    """Embedding 生成与入库流水线。"""

    def __init__(self):
        self.model = SentenceTransformer(EMBEDDING_MODEL)
        print(f"  🤖 加载模型: {EMBEDDING_MODEL} (dim={VECTOR_DIM})")

    def encode_batch(self, texts: list[str]) -> np.ndarray:
        """批量编码文本为归一化向量。"""
        embeddings = self.model.encode(
            texts,
            batch_size=BATCH_SIZE,
            show_progress_bar=True,
            normalize_embeddings=True,  # L2 归一化，配合 IP 度量 = cosine similarity
        )
        return embeddings

    def ingest_parquet(self, input_path: str,
                       event_col: Collection,
                       product_col: Optional[Collection] = None) -> dict:
        """从 Parquet 目录读取数据，生成 embedding 并写入 Milvus。"""
        print(f"\n{'='*50}")
        print(f"  📖 Parquet → Embedding → Milvus")
        print(f"  输入路径: {input_path}")
        print(f"{'='*50}")

        # 读取所有 Parquet 文件
        try:
            df = pq.read_table(input_path).to_pandas()
        except Exception:
            # 可能是分区目录，遍历读取
            dfs = []
            for root, dirs, files in os.walk(input_path):
                for f in files:
                    if f.endswith(".parquet"):
                        fp = os.path.join(root, f)
                        dfs.append(pq.read_table(fp).to_pandas())
            if not dfs:
                print("  ❌ 未找到 Parquet 文件！")
                return {"error": "no parquet files found"}
            df = pd.concat(dfs, ignore_index=True)

        total = len(df)
        print(f"  原始行数: {total}")

        # 采样（如果数据量太大）
        if total > 10000:
            df = df.sample(n=10000, random_state=42)
            print(f"  ⚠️  数据量较大，采样至 {len(df)} 行")
            total = len(df)

        # 构造文本
        print("  📝 构造事件文本...")
        texts = []
        records = []
        for _, row in df.iterrows():
            row_dict = row.to_dict()
            text = build_event_text(row_dict)
            texts.append(text)
            records.append(row_dict)

        # 批量编码
        print(f"  🧮 生成 embedding ({len(texts)} 条)...")
        t0 = time.time()
        embeddings = self.encode_batch(texts)
        encode_time = time.time() - t0
        print(f"     ⏱  编码耗时: {encode_time:.2f}s ({len(texts)/encode_time:.0f} 条/秒)")

        # 写入 Milvus
        print("  💾 写入 Milvus...")
        t0 = time.time()
        insert_data = []
        for i, rec in enumerate(records):
            ts_str = rec.get("timestamp", "")
            try:
                event_ts = int(pd.Timestamp(ts_str).timestamp())
            except Exception:
                event_ts = 0

            insert_data.append({
                "event_id": str(rec.get("event_id", f"evt_{i}")),
                "user_id": str(rec.get("user_id", "unknown")),
                "event_type": str(rec.get("event_type", "unknown")),
                "product_id": str(rec.get("product_id", "unknown")),
                "text_content": texts[i][:1024],
                "embedding": embeddings[i].tolist(),
                "event_ts": event_ts,
            })

        # 分批插入
        for start in range(0, len(insert_data), BATCH_SIZE):
            batch = insert_data[start:start + BATCH_SIZE]
            event_col.insert(batch)

        insert_time = time.time() - t0
        event_col.flush()

        stats = {
            "source": "parquet",
            "total_rows": total,
            "encode_time_s": round(encode_time, 2),
            "encode_speed": round(len(texts) / encode_time, 0),
            "insert_time_s": round(insert_time, 2),
            "collection": event_col.name,
        }

        print(f"     ⏱  写入耗时: {insert_time:.2f}s")
        print(f"  ✅ 完成! {total} 条 embedding 已写入 '{event_col.name}'")

        return stats

    def ingest_postgres(self, event_col: Collection,
                        product_col: Optional[Collection] = None,
                        limit: int = 5000) -> dict:
        """从 PostgreSQL 读取 dbt 维度表数据，生成 embedding 并写入。"""
        import sqlalchemy as sa

        DB_HOST = os.getenv("DATA_PLATFORM_DB_HOST", "localhost")
        DB_PORT = os.getenv("DATA_PLATFORM_DB_PORT", "5432")
        DB_USER = os.getenv("DATA_PLATFORM_DB_USER", "admin")
        DB_PASSWORD = os.getenv("DATA_PLATFORM_DB_PASSWORD", "changeme")
        DB_NAME = os.getenv("DATA_PLATFORM_DB_NAME", "data_platform")

        db_url = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        engine = sa.create_engine(db_url)

        stats = {"source": "postgres", "collections": {}}

        # ---- 商品向量 ----
        if product_col:
            print(f"\n  📖 从 PostgreSQL 读取商品数据 (dim_products)...")
            try:
                df_products = pd.read_sql(
                    f"SELECT * FROM public_clean.dim_products LIMIT {limit}",
                    engine,
                )
                if len(df_products) > 0:
                    texts = [build_product_text(row) for _, row in df_products.iterrows()]
                    embeddings = self.encode_batch(texts)

                    insert_data = []
                    for i, (_, row) in enumerate(df_products.iterrows()):
                        insert_data.append({
                            "product_id": str(row.get("product_id", f"p_{i}")),
                            "text_content": texts[i][:1024],
                            "embedding": embeddings[i].tolist(),
                            "total_views": int(row.get("total_views", 0)),
                            "total_purchases": int(row.get("total_purchases", 0)),
                        })

                    for start in range(0, len(insert_data), BATCH_SIZE):
                        batch = insert_data[start:start + BATCH_SIZE]
                        product_col.insert(batch)
                    product_col.flush()

                    print(f"  ✅ {len(insert_data)} 条商品 embedding 已写入 '{product_col.name}'")
                    stats["collections"]["product_vectors"] = len(insert_data)
            except Exception as e:
                print(f"  ⚠️  商品数据读取失败: {e}")

        # ---- 事件向量 ----
        print(f"\n  📖 从 PostgreSQL 读取事件数据 (raw.user_events)...")
        try:
            df_events = pd.read_sql(
                f"SELECT * FROM raw.user_events LIMIT {limit}",
                engine,
            )
            if len(df_events) > 0:
                texts = [build_event_text(row) for _, row in df_events.iterrows()]
                embeddings = self.encode_batch(texts)

                insert_data = []
                for i, (_, row) in enumerate(df_events.iterrows()):
                    ts_str = str(row.get("timestamp", ""))
                    try:
                        event_ts = int(pd.Timestamp(ts_str).timestamp())
                    except Exception:
                        event_ts = 0

                    insert_data.append({
                        "event_id": str(row.get("event_id", f"evt_{i}")),
                        "user_id": str(row.get("user_id", "unknown")),
                        "event_type": str(row.get("event_type", "unknown")),
                        "product_id": str(row.get("product_id", "unknown")),
                        "text_content": texts[i][:1024],
                        "embedding": embeddings[i].tolist(),
                        "event_ts": event_ts,
                    })

                for start in range(0, len(insert_data), BATCH_SIZE):
                    batch = insert_data[start:start + BATCH_SIZE]
                    event_col.insert(batch)
                event_col.flush()

                print(f"  ✅ {len(insert_data)} 条事件 embedding 已写入 '{event_col.name}'")
                stats["collections"]["user_events_vectors"] = len(insert_data)
        except Exception as e:
            print(f"  ⚠️  事件数据读取失败: {e}")

        engine.dispose()
        return stats


# ---- 性能评估 ----
def run_benchmark(event_col: Collection, model: SentenceTransformer):
    """在已入库数据上运行语义检索性能评估。"""
    print(f"\n{'='*50}")
    print("  📊 语义检索性能基准测试")
    print(f"{'='*50}")

    event_col.load()

    test_queries = [
        "用户浏览了哪些商品页面",
        "从搜索引擎来的购买事件",
        "移动端用户的加购行为",
        "最近有哪些搜索事件",
        "桌面端用户从谷歌搜索进入",
    ]

    print(f"\n  {'查询文本':<40s} {'Top-1 事件类型':<18s} {'延迟(ms)':<10s}")
    print(f"  {'-'*40} {'-'*18} {'-'*10}")

    total_latency = 0
    for query in test_queries:
        # 编码查询向量
        q_embedding = model.encode(
            [query], normalize_embeddings=True
        )[0].tolist()

        # 检索
        t0 = time.time()
        results = event_col.search(
            data=[q_embedding],
            anns_field="embedding",
            param={"metric_type": "IP", "params": {"nprobe": 16}},
            limit=10,
            output_fields=["event_type", "text_content"],
        )
        latency_ms = (time.time() - t0) * 1000
        total_latency += latency_ms

        top1_type = results[0][0].entity.get("event_type", "N/A") if results[0] else "N/A"
        print(f"  {query:<40s} {top1_type:<18s} {latency_ms:<10.1f}")

    avg_latency = total_latency / len(test_queries)
    print(f"\n  📊 平均检索延迟: {avg_latency:.1f} ms")
    print(f"  📊 查询总数: {len(test_queries)}")
    print(f"  ✅ 基准测试完成")


# ---- 主入口 ----
def main():
    parser = argparse.ArgumentParser(
        description="Embedding 生成与向量检索数据入库"
    )
    parser.add_argument(
        "--source",
        choices=["parquet", "postgres", "all"],
        default="all",
        help="数据源类型",
    )
    parser.add_argument("--input", default="data/output_parquet",
                        help="Parquet 输入路径")
    parser.add_argument("--limit", type=int, default=5000,
                        help="PostgreSQL 读取行数上限")
    parser.add_argument("--benchmark", action="store_true",
                        help="入库后运行检索性能基准测试")
    parser.add_argument("--host", default=MILVUS_HOST, help="Milvus 地址")
    parser.add_argument("--port", default=MILVUS_PORT, help="Milvus 端口")
    args = parser.parse_args()

    print("=" * 50)
    print("  🧬 Embedding Pipeline — 文本 → 向量 → Milvus")
    print("=" * 50)
    print(f"  Milvus: {args.host}:{args.port}")
    print(f"  模型: {EMBEDDING_MODEL}")
    print(f"  向量维度: {VECTOR_DIM}")
    print(f"  数据源: {args.source}")

    # 连接 Milvus
    connections.connect(host=args.host, port=args.port)
    print(f"  ✅ 已连接 Milvus\n")

    # 创建 Collections
    event_col = create_event_collection()
    product_col = create_product_collection()

    # 初始化 Embedding Pipeline
    pipeline = EmbeddingPipeline()

    all_stats = {}

    # 根据数据源执行
    if args.source in ("parquet", "all"):
        stats = pipeline.ingest_parquet(args.input, event_col, product_col)
        all_stats["parquet"] = stats

    if args.source in ("postgres", "all"):
        stats = pipeline.ingest_postgres(event_col, product_col, limit=args.limit)
        all_stats["postgres"] = stats

    # 基准测试
    if args.benchmark:
        run_benchmark(event_col, pipeline.model)

    # 汇总
    print(f"\n{'='*50}")
    print("  📊 入库统计汇总")
    print(f"{'='*50}")
    print(json.dumps(all_stats, indent=2, ensure_ascii=False, default=str))
    print(f"\n✅ Embedding Pipeline 完成！")

    connections.disconnect("default")


if __name__ == "__main__":
    main()
