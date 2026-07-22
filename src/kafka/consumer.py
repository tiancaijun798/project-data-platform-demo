#!/usr/bin/env python3
"""
Kafka Consumer — 消费指定 Topic 消息并写入本地 JSONL 文件。

用法:
    python consumer.py [--bootstrap-server localhost:9092] [--topic events] [--output data/input.jsonl]
"""

import argparse
import json
import signal
import sys
import time
from pathlib import Path

try:
    from kafka import KafkaConsumer
    from kafka.errors import KafkaError
except ImportError:
    print("请先安装 kafka-python: pip install kafka-python")
    raise


class EventConsumer:
    """消费 Kafka 事件并写入本地 JSONL。"""

    def __init__(
        self,
        bootstrap_servers: str = "localhost:9092",
        topic: str = "events",
        group_id: str = "demo-consumer-group",
        output_path: str = "data/input.jsonl",
        max_messages: int = 0,
    ):
        self.topic = topic
        self.output_path = Path(output_path)
        self.max_messages = max_messages
        self.received = 0
        self.running = True

        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        self.consumer = KafkaConsumer(
            topic,
            bootstrap_servers=bootstrap_servers,
            group_id=group_id,
            auto_offset_reset="earliest",
            enable_auto_commit=True,
            auto_commit_interval_ms=5000,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            consumer_timeout_ms=30000,  # 30s 无消息则退出
        )

        # 注册优雅退出的信号处理
        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)

    def _shutdown(self, signum, frame):
        print("\n  收到停止信号，正在优雅退出...")
        self.running = False

    def consume(self) -> int:
        """消费消息并写入 JSONL。返回写入条数。"""
        print(f"  监听 Topic: {self.topic}")
        print(f"  输出文件:   {self.output_path}")
        print(f"  最大消息数: {self.max_messages if self.max_messages else '无限制'}")
        print("-" * 50)

        with open(self.output_path, "a", encoding="utf-8") as fh:
            try:
                for message in self.consumer:
                    if not self.running:
                        break

                    fh.write(
                        json.dumps(message.value, ensure_ascii=False) + "\n"
                    )
                    self.received += 1

                    if self.received % 50 == 0:
                        print(
                            f"  已消费 {self.received} 条 | "
                            f"partition={message.partition} "
                            f"offset={message.offset}"
                        )

                    if self.max_messages and self.received >= self.max_messages:
                        print(f"  已达到最大消息数 {self.max_messages}，停止消费。")
                        break

            except KafkaError as e:
                print(f"  ❌ Kafka 错误: {e}")
            except Exception as e:
                print(f"  ❌ 异常: {e}")

        self.consumer.close()
        return self.received


def main():
    parser = argparse.ArgumentParser(description="Kafka 事件消费者 — 落地 JSONL")
    parser.add_argument("--bootstrap-server", default="localhost:9092")
    parser.add_argument("--topic", default="events")
    parser.add_argument("--group-id", default="demo-consumer-group")
    parser.add_argument("--output", default="data/input.jsonl")
    parser.add_argument("--max-messages", type=int, default=0, help="最大消费条数（0=无限制）")
    args = parser.parse_args()

    print("=" * 50)
    print("  Kafka Consumer — 事件落地")
    print("=" * 50)

    consumer = EventConsumer(
        bootstrap_servers=args.bootstrap_server,
        topic=args.topic,
        group_id=args.group_id,
        output_path=args.output,
        max_messages=args.max_messages,
    )

    start = time.time()
    count = consumer.consume()
    elapsed = time.time() - start

    print("-" * 50)
    print(f"  ✅ 落地完成: {count} 条 → {args.output}")
    if elapsed > 0:
        print(f"  耗时: {elapsed:.2f}s | 速率: {count/elapsed:.0f} msg/s")
    print("=" * 50)


if __name__ == "__main__":
    main()
