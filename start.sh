#!/bin/bash

# 启动脚本

echo "========================================="
echo "  Docker Image Sync Service"
echo "========================================="

# 检查环境变量文件
if [ ! -f .env ]; then
    echo "❌ 未找到 .env 文件"
    echo ""
    echo "请执行: cp env.example .env"
    echo "然后编辑 .env 文件填写配置"
    exit 1
fi

echo "✅ 检查 .env 文件"
echo ""

# 检查 Python 版本
if ! command -v python3 &> /dev/null; then
    echo "❌ 未安装 Python 3"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
echo "✅ Python 版本: $PYTHON_VERSION"
echo ""

# 检查依赖
if [ ! -d "venv" ]; then
    echo "创建虚拟环境..."
    python3 -m venv venv
fi

echo "激活虚拟环境..."
source venv/bin/activate

echo "安装依赖..."
pip install -r requirements.txt

echo ""
echo "========================================="
echo "  启动服务"
echo "========================================="
echo ""

python app.py

