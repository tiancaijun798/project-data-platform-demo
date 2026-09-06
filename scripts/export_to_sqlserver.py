#!/usr/bin/env python3
"""
导出 PostgreSQL 业务表 → CSV (UTF-8 BOM)，供 SQL Server / SSMS 导入。

导出对象:
    - raw.user_events              (原始事件，默认采样 20000 行，--full 导出全量)
    - public_clean.dim_users       (用户维度表)
    - public_clean.dim_products    (商品维度表)
    - public_clean.fct_user_events_daily (每日事实表)

说明:
    - 所有时间戳列统一格式化为 'YYYY-MM-DD HH:MM:SS'，SQL Server 可直接解析
    - 保留字列名 timestamp 改名为 event_timestamp
    - CSV 使用 UTF-8 BOM 编码，Excel / SSMS 打开中文不乱码

用法:
    python scripts/export_to_sqlserver.py                 # 采样导出
    python scripts/export_to_sqlserver.py --full          # 全量导出 user_events
    python scripts/export_to_sqlserver.py --sample 50000  # 自定义采样行数
"""

import argparse
import os
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine

DB_URL = "postgresql://admin:changeme@localhost:5432/data_platform"

# 表名 → (schema 表, 导出 CSV 文件名)
TABLES = {
    "user_events": ("raw.user_events", "user_events.csv"),
    "dim_users": ("public_clean.dim_users", "dim_users.csv"),
    "dim_products": ("public_clean.dim_products", "dim_products.csv"),
    "fct_user_events_daily": ("public_clean.fct_user_events_daily", "fct_user_events_daily.csv"),
}

# 日期列（只保留 YYYY-MM-DD）与时间戳列（保留到秒）
DATE_COLS = {"processing_date", "first_seen_at", "last_seen_at", "event_date"}
TIMESTAMP_COLS = {"event_timestamp", "event_ts", "processed_at"}


def format_datetimes(df: pd.DataFrame) -> pd.DataFrame:
    """把 datetime/date 列统一转成字符串，供 SQL Server 直接解析。"""
    for c in df.columns:
        if c in DATE_COLS:
            fmt = "%Y-%m-%d"
        elif c in TIMESTAMP_COLS:
            fmt = "%Y-%m-%d %H:%M:%S"
        else:
            continue
        s = df[c]
        if pd.api.types.is_datetime64_any_dtype(s):
            df[c] = s.dt.strftime(fmt)
        else:
            def _fmt(x):
                if pd.isna(x):
                    return ""
                if hasattr(x, "strftime"):
                    return x.strftime(fmt)
                return str(x)
            df[c] = s.apply(_fmt)
    return df


def export_table(engine, schema_table: str, out_path: Path,
                 sample: int | None = None, full: bool = False) -> pd.DataFrame:
    """导出单张表到 CSV，返回 DataFrame（供打印预览）。"""
    if full and sample:
        sql = f"SELECT * FROM {schema_table} ORDER BY random() LIMIT {sample}"
    elif full:
        sql = f"SELECT * FROM {schema_table}"
    elif sample:
        sql = f"SELECT * FROM {schema_table} ORDER BY random() LIMIT {sample}"
    else:
        sql = f"SELECT * FROM {schema_table}"

    df = pd.read_sql(sql, engine)

    # 保留字列名 timestamp → event_timestamp
    if "timestamp" in df.columns:
        df = df.rename(columns={"timestamp": "event_timestamp"})

    df = format_datetimes(df)
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    return df


def main():
    parser = argparse.ArgumentParser(description="导出 PG 表为 CSV 供 SQL Server 导入")
    parser.add_argument("--full", action="store_true", help="全量导出 user_events（默认采样）")
    parser.add_argument("--sample", type=int, default=20000, help="user_events 采样行数（默认 20000）")
    parser.add_argument("--out", type=Path, default=Path("sqlserver_export"), help="输出目录")
    args = parser.parse_args()

    engine = create_engine(DB_URL)
    args.out.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("  PostgreSQL → CSV 导出（供 SQL Server 导入）")
    print("=" * 60)

    for name, (schema_table, csv_name) in TABLES.items():
        out_path = args.out / csv_name
        # user_events 支持采样；其余表全量
        if name == "user_events":
            df = export_table(engine, schema_table, out_path,
                              sample=args.sample, full=args.full)
            label = f"{len(df):,} 行" + ("" if args.full else f"（采样，全量可加 --full）")
        else:
            df = export_table(engine, schema_table, out_path, full=True)
            label = f"{len(df):,} 行"

        size_kb = out_path.stat().st_size / 1024
        print(f"  [OK] {csv_name:<28s} {label:<18s} {size_kb:>8.1f} KB")

    print("\n  导出完成 →", args.out.resolve())
    print("  下一步: 用 SSMS 导入（见 sqlserver_export/导入说明.md）")


if __name__ == "__main__":
    main()
