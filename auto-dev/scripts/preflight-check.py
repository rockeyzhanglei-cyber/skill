#!/usr/bin/env python3
"""
Preflight 环境检测脚本
强制检测 OpenSpec CLI 和 Superpowers skills 是否可用
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


def should_use_shell():
    """判断是否应该使用 shell=True（仅 Windows 需要）"""
    return sys.platform == "win32"


def safe_print(message):
    """安全打印，处理 Windows 控制台编码问题"""
    try:
        print(message)
    except UnicodeEncodeError:
        # Windows GBK 编码无法处理 emoji，替换为 ASCII
        message = message.replace("✅", "[OK]").replace("❌", "[FAIL]")
        print(message.encode(sys.stdout.encoding or 'utf-8', errors='replace').decode(sys.stdout.encoding or 'utf-8', errors='replace'))


def check_openspec_cli():
    """检测 OpenSpec CLI 是否可用"""
    # 尝试 openspec --version
    try:
        result = subprocess.run(
            ["openspec", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            shell=should_use_shell()
        )
        if result.returncode == 0:
            return True, f"OpenSpec CLI 可用: {result.stdout.strip()}"
    except FileNotFoundError:
        pass
    except subprocess.TimeoutExpired:
        pass
    except Exception as e:
        pass

    # 回退到 openspec --help
    try:
        result = subprocess.run(
            ["openspec", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
            shell=should_use_shell()
        )
        if result.returncode == 0:
            return True, "OpenSpec CLI 可用 (--help 成功)"
    except FileNotFoundError:
        return False, "OpenSpec CLI 不存在: 命令 'openspec' 未找到"
    except subprocess.TimeoutExpired:
        return False, "OpenSpec CLI 超时: 执行超时"
    except Exception as e:
        return False, f"OpenSpec CLI 失败: {str(e)}"

    return False, "OpenSpec CLI 不可用: 退出码非 0"


def find_superpowers_dir(skill_dir):
    """查找 Superpowers skills 目录"""
    # 优先环境变量
    env_dir = os.environ.get("SUPERPOWERS_SKILL_DIR")
    if env_dir and Path(env_dir).exists():
        return Path(env_dir)

    # 默认查找路径（按优先级排序）
    candidates = [
        # 插件缓存路径：~/.claude/plugins/cache/*/superpowers（动态匹配任意 marketplace）
        Path.home() / ".claude/plugins/cache",
        # superpowers 插件数据路径
        Path.home() / ".claude/plugins/data/superpowers-claude-plugins-official",
        # 相对于 skill_dir 的路径
        Path(skill_dir) / "../superpowers",
        # 其他常见路径
        Path.home() / ".codex/skills/superpowers",
        Path.home() / ".agents/skills",
    ]

    for base_dir in candidates:
        if not base_dir.exists():
            continue

        # 插件缓存路径特殊处理：glob 匹配 */superpowers
        if base_dir.name == "cache" and base_dir.parent.name == "plugins":
            for marketplace_dir in base_dir.glob("*"):
                superpowers_base = marketplace_dir / "superpowers"
                if not superpowers_base.exists():
                    continue
                # 查找版本化的 skills 目录（如 5.0.5/skills）
                version_dirs = sorted(superpowers_base.glob("*/skills"), key=lambda p: p.parent.name, reverse=True)
                if version_dirs:
                    return version_dirs[0]  # 返回最新版本

        # 其他路径：查找版本化目录或直接的 skills 目录
        version_dirs = sorted(base_dir.glob("*/skills"), key=lambda p: p.name, reverse=True)
        if version_dirs:
            return version_dirs[0]  # 返回最新版本
        skills_dir = base_dir / "skills"
        if skills_dir.exists():
            return skills_dir

    return None


def check_superpowers_skills(skill_dir):
    """检测 Superpowers 关键技能是否存在"""
    superpowers_dir = find_superpowers_dir(skill_dir)

    if not superpowers_dir:
        return False, "Superpowers skills 目录不存在"

    required_skills = [
        "test-driven-development",
        "systematic-debugging",
        "requesting-code-review",
        "verification-before-completion",
    ]

    missing = []
    for skill in required_skills:
        skill_file = superpowers_dir / skill / "SKILL.md"
        if not skill_file.exists():
            missing.append(skill)

    if missing:
        return False, f"Superpowers 关键技能缺失: {', '.join(missing)}"

    return True, f"Superpowers skills 可用: {superpowers_dir}"


def main():
    parser = argparse.ArgumentParser(description="Preflight 环境检测")
    parser.add_argument("--skill-dir", required=True, help="auto-dev skill 目录路径")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    args = parser.parse_args()

    skill_dir = Path(args.skill_dir).resolve()

    # 检测 OpenSpec
    openspec_ok, openspec_msg = check_openspec_cli()

    # 检测 Superpowers
    superpowers_ok, superpowers_msg = check_superpowers_skills(skill_dir)

    # 判断总体结果
    all_ok = openspec_ok and superpowers_ok

    if args.json:
        import json
        result = {
            "status": "pass" if all_ok else "fail",
            "openspec": {
                "available": openspec_ok,
                "message": openspec_msg
            },
            "superpowers": {
                "available": superpowers_ok,
                "message": superpowers_msg
            }
        }
        print(json.dumps(result, indent=2))
    else:
        safe_print(f"[Preflight] OpenSpec: {openspec_msg}")
        safe_print(f"[Preflight] Superpowers: {superpowers_msg}")
        if all_ok:
            safe_print("[Preflight] ✅ 环境检测通过")
        else:
            safe_print("[Preflight] ❌ 环境检测失败，流水线终止")

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()