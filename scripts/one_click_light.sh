#!/bin/bash
# ============================================================
# 一键启动 (轻量模式) — 仅启动核心演示服务
# 适用于: 快速 Demo、面试演示、开发调试
#
# 用法:
#   bash scripts/one_click_light.sh                    # 基础: PG + Redis + API
#   bash scripts/one_click_light.sh --kafka             # + Kafka
#   bash scripts/one_click_light.sh --airflow           # + Airflow
#   bash scripts/one_click_light.sh --monitoring        # + Prometheus/Grafana
#   bash scripts/one_click_light.sh --ml                # + MLflow
#   bash scripts/one_click_light.sh --vector            # + Milvus
#   bash scripts/one_click_light.sh --all               # 全部服务
# ============================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DOCKER_DIR="$PROJECT_ROOT/docker"
MONITORING_DIR="$PROJECT_ROOT/monitoring"
MLFLOW_DIR="$PROJECT_ROOT/mlflow"
VECTOR_DIR="$PROJECT_ROOT/demo_vector"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# ---- 参数解析 ----
KAFKA=false
AIRFLOW=false
MONITORING=false
ML=false
VECTOR=false
ALL=false

for arg in "$@"; do
    case $arg in
        --kafka|-k)    KAFKA=true ;;
        --airflow|-a)  AIRFLOW=true ;;
        --monitoring|-m) MONITORING=true ;;
        --ml|--mlflow) ML=true ;;
        --vector|-v)   VECTOR=true ;;
        --all)         ALL=true ;;
        --help|-h)
            echo "用法: bash scripts/one_click_light.sh [选项]"
            echo ""
            echo "选项:"
            echo "  --kafka, -k        启用 Kafka 消息队列"
            echo "  --airflow, -a      启用 Airflow 调度"
            echo "  --monitoring, -m   启用 Prometheus + Grafana"
            echo "  --ml, --mlflow     启用 MLflow 实验跟踪"
            echo "  --vector, -v       启用 Milvus 向量检索"
            echo "  --all              启动全部服务"
            echo "  --help, -h         显示帮助"
            exit 0
            ;;
    esac
done

if [ "$ALL" = true ]; then
    KAFKA=true
    AIRFLOW=true
    MONITORING=true
    ML=true
    VECTOR=true
fi

# ---- 打印头部 ----
echo ""
echo -e "${CYAN}${BOLD}========================================${NC}"
echo -e "${CYAN}${BOLD}  Data Platform 一键启动 (轻量模式)${NC}"
echo -e "${CYAN}${BOLD}  $(date '+%Y-%m-%d %H:%M:%S')${NC}"
echo -e "${CYAN}${BOLD}========================================${NC}"

TOTAL_STEPS=1  # 基础服务总是启动
[ "$KAFKA" = true ] && TOTAL_STEPS=$((TOTAL_STEPS + 1))
[ "$AIRFLOW" = true ] && TOTAL_STEPS=$((TOTAL_STEPS + 1))
[ "$MONITORING" = true ] && TOTAL_STEPS=$((TOTAL_STEPS + 1))
[ "$ML" = true ] && TOTAL_STEPS=$((TOTAL_STEPS + 1))
[ "$VECTOR" = true ] && TOTAL_STEPS=$((TOTAL_STEPS + 1))

CURRENT=0

step() {
    CURRENT=$((CURRENT + 1))
    echo ""
    echo -e "${CYAN}[${CURRENT}/${TOTAL_STEPS}] $1...${NC}"
}

# ---- Step 1: 基础服务 ----
step "启动基础服务 (PostgreSQL + Redis + FastAPI + Frontend)"
cd "$DOCKER_DIR"
docker compose up -d postgres redis app 2>/dev/null || docker compose up -d
echo -e "${GREEN}  ✅ App + PostgreSQL + Redis${NC}"

# ---- 等待 PostgreSQL 就绪 ----
echo -e "${YELLOW}  ⏳ 等待 PostgreSQL 就绪...${NC}"
for i in $(seq 1 30); do
    if docker exec data-platform-db pg_isready -U admin -d data_platform 2>/dev/null; then
        echo -e "${GREEN}  ✅ PostgreSQL 就绪${NC}"
        break
    fi
    sleep 1
done

# ---- Step 2: Kafka ----
if [ "$KAFKA" = true ]; then
    step "启动 Kafka 消息队列"
    cd "$DOCKER_DIR"
    docker compose -f docker-compose-kafka.yml up -d
    echo -e "${GREEN}  ✅ Zookeeper + Kafka${NC}"
fi

# ---- Step 3: Airflow ----
if [ "$AIRFLOW" = true ]; then
    step "启动 Airflow 调度服务"
    cd "$DOCKER_DIR"
    docker compose -f docker-compose-airflow.yml up -d
    echo -e "${GREEN}  ✅ Airflow (webserver + scheduler + worker)${NC}"
fi

# ---- Step 4: Monitoring ----
if [ "$MONITORING" = true ]; then
    step "启动 Prometheus + Grafana 监控"
    cd "$MONITORING_DIR"
    docker compose -f docker-compose-monitoring.yml up -d
    echo -e "${GREEN}  ✅ Prometheus + Grafana${NC}"
fi

# ---- Step 5: MLflow ----
if [ "$ML" = true ]; then
    step "启动 MLflow 实验跟踪"
    if [ -f "$MLFLOW_DIR/docker-compose.mlflow.yml" ]; then
        cd "$MLFLOW_DIR"
        docker compose -f docker-compose.mlflow.yml up -d
        echo -e "${GREEN}  ✅ MLflow Server (http://localhost:5000)${NC}"
    else
        echo -e "${YELLOW}  ⚠️  MLflow compose 文件未找到，跳过${NC}"
    fi
fi

# ---- Step 6: Vector ----
if [ "$VECTOR" = true ]; then
    step "启动 Milvus 向量检索服务"
    if [ -f "$VECTOR_DIR/docker-compose.vector.yml" ]; then
        cd "$VECTOR_DIR"
        docker compose -f docker-compose.vector.yml up -d milvus etcd minio 2>/dev/null || \
        docker compose -f docker-compose.vector.yml up -d
        echo -e "${GREEN}  ✅ Milvus + etcd + MinIO${NC}"
    else
        echo -e "${YELLOW}  ⚠️  Vector compose 文件未找到，跳过${NC}"
    fi
fi

# ---- 等待 & 状态 ----
echo ""
echo -e "${CYAN}${BOLD}========================================${NC}"
echo -e "${CYAN}${BOLD}  服务状态一览${NC}"
echo -e "${CYAN}${BOLD}========================================${NC}"
cd "$DOCKER_DIR"
docker compose ps 2>/dev/null

echo ""
echo -e "${CYAN}${BOLD}========================================${NC}"
echo -e "${CYAN}${BOLD}  访问地址${NC}"
echo -e "${CYAN}${BOLD}========================================${NC}"
echo -e "  FastAPI Docs:    ${GREEN}http://localhost:8000/docs${NC}"
echo -e "  Frontend:        ${GREEN}http://localhost:80${NC}"
echo -e "  PostgreSQL:      ${GREEN}localhost:5432${NC}"

if [ "$AIRFLOW" = true ]; then
    echo -e "  Airflow WebUI:   ${GREEN}http://localhost:8080${NC}  (airflow / airflow)"
fi
if [ "$KAFKA" = true ]; then
    echo -e "  Kafka Broker:    ${GREEN}localhost:9092${NC}"
fi
if [ "$MONITORING" = true ]; then
    echo -e "  Grafana:         ${GREEN}http://localhost:3000${NC}  (admin / admin)"
    echo -e "  Prometheus:      ${GREEN}http://localhost:9090${NC}"
fi
if [ "$ML" = true ]; then
    echo -e "  MLflow:          ${GREEN}http://localhost:5000${NC}"
fi
if [ "$VECTOR" = true ]; then
    echo -e "  Embedding API:   ${GREEN}http://localhost:8001/docs${NC}"
    echo -e "  Milvus:          ${GREEN}localhost:19530${NC}"
fi

echo ""
echo -e "${GREEN}${BOLD}✅ 轻量模式启动完成！${NC}"
echo -e "${YELLOW}💡 提示: 使用 --help 查看更多启动选项${NC}"
echo ""
