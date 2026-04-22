#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
播客转文章Web平台启动脚本
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from web.app import app

if __name__ == '__main__':
    print("=" * 60)
    print("🎙️ 播客转文章Web平台")
    print("=" * 60)
    print()
    print("启动信息:")
    print(f"  - 访问地址: http://localhost:5000")
    print(f"  - 按 Ctrl+C 停止服务")
    print()
    print("=" * 60)

    app.run(
        debug=True,
        host='0.0.0.0',
        port=5000,
        threaded=True
    )
