#!/usr/bin/env python3
"""
OpenSpec 管理脚本
封装 OpenSpec CLI 操作，提供确定性接口
支持双路径策略：项目目录（用户可编辑）+ DOCS_DIR（流水线归档）
"""

import argparse
import json
import os
import subprocess
import sys
import shutil
from pathlib import Path


def run_openspec(args, timeout=60):
    """执行 OpenSpec CLI 命令"""
    cmd = ["openspec"] + args
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 1, "", "OpenSpec CLI 执行超时"
    except Exception as e:
        return 1, "", str(e)


def init_demand(docs_dir, project_dir, demand_id, demand_title, requirement_body):
    """为需求创建 OpenSpec 目录结构（双路径）"""
    # DOCS_DIR 归档路径
    docs_openspec_dir = Path(docs_dir) / "openspec" / "changes" / f"tfs-{demand_id}"
    docs_openspec_dir.mkdir(parents=True, exist_ok=True)
    (docs_openspec_dir / "specs").mkdir(exist_ok=True)

    # 项目目录路径（如果指定）
    project_openspec_dir = None
    if project_dir:
        project_openspec_dir = Path(project_dir) / "openspec" / "changes" / f"tfs-{demand_id}"
        project_openspec_dir.mkdir(parents=True, exist_ok=True)
        (project_openspec_dir / "specs").mkdir(exist_ok=True)

    # 创建空的 OpenSpec 文件模板
    proposal_content = f"# Proposal: {demand_title}\n\n## 背景\n\n{requirement_body}\n\n## 目标\n\n[待填充]\n\n## 影响分析\n\n[待填充]\n\n## 非目标\n\n[待填充]\n"
    design_content = f"# Design: {demand_title}\n\n## 技术方案\n\n[待填充]\n\n## API 设计\n\n[待填充]\n\n## 数据模型\n\n[待填充]\n\n## 风险点\n\n[待填充]\n"
    tasks_content = f"# Tasks: {demand_title}\n\n## 实现任务\n\n[待填充]\n"

    # 写入 DOCS_DIR
    (docs_openspec_dir / "proposal.md").write_text(proposal_content)
    (docs_openspec_dir / "design.md").write_text(design_content)
    (docs_openspec_dir / "tasks.md").write_text(tasks_content)

    # 写入项目目录（如果指定）
    if project_openspec_dir:
        (project_openspec_dir / "proposal.md").write_text(proposal_content)
        (project_openspec_dir / "design.md").write_text(design_content)
        (project_openspec_dir / "tasks.md").write_text(tasks_content)
        print(f"OpenSpec 目录已创建（双路径）:")
        print(f"  项目目录: {project_openspec_dir}")
        print(f"  归档目录: {docs_openspec_dir}")
    else:
        print(f"OpenSpec 目录已创建: {docs_openspec_dir}")

    return 0


def validate_demand(docs_dir, project_dir, demand_id, openspec_dir=None):
    """校验 OpenSpec 产物完整性（优先项目目录）"""
    # 确定校验目录（优先级）
    check_dir = None

    if openspec_dir:
        # 直接指定目录
        check_dir = Path(openspec_dir)
    elif project_dir:
        # 优先项目目录
        project_openspec = Path(project_dir) / "openspec" / "changes" / f"tfs-{demand_id}"
        if project_openspec.exists():
            check_dir = project_openspec
        else:
            # 回退到 DOCS_DIR
            docs_openspec = Path(docs_dir) / "openspec" / "changes" / f"tfs-{demand_id}"
            check_dir = docs_openspec
    else:
        # 只检查 DOCS_DIR
        check_dir = Path(docs_dir) / "openspec" / "changes" / f"tfs-{demand_id}"

    if not check_dir.exists():
        print(f"OpenSpec 校验失败: 目录不存在 {check_dir}")
        return "fail"

    required_files = [
        check_dir / "proposal.md",
        check_dir / "design.md",
        check_dir / "tasks.md",
    ]

    missing = []
    empty = []

    for file in required_files:
        if not file.exists():
            missing.append(file.name)
        elif file.stat().st_size < 100:  # 至少 100 字节才算有实质内容
            empty.append(file.name)

    if missing:
        print(f"OpenSpec 校验失败: 缺失文件 {', '.join(missing)}")
        return "fail"
    if empty:
        print(f"OpenSpec 校验失败: 空文件 {', '.join(empty)}")
        return "fail"

    print(f"OpenSpec 校验通过: {check_dir}")
    return "pass"


def sync_to_docs(docs_dir, project_dir, demand_id):
    """同步项目目录到 DOCS_DIR"""
    if not project_dir:
        print("未指定项目目录，无需同步")
        return 0

    project_openspec = Path(project_dir) / "openspec" / "changes" / f"tfs-{demand_id}"
    docs_openspec = Path(docs_dir) / "openspec" / "changes" / f"tfs-{demand_id}"

    if not project_openspec.exists():
        print(f"项目目录不存在: {project_openspec}")
        return 1

    # 复制所有文件
    docs_openspec.mkdir(parents=True, exist_ok=True)
    for file in project_openspec.glob("*"):
        if file.is_file():
            shutil.copy2(file, docs_openspec / file.name)

    print(f"同步完成: {project_openspec} -> {docs_openspec}")
    return 0


def get_status(docs_dir, demand_id):
    """获取 OpenSpec 状态"""
    status_file = Path(docs_dir) / ".spec-status"

    if not status_file.exists():
        return "pending"

    return status_file.read_text().strip()


def write_status(docs_dir, demand_id, status):
    """写入 OpenSpec 状态文件"""
    status_file = Path(docs_dir) / ".spec-status"
    status_file.write_text(status)
    print(f".spec-status 已写入: {status}")

    # 如果是 confirmed 状态，同时写入 .spec-confirmed
    if status == "confirmed":
        confirmed_file = Path(docs_dir) / ".spec-confirmed"
        from datetime import datetime
        confirmed_file.write_text(f"confirmed\n{datetime.now().strftime('%Y%m%d%H%M%S')}\n")
        print(f".spec-confirmed 已写入")


def main():
    parser = argparse.ArgumentParser(description="OpenSpec 管理脚本")
    parser.add_argument("--docs-dir", required=True, help="需求文档目录")
    parser.add_argument("--demand-id", required=True, help="需求 ID")
    parser.add_argument("--project-dir", help="项目目录（可选，用于双路径策略）")
    parser.add_argument("--openspec-dir", help="直接指定 OpenSpec 目录（优先级最高）")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # init-demand 命令
    init_parser = subparsers.add_parser("init-demand", help="创建 OpenSpec 目录结构")
    init_parser.add_argument("--demand-title", required=True, help="需求标题")
    init_parser.add_argument("--requirement-body", required=True, help="需求描述")

    # validate-demand 命令
    validate_parser = subparsers.add_parser("validate-demand", help="校验 OpenSpec 产物")

    # sync-to-docs 命令（新增）
    sync_parser = subparsers.add_parser("sync-to-docs", help="同步项目目录到 DOCS_DIR")

    # status 命令
    status_parser = subparsers.add_parser("status", help="获取 OpenSpec 状态")

    # write-status 命令
    write_parser = subparsers.add_parser("write-status", help="写入 OpenSpec 状态")
    write_parser.add_argument("--status", required=True, choices=["pass", "fail", "pending", "confirmed"], help="状态值")

    args = parser.parse_args()

    docs_dir = Path(args.docs_dir).resolve()
    demand_id = args.demand_id
    project_dir = args.project_dir if args.project_dir else None
    openspec_dir = args.openspec_dir if args.openspec_dir else None

    if args.command == "init-demand":
        sys.exit(init_demand(docs_dir, project_dir, demand_id, args.demand_title, args.requirement_body))
    elif args.command == "validate-demand":
        status = validate_demand(docs_dir, project_dir, demand_id, openspec_dir)
        print(status)
        sys.exit(0 if status == "pass" else 1)
    elif args.command == "sync-to-docs":
        sys.exit(sync_to_docs(docs_dir, project_dir, demand_id))
    elif args.command == "status":
        print(get_status(docs_dir, demand_id))
        sys.exit(0)
    elif args.command == "write-status":
        write_status(docs_dir, demand_id, args.status)
        sys.exit(0)


if __name__ == "__main__":
    main()