#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
静态检查：找出模块中"未定义的名字"（拆分重构后的依赖漏带守卫）

为什么需要它
------------
golden baseline（端到端回归）只能保证**被数据触发到的代码路径**行为不变，
保证不了 100% 代码覆盖。P1-2 拆分时就出现过：

    方法从大类迁到新模块后忘了带 `import re`，但该分支在 V6.0 数据集上
    未被触发，端到端回归照样全绿，直到后续调用才暴露 NameError。

本脚本用 AST 静态扫描，不依赖运行，能提前发现这类"潜伏的缺失依赖"。

用法
----
    # 检查 matchers/ 下所有模块
    python scripts/check_undefined_names.py

    # 检查指定文件
    python scripts/check_undefined_names.py matchers/auto_relation.py

退出码
------
    0 = 无未定义名字    1 = 发现问题
"""

import ast
import builtins
import os
import sys

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 模块级内置名（__file__ 等），不算"未定义"
MODULE_DUNDERS = {'__file__', '__name__', '__doc__', '__package__',
                  '__spec__', '__loader__', '__builtins__', '__path__',
                  '__all__', '__version__', '__author__'}
BUILTIN = set(dir(builtins)) | MODULE_DUNDERS


def collect_defined(tree):
    """模块级定义的名字（函数/类/常量/import）。

    注意用 ast.walk 而非只扫 tree.body：有些模块的 import 写在
    try/except 兼容链里（如 self_validator 为兼容不同加载方式做的
    三级 import），只扫顶层会误报。
    """
    names = set()
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(n.name)
        elif isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name):
                    names.add(t.id)
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
            names.add(n.target.id)
    # 全局收集 import（含 try/except 内的兼容导入）
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                names.add(a.asname or a.name.split('.')[0])
        elif isinstance(n, ast.ImportFrom):
            for a in n.names:
                names.add(a.asname or a.name)
    return names


def collect_local(tree):
    """各函数作用域内的局部名（参数/赋值/嵌套定义/except/内部 import）。"""
    names = set()
    for fn in ast.walk(tree):
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            args = getattr(fn, 'args', None)
            if args is not None:
                names |= {x.arg for x in list(args.posonlyargs)
                          + list(args.args) + list(args.kwonlyargs)}
                if args.vararg:
                    names.add(args.vararg.arg)
                if args.kwarg:
                    names.add(args.kwarg.arg)
            for sub in ast.walk(fn):
                if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Store):
                    names.add(sub.id)
                elif isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef,
                                      ast.ClassDef)):
                    names.add(sub.name)
                elif isinstance(sub, ast.ExceptHandler) and sub.name:
                    names.add(sub.name)
                elif isinstance(sub, (ast.Import, ast.ImportFrom)):
                    for al in sub.names:
                        names.add(al.asname or al.name.split('.')[0])
                elif isinstance(sub, ast.Global):
                    names |= set(sub.names)
                elif isinstance(sub, ast.Nonlocal):
                    names |= set(sub.names)
    return names


def check(path):
    with open(path, 'r', encoding='utf-8') as f:
        src = f.read()
    tree = ast.parse(src, filename=path)

    defined = collect_defined(tree)
    local = collect_local(tree)
    used = {n.id for n in ast.walk(tree)
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}

    return sorted(used - defined - local - BUILTIN)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('-')]
    if args:
        targets = args
    else:
        mdir = os.path.join(SKILL_DIR, 'matchers')
        targets = sorted(
            os.path.join(mdir, f) for f in os.listdir(mdir)
            if f.endswith('.py') and f != '__init__.py'
        )

    print('=' * 72)
    print('未定义名字检查（拆分重构后的依赖漏带守卫）')
    print('=' * 72)

    bad = 0
    for p in targets:
        try:
            miss = check(p)
        except SyntaxError as e:
            print(f'\n✗ {os.path.basename(p):<34} 语法错误: {e}')
            bad += 1
            continue
        rel = os.path.relpath(p, SKILL_DIR)
        if miss:
            print(f'\n✗ {rel:<40} 未定义: {miss}')
            bad += 1
        else:
            print(f'  ✓ {rel}')

    print('\n' + '=' * 72)
    if bad:
        print(f'发现 {bad} 个模块存在未定义名字（通常是迁移时漏带 import）')
        return 1
    print(f'✓ 全部 {len(targets)} 个模块通过')
    return 0


if __name__ == '__main__':
    sys.exit(main())
