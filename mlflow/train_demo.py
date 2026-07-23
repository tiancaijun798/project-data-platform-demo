#!/usr/bin/env python3
"""
MLflow 训练演示脚本
从 PostgreSQL 获取 Feast 特征，训练用户分层预测模型，记录到 MLflow。

工作流:
    1. 连接 PostgreSQL 获取用户特征 (dim_users)
    2. 数据预处理 & 特征工程
    3. 训练 RandomForest 分类器预测 user_segment
    4. 记录参数、指标、模型、特征重要性到 MLflow
    5. 注册模型到 MLflow Model Registry

用法:
    python train_demo.py
    python train_demo.py --mlflow-uri http://localhost:5000
    python train_demo.py --dry-run  # 不连接 MLflow，仅本地运行
"""
import argparse
import os
import sys
import time
import warnings
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sqlalchemy import create_engine, text

warnings.filterwarnings("ignore")


# ---- 配置 ----
DB_HOST = os.getenv("DATA_PLATFORM_DB_HOST", "localhost")
DB_PORT = os.getenv("DATA_PLATFORM_DB_PORT", "5432")
DB_USER = os.getenv("DATA_PLATFORM_DB_USER", "admin")
DB_PASSWORD = os.getenv("DATA_PLATFORM_DB_PASSWORD", "changeme")
DB_NAME = os.getenv("DATA_PLATFORM_DB_NAME", "data_platform")
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")

# 实验名称
EXPERIMENT_NAME = "user_segment_prediction"


def load_data() -> pd.DataFrame:
    """从 PostgreSQL 加载用户特征数据。"""
    print("  📖 从 PostgreSQL 加载用户特征...")
    engine = create_engine(DATABASE_URL)

    query = """
        SELECT
            user_id,
            user_segment,
            total_events,
            EXTRACT(EPOCH FROM NOW() - first_seen_at) / 86400 AS days_since_first_seen,
            EXTRACT(EPOCH FROM NOW() - last_seen_at) / 86400 AS days_since_last_seen
        FROM public_clean.dim_users
        WHERE user_segment IS NOT NULL
          AND total_events > 0
    """
    df = pd.read_sql(text(query), engine)
    engine.dispose()

    print(f"     ✅ 加载 {len(df)} 条用户记录")
    return df


def preprocess(df: pd.DataFrame) -> tuple:
    """数据预处理：编码、特征工程、划分数据集。"""
    print("  🧹 数据预处理...")

    # 衍生特征
    df["events_per_day"] = df["total_events"] / (df["days_since_first_seen"] + 1)
    df["recency_score"] = 1.0 / (df["days_since_last_seen"] + 1)
    df["activity_score"] = (
        df["total_events"] / (df["days_since_last_seen"] + 1)
    ).clip(0, 100)

    # 编码目标变量
    le = LabelEncoder()
    df["segment_encoded"] = le.fit_transform(df["user_segment"])

    # 特征列
    feature_cols = [
        "total_events",
        "days_since_first_seen",
        "days_since_last_seen",
        "events_per_day",
        "recency_score",
        "activity_score",
    ]

    X = df[feature_cols].values
    y = df["segment_encoded"].values

    # 处理缺失值
    X = np.nan_to_num(X, nan=0.0, posinf=999, neginf=-999)

    # 标准化
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # 划分
    X_train, X_test, y_train, y_test = train_test_split(
        X_scaled, y, test_size=0.2, random_state=42, stratify=y
    )

    print(f"     训练集: {len(X_train)} | 测试集: {len(X_test)}")
    print(f"     类别: {dict(zip(le.classes_, range(len(le.classes_))))}")

    return X_train, X_test, y_train, y_test, le, feature_cols


def train_and_evaluate(X_train, X_test, y_train, y_test, le, feature_cols,
                       dry_run: bool = False, mlflow_uri: str = None) -> dict:
    """训练模型并评估。"""
    print("  🤖 训练模型...")

    # 模型参数
    params = {
        "n_estimators": 100,
        "max_depth": 10,
        "min_samples_split": 5,
        "min_samples_leaf": 2,
        "random_state": 42,
    }

    model = RandomForestClassifier(**params)
    t0 = time.time()
    model.fit(X_train, y_train)
    train_time = time.time() - t0

    # 预测
    t0 = time.time()
    y_pred = model.predict(X_test)
    infer_time = (time.time() - t0) / len(X_test) * 1000  # ms per sample

    # 指标
    accuracy = accuracy_score(y_test, y_pred)
    precision = precision_score(y_test, y_pred, average="weighted", zero_division=0)
    recall = recall_score(y_test, y_pred, average="weighted", zero_division=0)
    f1 = f1_score(y_test, y_pred, average="weighted", zero_division=0)

    # 交叉验证
    cv_scores = cross_val_score(model, X_train, y_train, cv=5, scoring="f1_weighted")
    cv_mean = cv_scores.mean()
    cv_std = cv_scores.std()

    # 特征重要性
    importance = dict(zip(feature_cols, model.feature_importances_))
    importance_sorted = sorted(importance.items(), key=lambda x: x[1], reverse=True)

    # 打印结果
    print(f"\n  {'='*50}")
    print(f"  📊 模型评估结果")
    print(f"  {'='*50}")
    print(f"  Accuracy:     {accuracy:.4f}")
    print(f"  Precision:    {precision:.4f} (weighted)")
    print(f"  Recall:       {recall:.4f} (weighted)")
    print(f"  F1 Score:     {f1:.4f} (weighted)")
    print(f"  CV F1:        {cv_mean:.4f} (±{cv_std:.4f})")
    print(f"  训练耗时:     {train_time:.2f}s")
    print(f"  推理耗时:     {infer_time:.3f} ms/样本")
    print(f"\n  📈 特征重要性:")
    for feat, imp in importance_sorted:
        bar = "█" * int(imp * 50)
        print(f"     {feat:<25s} {imp:.4f} {bar}")

    # 分类报告
    print(f"\n  📋 分类报告:")
    print(classification_report(y_test, y_pred, target_names=le.classes_, zero_division=0))

    metrics = {
        "accuracy": accuracy,
        "precision_weighted": precision,
        "recall_weighted": recall,
        "f1_weighted": f1,
        "cv_f1_mean": cv_mean,
        "cv_f1_std": cv_std,
        "train_time_s": train_time,
        "infer_time_ms_per_sample": infer_time,
        "feature_importance": importance,
    }

    # MLflow 记录
    if not dry_run:
        log_to_mlflow(params, metrics, model, le, feature_cols, mlflow_uri)

    return metrics


def log_to_mlflow(params: dict, metrics: dict, model, le, feature_cols,
                  mlflow_uri: str = None):
    """记录实验到 MLflow。"""
    try:
        import mlflow
        import mlflow.sklearn

        uri = mlflow_uri or MLFLOW_TRACKING_URI
        mlflow.set_tracking_uri(uri)
        mlflow.set_experiment(EXPERIMENT_NAME)

        with mlflow.start_run(run_name=f"train_{datetime.now():%Y%m%d_%H%M%S}"):
            # 参数
            mlflow.log_params(params)

            # 指标
            mlflow.log_metrics({
                "accuracy": metrics["accuracy"],
                "precision_weighted": metrics["precision_weighted"],
                "recall_weighted": metrics["recall_weighted"],
                "f1_weighted": metrics["f1_weighted"],
                "cv_f1_mean": metrics["cv_f1_mean"],
                "cv_f1_std": metrics["cv_f1_std"],
                "train_time_s": metrics["train_time_s"],
                "infer_time_ms": metrics["infer_time_ms_per_sample"],
            })

            # 特征重要性
            for feat, imp in metrics["feature_importance"].items():
                mlflow.log_metric(f"importance_{feat}", imp)

            # 模型
            mlflow.sklearn.log_model(
                model,
                "user_segment_classifier",
                registered_model_name="user_segment_predictor",
            )

            print(f"\n  ✅ 已记录到 MLflow: {mlflow.get_tracking_uri()}")
            print(f"     Experiment: {EXPERIMENT_NAME}")

    except Exception as e:
        print(f"\n  ⚠️  MLflow 记录失败: {e}")
        print(f"     MLflow URI: {mlflow_uri or MLFLOW_TRACKING_URI}")
        print(f"     (使用 --dry-run 跳过 MLflow)")


def generate_synthetic_data() -> pd.DataFrame:
    """当数据库不可用时，生成模拟用户特征数据用于演示。"""
    print("  ⚠️  数据库不可用，使用模拟数据演示...")
    np.random.seed(42)
    n = 500

    segments = ["new", "active", "lapsed", "vip"]
    weights = [0.3, 0.4, 0.2, 0.1]

    data = {
        "user_id": [f"U{i:04d}" for i in range(n)],
        "user_segment": np.random.choice(segments, n, p=weights),
        "total_events": np.random.randint(1, 200, n),
        "days_since_first_seen": np.random.randint(1, 365, n),
        "days_since_last_seen": np.random.randint(0, 60, n),
    }
    return pd.DataFrame(data)


def main():
    parser = argparse.ArgumentParser(description="MLflow 训练演示")
    parser.add_argument(
        "--mlflow-uri",
        default=MLFLOW_TRACKING_URI,
        help="MLflow tracking server URI",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="不连接 MLflow，仅本地运行",
    )
    args = parser.parse_args()

    mlflow_uri = args.mlflow_uri

    print("=" * 60)
    print("  🤖 MLflow 训练演示 — 用户分层预测")
    print("=" * 60)
    print(f"  MLflow URI: {mlflow_uri}")
    print(f"  数据库: {DB_HOST}:{DB_PORT}/{DB_NAME}")
    print(f"  时间: {datetime.now().isoformat()}")

    # Step 1: 加载数据
    try:
        df = load_data()
        if len(df) < 50:
            print(f"  ⚠️  数据量不足 ({len(df)} 条)，使用模拟数据")
            df = generate_synthetic_data()
    except Exception as e:
        print(f"  ⚠️  数据加载失败: {e}")
        df = generate_synthetic_data()

    print(f"  📊 数据分布: {df['user_segment'].value_counts().to_dict()}")

    # Step 2: 预处理
    X_train, X_test, y_train, y_test, le, feature_cols = preprocess(df)

    # Step 3: 训练 & 评估
    metrics = train_and_evaluate(
        X_train, X_test, y_train, y_test, le, feature_cols,
        dry_run=args.dry_run, mlflow_uri=mlflow_uri,
    )

    print(f"\n✅ MLflow 训练演示完成!")
    print(f"💡 面试展示要点:")
    print(f"   1. 使用 Feast 定义的特征从 PostgreSQL 获取训练数据")
    print(f"   2. RandomForest 分类器预测 user_segment (4 类)")
    print(f"   3. MLflow 记录实验参数、指标、模型和特征重要性")
    print(f"   4. 模型注册到 MLflow Model Registry，支持版本管理")
    if args.dry_run:
        print(f"   5. 启动 MLflow UI: mlflow ui --host 0.0.0.0")


if __name__ == "__main__":
    main()
