#!/bin/bash
# ============================================================
# 一键重置脚本 — 停止并清理全部数据平台服务
# 用法: bash scripts/one_click_reset.sh [--hard]
#   --hard: 同时删除数据卷（PostgreSQL, Redis, Airflow DB）
# ============================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DOCKER_DIR="$PROJECT_ROOT/docker"
MONITORING_DIR="$PROJECT_ROOT/monitoring"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

HARD_RESET=false
if [ "$1" = "--hard" ] || [ "$1" = "-h" ]; then
    HARD_RESET=true
fi

echo ""
echo -e "${YELLOW}========================================"
if [ "$HARD_RESET" = true ]; then
    echo "  ⚠️  一键重置 — 硬重置模式（删除数据卷）"
else
    echo "  一键重置 — 软重置模式（保留数据）"
fi
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo -e "========================================${NC}"

# ---- 确认 ----
if [ "$HARD_RESET" = true ]; then
    echo ""
    echo -e "${RED}⚠️  警告: 此操作将删除所有持久化数据！${NC}"
    echo -e "${RED}   包括: PostgreSQL 数据、Redis 数据、Airflow 数据库${NC}"
    echo ""
    read -p "  确认继续？(输入 YES 以确认): " confirm
    if [ "$confirm" != "YES" ]; then
        echo "  已取消"
        exit 0
    fi
fi

# ---- Step 1: 停止 Airflow ----
echo -e "\n${CYAN}[1/3] 停止 Airflow 服务...${NC}"
cd "$DOCKER_DIR"
docker compose -f docker-compose-airflow.yml down
echo -e "${GREEN}  ✅ Airflow 已停止${NC}"

# ---- Step 2: 停止 Kafka ----
echo -e "\n${CYAN}[2/3] 停止 Kafka 服务...${NC}"
docker compose -f docker-compose-kafka.yml down
echo -e "${GREEN}  ✅ Kafka 已停止${NC}"

# ---- Step 3: 停止基础服务 & 监控 ----
echo -e "\n${CYAN}[3/3] 停止基础服务和监控...${NC}"
docker compose down
echo -e "${GREEN}  ✅ 基础服务已停止${NC}"

# 停止监控（如果存在）
cd "$MONITORING_DIR" 2>/dev/null && {
    docker compose -f docker-compose-monitoring.yml down 2>/dev/null || true
    echo -e "${GREEN}  ✅ 监控服务已停止${NC}"
}

# ---- 硬重置：删除数据卷 ----
if [ "$HARD_RESET" = true ]; then
    echo -e "\n${YELLOW}删除数据卷...${NC}"
    docker volume rm -f data-platform-postgres data-platform-redis airflow-postgres-data monitoring-prometheus monitoring-grafana 2>/dev/null || true
    echo -e "${GREEN}  ✅ 数据卷已删除${NC}"

    # 清理本地数据
    cd "$PROJECT_ROOT"
    rm -rf data/input.jsonl data/output_parquet data/iceberg_warehouse data/benchmark_reports data/optimization_report 2>/dev/null || true
    echo -e "${GREEN}  ✅ 本地数据文件已删除${NC}"
fi

# ---- 汇总 ----
echo ""
echo -e "${GREEN}========================================"
echo "  ✅ 重置完成"
echo -e "========================================${NC}"

# 残留容器检查
REMAINING=$(docker ps -q --filter "name=data-|airflow-" 2>/dev/null | wc -l)
if [ "$REMAINING" -gt 0 ]; then
    echo -e "  ${YELLOW}⚠️  仍有 ${REMAINING} 个相关容器运行中${NC}"
else
    echo -e "  ${GREEN}✅ 所有容器已清理${NC}"
fi
echo ""
