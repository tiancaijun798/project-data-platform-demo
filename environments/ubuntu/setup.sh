#!/bin/bash
# ============================================================
# Ubuntu 24.04 虚拟机一键环境配置（精简版）
# 用法: bash environments/ubuntu/setup.sh
# ============================================================
set -e
echo "=============================="
echo "  Ubuntu VM 环境一键配置"
echo "=============================="

# [1] apt 清华源
echo "[1/5] apt 清华镜像源..."
sudo sed -i 's|http://.*archive.ubuntu.com|https://mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list.d/ubuntu.sources 2>/dev/null || true
sudo sed -i 's|http://.*security.ubuntu.com|https://mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list.d/ubuntu.sources 2>/dev/null || true
sudo apt update -qq && echo "  ✅ apt 清华源完成"

# [2] Docker CE + Compose
echo "[2/5] Docker CE..."
sudo apt install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://mirrors.tuna.tsinghua.edu.cn/docker-ce/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://mirrors.tuna.tsinghua.edu.cn/docker-ce/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update -qq
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker $USER
echo "  ✅ Docker CE: $(docker --version)"

# [3] Git
echo "[3/5] Git..."
sudo apt install -y git
echo "  ✅ Git: $(git --version)"

# [4] kubectl
echo "[4/5] kubectl..."
KUBE_LATEST=$(curl -sL https://mirrors.huaweicloud.com/kubernetes/kubectl/stable.txt)
curl -LO "https://mirrors.huaweicloud.com/kubernetes/kubectl/${KUBE_LATEST}/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl && rm -f kubectl
echo "  ✅ kubectl installed"

# [5] Helm
echo "[5/5] Helm..."
curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
echo "  ✅ Helm: $(helm version --short)"

# 校验
echo ""
echo "=============================="
echo "  VM 环境校验结果"
echo "=============================="
echo "Docker:  $(docker --version)"
echo "Git:     $(git --version)"
echo "kubectl: $(kubectl version --client --short 2>/dev/null || kubectl version --client | head -1)"
echo "Helm:    $(helm version --short)"
echo "=============================="
