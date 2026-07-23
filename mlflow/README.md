# 🤖 MLflow 实验跟踪与模型管理

> 模型训练实验跟踪、参数记录、模型注册表，与 Feast 特征平台对接。

---

## 架构

```
Feast 特征 (PostgreSQL)
     │
     ├──→ train_demo.py (特征加载 + 训练)
     │         │
     │         ├──→ MLflow Tracking (实验记录)
     │         └──→ MLflow Model Registry (模型注册)
     │
     └──→ FastAPI 推理服务 (模型部署)
```

## 快速开始

### 1. 启动 MLflow Tracking Server
```bash
cd mlflow
docker compose -f docker-compose.mlflow.yml up -d
```

访问 http://localhost:5000 查看 MLflow UI。

### 2. 运行训练演示
```bash
# 安装依赖
pip install -r requirements.txt

# 本地运行（不连接 MLflow Server）
python train_demo.py --dry-run

# 连接 MLflow Server 运行
python train_demo.py --mlflow-uri http://localhost:5000
```

### 3. 查看实验结果
1. 打开 http://localhost:5000
2. 选择 Experiment: `user_segment_prediction`
3. 对比不同 run 的指标
4. 查看特征重要性

## 实验内容

| 实验 | 模型 | 目标 |
|------|------|------|
| `user_segment_prediction` | RandomForest | 预测用户分层 (4 类) |

## 特征列表

| 特征 | 来源 | 说明 |
|------|------|------|
| `total_events` | Feast `user_features` | 累计事件数 |
| `days_since_first_seen` | Feast `user_derived_features` | 距首次活跃天数 |
| `days_since_last_seen` | Feast `user_derived_features` | 距最近活跃天数 |
| `events_per_day` | 衍生特征 | 日均事件数 |
| `recency_score` | 衍生特征 | 最近活跃度 |
| `activity_score` | Feast `user_derived_features` | 综合活跃度评分 |

## 面试展示要点

1. **"我在 MLflow 上记录实验，对比不同模型参数和特征组合的效果"**
2. **"模型训练数据来自 Feast 特征平台，保证离线/在线特征一致性"**
3. **"MLflow Model Registry 支持模型版本管理和一键部署"**
4. **"特征重要性分析帮助理解用户分层的关键驱动因素"**
