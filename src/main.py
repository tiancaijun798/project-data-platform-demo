"""
project-data-platform-demo
FastAPI Application Entry Point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

app = FastAPI(
    title="Data Platform Demo",
    version="0.1.0",
    description="全栈数据平台演示项目 API",
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
        "environment": "dev",
        "python_version": "3.13",
        "framework": "FastAPI",
    }

# 业务数据查询接口
@app.get("/api/stats/users")
async def user_stats():
    """返回用户统计数据"""
    import psycopg2
    conn = psycopg2.connect(
        host="localhost", port=5432, user="admin", password="changeme", dbname="data_platform"
    )
    cur = conn.cursor()
    cur.execute("SELECT user_segment, COUNT(*) as cnt, SUM(total_events) as events FROM public_clean.dim_users GROUP BY user_segment ORDER BY cnt DESC")
    rows = [{"segment": r[0], "count": r[1], "total_events": r[2]} for r in cur.fetchall()]
    cur.close(); conn.close()
    return {"users_by_segment": rows}


@app.get("/api/stats/events")
async def event_stats():
    """返回事件统计数据"""
    import psycopg2
    conn = psycopg2.connect(
        host="localhost", port=5432, user="admin", password="changeme", dbname="data_platform"
    )
    cur = conn.cursor()
    cur.execute("SELECT event_type, SUM(total_events) as cnt FROM public_clean.fct_user_events_daily GROUP BY event_type ORDER BY cnt DESC")
    rows = [{"event_type": r[0], "count": r[1]} for r in cur.fetchall()]
    cur.close(); conn.close()
    return {"events_by_type": rows}
