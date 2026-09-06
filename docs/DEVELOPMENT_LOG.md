# 📒 开发日志 · 过程记录

> 本文件是 `project-data-platform-demo` 的**过程性记录**（逐日开发轨迹、环境拓扑、镜像加速、PR 方向等）。
> 面向简历前门的介绍请看根目录 `README.md`；按代码层阅读请看 `docs/CODE_MAP.md`。
> 这里保留的是「怎么一步步做出来 + 本机环境怎么搭」，供复盘与复现参考。

---

## 📆 开发路径（6 周 → 第 7 阶段扩展）

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

### 第5周：AI 数据基础设施升级 ✅
- [x] Day21 — Milvus 向量数据库集成 + embedding pipeline
- [x] Day22 — Feast 特征平台 (离线/在线特征存储)
- [x] Day23 — MLflow 实验跟踪 + 模型训练 demo
- [x] Day24 — RAG 知识库检索 (FAISS + Prompt 构建)
- [x] Day25 — 数据血缘可视化 (Mermaid.js)

### 第6周：工程化打磨 ✅
- [x] Day26 — CI 全面升级 (GE 校验 + 集成测试 + DAG 结构验证)
- [x] Day27 — 性能基准测试套件 (Parquet/向量/Embedding)
- [x] Day28 — 轻量一键启动脚本
- [x] Day29 — 全部模块 README 文档化
- [x] Day30 — 项目升级汇总 & 面试材料准备

### 第7阶段：AI 工作台 + 图分析 + 数据互操作 ✅
- Neo4j 图数据库模块（行为路径/商品共现/漏斗/协同过滤/高价值用户）
- RAG 知识库升级：LLM 问答生成器（DeepSeek/OpenAI 兼容）、检索→Prompt 链路测试化
- 前端 AI 工作台：AI Lab / 图分析 / 血缘 / MLflow 四页 + 中英 i18n + nginx 反代
- FastAPI `/api/ai/*` 网关聚合向量检索/RAG/图查询/MLflow
- SQL Server 互操作导出（Postgres→CSV UTF-8 BOM）、百万级事件生成脚本
- 一键启动全部服务（`start_all.bat` / `one_click_start.sh`）+ 轻量版编排

---

## 🏗️ 环境就绪状态（本机开发拓扑）

| 环境层 | 检测日期 | 状态 |
|--------|---------|------|
| Windows 宿主机 | 2026-07-20 | ✅ 就绪 |
| VirtualBox Ubuntu VM | 2026-07-20 | ✅ 就绪（SSH 配置完成） |
| Docker Desktop | 2026-07-20 | ✅ 就绪（约 7.65 GiB） |
| GitHub 仓库 | 2026-07-20 | 🚀 活跃开发中 |

> 说明：宿主机 + VM + 容器是本机开发拓扑；仓库内 `docker/`、`scripts/` 提供纯容器化一键启动路径（见根 README「快速开始」）。

---

## 🔧 镜像加速策略

| 工具 | 镜像源 | 状态 |
|------|--------|------|
| pip | `https://pypi.tuna.tsinghua.edu.cn/simple` | ✅ |
| Conda | `https://mirrors.tuna.tsinghua.edu.cn/anaconda/...` | ✅ |
| apt | `https://mirrors.tuna.tsinghua.edu.cn` | ✅ |
| Docker Hub | `https://docker.m.daocloud.io` | ✅ |
| Helm Charts | Bitnami (官方) | ✅ |

> 这些是针对国内网络的本机配置；在 CI / 海外环境会回退到官方源，不影响仓库在任意环境构建。

---

## 📝 开源 PR 备选方向（调研，未全部落地）

| 项目 | 方向 | 难度 | 通过率 |
|------|------|:--:|:--:|
| Apache Airflow | 提交自定义 Demo DAG 示例 | 🟢 低 | 高 |
| dbt | 补充数据建模最佳实践文档 | 🟢 低 | 高 |
| Great Expectations | 修复文档瑕疵、新增教程代码 | 🟢 低 | 高 |
| Apache Iceberg | Python API 使用示例 PR | 🟡 中 | 中 |

---

## 📎 附录：环境变量与常见问题（运行参考）

### 必需环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DATA_PLATFORM_DB_HOST` | `data-platform-db` | PostgreSQL 主机 |
| `DATA_PLATFORM_DB_PORT` | `5432` | PostgreSQL 端口 |
| `DATA_PLATFORM_DB_USER` | `admin` | 数据库用户 |
| `DATA_PLATFORM_DB_PASSWORD` | `changeme` | **生产环境务必修改！** |
| `DATA_PLATFORM_DB_NAME` | `data_platform` | 数据库名 |
| `SPARK_MODE` | `local` | `local`=容器内执行 / `remote`=SSH 到 VM |
| `VM_HOST` / `VM_USER` / `VM_PASS` | — | Spark 远端执行 VM 配置（仅 remote 模式） |
| `LLM_API_KEY` | `your-api-key-here` | RAG LLM 问答密钥（DeepSeek/OpenAI 兼容） |
| `LLM_API_BASE_URL` | `https://api.deepseek.com/v1` | LLM API 地址 |
| `EMBEDDING_BACKEND` | `local` | `local`=sentence-transformers / `openai`=Embedding API |
| `NEO4J_URI` / `NEO4J_USER` / `NEO4J_PASSWORD` | `bolt://localhost:7687` / `neo4j` / `changeme123` | Neo4j 连接 |

复制 `.env.example` 为 `.env` 并修改；轻量模式用 `.env.example.light`。

### 常见问题排查

| 问题 | 原因 | 解决 |
|------|------|------|
| Airflow 无法连接数据库 | `airflow-postgres` 容器未启动 | `docker compose -f docker-compose-airflow.yml up -d airflow-postgres airflow-redis` |
| `generate_events` 失败 | Kafka 未运行 | `docker compose -f docker-compose-kafka.yml up -d` |
| `check_dbt_env` 显示 "dbt 未安装" | 正常现象，dbt 在宿主机运行 | 不影响，已在宿主机配置好 |
| Grafana 无数据 | Prometheus 目标离线 | 检查 `http://localhost:9090/targets` |
| Prometheus targets DOWN | 缺少 exporter 容器 | 目前只需 airflow-statsd + prometheus + app 三个 UP |
| API `/api/stats/*` 500 错误 | 数据库连接失败 | 确认 `data-platform-db` 容器运行中，检查环境变量 |
| Parquet 输出为空 | 源数据缺失 | 运行 `python scripts/generate_real_data.py` 生成测试数据 |
| MLflow 5000 端口被占 | Steam++ 等工具拦截 | 已改走前端 `/proxy/mlflow/`，不映射主机 5000 端口 |

### 一键重置

```bash
# 软重置（保留数据）
bash scripts/one_click_reset.sh

# 硬重置（删除所有数据卷）
bash scripts/one_click_reset.sh --hard
```

---

*项目创建: 2026-07-20 · 4 周规划完成: 2026-07-22 · 6 周闭环 + 第 7 阶段扩展 · 维护者: 戴俊杰*
