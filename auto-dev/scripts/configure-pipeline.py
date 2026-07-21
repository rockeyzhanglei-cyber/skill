#!/usr/bin/env python3
"""
configure-pipeline.py - Auto-Dev 流水线交互式配置向导

用法:
  python3 configure-pipeline.py                    # 交互式向导
  python3 configure-pipeline.py --validate         # 校验已有 pipeline.yaml
  python3 configure-pipeline.py --dry-run          # 预览配置不写文件
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib.pipeline_utils import load_yaml, save_yaml, validate_config

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PIPELINE_PATH = os.path.join(SKILL_DIR, "templates", "pipeline.yaml")
TEMPLATE_PATH = os.path.join(SKILL_DIR, "templates", "pipeline-template.yaml")

# 内置默认技能注册表（用于校验不可替换技能）
DEFAULT_REGISTRY = {
    "pm": {"prefix": "pm", "default": "pm"},
    "code": {"prefix": "backend-dev", "default": "backend-dev"},
    "frontend": {"prefix": "frontend-dev", "default": "frontend-dev"},
    "rdf": {"prefix": "rdf-dev", "default": "rdf-dev"},
    "verify": {"prefix": "req-verify", "default": "req-verify"},
    "submit": {"prefix": "git-merge", "default": "git-merge"},
    "pr": {"prefix": "devops-mcp", "default": "devops-mcp"},
    "test": {"prefix": "unit-test", "default": "unit-test"},
    "build": {"prefix": "devops-mcp", "default": "devops-mcp"},
    "deploy": {"prefix": "devops-mcp", "default": "devops-mcp"},
}


def cmd_validate():
    """校验已有 pipeline.yaml"""
    if not os.path.exists(PIPELINE_PATH):
        print(f"错误: {PIPELINE_PATH} 不存在", file=sys.stderr)
        sys.exit(1)

    config = load_yaml(PIPELINE_PATH)
    errors, warnings = validate_config(config, SKILL_DIR, DEFAULT_REGISTRY)

    stages = config.get("stages", [])
    registry = config.get("skill_registry", {})
    prompts_dir = os.path.join(SKILL_DIR, "prompts")
    refs_dir = os.path.join(SKILL_DIR, "references")

    print("=== 流水线配置校验 ===\n")

    for s in stages:
        sid = s["id"]
        sname = s["name"]
        req = "必选" if s.get("required") else "可选"
        prompt = s.get("prompt", "")
        prompt_exists = os.path.exists(os.path.join(prompts_dir, prompt)) if prompt else False

        print(f"[{sid}] {sname} ({req})")
        prompt_status = "✅" if prompt_exists else "❌"
        print(f"  {prompt_status} prompt: {prompt}")

        for skill_key in s.get("skills", []):
            if skill_key in registry:
                reg_entry = registry[skill_key]
                default_val = reg_entry.get("default", skill_key)
                prefix = reg_entry.get("prefix", "")
                replaceable = reg_entry.get("replaceable", True)
                reason = reg_entry.get("reason", "")

                if not replaceable:
                    # 使用 DEFAULT_REGISTRY 获取原始默认值进行比较
                    original_default = DEFAULT_REGISTRY.get(skill_key, {}).get("default", prefix)
                    status = "🔒" if default_val == original_default else "❌"
                    print(f"  {status} skill \"{default_val}\" (不可替换)")
                    if default_val != original_default:
                        print(f"     原因: {reason}")
                        print(f"     建议: 恢复为 '{original_default}'")
                else:
                    if default_val.startswith(prefix):
                        print(f"  ✅ skill \"{default_val}\" (可替换, 前缀匹配)")
                        contract_ref = reg_entry.get("contract_ref", "")
                        if contract_ref:
                            contract_path = os.path.join(refs_dir, contract_ref.split("#")[0])
                            contract_status = "✅" if os.path.exists(contract_path) else "⚠️"
                            print(f"     {contract_status} 契约: references/{contract_ref}")
                    else:
                        print(f"  ❌ skill \"{default_val}\" 不匹配前缀 '{prefix}'")
            else:
                print(f"  ❌ skill key \"{skill_key}\" 未在 registry 中注册")

    print()

    if errors:
        print("❌ 配置校验失败:")
        for e in errors:
            print(f"  FAIL: {e}")
        sys.exit(1)
    else:
        if warnings:
            print("⚠️ 警告:")
            for w in warnings:
                print(f"  WARN: {w}")
        print(f"✅ 校验通过: {len(stages)} 个阶段, {len(registry)} 个技能注册")


def cmd_wizard(dry_run=False):
    """交互式配置向导"""
    print("=== Auto-Dev 流水线配置向导 ===\n")

    # 从模板或现有配置加载
    if os.path.exists(PIPELINE_PATH):
        config = load_yaml(PIPELINE_PATH)
        print("已加载现有 pipeline.yaml 配置\n")
    elif os.path.exists(TEMPLATE_PATH):
        config = load_yaml(TEMPLATE_PATH)
        print("已加载 pipeline-template.yaml 模板\n")
    else:
        print("错误: 未找到 pipeline.yaml 或 pipeline-template.yaml", file=sys.stderr)
        sys.exit(1)

    registry = config.get("skill_registry", {})
    stages = config.get("stages", [])

    # 遍历每个阶段询问
    new_stages = []
    for stage in stages:
        sid = stage["id"]
        sname = stage["name"]
        required = stage.get("required", False)
        skills = stage.get("skills", [])

        print(f"[{sid}] {sname} {'[必选]' if required else '[可选]'}")

        if not required:
            enable = input(f"  是否启用此阶段? (Y/n): ").strip().lower()
            if enable == "n":
                print(f"  -> 已跳过 {sname} 阶段\n")
                continue

        # 技能替换
        for skill_key in skills:
            if skill_key in registry:
                reg_entry = registry[skill_key]
                current_default = reg_entry.get("default", skill_key)
                prefix = reg_entry.get("prefix", "")
                replaceable = reg_entry.get("replaceable", True)
                reason = reg_entry.get("reason", "")
                contract_ref = reg_entry.get("contract_ref", "")

                # 显示 replaceable 状态提示
                if not replaceable:
                    print(f"  ❗ 技能 {skill_key} 不可替换")
                    print(f"     原因: {reason}")
                    print(f"     当前: {current_default} (请勿修改)")
                else:
                    print(f"  ✅ 技能 {skill_key} 可替换 (必须以 '{prefix}' 开头)")
                    if contract_ref:
                        print(f"     契约文档: references/{contract_ref}")
                    new_skill = input(f"     技能名 [{current_default}]: ").strip()
                    if new_skill:
                        if new_skill.startswith(prefix):
                            registry[skill_key]["default"] = new_skill
                            print(f"     OK {new_skill} 前缀校验通过")
                        else:
                            print(f"     FAIL {new_skill} 不匹配前缀 '{prefix}'，保持 {current_default}")

        new_stages.append(stage)
        print()

    config["stages"] = new_stages
    config["skill_registry"] = registry

    # 校验
    errors, warnings = validate_config(config, SKILL_DIR, DEFAULT_REGISTRY)
    if errors:
        print("配置校验失败:")
        for e in errors:
            print(f"  FAIL: {e}")
        print("请修正后重新运行")
        sys.exit(1)

    if warnings:
        for w in warnings:
            print(f"  WARN: {w}")

    # 输出或写入
    if dry_run:
        print("\n=== 配置预览 (--dry-run) ===")
        try:
            import yaml
            print(yaml.dump(config, allow_unicode=True, default_flow_style=False, sort_keys=False))
        except (ImportError, Exception) as e:
            print(f"错误: PyYAML 不可用 ({e})", file=sys.stderr)
            sys.exit(1)
        print("（未写入文件）")
    else:
        save_yaml(PIPELINE_PATH, config)
        print(f"\n=== 配置已写入 {PIPELINE_PATH} ===")
        print("请检查配置: python scripts/configure-pipeline.py --validate")


def main():
    args = sys.argv[1:]
    if "--validate" in args:
        cmd_validate()
    elif "--dry-run" in args:
        cmd_wizard(dry_run=True)
    else:
        cmd_wizard()


if __name__ == "__main__":
    main()
