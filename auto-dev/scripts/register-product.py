#!/usr/bin/env python3
"""
register-product.py - 从本地仓库扫描结果注册新产品到 products.yaml

用法:
  python register-product.py --name <产品名> --repos '<JSON数组>'
  python register-product.py --name <产品名> --repos-file <文件路径>
"""

import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib.product_utils import guess_skill, generate_product_yaml, product_exists, remove_product_block

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
PRODUCTS_YAML = os.path.join(SKILL_DIR, "templates", "products.yaml")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="注册本地产品到 products.yaml")
    parser.add_argument("--name", required=True, help="产品名称")
    parser.add_argument("--repos", help="仓库 JSON 数组字符串")
    parser.add_argument("--repos-file", help="仓库 JSON 数组文件路径")
    args = parser.parse_args()

    if not args.repos and not args.repos_file:
        print("错误: 必须提供 --repos 或 --repos-file", file=sys.stderr)
        sys.exit(1)

    if args.repos_file:
        with open(args.repos_file, "r", encoding="utf-8") as f:
            repos = json.load(f)
    else:
        repos = json.loads(args.repos)

    if not repos:
        print("错误: 仓库列表为空", file=sys.stderr)
        sys.exit(1)

    # 补充默认 skill
    for r in repos:
        if "skill" not in r or not r["skill"]:
            r["skill"] = guess_skill(r["name"])

    product_name = args.name
    tfs_project = repos[0].get("tfs_project", "")
    default_branch = repos[0].get("branch", "master")

    # 确保 products.yaml 存在
    if not os.path.exists(PRODUCTS_YAML):
        with open(PRODUCTS_YAML, "w", encoding="utf-8") as f:
            f.write("products:\n")

    # 检查是否已存在
    existed = product_exists(PRODUCTS_YAML, product_name)
    if existed:
        print(f"警告: 产品 '{product_name}' 已存在，将覆盖", file=sys.stderr)

    # 备份
    bak = PRODUCTS_YAML + ".bak"
    shutil.copy2(PRODUCTS_YAML, bak)

    # 原子写入：先拼接完整内容再一次性写入（路径转义由 generate_product_yaml 内部统一处理）
    product_dir = os.getcwd()
    yaml_block = generate_product_yaml(product_name, tfs_project, default_branch, repos, product_dir=product_dir)
    if existed:
        content = remove_product_block(PRODUCTS_YAML, product_name)
        content += yaml_block + "\n"
    else:
        with open(PRODUCTS_YAML, "r", encoding="utf-8") as f:
            content = f.read()
        content += yaml_block + "\n"
    with open(PRODUCTS_YAML, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"OK: 产品 '{product_name}' 已注册 ({len(repos)} 个仓库)")


if __name__ == "__main__":
    main()
