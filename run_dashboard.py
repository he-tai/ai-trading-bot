#!/usr/bin/env python
"""启动 Web 控制面板"""
import sys
import os
import argparse

# 确保从项目根目录运行，src 加入 path 以支持 config/api/trading 等模块
project_root = os.path.dirname(os.path.abspath(__file__))
os.chdir(project_root)
sys.path.insert(0, os.path.join(project_root, "src"))

from web.app import run_dashboard

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0", help="监听地址")
    parser.add_argument("--port", type=int, default=5000, help="端口")
    args = parser.parse_args()
    run_dashboard(host=args.host, port=args.port)
