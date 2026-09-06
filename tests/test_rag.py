"""
RAG 模块单元测试 — 测试文档分块、检索、prompt 构建、LLM 生成。

运行要求:
    - sentence-transformers 或 TF-IDF fallback
    - FAISS 已安装
"""
import json
import os
import sys
import tempfile
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path


# ---- 将 rag_demo 加入 path ----
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "rag_demo"))


class TestChunking:
    """测试事件行 → 自然语言 chunk 转换。"""

    def test_row_to_chunk_full(self):
        from build_knowledge_base import row_to_chunk
        row = {
            "user_id": "U0001",
            "event_type": "purchase",
            "product_id": "P0100",
            "product_category": "Electronics",
            "referrer": "google",
            "page": "checkout",
            "device": "mobile",
            "browser": "Chrome",
            "duration_ms": 15000,
        }
        chunk = row_to_chunk(row)
        assert "U0001" in chunk
        assert "purchase" in chunk
        assert "P0100" in chunk
        assert "Electronics" in chunk
        assert "google" in chunk

    def test_row_to_chunk_minimal(self):
        from build_knowledge_base import row_to_chunk
        row = {
            "user_id": "U0099",
            "event_type": "view",
        }
        chunk = row_to_chunk(row)
        assert "U0099" in chunk
        assert "view" in chunk

    def test_row_to_chunk_skips_none_product(self):
        from build_knowledge_base import row_to_chunk
        row = {
            "user_id": "U0001",
            "event_type": "click",
            "product_id": None,
            "device": "desktop",
        }
        chunk = row_to_chunk(row)
        # product_id=None 不应出现在 chunk 中
        assert "None" not in chunk
        assert "desktop" in chunk

    def test_row_to_chunk_skips_direct_referrer(self):
        from build_knowledge_base import row_to_chunk
        row = {
            "user_id": "U0001",
            "event_type": "view",
            "referrer": "direct",
        }
        chunk = row_to_chunk(row)
        # direct referrer 应被省略
        assert "direct" not in chunk.lower() or "from direct" not in chunk.lower()


class TestSyntheticData:
    """测试合成数据生成。"""

    def test_generate_synthetic_events(self):
        from build_knowledge_base import generate_synthetic_events
        events = generate_synthetic_events(500)
        assert len(events) == 500
        # 验证必要字段
        for e in events[:10]:
            assert "event_id" in e
            assert "user_id" in e
            assert "event_type" in e
            assert "device" in e
            assert "browser" in e

    def test_generate_deterministic(self):
        from build_knowledge_base import generate_synthetic_events
        events1 = generate_synthetic_events(100)
        events2 = generate_synthetic_events(100)
        # Same seed produces same data distribution, but UUIDs differ
        # Verify same counts of event types instead
        from collections import Counter
        c1 = Counter(e["event_type"] for e in events1)
        c2 = Counter(e["event_type"] for e in events2)
        assert c1 == c2  # Same distribution
        assert len(events1) == len(events2) == 100


class TestBuildFAISSIndex:
    """测试 FAISS 索引构建。"""

    def test_build_index_with_tfidf_fallback(self):
        """使用 TF-IDF fallback 构建 FAISS 索引。"""
        import faiss
        import tempfile
        import numpy as np
        from build_knowledge_base import build_faiss_index

        # Generate 500 diverse chunks for robust TF-IDF+SVD
        np.random.seed(42)
        events = ["view", "click", "purchase", "search", "add_to_cart", "logout"]
        devs = ["desktop Chrome", "mobile Safari", "tablet Firefox", "mobile Edge"]
        pages = ["home page", "product detail", "checkout", "search results", "category listing"]
        refs = ["google search", "direct visit", "wechat share", "email campaign", "facebook ad", "twitter link"]
        chunks = []
        for i in range(500):
            chunks.append(
                f"User U{i:04d} performed {np.random.choice(events)} on product "
                f"P{np.random.randint(1,100):04d} via {np.random.choice(devs)} "
                f"on {np.random.choice(pages)} from {np.random.choice(refs)}"
            )
        metadata = [{"id": i, "event_type": "test", "user_id": f"U{i:04d}"} for i in range(500)]

        tmpdir = tempfile.mkdtemp(dir="C:/temp" if os.path.exists("C:/temp") else None)
        try:
            output_dir = Path(tmpdir) / "kb"
            output_dir.mkdir(parents=True, exist_ok=True)
            stats = build_faiss_index(
                chunks=chunks, metadata=metadata,
                model=None, output_dir=output_dir,
            )
            assert stats["total_vectors"] == 500
            assert (output_dir / "index.faiss").exists()
            assert (output_dir / "metadata.json").exists()

            # Verify read-back works
            index = faiss.read_index(str(output_dir / "index.faiss"))
            assert index.ntotal == 500
            # Verify search works
            D, I = index.search(np.random.randn(1, stats["vector_dim"]).astype(np.float32), 5)
            assert len(I[0]) == 5
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_build_index_empty_chunks(self):
        """测试空 chunks 的行为。"""
        import faiss
        import tempfile
        from build_knowledge_base import build_faiss_index

        tmpdir = tempfile.mkdtemp(dir="C:/temp" if os.path.exists("C:/temp") else None)
        try:
            output_dir = Path(tmpdir) / "kb"
            output_dir.mkdir(parents=True, exist_ok=True)
            stats = build_faiss_index(
                chunks=[],
                metadata=[],
                model=None,
                output_dir=output_dir,
            )
            assert stats["total_vectors"] == 0
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestPromptBuilding:
    """测试 RAG prompt 构建。"""

    def test_build_prompt_default_system(self):
        from rag_server import build_prompt
        docs = [
            {
                "id": 0,
                "score": 0.95,
                "event_type": "purchase",
                "user_id": "U0001",
                "product_id": "P0100",
                "chunk": "User U0001 performed purchase on product P0100 via mobile Chrome",
                "metadata": {"device": "mobile", "browser": "Chrome"},
            },
            {
                "id": 1,
                "score": 0.88,
                "event_type": "add_to_cart",
                "user_id": "U0002",
                "product_id": "P0200",
                "chunk": "User U0002 performed add_to_cart on product P0200 via desktop Firefox",
                "metadata": {"device": "desktop", "browser": "Firefox"},
            },
        ]
        prompt = build_prompt("哪些用户通过移动端购买了商品？", docs)
        assert "data analytics assistant" in prompt.lower()
        assert "U0001" in prompt
        assert "U0002" in prompt
        assert "purchase" in prompt
        assert "移动端" in prompt or "purchased" in prompt

    def test_build_prompt_custom_system(self):
        from rag_server import build_prompt
        docs = [{"id": 0, "score": 0.9, "event_type": "view", "user_id": "U0001",
                  "product_id": "P0100", "chunk": "test chunk", "metadata": {}}]
        custom_prompt = "你是一个电商数据分析专家。"
        prompt = build_prompt("query", docs, system_prompt=custom_prompt)
        assert custom_prompt in prompt

    def test_build_prompt_empty_docs(self):
        from rag_server import build_prompt
        prompt = build_prompt("test query", [])
        assert "test query" in prompt
        assert "Context" in prompt


class TestRAGServerEndpoints:
    """测试 RAG FastAPI 端点（无需真实 index）。"""

    @pytest.fixture
    def client(self):
        """创建测试 client — RAG server 在无 index 时仍可启动。"""
        from rag_server import app
        from fastapi.testclient import TestClient
        return TestClient(app)

    def test_health_degraded(self, client):
        """无 index 时应返回 degraded 状态。"""
        response = client.get("/rag/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"  # no index loaded
        assert data["vectors_in_index"] == 0

    def test_query_no_index(self, client):
        """无 index 时查询应返回 503。"""
        response = client.post(
            "/rag/query",
            json={
                "query": "test query",
                "top_k": 3,
                "mode": "retrieve-only",
            },
        )
        assert response.status_code == 503


class TestLLMGenerator:
    """测试 LLM 生成模块。"""

    def test_llm_generator_module_exists(self):
        """验证 llm_generator 模块可导入。"""
        try:
            from llm_generator import LLMGenerator
            assert LLMGenerator is not None
        except ImportError as e:
            pytest.skip(f"llm_generator not available: {e}")

    def test_generator_init(self):
        """测试 LLMGenerator 初始化。"""
        try:
            from llm_generator import LLMGenerator
            gen = LLMGenerator(
                api_key="test-key",
                base_url="https://api.test.com/v1",
                model="test-model",
            )
            assert gen.api_key == "test-key"
            assert gen.model == "test-model"
        except ImportError:
            pytest.skip("llm_generator not available")

    def test_generate_with_docs(self):
        """测试带文档的生成（mock API call）。"""
        try:
            from llm_generator import LLMGenerator
            gen = LLMGenerator(api_key="test-key")
            # 不实际调用 API，只测试 prompt 构建
            docs = [
                {"chunk": "User U0001 purchased product P0100", "event_type": "purchase"},
            ]
            prompt = gen._build_generation_prompt("test query", docs)
            assert "test query" in prompt
            assert "U0001" in prompt
        except ImportError:
            pytest.skip("llm_generator not available")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
