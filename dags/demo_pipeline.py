"""
demo_pipeline DAG — 第1周核心交付：Kafka → PySpark 端到端数据流水线。

流水线步骤:
    1. generate_events  — 执行 Kafka Producer 生成模拟事件
    2. consume_events   — 执行 Kafka Consumer 落地 JSONL
    3. spark_process    — 执行 PySpark JSONL → Parquet 清洗转换
    4. validate_output  — 校验输出 Parquet 文件完整性

调度: 每日 UTC 0 点自动触发 + 支持手动触发
"""

import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.empty import EmptyOperator
from airflow.utils.trigger_rule import TriggerRule


# ---- 配置常量 ----
PROJECT_ROOT = os.environ.get("PROJECT_ROOT", "/opt/airflow")
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
KAFKA_DIR = os.path.join(SRC_DIR, "kafka_scripts")
SPARK_DIR = os.path.join(SRC_DIR, "spark")

# Kafka & SSH 配置（可通过 Airflow Variables 覆盖）
KAFKA_BOOTSTRAP = "kafka:29092"  # Docker 内部网络地址
KAFKA_TOPIC = "events"
EVENT_COUNT = 100

# PySpark 执行模式: "local" 在容器内本地执行 / "remote" 通过 SSH 到 VM
SPARK_MODE = os.environ.get("SPARK_MODE", "local")

# Ubuntu VM SSH 配置（仅 SPARK_MODE=remote 时使用）
VM_HOST = os.environ.get("VM_HOST", "")
VM_PORT = os.environ.get("VM_PORT", "2222")
VM_USER = os.environ.get("VM_USER", "")
VM_PASS = os.environ.get("VM_PASS", "")

# ---- 默认参数 ----
default_args = {
    "owner": "data-platform",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=2),
    "start_date": datetime(2026, 7, 20),
}


# ---- 可复用 Python 回调 ----
def _print_context(**context):
    """打印 DAG 运行上下文信息，方便调试。"""
    ds = context["ds"]
    ts = context["ts"]
    dag_id = context["dag"].dag_id
    run_id = context["run_id"]
    print(f"DAG: {dag_id} | Run: {run_id} | ds={ds} | ts={ts}")


def _check_data_file(**context) -> str:
    """校验 data/input.jsonl 是否生成成功，决定下一步分支。"""
    import os

    jsonl_path = os.path.join(PROJECT_ROOT, "data", "input.jsonl")
    if os.path.exists(jsonl_path) and os.path.getsize(jsonl_path) > 0:
        print(f"✅ JSONL 文件存在: {jsonl_path}")
        return "spark_process"
    else:
        print(f"❌ JSONL 文件缺失或为空: {jsonl_path}")
        return "skip_spark"


def _validate_parquet(**context):
    """校验 Parquet 输出是否成功生成。"""
    import os

    parquet_dir = os.path.join(PROJECT_ROOT, "data", "output_parquet")
    if not os.path.exists(parquet_dir):
        raise FileNotFoundError(f"Parquet 输出目录不存在: {parquet_dir}")

    # 统计文件
    file_count = 0
    total_size = 0
    for root, dirs, files in os.walk(parquet_dir):
        for f in files:
            fp = os.path.join(root, f)
            total_size += os.path.getsize(fp)
            file_count += 1

    if file_count == 0:
        raise ValueError("Parquet 目录为空，无意输出文件！")

    size_mb = total_size / (1024 * 1024)
    print(f"✅ Parquet 校验通过: {file_count} 文件, {size_mb:.2f} MB")
    return {"file_count": file_count, "size_mb": round(size_mb, 2)}


# ========================================
#  DAG 定义
# ========================================
with DAG(
    dag_id="demo_pipeline",
    default_args=default_args,
    description="第1周核心流水线: Kafka → PySpark → Parquet 端到端处理",
    schedule_interval="@daily",
    catchup=False,
    max_active_runs=1,
    tags=["demo", "week1", "pipeline"],
    doc_md=__doc__,
) as dag:

    # ---- 起始 / 结束哨兵 ----
    start = EmptyOperator(task_id="start")
    end = EmptyOperator(task_id="end", trigger_rule=TriggerRule.ALL_DONE)

    # ---- Task 1: 打印上下文 ----
    print_context = PythonOperator(
        task_id="print_context",
        python_callable=_print_context,
    )

    # ---- Task 2: 生成模拟事件 (Kafka Producer) ----
    generate_events = BashOperator(
        task_id="generate_events",
        bash_command=(
            f"echo '=== Kafka Producer Start ===' && "
            f"python {KAFKA_DIR}/producer.py "
            f"--bootstrap-server {KAFKA_BOOTSTRAP} "
            f"--topic {KAFKA_TOPIC} "
            f"--count {EVENT_COUNT} "
            f"--output-jsonl {DATA_DIR}/input.jsonl"
        ),
        env={
            "PYTHONPATH": f"{SRC_DIR}:$PYTHONPATH",
            "PYTHONUNBUFFERED": "1",
        },
    )

    # ---- Task 3: 消费事件落地 JSONL (Kafka Consumer) ----
    consume_events = BashOperator(
        task_id="consume_events",
        bash_command=(
            f"echo '=== Kafka Consumer Start ===' && "
            f"python {KAFKA_DIR}/consumer.py "
            f"--bootstrap-server {KAFKA_BOOTSTRAP} "
            f"--topic {KAFKA_TOPIC} "
            f"--output {DATA_DIR}/input.jsonl "
            f"--max-messages {EVENT_COUNT}"
        ),
        env={
            "PYTHONPATH": f"{SRC_DIR}:$PYTHONPATH",
            "PYTHONUNBUFFERED": "1",
        },
    )

    # ---- Task 4: 校验数据文件 → 决定分支 ----
    check_data = BranchPythonOperator(
        task_id="check_data",
        python_callable=_check_data_file,
    )

    # ---- Task 5: PySpark 清洗转换 (根据 SPARK_MODE 选择执行方式) ----
    spark_process = BashOperator(
        task_id="spark_process",
        bash_command=(
            f"echo '=== PySpark Process Start (mode: {SPARK_MODE}) ===' && "
            f"if [ \"{SPARK_MODE}\" = \"remote\" ] && [ -n \"{VM_HOST}\" ] && [ -n \"{VM_USER}\" ]; then "
            f"  echo '  -> 远端执行: {VM_USER}@{VM_HOST}' && "
            f"  sshpass -p '{VM_PASS}' ssh -o StrictHostKeyChecking=no "
            f"  -p {VM_PORT} {VM_USER}@{VM_HOST} "
            f"  'cd ~/project-data-platform-demo && "
            f"  python src/spark/process_data.py "
            f"  --input data/input.jsonl --output data/output_parquet' "
            f"  || echo '⚠️  远端执行失败'; "
            f"else "
            f"  echo '  -> 本地容器内执行' && "
            f"  PYTHONUTF8=1 python {SPARK_DIR}/process_data.py "
            f"  --input {DATA_DIR}/input.jsonl --output {DATA_DIR}/output_parquet; "
            f"fi"
        ),
        env={
            "PYTHONUNBUFFERED": "1",
        },
    )

    # ---- Task 5b: 跳过 PySpark（数据文件缺失时的分支） ----
    skip_spark = EmptyOperator(task_id="skip_spark")

    # ---- Task 6: 校验 Parquet 输出 ----
    validate_output = PythonOperator(
        task_id="validate_output",
        python_callable=_validate_parquet,
    )

    # ---- 定义任务依赖 ----
    start >> print_context >> generate_events >> consume_events
    consume_events >> check_data
    check_data >> spark_process >> validate_output >> end
    check_data >> skip_spark >> end
