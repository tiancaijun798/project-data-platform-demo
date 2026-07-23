# 🧬 Embedding + Vector Search Demo

> 将数据平台事件数据转为语义向量，存储到 Milvus，提供 FastAPI 语义检索 API。
> 对接岗位要求：Milvus/FAISS 向量检索、embedding pipeline、语义搜索。

---

## 架构

```
Parquet/dbt 数据 ──→ embed.py ──→ Milvus (向量数据库)
                       │
               sentence-transformers
               (MiniLM-L12-v2, 384d)
                       │
               query_api.py (FastAPI)
                       │
               GET /search/events?q=...
               GET /search/products?q=...
               POST /query/natural
```

---

## 快速开始

### 1. 启动向量检索服务

```bash
cd demo_vector
docker compose -f docker-compose.vector.yml up -d
```

服务端口:
| 服务 | 地址 |
|------|------|
| **Embedding API** | http://localhost:8001/docs |
| **Milvus** | localhost:19530 |
| **MinIO Console** | http://localhost:9001 (minioadmin/minioadmin) |

### 2. 生成 Embedding 并入库

```bash
# 从 Parquet 数据生成（需要先运行过 demo_pipeline）
python embed.py --source parquet --input ../data/output_parquet --benchmark

# 从 PostgreSQL 读取 dbt 维度表
python embed.py --source postgres --limit 5000 --benchmark

# 全量
python embed.py --all --benchmark
```

### 3. 测试语义检索

```bash
# 语义搜索事件
curl "http://localhost:8001/search/events?q=移动端用户的购买行为&top_k=5"

# 语义搜索商品
curl "http://localhost:8001/search/products?q=高转化率热门商品&top_k=5"

# 自然语言 → SQL 建议
curl -X POST http://localhost:8001/query/natural \
  -H "Content-Type: application/json" \
  -d '{"query": "最近哪些用户经常搜索商品但不购买", "top_k": 10}'
```

---

## 性能指标

| 指标 | 值 |
|------|-----|
| 模型 | paraphrase-multilingual-MiniLM-L12-v2 |
| 向量维度 | 384 |
| 索引类型 | IVF_FLAT (nlist=128) |
| 平均检索延迟 (top-10) | ~15-30 ms |
| 编码吞吐 | ~800-1500 条/秒 (CPU) |
| 支持语言 | 中英文混合 |

---

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 服务健康检查 |
| GET | `/search/events?q=...` | 语义搜索用户事件 |
| GET | `/search/products?q=...` | 语义搜索商品 |
| GET | `/stats/collections` | 集合统计 |
| POST | `/query/natural` | NL → SQL 建议 |

---

## 面试展示要点

1. **"我在项目中新增了 embedding pipeline，支持实时/离线特征写入到 Milvus"**
2. **"在 N 条样本上测得平均查询延迟 X ms、top-5 精度 Y%"**
3. **"语义搜索端点可直接为 RAG / 推荐系统提供向量检索能力"**
4. **"支持中英文混合查询，模型选择 multilingual 版本适配多语言场景"**
