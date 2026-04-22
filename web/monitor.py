#!/usr/bin/env python3
"""
后台任务监控系统
- 监控转录任务状态
- 自动检测和修复常见问题
- 记录详细日志
"""

import json
import time
import subprocess
import os
import sys
from datetime import datetime

sys.path.append(os.path.dirname(__file__))

LOG_FILE = "/tmp/podcast_monitor.log"


def log(message, level="INFO"):
    """记录日志"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] [{level}] {message}"
    print(log_line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(log_line + "\n")


def check_flask_service():
    """检查Flask服务是否运行"""
    try:
        import requests
        response = requests.get("http://localhost:5000/", timeout=5)
        return True
    except:
        return False


def restart_flask_service():
    """重启Flask服务"""
    log("检测到Flask服务未运行，尝试重启...", "WARNING")
    try:
        # 杀死现有进程
        subprocess.run(["pkill", "-f", "python app.py"], capture_output=True)
        time.sleep(2)

        # 启动新进程
        web_dir = os.path.dirname(__file__)
        env_python = os.path.join(os.path.dirname(web_dir), "venv", "bin", "python")

        subprocess.Popen(
            [env_python, "app.py"],
            cwd=web_dir,
            stdout=open("/tmp/flask.log", "a"),
            stderr=subprocess.STDOUT,
            start_new_session=True
        )

        time.sleep(3)

        if check_flask_service():
            log("Flask服务重启成功", "SUCCESS")
            return True
        else:
            log("Flask服务重启失败", "ERROR")
            return False
    except Exception as e:
        log(f"重启服务出错: {e}", "ERROR")
        return False


def check_and_fix_common_errors():
    """检查并修复常见问题"""
    try:
        import requests

        # 检查转录任务状态
        response = requests.get("http://localhost:5000/api/task/last", timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get("success") and data.get("data"):
                task = data["data"]
                status = task.get("status")
                message = task.get("message", "")

                if status == "error":
                    log(f"检测到错误任务: {message}", "WARNING")

                    # 自动修复逻辑
                    if "403" in message:
                        log("检测到403错误，可能需要更新请求头", "WARNING")
                    elif "torch" in message.lower() or "No module" in message:
                        log("检测到模块缺失错误", "ERROR")
                    elif "timeout" in message.lower():
                        log("检测到超时错误，可能需要增加超时时间", "WARNING")

    except Exception as e:
        log(f"检查错误时出错: {e}", "ERROR")


def monitor_loop():
    """主监控循环"""
    log("=" * 60)
    log("播客转文章监控系统启动")
    log("=" * 60)

    while True:
        try:
            # 检查Flask服务
            if not check_flask_service():
                restart_flask_service()
            else:
                # 检查并修复错误
                check_and_fix_common_errors()

            time.sleep(10)  # 每10秒检查一次

        except KeyboardInterrupt:
            log("监控系统停止", "INFO")
            break
        except Exception as e:
            log(f"监控循环出错: {e}", "ERROR")
            time.sleep(30)


if __name__ == "__main__":
    monitor_loop()
