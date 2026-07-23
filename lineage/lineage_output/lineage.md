# Data Platform Demo — End-to-End Data Lineage

> Color legend: 🔴 Ingestion  |  🟠 Processing  |  🔵 Storage  |  🟢 Serving  |  🟣 Consumption

```mermaid
graph LR

  %% ── Style classes by pipeline stage ──
  classDef ingestion fill:#fadbd8,stroke:#c0392b,stroke-width:2px,color:#333
  classDef processing fill:#fdebd0,stroke:#e67e22,stroke-width:2px,color:#333
  classDef storage fill:#d4e6f1,stroke:#2980b9,stroke-width:2px,color:#fff
  classDef serving fill:#d5f5e3,stroke:#27ae60,stroke-width:2px,color:#333
  classDef consumption fill:#e8daef,stroke:#8e44ad,stroke-width:2px,color:#fff

  subgraph INGEST [🔴 Ingestion Layer]
    direction LR
    KAFKA[Kafka<br/>Topic: user_events]
    JSONL[Raw JSONL<br/>data/input.jsonl]
    KAFKA -->|producer.py| JSONL
  end

  subgraph PROCESS [🟠 Processing Layer — PySpark]
    direction LR
    SPARK[PySpark<br/>process_data.py]
    PARQUET[Parquet<br/>data/output_parquet/]
    JSONL -->|read stream| SPARK
    SPARK -->|write| PARQUET
  end

  subgraph STORE [🔵 Storage Layer — dbt + PostgreSQL]
    direction TB
    STG[stg_user_events<br/>Raw View<br/>Schema: raw]
    DIM_U[dim_users<br/>User Dimension<br/>Schema: clean]
    DIM_P[dim_products<br/>Product Dimension<br/>Schema: clean]
    FCT[fct_user_events_daily<br/>Daily Fact Table<br/>Schema: clean]
    STG --> DIM_P
    STG --> DIM_U
    STG --> FCT
    PARQUET -->|dbt source| STG
  end

  subgraph SERVE [🟢 Serving Layer — FastAPI]
    direction TB
    API_DASH[/api/stats/dashboard]
    API_TREND[/api/stats/sales-trend]
    API_HEAT[/api/stats/hourly-heatmap]
    API_USEG[/api/stats/user-segments]
    API_TOPU[/api/stats/top-users]
    API_PROD[/api/stats/product-rank]
    API_CAT[/api/stats/category-share]
    API_FUN[/api/stats/funnel]
    API_QRY[/api/stats/query]
    API_SVC[/api/stats/services]
    STG --> API_DASH
    STG --> API_TREND
    STG --> API_HEAT
    DIM_U --> API_USEG
    DIM_U --> API_TOPU
    DIM_P --> API_PROD
    STG --> API_CAT
    STG --> API_FUN
    STG --> API_QRY
  end

  subgraph CONSUME [🟣 Consumption Layer — React Frontend]
    direction LR
    PG_DASH[Dashboard.tsx<br/>销售大盘]
    PG_USER[Users.tsx<br/>用户分群]
    PG_PROD[Products.tsx<br/>商品排行]
    PG_FUNN[Funnel.tsx<br/>转化漏斗]
    PG_QRY[Query.tsx<br/>自定义查询]
    PG_MON[Monitor.tsx<br/>服务监控]
    API_DASH --> PG_DASH
    API_TREND --> PG_DASH
    API_HEAT --> PG_DASH
    API_USEG --> PG_USER
    API_TOPU --> PG_USER
    API_PROD --> PG_PROD
    API_CAT --> PG_PROD
    API_FUN --> PG_FUNN
    API_QRY --> PG_QRY
    API_SVC --> PG_MON
  end

  class KAFKA,JSONL ingestion
  class SPARK,PARQUET processing
  class STG,DIM_U,DIM_P,FCT storage
  class API_DASH,API_TREND,API_HEAT,API_USEG,API_TOPU,API_PROD,API_CAT,API_FUN,API_QRY,API_SVC serving
  class PG_DASH,PG_USER,PG_PROD,PG_FUNN,PG_QRY,PG_MON consumption
```

## Table-Level Lineage (dbt)

### Sources

| Source | Schema | Description |
|--------|--------|-------------|
| user_events | raw | 用户行为事件原始表 |

### Models & Dependencies

| Model | Schema | Materialization | Depends On |
|-------|--------|-----------------|------------|
| dim_products | public_clean | table | stg_user_events |
| dim_users | public_clean | table | stg_user_events |
| stg_user_events | public_raw | view | user_events |
| fct_user_events_daily | public_clean | table | stg_user_events |

## Column-Level Lineage (Key Columns)

### `user_id`

```
raw_data.user_events.user_id
  └── stg_user_events.user_id   (pass-through, NOT NULL)
        ├── dim_users.user_id     (aggregated: first/last seen)
        └── fct_user_events_daily  (COUNT DISTINCT → unique_users)
```

### `event_type`

```
raw_data.user_events.event_type
  └── stg_user_events.event_type  (lowercased, accepted_values test)
        └── fct_user_events_daily.event_type  (group-by key)
```

### `product_id`

```
raw_data.user_events.product_id
  └── stg_user_events.product_id  (COALESCE → 'unknown')
        └── dim_products.product_id  (group-by, conversion_rate calc)
```

## Pipeline Summary

| # | Stage | Technology | Input | Output |
|---|-------|-----------|-------|--------|
| 1 | Ingestion | Kafka + Python `producer.py` | Simulated user behavior | `data/input.jsonl` |
| 2 | Processing | PySpark `process_data.py` | `data/input.jsonl` | `data/output_parquet/*.parquet` |
| 3 | Transformation | dbt (raw → clean) | Parquet via `raw.user_events` source | `dim_users`, `dim_products`, `fct_user_events_daily` |
| 4 | Testing | Great Expectations + dbt tests | All models | Test results (not_null, unique, accepted_values) |
| 5 | Serving | FastAPI (10+ endpoints) | PostgreSQL (raw + clean schemas) | JSON API responses |
| 6 | Monitoring | Prometheus + Grafana | FastAPI /metrics + PostgreSQL exporter | Dashboards |
| 7 | Consumption | React + Ant Design | FastAPI endpoints | 6 dashboard pages |
