"""
Feast 用户特征定义
数据源: public_clean.dim_users (dbt 清洗后的用户维度表)

特征列表:
    - user_segment: 用户分层 (new/active/lapsed/vip)
    - total_events: 总事件数
    - first_seen_at: 首次活跃时间
    - last_seen_at: 最近活跃时间
    - days_since_first_seen: 距首次活跃天数 (on-demand)
    - days_since_last_seen: 距最近活跃天数 (on-demand)
"""
from datetime import datetime

import pandas as pd
from feast import Entity, FeatureService, FeatureView, Field, OnDemandFeatureView
from feast.infra.offline_stores.postgres_source import PostgreSQLSource
from feast.types import Float32, Int64, String, UnixTimestamp


# ---- Entity ----
user = Entity(
    name="user_id",
    join_keys=["user_id"],
    description="用户唯一标识",
)


# ---- 数据源 (PostgreSQL dbt clean layer) ----
user_source = PostgreSQLSource(
    name="user_source",
    query="""
        SELECT
            user_id,
            user_segment,
            total_events,
            EXTRACT(EPOCH FROM first_seen_at)::BIGINT AS first_seen_at_ts,
            EXTRACT(EPOCH FROM last_seen_at)::BIGINT AS last_seen_at_ts
        FROM public_clean.dim_users
    """,
    timestamp_field="last_seen_at_ts",
)


# ---- Feature View ----
user_features = FeatureView(
    name="user_features",
    entities=[user],
    ttl=None,  # 维度表，无过期时间
    schema=[
        Field(name="user_segment", dtype=String, description="用户分层标签"),
        Field(name="total_events", dtype=Int64, description="累计事件数"),
        Field(name="first_seen_at_ts", dtype=UnixTimestamp, description="首次活跃时间"),
        Field(name="last_seen_at_ts", dtype=UnixTimestamp, description="最近活跃时间"),
    ],
    source=user_source,
    tags={"team": "data-platform", "layer": "clean"},
    online=True,
)


# ---- On-Demand Feature View (派生特征) ----
@OnDemandFeatureView(
    sources=[user_features],
    schema=[
        Field(name="days_since_first_seen", dtype=Int64),
        Field(name="days_since_last_seen", dtype=Int64),
        Field(name="activity_score", dtype=Float32),
    ],
)
def user_derived_features(inputs: pd.DataFrame) -> pd.DataFrame:
    """计算用户派生特征：活跃天数、活跃度评分。"""
    df = pd.DataFrame()
    now = datetime.now().timestamp()

    df["days_since_first_seen"] = (
        (now - inputs["first_seen_at_ts"]) / 86400
    ).astype("int64")
    df["days_since_last_seen"] = (
        (now - inputs["last_seen_at_ts"]) / 86400
    ).astype("int64")

    # 活跃度评分: 事件越多、最近越活跃，分数越高
    df["activity_score"] = (
        inputs["total_events"].astype("float32")
        / (df["days_since_last_seen"] + 1).astype("float32")
    ).clip(0, 100)

    return df
