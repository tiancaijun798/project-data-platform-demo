#!/usr/bin/env python3
"""
Neo4j Cypher 查询演示 — 用户行为图谱分析。

演示查询:
    1. 用户行为路径 — 特定用户的完整事件链
    2. 商品共现分析 — 同一事件中共同出现的商品
    3. 转化漏斗 — 按事件类型聚合
    4. 热门商品推荐 — "用户也购买了..." (协同过滤)
    5. 高价值用户发现 — 事件数 > 平均值的用户
    6. 设备偏好分析 — 按设备类型聚合事件

用法:
    python neo4j/query_demo.py
    python neo4j/query_demo.py --query all
    python neo4j/query_demo.py --query path --user-id U0001
"""

import argparse
import os
import sys
from pathlib import Path

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "changeme123")


def get_driver():
    from neo4j import GraphDatabase
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    driver.verify_connectivity()
    return driver


def print_header(title: str):
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)


def query_user_path(driver, user_id: str = "U0001", limit: int = 10):
    """查询特定用户的行为路径。"""
    print_header(f"[QUERY] 用户行为路径: {user_id}")

    with driver.session() as session:
        result = session.run("""
            MATCH (u:User {user_id: $user_id})-[:PERFORMED]->(e:Event)
            OPTIONAL MATCH (e)-[:ON_PRODUCT]->(p:Product)
            RETURN e.event_type AS event_type,
                   e.timestamp AS timestamp,
                   e.page AS page,
                   e.device AS device,
                   p.product_id AS product_id,
                   p.category AS category
            ORDER BY e.timestamp
            LIMIT $limit
        """, user_id=user_id, limit=limit)

        records = list(result)
        if not records:
            print(f"  [WARN]  未找到用户 {user_id} 的事件记录")
            return

        print(f"  {'事件类型':<16s} {'时间':<20s} {'页面':<16s} {'设备':<10s} {'商品':<10s} {'品类':<12s}")
        print(f"  {'-'*16} {'-'*20} {'-'*16} {'-'*10} {'-'*10} {'-'*12}")
        for r in records:
            ts_str = str(r["timestamp"])[:19] if r["timestamp"] else "N/A"
            print(f"  {r['event_type'] or 'N/A':<16s} {ts_str:<20s} "
                  f"{r['page'] or 'N/A':<16s} {r['device'] or 'N/A':<10s} "
                  f"{r['product_id'] or 'N/A':<10s} {r['category'] or 'N/A':<12s}")


def query_product_cooccurrence(driver, limit: int = 10):
    """商品共现分析 — 被同一用户关联的商品对。"""
    print_header("[COOCCUR] 商品共现关系 (Co-occurrence)")

    with driver.session() as session:
        result = session.run("""
            MATCH (p1:Product)<-[:ON_PRODUCT]-(e:Event)-[:ON_PRODUCT]->(p2:Product)
            WHERE p1.product_id < p2.product_id
            WITH p1, p2, count(e) AS co_count
            ORDER BY co_count DESC
            LIMIT $limit
            RETURN p1.product_id AS product_a,
                   p1.category AS category_a,
                   p2.product_id AS product_b,
                   p2.category AS category_b,
                   co_count
        """, limit=limit)

        print(f"  {'商品A':<10s} {'品类A':<14s} {'商品B':<10s} {'品类B':<14s} {'共现次数':>8s}")
        print(f"  {'-'*10} {'-'*14} {'-'*10} {'-'*14} {'-'*8}")
        for r in result:
            print(f"  {r['product_a']:<10s} {r['category_a'] or 'N/A':<14s} "
                  f"{r['product_b']:<10s} {r['category_b'] or 'N/A':<14s} "
                  f"{r['co_count']:>8d}")


def query_conversion_funnel(driver):
    """转化漏斗分析。"""
    print_header("[STATS] 事件转化漏斗")

    with driver.session() as session:
        result = session.run("""
            MATCH (e:Event)
            RETURN e.event_type AS event_type, count(e) AS cnt
            ORDER BY cnt DESC
        """)

        funnel_order = ["view", "click", "search", "add_to_cart", "purchase"]
        counts = {r["event_type"]: r["cnt"] for r in result}
        total = sum(counts.values())

        print(f"  总事件数: {total}")
        print(f"  {'事件类型':<16s} {'数量':>8s} {'占比':>8s} {'漏斗':>50s}")
        print(f"  {'-'*16} {'-'*8} {'-'*8} {'-'*50}")
        for et in funnel_order:
            cnt = counts.get(et, 0)
            pct = cnt / total * 100 if total > 0 else 0
            bar = "█" * int(pct * 2)
            print(f"  {et:<16s} {cnt:>8d} {pct:>7.1f}% {bar}")


def query_collaborative_filtering(driver, user_id: str = "U0001", limit: int = 5):
    """简单协同过滤 — "和你行为相似的用户也浏览了..."。"""
    print_header(f"[RECOMMEND] 协同过滤推荐 (基于 {user_id})")

    with driver.session() as session:
        result = session.run("""
            // 找到目标用户浏览过的商品
            MATCH (u:User {user_id: $user_id})-[:PERFORMED]->(:Event)-[:ON_PRODUCT]->(p:Product)
            WITH u, collect(DISTINCT p) AS my_products

            // 找到也浏览过这些商品的其他用户
            MATCH (u)-[:PERFORMED]->(:Event)-[:ON_PRODUCT]->(p)<-[:ON_PRODUCT]-(:Event)<-[:PERFORMED]-(other:User)
            WHERE other <> u

            // 找到这些其他用户浏览过但我没浏览过的商品
            MATCH (other)-[:PERFORMED]->(:Event)-[:ON_PRODUCT]->(rec:Product)
            WHERE NOT rec IN my_products

            RETURN rec.product_id AS recommended_product,
                   rec.category AS category,
                   count(*) AS strength
            ORDER BY strength DESC
            LIMIT $limit
        """, user_id=user_id, limit=limit)

        records = list(result)
        if not records:
            print(f"  [WARN]  未找到针对 {user_id} 的推荐")
            return

        print(f"  推荐给 {user_id} 的商品:")
        print(f"  {'商品':<10s} {'品类':<14s} {'推荐强度':>8s}")
        print(f"  {'-'*10} {'-'*14} {'-'*8}")
        for r in records:
            print(f"  {r['recommended_product']:<10s} "
                  f"{r['category'] or 'N/A':<14s} {r['strength']:>8d}")


def query_high_value_users(driver, limit: int = 10):
    """发现高活跃用户。"""
    print_header("[TOP] 高活跃用户 (事件数 > 平均值)")

    with driver.session() as session:
        result = session.run("""
            MATCH (u:User)-[:PERFORMED]->(e:Event)
            WITH u, count(e) AS event_count
            MATCH (u2:User)-[:PERFORMED]->(e2:Event)
            WITH u, event_count, avg(event_count) AS avg_events
            WHERE event_count > avg_events
            RETURN u.user_id AS user_id, event_count, round(avg_events) AS avg_events
            ORDER BY event_count DESC
            LIMIT $limit
        """, limit=limit)

        print(f"  {'用户ID':<10s} {'事件数':>8s} {'平均值':>8s} {'超出':>8s}")
        print(f"  {'-'*10} {'-'*8} {'-'*8} {'-'*8}")
        for r in result:
            excess = r["event_count"] - r["avg_events"]
            print(f"  {r['user_id']:<10s} {r['event_count']:>8d} "
                  f"{r['avg_events']:>8d} {excess:>+8d}")


def query_device_preferences(driver):
    """设备偏好分析。"""
    print_header("[DEVICE] 设备偏好分析")

    with driver.session() as session:
        result = session.run("""
            MATCH (e:Event)
            WHERE e.device IS NOT NULL
            WITH e.device AS device, e.event_type AS event_type, count(e) AS cnt
            ORDER BY device, cnt DESC
            RETURN device, event_type, cnt
        """)

        from collections import defaultdict
        device_data = defaultdict(dict)
        for r in result:
            device_data[r["device"]][r["event_type"]] = r["cnt"]

        devices = sorted(device_data.keys())
        all_types = set()
        for d in devices:
            all_types.update(device_data[d].keys())

        # 表头
        type_list = sorted(all_types)
        header = f"  {'设备':<10s}"
        for t in type_list:
            header += f" {t:>10s}"
        header += f" {'总计':>8s}"
        print(header)
        print(f"  {'-'*10}{'-'*(11*len(type_list)+10)}")

        for dev in devices:
            total = sum(device_data[dev].values())
            row = f"  {dev:<10s}"
            for t in type_list:
                row += f" {device_data[dev].get(t, 0):>10d}"
            row += f" {total:>8d}"
            print(row)


def run_all_queries(driver):
    """运行所有演示查询。"""
    query_user_path(driver, "U0001")
    query_product_cooccurrence(driver)
    query_conversion_funnel(driver)
    query_collaborative_filtering(driver, "U0001")
    query_high_value_users(driver)
    query_device_preferences(driver)


def main():
    parser = argparse.ArgumentParser(
        description="Neo4j Cypher 查询演示"
    )
    parser.add_argument("--query", default="all",
                        choices=["all", "path", "cooccur", "funnel",
                                 "recommend", "high-value", "device"],
                        help="要运行的查询类型")
    parser.add_argument("--user-id", default="U0001", help="目标用户 ID")
    parser.add_argument("--uri", default=NEO4J_URI, help="Neo4j Bolt URI")
    parser.add_argument("--user", default=NEO4J_USER, help="Neo4j 用户")
    parser.add_argument("--password", default=NEO4J_PASSWORD, help="Neo4j 密码")
    args = parser.parse_args()

    print("=" * 70)
    print("  [Neo4j]  Neo4j 图查询演示 — 用户行为图谱分析")
    print("=" * 70)

    try:
        driver = get_driver()
    except Exception as e:
        print(f"[ERROR] 无法连接 Neo4j: {e}")
        print(f"[TIP] 请先启动 Neo4j: docker compose -f neo4j/docker-compose.neo4j.yml up -d")
        sys.exit(1)

    try:
        if args.query == "all":
            run_all_queries(driver)
        elif args.query == "path":
            query_user_path(driver, args.user_id)
        elif args.query == "cooccur":
            query_product_cooccurrence(driver)
        elif args.query == "funnel":
            query_conversion_funnel(driver)
        elif args.query == "recommend":
            query_collaborative_filtering(driver, args.user_id)
        elif args.query == "high-value":
            query_high_value_users(driver)
        elif args.query == "device":
            query_device_preferences(driver)

        print(f"\n[OK] 查询演示完成!")
        print(f"[TIP] 访问 Neo4j Browser: http://localhost:7474 (neo4j/changeme123)")

    finally:
        driver.close()


if __name__ == "__main__":
    main()
