"""
FastAPI 端点测试 — 使用 TestClient 测试所有 API 路由。

测试覆盖:
    - 健康检查端点
    - 基础信息端点
    - 统计 API 端点（mock DB）
    - 自定义查询端点（安全检查）
"""
import json
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


# ---- Mock the database engine before importing app ----
# 避免导入时尝试连接真实数据库
with patch("src.main.create_engine"), \
     patch("src.main.engine", MagicMock()), \
     patch("src.main.Instrumentator"):
    from src.main import app


client = TestClient(app)


# ---- 测试数据 ----
MOCK_USER_STATS = [
    {"user_segment": "active", "cnt": 150, "events": 4500},
    {"user_segment": "new", "cnt": 80, "events": 800},
    {"user_segment": "lapsed", "cnt": 40, "events": 200},
    {"user_segment": "vip", "cnt": 20, "events": 1500},
]

MOCK_EVENT_STATS = [
    {"event_type": "view", "cnt": 5000},
    {"event_type": "click", "cnt": 3000},
    {"event_type": "purchase", "cnt": 800},
]

MOCK_PRODUCT_STATS = [
    {"product_id": "P0001", "total_views": 200, "total_purchases": 50, "conversion_rate_pct": 25.0},
    {"product_id": "P0002", "total_views": 150, "total_purchases": 30, "conversion_rate_pct": 20.0},
]

MOCK_DASHBOARD = [
    {"total_events": 10000, "today_orders": 300, "today_users": 1200, "conversion_rate": 3.5},
]

MOCK_TREND = [
    {"date": "2026-07-20", "events": 500, "purchases": 25},
    {"date": "2026-07-21", "events": 600, "purchases": 30},
]

MOCK_HEATMAP = [
    {"hour": 0, "events": 100},
    {"hour": 12, "events": 800},
    {"hour": 18, "events": 600},
]

MOCK_SEGMENTS = [
    {"segment": "active", "users": 150, "events": 4500, "pct": 51.7},
    {"segment": "new", "users": 80, "events": 800, "pct": 27.6},
]

MOCK_FUNNEL = [
    {"name": "浏览/搜索", "value": 10000, "pct": 100.0},
    {"name": "加入购物车", "value": 1500, "pct": 15.0},
    {"name": "下单购买", "value": 800, "pct": 8.0},
]


class TestHealthEndpoints:
    """测试健康检查与基础信息端点。"""

    def test_root(self):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert data["version"] == "0.1.0"

    def test_health(self):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}

    def test_info(self):
        response = client.get("/info")
        assert response.status_code == 200
        data = response.json()
        assert data["project"] == "project-data-platform-demo"
        assert data["framework"] == "FastAPI"
        assert "environment" in data
        assert "db_host" in data


class TestStatsEndpoints:
    """测试统计 API 端点（mock DB）。"""

    @patch("src.main._query")
    def test_user_stats(self, mock_query):
        mock_query.return_value = MOCK_USER_STATS
        response = client.get("/api/stats/users")
        assert response.status_code == 200
        data = response.json()
        assert "users_by_segment" in data
        assert len(data["users_by_segment"]) == 4

    @patch("src.main._query")
    def test_event_stats(self, mock_query):
        mock_query.return_value = MOCK_EVENT_STATS
        response = client.get("/api/stats/events")
        assert response.status_code == 200
        data = response.json()
        assert "events_by_type" in data
        assert len(data["events_by_type"]) == 3

    @patch("src.main._query")
    def test_top_products(self, mock_query):
        mock_query.return_value = MOCK_PRODUCT_STATS
        response = client.get("/api/stats/products/top?limit=5")
        assert response.status_code == 200
        data = response.json()
        assert "top_products" in data
        assert len(data["top_products"]) == 2

    @patch("src.main._query")
    def test_top_products_default_limit(self, mock_query):
        mock_query.return_value = MOCK_PRODUCT_STATS
        response = client.get("/api/stats/products/top")
        assert response.status_code == 200

    @patch("src.main._query")
    def test_dashboard(self, mock_query):
        mock_query.return_value = MOCK_DASHBOARD
        response = client.get("/api/stats/dashboard")
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert data["data"]["total_events"] == 10000

    @patch("src.main._query")
    def test_sales_trend(self, mock_query):
        mock_query.return_value = MOCK_TREND
        response = client.get("/api/stats/sales-trend")
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert len(data["data"]) == 2

    @patch("src.main._query")
    def test_hourly_heatmap(self, mock_query):
        mock_query.return_value = MOCK_HEATMAP
        response = client.get("/api/stats/hourly-heatmap")
        assert response.status_code == 200
        data = response.json()
        assert "data" in data

    @patch("src.main._query")
    def test_user_segments(self, mock_query):
        mock_query.return_value = MOCK_SEGMENTS
        response = client.get("/api/stats/user-segments")
        assert response.status_code == 200
        data = response.json()
        assert "data" in data

    @patch("src.main._query")
    def test_top_users(self, mock_query):
        mock_query.return_value = []
        response = client.get("/api/stats/top-users?limit=5")
        assert response.status_code == 200

    @patch("src.main._query")
    def test_product_rank(self, mock_query):
        mock_query.return_value = []
        response = client.get("/api/stats/product-rank?limit=5")
        assert response.status_code == 200

    @patch("src.main._query")
    def test_category_share(self, mock_query):
        mock_query.return_value = []
        response = client.get("/api/stats/category-share")
        assert response.status_code == 200

    @patch("src.main._query")
    def test_funnel(self, mock_query):
        mock_query.return_value = MOCK_FUNNEL
        response = client.get("/api/stats/funnel")
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert len(data["data"]) == 3

    @patch("src.main._query")
    def test_services(self, mock_query):
        """services 端点不调用 _query，但需要 patch 以便其他 mock 不影响。"""
        mock_query.return_value = []
        response = client.get("/api/stats/services")
        assert response.status_code == 200
        data = response.json()
        assert "data" in data


class TestQueryEndpoint:
    """测试自定义 SQL 查询端点。"""

    @patch("src.main._query")
    def test_run_select_query(self, mock_query):
        mock_query.return_value = [{"col1": "val1", "col2": 123}]
        response = client.post(
            "/api/stats/query",
            json={"sql": "SELECT * FROM raw.user_events LIMIT 10"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["columns"] == ["col1", "col2"]
        assert data["row_count"] == 1
        assert "elapsed_ms" in data

    def test_run_empty_query(self):
        response = client.post("/api/stats/query", json={"sql": ""})
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert "不能为空" in data["error"]

    def test_run_non_select_query(self):
        response = client.post(
            "/api/stats/query",
            json={"sql": "DROP TABLE users"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert "SELECT" in data["error"]

    def test_run_query_no_body(self):
        # endpoint 使用 body: dict 参数（非 Pydantic），空 dict 触发 SQL 为空错误
        response = client.post("/api/stats/query", json={})
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert "不能为空" in data["error"]


class TestCORSMiddleware:
    """测试 CORS 中间件。"""

    def test_cors_headers(self):
        response = client.options(
            "/",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code in (200, 405)  # OPTIONS may or may not be allowed


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
