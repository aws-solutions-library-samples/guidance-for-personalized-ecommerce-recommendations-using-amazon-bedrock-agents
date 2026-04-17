#!/bin/bash

# ShopBot Web 应用启动脚本

echo "🚀 启动 ShopBot Web 应用..."
echo "================================"

# 检查环境变量
if [ ! -f .env ]; then
    echo "⚠️  未找到 .env 文件"
    echo "请确保配置了以下环境变量:"
    echo "  - AWS_DEFAULT_REGION"
    echo "  - AWS_ACCESS_KEY_ID"
    echo "  - AWS_SECRET_ACCESS_KEY"
    echo "  - BEDROCK_MODEL_ID"
    exit 1
fi

# 检查依赖
echo "📦 检查依赖..."
python -c "import tiktoken" 2>/dev/null || {
    echo "⚠️  tiktoken 未安装，正在安装..."
    pip install tiktoken>=0.5.0
}

# 启动后端
echo ""
echo "🖥️  启动后端服务 (FastAPI)..."
echo "地址: http://localhost:8000"
echo "文档: http://localhost:8000/docs"
echo "前端: http://localhost:8000/app/index.html"
echo ""
echo "================================"
echo "💡 提示:"
echo "  - 使用 Ctrl+C 停止服务"
echo "  - 后端日志将实时显示"
echo "================================"
echo ""

# 运行 FastAPI
python -m uvicorn app.main:api --reload --host 0.0.0.0 --port 8000
