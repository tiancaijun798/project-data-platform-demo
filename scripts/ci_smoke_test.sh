#!/bin/bash
# ============================================================
# CI Smoke Test — Run complete local CI check before pushing
# Usage: bash scripts/ci_smoke_test.sh [--skip-dbt] [--skip-ge]
#
# Checks:
#   1. Python lint (flake8 on src/ dags/ tests/)
#   2. DAG syntax check (py_compile)
#   3. dbt compile
#   4. pytest unit tests
#   5. Great Expectations validation
#   6. Pass/fail summary with colored output
# ============================================================
set -e

# ---- Colors ----
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# ---- Parse flags ----
SKIP_DBT=false
SKIP_GE=false
for arg in "$@"; do
    case "$arg" in
        --skip-dbt) SKIP_DBT=true ;;
        --skip-ge)  SKIP_GE=true ;;
        --help|-h)
            echo "Usage: bash scripts/ci_smoke_test.sh [--skip-dbt] [--skip-ge]"
            echo ""
            echo "Runs all local CI checks that would run in GitHub Actions."
            echo ""
            echo "Options:"
            echo "  --skip-dbt    Skip dbt compile check (requires PostgreSQL)"
            echo "  --skip-ge     Skip Great Expectations validation"
            echo "  --help, -h    Show this help message"
            exit 0
            ;;
    esac
done

# ---- Track results ----
PASS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0
RESULTS=()

pass_step() {
    echo -e "  ${GREEN}✅ PASS${NC} — $1"
    PASS_COUNT=$((PASS_COUNT + 1))
    RESULTS+=("PASS:$1")
}

fail_step() {
    echo -e "  ${RED}❌ FAIL${NC} — $1"
    if [ -n "$2" ]; then
        echo -e "     ${RED}$2${NC}"
    fi
    FAIL_COUNT=$((FAIL_COUNT + 1))
    RESULTS+=("FAIL:$1")
}

skip_step() {
    echo -e "  ${YELLOW}⚠️  SKIP${NC} — $1"
    if [ -n "$2" ]; then
        echo -e "     ${YELLOW}$2${NC}"
    fi
    SKIP_COUNT=$((SKIP_COUNT + 1))
    RESULTS+=("SKIP:$1")
}

# ---- Header ----
echo ""
echo -e "${BOLD}${CYAN}========================================${NC}"
echo -e "${BOLD}${CYAN}  Data Platform — Local CI Smoke Test${NC}"
echo -e "${BOLD}${CYAN}  $(date '+%Y-%m-%d %H:%M:%S')${NC}"
echo -e "${BOLD}${CYAN}========================================${NC}"
echo ""

# Detect project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
echo -e "Project root: ${CYAN}$PROJECT_ROOT${NC}"
echo ""

# ---- Check 1: Python version ----
echo -e "${BOLD}[1/6] Python Version Check${NC}"
PY_VERSION=$(python3 --version 2>&1 || python --version 2>&1 || echo "unknown")
echo "  Detected: $PY_VERSION"
if python3 -c "import sys; assert sys.version_info >= (3, 11)" 2>/dev/null; then
    pass_step "Python version >= 3.11 ($PY_VERSION)"
else
    fail_step "Python version >= 3.11 required" "Found: $PY_VERSION"
fi
echo ""

# ---- Check 2: Python Lint (flake8) ----
echo -e "${BOLD}[2/6] Python Lint — flake8${NC}"

# Install flake8 if not present
if ! python3 -m flake8 --version &>/dev/null 2>&1; then
    echo "  Installing flake8..."
    pip install flake8 pyflakes >/dev/null 2>&1 || true
fi

if python3 -m flake8 --version &>/dev/null 2>&1; then
    echo "  Running flake8 on src/ dags/ tests/ ..."

    # Run flake8, capture output
    FLAKE_OUTPUT=$(python3 -m flake8 \
        "$PROJECT_ROOT/src/" \
        "$PROJECT_ROOT/dags/" \
        "$PROJECT_ROOT/tests/" \
        --count --select=E9,F63,F7,F82 --show-source --statistics 2>&1 || true)

    if echo "$FLAKE_OUTPUT" | grep -q "E\|F"; then
        echo "$FLAKE_OUTPUT"
        fail_step "flake8 found issues" "Review the errors above"
    else
        echo "  No syntax/error issues found"
        pass_step "flake8 passed with 0 critical errors"
    fi
else
    skip_step "flake8 not installed" "Install with: pip install flake8"
fi
echo ""

# ---- Check 3: DAG Syntax Check ----
echo -e "${BOLD}[3/6] DAG Syntax Check — py_compile${NC}"

DAG_COUNT=0
DAG_PASS=0
DAG_FAIL=0

for dag_file in "$PROJECT_ROOT/dags/"*.py; do
    if [ ! -f "$dag_file" ]; then
        continue
    fi
    dag_name=$(basename "$dag_file")
    DAG_COUNT=$((DAG_COUNT + 1))

    if python3 -m py_compile "$dag_file" 2>&1; then
        echo "  ✅ $dag_name — syntax OK"
        DAG_PASS=$((DAG_PASS + 1))
    else
        echo "  ❌ $dag_name — SYNTAX ERROR"
        DAG_FAIL=$((DAG_FAIL + 1))
    fi
done

if [ "$DAG_COUNT" -eq 0 ]; then
    skip_step "No DAG files found in dags/"
elif [ "$DAG_FAIL" -eq 0 ]; then
    pass_step "All $DAG_PASS DAG(s) pass syntax check"
else
    fail_step "$DAG_FAIL/$DAG_COUNT DAG(s) have syntax errors"
fi
echo ""

# ---- Check 4: dbt Compile ----
echo -e "${BOLD}[4/6] dbt Compile${NC}"

if [ "$SKIP_DBT" = true ]; then
    skip_step "dbt compile skipped (--skip-dbt)"
else
    # Check if dbt is installed
    if command -v dbt &>/dev/null || python3 -m dbt --version &>/dev/null 2>&1; then
        echo "  Running dbt compile in dbt/ ..."
        cd "$PROJECT_ROOT/dbt"

        # Run dbt compile (allow it to fail if no DB connection)
        if dbt compile --profiles-dir . 2>&1; then
            pass_step "dbt compile succeeded"
        else
            # Check if failure is just DB connection issue
            fail_step "dbt compile failed" "Check DB connection or skip with --skip-dbt"
        fi
        cd "$PROJECT_ROOT"
    else
        skip_step "dbt not installed" "Install with: pip install dbt-postgres, or use --skip-dbt"
    fi
fi
echo ""

# ---- Check 5: pytest Unit Tests ----
echo -e "${BOLD}[5/6] pytest Unit Tests${NC}"

# Ensure pytest is installed
if ! python3 -m pytest --version &>/dev/null 2>&1; then
    pip install pytest >/dev/null 2>&1 || true
fi

if python3 -m pytest --version &>/dev/null 2>&1; then
    echo "  Running pytest on tests/ ..."

    TEST_OUTPUT=$(python3 -m pytest "$PROJECT_ROOT/tests/" -v --tb=short 2>&1)
    TEST_EXIT=$?

    echo "$TEST_OUTPUT"

    if [ "$TEST_EXIT" -eq 0 ]; then
        TESTS_PASSED=$(echo "$TEST_OUTPUT" | grep -oP '\d+(?= passed)' || echo "?")
        pass_step "pytest passed ($TESTS_PASSED tests)"
    else
        TESTS_FAILED=$(echo "$TEST_OUTPUT" | grep -oP '\d+(?= failed)' || echo "?")
        fail_step "pytest failed ($TESTS_FAILED failures)" "Review test output above"
    fi
else
    skip_step "pytest not installed" "Install with: pip install pytest"
fi
echo ""

# ---- Check 6: Great Expectations Validation ----
echo -e "${BOLD}[6/6] Great Expectations Validation${NC}"

if [ "$SKIP_GE" = true ]; then
    skip_step "GE validation skipped (--skip-ge)"
else
    # Check if great_expectations is installed
    if python3 -c "import great_expectations" &>/dev/null 2>&1; then
        SUITE_PATH="$PROJECT_ROOT/great_expectations/expectations/user_events_suite.json"

        if [ ! -f "$SUITE_PATH" ]; then
            fail_step "GE suite not found" "Expected at: $SUITE_PATH"
        else
            echo "  Running GE validation against user_events_suite..."

            GE_OUTPUT=$(python3 -c "
import json, uuid, sys
import pandas as pd
import great_expectations as gx

try:
    # Generate test data
    event_types = ['view', 'click', 'add_to_cart', 'purchase', 'search']
    devices = ['desktop', 'mobile', 'tablet']
    browsers = ['Chrome', 'Firefox', 'Safari', 'Edge']

    events = []
    for i in range(1, 101):
        events.append({
            'event_id': str(uuid.uuid4()),
            'user_id': f'U{str(i % 20).zfill(4)}',
            'event_type': event_types[i % len(event_types)],
            'product_id': f'P{str(i % 15).zfill(4)}',
            'timestamp': f'2026-07-{str((i % 28)+1).zfill(2)}T{str(i % 24).zfill(2)}:00:00+00:00',
            'event_ts': pd.Timestamp('2026-07-20') + pd.Timedelta(hours=i),
            'page': 'home',
            'referrer': 'google' if i % 3 != 0 else 'direct',
            'duration_ms': i * 500,
            'device': devices[i % len(devices)],
            'browser': browsers[i % len(browsers)],
            'processed_at': pd.Timestamp.now(),
            'processing_date': pd.Timestamp.now().date(),
        })

    df = pd.DataFrame(events)
    context = gx.get_context()

    # Load suite
    with open('$SUITE_PATH', 'r') as f:
        suite_dict = json.load(f)

    suite = context.add_expectation_suite(
        expectation_suite_name=suite_dict.get('expectation_suite_name', 'user_events_suite')
    )

    for exp in suite_dict.get('expectations', []):
        suite.add_expectation(
            gx.expectations.Expectation(
                expectation_type=exp['expectation_type'],
                kwargs=exp['kwargs'],
            )
        )

    validator = context.sources.pandas_default.read_dataframe(df)
    result = validator.validate(expectation_suite=suite)

    passed = sum(1 for r in result.results if r.success)
    failed = sum(1 for r in result.results if not r.success)

    print(f'Total: {len(result.results)}, Passed: {passed}, Failed: {failed}')
    for r in result.results:
        status = 'PASS' if r.success else 'FAIL'
        print(f'  [{status}] {r.expectation_config.expectation_type}')

    if not result.success:
        print('GE_CHECK_FAILED')
        sys.exit(1)
    else:
        print('GE_CHECK_PASSED')
except Exception as e:
    print(f'GE Error: {e}')
    sys.exit(1)
" 2>&1)
            GE_EXIT=$?

            echo "$GE_OUTPUT"

            if [ "$GE_EXIT" -eq 0 ]; then
                pass_step "GE validation passed"
            else
                fail_step "GE validation failed" "See output above for details"
            fi
        fi
    else
        skip_step "great_expectations not installed" "Install with: pip install great_expectations, or use --skip-ge"
    fi
fi
echo ""

# ---- Summary ----
echo -e "${BOLD}${CYAN}========================================${NC}"
echo -e "${BOLD}${CYAN}  CI Smoke Test Summary${NC}"
echo -e "${BOLD}${CYAN}========================================${NC}"
echo ""

for result in "${RESULTS[@]}"; do
    status="${result%%:*}"
    name="${result#*:}"
    case "$status" in
        PASS) echo -e "  ${GREEN}✅ ${name}${NC}" ;;
        FAIL) echo -e "  ${RED}❌ ${name}${NC}" ;;
        SKIP) echo -e "  ${YELLOW}⚠️  ${name}${NC}" ;;
    esac
done

echo ""
echo -e "  ${GREEN}Passed: $PASS_COUNT${NC}"
echo -e "  ${RED}Failed: $FAIL_COUNT${NC}"
echo -e "  ${YELLOW}Skipped: $SKIP_COUNT${NC}"
echo -e "${BOLD}${CYAN}========================================${NC}"

if [ "$FAIL_COUNT" -gt 0 ]; then
    echo -e "\n  ${RED}${BOLD}⚠️  CI smoke test FAILED — fix issues before pushing${NC}\n"
    exit 1
elif [ "$SKIP_COUNT" -gt 0 ]; then
    echo -e "\n  ${YELLOW}${BOLD}⚠️  CI smoke test PASSED with $SKIP_COUNT skipped check(s)${NC}\n"
    exit 0
else
    echo -e "\n  ${GREEN}${BOLD}✅ All checks passed — ready to push!${NC}\n"
    exit 0
fi
