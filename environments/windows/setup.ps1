# ============================================================
# Windows 宿主机一键修复脚本
# 执行: 以管理员身份打开 PowerShell，粘贴执行
# ============================================================

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Windows 宿主机环境一键修复脚本"
Write-Host "========================================" -ForegroundColor Cyan

# --- [1] Git 全局配置 ---
Write-Host "`n[1/4] 配置 Git 全局用户" -ForegroundColor Yellow
$git_user = Read-Host "  输入 GitHub 用户名"
$git_email = Read-Host "  输入 GitHub 邮箱"
git config --global user.name $git_user
git config --global user.email $git_email
Write-Host "  ✅ Git 全局配置完成" -ForegroundColor Green

# --- [2] Conda 清华镜像源 ---
Write-Host "`n[2/4] 配置 Conda 清华镜像源" -ForegroundColor Yellow
conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main/
conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/free/
conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud/conda-forge/
conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud/pytorch/
conda config --set show_channel_urls yes
conda clean -i -y
Write-Host "  ✅ Conda 清华镜像源配置完成" -ForegroundColor Green

# --- [3] Helm 安装 ---
Write-Host "`n[3/4] 安装 Helm" -ForegroundColor Yellow
$helmUrl = "https://mirrors.huaweicloud.com/helm/v3.19.3/helm-v3.19.3-windows-amd64.zip"
$helmZip = "$env:TEMP\helm.zip"
$helmDir = "$env:TEMP\helm_extract"
Invoke-WebRequest -Uri $helmUrl -OutFile $helmZip -UseBasicParsing
Expand-Archive -Path $helmZip -DestinationPath $helmDir -Force
$destDir = "$env:USERPROFILE\bin"
New-Item -ItemType Directory -Path $destDir -Force | Out-Null
Copy-Item "$helmDir\windows-amd64\helm.exe" "$destDir\helm.exe" -Force
Remove-Item $helmZip -Force; Remove-Item $helmDir -Recurse -Force
$env:Path = "$destDir;$env:Path"
[Environment]::SetEnvironmentVariable("Path", "$destDir;" + [Environment]::GetEnvironmentVariable("Path", "User"), "User")
Write-Host "  ✅ Helm 安装完成" -ForegroundColor Green

# --- [4] .kube 目录 ---
Write-Host "`n[4/4] 初始化 kubeconfig 目录" -ForegroundColor Yellow
$kubeDir = "$env:USERPROFILE\.kube"
New-Item -ItemType Directory -Path $kubeDir -Force | Out-Null
Write-Host "  ✅ ~/.kube 目录已创建" -ForegroundColor Green

# --- 校验 ---
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  最终校验结果" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Git:       $(git --version)"
Write-Host "Python:    $(python --version)"
Write-Host "Conda:     $(conda --version)"
Write-Host "pip:       $(pip -V)"
Write-Host "Docker:    $(docker --version)"
Write-Host "Compose:   $(docker compose version)"
Write-Host "kubectl:   $(kubectl version --client --short 2>$null)"
Write-Host "Helm:      $(helm version --short 2>$null)"
Write-Host "========================================" -ForegroundColor Green
Write-Host "  ✅ Windows 宿主机环境修复完成！" -ForegroundColor Green
