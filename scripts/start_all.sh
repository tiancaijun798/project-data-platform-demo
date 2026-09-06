#!/bin/bash
# ============================================================
# start_all.sh — 一键启动全部服务 + 初始化数据
# ============================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DOCKER_DIR="$PROJECT_ROOT/docker"
MONITORING_DIR="$PROJECT_ROOT/monitoring"
MLFLOW_DIR="$PROJECT_ROOT/mlflow"
VECTOR_DIR="$PROJECT_ROOT/demo_vector"
NEO4J_DIR="$PROJECT_ROOT/neo4j"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

print_step() { echo -e "\n${CYAN}${BOLD}[$1]${NC} ${CYAN}$2${NC}"; }
print_ok()   { echo -e "  ${GREEN}[OK]${NC} $1"; }
print_warn() { echo -e "  ${YELLOW}[WARN]${NC} $1"; }
print_err()  { echo -e "  ${RED}[ERR]${NC} $1"; }

echo ""
echo -e "${CYAN}${BOLD}========================================"
echo "  Data Platform — 一键启动全部服务"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo -e "========================================${NC}"

# ---- Step 1: 基础服务 ----
print_step "1/8" "启动基础服务 (PostgreSQL + Redis + FastAPI + Frontend)"
cd "$DOCKER_DIR"
docker compose up -d 2>/dev/null
print_ok "App + PostgreSQL + Redis + Frontend"

echo -e "${YELLOW}  等待 PostgreSQL 就绪...${NC}"
for i in $(seq 1 30); do
    docker exec data-platform-db pg_isready -U admin -d data_platform 2>/dev/null && break
    sleep 1
done
print_ok "PostgreSQL 就绪"

# ---- Step 2: Kafka ----
print_step "2/8" "启动 Kafka 消息队列"
docker compose -f docker-compose-kafka.yml up -d 2>/dev/null
print_ok "Zookeeper + Kafka"

# ---- Step 3: Airflow ----
print_step "3/8" "启动 Airflow 调度"
docker compose -f docker-compose-airflow.yml up -d 2>/dev/null
print_ok "Airflow (webserver + scheduler + worker)"

# ---- Step 4: 监控 ----
print_step "4/8" "启动 Prometheus + Grafana"
cd "$MONITORING_DIR"
docker compose -f docker-compose-monitoring.yml up -d 2>/dev/null
print_ok "Prometheus + Grafana"

# ---- Step 5: MLflow ----
print_step "5/8" "启动 MLflow 实验跟踪"
if [ -f "$MLFLOW_DIR/docker-compose.mlflow.yml" ]; then
    cd "$MLFLOW_DIR"
    docker compose -f docker-compose.mlflow.yml up -d 2>/dev/null
    print_ok "MLflow (http://localhost:5000)"
else
    print_warn "MLflow compose 未找到, 跳过"
fi

# ---- Step 6: Milvus ----
print_step "6/8" "启动 Milvus 向量检索"
if [ -f "$VECTOR_DIR/docker-compose.vector.yml" ]; then
    cd "$VECTOR_DIR"
    docker compose -f docker-compose.vector.yml up -d etcd minio milvus 2>/dev/null
    print_ok "Milvus + etcd + MinIO"
else
    print_warn "Vector compose 未找到, 跳过"
fi

# ---- Step 7: Neo4j ----
print_step "7/8" "启动 Neo4j 图数据库"
if [ -f "$NEO4J_DIR/docker-compose.neo4j.yml" ]; then
    docker network create data-platform-net 2>/dev/null || true
    cd "$NEO4J_DIR"
    docker compose -f docker-compose.neo4j.yml up -d 2>/dev/null
    print_ok "Neo4j (http://localhost:7474)"
else
    print_warn "Neo4j compose 未找到, 跳过"
fi

# ---- Step 8: 数据初始化 ----
print_step "8/8" "初始化数据"

# 等待 Milvus
if docker ps --format '{{.Names}}' | grep -q data-v-milvus; then
    echo "  等待 Milvus 就绪..."
    for i in $(seq 1 20); do
        docker exec data-v-milvus curl -sf http://localhost:9091/healthz 2>/dev/null && break
        sleep 3
    done
    print_ok "Milvus 就绪"
fi

# 等待 Neo4j
if docker ps --format '{{.Names}}' | grep -q data-platform-neo4j; then
    echo "  等待 Neo4j 就绪..."
    for i in $(seq 1 20); do
        docker exec data-platform-neo4j wget -qO- http://localhost:7474 2>/dev/null && break
        sleep 3
    done
    print_ok "Neo4j 就绪"

    # 初始化图数据
    cd "$PROJECT_ROOT"
    python neo4j/init_graph.py --seed-file data/seed_events.jsonl --limit 500 2>/dev/null && \
        print_ok "Neo4j 图数据已初始化" || \
        print_warn "Neo4j 数据初始化跳过（可能已有数据）"
fi

# 构建 RAG 知识库
if [ -d "$PROJECT_ROOT/rag_demo" ]; then
    cd "$PROJECT_ROOT"
    python rag_demo/build_knowledge_base.py --sample-size 500 --no-benchmark 2>/dev/null && \
        print_ok "RAG 知识库已构建" || \
        print_warn "RAG 知识库构建跳过"
fi

# ---- 总结 ----
echo ""
echo -e "${CYAN}${BOLD}========================================"
echo "  全部服务启动完成!"
echo -e "========================================${NC}"
echo ""
echo -e "  ${BOLD}访问地址:${NC}"
echo -e "  ${GREEN}http://localhost:3001${NC}        React 数据面板"
echo -e "  ${GREEN}http://localhost:8000/docs${NC}   FastAPI 接口文档"
echo -e "  ${GREEN}http://localhost:8080${NC}        Airflow (airflow/airflow)"
echo -e "  ${GREEN}http://localhost:3000${NC}        Grafana (admin/admin)"
echo -e "  ${GREEN}http://localhost:9090${NC}        Prometheus"
echo -e "  ${GREEN}http://localhost:5000${NC}        MLflow 实验跟踪"
echo -e "  ${GREEN}http://localhost:7474${NC}        Neo4j Browser (neo4j/changeme123)"
echo -e "  ${GREEN}http://localhost:8001/docs${NC}   Embedding API (需手动启动)"
echo -e "  ${GREEN}http://localhost:8002/docs${NC}   RAG API (需手动启动)"
echo ""
echo -e "  ${BOLD}数据管道:${NC}"
echo -e "  触发 DAG: ${CYAN}docker exec docker-airflow-webserver-1 airflow dags trigger demo_pipeline${NC}"
echo -e "  向量入库: ${CYAN}python demo_vector/embed.py --source parquet --input data/ --benchmark${NC}"
echo -e "  图查询:   ${CYAN}python neo4j/query_demo.py${NC}"
echo -e "  性能基准: ${CYAN}python benchmarks/run_benchmarks.py${NC}"
echo ""
echo -e "  ${BOLD}运行测试:${NC}"
echo -e "  ${CYAN}python -m pytest tests/ -v${NC}"
echo ""
echo -e "${GREEN}${BOLD}  Ready!${NC}"
echo ""
