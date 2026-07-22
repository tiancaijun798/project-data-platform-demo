"""
PySpark 数据处理单元测试
"""
import json
import os
import tempfile
import pytest


# ---- 测试数据 ----
SAMPLE_EVENTS = [
    {
        "event_id": "evt-001", "user_id": "U0001", "event_type": "view",
        "product_id": "P0100", "timestamp": "2026-07-20T10:30:00+00:00",
        "page": "product_detail", "referrer": "google",
        "duration_ms": 15000, "device": "mobile", "browser": "Chrome",
    },
    {
        "event_id": "evt-002", "user_id": "U0002", "event_type": "purchase",
        "product_id": None, "timestamp": "2026-07-20T11:00:00+00:00",
        "page": "checkout", "referrer": None,
        "duration_ms": -100, "device": "desktop", "browser": "Firefox",
    },
    {
        "event_id": "evt-003", "user_id": "U0001", "event_type": "CLICK",
        "product_id": "P0200", "timestamp": "2026-07-20T12:00:00+00:00",
        "page": "home", "referrer": "direct",
        "duration_ms": 400000, "device": "tablet", "browser": "Safari",
    },
    {
        "event_id": "evt-004", "user_id": None, "event_type": "view",
        "product_id": "P0300", "timestamp": "2026-07-20T13:00:00+00:00",
        "page": "home", "referrer": "google",
        "duration_ms": 5000, "device": "mobile", "browser": "Chrome",
    },
]


def create_temp_jsonl(events):
    """创建临时测试 JSONL 文件。"""
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8")
    for e in events:
        tmp.write(json.dumps(e, ensure_ascii=False) + "\n")
    tmp.close()
    return tmp.name


class TestProcessDataLocal:
    """本地 pandas 清洗逻辑测试（与 PySpark 逻辑等价）。"""

    def test_read_and_count(self):
        """测试读取 JSONL 并计数。"""
        import pandas as pd
        path = create_temp_jsonl(SAMPLE_EVENTS)
        df = pd.read_json(path, lines=True)
        assert len(df) == 4
        os.unlink(path)

    def test_remove_null_keys(self):
        """测试删除空 event_id 或 user_id 的行。"""
        import pandas as pd
        path = create_temp_jsonl(SAMPLE_EVENTS)
        df = pd.read_json(path, lines=True)
        before = len(df)
        df = df.dropna(subset=["event_id", "user_id"])
        assert len(df) == 3  # evt-004 user_id=None 被丢弃
        assert before - len(df) == 1
        os.unlink(path)

    def test_fill_missing_product_id(self):
        """测试填充缺失 product_id。"""
        import pandas as pd
        path = create_temp_jsonl(SAMPLE_EVENTS)
        df = pd.read_json(path, lines=True)
        df = df.dropna(subset=["event_id", "user_id"])
        df["product_id"] = df["product_id"].fillna("unknown")
        assert df[df["event_id"] == "evt-002"]["product_id"].values[0] == "unknown"
        os.unlink(path)

    def test_normalize_event_type(self):
        """测试 event_type 统一小写。"""
        import pandas as pd
        path = create_temp_jsonl(SAMPLE_EVENTS)
        df = pd.read_json(path, lines=True)
        df["event_type"] = df["event_type"].str.lower()
        assert df[df["event_id"] == "evt-003"]["event_type"].values[0] == "click"
        os.unlink(path)

    def test_filter_invalid_duration(self):
        """测试过滤异常 duration_ms。"""
        import pandas as pd
        path = create_temp_jsonl(SAMPLE_EVENTS)
        df = pd.read_json(path, lines=True)
        df = df.dropna(subset=["event_id", "user_id"])
        before = len(df)
        df["duration_ms"] = df["duration_ms"].clip(0, 300000)
        # evt-002 duration_ms=-100 被 clip 到 0, evt-003 被 clip 到 300000
        assert df[df["event_id"] == "evt-002"]["duration_ms"].values[0] == 0
        assert df[df["event_id"] == "evt-003"]["duration_ms"].values[0] == 300000
        assert len(df) == before  # clip 不会删除行
        os.unlink(path)

    def test_fill_missing_referrer(self):
        """测试填充缺失 referrer。"""
        import pandas as pd
        path = create_temp_jsonl(SAMPLE_EVENTS)
        df = pd.read_json(path, lines=True)
        df["referrer"] = df["referrer"].fillna("direct")
        assert df[df["event_id"] == "evt-002"]["referrer"].values[0] == "direct"
        os.unlink(path)

    def test_output_parquet(self):
        """测试端到端：JSONL → 清洗 → Parquet。"""
        import pandas as pd
        path = create_temp_jsonl(SAMPLE_EVENTS)
        df = pd.read_json(path, lines=True)
        df = df.dropna(subset=["event_id", "user_id"])
        df["event_ts"] = pd.to_datetime(df["timestamp"], errors="coerce")
        df["event_type"] = df["event_type"].str.lower()
        df["product_id"] = df["product_id"].fillna("unknown")
        df["referrer"] = df["referrer"].fillna("direct")
        df["duration_ms"] = df["duration_ms"].clip(0, 300000)
        df["processed_at"] = pd.Timestamp.now()
        df["processing_date"] = pd.Timestamp.now().date()

        out = tempfile.mkdtemp()
        df.to_parquet(os.path.join(out, "test.parquet"), index=False)
        df_back = pd.read_parquet(out)
        assert len(df_back) == 3  # 4 原始, -1 null user_id
        assert df_back[df_back["event_id"] == "evt-003"]["product_id"].values[0] == "P0200"
        os.unlink(path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
