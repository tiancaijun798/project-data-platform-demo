"""
Feast 商品特征定义
数据源: public_clean.dim_products (dbt 清洗后的商品维度表)

特征列表:
    - total_views: 总浏览次数
    - total_purchases: 总购买次数
    - conversion_rate_pct: 转化率(%)
"""
import pandas as pd
from feast import Entity, FeatureView, Field, OnDemandFeatureView
from feast.infra.offline_stores.postgres_source import PostgreSQLSource
from feast.types import Float32, Int64, String


# ---- Entity ----
product = Entity(
    name="product_id",
    join_keys=["product_id"],
    description="商品唯一标识",
)


# ---- 数据源 ----
product_source = PostgreSQLSource(
    name="product_source",
    query="""
        SELECT
            product_id,
            total_views,
            total_purchases,
            conversion_rate_pct
        FROM public_clean.dim_products
    """,
    timestamp_field="product_id",  # 维度表用主键作为时间字段占位
)


# ---- Feature View ----
product_features = FeatureView(
    name="product_features",
    entities=[product],
    ttl=None,
    schema=[
        Field(name="total_views", dtype=Int64, description="总浏览次数"),
        Field(name="total_purchases", dtype=Int64, description="总购买次数"),
        Field(name="conversion_rate_pct", dtype=Float32, description="浏览→购买转化率(%)"),
    ],
    source=product_source,
    tags={"team": "data-platform", "layer": "clean"},
    online=True,
)


# ---- On-Demand Feature View (派生特征) ----
@OnDemandFeatureView(
    sources=[product_features],
    schema=[
        Field(name="popularity_tier", dtype=String),
        Field(name="purchase_view_ratio", dtype=Float32),
    ],
)
def product_derived_features(inputs: pd.DataFrame) -> pd.DataFrame:
    """计算商品派生特征：热度分层、购买观看比。"""
    df = pd.DataFrame()

    # 热度分层
    def _tier(views):
        if views >= 100:
            return "hot"
        elif views >= 50:
            return "warm"
        elif views >= 10:
            return "cool"
        return "cold"

    df["popularity_tier"] = inputs["total_views"].apply(_tier)

    # 购买/观看比 (避免除零)
    df["purchase_view_ratio"] = (
        inputs["total_purchases"].astype("float32")
        / (inputs["total_views"].astype("float32") + 1)
    ).round(4)

    return df
