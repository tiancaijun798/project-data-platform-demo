#!/usr/bin/env python3
"""
Data Lineage Generator — parse dbt manifest (or fall back to known structure)
and output a Mermaid.js diagram showing the full data pipeline.

Sources (auto-detected):
    1. dbt  manifest.json  (dbt/target/manifest.json)  —  table-level  lineage
    2. Project structure fallback — full pipeline from Kafka → frontend

Output:
    lineage_output/lineage.md   —  Mermaid markdown diagram
    lineage_output/lineage.html —  self-contained rendered HTML page

Usage:
    python generate_lineage.py
    python generate_lineage.py --manifest ../dbt/target/manifest.json
    python generate_lineage.py --output-dir ./my_output
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional

# Fix Windows console encoding for emoji/Unicode output
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Pipeline stage colours (used in Mermaid style directives)
STAGE_COLORS = {
    "ingestion":   "#c0392b",  # red
    "processing":  "#e67e22",  # orange
    "storage":     "#2980b9",  # blue
    "serving":     "#27ae60",  # green
    "consumption": "#8e44ad",  # purple
}

STAGE_BG = {
    "ingestion":   "#fadbd8",
    "processing":  "#fdebd0",
    "storage":     "#d4e6f1",
    "serving":     "#d5f5e3",
    "consumption": "#e8daef",
}

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = PROJECT_ROOT / "dbt" / "target" / "manifest.json"
DEFAULT_OUTPUT = Path(__file__).resolve().parent / "lineage_output"


# ---------------------------------------------------------------------------
# 1.  Parse dbt manifest  (table-level lineage)
# ---------------------------------------------------------------------------
def parse_dbt_manifest(manifest_path: Path) -> Optional[dict]:
    """Extract table-level lineage from a dbt manifest.json.

    Returns a dict with keys 'nodes' (model info) and 'edges' (dependencies),
    or None if the manifest cannot be read / doesn't contain useful data.
    """
    if not manifest_path.exists():
        print(f"[INFO]  dbt manifest not found at {manifest_path} — "
              f"using project-structure fallback")
        return None

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[WARN]  Cannot parse manifest: {exc} — using fallback")
        return None

    nodes = raw.get("nodes", {})
    sources = raw.get("sources", {})
    parents = raw.get("parent_map", {})
    children = raw.get("child_map", {})

    dbt_nodes: dict[str, dict] = {}
    edges: list[tuple[str, str]] = []

    # Collect model + source nodes
    for uid, info in {**nodes, **sources}.items():
        res_type = info.get("resource_type", "")
        if res_type in ("model", "source"):
            dbt_nodes[uid] = {
                "name": info.get("name", uid),
                "schema": info.get("schema", info.get("schema_name", "")),
                "database": info.get("database", ""),
                "resource_type": res_type,
                "columns": {
                    col: meta.get("description", "")
                    for col, meta in info.get("columns", {}).items()
                },
                "description": info.get("description", ""),
                "depends_on": info.get("depends_on", {}).get("nodes", []),
            }

    # Build edges from depends_on
    for uid, info in dbt_nodes.items():
        for dep in info.get("depends_on", []):
            if dep in dbt_nodes:
                edges.append((dep, uid))

    if not dbt_nodes:
        return None

    return {"nodes": dbt_nodes, "edges": edges}


# ---------------------------------------------------------------------------
# 2.  Build full-pipeline lineage  (fallback / enrichment)
# ---------------------------------------------------------------------------
def build_full_lineage(dbt_info: Optional[dict]) -> str:
    """Return a complete Mermaid markdown diagram covering the entire
    pipeline from Kafka ingestion to the React frontend.
    """

    lines: list[str] = []

    # ── Header ──────────────────────────────────────────────────────
    lines.append("# Data Platform Demo — End-to-End Data Lineage")
    lines.append("")
    lines.append("> Color legend: "
                 "🔴 Ingestion  |  "
                 "🟠 Processing  |  "
                 "🔵 Storage  |  "
                 "🟢 Serving  |  "
                 "🟣 Consumption")
    lines.append("")

    # ── Mermaid diagram ─────────────────────────────────────────────
    lines.append("```mermaid")
    lines.append("graph LR")
    lines.append("")

    # ---- Style directives ----
    lines.append("  %% ── Style classes by pipeline stage ──")
    lines.append(f"  classDef ingestion fill:{STAGE_BG['ingestion']},"
                 f"stroke:{STAGE_COLORS['ingestion']},stroke-width:2px,"
                 f"color:#333")
    lines.append(f"  classDef processing fill:{STAGE_BG['processing']},"
                 f"stroke:{STAGE_COLORS['processing']},stroke-width:2px,"
                 f"color:#333")
    lines.append(f"  classDef storage fill:{STAGE_BG['storage']},"
                 f"stroke:{STAGE_COLORS['storage']},stroke-width:2px,"
                 f"color:#fff")
    lines.append(f"  classDef serving fill:{STAGE_BG['serving']},"
                 f"stroke:{STAGE_COLORS['serving']},stroke-width:2px,"
                 f"color:#333")
    lines.append(f"  classDef consumption fill:{STAGE_BG['consumption']},"
                 f"stroke:{STAGE_COLORS['consumption']},stroke-width:2px,"
                 f"color:#fff")
    lines.append("")

    # ---- 1. Ingestion subgraph ----
    lines.append("  subgraph INGEST [🔴 Ingestion Layer]")
    lines.append("    direction LR")
    lines.append("    KAFKA[Kafka<br/>Topic: user_events]")
    lines.append("    JSONL[Raw JSONL<br/>data/input.jsonl]")
    lines.append("    KAFKA -->|producer.py| JSONL")
    lines.append("  end")
    lines.append("")

    # ---- 2. Processing subgraph ----
    lines.append("  subgraph PROCESS [🟠 Processing Layer — PySpark]")
    lines.append("    direction LR")
    lines.append("    SPARK[PySpark<br/>process_data.py]")
    lines.append("    PARQUET[Parquet<br/>data/output_parquet/]")
    lines.append("    JSONL -->|read stream| SPARK")
    lines.append("    SPARK -->|write| PARQUET")
    lines.append("  end")
    lines.append("")

    # ---- 3. Storage subgraph (dbt) ----
    lines.append("  subgraph STORE [🔵 Storage Layer — dbt + PostgreSQL]")
    lines.append("    direction TB")
    lines.append("    STG[stg_user_events<br/>Raw View<br/>Schema: raw]")
    lines.append("    DIM_U[dim_users<br/>User Dimension<br/>Schema: clean]")
    lines.append("    DIM_P[dim_products<br/>Product Dimension<br/>Schema: clean]")
    lines.append("    FCT[fct_user_events_daily<br/>Daily Fact Table<br/>Schema: clean]")

    # Map dbt model names → short Mermaid node IDs
    MODEL_ID_MAP = {
        "stg_user_events":       "STG",
        "dim_users":             "DIM_U",
        "dim_products":          "DIM_P",
        "fct_user_events_daily": "FCT",
    }

    if dbt_info:
        # Real edges from dbt manifest (source → stg, stg → dims/fct)
        dbt_nodes = dbt_info["nodes"]
        dbt_edges = dbt_info["edges"]
        for src_uid, dst_uid in dbt_edges:
            src_name = dbt_nodes.get(src_uid, {}).get("name", src_uid)
            dst_name = dbt_nodes.get(dst_uid, {}).get("name", dst_uid)
            # Skip test edges and source→stg (expressed as PARQUET → STG)
            if src_name not in MODEL_ID_MAP or dst_name not in MODEL_ID_MAP:
                continue
            src_id = MODEL_ID_MAP[src_name]
            dst_id = MODEL_ID_MAP[dst_name]
            lines.append(f"    {src_id} --> {dst_id}")

    # Ensure hard-coded edges exist even if manifest edges were generated
    dbt_models_seen = set()
    if dbt_info:
        for _, dst_uid in dbt_info["edges"]:
            dst_name = dbt_info["nodes"].get(dst_uid, {}).get("name", "")
            if dst_name in MODEL_ID_MAP:
                dbt_models_seen.add(MODEL_ID_MAP[dst_name])
    for edge in [("STG", "DIM_U"), ("STG", "DIM_P"), ("STG", "FCT")]:
        # Only add hard-coded edge if the target was NOT already linked via manifest
        if edge[1] not in dbt_models_seen:
            lines.append(f"    {edge[0]} --> {edge[1]}")

    lines.append("    PARQUET -->|dbt source| STG")
    lines.append("  end")
    lines.append("")

    # ---- 4. Serving subgraph ----
    lines.append("  subgraph SERVE [🟢 Serving Layer — FastAPI]")
    lines.append("    direction TB")

    # Map frontend pages → API endpoints → dbt models
    lines.append("    API_DASH[/api/stats/dashboard]")
    lines.append("    API_TREND[/api/stats/sales-trend]")
    lines.append("    API_HEAT[/api/stats/hourly-heatmap]")
    lines.append("    API_USEG[/api/stats/user-segments]")
    lines.append("    API_TOPU[/api/stats/top-users]")
    lines.append("    API_PROD[/api/stats/product-rank]")
    lines.append("    API_CAT[/api/stats/category-share]")
    lines.append("    API_FUN[/api/stats/funnel]")
    lines.append("    API_QRY[/api/stats/query]")
    lines.append("    API_SVC[/api/stats/services]")

    lines.append("    STG --> API_DASH")
    lines.append("    STG --> API_TREND")
    lines.append("    STG --> API_HEAT")
    lines.append("    DIM_U --> API_USEG")
    lines.append("    DIM_U --> API_TOPU")
    lines.append("    DIM_P --> API_PROD")
    lines.append("    STG --> API_CAT")
    lines.append("    STG --> API_FUN")
    lines.append("    STG --> API_QRY")
    lines.append("  end")
    lines.append("")

    # ---- 5. Consumption subgraph ----
    lines.append("  subgraph CONSUME [🟣 Consumption Layer — React Frontend]")
    lines.append("    direction LR")
    lines.append("    PG_DASH[Dashboard.tsx<br/>销售大盘]")
    lines.append("    PG_USER[Users.tsx<br/>用户分群]")
    lines.append("    PG_PROD[Products.tsx<br/>商品排行]")
    lines.append("    PG_FUNN[Funnel.tsx<br/>转化漏斗]")
    lines.append("    PG_QRY[Query.tsx<br/>自定义查询]")
    lines.append("    PG_MON[Monitor.tsx<br/>服务监控]")

    lines.append("    API_DASH --> PG_DASH")
    lines.append("    API_TREND --> PG_DASH")
    lines.append("    API_HEAT --> PG_DASH")
    lines.append("    API_USEG --> PG_USER")
    lines.append("    API_TOPU --> PG_USER")
    lines.append("    API_PROD --> PG_PROD")
    lines.append("    API_CAT --> PG_PROD")
    lines.append("    API_FUN --> PG_FUNN")
    lines.append("    API_QRY --> PG_QRY")
    lines.append("    API_SVC --> PG_MON")
    lines.append("  end")
    lines.append("")

    # ---- Apply style classes ----
    lines.append("  class KAFKA,JSONL ingestion")
    lines.append("  class SPARK,PARQUET processing")
    lines.append("  class STG,DIM_U,DIM_P,FCT storage")
    lines.append("  class API_DASH,API_TREND,API_HEAT,API_USEG,API_TOPU,API_PROD,API_CAT,API_FUN,API_QRY,API_SVC serving")
    lines.append("  class PG_DASH,PG_USER,PG_PROD,PG_FUNN,PG_QRY,PG_MON consumption")

    lines.append("```")
    lines.append("")

    # ── Table-level lineage detail ───────────────────────────────────
    lines.append("## Table-Level Lineage (dbt)")
    lines.append("")

    if dbt_info:
        dbt_nodes = dbt_info["nodes"]
        model_nodes = {k: v for k, v in dbt_nodes.items()
                       if v["resource_type"] == "model"}
        source_nodes = {k: v for k, v in dbt_nodes.items()
                        if v["resource_type"] == "source"}

        lines.append("### Sources")
        lines.append("")
        lines.append("| Source | Schema | Description |")
        lines.append("|--------|--------|-------------|")
        for uid, n in source_nodes.items():
            desc = n.get("description", "-")
            lines.append(f"| {n['name']} | {n['schema']} | {desc} |")

        lines.append("")
        lines.append("### Models & Dependencies")
        lines.append("")
        lines.append("| Model | Schema | Materialization | Depends On |")
        lines.append("|-------|--------|-----------------|------------|")
        for uid, n in model_nodes.items():
            deps = [dbt_nodes[d]["name"] for d in n.get("depends_on", [])
                    if d in dbt_nodes and dbt_nodes[d]["resource_type"] == "model"]
            if not deps:
                deps = [
                    dbt_nodes[d]["name"] for d in n.get("depends_on", [])
                    if d in dbt_nodes
                ]
            lines.append(
                f"| {n['name']} | {n['schema']} | "
                f"{'table' if 'clean' in n['schema'] else 'view'} | "
                f"{', '.join(deps) if deps else 'source: user_events'} |"
            )
    else:
        lines.append("| Model | Schema | Materialization | Depends On |")
        lines.append("|-------|--------|-----------------|------------|")
        lines.append("| stg_user_events | raw | view | source: user_events |")
        lines.append("| dim_users | clean | table | stg_user_events |")
        lines.append("| dim_products | clean | table | stg_user_events |")
        lines.append("| fct_user_events_daily | clean | table | stg_user_events |")
    lines.append("")

    # ── Column-level lineage ─────────────────────────────────────────
    lines.append("## Column-Level Lineage (Key Columns)")
    lines.append("")
    lines.append("### `user_id`")
    lines.append("")
    lines.append("```")
    lines.append("raw_data.user_events.user_id")
    lines.append("  └── stg_user_events.user_id   (pass-through, NOT NULL)")
    lines.append("        ├── dim_users.user_id     (aggregated: first/last seen)")
    lines.append("        └── fct_user_events_daily  (COUNT DISTINCT → unique_users)")
    lines.append("```")
    lines.append("")
    lines.append("### `event_type`")
    lines.append("")
    lines.append("```")
    lines.append("raw_data.user_events.event_type")
    lines.append("  └── stg_user_events.event_type  (lowercased, accepted_values test)")
    lines.append("        └── fct_user_events_daily.event_type  (group-by key)")
    lines.append("```")
    lines.append("")
    lines.append("### `product_id`")
    lines.append("")
    lines.append("```")
    lines.append("raw_data.user_events.product_id")
    lines.append("  └── stg_user_events.product_id  (COALESCE → 'unknown')")
    lines.append("        └── dim_products.product_id  (group-by, conversion_rate calc)")
    lines.append("```")
    lines.append("")

    # ── Full pipeline text summary ───────────────────────────────────
    lines.append("## Pipeline Summary")
    lines.append("")
    lines.append("| # | Stage | Technology | Input | Output |")
    lines.append("|---|-------|-----------|-------|--------|")
    lines.append("| 1 | Ingestion | Kafka + Python `producer.py` | "
                 "Simulated user behavior | `data/input.jsonl` |")
    lines.append("| 2 | Processing | PySpark `process_data.py` | "
                 "`data/input.jsonl` | `data/output_parquet/*.parquet` |")
    lines.append("| 3 | Transformation | dbt (raw → clean) | "
                 "Parquet via `raw.user_events` source | "
                 "`dim_users`, `dim_products`, `fct_user_events_daily` |")
    lines.append("| 4 | Testing | Great Expectations + dbt tests | "
                 "All models | Test results (not_null, unique, accepted_values) |")
    lines.append("| 5 | Serving | FastAPI (10+ endpoints) | "
                 "PostgreSQL (raw + clean schemas) | JSON API responses |")
    lines.append("| 6 | Monitoring | Prometheus + Grafana | "
                 "FastAPI /metrics + PostgreSQL exporter | Dashboards |")
    lines.append("| 7 | Consumption | React + Ant Design | "
                 "FastAPI endpoints | 6 dashboard pages |")
    lines.append("")

    return "\n".join(lines)


def _mermaid_id(name: str) -> str:
    """Convert a human-readable name into a safe Mermaid node id."""
    return name.replace("-", "_").replace(".", "_").upper()


# ---------------------------------------------------------------------------
# 3.  Build self-contained HTML page
# ---------------------------------------------------------------------------
def build_html(mermaid_md: str) -> str:
    """Wrap a Mermaid markdown diagram in a standalone HTML page."""

    # Extract just the Mermaid code block content
    import re
    m = re.search(r"```mermaid\n(.*?)```", mermaid_md, re.DOTALL)
    mermaid_code = m.group(1).strip() if m else "graph LR\n  A-->B"

    # Escape backticks inside the Mermaid code for JS template literal
    escaped = mermaid_code.replace("\\", "\\\\").replace("`", "\\`")

    page_title = "Data Platform Demo — Data Lineage"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{page_title}</title>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto,
                 'Helvetica Neue', Arial, sans-serif;
    background: #f0f2f5;
    color: #333;
  }}
  .header {{
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
    color: #fff;
    padding: 32px 40px;
    text-align: center;
  }}
  .header h1 {{ font-size: 28px; font-weight: 600; margin-bottom: 8px; }}
  .header p  {{ font-size: 14px; opacity: 0.8; }}
  .legend {{
    display: flex; justify-content: center; gap: 24px;
    margin-top: 16px; flex-wrap: wrap;
  }}
  .legend-item {{ display: flex; align-items: center; gap: 6px; font-size: 13px; }}
  .legend-dot {{
    width: 14px; height: 14px; border-radius: 3px; border: 2px solid;
  }}
  .container {{
    max-width: 1400px; margin: 24px auto; padding: 0 24px;
  }}
  .diagram-card {{
    background: #fff; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,.08);
    padding: 32px; margin-bottom: 24px; overflow-x: auto;
  }}
  .diagram-card h2 {{
    font-size: 20px; margin-bottom: 20px; padding-bottom: 12px;
    border-bottom: 1px solid #f0f0f0; color: #1a1a2e;
  }}
  .mermaid {{ display: flex; justify-content: center; }}
  .table-card {{
    background: #fff; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,.08);
    padding: 32px; margin-bottom: 24px;
  }}
  table {{
    width: 100%; border-collapse: collapse; font-size: 14px;
  }}
  th {{ background: #f7f8fa; padding: 10px 14px; text-align: left;
        font-weight: 600; border-bottom: 2px solid #e8e8e8; }}
  td {{ padding: 10px 14px; border-bottom: 1px solid #f0f0f0; }}
  tr:hover td {{ background: #fafafa; }}
  .stage-tag {{
    display: inline-block; padding: 2px 10px; border-radius: 12px;
    font-size: 12px; font-weight: 600; color: #fff;
  }}
  .tag-ingest {{ background: {STAGE_COLORS['ingestion']}; }}
  .tag-process {{ background: {STAGE_COLORS['processing']}; }}
  .tag-storage {{ background: {STAGE_COLORS['storage']}; }}
  .tag-serving {{ background: {STAGE_COLORS['serving']}; }}
  .tag-consume {{ background: {STAGE_COLORS['consumption']}; }}
  pre {{ background: #1e1e2e; color: #cdd6f4; padding: 20px; border-radius: 8px;
        overflow-x: auto; font-size: 13px; line-height: 1.6; margin-top: 12px; }}
  footer {{
    text-align: center; padding: 24px; color: #999; font-size: 13px;
  }}
</style>
</head>
<body>

<div class="header">
  <h1>Data Platform Demo — End-to-End Data Lineage</h1>
  <p>From Kafka ingestion to React frontend — every transformation step documented</p>
  <div class="legend">
    <div class="legend-item">
      <span class="legend-dot" style="background:{STAGE_BG['ingestion']};border-color:{STAGE_COLORS['ingestion']}"></span>
      Ingestion (Kafka)
    </div>
    <div class="legend-item">
      <span class="legend-dot" style="background:{STAGE_BG['processing']};border-color:{STAGE_COLORS['processing']}"></span>
      Processing (PySpark)
    </div>
    <div class="legend-item">
      <span class="legend-dot" style="background:{STAGE_BG['storage']};border-color:{STAGE_COLORS['storage']}"></span>
      Storage (dbt + PostgreSQL)
    </div>
    <div class="legend-item">
      <span class="legend-dot" style="background:{STAGE_BG['serving']};border-color:{STAGE_COLORS['serving']}"></span>
      Serving (FastAPI)
    </div>
    <div class="legend-item">
      <span class="legend-dot" style="background:{STAGE_BG['consumption']};border-color:{STAGE_COLORS['consumption']}"></span>
      Consumption (React)
    </div>
  </div>
</div>

<div class="container">

  <div class="diagram-card">
    <h2>Full Pipeline Lineage Diagram</h2>
    <div class="mermaid">
{escaped}
    </div>
  </div>

  <div class="table-card">
    <h2>Column-Level Lineage — Key Columns</h2>

    <h3 style="margin-top:16px;color:#1a1a2e"><code>user_id</code></h3>
    <pre>raw_data.user_events.user_id
  └── stg_user_events.user_id   (pass-through, NOT NULL)
        ├── dim_users.user_id     (aggregated: first/last seen)
        └── fct_user_events_daily  (COUNT DISTINCT → unique_users)</pre>

    <h3 style="margin-top:24px;color:#1a1a2e"><code>event_type</code></h3>
    <pre>raw_data.user_events.event_type
  └── stg_user_events.event_type  (lowercased, accepted_values test)
        └── fct_user_events_daily.event_type  (group-by key)</pre>

    <h3 style="margin-top:24px;color:#1a1a2e"><code>product_id</code></h3>
    <pre>raw_data.user_events.product_id
  └── stg_user_events.product_id  (COALESCE → 'unknown')
        └── dim_products.product_id  (group-by, conversion_rate calc)</pre>
  </div>

  <div class="table-card">
    <h2>Pipeline Stage Summary</h2>
    <table>
      <thead>
        <tr><th>#</th><th>Stage</th><th>Technology</th><th>Input</th><th>Output</th></tr>
      </thead>
      <tbody>
        <tr>
          <td><span class="stage-tag tag-ingest">1</span></td>
          <td>Ingestion</td>
          <td>Kafka + producer.py</td>
          <td>Simulated user behavior</td>
          <td>data/input.jsonl</td>
        </tr>
        <tr>
          <td><span class="stage-tag tag-process">2</span></td>
          <td>Processing</td>
          <td>PySpark process_data.py</td>
          <td>data/input.jsonl</td>
          <td>data/output_parquet/*.parquet</td>
        </tr>
        <tr>
          <td><span class="stage-tag tag-storage">3</span></td>
          <td>Transformation</td>
          <td>dbt (raw → clean)</td>
          <td>Parquet via raw.user_events</td>
          <td>dim_users, dim_products, fct_user_events_daily</td>
        </tr>
        <tr>
          <td><span class="stage-tag tag-storage">4</span></td>
          <td>Testing</td>
          <td>Great Expectations + dbt tests</td>
          <td>All models</td>
          <td>Test results</td>
        </tr>
        <tr>
          <td><span class="stage-tag tag-serving">5</span></td>
          <td>Serving</td>
          <td>FastAPI</td>
          <td>PostgreSQL</td>
          <td>JSON API (10+ endpoints)</td>
        </tr>
        <tr>
          <td><span class="stage-tag tag-serving">6</span></td>
          <td>Monitoring</td>
          <td>Prometheus + Grafana</td>
          <td>/metrics endpoint</td>
          <td>Dashboards</td>
        </tr>
        <tr>
          <td><span class="stage-tag tag-consume">7</span></td>
          <td>Consumption</td>
          <td>React + Ant Design</td>
          <td>FastAPI endpoints</td>
          <td>6 dashboard pages</td>
        </tr>
      </tbody>
    </table>
  </div>

</div>

<footer>
  Data Platform Demo &mdash; Generated <span id="gen-time"></span>
</footer>

<script>
  mermaid.initialize({{
    startOnLoad: true,
    theme: 'base',
    themeVariables: {{
      primaryColor: '#d4e6f1',
      primaryBorderColor: '#2980b9',
      primaryTextColor: '#333',
      lineColor: '#999',
      fontSize: '13px',
    }},
    flowchart: {{ useMaxWidth: true, htmlLabels: true, curve: 'basis' }},
  }});
  document.getElementById('gen-time').textContent = new Date().toISOString().slice(0, 19);
</script>

</body>
</html>
"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Generate data lineage diagrams from dbt manifest"
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="Path to dbt manifest.json (default: dbt/target/manifest.json)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Output directory (default: lineage/lineage_output)",
    )
    args = parser.parse_args()

    # 1. Try parsing dbt manifest for table-level lineage
    dbt_info = parse_dbt_manifest(args.manifest)

    # 2. Build full Mermaid markdown
    mermaid_md = build_full_lineage(dbt_info)

    # 3. Build self-contained HTML
    html = build_html(mermaid_md)

    # 4. Write outputs
    os.makedirs(args.output_dir, exist_ok=True)

    md_path = args.output_dir / "lineage.md"
    html_path = args.output_dir / "lineage.html"

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(mermaid_md)
    print(f"[OK]  Mermaid markdown → {md_path}")

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[OK]  Self-contained HTML → {html_path}")

    print(f"\n[DONE]  Lineage generation complete. "
          f"Open {html_path} in a browser to view the diagram.")


if __name__ == "__main__":
    main()
