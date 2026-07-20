# ============================================================
# project-data-platform-demo
# GitHub 推送脚本 - 双击或右键 PowerShell 执行
# ============================================================
# 前置条件:
#   1. 已在 https://github.com/new 创建空仓库 project-data-platform-demo
#   2. 已在 https://github.com/settings/tokens 创建 Personal Access Token
#      (勾选 repo + workflow 权限)
# ============================================================

$ErrorActionPreference = "Stop"

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  project-data-platform-demo" -ForegroundColor White
Write-Host "  GitHub 仓库推送脚本" -ForegroundColor White
Write-Host "========================================`n" -ForegroundColor Cyan

Set-Location "$PSScriptRoot"

# 检查 git 状态
Write-Host "[1/3] 检查仓库状态..." -ForegroundColor Yellow
$commit = git log --oneline -1 2>$null
if (-not $commit) {
    Write-Host "  ❌ 未找到 Git commit，请先初始化仓库" -ForegroundColor Red
    exit 1
}
Write-Host "  最新 commit: $commit" -ForegroundColor White

$branch = git branch --show-current
Write-Host "  当前分支: $branch" -ForegroundColor White

$remote = git remote get-url origin 2>$null
if (-not $remote) {
    Write-Host "  ❌ 未配置远端仓库" -ForegroundColor Red
    exit 1
}
Write-Host "  远端地址: $remote" -ForegroundColor White

# 提示用户确认
Write-Host "`n[2/3] 确认推送..." -ForegroundColor Yellow
Write-Host "  将推送至: https://github.com/tiancaijun798/project-data-platform-demo" -ForegroundColor White
Write-Host ""
Write-Host "  认证信息:" -ForegroundColor White
Write-Host "    Username: tiancaijun798" -ForegroundColor Gray
Write-Host "    Password: <粘贴你的 Personal Access Token>" -ForegroundColor Gray
Write-Host ""

$confirm = Read-Host "  确认推送？(输入 y 继续)"
if ($confirm -ne "y" -and $confirm -ne "Y") {
    Write-Host "  已取消推送" -ForegroundColor Yellow
    exit 0
}

# 执行推送
Write-Host "`n[3/3] 正在推送..." -ForegroundColor Yellow
git push -u origin main

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n========================================" -ForegroundColor Green
    Write-Host "  ✅ 推送成功！" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  验证地址: https://github.com/tiancaijun798/project-data-platform-demo" -ForegroundColor White
    Start-Process "https://github.com/tiancaijun798/project-data-platform-demo"
} else {
    Write-Host "`n  ❌ 推送失败，请检查:" -ForegroundColor Red
    Write-Host "    1. GitHub 空仓库是否已创建" -ForegroundColor White
    Write-Host "    2. Personal Access Token 是否正确生成" -ForegroundColor White
    Write-Host "    3. Token 权限是否勾选 repo" -ForegroundColor White
    Write-Host "`n  重新执行此脚本即可重试" -ForegroundColor Gray
}
