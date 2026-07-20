# 🚀 project-data-platform-demo GitHub 推送指令

# ============================================================
# 前置条件：在 GitHub 网页创建空仓库
# ============================================================
# 1. 浏览器打开: https://github.com/new
# 2. Repository name: project-data-platform-demo
# 3. Description: Data Platform Demo — 全栈混合开发环境项目
# 4. 选择 Public
# 5. ❌ 不勾选 "Add a README file"
# 6. ❌ 不勾选 ".gitignore"  
# 7. ❌ 不勾选 "Choose a license"
# 8. 点击 "Create repository"
# 9. 记下仓库 URL: https://github.com/tiancaijun798/project-data-platform-demo

# ============================================================
# 执行推送（PowerShell 终端）
# ============================================================
cd C:\Users\戴骏杰\Desktop\project-data-platform-demo

# 查看待推送内容
git log --oneline
git status

# 推送到 GitHub（HTTPS + Personal Access Token）
git push -u origin main

# 弹出 GitHub 登录窗口时：
#   Username: tiancaijun798
#   Password: 【粘贴 Personal Access Token，不是密码！】

# ============================================================
# 🔑 Personal Access Token 创建步骤
# ============================================================
# 1. 浏览器打开: https://github.com/settings/tokens
# 2. 点击 "Generate new token" → "Generate new token (classic)"
# 3. Note: project-data-platform-demo
# 4. Expiration: 90 days (推荐)
# 5. 勾选权限:
#    ✅ repo (全部)
#    ✅ workflow
# 6. 点击 "Generate token"
# 7. 复制生成的 token（ghp_xxxxxxxxxxxxxxxxxxxx）
#     ⚠️ 只显示一次！务必保存！

# ============================================================
# 推送成功验证
# ============================================================
# 浏览器访问:
#   https://github.com/tiancaijun798/project-data-platform-demo

# 命令行验证:
git ls-remote origin
