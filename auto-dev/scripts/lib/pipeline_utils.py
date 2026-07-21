"""
pipeline_utils.py - 流水线配置共享工具函数

从 configure-pipeline.py / parse-pipeline.py 提取的公共逻辑。
"""

import sys
import os


def load_yaml(path):
    """加载 YAML 文件"""
    try:
        import yaml
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except ImportError:
        print("错误: 需要 PyYAML，请运行 pip install pyyaml", file=sys.stderr)
        sys.exit(1)


def save_yaml(path, data):
    """保存 YAML 文件"""
    import yaml
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


def validate_config(config, skill_dir, default_registry=None):
    """校验流水线配置，返回 (errors, warnings)

    Args:
        config: pipeline.yaml 解析后的字典
        skill_dir: SKILL_DIR 路径（用于检查 prompt/contract 文件是否存在）
        default_registry: 内置默认技能注册表（用于比较不可替换技能）
    """
    errors = []
    warnings = []
    registry = config.get("skill_registry", {})
    stages = config.get("stages", [])
    prompts_dir = os.path.join(skill_dir, "prompts")
    refs_dir = os.path.join(skill_dir, "references")

    if default_registry is None:
        default_registry = {}

    required_ids = set()
    for i, stage in enumerate(stages):
        sid = stage.get("id", f"<unnamed-{i}>")
        if stage.get("required"):
            required_ids.add(sid)
        prompt = stage.get("prompt", "")
        if prompt:
            prompt_path = os.path.join(prompts_dir, prompt)
            if not os.path.exists(prompt_path):
                errors.append(f"stage[{sid}]: prompt '{prompt}' 不存在")
        for skill_key in stage.get("skills", []):
            if skill_key not in registry:
                errors.append(f"stage[{sid}]: skill key '{skill_key}' 未在 skill_registry 中注册")
            else:
                reg_entry = registry[skill_key]
                default_val = reg_entry.get("default", "")
                prefix = reg_entry.get("prefix", "")
                replaceable = reg_entry.get("replaceable", True)
                reason = reg_entry.get("reason", "")

                if not replaceable:
                    original_default = default_registry.get(skill_key, {}).get("default", prefix)
                    if default_val != original_default:
                        errors.append(f"stage[{sid}]: 技能 '{default_val}' 不可替换 - {reason}")
                else:
                    if default_val and not default_val.startswith(prefix):
                        errors.append(f"stage[{sid}]: skill '{default_val}' 不匹配前缀约束 '{prefix}'")

                contract_ref = reg_entry.get("contract_ref", "")
                if contract_ref:
                    contract_path = os.path.join(refs_dir, contract_ref.split("#")[0])
                    if not os.path.exists(contract_path):
                        warnings.append(f"skill_registry[{skill_key}]: 契约文档 '{contract_ref}' 不存在")

    built_in_required = {"prepare", "pm", "code", "verify", "submit", "report"}
    missing_required = built_in_required - required_ids
    if missing_required:
        warnings.append(f"缺少推荐必选阶段: {missing_required}")

    return errors, warnings
