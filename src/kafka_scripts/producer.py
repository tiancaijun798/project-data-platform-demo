#!/usr/bin/env python3
"""
Kafka Producer — 批量生成模拟用户行为事件并发送到 Kafka Topic。

用法:
    python producer.py [--bootstrap-server localhost:9092] [--topic events] [--count 100]
"""

import argparse
import json
import random
import time
import uuid
from datetime import datetime, timedelta, timezone

try:
    from kafka import KafkaProducer
    from kafka.errors import KafkaError
except ImportError:
    print("请先安装 kafka-python: pip install kafka-python")
    raise


# ---- 模拟数据模板 ----
USER_IDS = [f"U{str(i).zfill(4)}" for i in range(1, 51)]
PRODUCT_IDS = [f"P{str(i).zfill(4)}" for i in range(1, 201)]
EVENT_TYPES = ["click", "view", "add_to_cart", "purchase", "search", "logout"]
PAGES = ["home", "product_detail", "cart", "checkout", "profile", "search_results"]
REFERRERS = ["google", "direct", "twitter", "facebook", "email", None]


def generate_event() -> dict:
    """生成一条模拟用户行为事件。"""
    now = datetime.now(timezone.utc)
    event_time = now - timedelta(seconds=random.randint(0, 3600))

    return {
        "event_id": str(uuid.uuid4()),
        "user_id": random.choice(USER_IDS),
        "event_type": random.choice(EVENT_TYPES),
        "product_id": random.choice(PRODUCT_IDS) if random.random() > 0.3 else None,
        "timestamp": event_time.isoformat(),
        "page": random.choice(PAGES),
        "referrer": random.choice(REFERRERS),
        "duration_ms": random.randint(100, 30000),
        "device": random.choice(["desktop", "mobile", "tablet"]),
        "browser": random.choice(["Chrome", "Firefox", "Safari", "Edge"]),
    }


def produce_events(
    bootstrap_servers: str = "localhost:9092",
    topic: str = "events",
    count: int = 100,
    batch_size: int = 10,
    output_jsonl: str = None,
) -> int:
    """
    批量生成事件并发送到 Kafka，同时可选写入本地 JSONL 文件。

    返回成功发送的事件数量。
    """
    producer = KafkaProducer(
        bootstrap_servers=bootstrap_servers,
        value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode("utf-8"),
        acks="all",
        retries=3,
        max_block_ms=30000,
    )

    jsonl_fh = open(output_jsonl, "w", encoding="utf-8") if output_jsonl else None
    sent = 0

    try:
        for i in range(0, count, batch_size):
            batch = [generate_event() for _ in range(min(batch_size, count - i))]

            for event in batch:
                future = producer.send(topic, value=event)
                try:
                    record_meta = future.get(timeout=10)
                    sent += 1
                    if jsonl_fh:
                        jsonl_fh.write(json.dumps(event, ensure_ascii=False) + "\n")
                except KafkaError as e:
                    print(f"  ❌ 发送失败: {e}")

            print(f"  已发送 {sent}/{count} 条消息到 topic [{topic}]")

        producer.flush()
        print(f"\n✅ 完成: 成功发送 {sent} 条事件")
        if jsonl_fh:
            print(f"   本地 JSONL 文件: {output_jsonl}")
    finally:
        producer.close()
        if jsonl_fh:
            jsonl_fh.close()

    return sent


def main():
    parser = argparse.ArgumentParser(description="Kafka 模拟事件生产者")
    parser.add_argument("--bootstrap-server", default="localhost:9092")
    parser.add_argument("--topic", default="events")
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--output-jsonl", default="data/input.jsonl", help="本地 JSONL 输出路径")
    args = parser.parse_args()

    print("=" * 50)
    print("  Kafka Producer — 模拟事件生成器")
    print("=" * 50)
    print(f"  Bootstrap: {args.bootstrap_server}")
    print(f"  Topic:     {args.topic}")
    print(f"  Count:     {args.count}")
    print(f"  JSONL:     {args.output_jsonl}")
    print("-" * 50)

    start = time.time()
    sent = produce_events(
        bootstrap_servers=args.bootstrap_server,
        topic=args.topic,
        count=args.count,
        output_jsonl=args.output_jsonl,
    )
    elapsed = time.time() - start

    print("-" * 50)
    print(f"  耗时: {elapsed:.2f}s | 吞吐: {sent/elapsed:.0f} msg/s")
    print("=" * 50)


if __name__ == "__main__":
    main()
