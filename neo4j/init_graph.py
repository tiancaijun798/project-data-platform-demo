#!/usr/bin/env python3
"""
Neo4j 图数据库初始化 — 从 Parquet/JSONL 数据构建用户-事件-商品关系图。

图模型:
    (:User) -[:PERFORMED]-> (:Event) -[:ON_PRODUCT]-> (:Product)
    (:Event) -[:NEXT_EVENT]-> (:Event)  (同一用户的事件时间序列)

数据源（优先级降序）:
    1. data/output_parquet/   — Parquet 事件数据
    2. data/seed_events.jsonl — 种子数据
    3. 内存生成合成数据

用法:
    python neo4j/init_graph.py
    python neo4j/init_graph.py --parquet-dir data/output_parquet --limit 2000
    python neo4j/init_graph.py --clear  # 清空图后重建
"""

import argparse
import json
import os
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

# ---- 路径 ----
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DEFAULT_PARQUET_DIR = PROJECT_ROOT / "data" / "output_parquet"
DEFAULT_SEED_FILE = PROJECT_ROOT / "data" / "seed_events.jsonl"

# ---- Neo4j 连接 ----
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "changeme123")


def get_driver(uri: Optional[str] = None, user: Optional[str] = None,
               password: Optional[str] = None):
    """创建 Neo4j driver 连接。"""
    try:
        from neo4j import GraphDatabase
    except ImportError:
        print("[ERROR] 请安装 neo4j 驱动: pip install neo4j")
        sys.exit(1)

    uri = uri or NEO4J_URI
    user = user or NEO4J_USER
    password = password or NEO4J_PASSWORD
    driver = GraphDatabase.driver(uri, auth=(user, password))
    # 验证连接
    driver.verify_connectivity()
    print(f"  [OK] 已连接 Neo4j: {uri}")
    return driver


def clear_graph(driver):
    """清空图中所有节点和关系。"""
    print("  [CLEAR] 清空现有图数据...")
    with driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")
    print("  [OK] 图已清空")


def create_constraints(driver):
    """创建唯一性约束和索引。"""
    print("  [INDEX] 创建约束和索引...")
    with driver.session() as session:
        constraints = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (u:User) REQUIRE u.user_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Product) REQUIRE p.product_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (e:Event) REQUIRE e.event_id IS UNIQUE",
        ]
        indexes = [
            "CREATE INDEX IF NOT EXISTS FOR (u:User) ON (u.user_segment)",
            "CREATE INDEX IF NOT EXISTS FOR (e:Event) ON (e.event_type)",
            "CREATE INDEX IF NOT EXISTS FOR (e:Event) ON (e.timestamp)",
            "CREATE INDEX IF NOT EXISTS FOR (p:Product) ON (p.category)",
        ]
        for c in constraints:
            session.run(c)
        for idx in indexes:
            session.run(idx)
    print("  [OK] 约束和索引已创建")


def load_events(source_type: str, parquet_dir: Optional[Path] = None,
                seed_file: Optional[Path] = None,
                limit: int = 5000) -> list[dict]:
    """加载事件数据。返回 list[dict]。"""
    events = []

    if source_type == "parquet" and parquet_dir and parquet_dir.exists():
        print(f"  [LOAD] 从 Parquet 加载: {parquet_dir}")
        import pandas as pd
        import pyarrow.parquet as pq

        pq_files = []
        for root, dirs, files in os.walk(parquet_dir):
            for f in files:
                if f.endswith(".parquet"):
                    pq_files.append(os.path.join(root, f))

        if pq_files:
            dfs = []
            for fp in pq_files:
                dfs.append(pq.read_table(fp).to_pandas())
            df = pd.concat(dfs, ignore_index=True)
            if len(df) > limit:
                df = df.sample(n=limit, random_state=42)
            events = df.to_dict(orient="records")
            # 标准化 key 名
            for e in events:
                e_lower = {k.lower(): v for k, v in e.items()}
                e.clear()
                e.update(e_lower)

    if not events and seed_file and seed_file.exists():
        print(f"  [LOAD] 从种子数据加载: {seed_file}")
        with open(seed_file, "r", encoding="utf-8") as f:
            for line in f:
                events.append(json.loads(line.strip()))
                if len(events) >= limit:
                    break

    if not events:
        print(f"  [SYNTH] 生成合成数据 ({limit} 条)...")
        events = _generate_synthetic(limit)

    print(f"  [OK] 加载 {len(events)} 条事件")
    return events


def _generate_synthetic(n: int) -> list[dict]:
    """生成合成事件数据。"""
    import random
    random.seed(42)

    event_types = ["view", "click", "search", "add_to_cart", "purchase"]
    event_weights = [0.40, 0.25, 0.15, 0.12, 0.08]
    devices = ["desktop", "mobile", "tablet"]
    browsers = ["Chrome", "Safari", "Firefox", "Edge"]
    categories = ["Electronics", "Clothing", "Food", "Home", "Sports", "Books", "Beauty"]

    events = []
    base_ts = datetime(2026, 7, 20, 0, 0, 0).timestamp()

    for i in range(n):
        et = random.choices(event_types, weights=event_weights)[0]
        events.append({
            "event_id": str(uuid.uuid4()),
            "user_id": f"U{random.randint(1, 100):04d}",
            "event_type": et,
            "product_id": f"P{random.randint(1, 50):04d}" if random.random() < 0.7 else None,
            "product_category": random.choice(categories),
            "timestamp": datetime.fromtimestamp(
                base_ts + i * random.randint(60, 3600)
            ).isoformat() + "+00:00",
            "page": random.choice(["home", "product_detail", "checkout", "search", "category"]),
            "referrer": random.choice(["google", "direct", "wechat", "email"]),
            "device": random.choice(devices),
            "browser": random.choice(browsers),
            "duration_ms": random.randint(100, 120000),
        })

    return events


def build_graph(driver, events: list[dict], batch_size: int = 500):
    """将事件数据批量写入 Neo4j 图。"""
    print(f"\n  [BUILD]  构建图 ({len(events)} 条事件)...")
    t0 = time.time()

    # 使用 Cypher 批量合并节点和关系
    merge_user = """
    UNWIND $batch AS row
    MERGE (u:User {user_id: row.user_id})
    ON CREATE SET u.created_at = timestamp()
    ON MATCH SET u.last_seen = row.event_ts
    """

    merge_product = """
    UNWIND $batch AS row
    WITH row WHERE row.product_id IS NOT NULL
    MERGE (p:Product {product_id: row.product_id})
    ON CREATE SET
        p.category = row.product_category,
        p.created_at = timestamp()
    ON MATCH SET
        p.category = row.product_category
    """

    merge_event = """
    UNWIND $batch AS row
    MERGE (e:Event {event_id: row.event_id})
    ON CREATE SET
        e.event_type = row.event_type,
        e.timestamp = row.event_ts,
        e.page = row.page,
        e.referrer = row.referrer,
        e.device = row.device,
        e.browser = row.browser,
        e.duration_ms = row.duration_ms
    ON MATCH SET
        e.event_type = row.event_type,
        e.timestamp = row.event_ts,
        e.page = row.page,
        e.referrer = row.referrer,
        e.device = row.device,
        e.browser = row.browser,
        e.duration_ms = row.duration_ms
    """

    relate_user_event = """
    UNWIND $batch AS row
    MATCH (u:User {user_id: row.user_id})
    MATCH (e:Event {event_id: row.event_id})
    MERGE (u)-[:PERFORMED]->(e)
    """

    relate_event_product = """
    UNWIND $batch AS row
    WITH row WHERE row.product_id IS NOT NULL
    MATCH (e:Event {event_id: row.event_id})
    MATCH (p:Product {product_id: row.product_id})
    MERGE (e)-[:ON_PRODUCT]->(p)
    """

    # 时间序列关系: NEXT_EVENT
    relate_next_event = """
    UNWIND $pairs AS pair
    MATCH (e1:Event {event_id: pair.prev})
    MATCH (e2:Event {event_id: pair.next})
    MERGE (e1)-[:NEXT_EVENT]->(e2)
    """

    with driver.session() as session:
        # 预处理时间戳
        for e in events:
            try:
                from datetime import datetime as dt
                e["event_ts"] = int(dt.fromisoformat(
                    e["timestamp"].replace("+00:00", "").replace("Z", "")
                ).timestamp() * 1000)
            except Exception:
                e["event_ts"] = int(time.time() * 1000)

        # 分批写入节点
        total_batches = (len(events) - 1) // batch_size + 1
        for batch_idx in range(total_batches):
            start = batch_idx * batch_size
            end = min(start + batch_size, len(events))
            batch = events[start:end]

            session.run(merge_user, batch=batch)
            session.run(merge_product, batch=batch)
            session.run(merge_event, batch=batch)
            session.run(relate_user_event, batch=batch)
            session.run(relate_event_product, batch=batch)

            if batch_idx % 10 == 0:
                print(f"    批次 {batch_idx + 1}/{total_batches} "
                      f"({end}/{len(events)} 条)")

        # 构建事件链 NEXT_EVENT 关系（按用户和时间排序）
        print("  [CHAIN] 构建事件时间链 NEXT_EVENT...")
        result = session.run("""
            MATCH (u:User)-[:PERFORMED]->(e:Event)
            WITH u, e
            ORDER BY u.user_id, e.timestamp
            WITH u, collect(e) AS events
            UNWIND range(0, size(events)-2) AS i
            RETURN events[i].event_id AS prev, events[i+1].event_id AS next
            LIMIT 5000
        """)
        pairs = [{"prev": r["prev"], "next": r["next"]} for r in result]
        if pairs:
            # 分批写入关系
            pair_batch_size = 1000
            for i in range(0, len(pairs), pair_batch_size):
                pair_batch = pairs[i:i + pair_batch_size]
                session.run(relate_next_event, pairs=pair_batch)

    elapsed = time.time() - t0
    print(f"  [OK] 图构建完成 ({elapsed:.1f}s)")

    return get_graph_stats(driver)


def get_graph_stats(driver) -> dict:
    """获取图统计信息。"""
    with driver.session() as session:
        result = session.run("""
            MATCH (u:User)
            WITH count(u) AS users
            MATCH (e:Event)
            WITH users, count(e) AS events
            MATCH (p:Product)
            WITH users, events, count(p) AS products
            MATCH ()-[r:PERFORMED]->()
            WITH users, events, products, count(r) AS performed
            MATCH ()-[r2:ON_PRODUCT]->()
            WITH users, events, products, performed, count(r2) AS on_product
            MATCH ()-[r3:NEXT_EVENT]->()
            RETURN users, events, products, performed, on_product, count(r3) AS next_events
        """).single()

    stats = {
        "nodes": {
            "User": result["users"],
            "Event": result["events"],
            "Product": result["products"],
        },
        "relationships": {
            "PERFORMED": result["performed"],
            "ON_PRODUCT": result["on_product"],
            "NEXT_EVENT": result["next_events"],
        },
    }

    print(f"\n  [STATS] 图统计:")
    print(f"     Nodes:     User={stats['nodes']['User']}, "
          f"Event={stats['nodes']['Event']}, "
          f"Product={stats['nodes']['Product']}")
    print(f"     Relationships: PERFORMED={stats['relationships']['PERFORMED']}, "
          f"ON_PRODUCT={stats['relationships']['ON_PRODUCT']}, "
          f"NEXT_EVENT={stats['relationships']['NEXT_EVENT']}")

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Neo4j 图数据库初始化 — 构建用户行为图谱"
    )
    parser.add_argument("--parquet-dir", type=Path, default=DEFAULT_PARQUET_DIR,
                        help="Parquet 数据目录")
    parser.add_argument("--seed-file", type=Path, default=DEFAULT_SEED_FILE,
                        help="种子 JSONL 文件")
    parser.add_argument("--limit", type=int, default=5000,
                        help="最大事件数")
    parser.add_argument("--clear", action="store_true",
                        help="清空图后重建")
    parser.add_argument("--uri", default=NEO4J_URI, help="Neo4j Bolt URI")
    parser.add_argument("--user", default=NEO4J_USER, help="Neo4j 用户")
    parser.add_argument("--password", default=NEO4J_PASSWORD, help="Neo4j 密码")
    args = parser.parse_args()

    print("=" * 60)
    print("  [Neo4j] Graph Database Initialization")
    print("=" * 60)

    # 检测数据源
    source_type = "synthetic"
    if args.parquet_dir and args.parquet_dir.exists():
        source_type = "parquet"
    elif args.seed_file and args.seed_file.exists():
        source_type = "seed"

    print(f"  Neo4j: {args.uri}")
    print(f"  数据源: {source_type}")
    print(f"  上限: {args.limit} 条")

    # 连接
    driver = get_driver(args.uri, args.user, args.password)

    try:
        # 清空
        if args.clear:
            clear_graph(driver)

        # 创建约束
        create_constraints(driver)

        # 加载数据
        events = load_events(
            source_type, args.parquet_dir, args.seed_file, args.limit
        )

        # 构建图
        stats = build_graph(driver, events)

        print(f"\n[OK] Neo4j 图数据库初始化完成!")
        print(f"[TIP] 访问 Neo4j Browser: http://localhost:7474 (neo4j/changeme123)")
        print(f"[TIP] 运行查询演示: python neo4j/query_demo.py")

    finally:
        driver.close()


if __name__ == "__main__":
    main()
