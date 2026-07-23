"""
Feast Feature Services — 组合特征供模型训练/在线推理使用。
"""
from feast import FeatureService

from features.user_features import user, user_features, user_derived_features
from features.product_features import product, product_features, product_derived_features


# ---- 用户画像服务 ----
user_profile_service = FeatureService(
    name="user_profile_service",
    features=[
        user_features[["user_segment", "total_events"]],
        user_derived_features[["days_since_last_seen", "activity_score"]],
    ],
    tags={"use_case": "user_segmentation", "team": "data-platform"},
    description="用户画像特征服务：分层、活跃度评分",
)


# ---- 商品推荐服务 ----
product_recommendation_service = FeatureService(
    name="product_recommendation_service",
    features=[
        product_features[["total_views", "total_purchases", "conversion_rate_pct"]],
        product_derived_features[["popularity_tier", "purchase_view_ratio"]],
    ],
    tags={"use_case": "product_ranking", "team": "data-platform"},
    description="商品推荐特征服务：热度、转化率",
)
