#!/usr/bin/env python3
"""
wechat-notify.py - 企业微信 Webhook 通知
被 wechat-notify.sh 调用，不直接使用。

用法:
  python wechat-notify.py <消息类型> <产品> <需求号> <标题> <时间戳> <webhook_url> [扩展JSON文件]
"""

import json
import os
import sys
import urllib.request

# 设置标准输出编码为 UTF-8，避免 Windows 环境下的中文乱码
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
os.environ['PYTHONIOENCODING'] = 'utf-8'

if len(sys.argv) < 7:
    print(f"用法: wechat-notify.py <类型> <产品> <需求号> <标题> <时间戳> <webhook_url> [扩展JSON]", file=sys.stderr)
    sys.exit(1)

msg_type = sys.argv[1]
product = sys.argv[2]
task_id = sys.argv[3]
title = sys.argv[4]
timestamp = sys.argv[5]
webhook_url = sys.argv[6]
ext_file = sys.argv[7] if len(sys.argv) > 7 else ""

# 从扩展 JSON 读取字段
ext = {}
if ext_file:
    try:
        with open(ext_file, "r", encoding="utf-8") as f:
            ext = json.load(f)
    except Exception as e:
        print(f"[通知] 读取扩展 JSON 失败 ({ext_file}): {e}", file=sys.stderr)

# 通用字段
repo = ext.get("repo", "")
branch = ext.get("branch", "")
base_branch = ext.get("base_branch", "")
commit = ext.get("commit", "")
pr_url = ext.get("pr_url", "")
pr_id = ext.get("pr_id", "")
file_count = ext.get("file_count", "")
insertions = ext.get("insertions", "")
files_raw = ext.get("files", "")
logics_raw = ext.get("logics", "")
ddl = ext.get("ddl", "")

# fail 专用字段
fail_step = ext.get("fail_step", "")
fail_reason = ext.get("fail_reason", "")

# 阶段执行状态（success/fail 通用）
stages = ext.get("stages", [])

# summary 专用字段
total = ext.get("total", 0)
success_list = ext.get("success_list", [])
skipped_list = ext.get("skipped_list", [])
failed_list = ext.get("failed_list", [])

# start 专用字段（多需求列表）
demand_list = ext.get("demand_list", [])

def parse_lines(raw):
    if not raw:
        return []
    return [l.strip() for l in raw.split("|") if l.strip()]

files = parse_lines(files_raw)
logics = parse_lines(logics_raw)

def build_header(emoji, status_word):
    return (
        f"### {emoji} AI Auto-Dev {status_word}\n\n"
        f"📌 **需求**: <font color=\"comment\">#{task_id}</font> {title}\n"
        f"📦 **产品**: {product}\n"
        f"⏰ **时间**: {timestamp}\n"
    )

STAGE_ICONS = {"success": "✅", "skipped": "⏭️", "failed": "❌"}

def build_stages_body():
    if not stages:
        return ""
    lines = ["\n📋 **流水线执行**\n\n"]
    for s in stages:
        name = s.get("name", "?")
        status = s.get("status", "?")
        icon = STAGE_ICONS.get(status, "❓")
        reason = s.get("reason", "")
        if reason:
            lines.append(f"> {icon} {name} ({reason})\n")
        else:
            lines.append(f"> {icon} {name}\n")
    return "".join(lines)

def build_success_body():
    lines = []
    if repo:
        lines.append(f"📦 **仓库**: `{repo}`\n")
    if branch:
        bd = f"`{branch}` → `{base_branch}`" if base_branch else f"`{branch}`"
        lines.append(f"🌿 **分支**: {bd}\n")
    if commit:
        lines.append(f"📝 **Commit**: `{commit}`\n")
    if pr_url and pr_id:
        lines.append(f"🔗 **PR**: [👉 Pull Request #{pr_id}]({pr_url})\n")
    if file_count or insertions:
        stats = ""
        if file_count:
            stats += f"{file_count} files"
        if insertions:
            stats += f", <font color=\"info\">+{insertions}</font> insertions"
        lines.append(f"📊 **变更**: {stats}\n")

    if files:
        lines.append("\n")
        lines.append(f"📂 **修改文件** ({len(files)}个)\n\n")
        for f in files:
            lines.append(f"> `{f}`\n")

    if logics:
        lines.append("\n")
        lines.append("⚙️ **关键逻辑**\n\n")
        for l in logics:
            lines.append(f"> ✅ {l}\n")

    if ddl:
        lines.append("\n")
        lines.append("⚠️ <font color=\"warning\">**上线前执行 DDL**:</font>\n")
        lines.append(f"> `{ddl}`\n")

    lines.append(build_stages_body())

    return "".join(lines)

def build_fail_body():
    lines = []
    lines.append(build_stages_body())
    if fail_step:
        lines.append(f"❌ **失败步骤**: {fail_step}\n")
    lines.append(f"❌ **失败原因**: {fail_reason if fail_reason else '详见TFS工作项评论'}\n\n")
    lines.append("> ⚠️ 请人工介入处理")
    return "".join(lines)

def build_progress_body():
    return f"> 🔄 {title}"

def build_summary_body():
    lines = []
    lines.append(f"📊 **今日处理**: {total}个需求\n\n")

    if success_list:
        lines.append(f"✅ **成功**: {len(success_list)}个\n")
        for item in success_list:
            tid = item.get("task_id", "?")
            t = item.get("title", "")
            pid = item.get("pr_id", "")
            purl = item.get("pr_url", "")
            if purl and pid:
                lines.append(f"> #{tid} {t} → PR: [Pull Request #{pid}]({purl})\n")
            else:
                lines.append(f"> #{tid} {t} → 已完成\n")
        lines.append("\n")

    if skipped_list:
        lines.append(f"⏭️ **跳过**: {len(skipped_list)}个\n")
        for item in skipped_list:
            tid = item.get("task_id", "?")
            t = item.get("title", "")
            reason = item.get("reason", "未知原因")
            lines.append(f"> #{tid} {t} → {reason}\n")
        lines.append("\n")

    if failed_list:
        lines.append(f"❌ **失败**: {len(failed_list)}个\n")
        for item in failed_list:
            tid = item.get("task_id", "?")
            t = item.get("title", "")
            step = item.get("step", "")
            error = item.get("error", "未知错误")
            step_info = f"{step}: " if step else ""
            lines.append(f"> #{tid} {t} → {step_info}{error}\n")
        lines.append("\n")

    lines.append(f"📁 **详细日志**: 见 TFS 附件或 worktree 目录\n\n")
    lines.append(f"⏰ {timestamp}")

    return "".join(lines)

# 构建消息
TYPE_CONFIG = {
    "start":    ("🚀", "启动通知"),
    "success":  ("🎉", "完成通知"),
    "fail":     ("❌", "失败通知"),
    "progress": ("⏳", "进度通知"),
    "summary":  ("🤖", "每日报告"),
}

if msg_type in TYPE_CONFIG:
    emoji, status_word = TYPE_CONFIG[msg_type]
    content = build_header(emoji, status_word)

    if msg_type == "start":
        if demand_list:
            content += f"📊 **待处理**: {len(demand_list)}个需求\n\n"
            for item in demand_list:
                tid = item.get("task_id", "?")
                t = item.get("title", "")
                p = item.get("product", product)
                content += f"> <font color=\"comment\">#{tid}</font> {t} [{p}]\n"
            content += "\n"
            content += "> 🤖 正在自动接单，请稍候..."
        else:
            content += "> 🤖 正在自动接单，请稍候..."
    elif msg_type == "success":
        content += build_success_body()
    elif msg_type == "fail":
        content += build_fail_body()
    elif msg_type == "progress":
        content += build_progress_body()
    elif msg_type == "summary":
        content += build_summary_body()
else:
    content = f"> {msg_type}: {product} #{task_id}"

# 发送
if not webhook_url:
    print("[通知] 未配置企微Webhook，跳过通知")
    sys.exit(0)

# 安全校验：webhook URL 必须指向企微官方域名
_ALLOWED_DOMAINS = ("qyapi.weixin.qq.com",)
from urllib.parse import urlparse
parsed = urlparse(webhook_url)
if parsed.hostname not in _ALLOWED_DOMAINS:
    print(f"[通知] Webhook URL 域名不合法 ({parsed.hostname})，仅允许企微官方域名", file=sys.stderr)
    sys.exit(1)

payload = json.dumps({"msgtype": "markdown", "markdown": {"content": content}}, ensure_ascii=False).encode("utf-8")
req = urllib.request.Request(webhook_url, data=payload, headers={"Content-Type": "application/json"})
try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        errcode = result.get("errcode", -1)
        if errcode == 0:
            print("[通知] 企业微信通知发送成功 (" + msg_type + ")")
        else:
            print("[通知] 企业微信通知发送失败: " + json.dumps(result, ensure_ascii=False))
except Exception as e:
    print("[通知] 企业微信通知发送失败: " + str(e))
