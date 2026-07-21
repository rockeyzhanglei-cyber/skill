#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
winmetrics-manual-complete.py - 人工处理完成后状态更新与WinMetrics补发。

用于处理流水线失败后的人工修复场景：
  1. 更新状态文件（.pr-status、.build-status等）
  2. 删除失败标记文件
  3. 补发 WinMetrics 事件（stage.completed + pipeline.completed）
  4. 更新 auto-dev.log

Usage:
  python scripts/winmetrics-manual-complete.py --demand-id ID --stage NAME --docs-dir PATH [--run-id ID] [--product NAME]

触发场景:
  用户说："已人工处理完成" → 自动执行此脚本
  用户说："WinMetrics 补发成功状态" → 自动执行此脚本
  用户说："更新状态为成功" → 自动执行此脚本

Example:
  # 提交+PR阶段人工处理完成
  python scripts/winmetrics-manual-complete.py --demand-id 1651457 --stage submit --docs-dir "C:/Users/lenovo/auto-dev-docs/统一登录/1651457"

  # 构建阶段人工处理完成
  python scripts/winmetrics-manual-complete.py --demand-id 1651457 --stage build --docs-dir "C:/Users/lenovo/auto-dev-docs/统一登录/1651457"
"""

import argparse
import os
import sys
import time
import json
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lib"))
from mcp_protocol import emit_result

# 状态文件映射
STATUS_FILES = {
    "submit": {
        "status_file": ".pr-status",
        "failed_marker": ".pr-create-failed",
        "success_pattern": None,  # 需要动态填充
        "default_duration": 300
    },
    "build": {
        "status_file": ".build-status",
        "failed_marker": ".build-failed",
        "success_pattern": "success",
        "default_duration": 600
    },
    "deploy": {
        "status_file": ".deploy-status",
        "failed_marker": ".deploy-failed",
        "success_pattern": "success",
        "default_duration": 900
    },
    "verify": {
        "status_file": ".verify-status",
        "failed_marker": ".verify-failed",
        "success_pattern": "success",
        "default_duration": 300
    },
}


def find_docs_dir(demand_id):
    """根据需求 ID 定位文档目录（从 auto-dev-docs 搜索）。"""
    # 从环境变量获取 auto-dev-docs 根目录
    docs_root = os.environ.get("AUTO_DEV_DOCS_ROOT", os.path.expanduser("~/auto-dev-docs"))

    if not os.path.isdir(docs_root):
        # 尝试常见路径
        common_paths = [
            "C:/Users/lenovo/auto-dev-docs",
            os.path.expanduser("~/auto-dev-docs"),
            os.path.expanduser("~/docs"),
        ]
        for path in common_paths:
            if os.path.isdir(path):
                docs_root = path
                break

    # 搜索需求目录
    for root, dirs, files in os.walk(docs_root):
        for d in dirs:
            if d == str(demand_id):
                return os.path.join(root, d)

    return None


def read_run_id(docs_dir):
    """读取 run_id。"""
    run_id_file = os.path.join(docs_dir, ".run-id")
    if os.path.exists(run_id_file):
        with open(run_id_file, "r", encoding="utf-8") as f:
            return f.read().strip()
    return None


def update_status_file(docs_dir, stage, success_value=None):
    """更新状态文件为成功。"""
    if stage not in STATUS_FILES:
        print(f"[WARN] 未知阶段: {stage}")
        return False

    config = STATUS_FILES[stage]
    status_file = os.path.join(docs_dir, config["status_file"])

    if not os.path.exists(status_file):
        print(f"[WARN] 状态文件不存在: {config['status_file']}")
        return False

    # 读取当前状态
    with open(status_file, "r", encoding="utf-8") as f:
        current_content = f.read().strip()

    # 确定成功值
    if success_value:
        new_content = success_value
    elif config["success_pattern"]:
        new_content = config["success_pattern"]
    else:
        # 对于 submit 阶段，需要保持仓库和PR ID信息
        # 格式: winning-winex-basic-frame#997817=failed → =success
        if "=failed" in current_content:
            new_content = current_content.replace("=failed", "=success")
        else:
            new_content = "success"

    # 更新文件
    with open(status_file, "w", encoding="utf-8") as f:
        f.write(new_content + "\n")

    print(f"[INFO] 状态文件已更新: {config['status_file']} → {new_content}")
    return True


def delete_failed_marker(docs_dir, stage):
    """删除失败标记文件。"""
    if stage not in STATUS_FILES:
        return False

    config = STATUS_FILES[stage]
    failed_marker = os.path.join(docs_dir, config["failed_marker"])

    if os.path.exists(failed_marker):
        os.remove(failed_marker)
        print(f"[INFO] 失败标记已删除: {config['failed_marker']}")
        return True
    else:
        print(f"[INFO] 无失败标记文件: {config['failed_marker']}")
        return True


def append_log(docs_dir, stage, message):
    """追加日志记录。"""
    log_file = os.path.join(docs_dir, "auto-dev.log")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] [INFO ] [{stage}] {message}\n")

    print(f"[INFO] 日志已更新: {message}")


def send_winmetrics_events(docs_dir, stage, run_id, demand_id, product=None):
    """补发 WinMetrics 事件。"""
    # 导入 winmetrics-report 的发送函数
    import subprocess

    script_dir = os.path.dirname(__file__)
    winmetrics_script = os.path.join(script_dir, "winmetrics-report.py")

    if not os.path.exists(winmetrics_script):
        print(f"[ERROR] winmetrics-report.py 不存在")
        return False

    # Step 1: 补发 stage.completed (success)
    duration = STATUS_FILES.get(stage, {}).get("default_duration", 300)
    cmd_stage = [
        sys.executable, winmetrics_script,
        "stage-complete",
        "--stage", stage,
        "--status", "success",
        "--docs-dir", docs_dir,
        "--duration", str(duration),
    ]
    if run_id:
        cmd_stage.extend(["--run-id", run_id])

    print(f"[INFO] 补发 stage.completed ({stage}, success)...")
    result = subprocess.run(cmd_stage, cwd=script_dir, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[ERROR] stage.completed 发送失败: {result.stderr}")
        return False
    print(f"[INFO] {result.stdout.strip()}")

    # Step 2: 补发 pipeline.completed
    # 读取所有阶段状态（假设所有阶段都成功）
    stages_json = json.dumps([
        {"name": "spec", "status": "success"},
        {"name": "pm", "status": "success"},
        {"name": "code", "status": "success"},
        {"name": "verify", "status": "success"},
        {"name": stage, "status": "success"},
    ])

    cmd_pipeline = [
        sys.executable, winmetrics_script,
        "summary",
        "--demand_id", str(demand_id),
        "--docs-dir", docs_dir,
        "--stages", stages_json,
    ]
    if run_id:
        cmd_pipeline.extend(["--run-id", run_id])
    if product:
        cmd_pipeline.extend(["--product", product])

    print(f"[INFO] 补发 pipeline.completed...")
    result = subprocess.run(cmd_pipeline, cwd=script_dir, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[ERROR] pipeline.completed 发送失败: {result.stderr}")
        return False
    print(f"[INFO] {result.stdout.strip()}")

    return True


def main():
    parser = argparse.ArgumentParser(
        description="人工处理完成后状态更新与WinMetrics补发",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
触发场景:
  用户说："已人工处理完成" → 自动执行此脚本
  用户说："WinMetrics 补发成功状态" → 自动执行此脚本
  用户说："更新状态为成功" → 自动执行此脚本

支持阶段:
  - submit: 提交+PR阶段
  - build: 构建阶段
  - deploy: 部署阶段
  - verify: 验证阶段
        """
    )
    parser.add_argument("--demand-id", required=True, help="需求 ID（TFS 工作项 ID）")
    parser.add_argument("--stage", required=True, choices=["submit", "build", "deploy", "verify"],
                        help="失败阶段名称")
    parser.add_argument("--docs-dir", help="文档目录路径（可选，自动定位）")
    parser.add_argument("--run-id", help="流水线运行 ID（可选，自动读取）")
    parser.add_argument("--product", help="产品名称（可选）")
    parser.add_argument("--success-value", help="状态文件成功值（可选，自动填充）")

    args = parser.parse_args()

    # Step 1: 定位文档目录
    docs_dir = args.docs_dir
    if not docs_dir:
        docs_dir = find_docs_dir(args.demand_id)
        if not docs_dir:
            print(f"[ERROR] 未找到需求 {args.demand_id} 的文档目录")
            print("\n请指定 --docs-dir 参数")
            sys.exit(1)

    print(f"[INFO] 文档目录: {docs_dir}")

    # Step 2: 读取 run_id
    run_id = args.run_id
    if not run_id:
        run_id = read_run_id(docs_dir)
        if run_id:
            print(f"[INFO] Run ID: {run_id}")

    # Step 3: 更新状态文件
    print(f"\n=== Step 1: 更新状态文件 ===")
    if not update_status_file(docs_dir, args.stage, args.success_value):
        sys.exit(1)

    # Step 4: 删除失败标记
    print(f"\n=== Step 2: 删除失败标记 ===")
    if not delete_failed_marker(docs_dir, args.stage):
        sys.exit(1)

    # Step 5: 追加日志
    print(f"\n=== Step 3: 更新日志 ===")
    append_log(docs_dir, args.stage, "人工处理完成，状态已更新为success")

    # Step 6: 补发 WinMetrics
    print(f"\n=== Step 4: 补发 WinMetrics 事件 ===")
    if not send_winmetrics_events(docs_dir, args.stage, run_id, args.demand_id, args.product):
        sys.exit(1)

    print(f"\n[SUCCESS] 所有操作完成！")
    print(f"需求 {args.demand_id} {args.stage} 阶段已标记为成功，WinMetrics 已补发")
    emit_result({
        "demand_id": args.demand_id,
        "stage": args.stage,
        "docs_dir": docs_dir,
        "status": "success",
        "winmetrics_sent": True,
    })


if __name__ == "__main__":
    main()