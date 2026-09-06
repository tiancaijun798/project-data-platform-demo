#!/usr/bin/env python3
"""
Generate massive realistic e-commerce event data.
Target: 1,000,000 events across 3 months, 5,000 users, 500 products, 12 categories.
Output: data/massive_events.parquet (partitioned) + PostgreSQL insert.

Usage:
    python scripts/generate_massive_data.py
    python scripts/generate_massive_data.py --events 500000 --users 2000
"""

import argparse, json, os, sys, time, uuid
from datetime import datetime, timedelta
from pathlib import Path
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

# ---- Config ----
N_EVENTS = 1_000_000
N_USERS = 5_000
N_PRODUCTS = 500
START_DATE = datetime(2026, 5, 1)
END_DATE = datetime(2026, 8, 1)

CATEGORIES = ["Electronics", "Clothing", "Food", "Home", "Sports", "Books", "Beauty",
              "Toys", "Automotive", "Health", "Office", "Garden"]

EVENT_TYPES = ["view", "click", "search", "add_to_cart", "purchase", "remove_cart"]
EVENT_WEIGHTS = [0.50, 0.15, 0.10, 0.10, 0.10, 0.05]

DEVICES = ["mobile", "desktop", "tablet"]
DEVICE_WEIGHTS = [0.50, 0.35, 0.15]

BROWSERS = ["Chrome", "Safari", "Firefox", "Edge", "Samsung Internet"]
BROWSER_WEIGHTS = [0.45, 0.25, 0.15, 0.10, 0.05]

REFERRERS = ["google", "direct", "wechat", "douyin", "weibo", "email", "facebook", "twitter"]
REFERRER_WEIGHTS = [0.30, 0.25, 0.15, 0.10, 0.05, 0.05, 0.05, 0.05]

PAGES = ["home", "product_detail", "search", "category", "checkout", "cart"]
PAGE_WEIGHTS = [0.30, 0.25, 0.15, 0.10, 0.10, 0.10]

CITIES = ["Beijing", "Shanghai", "Guangzhou", "Shenzhen", "Hangzhou", "Chengdu",
          "Wuhan", "Nanjing", "Xi'an", "Chongqing", "Suzhou", "Tianjin"]
AGE_GROUPS = ["18-24", "25-34", "35-44", "45-54", "55+"]
AGE_WEIGHTS = [0.25, 0.35, 0.25, 0.10, 0.05]


def generate():
    parser = argparse.ArgumentParser(description="Generate massive e-commerce event data")
    parser.add_argument("--events", type=int, default=N_EVENTS)
    parser.add_argument("--users", type=int, default=N_USERS)
    parser.add_argument("--products", type=int, default=N_PRODUCTS)
    parser.add_argument("--output", type=Path, default=DATA_DIR / "massive_events.parquet")
    parser.add_argument("--pg-insert", action="store_true", help="Also insert into PostgreSQL")
    args = parser.parse_args()

    rng = np.random.default_rng(42)

    print("=" * 60)
    print("  Generating Massive E-Commerce Data")
    print("=" * 60)
    print(f"  Events:   {args.events:,}")
    print(f"  Users:    {args.users:,}")
    print(f"  Products: {args.products:,} ({len(CATEGORIES)} categories)")
    print(f"  Period:   {START_DATE.date()} → {END_DATE.date()}")
    print(f"  Output:   {args.output}")

    # ---- 1. Generate Users ----
    t0 = time.time()
    print("\n[1/4] Generating users...")
    users = []
    for i in range(1, args.users + 1):
        uid = f"U{str(i).zfill(6)}"
        users.append({
            "user_id": uid,
            "age_group": rng.choice(AGE_GROUPS, p=AGE_WEIGHTS),
            "city": rng.choice(CITIES),
            "registered_date": (START_DATE - timedelta(days=int(rng.integers(1, 365)))).date(),
        })
    user_df = pd.DataFrame(users)
    print(f"  Users: {len(user_df)}")

    # ---- 2. Generate Products ----
    print("\n[2/4] Generating products...")
    products = []
    for i in range(1, args.products + 1):
        pid = f"P{str(i).zfill(6)}"
        cat = CATEGORIES[i % len(CATEGORIES)]
        products.append({
            "product_id": pid,
            "category": cat,
            "price": round(rng.uniform(9.9, 9999.0), 2),
            "created_date": (START_DATE - timedelta(days=int(rng.integers(30, 365)))).date(),
        })
    product_df = pd.DataFrame(products)
    print(f"  Products: {len(product_df)}, price range: {product_df['price'].min():.1f}-{product_df['price'].max():.1f}")

    # ---- 3. Generate Events ----
    print(f"\n[3/4] Generating {args.events:,} events...")
    total_seconds = int((END_DATE - START_DATE).total_seconds())

    user_ids = user_df["user_id"].values
    product_ids = product_df["product_id"].values
    product_cats = dict(zip(product_df["product_id"], product_df["category"]))

    # Generate in chunks for memory efficiency
    chunk_size = 100_000
    total_chunks = (args.events - 1) // chunk_size + 1
    all_event_files = []

    for chunk_idx in range(total_chunks):
        n = min(chunk_size, args.events - chunk_idx * chunk_size)
        ts_offsets = rng.integers(0, total_seconds, size=n)
        timestamps = [START_DATE + timedelta(seconds=int(off)) for off in ts_offsets]
        timestamps.sort()

        events_chunk = pd.DataFrame({
            "event_id": [str(uuid.uuid4()) for _ in range(n)],
            "user_id": rng.choice(user_ids, size=n),
            "event_type": rng.choice(EVENT_TYPES, size=n, p=EVENT_WEIGHTS),
            "product_id": rng.choice(product_ids, size=n),
            "timestamp": [ts.isoformat() + "+00:00" for ts in timestamps],
            "page": rng.choice(PAGES, size=n, p=PAGE_WEIGHTS),
            "referrer": rng.choice(REFERRERS, size=n, p=REFERRER_WEIGHTS),
            "duration_ms": rng.integers(0, 300000, size=n),
            "device": rng.choice(DEVICES, size=n, p=DEVICE_WEIGHTS),
            "browser": rng.choice(BROWSERS, size=n, p=BROWSER_WEIGHTS),
        })
        events_chunk["product_category"] = events_chunk["product_id"].map(product_cats)
        events_chunk["event_ts"] = pd.to_datetime(events_chunk["timestamp"])
        events_chunk["processed_at"] = pd.Timestamp.now()
        events_chunk["processing_date"] = events_chunk["event_ts"].dt.date

        # Write partitioned Parquet
        part_dir = args.output.parent / f"massive_part_{chunk_idx}"
        events_chunk.to_parquet(part_dir, partition_cols=["processing_date", "event_type"], index=False)
        all_event_files.append(part_dir)
        print(f"  Chunk {chunk_idx + 1}/{total_chunks}: {n:,} events")

    # Write consolidated
    # Merge all chunks into one partitioned dataset.
    # Read each partition *directory* (not individual files) so pyarrow
    # reconstructs the hive-style partition columns (processing_date, event_type).
    all_dfs = []
    for part_dir in all_event_files:
        all_dfs.append(pd.read_parquet(part_dir))
    final_df = pd.concat(all_dfs, ignore_index=True)
    final_df.to_parquet(args.output, index=False)
    # Cleanup chunks
    import shutil
    for part_dir in all_event_files:
        shutil.rmtree(part_dir, ignore_errors=True)

    elapsed = time.time() - t0
    file_size_mb = os.path.getsize(args.output) / (1024 * 1024)
    print(f"\n[4/4] Data generated in {elapsed:.1f}s")
    print(f"  Output: {args.output} ({file_size_mb:.1f} MB)")
    print(f"  Rows: {len(final_df):,}")

    # Summary (use final_df from before partition write)
    print(f"\n  Event distribution:")
    for et in EVENT_TYPES:
        cnt = (final_df["event_type"] == et).sum()
        print(f"    {et:<15s}: {cnt:>8,} ({cnt/len(final_df)*100:.1f}%)")
    print(f"\n  Device distribution:")
    for d in DEVICES:
        cnt = (final_df["device"] == d).sum()
        print(f"    {d:<10s}: {cnt:>8,} ({cnt/len(final_df)*100:.1f}%)")

    # ---- Optional: PostgreSQL insert ----
    if args.pg_insert:
        print("\n[Optional] Inserting into PostgreSQL...")
        try:
            from sqlalchemy import create_engine
            db_url = os.getenv("DATABASE_URL",
                f"postgresql://admin:changeme@localhost:5432/data_platform")
            engine = create_engine(db_url)
            # Insert in chunks
            for start in range(0, len(final_df), 10_000):
                end = min(start + 10_000, len(final_df))
                batch = final_df.iloc[start:end]
                batch.to_sql("user_events", engine, schema="raw", if_exists="append", index=False)
                if start % 100_000 == 0:
                    print(f"  Inserted {end:,}/{len(final_df):,}")
            engine.dispose()
            print("  PostgreSQL insert complete!")
        except Exception as e:
            print(f"  PostgreSQL insert failed: {e}")

    print(f"\n[OK] Massive data generation complete!")
    print(f"  Next steps:")
    print(f"    cd dbt && dbt run              # Run dbt models")
    print(f"    python demo_vector/embed.py    # Generate embeddings")


if __name__ == "__main__":
    generate()
