#!/bin/bash

# Docker 容器启动脚本

set -e

echo "========================================="
echo "  Docker Image Sync Service"
echo "========================================="

# 检查环境变量
echo "🔍 检查环境变量..."
if [ -z "$CORP_ID" ] || [ -z "$GITHUB_TOKEN" ]; then
    echo "❌ 缺少必要的环境变量"
    echo "请设置 .env 文件"
    exit 1
fi

echo "✅ 环境变量检查通过"
echo ""
echo "服务配置："
echo "  - 企业ID: $CORP_ID"
echo "  - GitHub仓库: $GITHUB_REPO"
echo "  - 端口: ${PORT:-3000}"
echo ""

# 启动应用
echo "🚀 启动服务..."

# 执行 CMD 传递的命令
exec "$@"

