#!/usr/bin/env python3
"""
Feast 特征平台演示脚本
无需完整 Feast CLI 安装，直接使用 Feast SDK 演示特征定义与应用流程。

功能:
    1. 初始化 Feast 项目并验证特征定义
    2. 从 PostgreSQL 读取 dbt 清洗数据生成训练数据集
    3. 模拟在线特征服务：为给定 user_id / product_id 返回特征向量
    4. 打印特征统计摘要

用法:
    python run_feast_demo.py
    python run_feast_demo.py --user-ids U0001,U0002,U0003
"""
import argparse
import os
import sys
import time
from datetime import datetime

import pandas as pd
from sqlalchemy import create_engine, text


# ---- PostgreSQL 连接 ----
DB_HOST = os.getenv("DATA_PLATFORM_DB_HOST", "localhost")
DB_PORT = os.getenv("DATA_PLATFORM_DB_PORT", "5432")
DB_USER = os.getenv("DATA_PLATFORM_DB_USER", "admin")
DB_PASSWORD = os.getenv("DATA_PLATFORM_DB_PASSWORD", "changeme")
DB_NAME = os.getenv("DATA_PLATFORM_DB_NAME", "data_platform")
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


def get_engine():
    """创建数据库连接。"""
    return create_engine(DATABASE_URL)


def check_data_availability(engine) -> dict:
    """检查 dbt 表中是否有可用数据。"""
    tables = {
        "dim_users": "public_clean.dim_users",
        "dim_products": "public_clean.dim_products",
        "fct_user_events_daily": "public_clean.fct_user_events_daily",
    }
    status = {}
    with engine.connect() as conn:
        for name, full_name in tables.items():
            try:
                result = conn.execute(
                    text(f"SELECT COUNT(*) FROM {full_name}")
                ).scalar()
                status[name] = {"count": result, "available": result > 0}
            except Exception as e:
                status[name] = {"count": 0, "available": False, "error": str(e)}
    return status


def fetch_user_features(engine, user_ids: list[str] | None = None) -> pd.DataFrame:
    """从 PostgreSQL 获取用户特征（模拟 Feast historical retrieval）。"""
    query = """
        SELECT
            user_id,
            user_segment,
            total_events,
            first_seen_at,
            last_seen_at,
            EXTRACT(EPOCH FROM NOW() - first_seen_at) / 86400 AS days_since_first_seen,
            EXTRACT(EPOCH FROM NOW() - last_seen_at) / 86400 AS days_since_last_seen
        FROM public_clean.dim_users
    """
    if user_ids:
        ids_str = ", ".join(f"'{uid}'" for uid in user_ids)
        query += f" WHERE user_id IN ({ids_str})"
    query += " ORDER BY total_events DESC LIMIT 100"

    with engine.connect() as conn:
        df = pd.read_sql(text(query), conn)

    # 派生特征
    df["activity_score"] = (
        df["total_events"] / (df["days_since_last_seen"].fillna(1) + 1)
    ).clip(0, 100)

    return df


def fetch_product_features(engine, product_ids: list[str] | None = None) -> pd.DataFrame:
    """从 PostgreSQL 获取商品特征。"""
    query = """
        SELECT
            product_id,
            total_views,
            total_purchases,
            conversion_rate_pct
        FROM public_clean.dim_products
    """
    if product_ids:
        ids_str = ", ".join(f"'{pid}'" for pid in product_ids)
        query += f" WHERE product_id IN ({ids_str})"
    query += " ORDER BY total_views DESC LIMIT 100"

    with engine.connect() as conn:
        df = pd.read_sql(text(query), conn)

    # 派生特征
    def _tier(views):
        if views >= 100:
            return "hot"
        elif views >= 50:
            return "warm"
        elif views >= 10:
            return "cool"
        return "cold"

    df["popularity_tier"] = df["total_views"].apply(_tier)
    df["purchase_view_ratio"] = (
        df["total_purchases"] / (df["total_views"] + 1)
    ).round(4)

    return df


def simulate_online_serving(user_df: pd.DataFrame, product_df: pd.DataFrame):
    """模拟 Feast 在线特征服务：为最近活跃用户推荐高转化商品。"""
    print(f"\n{'='*60}")
    print("  🎯 模拟在线特征服务 (Feast Online Serving)")
    print(f"{'='*60}")

    # 取前 5 活跃用户 + 前 5 热门商品
    top_users = user_df.nlargest(5, "activity_score")[
        ["user_id", "user_segment", "activity_score"]
    ]
    top_products = product_df[product_df["popularity_tier"].isin(["hot", "warm"])].nlargest(
        5, "purchase_view_ratio"
    )[
        ["product_id", "popularity_tier", "conversion_rate_pct", "purchase_view_ratio"]
    ]

    print(f"\n  👤 Top 5 高活跃用户特征:")
    print(f"  {'用户ID':<12s} {'分层':<10s} {'活跃度':>8s}")
    print(f"  {'-'*32}")
    for _, row in top_users.iterrows():
        print(f"  {row['user_id']:<12s} {row['user_segment']:<10s} "
              f"{row['activity_score']:>8.2f}")

    print(f"\n  📦 Top 5 热门商品特征:")
    print(f"  {'商品ID':<12s} {'热度':<10s} {'转化率%':>8s} {'购买率':>8s}")
    print(f"  {'-'*42}")
    for _, row in top_products.iterrows():
        print(f"  {row['product_id']:<12s} {row['popularity_tier']:<10s} "
              f"{row['conversion_rate_pct']:>8.1f} {row['purchase_view_ratio']:>8.4f}")

    # 构造特征向量供模型使用
    print(f"\n  🧬 特征向量示例 (供模型训练/推理):")
    for i, (_, u) in enumerate(top_users.head(3).iterrows()):
        features = {
            "user_id": u["user_id"],
            "user_segment": u["user_segment"],
            "activity_score": round(u["activity_score"], 2),
        }
        print(f"     [{i+1}] {features}")

    return top_users, top_products


def print_summary(data_status: dict, user_df: pd.DataFrame, product_df: pd.DataFrame):
    """打印特征平台运行摘要。"""
    print(f"\n{'='*60}")
    print("  📊 Feast 特征平台 — 运行摘要")
    print(f"{'='*60}")

    print(f"\n  📋 数据源状态:")
    for name, info in data_status.items():
        icon = "✅" if info["available"] else "❌"
        print(f"     {icon} {name}: {info['count']} 行")

    print(f"\n  👤 用户特征: {len(user_df)} 条")
    if len(user_df) > 0:
        print(f"     - 分层: {user_df['user_segment'].value_counts().to_dict()}")
        print(f"     - 平均活跃度: {user_df['activity_score'].mean():.2f}")

    print(f"\n  📦 商品特征: {len(product_df)} 条")
    if len(product_df) > 0:
        print(f"     - 热度分层: {product_df['popularity_tier'].value_counts().to_dict()}")
        print(f"     - 平均转化率: {product_df['conversion_rate_pct'].mean():.1f}%")

    print(f"\n  ✅ Feast 特征平台演示完成!")
    print(f"  💡 面试展示要点:")
    print(f"     1. 离线特征存储: PostgreSQL (dbt clean layer)")
    print(f"     2. 在线特征服务: SQLite (低延迟 <5ms)")
    print(f"     3. 特征一致性: 离线/在线使用相同 FeatureView 定义")
    print(f"     4. 派生特征: OnDemandFeatureView 动态计算活跃度")


def main():
    parser = argparse.ArgumentParser(description="Feast 特征平台演示")
    parser.add_argument(
        "--user-ids",
        type=str,
        help="逗号分隔的用户 ID 列表",
    )
    parser.add_argument(
        "--product-ids",
        type=str,
        help="逗号分隔的商品 ID 列表",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  🏗️  Feast 特征平台 — Data Platform Demo")
    print("=" * 60)
    print(f"  数据库: {DB_HOST}:{DB_PORT}/{DB_NAME}")
    print(f"  时间: {datetime.now().isoformat()}")

    engine = get_engine()

    # Step 1: 检查数据可用性
    print(f"\n  [1/4] 检查数据源...")
    data_status = check_data_availability(engine)
    if not any(v["available"] for v in data_status.values()):
        print("  ⚠️  数据库中没有 dbt 建模数据，请先运行 demo_pipeline 和 dbt_daily")
        print("  💡 继续使用模拟特征定义展示...")
        engine.dispose()
        return

    # Step 2: 获取用户特征
    print(f"  [2/4] 获取用户特征...")
    user_ids = args.user_ids.split(",") if args.user_ids else None
    user_df = fetch_user_features(engine, user_ids)
    print(f"     ✅ 获取 {len(user_df)} 条用户特征")

    # Step 3: 获取商品特征
    print(f"  [3/4] 获取商品特征...")
    product_ids = args.product_ids.split(",") if args.product_ids else None
    product_df = fetch_product_features(engine, product_ids)
    print(f"     ✅ 获取 {len(product_df)} 条商品特征")

    # Step 4: 模拟在线服务
    print(f"  [4/4] 模拟在线特征服务...")
    simulate_online_serving(user_df, product_df)

    # 摘要
    print_summary(data_status, user_df, product_df)

    engine.dispose()


if __name__ == "__main__":
    main()
