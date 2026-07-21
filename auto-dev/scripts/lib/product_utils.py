"""
product_utils.py - 产品配置共享工具函数

从 add-product.py / register-product.py 提取的公共逻辑。
"""

import os
import re

from collections import Counter


def guess_skill(name: str) -> str:
    """根据仓库名推断默认技能"""
    lower = name.lower()
    if any(kw in lower for kw in ("rdf", "pango", "pangodesigner")):
        return "rdf-dev"
    if any(kw in lower for kw in ("web", "frontend", "ui", "vue", "react", "ymer", "page", "spa")):
        return "frontend-dev"
    return "backend-dev"


def generate_product_yaml(product_name: str, tfs_project: str,
                          default_branch: str, repos: list,
                          include_worktree: bool = True,
                          product_dir: str = "") -> str:
    """生成产品 YAML 配置块"""
    skill_counts = Counter(r["skill"] for r in repos)
    default_skill = skill_counts.most_common(1)[0][0]

    lines = [f"\n  {product_name}:"]
    if product_dir:
        # 内部统一处理 YAML 双引号字面量的路径转义（Windows 反斜杠）
        escaped_dir = str(product_dir).replace("\\", "\\\\")
        lines.append(f'    product_dir: "{escaped_dir}"  # 产品仓库根目录，auto-dev 自动切换到此目录')
    if include_worktree:
        lines.append(f'    worktree: false              # false=直接在源仓库开发（默认）, true=worktree隔离模式')
    lines += [
        f'    tfs_project: "{tfs_project}"',
        f'    default_skill: "{default_skill}"',
        f'    default_branch: "{default_branch}"',
        f'    deploy_env_id: ""               # 必填: 自动部署目标环境ID（每个产品独立配置）',
        f"    change_limits:                # 可选: 改动量安全阈值（超标则跳过）",
        f"      max_files: 20               # 最大改动文件数",
        f"      max_insertions: 500         # 最大新增行数",
        "",
        "    repos:",
    ]

    for r in repos:
        lines += [
            f'      - name: "{r["name"]}"',
            f'        url: "{r["url"]}"',
            f'        branch: "{r["branch"]}"',
            f'        skill: "{r["skill"]}"',
            f'        tfs_project: "{r["tfs_project"]}"',
            f'        description: ""',
            "",
        ]

    lines += [
        "    skill_routing:",
        '      "AI-BACKEND": "backend-dev"',
        '      "AI-FRONTEND": "frontend-dev"',
        '      "AI-RDF": "rdf-dev"',
        '      "AI-FULLSTACK":',
        '        - "backend-dev"',
        '        - "frontend-dev"',
    ]

    return "\n".join(lines)


def product_exists(yaml_path: str, product_name: str) -> bool:
    """检查产品是否已存在于 YAML 文件中"""
    if not os.path.exists(yaml_path):
        return False
    with open(yaml_path, "r", encoding="utf-8") as f:
        return bool(re.search(rf"^  {re.escape(product_name)}:", f.read(), re.MULTILINE))


def remove_product_block(yaml_path: str, product_name: str) -> str:
    """从 YAML 文件中删除指定产品的配置块，返回剩余内容"""
    with open(yaml_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    result = []
    skip = False
    for line in lines:
        if re.match(rf"^  {re.escape(product_name)}:\s*$", line):
            skip = True
            continue
        if skip:
            stripped = line.rstrip("\n")
            indent = len(stripped) - len(stripped.lstrip())
            # 遇到同级别或更低缩进的非空行结束跳过（注释行也作为边界）
            if indent <= 2 and stripped.strip():
                skip = False
                result.append(line)
        else:
            result.append(line)
    return "".join(result)
