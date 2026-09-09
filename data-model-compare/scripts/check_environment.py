#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""环境检查（只读，不安装、不改配置）

状态定义：
  ready       核心依赖齐全，直接开始
  partial     核心可用，部分可选功能降级（见输出）
  needs_setup 有必需依赖缺失（按提示安装后重跑本脚本）

用法: python3 scripts/check_environment.py
"""
import json
import os
import shutil
import subprocess
import sys

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEPS_FILE = os.path.join(SKILL_DIR, 'skill-dependencies.json')

PY_MIN = (3, 8)


def check_import(mod):
    try:
        __import__(mod)
        return True, None
    except Exception as e:
        return False, str(e)[:80]


def check_python():
    ok = sys.version_info >= PY_MIN
    return ok, f"Python {sys.version_info.major}.{sys.version_info.minor}"


def main():
    with open(DEPS_FILE, 'r', encoding='utf-8') as f:
        spec = json.load(f)

    passed, missing_required, missing_optional = [], [], []

    # runtime
    ok, ver = check_python()
    (passed if ok else missing_required).append(('python-runtime', ver if ok else 'Python < 3.8'))

    # pip 包（pip 包名 → import 模块名，不一致的在此映射）
    PIP_TO_IMPORT = {
        'pyyaml': 'yaml',
        'python-docx': 'docx',
        'pdfplumber': 'pdfplumber',
    }
    for dep in spec.get('dependencies', []):
        if dep['id'] == 'python-runtime':
            continue
        mod = PIP_TO_IMPORT.get(dep['id'], dep['id'].replace('-', '_'))
        ok, err = check_import(mod)
        if ok:
            passed.append((dep['id'], 'ok'))
        elif dep['required']:
            missing_required.append((dep['id'], err))
        else:
            missing_optional.append((dep['id'], dep['capabilities'][0]))

    # 环境变量（可选）
    env_status = []
    for env in spec.get('environment_variables', []):
        set_ = bool(os.environ.get(env['name']))
        env_status.append((env['name'], set_))

    # 状态判定
    if missing_required:
        status = 'needs_setup'
    elif missing_optional:
        status = 'partial'
    else:
        status = 'ready'

    print(f"环境检查结果: {status}")
    print(f"  已通过: {', '.join(name for name, _ in passed) or '（无）'}")
    if missing_required:
        print(f"  缺失必需项（安装后重检）: {', '.join(name for name, _ in missing_required)}")
        print("  安装命令: pip install " + ' '.join(name for name, _ in missing_required))
    if missing_optional:
        print("  缺失可选项（功能降级）:")
        for name, cap in missing_optional:
            print(f"    - {name}: 影响「{cap}」")
    unset = [name for name, s in env_status if not s]
    print(f"  环境变量: 已设置 {[n for n, s in env_status if s] or '（无）'}；未设置 {unset or '（无）'}（均为可选，用途见 skill-dependencies.json）")

    sys.exit({'ready': 0, 'partial': 0, 'needs_setup': 1}[status])


if __name__ == '__main__':
    main()
