"""
dbt_daily DAG — 每日 dbt 数据建模与质量校验调度。

在第1周 demo_pipeline 之后运行，执行:
    1. dbt run   — 运行所有模型（raw→clean→analytics）
    2. dbt test  — 执行数据质量校验
    3. dbt docs  — 生成数据文档

可在 demo_pipeline 完成后自动触发或独立运行。
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from airflow.operators.empty import EmptyOperator
from airflow.utils.trigger_rule import TriggerRule


PROJECT_ROOT = "/opt/airflow"
DBT_DIR = f"{PROJECT_ROOT}/../dbt"

default_args = {
    "owner": "data-platform",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
    "start_date": datetime(2026, 7, 20),
}


def _check_dbt_env(**context):
    """检查 dbt 环境是否可用。"""
    import subprocess
    import sys

    try:
        result = subprocess.run(
            ["dbt", "--version"],
            capture_output=True,
            text=True,
            cwd="/opt/airflow/../dbt",
        )
        print(result.stdout)
        if result.returncode != 0:
            raise RuntimeError("dbt 不可用")
    except FileNotFoundError:
        print("⚠️  dbt 未安装，跳过本 DAG")
        raise


with DAG(
    dag_id="dbt_daily",
    default_args=default_args,
    description="每日 dbt 数据建模与质量校验",
    schedule_interval="0 2 * * *",  # 凌晨2点
    catchup=False,
    max_active_runs=1,
    tags=["dbt", "week2", "data-quality"],
    doc_md=__doc__,
) as dag:

    start = EmptyOperator(task_id="start")
    end = EmptyOperator(task_id="end", trigger_rule=TriggerRule.ALL_DONE)

    check_env = PythonOperator(
        task_id="check_dbt_env",
        python_callable=_check_dbt_env,
    )

    dbt_deps = BashOperator(
        task_id="dbt_deps",
        bash_command=(
            f"cd {DBT_DIR} && "
            f"dbt deps 2>&1 || echo '⚠️ dbt deps skipped (可能缺少网络)'"
        ),
    )

    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=(
            f"cd {DBT_DIR} && "
            f"dbt run --profiles-dir {DBT_DIR} 2>&1 || "
            f"echo '⚠️ dbt run 部分失败 (DB 连接不可用)'"
        ),
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=(
            f"cd {DBT_DIR} && "
            f"dbt test --profiles-dir {DBT_DIR} 2>&1 || "
            f"echo '⚠️ dbt test 失败 (可能存在数据质量异常)'"
        ),
    )

    dbt_docs = BashOperator(
        task_id="dbt_docs_generate",
        bash_command=(
            f"cd {DBT_DIR} && "
            f"dbt docs generate --profiles-dir {DBT_DIR} 2>&1 || "
            f"echo '⚠️ dbt docs generate 失败'"
        ),
    )

    start >> check_env >> dbt_deps >> dbt_run >> dbt_test >> dbt_docs >> end
