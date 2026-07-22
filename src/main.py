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
