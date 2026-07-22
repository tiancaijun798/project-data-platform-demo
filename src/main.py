"""
project-data-platform-demo
FastAPI Application Entry Point
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
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
# 前端数据产品 API（新增）
# ============================================================

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
    """品类销售占比。"""
    rows = _query("""
        SELECT COALESCE(product_category, 'unknown') as category,
               COUNT(*) as views,
               COUNT(*) FILTER(WHERE event_type='purchase') as purchases,
               ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 1) as pct
        FROM raw.user_events
        WHERE product_category IS NOT NULL
        GROUP BY product_category ORDER BY views DESC
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
    """服务健康状态。"""
    import subprocess

    svcs = [
        ("Airflow", 8080, "http://localhost:8080"),
        ("FastAPI", 8000, "http://localhost:8000/docs"),
        ("Grafana", 3000, "http://localhost:3000"),
        ("Prometheus", 9090, "http://localhost:9090"),
        ("PostgreSQL", 5432, "localhost:5432"),
        ("Redis", 6379, "localhost:6379"),
        ("Kafka", 9092, "localhost:9092"),
    ]

    result = []
    for name, port, url in svcs:
        status = "unknown"
        try:
            r = subprocess.run(
                f"docker ps --format '{{{{.Status}}}}' --filter publish={port}",
                shell=True, capture_output=True, text=True, timeout=5
            )
            if "Up" in r.stdout:
                status = "running"
            elif r.stdout.strip():
                status = "stopped"
        except Exception:
            pass
        result.append({"name": name, "port": port, "url": url, "status": status})
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
