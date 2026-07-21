#!/usr/bin/env python3
"""
parse-pipeline.py - 解析 pipeline.yaml 并输出配置信息

注意: 本脚本由主代理直接调用读取配置，不走 MCP_CALL/RESULT 协议。
输出使用管道分隔符文本格式供主代理行级解析。

用法:
  python3 parse-pipeline.py stages              # 输出所有阶段（id|name|required|prompt|skills）
  python3 parse-pipeline.py registry            # 输出技能注册表（key|prefix|default）
  python3 parse-pipeline.py skill-map           # 输出技能映射（registry_key → 实际技能名）
  python3 parse-pipeline.py validate            # 校验配置合法性，输出校验结果
  python3 parse-pipeline.py stage <stage_id>    # 输出指定阶段的完整配置
  python3 parse-pipeline.py source              # 输出配置来源（file 或 default）
  python3 parse-pipeline.py skill-info          # 输出各技能详细信息和可替换状态
  python3 parse-pipeline.py count               # 输出阶段总数（仅数字）
  python3 parse-pipeline.py defaults            # 输出内置默认配置（无 pipeline.yaml 时使用）

输出: 管道分隔的文本，每行一条记录
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib.pipeline_utils import validate_config

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 内置默认配置（与 templates/pipeline.yaml 一致）
# 无 pipeline.yaml 文件时使用此配置
DEFAULT_CONFIG = {
    "skill_registry": {
        "pm": {"prefix": "pm", "default": "pm", "replaceable": True, "contract_ref": "skill-contracts.md#pm"},
        "code": {"prefix": "backend-dev", "default": "backend-dev", "replaceable": True, "contract_ref": "skill-contracts.md#code"},
        "frontend": {"prefix": "frontend-dev", "default": "frontend-dev", "replaceable": True, "contract_ref": "skill-contracts.md#frontend"},
        "rdf": {"prefix": "rdf-dev", "default": "rdf-dev", "replaceable": True, "contract_ref": "skill-contracts.md#rdf"},
        "verify": {"prefix": "req-verify", "default": "req-verify", "replaceable": False, "reason": "输出 .verify-status 是 submit 阶段的强依赖"},
        "submit": {"prefix": "git-merge", "default": "git-merge", "replaceable": False, "reason": "提交规范是核心流程，必须关联 Task ID"},
        "pr": {"prefix": "devops-mcp", "default": "devops-mcp", "replaceable": False, "reason": "依赖企业 MCP 服务 create_pr/query_pr_status"},
        "test": {"prefix": "unit-test", "default": "unit-test", "replaceable": True, "contract_ref": "skill-contracts.md#test"},
        "build": {"prefix": "devops-mcp", "default": "devops-mcp", "replaceable": False, "reason": "依赖企业 MCP 服务 build_single_demand"},
        "deploy": {"prefix": "devops-mcp", "default": "devops-mcp", "replaceable": False, "reason": "依赖企业 MCP 服务 trigger_deploy/query_deploy_progress"},
    },
    "stages": [
        {"id": "prepare", "name": "环境准备", "required": True, "prompt": "", "skills": [], "outputs": ["{DOCS_DIR}/auto-dev.log", "{DOCS_DIR}/.deploy-env-id"]},
        {"id": "pm", "name": "需求分析", "required": True, "prompt": "agents/agent-pm.md", "skills": ["pm"], "outputs": ["{DOCS_DIR}/dev-plan.md", "{DOCS_DIR}/.analysis-task-id"]},
        {"id": "code", "name": "编码开发", "required": True, "prompt": "agents/agent-code.md", "skills": ["code", "frontend", "rdf"], "outputs": ["{DOCS_DIR}/summary.md", "{DOCS_DIR}/.task-id"]},
        {"id": "verify", "name": "需求校验", "required": True, "prompt": "agents/agent-verify.md", "skills": ["verify"], "outputs": ["{DOCS_DIR}/verify-report.md", "{DOCS_DIR}/.verify-status", "{DOCS_DIR}/.verify-task-id"]},
        {"id": "submit", "name": "提交+PR", "required": True, "prompt": "", "skills": ["submit", "pr"], "outputs": ["{DOCS_DIR}/.pr-review.md", "{DOCS_DIR}/.test-task-id", "{DOCS_DIR}/.pr-status", "{DOCS_DIR}/.total-diff", "{DOCS_DIR}/.pr-create-failed"]},
        {"id": "build", "name": "构建", "required": False, "prompt": "", "skills": ["build"], "outputs": ["{DOCS_DIR}/.build-status"]},
        {"id": "deploy", "name": "部署", "required": False, "prompt": "", "skills": ["deploy"], "outputs": ["{DOCS_DIR}/.deploy-status", "{DOCS_DIR}/.deploy-step-id"]},
        {"id": "report", "name": "报告通知", "required": True, "prompt": "", "skills": [], "outputs": ["{DOCS_DIR}/ai-report.md"]},
    ]
}


def load_pipeline():
    """加载 pipeline.yaml，不存在则返回默认配置"""
    yaml_path = os.path.join(SKILL_DIR, "templates", "pipeline.yaml")
    if not os.path.exists(yaml_path):
        return DEFAULT_CONFIG, "default"
    try:
        import yaml
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if data and "stages" in data:
            return data, "file"
    except ImportError:
        print("警告: 缺少 PyYAML 库，无法解析 pipeline.yaml，使用内置默认配置", file=sys.stderr)
        pass
    except Exception as e:
        print(f"警告: 解析 pipeline.yaml 失败: {e}，使用默认配置", file=sys.stderr)
    return DEFAULT_CONFIG, "default"


def cmd_stages(config):
    """输出所有阶段: id|name|required|prompt|skills"""
    for s in config.get("stages", []):
        sid = s.get("id", "")
        name = s.get("name", "")
        skills = ",".join(s.get("skills", []))
        prompt = s.get("prompt", "")
        print(f"{sid}|{name}|{s.get('required', False)}|{prompt}|{skills}")


def cmd_registry(config):
    """输出技能注册表: key|prefix|default"""
    for key, val in config.get("skill_registry", {}).items():
        print(f"{key}|{val['prefix']}|{val.get('default', val['prefix'])}")


def cmd_skill_map(config):
    """输出技能映射: registry_key → 实际技能名"""
    registry = config.get("skill_registry", {})
    for key, val in registry.items():
        default_skill = val.get("default", val["prefix"])
        print(f"{key}={default_skill}")


def cmd_validate(config):
    """校验配置合法性"""
    default_registry = DEFAULT_CONFIG.get("skill_registry", {})
    errors, warnings = validate_config(config, SKILL_DIR, default_registry)

    if errors:
        print("❌ 配置校验失败:", file=sys.stderr)
        for e in errors:
            print(f"  FAIL: {e}", file=sys.stderr)
        for w in warnings:
            print(f"  WARN: {w}")
        sys.exit(1)
    else:
        if warnings:
            for w in warnings:
                print(f"WARN: {w}")
        print("✅ 配置校验通过")


def cmd_stage(config, stage_id):
    """输出指定阶段的完整配置"""
    for s in config.get("stages", []):
        if s["id"] == stage_id:
            print(f"id: {s['id']}")
            print(f"name: {s['name']}")
            print(f"required: {s.get('required', False)}")
            print(f"prompt: {s['prompt']}")
            skills = s.get("skills", [])
            print(f"skills: {','.join(skills)}")
            outputs = s.get("outputs", [])
            if outputs:
                print(f"outputs: {','.join(outputs)}")
            return
    print(f"错误: 阶段 '{stage_id}' 未找到", file=sys.stderr)
    sys.exit(1)


def cmd_source(config, source):
    """输出配置来源: file 或 default"""
    print(source)


def cmd_count(config):
    """输出阶段总数（仅数字）"""
    print(len(config.get("stages", [])))


def cmd_defaults(_config):
    """输出内置默认配置"""
    import json
    print(json.dumps(DEFAULT_CONFIG, ensure_ascii=False, indent=2))


def cmd_skill_info(config):
    """输出技能详细信息: registry_key|replaceable|default|prefix|reason|contract_ref"""
    for key, val in config.get("skill_registry", {}).items():
        replaceable = val.get("replaceable", True)  # 默认 true 兼容旧配置
        default_val = val.get("default", val["prefix"])
        prefix = val["prefix"]
        reason = val.get("reason", "")
        contract_ref = val.get("contract_ref", "")
        print(f"{key}|{replaceable}|{default_val}|{prefix}|{reason}|{contract_ref}")


def main():
    if len(sys.argv) < 2:
        print(f"用法: {sys.executable} parse-pipeline.py <command> [args]", file=sys.stderr)
        print("命令: stages, registry, skill-map, skill-info, validate, stage <id>, source, count, defaults", file=sys.stderr)
        sys.exit(1)

    config, source = load_pipeline()

    command = sys.argv[1]
    if command == "stages":
        cmd_stages(config)
    elif command == "registry":
        cmd_registry(config)
    elif command == "skill-map":
        cmd_skill_map(config)
    elif command == "validate":
        cmd_validate(config)
    elif command == "stage":
        if len(sys.argv) < 3:
            print(f"用法: {sys.executable} parse-pipeline.py stage <stage_id>", file=sys.stderr)
            sys.exit(1)
        cmd_stage(config, sys.argv[2])
    elif command == "source":
        cmd_source(config, source)
    elif command == "skill-info":
        cmd_skill_info(config)
    elif command == "count":
        cmd_count(config)
    elif command == "defaults":
        cmd_defaults(config)
    else:
        print(f"未知命令: {command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
