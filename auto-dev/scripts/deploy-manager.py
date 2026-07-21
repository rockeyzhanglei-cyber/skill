#!/usr/bin/env python3
"""
deploy-manager.py - 部署触发与轮询协调。

Usage:
  python scripts/deploy-manager.py trigger --demand-id ID --env-id ENV
  python scripts/deploy-manager.py poll --step-id ID [--interval SEC] [--max-attempts N]
  python scripts/deploy-manager.py parse-trigger --result-file PATH
  python scripts/deploy-manager.py parse-poll --result-file PATH
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


def cmd_trigger(args):
    params = {"demandId": str(args.demand_id), "envId": args.env_id}
    emit_mcp_call("mcp__devops-mcp__trigger_deploy", params)


def cmd_poll(args):
    """FIX-12: initial_wait=300，CANCELLED 为终止状态。"""
    params = {"stepId": str(args.step_id)}
    emit_mcp_call_poll(
        "mcp__devops-mcp__query_deploy_progress",
        params,
        interval=args.interval if args.interval is not None else 120,
        max_attempts=args.max_attempts if args.max_attempts is not None else 30,
        terminal_states=["SUCCESS", "FAILURE", "FAILED", "CANCELLED"],
        on_success="continue",
        on_timeout="fail_stage",
        initial_wait=300,
    )


def _read_result(args):
    """统一读取结果：支持 --result-file 和 --result-stdin。"""
    if getattr(args, "result_stdin", False):
        return read_result_stdin()
    return read_result_file(args.result_file)


def cmd_parse_trigger(args):
    data = _read_result(args)
    if not data:
        emit_error("E003", "No result from deploy trigger")
    step_id = data.get("taskId", data.get("stepId", ""))
    if not step_id:
        emit_error("E003", f"Deploy trigger returned no step ID: {json.dumps(data, ensure_ascii=False)}")
    emit_result({"step_id": str(step_id), "success": True})


def cmd_parse_poll(args):
    data = _read_result(args)
    if not data:
        emit_result({"terminal": True, "deploy_status": "failed", "reason": "No data"})
        return

    if isinstance(data, str):
        status = data.upper()
    elif isinstance(data, dict):
        status = str(data.get("status", data.get("state", ""))).upper()
    else:
        status = ""

    if status == "SUCCESS":
        emit_result({"terminal": True, "deploy_status": "success"})
    elif status in ("FAILURE", "FAILED"):
        reason = data.get("failReason", "") if isinstance(data, dict) else ""
        emit_result({"terminal": True, "deploy_status": "failed", "reason": reason})
    elif status == "CANCELLED":
        emit_result({"terminal": True, "deploy_status": "failed", "reason": "Deploy cancelled"})
    elif status == "PROGRESSING":
        emit_result({"terminal": False, "deploy_status": "in_progress"})
    else:
        print(f"[WARN] 未识别的部署状态: {status}, 原始数据: {str(data)[:200]}", file=sys.stderr, flush=True)
        emit_result({"terminal": False, "deploy_status": "in_progress", "raw": str(data)})


def main():
    parser = argparse.ArgumentParser(description="部署触发与轮询")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("trigger")
    p.add_argument("--demand-id", required=True)
    p.add_argument("--env-id", required=True)

    p = sub.add_parser("poll")
    p.add_argument("--step-id", required=True)
    p.add_argument("--interval", type=int, default=120)
    p.add_argument("--max-attempts", type=int, default=30)

    p = sub.add_parser("parse-trigger")
    p.add_argument("--result-file", default=None)
    p.add_argument("--result-stdin", action="store_true", default=False)

    p = sub.add_parser("parse-poll")
    p.add_argument("--result-file", default=None)
    p.add_argument("--result-stdin", action="store_true", default=False)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        "trigger": cmd_trigger,
        "poll": cmd_poll,
        "parse-trigger": cmd_parse_trigger,
        "parse-poll": cmd_parse_poll,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
