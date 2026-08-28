#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
回归检查脚本（P1-1）—— 真实数据端到端基线守卫

用途：
    改动匹配逻辑（拆分 standard_comparator.py、调整匹配规则、重构 matcher 等）
    前后，对同一套真实标准文档重跑「比对 + 自验证 + 条件装配」，与 golden
    baseline 逐项对比，确认**行为零变化**。

与 scripts/test_runner.py 的单元级基线互补，二者不重复：
    test_runner.py   : 27 条手工用例（tests/test_cases.yaml），快，覆盖规则点
    regression_check : 真实全量数据（本例 5349 个字段判定），慢，覆盖端到端行为

用法：
    # 建立 / 更新基线（人工确认当前结果正确后再执行）
    python scripts/regression_check.py --task-dir <任务目录> --update-baseline

    # 回归检查（有差异则退出码 1，可接 CI）
    python scripts/regression_check.py --task-dir <任务目录>

    # 控制差异明细的显示条数
    python scripts/regression_check.py --task-dir <任务目录> --show-diff 30

说明：
    <任务目录> 形如 ~/data-model-compare-docs/V6.0医疗服务_vs_省平台v1.4.1医疗部分
    脚本自动定位其下的 temp/，复用已解析的 source_standard.json /
    target_standard.json，跳过耗时的 docx→md 解析阶段。

    回归检查是**只读**的：结果只在内存中判分，不覆盖 temp 下任何产物。

退出码：
    0 = 无回归（或已成功更新基线）    1 = 检出回归    2 = 参数/文件错误
"""

import os
import sys
import json
import hashlib
import argparse
from collections import Counter
from datetime import datetime

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SKILL_DIR)
sys.path.insert(0, os.path.join(SKILL_DIR, 'scripts'))

from fast_iterate import load_standard, to_dict                     # noqa: E402
from matchers.standard_comparator import StandardComparator          # noqa: E402
from matchers.self_validator import self_validate                    # noqa: E402
from apply_conditional_constraints import (                          # noqa: E402
    apply_condition_display_to_result,
)

GOLDEN_DIR = os.path.join(SKILL_DIR, 'tests', 'golden')

# 各判定类型的目标字段名不一致（matched 用 target_field、modified 用
# field_name、new_fields 用 name），此处统一声明，避免写错。
_KIND_SPEC = [
    ('matched', 'matched', 'target_field'),
    ('modified', 'modified', 'field_name'),
    ('new', 'new_fields', 'name'),
]


# --------------------------------------------------------------------------
# 指标提取
# --------------------------------------------------------------------------
def build_field_rows(result):
    """构建字段级指纹行。

    每行格式：{判定}|{目标表}.{目标字段}|{匹配类型}|{源表}.{源字段}|{条件显示}

    之所以做到字段级（而不只比总数）：可能出现「matched 总数不变，但某字段
    从 synonym 变成 keyword」这类静默漂移，纯计数检测不出来。
    """
    rows = []
    for kind, key, fkey in _KIND_SPEC:
        for it in result.get(key, []):
            rows.append('|'.join([
                kind,
                f"{it.get('table_name', '')}.{it.get(fkey, '')}",
                it.get('match_type', '-') or '-',
                f"{it.get('source_table', '')}.{it.get('source_field', '')}",
                it.get('condition_display', '') or '',
            ]))
    for it in result.get('new_tables', []):
        rows.append('|'.join([
            'new_table',
            it.get('table_name', ''),
            '-', '-',
            it.get('reason', '') or '',
        ]))
    return sorted(rows)


def extract_metrics(result, sv, source_doc, target_doc, task_name, temp_dir):
    matched = result.get('matched', [])
    modified = result.get('modified', [])
    new_fields = result.get('new_fields', [])
    new_tables = result.get('new_tables', [])
    kb = result.get('kb_conflicts', {}) or {}

    leaks = sv.get('leaks', []) or []
    suspects = sv.get('suspects', []) or []
    total = len(matched) + len(modified) + len(new_fields)
    suspicious = len(leaks) + len(suspects)
    correct = ((len(matched) + len(modified) - len(suspects))
               + (len(new_fields) - len(leaks)))
    acc = round(correct / total * 100, 2) if total else 0.0

    rows = build_field_rows(result)
    blob = '\n'.join(rows).encode('utf-8')

    return {
        'meta': {
            'task': task_name,
            'temp_dir': temp_dir,
            'created_at': datetime.now().astimezone().isoformat(timespec='seconds'),
            'generator': 'scripts/regression_check.py',
        },
        'scale': {
            'source_tables': len(source_doc.tables),
            'source_fields': sum(len(t.fields) for t in source_doc.tables),
            'target_tables': len(target_doc.tables),
            'target_fields': sum(len(t.fields) for t in target_doc.tables),
        },
        'counts': {
            'matched': len(matched),
            'modified': len(modified),
            'new_fields': len(new_fields),
            'new_tables': len(new_tables),
            'matched_by_type': dict(Counter(m.get('match_type', '?') for m in matched)),
            'modified_by_type': dict(Counter(m.get('match_type', '?') for m in modified)),
            'ghost_source_tables': len(result.get('ghost_source_tables', []) or []),
            'condition_display': sum(
                1 for x in matched + modified if x.get('condition_display')
            ),
            'kb_stale_negative': len(kb.get('stale_negative', []) or []),
            'kb_stale_positive': len(kb.get('stale_positive', []) or []),
        },
        'self_validation': {
            'leak': len(leaks),
            'suspect': len(suspects),
            'total_judged': total,
            'suspicious': suspicious,
            'accuracy': acc,
        },
        'field_rows_sha256': hashlib.sha256(blob).hexdigest(),
        'field_rows_count': len(rows),
        'field_rows': rows,
    }


# --------------------------------------------------------------------------
# 差异对比
# --------------------------------------------------------------------------
def _walk(prefix, base_v, cur_v, out):
    """递归收集标量与字典的差异。"""
    if isinstance(base_v, dict):
        for k in sorted(set(base_v) | set(cur_v if isinstance(cur_v, dict) else {})):
            b = base_v.get(k, 0)
            c = (cur_v or {}).get(k, 0) if isinstance(cur_v, dict) else 0
            _walk(f'{prefix}.{k}', b, c, out)
    else:
        if base_v != cur_v:
            out.append((prefix, base_v, cur_v))


def diff_field_rows(base_rows, cur_rows):
    """返回 (added, removed, changed) 三组差异。

    changed 指「同一 (判定, 目标表.字段) 键仍在，但匹配类型/源字段/条件变了」
    这类最需要关注的静默漂移。
    """
    def to_map(rows):
        m = {}
        for r in rows:
            p = r.split('|')
            m[(p[0], p[1])] = p
        return m

    bmap, cmap = to_map(base_rows), to_map(cur_rows)
    added = sorted(set(cmap) - set(bmap))
    removed = sorted(set(bmap) - set(cmap))
    changed = []
    for k in sorted(set(bmap) & set(cmap)):
        if bmap[k] != cmap[k]:
            changed.append((k, bmap[k], cmap[k]))
    return added, removed, changed


def compare(base, cur):
    """返回 (metric_diffs, added, removed, changed)。"""
    metric_diffs = []
    for section in ('scale', 'counts', 'self_validation'):
        _walk(section, base.get(section, {}), cur.get(section, {}), metric_diffs)
    if base.get('field_rows_sha256') != cur.get('field_rows_sha256'):
        metric_diffs.append(
            ('field_rows_sha256',
             (base.get('field_rows_sha256') or '')[:12],
             (cur.get('field_rows_sha256') or '')[:12])
        )
    added, removed, changed = diff_field_rows(
        base.get('field_rows', []) or [], cur.get('field_rows', []) or []
    )
    return metric_diffs, added, removed, changed


# --------------------------------------------------------------------------
# 报告输出
# --------------------------------------------------------------------------
def _fmt_row(p):
    """把指纹行 parts 渲染成人类可读形式。"""
    if p[0] == 'new_table':
        return f'[新增表] {p[1]}  原因={p[4]}'
    kind, key, mtype, src, cond = p
    label = {'matched': '满足', 'modified': '需修改', 'new': '需新增'}.get(kind, kind)
    s = f'[{label}] {key}  类型={mtype}'
    if src != '.':
        s += f'  源={src}'
    if cond:
        s += f'  条件={cond}'
    return s


def report(base, cur, metric_diffs, added, removed, changed, show):
    print('\n' + '=' * 74)
    print('回归检查报告')
    print('=' * 74)
    print(f"  任务     : {cur['meta']['task']}")
    print(f"  基线时间 : {base['meta'].get('created_at', '未知')}")
    s, c = cur['scale'], cur['self_validation']
    print(f"  数据规模 : 源 {s['source_tables']}表/{s['source_fields']}字段  "
          f"目标 {s['target_tables']}表/{s['target_fields']}字段")
    print(f"  当前结果 : matched={cur['counts']['matched']}  "
          f"modified={cur['counts']['modified']}  "
          f"new_fields={cur['counts']['new_fields']}  "
          f"new_tables={cur['counts']['new_tables']}")
    print(f"  自验证   : leak={c['leak']}  suspect={c['suspect']}  "
          f"准确率={c['accuracy']}%")

    if not metric_diffs and not (added or removed or changed):
        print('\n  ✅ 无回归：与 golden baseline 完全一致（行为零变化）')
        print('=' * 74)
        return True

    print('\n  ❌ 检出回归')
    print('-' * 74)

    if metric_diffs:
        print(f'\n  【指标差异】共 {len(metric_diffs)} 项')
        print(f"    {'指标':<44} {'基线':>12} {'当前':>12}")
        for name, b, v in metric_diffs:
            print(f'    {name:<44} {str(b):>12} {str(v):>12}')

    if changed:
        print(f'\n  【字段判定变更】共 {len(changed)} 条（最需关注：静默漂移）')
        for k, old, new in changed[:show]:
            print(f'    {k[1]}')
            print(f'      基线: {_fmt_row(old)}')
            print(f'      当前: {_fmt_row(new)}')
        if len(changed) > show:
            print(f'    ... 另 {len(changed) - show} 条（--show-diff N 调整显示条数）')

    if added:
        print(f'\n  【新增判定】共 {len(added)} 条')
        for k in added[:show]:
            print(f'    {_fmt_row(_row_of(cur, k))}')
        if len(added) > show:
            print(f'    ... 另 {len(added) - show} 条')

    if removed:
        print(f'\n  【消失判定】共 {len(removed)} 条')
        for k in removed[:show]:
            print(f'    {_fmt_row(_row_of(base, k))}')
        if len(removed) > show:
            print(f'    ... 另 {len(removed) - show} 条')

    print('\n' + '=' * 74)
    return False


def _row_of(metrics, key):
    """按 (kind, key) 从 metrics 里取回指纹行。"""
    for r in metrics.get('field_rows', []):
        p = r.split('|')
        if (p[0], p[1]) == key:
            return p
    return [key[0], key[1], '-', '-', '']


# --------------------------------------------------------------------------
# 主流程
# --------------------------------------------------------------------------
def resolve_temp(task_dir):
    """任务目录 → temp 目录（兼容直接传 temp 目录）。"""
    task_dir = os.path.expanduser(task_dir)
    cand = os.path.join(task_dir, 'temp')
    if os.path.isdir(cand):
        return task_dir, cand
    if os.path.isdir(task_dir):
        return os.path.dirname(task_dir) or task_dir, task_dir
    return task_dir, None


def run_compare(temp):
    """在内存中跑完「比对 + 自验证 + 条件装配」，不写任何磁盘产物。"""
    src_path = os.path.join(temp, 'source_standard.json')
    tgt_path = os.path.join(temp, 'target_standard.json')
    for p in (src_path, tgt_path):
        if not os.path.exists(p):
            raise FileNotFoundError(f'缺少 {p}，请先跑一次完整流程生成解析产物')

    source_doc = load_standard(src_path)
    target_doc = load_standard(tgt_path)
    with open(src_path, 'r', encoding='utf-8') as f:
        src_raw = json.load(f)
    with open(tgt_path, 'r', encoding='utf-8') as f:
        tgt_raw = json.load(f)

    result = to_dict(StandardComparator().compare(source_doc, target_doc))
    sv = self_validate(result, src_raw, tgt_raw)
    apply_condition_display_to_result(result, temp)   # 内存装配，不写盘
    return result, sv, source_doc, target_doc


def main():
    ap = argparse.ArgumentParser(
        description='真实数据端到端回归检查（P1-1）'
    )
    ap.add_argument('--task-dir', required=True,
                    help='任务目录（含 temp/），或直接传 temp 目录')
    ap.add_argument('--update-baseline', action='store_true',
                    help='把当前结果写入 golden baseline（覆盖）')
    ap.add_argument('--baseline', help='指定基线文件路径（默认 tests/golden/<任务名>.json）')
    ap.add_argument('--show-diff', type=int, default=15,
                    help='差异明细显示条数（默认 15）')
    args = ap.parse_args()

    task_dir, temp = resolve_temp(args.task_dir)
    if not temp:
        print(f'[ERR] 目录不存在: {task_dir}')
        return 2
    task_name = os.path.basename(os.path.normpath(task_dir))

    print(f'任务: {task_name}')
    print(f'缓存: {temp}')
    print('\n加载已解析标准并重跑比对（只读，不覆盖任何产物）...')
    result, sv, source_doc, target_doc = run_compare(temp)
    cur = extract_metrics(result, sv, source_doc, target_doc, task_name, temp)
    print(f"  matched={cur['counts']['matched']}  modified={cur['counts']['modified']}  "
          f"new_fields={cur['counts']['new_fields']}  leak={cur['self_validation']['leak']}  "
          f"suspect={cur['self_validation']['suspect']}")

    baseline_path = args.baseline or os.path.join(GOLDEN_DIR, f'{task_name}.json')

    if args.update_baseline:
        os.makedirs(os.path.dirname(baseline_path), exist_ok=True)
        with open(baseline_path, 'w', encoding='utf-8') as f:
            json.dump(cur, f, ensure_ascii=False, indent=2)
        size = os.path.getsize(baseline_path) / 1024
        print(f'\n✅ 基线已写入: {baseline_path}  ({size:.0f} KB)')
        print(f"   字段级指纹: {cur['field_rows_sha256'][:16]}…  "
              f"({cur['field_rows_count']} 行)")
        return 0

    if not os.path.exists(baseline_path):
        print(f'\n[ERR] 基线文件不存在: {baseline_path}')
        print('      请先执行: --update-baseline')
        return 2

    with open(baseline_path, 'r', encoding='utf-8') as f:
        base = json.load(f)

    metric_diffs, added, removed, changed = compare(base, cur)
    ok = report(base, cur, metric_diffs, added, removed, changed, args.show_diff)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
