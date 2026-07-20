# project-data-platform-demo

> 🏗️ 全栈数据平台演示项目  
> 混合开发环境：Windows 11 + VirtualBox Ubuntu 24.04 + Docker Desktop + K3s(K8s)

---

## 📋 技术栈

| 层级 | 技术 | 版本 |
|------|------|------|
| **宿主机** | Windows 11 | 24H2 |
| **虚拟化** | VirtualBox | 7.2.6 |
| **虚拟机** | Ubuntu | 24.04 LTS (64-bit, 8GB RAM) |
| **容器运行时** | Docker Desktop / Docker CE | 29.4.x |
| **容器编排** | Docker Compose / K3s (Kubernetes) | v5.x / v1.32.x |
| **CLI 工具** | Git, kubectl, Helm | 2.54 / 1.34 / 3.19 |
| **开发语言** | Python + Conda | 3.13 / 25.5 |
| **代码托管** | GitHub | HTTPS + PAT |

---

## 📁 项目结构

```
project-data-platform-demo/
├── README.md                     # 项目说明文档
├── .gitignore                    # Git 忽略规则（Python/Docker/K8s/IDE）
├── environments/                 # 环境配置脚本
│   ├── windows/                  # Windows 宿主机脚本
│   │   └── setup.ps1             # PowerShell 一键修复
│   └── ubuntu/                   # Ubuntu 虚拟机脚本
│       └── setup.sh              # Bash 一键配置
├── docker/                       # Docker 容器环境
│   ├── docker-compose.yml        # 主 Compose 文件
│   └── Dockerfile                # 应用镜像构建文件
├── k8s/                          # Kubernetes 资源清单
│   ├── namespace.yaml
│   ├── deployment.yaml
│   └── service.yaml
├── src/                          # 应用源代码
│   └── main.py
├── notebooks/                    # Jupyter 数据分析 Notebook
├── scripts/                      # 工具/辅助脚本
└── data/                         # 数据文件（.gitignore 排除）
```

---

## 🚀 快速开始

### 0. 环境检测
```bash
# 运行分层环境检测
bash scripts/check_env.sh
```

### 1. Windows 宿主机
```powershell
# 以管理员身份运行一键修复脚本
.\environments\windows\setup.ps1
```

### 2. Ubuntu 虚拟机
```bash
# SSH 登录后执行
ssh -p 2222 <用户名>@localhost
bash ~/ubuntu_vm_setup.sh
```

### 3. Docker Compose 启动
```bash
cd docker
docker compose up -d
```

### 4. Kubernetes 部署（K3s）
```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/
kubectl get pods -A
```

---

## 📊 环境就绪状态

| 环境层 | 检测日期 | 状态 |
|--------|---------|------|
| Windows 宿主机 | 2026-07-20 | ✅ 就绪 |
| VirtualBox Ubuntu VM | 2026-07-20 | ⚠️ 待 SSH 登录配置 |
| Docker Desktop | 2026-07-20 | ✅ 就绪（7.65 GiB） |
| GitHub 仓库 | 2026-07-20 | 🚀 初始化中 |

---

## 🔧 镜像加速策略

| 工具 | 镜像源 | 状态 |
|------|--------|------|
| pip | `https://pypi.tuna.tsinghua.edu.cn/simple` | ✅ |
| Conda | `https://mirrors.tuna.tsinghua.edu.cn/anaconda/...` | ✅ |
| apt | `https://mirrors.tuna.tsinghua.edu.cn` | ✅ |
| Docker Hub | `https://docker.m.daocloud.io` | ✅ |
| Helm Charts | Bitnami (官方) | ✅ |

---

## 📝 环境检测报告

完整环境检测报告见：`环境就绪检测报告_20260719.md`

---

*项目创建: 2026-07-20 | 维护者: 戴骏杰*
