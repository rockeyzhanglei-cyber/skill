#!/usr/bin/env python3
"""
add-product.py - 从 git clone 命令自动生成 products.yaml 配置

用法:
  python add-product.py                     # 交互模式
  python add-product.py -f commands.txt     # 从文件读取
  python add-product.py -n                  # dry-run, 只输出不写入

交互流程:
  1. 输入产品名称
  2. 粘贴 git clone 命令 (每行一个, 空行结束)
  3. 确认 TFS 项目路径和默认分支
  4. 确认写入
"""

import os
import re
import sys
import shutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib.product_utils import guess_skill, generate_product_yaml, product_exists, remove_product_block

# ---- 路径 ----
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
PRODUCTS_YAML = os.path.join(SKILL_DIR, "templates", "products.yaml")

# ---- 颜色 (兼容 Windows/Max/Linux) ----
def _supports_color():
    if os.name == "nt":
        return os.environ.get("TERM_PROGRAM") in ("vscode",) or \
               os.environ.get("WT_SESSION") is not None or \
               os.environ.get("ConEmuANSI") == "ON"
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

if _supports_color():
    RED = "\033[0;31m"
    GREEN = "\033[0;32m"
    YELLOW = "\033[1;33m"
    CYAN = "\033[0;36m"
    BOLD = "\033[1m"
    NC = "\033[0m"
else:
    RED = GREEN = YELLOW = CYAN = BOLD = NC = ""

def log_info(msg):  print(f"{GREEN}[INFO]{NC} {msg}")
def log_warn(msg):  print(f"{YELLOW}[WARN]{NC} {msg}")
def log_error(msg): print(f"{RED}[ERROR]{NC} {msg}")
def prompt(msg):    return input(f"{CYAN}>>>{NC} {msg} ").strip()


# ============================================================
# 解析 git clone 命令
# ============================================================
# 匹配: .../tfs/{collection}/{project}/_git/{repo}
CLONE_RE = re.compile(
    r"(?:git\s+clone\s+)?"
    r"(?:(?:-b|--branch)\s+(\S+)\s+)?"
    r"(https?://\S+?/tfs/([^/]+/[^/]+)/_git/([^/?#\s]+))"
    r"(?:\s+(?:-b|--branch)\s+(\S+))?"
)

def parse_clone_line(line: str) -> dict | None:
    """解析单条 git clone 命令, 返回 dict 或 None"""
    line = line.strip()
    if not line or line.startswith("#"):
        return None

    m = CLONE_RE.search(line)
    if not m:
        return None

    branch = m.group(1) or m.group(5) or ""
    url = m.group(2)
    tfs_project = m.group(3)
    repo_name = m.group(4)

    return {
        "name": repo_name,
        "url": url,
        "branch": branch,
        "tfs_project": tfs_project,
    }


# ============================================================
# 主流程
# ============================================================
def main():
    import argparse
    parser = argparse.ArgumentParser(description="从 git clone 命令生成 products.yaml 配置")
    parser.add_argument("-f", "--file", help="从文件读取 git clone 命令")
    parser.add_argument("-n", "--dry-run", action="store_true", help="只输出, 不写入文件")
    parser.add_argument("-y", "--yes", action="store_true", help="跳过确认, 直接写入")
    args = parser.parse_args()

    print(f"{BOLD}=== Auto-Dev 产品配置生成器 ==={NC}\n")

    if not os.path.exists(PRODUCTS_YAML):
        template = PRODUCTS_YAML.replace("products.yaml", "products-template.yaml")
        if os.path.exists(template):
            shutil.copy2(template, PRODUCTS_YAML)
            log_info(f"从模板创建: {PRODUCTS_YAML}")
        else:
            with open(PRODUCTS_YAML, "w", encoding="utf-8") as f:
                f.write("\nproducts:\n")
            log_info(f"创建空配置: {PRODUCTS_YAML}")

    # 1. 产品名称
    product_name = prompt("请输入产品名称:")
    if not product_name:
        log_error("产品名称不能为空")
        sys.exit(1)

    existed = product_exists(PRODUCTS_YAML, product_name)
    if existed:
        log_warn(f"产品 '{product_name}' 已存在, 将覆盖 (原配置会备份为 .bak)")

    # 2. 读取 git clone 命令
    raw_lines: list[str] = []
    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            raw_lines = f.readlines()
    else:
        print(f"{CYAN}>>>{NC} 请粘贴 git clone 命令 (每行一个, 空行结束):")
        while True:
            try:
                line = input()
            except EOFError:
                break
            if not line.strip():
                break
            raw_lines.append(line)

    # 3. 解析
    repos: list[dict] = []
    skipped = 0

    for raw in raw_lines:
        parsed = parse_clone_line(raw)
        if not parsed:
            if raw.strip() and not raw.strip().startswith("#"):
                log_warn(f"  跳过(无法解析): {raw.strip()}")
                skipped += 1
            continue

        parsed["skill"] = guess_skill(parsed["name"])
        repos.append(parsed)

    if not repos:
        log_error("没有解析到有效的 git clone 命令")
        sys.exit(1)

    # 推断公共参数
    tfs_project = repos[0]["tfs_project"]
    default_branch = repos[0].get("branch", "")

    # 对齐列显示
    print(f"\n{GREEN}[INFO]{NC} 解析 {len(repos)} 个仓库, {skipped} 个跳过\n")
    name_w = max(len(r["name"]) for r in repos)
    for r in repos:
        print(f"  {r['name']:<{name_w}}  branch={r['branch']:<20} skill={r['skill']}")

    # 4. 确认公共参数
    print(f"\n{GREEN}[INFO]{NC} 自动推断:")
    print(f"  TFS 项目:    {tfs_project}")
    print(f"  默认分支:    {default_branch}")
    print()

    input_tfs = prompt(f"确认 TFS 项目路径 (回车确认, 或输入修改):")
    if input_tfs:
        tfs_project = input_tfs

    input_branch = prompt(f"确认默认分支 (回车确认, 或输入修改):")
    if input_branch:
        default_branch = input_branch
        # 同步所有 repo 的 branch
        for r in repos:
            if not r["branch"]:
                r["branch"] = default_branch

    # 5. 生成 YAML（路径转义由 generate_product_yaml 内部统一处理）
    product_dir = os.getcwd()
    yaml_block = generate_product_yaml(product_name, tfs_project, default_branch, repos, product_dir=product_dir)

    print(f"\n{BOLD}===== 生成的配置 ====={NC}")
    print(yaml_block)
    print(f"{BOLD}======================={NC}\n")

    if args.dry_run:
        log_info("dry-run 模式, 未写入文件")
        return

    # 6. 确认写入
    if not args.yes:
        confirm = prompt("写入 products.yaml? (y/n):").lower()
        if confirm != "y":
            log_info("已取消")
            return

    # 备份
    bak = PRODUCTS_YAML + ".bak"
    shutil.copy2(PRODUCTS_YAML, bak)
    log_info(f"备份: {bak}")

    # 原子写入：先拼接完整内容再一次性写入
    if existed:
        content = remove_product_block(PRODUCTS_YAML, product_name)
        content += yaml_block + "\n"
    else:
        with open(PRODUCTS_YAML, "r", encoding="utf-8") as f:
            content = f.read()
        content += yaml_block + "\n"
    with open(PRODUCTS_YAML, "w", encoding="utf-8") as f:
        f.write(content)

    log_info(f"已写入: {PRODUCTS_YAML}")


if __name__ == "__main__":
    main()
