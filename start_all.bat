@echo off
title Data Platform - One Click Start
cd /d "%~dp0"

echo.
echo ========================================
echo   Data Platform - One Click Start
echo   %date% %time%
echo ========================================
echo.

echo [1/8] Starting core services...
cd docker
docker compose up -d >nul 2>&1
echo   [OK] PostgreSQL + Redis + FastAPI + Frontend

echo [2/8] Starting Kafka...
docker compose -f docker-compose-kafka.yml up -d >nul 2>&1
echo   [OK] Zookeeper + Kafka

echo [3/8] Starting Airflow...
docker compose -f docker-compose-airflow.yml up -d >nul 2>&1
echo   [OK] Airflow

echo [4/8] Starting Prometheus + Grafana...
cd ..\monitoring
docker compose -f docker-compose-monitoring.yml up -d >nul 2>&1
echo   [OK] Prometheus + Grafana

echo [5/8] Starting MLflow...
cd ..\mlflow
if exist docker-compose.mlflow.yml (
    docker compose -f docker-compose.mlflow.yml up -d >nul 2>&1
    echo   [OK] MLflow
) else (
    echo   [WARN] MLflow compose not found
)

echo [6/8] Starting Milvus...
cd ..\demo_vector
if exist docker-compose.vector.yml (
    docker compose -f docker-compose.vector.yml up -d etcd minio milvus >nul 2>&1
    echo   [OK] Milvus + etcd + MinIO
    rem Connect app to vector network
    docker network connect data-vector-net data-platform-app >nul 2>&1
) else (
    echo   [WARN] Vector compose not found
)

echo [7/8] Starting Neo4j...
cd ..\neo4j
if exist docker-compose.neo4j.yml (
    docker network create data-platform-net >nul 2>&1
    docker compose -f docker-compose.neo4j.yml up -d >nul 2>&1
    echo   [OK] Neo4j
) else (
    echo   [WARN] Neo4j compose not found
)

echo [8/8] Initializing data...
cd ..
echo    Waiting for services (30s)...
timeout /t 30 /nobreak >nul
echo    Initializing Neo4j graph...
python neo4j\init_graph.py --seed-file data\seed_events.jsonl --limit 500 >nul 2>&1
echo   [OK] Graph data initialized
echo    Building RAG knowledge base...
python rag_demo\build_knowledge_base.py --sample-size 500 --no-benchmark >nul 2>&1
echo   [OK] RAG knowledge base built

echo.
echo ========================================
echo   All services started!
echo ========================================
echo.
echo   Frontend:   http://localhost:3001
echo   FastAPI:    http://localhost:8000/docs
echo   Airflow:    http://localhost:8080  (airflow/airflow)
echo   Grafana:    http://localhost:3000  (admin/admin)
echo   MLflow:     http://localhost:3001/mlflow/  (经前端代理)
echo   Neo4j:      http://localhost:7474  (neo4j/changeme123)
echo   Prometheus: http://localhost:9090
echo.
echo   Commands:
echo     Trigger DAG:  docker exec docker-airflow-webserver-1 airflow dags trigger demo_pipeline
echo     Vector ingest: python demo_vector\embed.py --source parquet --input data\ --benchmark
echo     Graph query:   python neo4j\query_demo.py
echo     Run tests:     python -m pytest tests\ -v
echo.
echo   Opening browser...
start http://localhost:3001
echo.
pause
