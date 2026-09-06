# 🕸️ Neo4j 图数据库 — 用户行为图谱分析

> 将关系型事件数据转为属性图，通过 Cypher 实现行为路径、商品共现、协同过滤推荐等图分析。

---

## 图模型

```
┌──────────┐     PERFORMED      ┌──────────┐     ON_PRODUCT     ┌──────────┐
│  :User   │ ──────────────────▶│  :Event  │ ──────────────────▶│ :Product │
│ user_id  │                    │ event_id │                    │product_id│
│ segment  │                    │ type     │                    │ category │
└──────────┘                    │ timestamp│                    └──────────┘
                                │ device   │
                                │ browser  │
                                └──────────┘
                                     │
                                     │ NEXT_EVENT (时间序列)
                                     ▼
                                ┌──────────┐
                                │  :Event  │
                                └──────────┘
```

- **User** 节点: user_id (唯一), user_segment, total_events
- **Event** 节点: event_id (唯一), event_type, timestamp, device, browser, page, referrer
- **Product** 节点: product_id (唯一), category
- **PERFORMED** 关系: User → Event
- **ON_PRODUCT** 关系: Event → Product
- **NEXT_EVENT** 关系: Event → Event (同一用户按时间排序)

---

## 快速开始

### 1. 启动 Neo4j

```bash
# 确保 data-platform-net 已存在
docker network create data-platform-net 2>/dev/null || true

# 启动 Neo4j
docker compose -f neo4j/docker-compose.neo4j.yml up -d

# 等待就绪（约 30 秒）
```

### 2. 初始化图数据

```bash
# 安装依赖
pip install neo4j

# 从 Parquet 数据构建图
python neo4j/init_graph.py --parquet-dir data/output_parquet --limit 3000

# 从种子数据构建
python neo4j/init_graph.py --seed-file data/seed_events.jsonl

# 清空后重建
python neo4j/init_graph.py --clear --limit 5000
```

### 3. 运行查询演示

```bash
python neo4j/query_demo.py              # 运行全部查询
python neo4j/query_demo.py --query path --user-id U0005
python neo4j/query_demo.py --query recommend --user-id U0010
```

### 4. Neo4j Browser

打开 http://localhost:7474，使用 `neo4j` / `changeme123` 登录，可在可视化界面中执行 Cypher 查询并查看节点关系图。

---

## 演示查询

### 1. 用户行为路径

```cypher
MATCH (u:User {user_id: 'U0001'})-[:PERFORMED]->(e:Event)
OPTIONAL MATCH (e)-[:ON_PRODUCT]->(p:Product)
RETURN e.event_type, e.timestamp, p.product_id
ORDER BY e.timestamp
```

### 2. 商品共现

```cypher
MATCH (p1:Product)<-[:ON_PRODUCT]-(e:Event)-[:ON_PRODUCT]->(p2:Product)
WHERE p1.product_id < p2.product_id
RETURN p1.product_id, p2.product_id, count(e) AS co_count
ORDER BY co_count DESC LIMIT 10
```

### 3. 协同过滤推荐

```cypher
MATCH (u:User {user_id: 'U0001'})-[:PERFORMED]->(:Event)-[:ON_PRODUCT]->(p:Product)
WITH u, collect(DISTINCT p) AS my_products
MATCH (u)-[:PERFORMED]->(:Event)-[:ON_PRODUCT]->(p)<-[:ON_PRODUCT]-(:Event)<-[:PERFORMED]-(other:User)
WHERE other <> u
MATCH (other)-[:PERFORMED]->(:Event)-[:ON_PRODUCT]->(rec:Product)
WHERE NOT rec IN my_products
RETURN rec.product_id, rec.category, count(*) AS strength
ORDER BY strength DESC LIMIT 5
```

---

## 面试展示要点

1. **"我将关系型事件数据建模为属性图，支持行为路径和推荐分析"**
2. **"Cypher 查询比 SQL 更适合表达多跳关系（如'购买了X的用户也购买了Y'）"**
3. **"User→Event→Product 三元组可以扩展为更复杂的推荐图（KGAT / GraphSAGE）"**
4. **"Neo4j GDS 库支持 Louvain 社区发现、PageRank 等图算法"**

---

## 技术决策

**为什么 Neo4j 而不是其他图数据库？**
- Neo4j Community Edition 免费、Docker 部署简单
- Cypher 是最成熟的图查询语言，学习曲线平缓
- GDS (Graph Data Science) 库提供丰富的图算法
- 在面试中展示"图数据库"是 JD 中提到的加分项

**与 PostgreSQL 的互补关系：**
- PostgreSQL 负责 OLAP 聚合、报表、dbt 建模
- Neo4j 负责关系发现、路径分析、图算法
- 两者不冲突，数据通过 `init_graph.py` 从 Parquet/PostgreSQL 同步到 Neo4j
