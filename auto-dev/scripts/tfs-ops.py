#!/usr/bin/env python3
"""
tfs-ops.py - TFS 工作项操作参数准备与结果解析。

输出 tfs-mcp 工具的 MCP_CALL 指令。主代理执行 MCP 调用并将结果
写入文件，本脚本随后解析该文件。

Usage:
  python scripts/tfs-ops.py validate-connection [--collection COL]
  python scripts/tfs-ops.py get-workitem --id ID [--collection COL]
  python scripts/tfs-ops.py create-task --parent ID --title TITLE [--type TYPE] [--project PROJ] [...]
  python scripts/tfs-ops.py update-state --id ID --state STATE [--reason REASON] [--collection COL]
  python scripts/tfs-ops.py add-tags --id ID --tags TAG1,TAG2 [--collection COL]
  python scripts/tfs-ops.py add-comment --id ID --comment TEXT [--collection COL]
  python scripts/tfs-ops.py upload-attachment --id ID --file PATH [--collection COL]
  python scripts/tfs-ops.py download-attachments --id ID --dest DIR [--target-dir DIR] [--collection COL]
  python scripts/tfs-ops.py get-relations --id ID [--collection COL]
  python scripts/tfs-ops.py list-attachments --id ID [--collection COL]
  python scripts/tfs-ops.py update-workitem --id ID --fields JSON [--comment TEXT] [--collection COL]
  python scripts/tfs-ops.py parse-<command> --result-file PATH
"""

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lib"))
from mcp_protocol import (
    emit_mcp_call, emit_result, emit_error, read_result_file, read_result_stdin,
    _parse_json_robust,
)


def _collection(args):
    return getattr(args, "collection", None) or os.environ.get("DEMAND_COLLECTION", "")


def _clean_assigned_to(raw):
    """Normalize TFS System.AssignedTo into DOMAIN\\username format.

    TFS returns various formats; API requires single-backslash domain account.
    Extracts uniqueName from angle brackets, normalizes \\\\ to \\.
    """
    if not raw:
        return ""

    # Dict format (TFS API sometimes returns structured object)
    if isinstance(raw, dict):
        unique = raw.get("uniqueName", "")
        if unique:
            return unique.replace("\\\\", "\\")
        return ""

    s = str(raw).strip()
    if not s:
        return ""

    # Extract uniqueName from angle brackets: "c_xp(晁兴鹏) <WINNING\\c_xp>" -> "WINNING\\c_xp"
    bracket_match = re.search(r'<([^>]+)>', s)
    if bracket_match:
        unique = bracket_match.group(1)
        return unique.replace("\\\\", "\\")

    # No brackets — normalize double backslash to single
    return s.replace("\\\\", "\\")


def _read_fields(args):
    """读取字段 JSON：支持 --fields-stdin 或 --fields。"""
    if getattr(args, "fields_stdin", False):
        raw = sys.stdin.read()
        if not raw or not raw.strip():
            return None
        try:
            return _parse_json_robust(raw)
        except json.JSONDecodeError as e:
            emit_error("E003", f"Invalid fields JSON from stdin: {e}")
    if args.fields:
        try:
            return json.loads(args.fields)
        except json.JSONDecodeError:
            emit_error("E003", f"Invalid fields JSON: {args.fields}")
    return None


def cmd_validate_connection(args):
    col = _collection(args)
    params = {}
    if col:
        params["collection"] = col
    emit_mcp_call("mcp__tfs-mcp__tfs_get_current_collection", params)


def cmd_get_workitem(args):
    # FIX-46: id as int, not string
    params = {"id": args.id}
    col = _collection(args)
    if col:
        params["collection"] = col
    emit_mcp_call("mcp__tfs-mcp__tfs_get_workitem", params)


def cmd_create_task(args):
    # FIX-47: 仅包含非空的可选参数
    params = {
        "workItemType": args.type or "Task",
        "title": args.title,
        "parentWorkItemId": args.parent,
    }
    if args.project:
        params["project"] = args.project
    if args.assigned_to:
        params["assignedTo"] = _clean_assigned_to(args.assigned_to)
    if args.iteration_path:
        params["iterationPath"] = args.iteration_path
    if args.area_path:
        params["areaPath"] = args.area_path
    col = _collection(args)
    if col:
        params["collection"] = col
    fields_data = _read_fields(args)
    if fields_data:
        params["fields"] = fields_data
    emit_mcp_call("mcp__tfs-mcp__tfs_create_workitem", params)


def cmd_update_state(args):
    params = {"id": args.id, "state": args.state}
    if args.reason:
        params["reason"] = args.reason
    col = _collection(args)
    if col:
        params["collection"] = col
    emit_mcp_call("mcp__tfs-mcp__tfs_change_state", params)


def cmd_add_tags(args):
    # FIX-11: 将逗号分隔的 CLI 输入转换为 TFS 所需的分号分隔格式
    tags = args.tags.replace(",", ";")
    params = {"id": args.id, "tags": tags}
    col = _collection(args)
    if col:
        params["collection"] = col
    emit_mcp_call("mcp__tfs-mcp__tfs_add_tags", params)


def cmd_add_comment(args):
    params = {"id": args.id, "comment": args.comment}
    col = _collection(args)
    if col:
        params["collection"] = col
    emit_mcp_call("mcp__tfs-mcp__tfs_add_comment", params)


def cmd_upload_attachment(args):
    params = {"id": args.id, "filePath": os.path.abspath(args.file)}
    col = _collection(args)
    if col:
        params["collection"] = col
    emit_mcp_call("mcp__tfs-mcp__tfs_upload_attachment", params)


def cmd_download_attachments(args):
    params = {"id": args.id, "targetDir": os.path.abspath(args.dest)}
    col = _collection(args)
    if col:
        params["collection"] = col
    emit_mcp_call("mcp__tfs-mcp__tfs_download_attachments", params)


def cmd_get_relations(args):
    params = {"id": args.id, "relationType": "children"}
    col = _collection(args)
    if col:
        params["collection"] = col
    emit_mcp_call("mcp__tfs-mcp__tfs_get_relations", params)


def cmd_list_attachments(args):
    params = {"id": args.id}
    col = _collection(args)
    if col:
        params["collection"] = col
    emit_mcp_call("mcp__tfs-mcp__tfs_list_attachments", params)


def cmd_update_workitem(args):
    params = {"id": args.id}
    updates = _read_fields(args)
    if not updates:
        emit_error("E003", "update-workitem requires --fields or --fields-stdin")
    params["updates"] = updates
    if args.comment:
        params["comment"] = args.comment
    col = _collection(args)
    if col:
        params["collection"] = col
    emit_mcp_call("mcp__tfs-mcp__tfs_update_workitem", params)


# --- 结果解析器 ---

def _read_result(args):
    """统一读取结果：支持 --result-file 和 --result-stdin。"""
    if getattr(args, "result_stdin", False):
        return read_result_stdin()
    return read_result_file(args.result_file)


def cmd_parse_get_workitem(args):
    data = _read_result(args)
    if not data:
        emit_error("E003", "No result data")
    item = data if isinstance(data, dict) else {"raw": data}
    result = {
        "id": item.get("id", ""),
        "title": item.get("title", item.get("System.Title", "")),
        "tags": item.get("tags", item.get("System.Tags", "")),
        "state": item.get("state", item.get("System.State", "")),
        "project": item.get("project", item.get("System.TeamProject", "")),
        "areaPath": item.get("areaPath", item.get("System.AreaPath", "")),
        "iterationPath": item.get("iterationPath", item.get("System.IterationPath", "")),
        "assignedTo": _clean_assigned_to(item.get("assignedTo", item.get("System.AssignedTo", ""))),
        "module_name": item.get("Winning.Module.name", ""),
    }
    emit_result(result)


def cmd_parse_create_task(args):
    data = _read_result(args)
    if not data:
        emit_error("E003", "No result data")
    if not isinstance(data, dict):
        emit_error("E003", f"Unexpected result type: {type(data).__name__}")
    task_id = data.get("id", data.get("work_item_id", ""))
    if not task_id:
        emit_error("E003", f"Task creation failed: {json.dumps(data, ensure_ascii=False)}")
    emit_result({"task_id": str(task_id), "success": True})


def cmd_parse_generic(args):
    data = _read_result(args)
    if not data:
        emit_error("E003", "No result data")
    # 仅检查明确的错误字段，不检查 message（message 可能含正常信息）
    if isinstance(data, dict):
        err = data.get("error")
        if err:
            emit_result({"success": False, "error": str(err), "raw": data})
            return
    emit_result({"success": True, "raw": data})


def _add_common_args(p):
    p.add_argument("--collection", default=None)


def main():
    parser = argparse.ArgumentParser(description="TFS 工作项操作")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("validate-connection")
    _add_common_args(p)

    p = sub.add_parser("get-workitem")
    p.add_argument("--id", required=True, type=int)
    _add_common_args(p)

    p = sub.add_parser("create-task")
    p.add_argument("--parent", required=True, type=int)
    p.add_argument("--title", required=True)
    p.add_argument("--type", default="Task")
    p.add_argument("--project", default=None)
    p.add_argument("--assigned-to", default=None)
    p.add_argument("--iteration-path", default=None)
    p.add_argument("--area-path", default=None)
    p.add_argument("--fields", default=None)
    p.add_argument("--fields-stdin", action="store_true", default=False)
    _add_common_args(p)

    p = sub.add_parser("update-state")
    p.add_argument("--id", required=True, type=int)
    p.add_argument("--state", required=True)
    p.add_argument("--reason", default=None)
    _add_common_args(p)

    p = sub.add_parser("add-tags")
    p.add_argument("--id", required=True, type=int)
    p.add_argument("--tags", required=True, help="逗号分隔，自动转换为分号")
    _add_common_args(p)

    p = sub.add_parser("add-comment")
    p.add_argument("--id", required=True, type=int)
    p.add_argument("--comment", required=True)
    _add_common_args(p)

    p = sub.add_parser("upload-attachment")
    p.add_argument("--id", required=True, type=int)
    p.add_argument("--file", required=True)
    _add_common_args(p)

    p = sub.add_parser("download-attachments")
    p.add_argument("--id", required=True, type=int)
    p.add_argument("--dest", "--target-dir", required=True)
    _add_common_args(p)

    p = sub.add_parser("get-relations")
    p.add_argument("--id", required=True, type=int)
    _add_common_args(p)

    p = sub.add_parser("list-attachments")
    p.add_argument("--id", required=True, type=int)
    _add_common_args(p)

    p = sub.add_parser("update-workitem")
    p.add_argument("--id", required=True, type=int)
    p.add_argument("--fields", default=None)
    p.add_argument("--fields-stdin", action="store_true", default=False)
    p.add_argument("--comment", default=None)
    _add_common_args(p)

    # 解析结果子命令：支持 --result-file 或 --result-stdin（二选一）
    for cmd_name in ["get-workitem", "create-task", "update-state", "add-tags",
                     "add-comment", "upload-attachment", "download-attachments",
                     "get-relations", "list-attachments", "update-workitem"]:
        p = sub.add_parser(f"parse-{cmd_name}")
        p.add_argument("--result-file", default=None)
        p.add_argument("--result-stdin", action="store_true", default=False)

    p = sub.add_parser("parse-validate-connection")
    p.add_argument("--result-file", default=None)
    p.add_argument("--result-stdin", action="store_true", default=False)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    parsers = {
        "parse-get-workitem": cmd_parse_get_workitem,
        "parse-create-task": cmd_parse_create_task,
    }
    generic_parse_cmds = [
        "parse-validate-connection", "parse-update-state", "parse-add-tags",
        "parse-add-comment", "parse-upload-attachment", "parse-download-attachments",
        "parse-get-relations", "parse-list-attachments", "parse-update-workitem",
    ]

    if args.command in parsers:
        parsers[args.command](args)
        return
    if args.command in generic_parse_cmds:
        cmd_parse_generic(args)
        return

    commands = {
        "validate-connection": cmd_validate_connection,
        "get-workitem": cmd_get_workitem,
        "create-task": cmd_create_task,
        "update-state": cmd_update_state,
        "add-tags": cmd_add_tags,
        "add-comment": cmd_add_comment,
        "upload-attachment": cmd_upload_attachment,
        "download-attachments": cmd_download_attachments,
        "get-relations": cmd_get_relations,
        "list-attachments": cmd_list_attachments,
        "update-workitem": cmd_update_workitem,
    }
    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
