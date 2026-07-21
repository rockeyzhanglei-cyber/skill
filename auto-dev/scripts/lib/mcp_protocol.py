"""
mcp_protocol.py - 共享 MCP_CALL 协议工具库。

各脚本通过标准输出输出 MCP_CALL 指令。主代理解析这些指令，
执行 MCP 调用，将结果写入临时文件，并通过 --result-file 回传以供解析。

输出格式:
  MCP_CALL: <tool_name> <json_params>
  MCP_CALL_POLL: <tool_name> <json_params>
    interval=<sec> max_attempts=<n> terminal_states=[<state>,...]
    on_success=<action> on_timeout=<action> initial_wait=<sec>
  DRY_RUN: <tool_name> <json_params>
  RESULT: <json>
"""

import json
import os
import re
import sys
import tempfile


def emit_mcp_call(tool_name, params):
    """输出单条 MCP_CALL 指令。"""
    params_json = json.dumps(params, ensure_ascii=False)
    print(f"MCP_CALL: {tool_name} {params_json}", flush=True)


def emit_mcp_call_poll(tool_name, params, interval, max_attempts,
                       terminal_states, on_success="continue",
                       on_timeout="fail_stage", initial_wait=0):
    """输出带有轮询参数的 MCP_CALL_POLL 指令。"""
    params_json = json.dumps(params, ensure_ascii=False)
    states_str = json.dumps(terminal_states)
    print(f"MCP_CALL_POLL: {tool_name} {params_json}", flush=True)
    print(f"  interval={interval} max_attempts={max_attempts}"
          f" terminal_states={states_str}"
          f" on_success={on_success} on_timeout={on_timeout}"
          f" initial_wait={initial_wait}", flush=True)


def emit_dry_run(tool_name, params):
    """在 dry-run 模式下，打印将要调用的内容但不实际执行。"""
    params_json = json.dumps(params, ensure_ascii=False, indent=2)
    print(f"DRY_RUN: {tool_name} {params_json}", flush=True)
    emit_result({"dry_run": True, "tool": tool_name, "params": params})


def emit_result(data):
    """输出带有结构化数据的 RESULT 行。"""
    print(f"RESULT: {json.dumps(data, ensure_ascii=False)}", flush=True)


def emit_error(code, message, details=None):
    """输出带有正确退出码的错误 RESULT。"""
    data = {"error_code": code, "error_message": message}
    if details:
        data["details"] = details
    print(f"RESULT: {json.dumps(data, ensure_ascii=False)}", flush=True)
    # E001=可重试(1), E002=需要确认(2), E003=致命错误(3)
    exit_map = {"E001": 1, "E002": 2, "E003": 3}
    sys.exit(exit_map.get(code, 3))


def _repair_json(raw_text):
    """修复常见的 JSON 转义问题（宿主代理通过 heredoc 写入时反斜杠丢失）。

    仅在首次 json.loads 失败时调用。
    """
    # JSON 合法转义：\" \\ \/ \b \f \n \r \t \uXXXX
    # 将 \X（X 不是上述字符）替换为 \\X
    return re.sub(
        r'\\([^"\\/bfnrtu])',
        lambda m: '\\\\' + m.group(1),
        raw_text,
    )


def _parse_json_robust(raw_text):
    """尝试解析 JSON，失败时自动修复重试。"""
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        pass
    repaired = _repair_json(raw_text)
    try:
        return json.loads(repaired)
    except json.JSONDecodeError as e:
        raise e


def read_result_file(path):
    """读取并解析主代理写入的结果文件。

    返回 None 表示文件不存在或 JSON 损坏（后者会通过 stderr 输出诊断）。
    """
    if not path or not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read()
        return _parse_json_robust(raw)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"[WARN] 结果文件 JSON 损坏: {path}: {e}", file=sys.stderr, flush=True)
        return None


def read_result_stdin():
    """从 stdin 读取并解析主代理传入的 JSON 结果。

    用于 --result-stdin 模式，避免临时文件路径问题。
    返回 None 表示 stdin 为空或 JSON 损坏。
    """
    raw = sys.stdin.read()
    if not raw or not raw.strip():
        return None
    try:
        return _parse_json_robust(raw)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"[WARN] stdin JSON 损坏: {e}", file=sys.stderr, flush=True)
        return None


def write_result_file(path, data):
    """将结构化数据写入结果文件供脚本解析。"""
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_temp_result_path(prefix="mcp_result"):
    """生成用于结果传递的临时文件路径（供宿主代理调用，非脚本内部使用）。"""
    fd, path = tempfile.mkstemp(suffix=".json", prefix=prefix)
    os.close(fd)
    return path


def load_config_env(skill_dir):
    """加载 config.env 中的变量到 os.environ（仅在未设置时）。"""
    config_path = os.path.join(skill_dir, "config.env")
    if not os.path.exists(config_path):
        return
    with open(config_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export "):]
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                # 去除行内注释（如 KEY=value # comment）
                if " #" in value or "\t#" in value:
                    value = value.split("#", 1)[0].rstrip()
                if key not in os.environ:
                    os.environ[key] = value
