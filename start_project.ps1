# 全栈数据平台 - 一键启动 (PowerShell)
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  全栈数据平台 - 一键启动" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# [1/4] 基础服务
Write-Host "[1/4] 启动基础服务 (PostgreSQL + Redis + API)..." -ForegroundColor Yellow
docker compose -f "$ROOT\docker\docker-compose.yml" up -d
Write-Host ""

# [2/4] 消息队列
Write-Host "[2/4] 启动消息队列 (Kafka + Zookeeper)..." -ForegroundColor Yellow
docker compose -f "$ROOT\docker\docker-compose-kafka.yml" up -d
Write-Host ""

# [3/4] 调度服务
Write-Host "[3/4] 启动调度服务 (Airflow)..." -ForegroundColor Yellow
docker compose -f "$ROOT\docker\docker-compose-airflow.yml" up -d
Write-Host ""

# [4/4] 监控服务
Write-Host "[4/4] 启动监控服务 (Prometheus + Grafana)..." -ForegroundColor Yellow
docker compose -f "$ROOT\monitoring\docker-compose-monitoring.yml" up -d
Write-Host ""

Write-Host "========================================" -ForegroundColor Green
Write-Host "  全部服务已启动！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  数据产品:     http://localhost:5173"
Write-Host "  Airflow:      http://localhost:8080  (airflow / airflow)"
Write-Host "  Grafana:      http://localhost:3000  (admin / admin)"
Write-Host "  FastAPI:      http://localhost:8000/docs"
Write-Host "  Prometheus:   http://localhost:9090"
Write-Host ""
Write-Host "正在启动前端开发服务器..." -ForegroundColor Yellow
Write-Host ""

Start-Process "http://localhost:5173"
Set-Location "$ROOT\frontend"
npm run dev
