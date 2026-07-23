#!/usr/bin/env python3
"""
向量检索 API 服务 — FastAPI 语义搜索端点。

端点:
    GET  /health                    — 健康检查
    GET  /search/events?q=...       — 语义搜索用户事件
    GET  /search/products?q=...     — 语义搜索商品
    GET  /stats/collections         — 集合统计信息
    POST /query/natural             — 自然语言查询转 SQL 建议（演示用）

用法:
    uvicorn query_api:app --host 0.0.0.0 --port 8001
"""

import os
import time
from contextlib import asynccontextmanager
from typing import Optional

import numpy as np
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pymilvus import Collection, connections, utility
from sentence_transformers import SentenceTransformer


# ---- 配置 ----
MILVUS_HOST = os.getenv("MILVUS_HOST", "localhost")
MILVUS_PORT = int(os.getenv("MILVUS_PORT", "19530"))
EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2"
)
VECTOR_DIM = 384
TOP_K_DEFAULT = 10
COLLECTION_EVENTS = "user_events_vectors"
COLLECTION_PRODUCTS = "product_vectors"


# ---- 全局状态 ----
model: SentenceTransformer | None = None
event_col: Collection | None = None
product_col: Collection | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动: 加载模型 + 连接 Milvus。"""
    global model, event_col, product_col

    print("🚀 正在初始化向量检索服务...")

    # 加载 embedding 模型
    print(f"  🤖 加载模型: {EMBEDDING_MODEL}")
    model = SentenceTransformer(EMBEDDING_MODEL)

    # 连接 Milvus
    print(f"  🔗 连接 Milvus: {MILVUS_HOST}:{MILVUS_PORT}")
    connections.connect(host=MILVUS_HOST, port=MILVUS_PORT)

    # 加载 Collections
    if utility.has_collection(COLLECTION_EVENTS):
        event_col = Collection(COLLECTION_EVENTS)
        event_col.load()
        print(f"  ✅ 集合 '{COLLECTION_EVENTS}' 已加载 "
              f"({event_col.num_entities} 条)")
    else:
        print(f"  ⚠️  集合 '{COLLECTION_EVENTS}' 不存在，请先运行 embed.py")

    if utility.has_collection(COLLECTION_PRODUCTS):
        product_col = Collection(COLLECTION_PRODUCTS)
        product_col.load()
        print(f"  ✅ 集合 '{COLLECTION_PRODUCTS}' 已加载 "
              f"({product_col.num_entities} 条)")
    else:
        print(f"  ⚠️  集合 '{COLLECTION_PRODUCTS}' 不存在，请先运行 embed.py")

    print("✅ 向量检索服务就绪")
    yield

    # 清理
    connections.disconnect("default")
    print("👋 向量检索服务已关闭")


app = FastAPI(
    title="Data Platform — Vector Search API",
    version="0.2.0",
    description="Embedding + Milvus 语义检索演示服务",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---- 请求/响应模型 ----
class NaturalQueryRequest(BaseModel):
    query: str
    top_k: int = 10


class SearchResult(BaseModel):
    id: int
    score: float
    event_type: str = ""
    text_content: str = ""
    user_id: str = ""
    product_id: str = ""


class SearchResponse(BaseModel):
    query: str
    results: list[dict]
    elapsed_ms: float
    total_in_collection: int


# ---- 辅助函数 ----
def encode_query(query: str) -> list[float]:
    """将查询文本编码为归一化向量。"""
    if model is None:
        raise HTTPException(status_code=503, detail="模型未加载")
    embedding = model.encode(
        [query], normalize_embeddings=True, show_progress_bar=False
    )
    return embedding[0].tolist()


# ---- API 端点 ----
@app.get("/health")
async def health():
    """服务健康检查。"""
    return {
        "status": "healthy",
        "milvus_connected": connections.has_connection("default"),
        "model_loaded": model is not None,
        "event_collection": event_col.name if event_col else None,
        "product_collection": product_col.name if product_col else None,
    }


@app.get("/search/events")
async def search_events(
    q: str = Query(..., description="自然语言查询，例如 '移动端用户购买事件'"),
    top_k: int = Query(TOP_K_DEFAULT, ge=1, le=100),
    event_type: Optional[str] = Query(None, description="按事件类型过滤"),
):
    """
    语义搜索用户事件。

    支持中英文自然语言查询，返回最相关的用户事件记录。
    示例: "从谷歌搜索进入的购买事件"、"移动端的加购行为"
    """
    if event_col is None:
        raise HTTPException(
            status_code=503,
            detail=f"集合 '{COLLECTION_EVENTS}' 不可用，请先运行 embed.py",
        )

    t0 = time.time()

    # 编码查询
    q_vector = encode_query(q)

    # 构建过滤表达式
    expr = None
    if event_type:
        expr = f'event_type == "{event_type}"'

    # 检索
    search_params = {
        "metric_type": "IP",
        "params": {"nprobe": 32},
    }

    results = event_col.search(
        data=[q_vector],
        anns_field="embedding",
        param=search_params,
        limit=top_k,
        expr=expr,
        output_fields=[
            "event_id", "user_id", "event_type", "product_id",
            "text_content", "event_ts",
        ],
    )

    elapsed_ms = round((time.time() - t0) * 1000, 1)

    # 格式化结果
    hits = []
    for hit in results[0]:
        hits.append({
            "id": hit.id,
            "score": round(hit.distance, 4),  # IP 距离 ≈ cosine similarity
            "event_id": hit.entity.get("event_id", ""),
            "user_id": hit.entity.get("user_id", ""),
            "event_type": hit.entity.get("event_type", ""),
            "product_id": hit.entity.get("product_id", ""),
            "text_content": hit.entity.get("text_content", ""),
            "event_ts": hit.entity.get("event_ts", 0),
        })

    return {
        "query": q,
        "results": hits,
        "elapsed_ms": elapsed_ms,
        "total_in_collection": event_col.num_entities,
    }


@app.get("/search/products")
async def search_products(
    q: str = Query(..., description="自然语言查询，例如 '高转化率的商品'"),
    top_k: int = Query(TOP_K_DEFAULT, ge=1, le=100),
):
    """
    语义搜索商品。

    支持自然语言查询，返回最相关的商品记录。
    示例: "浏览次数多但购买少的商品"、"高转化率商品"
    """
    if product_col is None:
        raise HTTPException(
            status_code=503,
            detail=f"集合 '{COLLECTION_PRODUCTS}' 不可用，请先运行 embed.py",
        )

    t0 = time.time()
    q_vector = encode_query(q)

    results = product_col.search(
        data=[q_vector],
        anns_field="embedding",
        param={"metric_type": "IP", "params": {"nprobe": 32}},
        limit=top_k,
        output_fields=[
            "product_id", "text_content", "total_views", "total_purchases",
        ],
    )

    elapsed_ms = round((time.time() - t0) * 1000, 1)

    hits = []
    for hit in results[0]:
        hits.append({
            "id": hit.id,
            "score": round(hit.distance, 4),
            "product_id": hit.entity.get("product_id", ""),
            "text_content": hit.entity.get("text_content", ""),
            "total_views": hit.entity.get("total_views", 0),
            "total_purchases": hit.entity.get("total_purchases", 0),
        })

    return {
        "query": q,
        "results": hits,
        "elapsed_ms": elapsed_ms,
        "total_in_collection": product_col.num_entities,
    }


@app.get("/stats/collections")
async def collection_stats():
    """获取所有向量集合的统计信息。"""
    stats = {}
    for name in [COLLECTION_EVENTS, COLLECTION_PRODUCTS]:
        if utility.has_collection(name):
            col = Collection(name)
            stats[name] = {
                "exists": True,
                "num_entities": col.num_entities,
                "schema": {f.name: str(f.dtype) for f in col.schema.fields},
                "indexes": [idx.params for idx in col.indexes],
            }
        else:
            stats[name] = {"exists": False}

    return {
        "collections": stats,
        "milvus_version": utility.get_server_version(),
    }


@app.post("/query/natural")
async def natural_query(body: NaturalQueryRequest):
    """
    自然语言查询 — 将 NL 转为最相关事件类型的 SQL 建议。

    这是一个演示端点，展示 embedding 如何为 AI 数据服务提供支撑：
    用语义相似度找到最相关的数据子集，辅助下游模型或分析。
    """
    if event_col is None:
        raise HTTPException(status_code=503, detail="事件集合不可用")

    q_vector = encode_query(body.query)

    results = event_col.search(
        data=[q_vector],
        anns_field="embedding",
        param={"metric_type": "IP", "params": {"nprobe": 32}},
        limit=body.top_k,
        output_fields=["event_type", "user_id", "product_id", "text_content"],
    )

    # 聚合统计
    event_types = {}
    user_ids = set()
    product_ids = set()
    top_hits = []

    for hit in results[0]:
        et = hit.entity.get("event_type", "unknown")
        event_types[et] = event_types.get(et, 0) + 1
        user_ids.add(hit.entity.get("user_id", ""))
        product_ids.add(hit.entity.get("product_id", ""))
        if len(top_hits) < 5:
            top_hits.append({
                "score": round(hit.distance, 4),
                "event_type": et,
                "text": hit.entity.get("text_content", ""),
            })

    # 生成 SQL 建议
    sorted_types = sorted(event_types.items(), key=lambda x: x[1], reverse=True)
    suggested_sql = None
    if sorted_types:
        top_type = sorted_types[0][0]
        suggested_sql = (
            f"SELECT * FROM raw.user_events "
            f"WHERE event_type = '{top_type}' "
            f"ORDER BY event_ts DESC LIMIT 100;"
        )

    return {
        "query": body.query,
        "interpreted_intent": sorted_types[0][0] if sorted_types else "unknown",
        "event_type_distribution": dict(sorted_types),
        "distinct_users": len(user_ids),
        "distinct_products": len(product_ids),
        "suggested_sql": suggested_sql,
        "top_matches": top_hits,
    }


# ---- 主入口 ----
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
