#!/bin/bash
# ============================================================
# 数据库初始化脚本 — 从零创建 schema 并加载样例数据
# 用法: bash scripts/init_database.sh
# ============================================================
set -e

echo "========================================"
echo "  数据库初始化"
echo "========================================"

# 检查 PostgreSQL 是否可访问
echo "[1/4] 检查 PostgreSQL 连接..."
if docker exec data-platform-db psql -U "${DB_USER:-admin}" -d "${DB_NAME:-data_platform}" -c "SELECT 1" &>/dev/null; then
    echo "  PostgreSQL 连接正常"
else
    echo "  PostgreSQL 未运行或不可达，请先启动服务:"
    echo "    cd docker && docker compose up -d"
    exit 1
fi

# 创建 Schema
echo "[2/4] 创建 Schema..."
docker exec data-platform-db psql -U "${DB_USER:-admin}" -d "${DB_NAME:-data_platform}" <<'SQL'
CREATE SCHEMA IF NOT EXISTS raw;
SQL
echo "  Schema(raw) 已创建"

# 创建源表
echo "[3/4] 创建源表 raw.user_events..."
docker exec data-platform-db psql -U "${DB_USER:-admin}" -d "${DB_NAME:-data_platform}" <<'SQL'
CREATE TABLE IF NOT EXISTS raw.user_events (
    event_id         TEXT,
    user_id          TEXT,
    event_type       TEXT,
    product_id       TEXT,
    product_category TEXT,
    timestamp        TEXT,
    event_ts         TIMESTAMP,
    page             TEXT,
    referrer         TEXT,
    duration_ms      DOUBLE PRECISION,
    device           TEXT,
    browser          TEXT,
    processed_at     TIMESTAMP DEFAULT NOW(),
    processing_date  DATE DEFAULT CURRENT_DATE
);
SQL
echo "  raw.user_events 已就绪"

# 生成并加载样例数据
echo "[4/4] 生成样例数据..."
cd "$(dirname "$0")/.."

if [ ! -f data/input.jsonl ]; then
    echo "  生成测试数据..."
    python scripts/generate_real_data.py
else
    echo "  已有数据文件: data/input.jsonl"
fi

echo "  加载数据到 PostgreSQL..."
python -c "
import pandas as pd
from sqlalchemy import create_engine
import os

url = f'postgresql://{os.getenv(\"DB_USER\",\"admin\")}:{os.getenv(\"DB_PASSWORD\",\"changeme\")}@localhost:5432/{os.getenv(\"DB_NAME\",\"data_platform\")}'
engine = create_engine(url)

df = pd.read_json('data/input.jsonl', lines=True)
df['event_ts'] = pd.to_datetime(df['timestamp'], errors='coerce')
df['product_id'] = df['product_id'].fillna('unknown')
df['referrer'] = df['referrer'].fillna('direct')
df['processed_at'] = pd.Timestamp.now()
df['processing_date'] = pd.Timestamp.now().date()

# 去重
df = df.drop_duplicates(subset=['event_id'])

# 先清空再写入
with engine.connect() as conn:
    conn.execute('DELETE FROM raw.user_events')
df.to_sql('user_events', engine, schema='raw', if_exists='append', index=False)

count = pd.read_sql('SELECT COUNT(*) as n FROM raw.user_events', engine).iloc[0,0]
print(f'  raw.user_events: {count} rows')
"

echo ""
echo "========================================"
echo "  数据库初始化完成！"
echo "========================================"
echo "  下一步:"
echo "    cd dbt && PYTHONUTF8=1 dbt run --profiles-dir ."
echo "    cd dbt && PYTHONUTF8=1 dbt test --profiles-dir ."
echo ""
