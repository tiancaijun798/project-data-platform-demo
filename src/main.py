"""
project-data-platform-demo
FastAPI Application Entry Point
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from prometheus_fastapi_instrumentator import Instrumentator
import httpx
from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool


# ---- 配置（全部从环境变量读取） ----
DB_HOST = os.getenv("DATA_PLATFORM_DB_HOST", "data-platform-db")
DB_PORT = os.getenv("DATA_PLATFORM_DB_PORT", "5432")
DB_USER = os.getenv("DATA_PLATFORM_DB_USER", "admin")
DB_PASSWORD = os.getenv("DATA_PLATFORM_DB_PASSWORD", "changeme")
DB_NAME = os.getenv("DATA_PLATFORM_DB_NAME", "data_platform")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# 连接池
engine = create_engine(DATABASE_URL, poolclass=QueuePool, pool_size=5, max_overflow=10)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动/关闭时管理连接池。"""
    yield
    engine.dispose()


app = FastAPI(
    title="Data Platform Demo",
    version="0.1.0",
    description="全栈数据平台演示项目 API",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus 指标采集
Instrumentator().instrument(app).expose(app)


@app.get("/")
async def root():
    return {"message": "Data Platform Demo API is running", "version": "0.1.0"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/info")
async def info():
    return {
        "project": "project-data-platform-demo",
        "environment": os.getenv("ENV", "dev"),
        "python_version": "3.13",
        "framework": "FastAPI",
        "db_host": DB_HOST,
    }


def _query(sql: str) -> list[dict]:
    """同步查询辅助函数（使用连接池）。"""
    with engine.connect() as conn:
        result = conn.execute(text(sql))
        columns = result.keys()
        return [dict(zip(columns, row)) for row in result.fetchall()]


@app.get("/api/stats/users")
async def user_stats():
    """返回用户分群统计数据。"""
    rows = _query(
        "SELECT user_segment, COUNT(*) as cnt, SUM(total_events) as events "
        "FROM public_clean.dim_users GROUP BY user_segment ORDER BY cnt DESC"
    )
    return {"users_by_segment": rows}


@app.get("/api/stats/events")
async def event_stats():
    """返回事件类型统计数据。"""
    rows = _query(
        "SELECT event_type, SUM(total_events) as cnt "
        "FROM public_clean.fct_user_events_daily GROUP BY event_type ORDER BY cnt DESC"
    )
    return {"events_by_type": rows}


@app.get("/api/stats/products/top")
async def top_products(limit: int = 10):
    """返回转化率最高的商品。"""
    rows = _query(
        f"SELECT product_id, total_views, total_purchases, conversion_rate_pct "
        f"FROM public_clean.dim_products WHERE total_views > 5 "
        f"ORDER BY conversion_rate_pct DESC LIMIT {limit}"
    )
    return {"top_products": rows}


# ============================================================
# 前端数据产品 API
# ============================================================

@app.get("/api/stats/data-overview")
async def data_overview():
    """数据平台总览 —— 各数据源的行数统计。"""
    counts = {}
    # PostgreSQL
    try:
        counts["postgres_events"] = _query("SELECT count(*) as c FROM raw.user_events")[0]["c"]
    except Exception:
        counts["postgres_events"] = 0
    try:
        counts["postgres_users"] = _query("SELECT count(*) as c FROM public_clean.dim_users")[0]["c"]
    except Exception:
        counts["postgres_users"] = 0
    try:
        counts["postgres_products"] = _query("SELECT count(*) as c FROM public_clean.dim_products")[0]["c"]
    except Exception:
        counts["postgres_products"] = 0
    # Milvus (Docker network direct)
    try:
        from pymilvus import MilvusClient
        client = MilvusClient(uri="http://data-v-milvus:19530", timeout=5)
        stats = client.get_collection_stats("user_events_vectors")
        counts["milvus_event_vectors"] = stats.get("row_count", 0)
    except Exception:
        counts["milvus_event_vectors"] = 0
    # Neo4j (Docker network direct)
    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver("bolt://data-platform-neo4j:7687", auth=("neo4j", "changeme123"))
        driver.verify_connectivity()
        with driver.session() as s:
            r = s.run("MATCH (n) RETURN COALESCE(labels(n)[0], 'unlabeled') as label, count(n) as cnt")
            for rec in r:
                counts[f"neo4j_{rec['label'].lower()}s"] = rec["cnt"]
        driver.close()
    except Exception:
        counts["neo4j_users"] = 0
    # FAISS
    try:
        import faiss
        from pathlib import Path
        idx_path = Path(os.getenv("RAG_INDEX_PATH", "rag_demo/knowledge_base/index.faiss"))
        if idx_path.exists():
            index = faiss.read_index(str(idx_path))
            counts["faiss_vectors"] = index.ntotal
        else:
            counts["faiss_vectors"] = 0
    except Exception:
        counts["faiss_vectors"] = 0

    return {"data": counts}


# ============================================================
# AI/ML API（向量检索、RAG、图分析、MLflow）
# ============================================================

# Module-level model cache — loaded once at first request, reused after
_embedding_model = None

def _get_embedding_model():
    """Lazy-load and cache the embedding model (384d MiniLM)."""
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        from pathlib import Path
        # Try local cache first (mounted from host)
        for candidate in [
            Path("/app/rag_demo/knowledge_base/models/sentence-transformers--paraphrase-multilingual-MiniLM-L12-v2"),
            Path("rag_demo/knowledge_base/models/sentence-transformers--paraphrase-multilingual-MiniLM-L12-v2"),
        ]:
            if candidate.exists():
                _embedding_model = SentenceTransformer(str(candidate))
                break
        if _embedding_model is None:
            _embedding_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    return _embedding_model


@app.get("/api/ai/vector-search")
async def vector_search(q: str = "", k: int = 5):
    """Milvus semantic search — model cached at module level for fast queries."""
    if not q:
        return {"error": "query parameter 'q' is required"}
    try:
        import socket
        from pymilvus import MilvusClient
        milvus_host = os.getenv("MILVUS_HOST", "data-v-milvus")
        milvus_port = os.getenv("MILVUS_PORT", "19530")
        # Resolve Docker hostname to IP (pymilvus gRPC has DNS issues)
        try:
            milvus_ip = socket.gethostbyname(milvus_host)
        except Exception:
            milvus_ip = milvus_host
        uri = f"http://{milvus_ip}:{milvus_port}"
        client = MilvusClient(uri=uri, timeout=10)
        model = _get_embedding_model()
        vec = model.encode([q], normalize_embeddings=True)[0].tolist()
        import time
        t0 = time.time()
        results = client.search(
            collection_name="user_events_vectors",
            data=[vec], limit=k,
            output_fields=["event_type", "user_id", "product_id", "text_content"],
        )
        elapsed = round((time.time() - t0) * 1000, 1)
        hits = []
        for hit in results[0]:
            ent = hit.get("entity", hit)
            hits.append({
                "id": hit.get("id", 0),
                "score": round(hit.get("distance", 0), 4),
                "event_type": ent.get("event_type", ""),
                "user_id": ent.get("user_id", ""),
                "product_id": ent.get("product_id", ""),
                "text": ent.get("text_content", ""),
            })
        stats = client.get_collection_stats("user_events_vectors")
        total = stats.get("row_count", 0)
        return {"query": q, "results": hits, "elapsed_ms": elapsed, "total": total}
    except Exception as e:
        return {"error": str(e), "results": [], "elapsed_ms": 0}


@app.post("/api/ai/rag-query")
async def rag_query(body: dict):
    """RAG 检索 + LLM 生成。"""
    q = body.get("query", "")
    k = body.get("top_k", 5)
    if not q:
        return {"error": "query is required"}
    try:
        import sys, json, time, faiss, numpy as np
        from pathlib import Path
        rag_path = os.path.join(os.path.dirname(__file__), "..", "rag_demo")
        sys.path.insert(0, rag_path)
        from rag_server import retrieve, encode_query
        idx_path = Path(os.getenv("RAG_INDEX_PATH", "rag_demo/knowledge_base/index.faiss"))
        meta_path = Path(os.getenv("RAG_META_PATH", "rag_demo/knowledge_base/metadata.json"))
        if not idx_path.exists() or not meta_path.exists():
            return {"error": "RAG index not found. Run: python rag_demo/build_knowledge_base.py"}

        import rag_server as rs
        rs.INDEX_PATH = idx_path
        rs.META_PATH = meta_path
        # Load model + index + metadata
        from sentence_transformers import SentenceTransformer
        model_path = Path("rag_demo/knowledge_base/models/sentence-transformers--paraphrase-multilingual-MiniLM-L12-v2")
        rs.model = SentenceTransformer(str(model_path) if model_path.exists() else "paraphrase-multilingual-MiniLM-L12-v2")
        rs.index = faiss.read_index(str(idx_path))
        with open(meta_path, "r", encoding="utf-8") as f:
            rs.metadata = json.load(f)
        rs.meta_lookup = {m["id"]: m for m in rs.metadata}

        t0 = time.time()
        docs = retrieve(q, k)
        retrieval_ms = round((time.time() - t0) * 1000, 1)

        # LLM generation
        from llm_generator import LLMGenerator
        gen = LLMGenerator()
        result = gen.generate(q, docs)
        return {
            "query": q, "retrieved_docs": docs, "retrieval_ms": retrieval_ms,
            "answer": result.get("answer", ""), "model": result.get("model", ""),
            "token_usage": result.get("usage", {}), "generation_ms": result.get("elapsed_ms", 0),
            "error": result.get("error"),
        }
    except Exception as e:
        return {"error": str(e), "retrieved_docs": [], "answer": ""}


@app.get("/api/ai/graph-stats")
async def graph_stats():
    """Neo4j 图数据库统计。"""
    try:
        from neo4j import GraphDatabase
        uri = os.getenv("NEO4J_URI", "bolt://data-platform-neo4j:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        pwd = os.getenv("NEO4J_PASSWORD", "changeme123")
        driver = GraphDatabase.driver(uri, auth=(user, pwd))
        driver.verify_connectivity()
        with driver.session() as s:
            r = s.run("MATCH (n) RETURN labels(n)[0] as label, count(n) as cnt ORDER BY cnt DESC")
            nodes = [{"label": rec["label"], "count": rec["cnt"]} for rec in r]
            r2 = s.run("MATCH ()-[r]->() RETURN type(r) as type, count(r) as cnt ORDER BY cnt DESC")
            rels = [{"type": rec["type"], "count": rec["cnt"]} for rec in r2]
        driver.close()
        return {"nodes": nodes, "relationships": rels}
    except Exception as e:
        return {"error": str(e), "nodes": [], "relationships": []}


@app.get("/api/ai/graph-path")
async def graph_path(user_id: str = "U0001", limit: int = 10):
    """用户行为路径（Neo4j）。"""
    try:
        from neo4j import GraphDatabase
        uri = os.getenv("NEO4J_URI", "bolt://data-platform-neo4j:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        pwd = os.getenv("NEO4J_PASSWORD", "changeme123")
        driver = GraphDatabase.driver(uri, auth=(user, pwd))
        with driver.session() as s:
            r = s.run("""
                MATCH (u:User {user_id: $uid})-[:PERFORMED]->(e:Event)
                OPTIONAL MATCH (e)-[:ON_PRODUCT]->(p:Product)
                RETURN e.event_type as event_type, e.timestamp as ts,
                       e.device as device, p.product_id as product_id,
                       p.category as category
                ORDER BY e.timestamp LIMIT $limit
            """, uid=user_id, limit=limit)
            path = [{
                "event_type": rec["event_type"], "timestamp": rec["ts"],
                "device": rec["device"], "product_id": rec["product_id"],
                "category": rec["category"],
            } for rec in r]
        driver.close()
        return {"user_id": user_id, "path": path}
    except Exception as e:
        return {"error": str(e), "path": []}


@app.get("/api/ai/mlflow-experiments")
async def mlflow_experiments():
    """MLflow 实验列表（从 PostgreSQL 读取）。"""
    try:
        rows = _query("""
            SELECT e.experiment_id, e.name,
                   (SELECT count(*) FROM runs r WHERE r.experiment_id = e.experiment_id) as run_count
            FROM experiments e ORDER BY e.experiment_id
        """)
        return {"experiments": rows}
    except Exception as e:
        return {"error": str(e), "experiments": []}

@app.get("/api/stats/dashboard")
async def dashboard():
    """销售大盘概览。"""
    stats = _query("""
        SELECT
          (SELECT COUNT(*) FROM raw.user_events) as total_events,
          (SELECT COUNT(*) FROM raw.user_events WHERE event_type='purchase') as today_orders,
          (SELECT COUNT(DISTINCT user_id) FROM raw.user_events) as today_users,
          CASE WHEN (SELECT COUNT(*) FROM raw.user_events WHERE event_type IN ('view','search','click')) > 0
            THEN ROUND((SELECT COUNT(*) FROM raw.user_events WHERE event_type='purchase') * 100.0 /
                       (SELECT COUNT(*) FROM raw.user_events WHERE event_type IN ('view','search','click')), 2)
            ELSE 0 END as conversion_rate
    """)
    return {"data": stats[0] if stats else {}}


@app.get("/api/stats/sales-trend")
async def sales_trend():
    """近 7 天趋势。"""
    rows = _query("""
        SELECT DATE(event_ts) as date,
               COUNT(*) as events,
               COUNT(*) FILTER(WHERE event_type='purchase') as purchases
        FROM raw.user_events
        WHERE event_ts IS NOT NULL
        GROUP BY DATE(event_ts)
        ORDER BY date
    """)
    return {"data": rows}


@app.get("/api/stats/hourly-heatmap")
async def hourly_heatmap():
    """时段热力图。"""
    rows = _query("""
        SELECT EXTRACT(HOUR FROM event_ts)::int as hour, COUNT(*) as events
        FROM raw.user_events WHERE event_ts IS NOT NULL
        GROUP BY hour ORDER BY hour
    """)
    return {"data": rows}


@app.get("/api/stats/user-segments")
async def user_segments():
    """用户分群数据。"""
    rows = _query("""
        SELECT user_segment as segment,
               COUNT(*) as users,
               SUM(total_events) as events,
               ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 1) as pct
        FROM public_clean.dim_users
        GROUP BY user_segment ORDER BY users DESC
    """)
    return {"data": rows}


@app.get("/api/stats/top-users")
async def top_users(limit: int = 20):
    """活跃用户排行榜。"""
    rows = _query(f"""
        SELECT user_id, user_segment as segment, total_events,
               first_seen_at as first_seen, last_seen_at as last_seen
        FROM public_clean.dim_users
        ORDER BY total_events DESC LIMIT {limit}
    """)
    return {"data": rows}


@app.get("/api/stats/product-rank")
async def product_rank(limit: int = 20):
    """商品排行。"""
    rows = _query(f"""
        SELECT p.product_id,
               COALESCE((SELECT DISTINCT product_category FROM raw.user_events u WHERE u.product_id=p.product_id LIMIT 1), 'unknown') as category,
               p.total_views, p.total_purchases,
               ROUND(p.conversion_rate_pct, 1) as conversion_rate
        FROM public_clean.dim_products p
        ORDER BY p.total_views DESC LIMIT {limit}
    """)
    return {"data": rows}


@app.get("/api/stats/category-share")
async def category_share():
    """品类销售占比 — 通过 product_id 末位数字映射品类。"""
    rows = _query("""
        SELECT
          CASE
            WHEN RIGHT(product_id, 1) = '0' THEN 'Electronics'
            WHEN RIGHT(product_id, 1) = '1' THEN 'Clothing'
            WHEN RIGHT(product_id, 1) = '2' THEN 'Food'
            WHEN RIGHT(product_id, 1) = '3' THEN 'Home'
            WHEN RIGHT(product_id, 1) = '4' THEN 'Sports'
            WHEN RIGHT(product_id, 1) = '5' THEN 'Books'
            WHEN RIGHT(product_id, 1) = '6' THEN 'Beauty'
            WHEN RIGHT(product_id, 1) = '7' THEN 'Toys'
            WHEN RIGHT(product_id, 1) = '8' THEN 'Automotive'
            WHEN RIGHT(product_id, 1) = '9' THEN 'Health'
            ELSE 'Other'
          END as category,
          COUNT(*) as views,
          COUNT(*) FILTER(WHERE event_type='purchase') as purchases,
          ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 1) as pct
        FROM raw.user_events
        WHERE product_id IS NOT NULL
        GROUP BY category ORDER BY views DESC
    """)
    return {"data": rows}


@app.get("/api/stats/funnel")
async def funnel():
    """转化漏斗数据。"""
    rows = _query("""
        SELECT '浏览/搜索' as name, COUNT(*) as value, 100.0 as pct
        FROM raw.user_events WHERE event_type IN ('view','search','click')
        UNION ALL
        SELECT '加入购物车', COUNT(*),
               ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM raw.user_events WHERE event_type IN ('view','search','click')), 1)
        FROM raw.user_events WHERE event_type='add_to_cart'
        UNION ALL
        SELECT '下单购买', COUNT(*),
               ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM raw.user_events WHERE event_type IN ('view','search','click')), 1)
        FROM raw.user_events WHERE event_type='purchase'
        ORDER BY value DESC
    """)
    return {"data": rows}


@app.get("/api/stats/services")
async def services():
    """服务健康状态（通过 TCP 端口检测）。"""
    import socket

    svcs = [
        ("Airflow", 8080, "http://localhost:8080", True, "host.docker.internal"),
        ("FastAPI", 8000, "http://localhost:8000/docs", True, "host.docker.internal"),
        ("Frontend", 3001, "http://localhost:3001", True, "host.docker.internal"),
        ("Grafana", 3000, "http://localhost:3000", True, "host.docker.internal"),
        ("Prometheus", 9090, "http://localhost:9090", True, "host.docker.internal"),
        ("MLflow", 5000, "http://localhost:3001/mlflow/", True, "data-mlflow"),
        ("Neo4j", 7474, "http://localhost:7474", True, "host.docker.internal"),
        ("PostgreSQL", 5432, "postgresql://admin@localhost:5432/data_platform", False, "host.docker.internal"),
        ("Redis", 6379, "redis://localhost:6379", False, "host.docker.internal"),
        ("Kafka", 9092, "kafka://localhost:9092", False, "host.docker.internal"),
        ("Milvus", 19530, "milvus://localhost:19530", False, "host.docker.internal"),
        ("Neo4j Bolt", 7688, "bolt://localhost:7688", False, "host.docker.internal"),
    ]

    result = []
    for name, port, url, is_web, host in svcs:
        status = "stopped"
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            if sock.connect_ex((host, port)) == 0:
                status = "running"
            sock.close()
        except Exception:
            pass
        result.append({"name": name, "port": port, "url": url, "status": status, "is_web": is_web})
    return {"data": result}


@app.post("/api/stats/query")
async def run_query(body: dict):
    """执行自定义 SQL 查询。"""
    import time

    sql = body.get("sql", "").strip()
    if not sql:
        return {"error": "SQL 不能为空"}

    # 安全检查：只允许 SELECT
    if not sql.upper().startswith("SELECT"):
        return {"error": "只允许 SELECT 查询"}

    t0 = time.time()
    try:
        rows = _query(sql)
    except Exception as e:
        return {"error": str(e)}

    elapsed_ms = int((time.time() - t0) * 1000)
    columns = list(rows[0].keys()) if rows else []

    # 转换日期类型为字符串
    from datetime import date, datetime
    for r in rows:
        for k, v in r.items():
            if isinstance(v, (date, datetime)):
                r[k] = str(v)

    return {"columns": columns, "rows": rows, "row_count": len(rows), "elapsed_ms": elapsed_ms}


# ---- 静态文件: 数据血缘 ----
LINEAGE_DIR = os.path.join(os.path.dirname(__file__), "..", "lineage", "lineage_output")
if os.path.isdir(LINEAGE_DIR):
    app.mount("/lineage-static", StaticFiles(directory=LINEAGE_DIR), name="lineage-static")

@app.get("/lineage.html")
async def serve_lineage():
    """服务数据血缘 HTML 页面。"""
    lineage_html = os.path.join(LINEAGE_DIR, "lineage.html")
    if os.path.isfile(lineage_html):
        return FileResponse(lineage_html, media_type="text/html")
    return {"error": "lineage.html not found. Run: python lineage/generate_lineage.py"}

# ---- 代理: 绕过 Steam++ 端口拦截 ----
import httpx

HTTP_CLIENT = httpx.AsyncClient(timeout=30, follow_redirects=True)

@app.get("/proxy/mlflow/{path:path}")
async def proxy_mlflow(path: str = "", request=None):
    """代理 MLflow UI + 静态资源。"""
    url = f"http://data-mlflow:5000/{path}"
    if request and request.query_params:
        url += f"?{request.query_params}"
    try:
        r = await HTTP_CLIENT.get(url)
        return Response(content=r.content, status_code=r.status_code,
                      media_type=r.headers.get("content-type", "text/html"))
    except Exception:
        return Response(content=b"MLflow not reachable. Try restarting: docker restart data-mlflow",
                      status_code=503)

@app.api_route("/proxy/grafana/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_grafana(path: str = "", request=None):
    """代理 Grafana（支持子路径）。"""
    url = f"http://data-mon-grafana:3000/{path}"
    if request and request.query_params:
        url += f"?{request.query_params}"
    try:
        r = await HTTP_CLIENT.get(url)
        content_type = r.headers.get("content-type", "text/html")
        # Rewrite asset paths in HTML
        content = r.content
        if "text/html" in content_type:
            content = content.replace(b'src="/public', b'src="/proxy/grafana/public')
            content = content.replace(b'href="/public', b'href="/proxy/grafana/public')
            content = content.replace(b'"/avatar/', b'"/proxy/grafana/avatar/')
        return Response(content=content, status_code=r.status_code,
                      media_type=content_type)
    except Exception:
        return Response(content=b"Grafana not reachable", status_code=503)
