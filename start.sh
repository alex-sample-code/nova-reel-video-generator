#!/bin/bash

echo "🎬 AI视频生成器"
echo "==============="
echo ""
echo "✨ 功能特色:"
echo "  🔄 自动刷新 - 每5秒自动检查生成状态"
echo "  🎥 多镜头视频 - 支持1-8张图片生成连贯视频"
echo "  🎨 多种风格 - 12种不同的视频风格"
echo "  ⚡ 异步生成 - 后台生成不阻塞界面"
echo ""
echo "🚀 启动中..."
echo ""

# 激活虚拟环境
source .venv/bin/activate

# 启动应用
python app.py
