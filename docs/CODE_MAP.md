# 📍 CODE_MAP · 代码地图（阅读导航）

> 配合根目录 `README.md` 使用：README 讲「项目是什么、整体怎么跑」，本文件讲「**代码在哪、看哪几个文件能最快读懂某一层**」。
> 每个关键文件头都有更详细的自述注释，这里只给「定位 + 一句话 + 关系」。

**怎么用**：想弄懂某一层 → 看对应小节，先点 `★` 文件，再看它调用了谁 / 被谁调用。

---

## ① 主后端 · FastAPI 聚合服务（一切 API 的入口）

| 文件 | 作用 | 关系 |
| --- | --- | --- |
| `src/main.py` ★ | **唯一 FastAPI 后端**：`/api/stats/*` 统计、`/api/ai/*`（向量检索/RAG问答/图查询/MLflow 代理）、`/proxy/*` 反代、静态页。启动即监控埋点 | 聚合下面全部能力；路由集中在 ~40–360 行 |
| `src/kafka_scripts/producer.py` / `consumer.py` | 事件生产者（模拟数据）→ Kafka → 消费者落地 JSONL | 主链路数据源头 |
| `src/spark/process_data.py` | JSONL → Parquet 清洗转换 | Airflow `demo_pipeline` 调用 |
| `src/spark/iceberg_migrate.py` / `query_benchmark.py` / `optimize_performance.py` | 湖仓迁移、多引擎查询对比、性能优化 | Spark 扩展脚本 |

> 想看「后端到底暴露了什么」：`src/main.py` 里搜 `@app.get/post` 即得 API 全景。

---

## ② 数据管道 · 调度 → 建模 → 质量

### 调度编排
| 文件 | 作用 |
| --- | --- |
| `dags/demo_pipeline.py` ★ | 端到端主 DAG：`generate_events → spark_process → dbt_run → GE_validate` |
| `dags/dbt_daily.py` | dbt 每日建模调度 |

### 数据建模（dbt）
| 文件 | 作用 |
| --- | --- |
| `dbt/models/raw/schema.yml` · `stg_user_events.sql` | 源定义、原始层 stage 视图 |
| `dbt/models/clean/{dim_users,dim_products}.sql` | 用户/产品维度表 |
| `dbt/models/clean/fct_user_events_daily.sql` ★ | 每日事件事实表（含空值处理） |
| `dbt/dbt_project.yml` · `profiles.yml` | dbt 项目与数据库连接配置 |

### 数据质量（Great Expectations）
| 文件 | 作用 |
| --- | --- |
| `great_expectations/great_expectations.yml` | GE 配置 |
| `great_expectations/expectations/user_events_suite.json` ★ | 事件数据校验规则集 |
| `.github/workflows/ci.yml` → `ge-validation` job | CI 里跑校验 |

> 数据血缘：`lineage/generate_lineage.py` 读 dbt `manifest.json` → 生成 `lineage/lineage_output/lineage.html`（Mermaid）。

---

## ③ AI-ML 模块（简历岗位关键词密集区）

### 向量检索 / Embedding
| 文件 | 作用 | 关系 |
| --- | --- | --- |
| `demo_vector/embed.py` ★ | embedding 生成 → **Milvus** 入库（支持后端选择/批量/基准） | 数据源可切 Parquet/dbt/synthetic |
| `demo_vector/query_api.py` | FastAPI 语义检索 `/search/events?q=` `/search/products?q=` | 独立向量检索服务 |
| `demo_vector/docker-compose.vector.yml` | Milvus + etcd + MinIO 编排 | — |

### 特征平台（Feast）
| 文件 | 作用 |
| --- | --- |
| `feast/feature_repo/` ★ | 特征仓库（FeatureView 定义） |
| `feast/run_feast_demo.py` | 离线/在线特征一致性演示 |

### 实验跟踪（MLflow）
| 文件 | 作用 |
| --- | --- |
| `mlflow/train_demo.py` ★ | RandomForest 训练，记录参数/指标/模型到 MLflow |
| `mlflow/docker-compose.mlflow.yml` | MLflow Server（经前端 `/proxy/mlflow/` 访问） |

### RAG 知识库（FAISS + LLM）
| 文件 | 作用 | 关系 |
| --- | --- | --- |
| `rag_demo/build_knowledge_base.py` ★ | Parquet/dbt 事件数据 → 分块 → embedding → **FAISS** 索引 + metadata | 产出 `rag_demo/knowledge_base/`（运行时生成，不入库） |
| `rag_demo/rag_server.py` | 检索 + Prompt 构建 API（`retrieve`/`encode_query`） | 可无 LLM key 独立跑检索 |
| `rag_demo/llm_generator.py` ★ | **LLM 问答生成器**（DeepSeek/OpenAI 兼容，可测） | RAG 链路末端 |

### 图数据库（Neo4j）
| 文件 | 作用 |
| --- | --- |
| `neo4j/init_graph.py` ★ | Parquet/JSONL 事件 → 用户-事件-商品关系图入库 |
| `neo4j/query_demo.py` | 6 类 Cypher 分析：行为路径/商品共现/漏斗/协同过滤/高价值用户/设备偏好 |
| `neo4j/docker-compose.neo4j.yml` | Neo4j 容器服务 |

### 性能基准
`benchmarks/run_benchmarks.py` — Pandas/DuckDB/Milvus 三种引擎的 Parquet 查询、向量检索、embedding 吞吐对比。

> **AI 侧数据流**：`embed.py / build_knowledge_base.py / init_graph.py`（构建）→ `src/main.py /api/ai/*`（服务）→ 前端页（消费）。

---

## ④ 前端工作台（React + TypeScript）

| 文件 | 作用 | 关系 |
| --- | --- | --- |
| `frontend/src/pages/AILab.tsx` ★ | AI Lab：向量检索 + RAG 问答 UI | 调 `api/ai.ts` → `/api/ai/vector-search`、`rag-query` |
| `frontend/src/pages/Graph.tsx` | Neo4j 行为图查询 | `/api/ai/graph-*` |
| `frontend/src/pages/Lineage.tsx` / `MLFlow.tsx` | 血缘 / MLflow 实验浏览 | `/lineage.html`、`/proxy/mlflow/*` |
| `frontend/src/api/ai.ts` | `/api/ai/*` 网关客户端封装 | 各页共用 |
| `frontend/src/i18n/index.tsx` | 中英多语言 | 全局 |
| `frontend/src/layouts/MainLayout.tsx` | 导航骨架（含 AI 入口） | 全部页面 |
| `frontend/nginx.conf` | `/proxy/mlflow`、`/proxy/grafana` 反代 + SPA fallback | 部署层 |

---

## ⑤ 部署 / 可观测 / CI

| 位置 | 内容 |
| --- | --- |
| `start_all.bat` ★ / `start_project.ps1` | Windows 一键启动全部服务 + 初始化图/知识库 |
| `scripts/one_click_start.sh` · `one_click_light.sh` | Linux/Mac 一键启动（完整/轻量，`--neo4j --ml --vector`） |
| `scripts/export_to_sqlserver.py` / `generate_massive_data.py` | Postgres→SQL Server CSV 导出 / 百万级事件生成 |
| `docker/docker-compose.yml` + 各模块 compose | 服务编排 |
| `monitoring/`（prometheus + grafana dashboards） | 指标采集与面板 |
| `k8s/` | K8s 资源清单（namespace/deployment/service） |
| `.github/workflows/ci.yml` ★ | 8 job：lint+单测 / GE / smoke / dbt / DAG / 集成 / AI-ML smoke / 汇总徽章 |

---

## 🧭 三分钟路线（给面试官的最短路径）

1. **验证「平台能不能跑」** → 根目录 `start_all.bat` / `scripts/one_click_start.sh`，服务表见 README「快速开始」
2. **验证「数据管道闭环」** → `dags/demo_pipeline.py`（一条 DAG 串 Kafka→Spark→dbt→GE）→ `dbt/models/clean/`
3. **验证「AI 数据设施深度」** → `rag_demo/llm_generator.py` + `build_knowledge_base.py`（RAG 链路可测）→ `neo4j/query_demo.py`（6 类图分析）→ `demo_vector/embed.py`（Milvus）
4. **验证「后端 API + 前端真联」** → `src/main.py` 搜 `@app.get("/api/ai` → `frontend/src/pages/AILab.tsx`
5. **验证「质量/工程化」** → `.github/workflows/ci.yml` + `tests/` + `great_expectations/`
