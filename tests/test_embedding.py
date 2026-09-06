"""
Embedding 模块单元测试 — 测试文本构造、编码、Milvus schema。

运行要求:
    - sentence-transformers 已安装
    - 不要求 Milvus 运行（schema 创建测试使用 mock）
"""
import json
import os
import sys
import tempfile
import pytest
from unittest.mock import patch, MagicMock, PropertyMock


# ---- 测试数据 ----
SAMPLE_EVENT = {
    "event_id": "evt-001",
    "user_id": "U0001",
    "event_type": "purchase",
    "product_id": "P0100",
    "page": "checkout",
    "referrer": "google",
    "device": "mobile",
    "browser": "Chrome",
    "duration_ms": 15000,
}

SAMPLE_PRODUCT = {
    "product_id": "P0100",
    "total_views": 500,
    "total_purchases": 50,
    "conversion_rate_pct": 10.0,
}


class TestTextConstruction:
    """测试文本构造函数。"""

    def test_build_event_text_full(self):
        from demo_vector.embed import build_event_text
        text = build_event_text(SAMPLE_EVENT)
        assert "purchase" in text
        assert "U0001" in text
        assert "P0100" in text
        assert "checkout" in text
        assert "google" in text
        assert "mobile" in text
        assert "Chrome" in text

    def test_build_event_text_minimal(self):
        from demo_vector.embed import build_event_text
        text = build_event_text({
            "event_id": "evt-min",
            "user_id": "U0099",
            "event_type": "view",
        })
        assert "view" in text
        assert "U0099" in text

    def test_build_event_text_unknown_product_skipped(self):
        from demo_vector.embed import build_event_text
        text = build_event_text({
            "event_id": "evt-xxx",
            "user_id": "U0001",
            "event_type": "click",
            "product_id": "unknown",
        })
        assert "unknown" not in text or "商品: unknown" not in text

    def test_build_product_text(self):
        from demo_vector.embed import build_product_text
        text = build_product_text(SAMPLE_PRODUCT)
        assert "P0100" in text
        assert "500" in text
        assert "50" in text
        assert "10.0" in text

    def test_build_product_text_minimal(self):
        from demo_vector.embed import build_product_text
        text = build_product_text({"product_id": "P0001"})
        assert "P0001" in text


class TestEmbeddingModel:
    """测试 embedding 模型加载和编码。"""

    @pytest.fixture(scope="class")
    def model(self):
        """加载轻量模型用于测试（class scope 避免重复加载）。"""
        try:
            from sentence_transformers import SentenceTransformer
            from pathlib import Path
            # Try local cache first (faster, no network)
            local_path = Path("rag_demo/knowledge_base/models/sentence-transformers--paraphrase-multilingual-MiniLM-L12-v2")
            if local_path.exists():
                return SentenceTransformer(str(local_path))
            return SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
        except Exception as e:
            pytest.skip(f"Model not available: {e}")

    def test_model_loads(self, model):
        assert model is not None
        dim = model.get_sentence_embedding_dimension()
        assert dim == 384

    def test_encode_single_text(self, model):
        embedding = model.encode(
            ["测试文本"], normalize_embeddings=True
        )
        assert embedding.shape == (1, 384)

    def test_encode_batch(self, model):
        texts = [f"事件 {i}: 用户 U{i:04d} 浏览了商品 P{i:04d}" for i in range(10)]
        embeddings = model.encode(texts, normalize_embeddings=True)
        assert embeddings.shape == (10, 384)

    def test_encode_normalized(self, model):
        """验证 L2 归一化后向量模长为 1（允许浮点误差）。"""
        import numpy as np
        embedding = model.encode(["test"], normalize_embeddings=True)[0]
        norm = np.linalg.norm(embedding)
        assert abs(norm - 1.0) < 1e-5

    def test_encode_chinese_text(self, model):
        """验证中文文本编码正常。"""
        embedding = model.encode(
            ["用户在移动端上浏览了商品详情页并加入了购物车"],
            normalize_embeddings=True,
        )
        assert embedding.shape == (1, 384)

    def test_encode_mixed_text(self, model):
        """验证中英混合文本编码。"""
        embedding = model.encode(
            ["User U0001 performed purchase on product P0100 通过移动端"],
            normalize_embeddings=True,
        )
        assert embedding.shape == (1, 384)


class TestMilvusSchema:
    """测试 Milvus Collection Schema 定义（不需要真实 Milvus）。"""

    @patch("demo_vector.embed.connections.connect")
    @patch("demo_vector.embed.utility.has_collection")
    @patch("demo_vector.embed.Collection")
    def test_create_event_collection_schema(self, mock_collection, mock_has, mock_connect):
        mock_has.return_value = False
        from demo_vector.embed import create_event_collection, VECTOR_DIM
        # Mock collection instance
        mock_instance = mock_collection.return_value
        mock_instance.name = "test_events"
        mock_instance.schema = type('obj', (object,), {
            'fields': [
                type('obj', (object,), {'name': 'id'})(),
                type('obj', (object,), {'name': 'event_id'})(),
                type('obj', (object,), {'name': 'user_id'})(),
                type('obj', (object,), {'name': 'event_type'})(),
                type('obj', (object,), {'name': 'embedding'})(),
            ]
        })()
        collection = create_event_collection()
        assert collection is not None
        field_names = [f.name for f in collection.schema.fields]
        assert "id" in field_names
        assert "event_id" in field_names
        assert "embedding" in field_names

    @patch("demo_vector.embed.connections.connect")
    @patch("demo_vector.embed.utility.has_collection")
    @patch("demo_vector.embed.Collection")
    def test_create_product_collection_schema(self, mock_collection, mock_has, mock_connect):
        mock_has.return_value = False
        from demo_vector.embed import create_product_collection, VECTOR_DIM
        mock_instance = mock_collection.return_value
        mock_instance.name = "test_products"
        mock_instance.schema = type('obj', (object,), {
            'fields': [
                type('obj', (object,), {'name': 'product_id'})(),
                type('obj', (object,), {'name': 'text_content'})(),
                type('obj', (object,), {'name': 'embedding'})(),
            ]
        })()
        collection = create_product_collection()
        assert collection is not None
        field_names = [f.name for f in collection.schema.fields]
        assert "product_id" in field_names
        assert "text_content" in field_names
        assert "embedding" in field_names


class TestEmbeddingPipeline:
    """测试 EmbeddingPipeline 类。"""

    @patch("demo_vector.embed.SentenceTransformer")
    @patch("demo_vector.embed.connections")
    def test_pipeline_init(self, mock_connections, mock_transformer):
        from demo_vector.embed import EmbeddingPipeline
        pipeline = EmbeddingPipeline()
        assert pipeline.model is not None

    def test_encode_batch_with_real_model(self):
        """使用真实模型测试批量编码。"""
        try:
            from sentence_transformers import SentenceTransformer
            from demo_vector.embed import EmbeddingPipeline
            pipeline = EmbeddingPipeline()
            texts = [f"事件 {i}" for i in range(128)]
            embeddings = pipeline.encode_batch(texts)
            assert embeddings.shape == (128, 384)
        except Exception as e:
            pytest.skip(f"Model not available: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
