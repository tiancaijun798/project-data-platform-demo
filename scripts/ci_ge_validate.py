#!/usr/bin/env python3
"""
CI Great Expectations validation (used by .github/workflows/ci.yml → ge-validation job).

Runs the committed ExpectationSuite (great_expectations/expectations/user_events_suite.json)
against a synthetic events DataFrame and fails (exit 1) if any expectation does not pass.

Design notes:
- Uses GE's *ephemeral* Data Context (gx.get_context(mode="ephemeral")) so the job does NOT
  depend on the (potentially legacy) great_expectations/great_expectations.yml project config.
- Expectations are constructed dynamically from the suite JSON by mapping snake_case
  expectation_type → CamelCase Expectation class (GE 1.x registry).
- The generated demo rows are intentionally conforming: every expectation in the suite
  must PASS for CI to go green (that is the demo's data-quality story).
"""

import json
import re
import sys
import uuid

import pandas as pd
import great_expectations as gx

SUITE_PATH = "great_expectations/expectations/user_events_suite.json"

# Columns in the exact order the suite's expect_table_columns_to_match_ordered_list requires.
COLUMNS = [
    "event_id", "user_id", "event_type", "product_id", "timestamp", "event_ts",
    "page", "referrer", "duration_ms", "device", "browser",
    "processed_at", "processing_date",
]

EVENT_TYPES = ["click", "view", "add_to_cart", "purchase", "search", "logout"]
DEVICES = ["desktop", "mobile", "tablet"]
BROWSERS = ["Chrome", "Firefox", "Safari", "Edge"]


def expectation_class(expectation_type: str):
    """snake_case 'expect_foo_bar' -> GE ExpectFooBar class."""
    body = expectation_type[len("expect_"):]
    return getattr(gx.expectations, "Expect" + "".join(p.capitalize() for p in body.split("_")))


def load_suite():
    with open(SUITE_PATH, encoding="utf-8") as f:
        return json.load(f)


def make_events(n: int = 100) -> pd.DataFrame:
    rows = []
    for i in range(n):
        rows.append({
            "event_id": str(uuid.uuid4()),
            "user_id": f"U{i % 20:04d}",
            "event_type": EVENT_TYPES[i % len(EVENT_TYPES)],
            "product_id": f"P{i % 15:04d}",
            "timestamp": f"2026-07-{(i % 28) + 1:02d}T{i % 24:02d}:00:00+00:00",
            "event_ts": pd.Timestamp("2026-07-20") + pd.Timedelta(hours=i),
            "page": "home",
            "referrer": "google" if i % 3 != 0 else "direct",
            # Keep min(duration_ms) within [0,100] and max within [0,300000] (see suite rules)
            "duration_ms": 0 if i == 0 else i * 500,
            "device": DEVICES[i % len(DEVICES)],
            "browser": BROWSERS[i % len(BROWSERS)],
            "processed_at": pd.Timestamp.now(),
            "processing_date": pd.Timestamp.now().date(),
        })
    return pd.DataFrame(rows, columns=COLUMNS)


def main() -> int:
    suite_dict = load_suite()

    # 1) ephemeral context → no project yml required
    context = gx.get_context(mode="ephemeral")

    # 2) build the ExpectationSuite from the committed JSON
    suite = context.suites.add(
        gx.core.ExpectationSuite(name=suite_dict["expectation_suite_name"])
    )
    for exp in suite_dict["expectations"]:
        cls = expectation_class(exp["expectation_type"])
        suite.add_expectation(cls(**exp["kwargs"]))

    # 3) validate a conforming events DataFrame
    df = make_events()
    batch = context.data_sources.pandas_default.read_dataframe(df)
    result = batch.validate(suite)

    print()
    print("=" * 60)
    print("  Great Expectations Validation Report")
    print("=" * 60)
    print(f"  Expectation suite : {suite.name}")
    print(f"  Rows validated    : {len(df)}")
    print(f"  Success           : {result.success}")
    print(f"    total           : {len(result.results)}")
    print(f"    passed          : {sum(1 for r in result.results if r.success)}")
    print(f"    failed          : {sum(1 for r in result.results if not r.success)}")
    print()
    for r in result.results:
        status = "PASS" if r.success else "FAIL"
        print(f"  [{status}] {r.expectation_config.type}")
        if not r.success:
            print(f"        -> {r.result}")
    print("=" * 60)

    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())
