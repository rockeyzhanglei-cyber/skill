#!/usr/bin/env python3
"""
winmetrics-report.py - WinMetrics HMAC 事件上报。

替代 shared-header.md 中的 _wm_event bash 函数。
直接使用 Python hmac/hashlib/urllib，无需 MCP 或 Node.js。

account 字段解析优先级：
  1. 显式 --account 参数
  2. {docs_dir}/.dev-assigned-to 文件（需求开发负责人）
  3. WM_ACCOUNT 环境变量
  4. "unknown"

Usage:
  python scripts/winmetrics-report.py event --name EVENT [--attrs key=val ...] [--docs-dir PATH] [--run-id ID] [--account NAME]
  python scripts/winmetrics-report.py stage-start --stage NAME --skill SKILL [--docs-dir PATH] [--run-id ID] [--account NAME]
  python scripts/winmetrics-report.py stage-complete --stage NAME --status STATUS --duration SEC [--docs-dir PATH] [--run-id ID]
  python scripts/winmetrics-report.py stage-failed --stage NAME --error MSG [--docs-dir PATH] [--run-id ID]
  python scripts/winmetrics-report.py pipeline-event --name EVENT --demand_id ID [--docs-dir PATH] [--title TEXT] [--product NAME] [--attrs key=val ...] [--run-id ID] [--account NAME]
  python scripts/winmetrics-report.py summary --demand_id ID [--stages JSON] [--docs-dir PATH] [--product NAME] [--run-id ID]
  python scripts/winmetrics-report.py retry-fallback --docs-dir PATH
"""

import argparse
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lib"))
from mcp_protocol import load_config_env, emit_result

_event_seq = 0


def _get_config():
    """从 config.env 加载 WinMetrics 配置。"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    load_config_env(os.path.join(script_dir, ".."))
    api = "https://wxpcpp.winning.com.cn:2443/winmetrics/api/events"
    secret = "d2lubmluZw=="
    if not secret:
        print("[WARN] WM_SECRET 未配置，HMAC 签名无效，事件将被服务端拒绝", file=sys.stderr)
    return api, secret


def _send_event(payload, api_url, secret, max_retries=2):
    """签名并发送 WinMetrics 事件，支持重试（FIX-32: 每次尝试使用新签名）。"""
    body_str = json.dumps(payload, ensure_ascii=False)
    body = body_str.encode("utf-8")
    for attempt in range(max_retries + 1):
        ts = str(int(time.time()))
        sig = hmac.new(
            secret.encode("utf-8"),
            (ts + "\n" + body_str).encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        req = urllib.request.Request(
            api_url, data=body,
            headers={
                "Content-Type": "application/json",
                "X-WM-Timestamp": ts,
                "X-WM-Signature": sig,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=3) as resp:
                code = resp.getcode()
                return code, code in (200, 409)
        except (urllib.error.URLError, OSError):
            if attempt < max_retries:
                time.sleep(1 * (attempt + 1))
            continue
    return 0, False


def _build_event(event_name, attrs, run_id=None, account=None):
    """构建 WinMetrics 事件负载。"""
    global _event_seq
    _event_seq += 1
    event = {
        "event_id": f"wm-{int(time.time())}-{os.getpid()}-{_event_seq}",
        "event": event_name,
        "run_id": run_id or os.environ.get("WM_RUN_ID", "unknown"),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "scenario_type": "auto_dev",
    }
    if account:
        event["account"] = account
    event.update(attrs)
    return event


STAGE_DISPLAY_NAMES = {
    "spec": "openspec",
    "规格": "openspec",
    "pm": "需求分析",
    "code": "编码",
    "verify": "需求校验",
    "submit": "提交+PR",
    "build": "构建",
    "deploy": "部署",
    "report": "报告",
}


def _append_log(docs_dir, level, stage, message):
    """向 auto-dev.log 追加一行日志。"""
    if not docs_dir:
        return
    log_dir = os.path.expanduser(docs_dir)
    log_path = os.path.join(log_dir, "auto-dev.log")
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    display_stage = STAGE_DISPLAY_NAMES.get(stage, stage)
    line = f"[{ts}] [{level.ljust(5)}] [{display_stage}] {message}\n"
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line)
    except OSError:
        pass


def _save_fallback(payload, docs_dir):
    """将发送失败的事件保存到回退文件。"""
    if not docs_dir:
        return
    os.makedirs(docs_dir, exist_ok=True)
    fallback_path = os.path.join(docs_dir, ".wm-events.json")
    with open(fallback_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _clean_assigned_to(raw_value):
    """清洗 TFS assignedTo 字段，提取纯用户名。

    输入格式示例：
      - "tfq(唐方琼)" 或 "tfq（唐方琼）" -> "tfq"
      - "tfq(唐方琼) <WINNING\\tfq>" -> "tfq"
      - "<WINNING\\tfq>" -> "tfq"
      - "tfq" -> "tfq"

    清洗规则：
      1. 提取第一个 "(" 或 "<" 或空格之前的部分
      2. 如果格式是 "<DOMAIN\\user>"，提取反斜杠后的用户名
      3. 如果已经是纯用户名，直接返回
    """
    if not raw_value:
        return raw_value

    value = raw_value.strip()

    # 处理 "<DOMAIN\user>" 格式
    if value.startswith("<") and "\\" in value:
        # 提取 <DOMAIN\user> 中的 user 部分
        inner = value[1:].rstrip(">")  # 去掉 < 和 >，得到 DOMAIN\user
        if "\\" in inner:
            return inner.split("\\", 1)[1]  # 返回 user 部分

    # 提取第一个 "(" 或 "（" 或 "<" 或空格之前的部分
    for stop_char in ("(", "（", "<", " "):
        idx = value.find(stop_char)
        if idx > 0:
            return value[:idx]

    # 如果没有特殊字符，可能已经是纯用户名或包含 DOMAIN\user
    if "\\" in value:
        return value.split("\\", 1)[1]

    return value


def _resolve_account(account=None, docs_dir=None):
    """按优先级解析 account：显式参数 → 配置(WM_ACCOUNT) → 需求开发负责人 → unknown。

    优先级说明：
      1. 显式 --account 参数（手动指定）
      2. WM_ACCOUNT 环境变量（配置优先）
      3. .dev-assigned-to 文件（需求开发负责人）
      4. "unknown"
    """
    if account:
        return account
    # 优先使用配置中的 account
    wm_account = os.environ.get("WM_ACCOUNT", "")
    if wm_account:
        return wm_account
    # 配置没有再取开发负责人
    if docs_dir:
        assigned_to_path = os.path.join(os.path.expanduser(docs_dir), ".dev-assigned-to")
        try:
            with open(assigned_to_path, "r", encoding="utf-8") as f:
                dev_assigned = f.read().strip()
            if dev_assigned:
                return _clean_assigned_to(dev_assigned)
        except OSError:
            pass
    return "unknown"


def _resolve_run_id(run_id=None, docs_dir=None):
    """按优先级解析 run_id：显式参数 → .run-id 文件 → 环境变量 → unknown。"""
    if run_id:
        return run_id
    if docs_dir:
        run_id_path = os.path.join(os.path.expanduser(docs_dir), ".run-id")
        try:
            with open(run_id_path, "r", encoding="utf-8") as f:
                rid = f.read().strip()
            if rid:
                return rid
        except OSError:
            pass
    return os.environ.get("WM_RUN_ID", "unknown")


def send_and_report(event_name, attrs, docs_dir=None, run_id=None, account=None):
    """发送事件并输出 RESULT。"""
    api_url, secret = _get_config()
    run_id = _resolve_run_id(run_id, docs_dir)
    account = _resolve_account(account, docs_dir)
    payload = _build_event(event_name, attrs, run_id, account)
    code, success = _send_event(payload, api_url, secret)
    if not success:
        _save_fallback(payload, docs_dir)
    emit_result({
        "event": event_name,
        "http_code": code,
        "success": success,
        "fallback_saved": not success,
    })


def cmd_event(args):
    """发送带有自定义属性的通用事件。"""
    attrs = {}
    for pair in (args.attrs or []):
        key, _, val = pair.partition("=")
        attrs[key] = val
    send_and_report(args.name, attrs, docs_dir=args.docs_dir, run_id=args.run_id, account=args.account)


def _record_stage_start_time(docs_dir, stage):
    """记录阶段开始时间到文件。"""
    if not docs_dir:
        return
    os.makedirs(docs_dir, exist_ok=True)
    start_time_path = os.path.join(docs_dir, f".stage-start-{stage}")
    with open(start_time_path, "w", encoding="utf-8") as f:
        f.write(str(int(time.time())))


def _get_stage_elapsed_time(docs_dir, stage):
    """从阶段开始时间文件计算耗时（秒）。"""
    if not docs_dir:
        return 0
    start_time_path = os.path.join(os.path.expanduser(docs_dir), f".stage-start-{stage}")
    try:
        with open(start_time_path, "r", encoding="utf-8") as f:
            start_time = int(f.read().strip())
        return int(time.time()) - start_time
    except (OSError, ValueError):
        return 0


def cmd_stage_start(args):
    """发送 stage.started 事件。"""
    _append_log(args.docs_dir, "INFO", args.stage, "阶段开始")
    _record_stage_start_time(args.docs_dir, args.stage)
    send_and_report(
        "stage.started",
        {"stage": args.stage, "skill": args.skill, "skill_source": "local"},
        docs_dir=args.docs_dir,
        run_id=args.run_id,
        account=args.account,
    )
    _append_log(args.docs_dir, "INFO", args.stage, "WinMetrics event 'stage.started' sent ok")


def cmd_stage_complete(args):
    """发送 stage.completed 事件。"""
    # 自动计算 duration：优先使用传入参数，否则从开始时间计算
    duration = args.duration
    if duration is None or duration <= 0:
        duration = _get_stage_elapsed_time(args.docs_dir, args.stage)
    send_and_report(
        "stage.completed",
        {"stage": args.stage, "status": args.status, "duration_sec": duration},
        docs_dir=args.docs_dir,
        run_id=args.run_id,
    )
    _append_log(args.docs_dir, "INFO", args.stage, f"阶段完成, 状态={args.status}, 耗时={duration}s")
    _append_log(args.docs_dir, "INFO", args.stage, "WinMetrics event 'stage.completed' sent ok")


def cmd_stage_failed(args):
    """发送 stage.completed 事件（status=failed）。"""
    _append_log(args.docs_dir, "ERROR", args.stage, args.error)
    send_and_report(
        "stage.completed",
        {"stage": args.stage, "status": "failed", "error_message": args.error},
        docs_dir=args.docs_dir,
        run_id=args.run_id,
    )


def cmd_pipeline_event(args):
    """发送流水线级别事件。"""
    attrs = {"demand_id": args.demand_id}
    if args.title:
        attrs["demand_title"] = args.title
    if args.product:
        attrs["product"] = args.product
    for pair in (args.attrs or []):
        key, _, val = pair.partition("=")
        attrs[key] = val
    send_and_report(args.name, attrs, docs_dir=args.docs_dir, run_id=args.run_id, account=args.account)
    _append_log(args.docs_dir, "INFO", "准备", f"WinMetrics event '{args.name}' sent ok")

def _get_pipeline_duration(docs_dir):
    """计算流水线总耗时（从最早阶段开始时间到当前）。"""
    if not docs_dir:
        return 0
    docs_path = os.path.expanduser(docs_dir)
    if not os.path.isdir(docs_path):
        return 0

    # 查找所有阶段开始时间文件，取最早的
    start_times = []
    for fname in os.listdir(docs_path):
        if fname.startswith(".stage-start-"):
            try:
                with open(os.path.join(docs_path, fname), "r", encoding="utf-8") as f:
                    ts = int(f.read().strip())
                    start_times.append(ts)
            except (OSError, ValueError):
                continue

    if not start_times:
        return 0

    earliest_start = min(start_times)
    return int(time.time()) - earliest_start


def _get_total_diff(docs_dir):
    """读取 .total-diff 文件内容。"""
    if not docs_dir:
        return ""
    diff_path = os.path.join(os.path.expanduser(docs_dir), ".total-diff")
    try:
        with open(diff_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""




def cmd_summary(args):
    """根据最终状态发送流水线终止事件。"""
    try:
        stages = json.loads(args.stages) if args.stages else []
    except json.JSONDecodeError:
        stages = []

    # "skipped" 表示有意跳过（阶段未启用），应视为正常终态
    # 只有 "failed" 才应触发 fallback
    all_success = all(
        isinstance(s, dict) and s.get("status") in ("success", "skipped")
        for s in stages
    ) if stages else True
    event_name = "pipeline.completed" if all_success else "pipeline.fallback"
    attrs = {"demand_id": args.demand_id}
    if args.product:
        attrs["product"] = args.product

    # 添加流水线总耗时和代码差异统计
        duration = _get_pipeline_duration(args.docs_dir)
        if duration > 0:
            attrs["total_duration_sec"] = duration

        total_diff = _get_total_diff(args.docs_dir)
        if total_diff:
            attrs["total_diff"] = total_diff

    if not all_success:
        failed = [s["name"] for s in stages if isinstance(s, dict) and s.get("status") == "failed"]
        attrs["fallback_reason"] = f"stages failed: {', '.join(failed)}"
    send_and_report(event_name, attrs, docs_dir=args.docs_dir, run_id=args.run_id)


def cmd_retry_fallback(args):
    """重试发送回退文件中所有失败的事件（FIX-58）。"""
    import tempfile
    docs_dir = os.path.expanduser(args.docs_dir)
    fallback_path = os.path.join(docs_dir, ".wm-events.json")
    if not os.path.exists(fallback_path):
        emit_result({"retried": 0})
        return
    api_url, secret = _get_config()
    succeeded = 0
    remaining = []
    with open(fallback_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
                code, ok = _send_event(payload, api_url, secret)
                if ok:
                    succeeded += 1
                else:
                    remaining.append(line)
            except json.JSONDecodeError:
                remaining.append(line)
    # 原子写入：先写临时文件再 rename
    fd, tmp_path = tempfile.mkstemp(dir=docs_dir, suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for line in remaining:
                f.write(line + "\n")
        os.replace(tmp_path, fallback_path)
    except Exception:
        os.unlink(tmp_path)
        raise
    emit_result({"retried": succeeded, "remaining": len(remaining)})


def main():
    parser = argparse.ArgumentParser(description="WinMetrics 事件上报")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("event")
    p.add_argument("--name", required=True)
    p.add_argument("--attrs", nargs="*", default=[])
    p.add_argument("--docs-dir", default=None)
    p.add_argument("--run-id", default=None)
    p.add_argument("--account", default=None)

    p = sub.add_parser("stage-start")
    p.add_argument("--stage", required=True)
    p.add_argument("--skill", required=True)
    p.add_argument("--docs-dir", default=None)
    p.add_argument("--run-id", default=None)
    p.add_argument("--account", default=None)

    p = sub.add_parser("stage-complete")
    p.add_argument("--stage", required=True)
    p.add_argument("--status", required=True)
    p.add_argument("--duration", default=0, type=int, help="阶段耗时(秒)，不传则自动计算")
    p.add_argument("--docs-dir", default=None)
    p.add_argument("--run-id", default=None)

    p = sub.add_parser("stage-failed")
    p.add_argument("--stage", required=True)
    p.add_argument("--error", required=True)
    p.add_argument("--docs-dir", default=None)
    p.add_argument("--run-id", default=None)

    p = sub.add_parser("pipeline-event")
    p.add_argument("--name", required=True)
    p.add_argument("--demand_id", required=True)
    p.add_argument("--docs-dir", default=None)
    p.add_argument("--title", default=None)
    p.add_argument("--product", default=None)
    p.add_argument("--attrs", nargs="*", default=[])
    p.add_argument("--run-id", default=None)
    p.add_argument("--account", default=None)

    p = sub.add_parser("summary")
    p.add_argument("--demand_id", required=True)
    p.add_argument("--stages", default=None)
    p.add_argument("--docs-dir", default=None)
    p.add_argument("--product", default=None)
    p.add_argument("--run-id", default=None)

    p = sub.add_parser("retry-fallback")
    p.add_argument("--docs-dir", required=True)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        "event": cmd_event,
        "stage-start": cmd_stage_start,
        "stage-complete": cmd_stage_complete,
        "stage-failed": cmd_stage_failed,
        "pipeline-event": cmd_pipeline_event,
        "summary": cmd_summary,
        "retry-fallback": cmd_retry_fallback,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
