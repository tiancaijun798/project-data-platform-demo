# project-data-platform-demo

> **端到端数据 & AI 平台 Demo** — Kafka → PySpark → dbt → Feast → MLflow → Milvus/FAISS → RAG → Neo4j → Airflow → GE → Prometheus/Grafana → FastAPI + React。
> **一键部署 · Docker Compose 复现 · 全链路数据/AI 工程实践**

一个把**数据工程主链**（采集/处理/建模/质量/调度/监控）与**AI 数据基础设施**（向量检索 / 特征平台 / 实验跟踪 / RAG 知识库 / 图分析）串起来、可一键跑通的工程演示。

> ⚙️ 环境：Windows 11 + VirtualBox Ubuntu 24.04 + Docker Desktop + K3s；全部服务容器化，`start_all.bat` / `one_click_start.sh` 一键拉起。

---

## ✨ 能力

| 能力域 | 落地组件 | 关键点 |
| --- | --- | --- |
| **数据管道工程** | Kafka → PySpark → Airflow → dbt | 消息采集、JSONL→Parquet、端到端 DAG 调度、`raw→clean` 分层建模 |
| **数据质量治理** | Great Expectations + dbt test | 期望套件校验 + 模型约束 + CI 集成 |
| **向量检索 / Embedding** | Milvus + sentence-transformers | 事件/商品语义搜索，384 维 embedding pipeline（实时+离线） |
| **特征平台** | Feast（离线/在线特征） | 与 dbt clean 层对接，训练/在线一致性特征，OnDemand FeatureView |
| **实验跟踪 / 模型** | MLflow + scikit-learn | RandomForest 训练、参数/指标记录、Model Registry，经前端反代访问 |
| **RAG 知识库** | FAISS + LLM（DeepSeek/OpenAI 兼容） | 事件数据分块→索引→语义检索→Prompt 构建→LLM 问答，可测（无 key 也可跑检索） |
| **图数据库分析** | Neo4j + Cypher | 用户行为图、商品共现、转化漏斗、协同过滤推荐、高价值用户发现 |
| **数据血缘可视化** | dbt manifest + Mermaid.js | 表级/列级血缘 HTML 图 |
| **性能基准** | Pandas / DuckDB / Milvus | Parquet 查询、向量检索、embedding 吞吐对比脚本 |
| **可观测 / 部署** | Prometheus + Grafana + K8s + CI | 实时指标面板、Docker Compose/K3s 清单、GitHub Actions 8-job 流水线 |

---

## 🏗️ 系统架构

```
┌──────────────┐    ┌──────────────┐    ┌──────────────────┐
│ Kafka 消息队列 │ -> │ PySpark 离线处理│ -> │ Airflow 工作流调度│
│ (事件采集)     │    │ (JSONL→Parquet)│    │ (端到端流水线)    │
└──────────────┘    └──────────────┘    └──────────────────┘
        │                   │                      │
        └───────────────────┼──────────────────────┘
                            │
    ┌───────────────────────┼───────────────────────────┐
    │                       │                           │
┌───▼──────┐  ┌─────────▼────┐  ┌──────────▼────┐  ┌───▼──────────┐
│ dbt 建模  │  │ Great Expect │  │ Prometheus    │  │ FastAPI API  │
│ (数据分层) │  │ (质量校验)    │  │ + Grafana     │  │ (数据产品)    │
└───┬──────┘  └──────────────┘  └───────────────┘  └───┬──────────┘
    │                                                   │
    └───────────┬───────────────────────────────────────┘
                │
    ┌───────────┼───────────────────────────┐
    │           │                           │
┌───▼────┐ ┌───▼────────┐ ┌───────────▼────┐ ┌────────────▼───┐ ┌──────────▼───┐
│ Feast  │ │ Milvus     │ │ MLflow        │ │ RAG / FAISS    │ │ Neo4j        │
│ 特征存储│ │ 向量数据库  │ │ 实验跟踪       │ │ 知识库检索      │ │ 图数据库      │
└────────┘ └────────────┘ └───────────────┘ └────────────────┘ └──────────────┘
```

核心数据流：`事件采集 → 批处理 → 建模/质量 → 特征 → 训练/AI → 服务 → 监控`
AI 侧数据流：`事件数据 → embedding/分块 → Milvus/FAISS 向量库 & RAG 知识库 → FastAPI /api/ai/* → React 前端`

---

## 🧭 仓库导航（读者的建议阅读顺序）

```
按模块组织的真实目录（★ = 主线入口）：
├── 主后端        src/main.py ★(FastAPI 聚合 API) / src/{kafka,spark}/
├── 调度建模      dags/(Airflow) · dbt/(分层建模) · great_expectations/(质量)
├── AI-ML 模块    demo_vector/(Milvus) · feast/ · mlflow/ · rag_demo/ · neo4j/ ★
│                 benchmarks/ · lineage/
├── 前端工作台    frontend/src/(React) ★ — AI Lab/图/血缘/MLflow 可视化
├── 部署运维      docker/ · k8s/ · monitoring/(Prometheus+Grafana) · environments/
│                 scripts/(一键启动) · start_all.bat / start_project.ps1
└── 测试与 CI     tests/ · .github/workflows/ci.yml(8 job)
```

**推荐路径 1 —— 快速看懂「做了什么」**：
`本 README` → `src/main.py`（看 `/api/*` 路由全景）→ `frontend/src/pages/`（看前端接了什么）→ 各模块 `README.md`

**推荐路径 2 —— 检查「数据管道能不能跑、质量怎么保证」**：
`start_all.bat`（一键起）→ `dags/demo_pipeline.py`（端到端 DAG）→ `dbt/`（建模）→ `great_expectations/` → `.github/workflows/ci.yml`

**推荐路径 3 —— 深挖「AI 数据基础设施」**：
`rag_demo/`(RAG 链路) → `demo_vector/`(Milvus 向量检索) → `feast/`(特征平台) → `neo4j/`(图分析) → `mlflow/`(实验跟踪)

> ⏱️ **时间有限先看 ★**：后端聚合入口 = `src/main.py`；AI 能力入口 = `rag_demo/` + `neo4j/` + `demo_vector/`。
> 🗺️ **想按文件深入读代码** → [`docs/CODE_MAP.md`](docs/CODE_MAP.md)。

---

## 🚀 快速开始

### 前置条件
Docker Desktop（已运行）、Git；可选 VirtualBox Ubuntu VM 跑 PySpark 远端模式。

### 1. 一键启动全部服务（Windows / Linux）
```bash
# Windows: 双击 或
.\start_all.bat            # PowerShell 或 cmd 运行，自动起全部 + 初始化图/知识库

# Linux / Mac / Git Bash:
bash scripts/one_click_start.sh              # 完整模式
bash scripts/one_click_start.sh --monitoring --ml --vector --neo4j
bash scripts/one_click_light.sh              # 轻量模式(仅核心，更快)
```

### 2. 访问服务

| 服务 | 地址 | 说明 |
|------|------|------|
| **前端工作台** | http://localhost:3001 | React；含 AI Lab / 图 / 血缘 / MLflow 页 |
| **FastAPI Docs** | http://localhost:8000/docs | 全部 API，含 `/api/ai/*` |
| **Airflow** | http://localhost:8080 | airflow / airflow |
| **Grafana** | http://localhost:3000 | admin / admin |
| **Neo4j Browser** | http://localhost:7474 | neo4j / changeme123 |
| **MLflow** | http://localhost:3001/mlflow/ | 经前端反代 |
| **数据血缘** | `lineage/lineage_output/lineage.html` | Mermaid 血缘图 |

### 3. 触发数据流水线
浏览器打开 Airflow → 搜索 DAG `demo_pipeline` → 手动触发 → 数据流经 Kafka→Spark→dbt 落地。

> 💡 **AI 组件**：`start_all.bat` 会顺带初始化 Neo4j 图（500 事件）与 RAG 知识库；向量/图谱的初始化脚本与入口见 `docs/CODE_MAP.md`。

---

## 🧪 测试与 CI

```bash
python -m pytest tests/ -v     # 52 项：API 端点 / embedding / LLM+RAG 单元测试
flake8 src/ dags/ tests/       # lint
bash scripts/check_env.sh      # 环境自检
```

GitHub Actions **8 个 job**：lint+单测 · GE 校验 · smoke · dbt compile/test · DAG 校验 · 集成测试 · AI/ML smoke · CI 汇总徽章。

---

## 📁 技术栈速览

| 层 | 技术 |
| --- | --- |
| 数据管道 | Kafka · PySpark · Airflow(CeleryExecutor) · dbt · Great Expectations |
| 存储/查询 | PostgreSQL 16 · Redis · DuckDB · Iceberg · MinIO |
| AI/ML 设施 | Feast · MLflow · Milvus 2.4 · FAISS · sentence-transformers · Neo4j · scikit-learn |
| 应用/前端 | FastAPI · React(TypeScript) · nginx 反代 |
| 可观测/部署 | Prometheus · Grafana · Docker Compose · K3s(K8s) · GitHub Actions |
| 语言/环境 | Python 3.13(Conda) · Git(Bash) · 多级子模块独立 requirements |

详细版本号与各模块独立文档见对应目录 `README.md`。

---

## 📄 关键文档

| 位置 | 内容 |
| --- | --- |
| `docs/CODE_MAP.md` | 按数据流分层的**代码阅读地图**（每个模块入口 + 文件关系） |
| `docs/DEVELOPMENT_LOG.md` | 6 周逐日开发日志、环境/镜像加速、开源 PR 方向（过程记录，非作品主体） |
| `benchmarks/benchmark_report.md` | 基准测试方法与说明 |
| 各模块 `README.md` | `rag_demo/` `demo_vector/` `feast/` `mlflow/` `neo4j/` `lineage/` 独立文档 |

---

