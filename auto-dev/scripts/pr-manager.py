#!/usr/bin/env python3
"""
pr-manager.py - PR 创建与轮询协调。

Usage:
  python scripts/pr-manager.py create --repo URL --source BRANCH --target BRANCH
  python scripts/pr-manager.py poll --pr-id ID [--interval SEC] [--max-attempts N]
  python scripts/pr-manager.py parse-create --result-file PATH
  python scripts/pr-manager.py parse-poll --result-file PATH
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lib"))
from mcp_protocol import (
    emit_mcp_call, emit_mcp_call_poll, emit_result, emit_error, read_result_file,
    read_result_stdin,
)


def cmd_create(args):
    """输出用于创建 PR 的 MCP_CALL。"""
    params = {
        "repo_url": args.repo,
        "source_branch": args.source,
        "target_branch": args.target,
    }
    emit_mcp_call("mcp__devops-mcp__create_pr", params)


def cmd_poll(args):
    """输出用于 PR 状态轮询的 MCP_CALL_POLL（FIX-13: initial_wait=120）。

    terminal_states 使用简单大写状态值，宿主代理对 MCP 返回的
    current_step + status 分别匹配。parse-poll 做最终终态判定。
    """
    params = {"pr_id": str(args.pr_id)}
    emit_mcp_call_poll(
        "mcp__devops-mcp__query_pr_status",
        params,
        interval=args.interval if args.interval is not None else 120,
        max_attempts=args.max_attempts if args.max_attempts is not None else 60,
        terminal_states=["SUCCESS",
                         "FAILURE", "ERROR", "CHECK_FAILED",
                         "DEPLOY_FAILED", "MERGE_FAILED",
                         "REVIEW_REJECTED", "REJECT"],
        on_success="continue",
        on_timeout="continue",  # PR 可能需要人工评审，超时不终止流水线
        initial_wait=120,
    )


def _read_result(args):
    """统一读取结果：支持 --result-file 和 --result-stdin。"""
    if getattr(args, "result_stdin", False):
        return read_result_stdin()
    return read_result_file(args.result_file)


# 可重试的错误关键词 → (延迟秒, 最大重试次数)
RETRYABLE_ERRORS = {
    "提交未关联工作项": (30, 3),
    "未关联工作项": (30, 3),
}


def cmd_parse_create(args):
    """解析 PR 创建结果。"""
    data = _read_result(args)
    if not data:
        emit_error("E003", "No result data from PR creation")

    pr_id = data.get("tfs_pr_id", data.get("pr_id", ""))
    if not pr_id:
        error_msg = data.get("error", data.get("message", json.dumps(data, ensure_ascii=False)))
        # 检查是否为可重试错误
        retry_count = getattr(args, "retry_count", 0)
        for keyword, (delay, max_retries) in RETRYABLE_ERRORS.items():
            if keyword in error_msg:
                if retry_count < max_retries:
                    emit_result({
                        "success": False,
                        "action": "retry",
                        "retry_count": retry_count + 1,
                        "max_retries": max_retries,
                        "delay": delay,
                        "error": error_msg,
                    })
                    return
                # 重试耗尽
                emit_error("E003", f"PR creation failed after {max_retries} retries: {error_msg}")
                return
        emit_error("E003", f"PR creation failed: {error_msg}")

    emit_result({
        "success": True,
        "pr_id": str(pr_id),
        "pr_url": data.get("pr_url", data.get("url", "")),
    })


def cmd_parse_poll(args):
    """解析 PR 状态轮询结果。"""
    data = _read_result(args)
    if not data:
        emit_result({"terminal": True, "pr_status": "failed", "reason": "No result data"})
        return

    status = data.get("status", "").upper()
    current_step = data.get("current_step", "").upper()
    error_detail = data.get("error_detail", data.get("check_detail", ""))

    if current_step == "FINISH" and status == "SUCCESS":
        emit_result({"terminal": True, "pr_status": "success"})
        return

    if current_step == "REVIEW" and status == "PROGRESSING":
        emit_result({"terminal": True, "pr_status": "review-wait"})
        return

    failure_states = ["FAILURE", "ERROR", "CHECK_FAILED", "DEPLOY_FAILED",
                      "MERGE_FAILED", "REVIEW_REJECTED", "REJECT"]
    if status in failure_states:
        emit_result({
            "terminal": True,
            "pr_status": "failed",
            "reason": error_detail or f"{current_step}:{status}",
        })
        return

    if not status and not current_step:
        print("[WARN] PR 轮询返回空响应，可能是 MCP 连接异常", file=sys.stderr, flush=True)
        emit_result({"terminal": True, "pr_status": "failed", "reason": "Empty response from PR status query"})
        return

    emit_result({
        "terminal": False,
        "pr_status": "in_progress",
        "current_step": current_step,
        "status": status,
    })


def main():
    parser = argparse.ArgumentParser(description="PR 创建与轮询")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("create")
    p.add_argument("--repo", required=True)
    p.add_argument("--source", required=True)
    p.add_argument("--target", required=True)

    p = sub.add_parser("poll")
    p.add_argument("--pr-id", required=True)
    p.add_argument("--interval", type=int, default=120)
    p.add_argument("--max-attempts", type=int, default=60)

    p = sub.add_parser("parse-create")
    p.add_argument("--result-file", default=None)
    p.add_argument("--result-stdin", action="store_true", default=False)
    p.add_argument("--retry-count", type=int, default=0)

    p = sub.add_parser("parse-poll")
    p.add_argument("--result-file", default=None)
    p.add_argument("--result-stdin", action="store_true", default=False)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        "create": cmd_create,
        "poll": cmd_poll,
        "parse-create": cmd_parse_create,
        "parse-poll": cmd_parse_poll,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
