#!/bin/bash
# ============================================================
# Windows 一键启动脚本 (Git Bash / WSL)
# 用法: bash scripts/one_click_start_windows.sh
# ============================================================
set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DOCKER_DIR="$PROJECT_ROOT/docker"

echo "========================================"
echo "  Data Platform 一键启动 (Windows)"
echo "========================================"

# 检查 Docker Desktop 运行状态
echo "[1/6] 检查 Docker Desktop..."
if ! docker info &>/dev/null; then
    echo "  ❌ Docker Desktop 未运行，请先启动 Docker Desktop"
    exit 1
fi
echo "  ✅ Docker Desktop 运行中"

# 启动基础服务
echo "[2/6] 启动基础服务 (App + PostgreSQL + Redis)..."
cd "$DOCKER_DIR"
docker compose up -d

# 启动 Kafka
echo "[3/6] 启动 Kafka..."
docker compose -f docker-compose-kafka.yml up -d

# 启动 Airflow
echo "[4/6] 启动 Airflow..."
docker compose -f docker-compose-airflow.yml up -d

# 创建 Kafka Topic
echo "[5/6] 初始化 Kafka Topic..."
sleep 10
docker exec data-kafka bash -c \
    "kafka-topics.sh --create --topic events --bootstrap-server localhost:9092 --partitions 3 --replication-factor 1" \
    2>/dev/null && echo "  ✅ Topic [events] 已创建" \
    || echo "  ⚠️ Topic 可能已存在"

# 运行环境检测
echo "[6/6] 环境检测..."
bash "$PROJECT_ROOT/scripts/check_env.sh" 2>/dev/null || echo "  ⚠️ 检测脚本执行失败（不影响环境）"

echo ""
echo "========================================"
echo "  ✅ 启动完成！"
echo "========================================"
echo ""
echo "  服务访问:"
echo "    Airflow:  http://localhost:8080  (admin: airflow / airflow)"
echo "    FastAPI:  http://localhost:8000  (GET /health)"
echo "    Kafka:    localhost:9092"
echo "    Grafana:  http://localhost:3000  (admin: admin) [需 --monitoring]"
echo ""
echo "  下一步:"
echo "    浏览器访问 Airflow WebUI，手动触发 'demo_pipeline' DAG"
echo ""
