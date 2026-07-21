#!/usr/bin/env python3
"""
stage-helper.py - 阶段生命周期工具。

替代旧版 shared-header.md 中的 _log() bash 函数、STAGE_RESULT 格式化
以及阶段数据文件的读写功能。

Usage:
  python scripts/stage-helper.py init-stage --demand ID --product NAME --stage NAME
  python scripts/stage-helper.py log --log-file PATH --level LEVEL --stage NAME --message MSG
  python scripts/stage-helper.py write-result --docs-dir PATH --stage NAME --status STATUS [--data JSON]
  python scripts/stage-helper.py read-result --docs-dir PATH --stage NAME
  python scripts/stage-helper.py write-status --file PATH --value VALUE
  python scripts/stage-helper.py write-diff --docs-dir PATH
  python scripts/stage-helper.py check-limits --docs-dir PATH [--max-files N] [--max-insertions N]
  python scripts/stage-helper.py check-lock --docs-dir PATH
  python scripts/stage-helper.py format-stage-result --stage NAME --status STATUS [--summary TEXT] [--stage-num N] [--total-stages N]
  python scripts/stage-helper.py generate-report --docs-dir PATH --demand-id ID --template PATH --product NAME
  python scripts/stage-helper.py gen-notify-ext --docs-dir PATH --demand-id ID --type success|fail [--fail-step STEP] [--fail-reason REASON]
"""

import argparse
import json
import os
import re
import sys
import subprocess
import time
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lib"))
from mcp_protocol import emit_result, emit_error


def cmd_init_stage(args):
    """创建阶段目录结构和初始日志文件。"""
    # 路径安全校验：只允许字母、数字、连字符、下划线、点、中文
    _SAFE_NAME_RE = re.compile(r'^[\w.\-]+$')
    for label, value in [("product", args.product), ("demand", args.demand)]:
        if not _SAFE_NAME_RE.match(value):
            emit_error("E003", f"Invalid {label} name (unsafe characters): {value}")
            return
    docs_dir = os.path.expanduser(
        os.path.join("~", "auto-dev-docs", args.product, args.demand)
    )
    os.makedirs(docs_dir, exist_ok=True)
    log_file = os.path.join(docs_dir, "auto-dev.log")
    if not os.path.exists(log_file):
        with open(log_file, "w", encoding="utf-8") as f:
            f.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] [INFO ] [{args.stage}] Stage directory initialized\n")
    emit_result({"docs_dir": docs_dir, "log_file": log_file, "status": "initialized"})


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


def _display_stage(stage):
    return STAGE_DISPLAY_NAMES.get(stage, stage)


def cmd_log(args):
    """向日志文件追加一条日志记录。"""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    level = args.level.ljust(5)
    line = f"[{ts}] [{level}] [{_display_stage(args.stage)}] {args.message}\n"
    with open(args.log_file, "a", encoding="utf-8") as f:
        f.write(line)
    emit_result({"logged": True})


def cmd_write_result(args):
    """写入阶段完成标记文件（无点前缀，按 FIX-01 规范）。"""
    docs_dir = os.path.expanduser(args.docs_dir)
    filename = f"{args.stage}-done.json"
    path = os.path.join(docs_dir, filename)
    data = {"status": args.status, "timestamp": datetime.now().isoformat()}
    if args.verdict:
        data["verdict"] = args.verdict
    if args.data:
        try:
            data["data"] = json.loads(args.data)
        except json.JSONDecodeError:
            data["data"] = args.data
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    emit_result({"file": path, "status": args.status})


def cmd_read_result(args):
    """读取阶段完成标记文件（无点前缀，按 FIX-01 规范）。"""
    docs_dir = os.path.expanduser(args.docs_dir)
    filename = f"{args.stage}-done.json"
    path = os.path.join(docs_dir, filename)
    if not os.path.exists(path):
        emit_error("E003", f"Stage result not found: {args.stage}")
        return
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    emit_result(data)


def cmd_write_status(args):
    """写入流水线状态文件（纯文本，按 FIX-65 规范）。"""
    path = os.path.expanduser(args.file)
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(args.value)
    emit_result({"file": path, "value": args.value})


def cmd_write_diff(args):
    """执行 git diff 统计并写入 .total-diff 文件（按 SKILL.md Step 4.1.1 规范）。"""
    docs_dir = os.path.expanduser(args.docs_dir)
    os.makedirs(docs_dir, exist_ok=True)
    total_diff_path = os.path.join(docs_dir, ".total-diff")

    try:
        # 执行 git diff --shortstat HEAD~1 获取差异统计
        result = subprocess.run(
            ["git", "diff", "--shortstat", "HEAD~1"],
            capture_output=True, text=True, cwd=os.getcwd()
        )
        diff_content = result.stdout.strip()
        if not diff_content:
            # 如果 HEAD~1 不存在（首次提交），尝试与空树比较
            result = subprocess.run(
                ["git", "diff", "--shortstat", "4b825dc642cb6eb9a060e54bf8d69288fbee4904"],
                capture_output=True, text=True, cwd=os.getcwd()
            )
            diff_content = result.stdout.strip()

        # 写入 .total-diff 文件
        with open(total_diff_path, "w", encoding="utf-8") as f:
            f.write(diff_content if diff_content else "0 files changed")

        emit_result({
            "file": total_diff_path,
            "content": diff_content,
            "status": "written"
        })
    except Exception as e:
        emit_error("E003", f"Failed to write diff: {e}")


def cmd_check_limits(args):
    """使用 numstat 检查 git diff 统计是否超出限制（按 FIX-29 规范）。"""
    max_files = args.max_files if args.max_files is not None else 20
    max_insertions = args.max_insertions if args.max_insertions is not None else 500
    try:
        # 检查暂存区（已 staged 的改动）+ 工作区（未 staged 的改动）
        result_staged = subprocess.run(
            ["git", "diff", "--numstat", "--cached"],
            capture_output=True, text=True, cwd=os.getcwd()
        )
        result_unstaged = subprocess.run(
            ["git", "diff", "--numstat"],
            capture_output=True, text=True, cwd=os.getcwd()
        )
        all_lines = (
            [l for l in result_staged.stdout.strip().split("\n") if l.strip()]
            + [l for l in result_unstaged.stdout.strip().split("\n") if l.strip()]
        )
        # 去重（同一文件可能同时出现在 staged 和 unstaged）
        seen = set()
        unique_lines = []
        for line in all_lines:
            fname = line.split("\t")[-1] if "\t" in line else line
            if fname not in seen:
                seen.add(fname)
                unique_lines.append(line)
        files_changed = len(unique_lines)
        total_insertions = 0
        for line in unique_lines:
            parts = line.split()
            if parts and parts[0].isdigit():
                total_insertions += int(parts[0])

        exceeded = files_changed > max_files or total_insertions > max_insertions
        exceeded_reason = None
        reasons = []
        if files_changed > max_files:
            reasons.append(f"files={files_changed}>{max_files}")
        if total_insertions > max_insertions:
            reasons.append(f"insertions={total_insertions}>{max_insertions}")
        if reasons:
            exceeded_reason = ", ".join(reasons)

        emit_result({
            "files_changed": files_changed,
            "total_insertions": total_insertions,
            "max_files": max_files,
            "max_insertions": max_insertions,
            "exceeded": exceeded,
            "exceeded_reason": exceeded_reason,
        })
    except Exception as e:
        emit_error("E003", f"Failed to check limits: {e}")


def cmd_check_lock(args):
    """检查/创建锁文件以防止并发运行（按 FIX-68 规范）。"""
    LOCK_EXPIRE_SECONDS = 1800  # 锁过期时间：30 分钟
    docs_dir = os.path.expanduser(args.docs_dir)
    os.makedirs(docs_dir, exist_ok=True)
    lock_path = os.path.join(docs_dir, ".lock")
    if os.path.exists(lock_path):
        with open(lock_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
        pid = content.split(":")[0] if ":" in content else content
        lock_ts = float(content.split(":")[1]) if ":" in content else 0
        # 检查时间戳过期
        if lock_ts and (time.time() - lock_ts) > LOCK_EXPIRE_SECONDS:
            try:
                os.remove(lock_path)
            except FileNotFoundError:
                pass
        else:
            try:
                pid_int = int(pid)
                os.kill(pid_int, 0)
                emit_error("E002", f"Demand is locked by process {pid}")
                return
            except (OSError, ProcessLookupError, PermissionError):
                # 进程不存在或无权限 → 锁过期，清理旧锁
                try:
                    os.remove(lock_path)
                except FileNotFoundError:
                    pass
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(f"{os.getpid()}:{time.time()}")
    except FileExistsError:
        # 另一个进程在我们清理旧锁后抢先创建了新锁
        emit_error("E002", "Demand is locked by another concurrent process")
        return
    emit_result({"locked": True, "pid": os.getpid()})


def cmd_format_stage_result(args):
    """输出格式化的 STAGE_RESULT 块。"""
    status = args.status
    stage_num = args.stage_num or "?"
    total = args.total_stages or "?"
    lines = ["STAGE_RESULT_START"]

    if status == "success":
        lines.append("STATUS: success")
        lines.append(f"STAGE: {stage_num}/{total}")
        if args.summary:
            lines.append(f"SUMMARY: {args.summary}")
        lines.append("DATA:")
        lines.append("DETAILS:")
    elif status == "failed":
        lines.append("STATUS: failed")
        lines.append(f"STAGE: {stage_num}/{total}")
        if args.summary:
            lines.append(f"FAIL_STEP: {args.summary}")
            lines.append("FAIL_ERROR: see log")
    elif status == "skipped":
        lines.append("STATUS: skipped")
        lines.append(f"STAGE: {stage_num}/{total}")
        if args.summary:
            lines.append(f"SKIP_REASON: {args.summary}")

    lines.append("STAGE_RESULT_END")
    block = "\n".join(lines)
    print(block)
    emit_result({"stage_result_block": block, "status": status})


def cmd_generate_report(args):
    """收集阶段数据并生成 ai-report.md。"""
    docs_dir = os.path.expanduser(args.docs_dir)
    report_path = os.path.join(docs_dir, "ai-report.md")

    sections = []
    sections.append(f"# AI Auto-Dev Report - Requirement #{args.demand_id}\n")
    sections.append(f"**Product**: {args.product}")
    sections.append(f"**Generated**: {datetime.now():%Y-%m-%d %H:%M:%S}\n")

    # 警告文件检查（降级、PR 创建失败）
    alert_files = {
        ".task-degraded": "⚠️ 降级告警",
        ".degradation-reason": "降级原因",
        ".pr-create-failed": "⚠️ PR 创建失败",
        ".pr-review.md": "PR 评审结果",
    }
    for fname, label in alert_files.items():
        fpath = os.path.join(docs_dir, fname)
        if os.path.exists(fpath):
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read().strip()
            if content:
                sections.append(f"- **{label}**: {content[:300]}")

    # 差异统计
    total_diff_path = os.path.join(docs_dir, ".total-diff")
    if os.path.exists(total_diff_path):
        with open(total_diff_path, "r", encoding="utf-8") as f:
            diff_content = f.read().strip()
        if diff_content:
            sections.append(f"\n## 代码差异统计\n{diff_content}")

    data_files = {
        ".pm-status": "开发计划",
        ".code-status": "编码总结",
        ".verify-status": "校验状态",
        ".pr-status": "PR 状态",
        ".build-status": "构建状态",
        ".deploy-status": "部署状态",
        ".unit-test-result": "单元测试结果",
    }
    sections.append("## 阶段状态\n")
    for fname, label in data_files.items():
        fpath = os.path.join(docs_dir, fname)
        if os.path.exists(fpath):
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read().strip()
            sections.append(f"- **{label}**: {content[:200]}")
        else:
            sections.append(f"- **{label}**: (未执行)")

    if args.template and os.path.exists(args.template):
        with open(args.template, "r", encoding="utf-8") as f:
            sections.append(f.read())

    report_content = "\n".join(sections)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_content)

    emit_result({"report_path": report_path, "sections": len(sections)})


def _read_status_file(docs_dir, filename):
    """读取 docs_dir 下的状态文件，返回内容或空字符串。"""
    fpath = os.path.join(docs_dir, filename)
    if os.path.exists(fpath):
        with open(fpath, "r", encoding="utf-8") as f:
            return f.read().strip()
    return ""


def cmd_gen_notify_ext(args):
    """收集阶段状态文件，生成 success-ext.json 或 fail-ext.json 供通知脚本使用。"""
    docs_dir = os.path.expanduser(args.docs_dir)
    notify_type = args.type  # success 或 fail

    ext = {}

    if notify_type == "success":
        # 读取差异统计
        diff_content = _read_status_file(docs_dir, ".total-diff")
        if diff_content:
            import re as _re
            m = _re.search(r'(\d+)\s+files?\s+changed', diff_content)
            if m:
                ext["file_count"] = m.group(1)
            m = _re.search(r'(\d+)\s+insertions?', diff_content)
            if m:
                ext["insertions"] = m.group(1)

        # 读取 PR 状态
        pr_content = _read_status_file(docs_dir, ".pr-status")
        if pr_content:
            try:
                first_line = pr_content.split("\n")[0]
                if "#" in first_line and "=" in first_line:
                    pr_id = first_line.split("#")[1].split("=")[0].strip()
                    if pr_id:
                        ext["pr_id"] = pr_id
            except IndexError:
                pass

        # 读取仓库列表
        repos_content = _read_status_file(docs_dir, ".repos")
        if repos_content:
            first_repo = repos_content.split("\n")[0]
            parts = first_repo.split("|")
            if len(parts) >= 3:
                ext["repo"] = parts[0]
                ext["branch"] = f"feature/{args.demand_id}"
                ext["base_branch"] = parts[2]
                # 从 .repos 提取实际分支名（第3列为 base_branch，feature 分支为 feature/{demand_id}）
                # 多仓库时仍使用 feature/{demand_id} 统一格式

    elif notify_type == "fail":
        ext["fail_step"] = args.fail_step or "未知"
        ext["fail_reason"] = args.fail_reason or "详见TFS工作项评论"

    # 构建阶段状态数组
    stages = []
    # (名称, 文件名, forced状态, 检查模式)
    # 检查模式: "status" = 读取内容匹配状态值, "exists" = 文件存在即成功, "pr" = 多仓库PR状态聚合
    stage_checks = [
        ("环境准备", None, "success", "status"),
        ("需求分析", ".pm-status", None, "status"),
        ("编码开发", ".code-status", None, "status"),
        ("需求校验", ".verify-status", None, "status"),
        ("单元测试", ".unit-test-result", None, "status"),
        ("提交+PR", ".pr-status", None, "pr"),
        ("构建", ".build-status", None, "status"),
        ("部署", ".deploy-status", None, "status"),
        ("报告通知", None, "success", "status"),
    ]
    for name, filename, forced, mode in stage_checks:
        if forced:
            stages.append({"name": name, "status": forced})
            continue
        filepath = os.path.join(docs_dir, filename) if filename else ""
        if mode == "exists":
            # 文件存在即 success，不存在则 skipped
            if os.path.exists(filepath):
                status = "success"
                reason = ""
            else:
                status = "skipped"
                reason = "未执行"
        elif mode == "pr":
            # 解析多仓库 PR 状态: repo#pr_id=status (每行一个仓库)
            content = _read_status_file(docs_dir, filename) if filename else ""
            if not content:
                status = "skipped"
                reason = "未执行"
            else:
                pr_statuses = []
                for line in content.strip().split("\n"):
                    if "=" in line:
                        pr_statuses.append(line.split("=")[-1].strip())
                if not pr_statuses:
                    status = "skipped"
                    reason = "未执行"
                elif all(s in ("success", "review-wait") for s in pr_statuses):
                    status = "success"
                    reason = ""
                elif any(s == "failed" for s in pr_statuses) and not all(s == "failed" for s in pr_statuses):
                    status = "warn"
                    reason = "部分仓库PR失败"
                elif all(s == "failed" for s in pr_statuses):
                    status = "failed"
                    reason = ""
                else:
                    status = "warn"
                    reason = f"未识别的PR状态: {pr_statuses}"
        else:
            # 标准状态文件检查
            content = _read_status_file(docs_dir, filename) if filename else ""
            if not content:
                status = "skipped"
                reason = "未执行"
            elif content.lower() in ("success", "pass"):
                status = "success"
                reason = ""
            elif content.lower() in ("warn", "partial"):
                status = "success"
                reason = content.lower()
            elif content.lower() in ("failed", "fail"):
                status = "failed"
                reason = ""
            else:
                status = "skipped"
                reason = f"未知状态(视同未执行): {content}"
        stages.append({"name": name, "status": status, **({"reason": reason} if reason else {})})

    ext["stages"] = stages

    # 写入 ext.json
    ext_filename = f"{notify_type}-ext.json"
    ext_path = os.path.join(docs_dir, ext_filename)
    with open(ext_path, "w", encoding="utf-8") as f:
        json.dump(ext, f, ensure_ascii=False, indent=2)

    emit_result({"ext_file": ext_path, "type": notify_type, "stages_count": len(stages)})


def main():
    parser = argparse.ArgumentParser(description="阶段生命周期工具")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("init-stage")
    p.add_argument("--demand", required=True)
    p.add_argument("--product", required=True)
    p.add_argument("--stage", required=True)

    p = sub.add_parser("log")
    p.add_argument("--log-file", required=True)
    p.add_argument("--level", default="INFO")
    p.add_argument("--stage", required=True)
    p.add_argument("--message", required=True)

    p = sub.add_parser("write-result")
    p.add_argument("--docs-dir", required=True)
    p.add_argument("--stage", required=True)
    p.add_argument("--status", required=True, choices=["success", "failed", "skipped"])
    p.add_argument("--verdict", default=None, choices=["pass", "warn", "fail"])
    p.add_argument("--data", default=None)

    p = sub.add_parser("read-result")
    p.add_argument("--docs-dir", required=True)
    p.add_argument("--stage", required=True)

    p = sub.add_parser("write-status")
    p.add_argument("--file", required=True)
    p.add_argument("--value", required=True)

    p = sub.add_parser("write-diff")
    p.add_argument("--docs-dir", required=True)

    p = sub.add_parser("check-limits")
    p.add_argument("--docs-dir", default=".")
    p.add_argument("--max-files", type=int, default=None)
    p.add_argument("--max-insertions", type=int, default=None)

    p = sub.add_parser("check-lock")
    p.add_argument("--docs-dir", required=True)

    p = sub.add_parser("format-stage-result")
    p.add_argument("--stage", required=True)
    p.add_argument("--status", required=True, choices=["success", "failed", "skipped"])
    p.add_argument("--summary", default=None)
    p.add_argument("--stage-num", default=None)
    p.add_argument("--total-stages", default=None)

    p = sub.add_parser("generate-report")
    p.add_argument("--docs-dir", required=True)
    p.add_argument("--demand-id", required=True)
    p.add_argument("--template", default=None)
    p.add_argument("--product", required=True)

    p = sub.add_parser("gen-notify-ext")
    p.add_argument("--docs-dir", required=True)
    p.add_argument("--demand-id", required=True)
    p.add_argument("--type", required=True, choices=["success", "fail"])
    p.add_argument("--fail-step", default=None)
    p.add_argument("--fail-reason", default=None)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        "init-stage": cmd_init_stage,
        "log": cmd_log,
        "write-result": cmd_write_result,
        "read-result": cmd_read_result,
        "write-status": cmd_write_status,
        "write-diff": cmd_write_diff,
        "check-limits": cmd_check_limits,
        "check-lock": cmd_check_lock,
        "format-stage-result": cmd_format_stage_result,
        "generate-report": cmd_generate_report,
        "gen-notify-ext": cmd_gen_notify_ext,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
