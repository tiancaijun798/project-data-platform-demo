# Data Lineage Visualization

> End-to-end data lineage from Kafka ingestion to React frontend, with
> table-level and column-level traceability.

## Quick Start

```bash
# Generate lineage diagrams from the dbt manifest + project structure
cd lineage
python generate_lineage.py

# Open the HTML diagram in your browser
start lineage_output/lineage.html
```

## Output Files

| File | Description |
|------|-------------|
| `lineage_output/lineage.md` | Mermaid markdown diagram (renderable on GitHub/GitLab) |
| `lineage_output/lineage.html` | Self-contained HTML page with rendered Mermaid diagram |

## What Gets Generated

### 1. Full Pipeline Diagram (Mermaid)
A color-coded graph showing every stage of the data pipeline:

- **Ingestion (red)** -- Kafka producer -> JSONL files
- **Processing (orange)** -- PySpark transforms JSONL to Parquet
- **Storage (blue)** -- dbt models (raw views, clean tables) in PostgreSQL
- **Serving (green)** -- FastAPI endpoints that query PostgreSQL
- **Consumption (purple)** -- React frontend pages that call the API

### 2. Table-Level Lineage
Extracted from `dbt/target/manifest.json` (if available), showing exactly which dbt models depend on which sources and upstream models.

### 3. Column-Level Lineage
Trace key columns (`user_id`, `event_type`, `product_id`) through every transformation:
```
raw_data.user_events.user_id
  └── stg_user_events.user_id   (pass-through, NOT NULL)
        ├── dim_users.user_id     (aggregated: first/last seen)
        └── fct_user_events_daily  (COUNT DISTINCT → unique_users)
```

## Options

```bash
python generate_lineage.py --manifest /path/to/manifest.json
python generate_lineage.py --output-dir ./custom_output
```

## Fallback Behavior

If `dbt/target/manifest.json` is missing (e.g., dbt hasn't been run), the script
falls back to generating lineage from the known project structure. The diagram
will still be complete -- it just won't have dbt-manifest-verified edges.
