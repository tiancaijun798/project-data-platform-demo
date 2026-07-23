#!/bin/bash
# ============================================================
# 一键启动脚本 — 启动全部数据平台服务
# 用法: bash scripts/one_click_start.sh [--monitoring] [--ml] [--vector]
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
CYAN='\033[0;36m'
NC='\033[0m'

START_MONITORING=false
START_ML=false
START_VECTOR=false

for arg in "$@"; do
    case $arg in
        --monitoring|-m) START_MONITORING=true ;;
        --ml|--mlflow)   START_ML=true ;;
        --vector|-v)     START_VECTOR=true ;;
        --all)           START_MONITORING=true; START_ML=true; START_VECTOR=true ;;
    esac
done

echo ""
echo -e "${CYAN}========================================"
echo "  Data Platform 一键启动"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo -e "========================================${NC}"

# ---- Step 1: 启动基础服务 (App + PostgreSQL + Redis) ----
echo -e "\n${CYAN}[1/4] 启动基础服务...${NC}"
cd "$DOCKER_DIR"
docker compose up -d
echo -e "${GREEN}  ✅ App + PostgreSQL + Redis${NC}"

# ---- Step 2: 启动 Kafka ----
echo -e "\n${CYAN}[2/4] 启动 Kafka 消息队列...${NC}"
docker compose -f docker-compose-kafka.yml up -d
echo -e "${GREEN}  ✅ Zookeeper + Kafka${NC}"

# ---- Step 3: 启动 Airflow ----
echo -e "\n${CYAN}[3/4] 启动 Airflow 调度服务...${NC}"
docker compose -f docker-compose-airflow.yml up -d
echo -e "${GREEN}  ✅ Airflow (webserver + scheduler + worker + triggerer)${NC}"

# ---- Step 4 (可选): 启动监控 ----
STEP=4
TOTAL=4
[ "$START_ML" = true ] && TOTAL=$((TOTAL + 1))
[ "$START_VECTOR" = true ] && TOTAL=$((TOTAL + 1))

if [ "$START_MONITORING" = true ]; then
    echo -e "\n${CYAN}[${STEP}/${TOTAL}] 启动 Prometheus + Grafana 监控...${NC}"
    cd "$MONITORING_DIR"
    docker compose -f docker-compose-monitoring.yml up -d
    echo -e "${GREEN}  ✅ Prometheus + Grafana${NC}"
else
    echo -e "\n${CYAN}[${STEP}/${TOTAL}] 跳过监控服务 (使用 --monitoring 启用)${NC}"
fi
STEP=$((STEP + 1))

# ---- Step 5 (可选): 启动 MLflow ----
if [ "$START_ML" = true ]; then
    echo -e "\n${CYAN}[${STEP}/${TOTAL}] 启动 MLflow 实验跟踪...${NC}"
    if [ -f "$MLFLOW_DIR/docker-compose.mlflow.yml" ]; then
        cd "$MLFLOW_DIR"
        docker compose -f docker-compose.mlflow.yml up -d
        echo -e "${GREEN}  ✅ MLflow Server (http://localhost:5000)${NC}"
    else
        echo -e "${RED}  ⚠️  MLflow compose 文件未找到${NC}"
    fi
else
    echo -e "\n${CYAN}[${STEP}/${TOTAL}] 跳过 MLflow (使用 --ml 启用)${NC}"
fi
STEP=$((STEP + 1))

# ---- Step 6 (可选): 启动向量检索 ----
if [ "$START_VECTOR" = true ]; then
    echo -e "\n${CYAN}[${STEP}/${TOTAL}] 启动 Milvus 向量检索服务...${NC}"
    if [ -f "$VECTOR_DIR/docker-compose.vector.yml" ]; then
        cd "$VECTOR_DIR"
        docker compose -f docker-compose.vector.yml up -d
        echo -e "${GREEN}  ✅ Milvus + Embedding API${NC}"
    else
        echo -e "${RED}  ⚠️  Vector compose 文件未找到${NC}"
    fi
else
    echo -e "\n${CYAN}[${STEP}/${TOTAL}] 跳过 Milvus 向量检索 (使用 --vector 启用)${NC}"
fi

# ---- 等待状态 ----
echo -e "\n${CYAN}等待服务就绪...${NC}"
sleep 5

echo -e "\n${CYAN}========================================"
echo "  服务状态一览"
echo -e "========================================${NC}"
cd "$DOCKER_DIR"
docker compose ps
echo ""
docker compose -f docker-compose-kafka.yml ps
echo ""
docker compose -f docker-compose-airflow.yml ps

if [ "$START_MONITORING" = true ]; then
    echo ""
    cd "$MONITORING_DIR"
    docker compose -f docker-compose-monitoring.yml ps
fi
	if [ "$START_ML" = true ] && [ -f "$MLFLOW_DIR/docker-compose.mlflow.yml" ]; then
	    echo ""
	    cd "$MLFLOW_DIR"
	    docker compose -f docker-compose.mlflow.yml ps 2>/dev/null || true
	fi
	if [ "$START_VECTOR" = true ] && [ -f "$VECTOR_DIR/docker-compose.vector.yml" ]; then
	    echo ""
	    cd "$VECTOR_DIR"
	    docker compose -f docker-compose.vector.yml ps 2>/dev/null || true
	fi

echo ""
echo -e "${CYAN}========================================"
echo "  访问地址"
echo -e "========================================${NC}"
echo -e "  FastAPI App:     ${GREEN}http://localhost:8000${NC}"
echo -e "  FastAPI Docs:    ${GREEN}http://localhost:8000/docs${NC}"
echo -e "  Airflow WebUI:   ${GREEN}http://localhost:8080${NC}  (airflow / airflow)"
echo -e "  Kafka Broker:    ${GREEN}localhost:9092${NC}"
echo -e "  PostgreSQL:      ${GREEN}localhost:5432${NC}"
echo -e "  Redis:           ${GREEN}localhost:6379${NC}"

if [ "$START_MONITORING" = true ]; then
    echo -e "  Prometheus:      ${GREEN}http://localhost:9090${NC}"
    echo -e "  Grafana:         ${GREEN}http://localhost:3000${NC}  (admin / admin)"
fi

echo -e "\n${GREEN}✅ 一键启动完成！${NC}"
echo ""
