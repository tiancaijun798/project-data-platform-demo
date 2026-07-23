# 🏗️ Feast 特征平台集成

> 离线/在线特征存储，与 dbt 清洗数据层对接，为模型训练和推理提供一致性特征。

---

## 架构

```
PostgreSQL (dbt clean tables)
     │
     ├──→ Feast Offline Store (训练数据集生成)
     │
     └──→ Feast Online Store (低延迟在线服务)
              │
              └──→ MLflow 模型训练 / FastAPI 推理
```

## 特征列表

### 用户特征 (`user_features`)
| 特征 | 类型 | 说明 |
|------|------|------|
| `user_segment` | String | 用户分层 (new/active/lapsed/vip) |
| `total_events` | Int64 | 累计事件数 |
| `days_since_first_seen` | Int64 | 距首次活跃天数 |
| `days_since_last_seen` | Int64 | 距最近活跃天数 |
| `activity_score` | Float32 | 活跃度评分 (0-100) |

### 商品特征 (`product_features`)
| 特征 | 类型 | 说明 |
|------|------|------|
| `total_views` | Int64 | 总浏览次数 |
| `total_purchases` | Int64 | 总购买次数 |
| `conversion_rate_pct` | Float32 | 转化率(%) |
| `popularity_tier` | String | 热度分层 (hot/warm/cool/cold) |
| `purchase_view_ratio` | Float32 | 购买/浏览比 |

---

## 快速开始

### 1. 安装依赖
```bash
cd feast
pip install -r requirements.txt
```

### 2. 运行演示（无需完整 Feast 安装）
```bash
# 基本演示: 从 PostgreSQL 读取特征并模拟在线服务
python run_feast_demo.py

# 查询特定用户
python run_feast_demo.py --user-ids U0001,U0002,U0003
```

### 3. 完整 Feast 工作流（需要完整 Feast CLI）
```bash
cd feature_repo

# 初始化
feast init data_platform_demo

# 应用特征定义
feast apply

# 生成训练数据集
feast materialize 2024-01-01T00:00:00 2026-12-31T23:59:59

# 在线特征查询
feast serve
```

---

## 面试展示要点

1. **"我实现了 Feast 离线/在线特征一致性验证，确保训练-服务特征无偏移"**
2. **"特征存储在 PostgreSQL，在线服务延迟 <5ms (SQLite)"**
3. **"与 dbt 数据建模层无缝对接，dim_users/dim_products 直接作为特征源"**
4. **"OnDemandFeatureView 支持动态派生特征，无需预计算"**
