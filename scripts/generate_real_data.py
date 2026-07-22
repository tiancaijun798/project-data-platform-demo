#!/usr/bin/env python3
"""生成真实模式的电商用户行为模拟数据。"""
import json, random, uuid, os
from datetime import datetime, timedelta, timezone
from collections import defaultdict

os.makedirs("data", exist_ok=True)

# ---- 用户画像 ----
USER_PROFILES = {
    "power": {"count": 30, "daily_events": (20, 80), "purchase_rate": 0.15},
    "active": {"count": 80, "daily_events": (5, 25), "purchase_rate": 0.06},
    "regular": {"count": 150, "daily_events": (1, 8), "purchase_rate": 0.02},
    "new": {"count": 240, "daily_events": (0, 3), "purchase_rate": 0.01},
}
DEVICES = {"desktop": 0.35, "mobile": 0.50, "tablet": 0.15}
EVENT_WEIGHTS = {"view": 0.40, "click": 0.25, "search": 0.15, "add_to_cart": 0.10, "purchase": 0.06, "logout": 0.04}
CATEGORIES = ["电子产品", "服装", "食品", "家居", "运动户外", "图书", "美妆", "母婴"]
BROWSERS = {"Chrome": 0.55, "Safari": 0.22, "Edge": 0.13, "Firefox": 0.10}
REFERRERS = {"direct": 0.35, "google": 0.30, "wechat": 0.15, "douyin": 0.10, "weibo": 0.05, "email": 0.05}

users = {}
uid = 0
for segment, profile in USER_PROFILES.items():
    for _ in range(profile["count"]):
        uid += 1
        users[f"U{str(uid).zfill(4)}"] = {
            "segment": segment,
            "daily_events": profile["daily_events"],
            "purchase_rate": profile["purchase_rate"],
            "device": random.choices(list(DEVICES.keys()), weights=list(DEVICES.values()))[0],
            "browser": random.choices(list(BROWSERS.keys()), weights=list(BROWSERS.values()))[0],
            "fav_category": random.choice(CATEGORIES),
        }

products = {}
for i in range(1, 301):
    cat = random.choice(CATEGORIES)
    products[f"P{str(i).zfill(4)}"] = {
        "category": cat,
        "price": random.randint(9, 9999),
        "popularity": random.randint(1, 100),
    }

# ---- 生成 3 天数据 ----
now = datetime.now(timezone.utc)
events = []
for day_offset in range(3, 0, -1):
    day = now - timedelta(days=day_offset)
    is_weekend = day.weekday() >= 5

    for user_id, profile in users.items():
        daily_min, daily_max = profile["daily_events"]
        if is_weekend:
            daily_min = max(0, daily_min - 2)
            daily_max = max(1, daily_max - 5)

        num_events = random.randint(daily_min, daily_max)
        for _ in range(num_events):
            hour = random.choices(
                list(range(24)),
                weights=[1,1,1,2,3,5,12,20,25,22,18,15,15,18,20,22,20,18,15,12,10,8,5,3]
            )[0]
            minute = random.randint(0, 59)
            event_ts = day.replace(hour=hour, minute=minute, second=random.randint(0, 59))

            event_type = random.choices(list(EVENT_WEIGHTS.keys()), weights=list(EVENT_WEIGHTS.values()))[0]

            prod = random.choice(list(products.values()))
            product_id = random.choice(list(products.keys())) if random.random() < 0.7 else None

            duration_ms = None
            if event_type == "view":
                duration_ms = int(random.gauss(45000, 30000))
            elif event_type == "click":
                duration_ms = int(random.gauss(15000, 12000))
            elif event_type == "search":
                duration_ms = int(random.gauss(25000, 20000))
            elif event_type == "add_to_cart":
                duration_ms = int(random.gauss(8000, 5000))

            events.append({
                "event_id": str(uuid.uuid4()),
                "user_id": user_id,
                "event_type": event_type,
                "product_id": product_id,
                "product_category": prod["category"] if product_id else None,
                "timestamp": event_ts.isoformat(),
                "page": random.choice(["home", "product_detail", "search_results", "cart", "checkout", "profile"]),
                "referrer": random.choices(list(REFERRERS.keys()), weights=list(REFERRERS.values()))[0],
                "duration_ms": max(0, duration_ms) if duration_ms else None,
                "device": profile["device"],
                "browser": profile["browser"],
            })

random.shuffle(events)

with open("data/input.jsonl", "w", encoding="utf-8") as f:
    for e in events:
        f.write(json.dumps(e, ensure_ascii=False) + "\n")

# 统计
by_type = defaultdict(int)
by_day = defaultdict(int)
for e in events:
    by_type[e["event_type"]] += 1
    by_day[e["timestamp"][:10]] += 1

print(f"[OK] Generated {len(events)} events across {len(by_day)} days")
print(f"     Unique users: {len(users)}")
print(f"     By type: {dict(by_type)}")
print(f"     By day:  {dict(sorted(by_day.items()))}")
print(f"     Output:  data/input.jsonl ({os.path.getsize('data/input.jsonl')/1024:.1f} KB)")
