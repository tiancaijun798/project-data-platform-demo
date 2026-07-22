#!/bin/bash
# ============================================================
# 环境检测脚本 — 分层校验全栈环境就绪状态
# 用法: bash scripts/check_env.sh
# ============================================================
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

pass_count=0
fail_count=0
warn_count=0

check() {
    local label="$1"
    local cmd="$2"
    local expected="$3"
    printf "  %-40s " "$label"
    if eval "$cmd" &>/dev/null; then
        local ver=$(eval "$cmd" 2>/dev/null | head -1)
        printf "${GREEN}✅${NC}  %s\n" "$ver"
        ((pass_count++))
    else
        printf "${RED}❌${NC}  未安装或不可用"
        if [ -n "$expected" ]; then
            printf " (期望: %s)" "$expected"
        fi
        printf "\n"
        ((fail_count++))
    fi
}

echo ""
echo "========================================"
echo "  环境就绪检测报告"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================"

# ---- 第1层：操作系统 ----
echo -e "\n${CYAN}[第1层] 操作系统${NC}"
check "OS/Kernel"       "uname -s"
check "Architecture"    "uname -m"
echo "  主机名: $(hostname)"

# ---- 第2层：CLI 工具 ----
echo -e "\n${CYAN}[第2层] CLI 工具${NC}"
check "Git"             "git --version"              ">=2.40"
check "Python"          "python3 --version"          "Python 3.13"
check "pip"             "pip3 --version"             ">=24"
check "Conda"           "conda --version"            "Conda 25"

# ---- 第3层：容器运行时 ----
echo -e "\n${CYAN}[第3层] 容器运行时${NC}"
check "Docker"          "docker --version"           ">=29"
check "Docker Compose"  "docker compose version"     ">=v5"
check "kubectl"         "kubectl version --client --short 2>/dev/null || kubectl version --client" ">=1.30"
check "Helm"            "helm version --short"       ">=3.19"

# ---- 第4层：Docker 运行状态 ----
echo -e "\n${CYAN}[第4层] Docker 运行状态${NC}"
if docker info &>/dev/null; then
    echo -e "  Docker Desktop:  ${GREEN}✅ 运行中${NC}"
    echo "  容器数: $(docker ps -q 2>/dev/null | wc -l)"
    echo "  镜像数: $(docker images -q 2>/dev/null | wc -l)"
    ((pass_count++))
else
    echo -e "  Docker Desktop:  ${RED}❌ 未运行${NC}"
    ((fail_count++))
fi

# ---- 第5层：Airflow 服务 ----
echo -e "\n${CYAN}[第5层] Airflow 服务${NC}"
for svc in airflow-webserver airflow-scheduler airflow-worker airflow-postgres airflow-redis; do
    if docker ps --format '{{.Names}}' 2>/dev/null | grep -q "$svc"; then
        echo -e "  $svc:  ${GREEN}✅${NC}"
        ((pass_count++))
    else
        echo -e "  $svc:  ${YELLOW}⚠️  未运行${NC}"
        ((warn_count++))
    fi
done

# ---- 第6层：Kafka 服务 ----
echo -e "\n${CYAN}[第6层] Kafka 服务${NC}"
for svc in data-kafka data-zookeeper; do
    if docker ps --format '{{.Names}}' 2>/dev/null | grep -q "$svc"; then
        echo -e "  $svc:  ${GREEN}✅${NC}"
        ((pass_count++))
    else
        echo -e "  $svc:  ${YELLOW}⚠️  未运行${NC}"
        ((warn_count++))
    fi
done

# ---- 第7层：端口监听 ----
echo -e "\n${CYAN}[第7层] 端口监听${NC}"
for port in 8000 8080 9092 5432 6379; do
    case $port in
        8000) label="FastAPI App";;
        8080) label="Airflow WebUI";;
        9092) label="Kafka Broker";;
        5432) label="PostgreSQL";;
        6379) label="Redis";;
    esac
    if command -v ss &>/dev/null; then
        if ss -tlnp 2>/dev/null | grep -q ":$port "; then
            echo -e "  :$port ($label):  ${GREEN}✅${NC}"
            ((pass_count++))
        else
            echo -e "  :$port ($label):  ${YELLOW}⚠️  未监听${NC}"
            ((warn_count++))
        fi
    elif command -v netstat &>/dev/null; then
        if netstat -tlnp 2>/dev/null | grep -q ":$port "; then
            echo -e "  :$port ($label):  ${GREEN}✅${NC}"
            ((pass_count++))
        else
            echo -e "  :$port ($label):  ${YELLOW}⚠️  未监听${NC}"
            ((warn_count++))
        fi
    else
        echo -e "  :$port ($label):  ${YELLOW}⚠️  无法检测（缺少 ss/netstat）${NC}"
        ((warn_count++))
    fi
done

# ---- 第8层：GitHub 连接 ----
echo -e "\n${CYAN}[第8层] GitHub 连接${NC}"
if git remote -v 2>/dev/null | grep -q "github.com"; then
    echo -e "  Remote: ${GREEN}✅${NC} $(git remote get-url origin 2>/dev/null)"
    ((pass_count++))
else
    echo -e "  Remote: ${RED}❌ 未配置${NC}"
    ((fail_count++))
fi

# ---- 汇总 ----
echo ""
echo "========================================"
echo "  检测汇总"
echo "========================================"
echo -e "  通过: ${GREEN}${pass_count}${NC}"
echo -e "  警告: ${YELLOW}${warn_count}${NC}"
echo -e "  失败: ${RED}${fail_count}${NC}"
echo "========================================"

if [ "$fail_count" -gt 0 ]; then
    echo -e "\n  ${RED}⚠️  存在不满足项，请检查后重试${NC}\n"
    exit 1
else
    echo -e "\n  ${GREEN}✅ 所有环境就绪${NC}\n"
    exit 0
fi
