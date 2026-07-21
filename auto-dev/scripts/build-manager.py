#!/usr/bin/env python3
"""
build-manager.py - 构建触发与轮询协调。

Usage:
  python scripts/build-manager.py trigger --demand-id ID --collection COL
  python scripts/build-manager.py poll --demand-id ID --collection COL [--interval SEC] [--max-attempts N]
  python scripts/build-manager.py parse-trigger --result-file PATH
  python scripts/build-manager.py parse-poll --result-file PATH
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
    params = {"demand_id": str(args.demand_id), "collection": args.collection}
    emit_mcp_call("mcp__devops-mcp__build_single_demand", params)


def cmd_poll(args):
    """FIX-21: 构建轮询使用 initial_wait=120。"""
    params = {"demand_id": str(args.demand_id), "collection": args.collection}
    emit_mcp_call_poll(
        "mcp__devops-mcp__check_demand_build_status",
        params,
        interval=args.interval if args.interval is not None else 120,
        max_attempts=args.max_attempts if args.max_attempts is not None else 20,
        terminal_states=["SUCCESS", "FAILURE", "FAILED", "ERROR"],
        on_success="continue",
        on_timeout="fail_stage",
        initial_wait=120,
    )


def _read_result(args):
    """统一读取结果：支持 --result-file 和 --result-stdin。"""
    if getattr(args, "result_stdin", False):
        return read_result_stdin()
    return read_result_file(args.result_file)


def cmd_parse_trigger(args):
    data = _read_result(args)
    if not data:
        emit_error("E003", "No result from build trigger")
    status = "triggered" if data.get("success", False) else "failed"
    emit_result({"status": status, "raw": data})


def cmd_parse_poll(args):
    data = _read_result(args)
    if not data:
        emit_result({"terminal": True, "build_status": "failed", "reason": "No data"})
        return

    if isinstance(data, str):
        result_str = data.strip().upper()
    elif isinstance(data, dict):
        raw = data.get("status") or data.get("result") or ""
        result_str = str(raw).upper()
    else:
        result_str = ""

    if result_str == "SUCCESS":
        emit_result({"terminal": True, "build_status": "success"})
    elif result_str in ("FAILURE", "FAILED", "ERROR"):
        emit_result({"terminal": True, "build_status": "failed", "reason": "Build failed"})
    elif result_str == "UNBUILT":
        emit_result({"terminal": False, "build_status": "in_progress"})
    else:
        emit_result({"terminal": False, "build_status": "in_progress", "raw": str(data)})


def main():
    parser = argparse.ArgumentParser(description="构建触发与轮询")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("trigger")
    p.add_argument("--demand-id", required=True)
    p.add_argument("--collection", required=True)

    p = sub.add_parser("poll")
    p.add_argument("--demand-id", required=True)
    p.add_argument("--collection", required=True)
    p.add_argument("--interval", type=int, default=120)
    p.add_argument("--max-attempts", type=int, default=20)

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
