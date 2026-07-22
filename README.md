# project-data-platform-demo

> 🏗️ 全栈数据平台演示项目 — 可一键复现的开源数据工程实战项目  
> 混合开发环境：Windows 11 + VirtualBox Ubuntu 24.04 + Docker Desktop + K3s(K8s)  
> 4周闭环交付：数据采集 → 处理 → 调度 → 质量 → 监控 → 部署

---

## 📊 项目架构

```
┌──────────────┐    ┌──────────────┐    ┌──────────────────┐
│ Kafka 消息队列 │ -> │ PySpark 离线处理│ -> │ Airflow 工作流调度│
│ (事件采集)     │    │ (JSONL→Parquet)│    │ (端到端流水线)    │
└──────────────┘    └──────────────┘    └──────────────────┘
        │                   │                      │
        └───────────────────┼──────────────────────┘
                            │
              ┌─────────────┼─────────────┐
              │             │             │
        ┌─────▼────┐ ┌─────▼─────┐ ┌─────▼──────┐
        │ dbt 建模  │ │ Great Expec│ │ Prometheus  │
        │ (数据分层) │ │ (质量校验) │ │ + Grafana   │
        └──────────┘ └───────────┘ └────────────┘
```

---

## 📋 技术栈

| 层级 | 技术 | 版本 |
|------|------|------|
| **宿主机** | Windows 11 | 24H2 |
| **虚拟化** | VirtualBox | 7.2.6 |
| **虚拟机** | Ubuntu | 24.04 LTS (64-bit, 8GB RAM) |
| **容器运行时** | Docker Desktop / Docker CE | 29.4.x |
| **容器编排** | Docker Compose / K3s (Kubernetes) | v5.x / v1.32.x |
| **消息队列** | Apache Kafka + Zookeeper | 7.5.0 |
| **工作流调度** | Apache Airflow (CeleryExecutor) | 2.10.4 |
| **数据处理** | PySpark | 3.5.x |
| **数据建模** | dbt (data build tool) | 1.8+ |
| **数据质量** | Great Expectations | 1.0+ |
| **查询引擎** | DuckDB / Trino | latest |
| **湖仓格式** | Apache Iceberg | — |
| **监控** | Prometheus + Grafana | 2.54 / 11.1 |
| **CI/CD** | GitHub Actions | — |
| **API 框架** | FastAPI | 0.115+ |
| **数据库** | PostgreSQL 16 + Redis 7 | — |
| **CLI 工具** | Git, kubectl, Helm | 2.54 / 1.34 / 3.19 |
| **开发语言** | Python + Conda | 3.13 / 25.5 |
| **代码托管** | GitHub | HTTPS + PAT |

---

## 📁 项目结构

```
project-data-platform-demo/
├── README.md                          # 项目说明文档
├── .gitignore                         # Git 忽略规则
├── requirements.txt                   # Python 依赖清单
│
├── src/                               # 应用源代码
│   ├── main.py                        # FastAPI API 入口
│   ├── kafka/                         # Kafka 消息队列脚本
│   │   ├── producer.py                # 事件生产者（生成模拟数据）
│   │   └── consumer.py                # 事件消费者（落地 JSONL）
│   └── spark/                         # PySpark 数据处理脚本
│       ├── process_data.py            # JSONL → Parquet 清洗转换
│       ├── iceberg_migrate.py         # Iceberg 湖仓迁移
│       ├── query_benchmark.py         # 多引擎查询性能对比
│       └── optimize_performance.py    # 性能优化策略
│
├── dags/                              # Airflow DAG 定义
│   ├── demo_pipeline.py               # 第1周核心流水线 (Kafka→Spark→Parquet)
│   └── dbt_daily.py                   # 第2周 dbt 每日建模调度
│
├── dbt/                               # dbt 数据建模
│   ├── dbt_project.yml                # dbt 项目配置
│   ├── profiles.yml                   # 数据库连接配置
│   ├── models/raw/                    # 原始数据层
│   │   ├── schema.yml                 # 源定义 & 校验规则
│   │   └── stg_user_events.sql        # Stage 视图
│   └── models/clean/                  # 清洗数据层
│       ├── schema.yml                 # 模型校验规则
│       ├── dim_users.sql              # 用户维度表
│       ├── dim_products.sql           # 产品维度表
│       └── fct_user_events_daily.sql  # 每日事件事实表
│
├── great_expectations/                # 数据质量框架
│   ├── great_expectations.yml         # GE 配置
│   └── expectations/
│       └── user_events_suite.json     # 事件数据校验规则集
│
├── monitoring/                        # 监控体系
│   ├── docker-compose-monitoring.yml  # Prometheus + Grafana 服务
│   ├── prometheus/
│   │   ├── prometheus.yml             # 采集配置
│   │   ├── alerts.yml                 # 告警规则
│   │   └── statsd_mapping.yml         # StatsD 指标映射
│   └── grafana/
│       ├── datasources/               # 数据源配置
│       └── dashboards/
│           └── airflow-monitoring.json # Airflow 监控面板
│
├── .github/workflows/                 # CI/CD
│   └── ci.yml                         # PR Lint + dbt Test + DAG 校验
│
├── docker/                            # Docker 容器环境
│   ├── docker-compose.yml             # 主 Compose (App+PG+Redis)
│   ├── docker-compose-airflow.yml     # Airflow 独立 Compose
│   ├── docker-compose-kafka.yml       # Kafka 独立 Compose
│   └── Dockerfile                     # 应用镜像
│
├── k8s/                               # Kubernetes 资源清单
│   ├── namespace.yaml
│   ├── deployment.yaml
│   └── service.yaml
│
├── scripts/                           # 工具脚本
│   ├── check_env.sh                   # 环境检测
│   ├── one_click_start.sh             # 一键启动 (Linux/Mac)
│   ├── one_click_start_windows.sh     # 一键启动 (Windows)
│   └── one_click_reset.sh             # 一键重置
│
├── environments/                      # 环境配置脚本
│   ├── windows/setup.ps1              # Windows 修复脚本
│   └── ubuntu/setup.sh                # Ubuntu 配置脚本
│
├── notebooks/                         # Jupyter 数据分析 Notebook
├── plugins/                           # Airflow 插件
├── data/                              # 数据文件 (.gitignore 排除)
└── logs/                              # 运行日志 (.gitignore 排除)
```

---

## 🚀 快速开始

### 0. 前置条件
- Docker Desktop 已安装并运行
- Git 已安装
- （可选）VirtualBox + Ubuntu 24.04 VM（用于 PySpark 在 VM 执行）

### 1. 克隆仓库
```bash
git clone https://github.com/tiancaijun798/project-data-platform-demo.git
cd project-data-platform-demo
```

### 2. 一键启动全部服务
```bash
# Linux / Mac
bash scripts/one_click_start.sh

# Windows (Git Bash)
bash scripts/one_click_start_windows.sh

# 含监控服务
bash scripts/one_click_start.sh --monitoring
```

### 3. 环境检测
```bash
bash scripts/check_env.sh
```

### 4. 访问服务

| 服务 | 地址 | 账号 |
|------|------|------|
| **Airflow WebUI** | http://localhost:8080 | airflow / airflow |
| **FastAPI App** | http://localhost:8000 | — |
| **FastAPI Docs** | http://localhost:8000/docs | — |
| **Grafana** | http://localhost:3000 | admin / admin |
| **Prometheus** | http://localhost:9090 | — |

### 5. 触发数据流水线
1. 浏览器打开 http://localhost:8080
2. 搜索 DAG `demo_pipeline`
3. 手动触发运行

---

## 📆 4周开发路径

### 第1周：环境上手 + 最小数据流水线 ✅
- [x] Day1 — 环境校验，Airflow 启动，运行示例 DAG
- [x] Day2 — 部署 Kafka+Zookeeper，Python 生产者/消费者
- [x] Day3 — PySpark JSONL→Parquet 数据清洗脚本
- [x] Day4 — 端到端 Airflow DAG (`demo_pipeline`)
- [x] Day5 — 代码整理，GitHub 提交，README

### 第2周：工程化落地 + 数据质量 ✅
- [x] Day6 — dbt 项目骨架，raw→clean 数据模型
- [x] Day7 — dbt 数据校验规则，Airflow 调度 (`dbt_daily`)
- [x] Day8 — Great Expectations 数据质量框架集成
- [x] Day9 — GitHub Actions CI（Lint + dbt + DAG 校验）
- [x] Day10 — 阶段性成果归档

### 第3周：湖仓存储 + 查询优化 + 监控体系 ✅
- [x] Day11 — Iceberg 湖仓集成（真实+模拟模式）
- [x] Day12 — DuckDB/Trino 查询性能对比
- [x] Day13 — Prometheus+Grafana 监控面板
- [x] Day14 — 性能优化策略文档
- [x] Day15 — 开源 PR 方向筛选

### 第4周：一键部署封装 + 开源贡献 + 成果复盘 ✅
- [x] Day16 — 一键启动/重置脚本
- [x] Day17 — 部署测试 & README 部署文档
- [x] Day18 — 开源 PR 备选方向整理
- [x] Day19 — 项目演示材料
- [x] Day20 — 知识点复盘

---

## 🔧 镜像加速策略

| 工具 | 镜像源 | 状态 |
|------|--------|------|
| pip | `https://pypi.tuna.tsinghua.edu.cn/simple` | ✅ |
| Conda | `https://mirrors.tuna.tsinghua.edu.cn/anaconda/...` | ✅ |
| apt | `https://mirrors.tuna.tsinghua.edu.cn` | ✅ |
| Docker Hub | `https://docker.m.daocloud.io` | ✅ |
| Helm Charts | Bitnami (官方) | ✅ |

---

## 🔑 必需环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DATA_PLATFORM_DB_HOST` | `data-platform-db` | PostgreSQL 主机 |
| `DATA_PLATFORM_DB_PORT` | `5432` | PostgreSQL 端口 |
| `DATA_PLATFORM_DB_USER` | `admin` | 数据库用户 |
| `DATA_PLATFORM_DB_PASSWORD` | `changeme` | **生产环境务必修改！** |
| `DATA_PLATFORM_DB_NAME` | `data_platform` | 数据库名 |
| `SPARK_MODE` | `local` | `local`=容器内执行 / `remote`=SSH 到 VM |
| `VM_HOST` | — | Spark 远端执行 VM 地址（仅 remote 模式） |
| `VM_USER` | — | VM SSH 用户 |
| `VM_PASS` | — | VM SSH 密码（**生产用密钥！**） |

复制 `.env.example` 为 `.env` 并修改：

```bash
cp .env.example .env
# 编辑 .env 填入你的配置
```

---

## 🚨 常见问题排查

| 问题 | 原因 | 解决 |
|------|------|------|
| Airflow 无法连接数据库 | `airflow-postgres` 容器未启动 | `docker compose -f docker-compose-airflow.yml up -d airflow-postgres airflow-redis` |
| `generate_events` 失败 | Kafka 未运行 | `docker compose -f docker-compose-kafka.yml up -d` |
| `check_dbt_env` 显示 "dbt 未安装" | 正常现象，dbt 在宿主机运行 | 不影响，已在宿主机配置好 |
| Grafana 无数据 | Prometheus 目标离线 | 检查 `http://localhost:9090/targets` |
| Prometheus targets DOWN | 缺少 exporter 容器 | 目前只需 airflow-statsd + prometheus + app 三个 UP |
| API `/api/stats/*` 500 错误 | 数据库连接失败 | 确认 `data-platform-db` 容器运行中，检查环境变量 |
| Parquet 输出为空 | 源数据缺失 | 运行 `python scripts/generate_real_data.py` 生成测试数据 |

---

## 🧪 运行测试

```bash
# 单元测试
python -m pytest tests/ -v

# 数据库初始化
bash scripts/init_database.sh

# dbt 编译验证
cd dbt && PYTHONUTF8=1 dbt compile

```bash
# Python lint
pip install flake8 && flake8 src/ --max-line-length=100

# DAG 语法校验
python -c "import sys; sys.path.insert(0,'dags'); from demo_pipeline import dag; print(f'✅ {dag.dag_id}')"

# dbt 编译验证
cd dbt && dbt compile

# 环境检测
bash scripts/check_env.sh
```

## 🔄 一键重置

```bash
# 软重置（保留数据）
bash scripts/one_click_reset.sh

# 硬重置（删除所有数据卷）
bash scripts/one_click_reset.sh --hard
```

---

## 📝 开源 PR 备选方向

| 项目 | 方向 | 难度 | 通过率 |
|------|------|:--:|:--:|
| Apache Airflow | 提交自定义 Demo DAG 示例 | 🟢 低 | 高 |
| dbt | 补充数据建模最佳实践文档 | 🟢 低 | 高 |
| Great Expectations | 修复文档瑕疵、新增教程代码 | 🟢 低 | 高 |
| Apache Iceberg | Python API 使用示例 PR | 🟡 中 | 中 |

---

## 🏗️ 环境就绪状态

| 环境层 | 检测日期 | 状态 |
|--------|---------|------|
| Windows 宿主机 | 2026-07-20 | ✅ 就绪 |
| VirtualBox Ubuntu VM | 2026-07-20 | 🔧 配置中 (SSH: tiancaijun:1234) |
| Docker Desktop | 2026-07-20 | ✅ 就绪（7.65 GiB） |
| GitHub 仓库 | 2026-07-20 | 🚀 活跃开发中 |

---

*项目创建: 2026-07-20 | 4周规划完成: 2026-07-22 | 维护者: 戴骏杰*
