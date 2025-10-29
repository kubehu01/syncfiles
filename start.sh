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

# 检查或创建虚拟环境
if [ ! -d "venv" ]; then
    echo "创建虚拟环境..."
    python3 -m venv venv
fi

echo "激活虚拟环境..."
source venv/bin/activate

echo ""
echo "========================================="
echo "  检查依赖"
echo "========================================="
echo ""

# 第一次尝试：检查依赖是否已安装
echo "检查依赖是否已安装..."
if python -c "import flask; import requests; from github import Github; import qingstor" 2>/dev/null; then
    echo "✅ 依赖已安装"
    echo ""
    echo "========================================="
    echo "  启动服务（后台运行）"
    echo "========================================="
    echo ""
    # 创建日志目录
    mkdir -p logs
    
    # 检查是否已运行
    if [ -f "app.pid" ]; then
        OLD_PID=$(cat app.pid)
        if ps -p $OLD_PID > /dev/null 2>&1; then
            echo "⚠️  服务已在运行中（PID: $OLD_PID）"
            echo "如需重启，请先执行: ./stop.sh 或 kill $OLD_PID"
            exit 1
        else
            echo "ℹ️  清理旧的 PID 文件"
            rm -f app.pid
        fi
    fi
    
    # 后台启动服务
    nohup python app.py > logs/app.log 2>&1 &
    PID=$!
    echo $PID > app.pid
    
    echo "✅ 服务已启动"
    echo "   PID: $PID"
    echo "   日志: logs/app.log"
    echo ""
    echo "查看日志: tail -f logs/app.log"
    echo "停止服务: kill $PID"
else
    echo "⚠️  依赖未完全安装，正在安装..."
    pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    
    echo ""
    echo "========================================="
    echo "  再次检查依赖"
    echo "========================================="
    echo ""
    
    # 第二次尝试：安装后检查
    if python -c "import flask; import requests; from github import Github; import qingstor" 2>/dev/null; then
        echo "✅ 依赖安装成功"
        echo ""
        echo "========================================="
        echo "  启动服务（后台运行）"
        echo "========================================="
        echo ""
        # 创建日志目录
        mkdir -p logs
        
        # 检查是否已运行
        if [ -f "app.pid" ]; then
            OLD_PID=$(cat app.pid)
            if ps -p $OLD_PID > /dev/null 2>&1; then
                echo "⚠️  服务已在运行中（PID: $OLD_PID）"
                echo "如需重启，请先执行: kill $OLD_PID"
                exit 1
            else
                echo "ℹ️  清理旧的 PID 文件"
                rm -f app.pid
            fi
        fi
        
        # 后台启动服务
        nohup python app.py > logs/app.log 2>&1 &
        PID=$!
        echo $PID > app.pid
        
        echo "✅ 服务已启动"
        echo "   PID: $PID"
        echo "   日志: logs/app.log"
        echo ""
        echo "查看日志: tail -f logs/app.log"
        echo "停止服务: kill $PID"
    else
        echo "❌ 依赖安装失败，请检查错误信息"
        exit 1
    fi
fi


