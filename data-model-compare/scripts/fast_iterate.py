#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速迭代验证脚本（调优 Skill 匹配逻辑时使用）

目的：跳过耗时的 docx→md 解析阶段，直接复用 temp/ 下已解析好的
source_standard.json / target_standard.json 重跑比对 + 自验证，
用于"改一版匹配逻辑 → 立刻看准确率变化"的循环。

用法：
    python scripts/fast_iterate.py <temp_dir> [--dump-leaks N] [--dump-suspects N]

示例：
    python scripts/fast_iterate.py ~/data-model-compare-docs/xxx_vs_yyy/temp
    python scripts/fast_iterate.py <temp> --dump-leaks 40 --dump-suspects 20

输出：
    - 匹配类型分布（matched / modified 各来源）
    - new_fields / new_tables 计数
    - 自验证 leak / suspect 计数
    - 准确率估算
    - 结果写入 <temp_dir>/iter_compare_result.json 与 iter_self_validation.json
"""

import os
import sys
import json
import argparse
from collections import Counter

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SKILL_DIR)

from parsers.standard_parser import (  # noqa: E402
    StandardDocument, StandardTable, StandardField, ValueDomain,
)
from matchers.standard_comparator import StandardComparator  # noqa: E402
from matchers.self_validator import self_validate  # noqa: E402


def load_standard(path: str) -> StandardDocument:
    """把 *_standard.json 还原成 StandardDocument 对象。"""
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    tables = []
    for t in data.get('tables', []):
        fields = []
        for fd in t.get('fields', []):
            vds = [
                ValueDomain(
                    code=str(vd.get('code', '')),
                    name=str(vd.get('name', '')),
                    description=str(vd.get('description', '') or ''),
                )
                for vd in (fd.get('value_domains') or [])
            ]
            fields.append(StandardField(
                name=fd.get('name', '') or '',
                chinese_name=fd.get('chinese_name', '') or '',
                data_type=fd.get('data_type', '') or '',
                length=fd.get('length', 0) or 0,
                constraint=fd.get('constraint', '') or '',
                description=fd.get('description', '') or '',
                value_domains=vds,
                data_element_id=fd.get('data_element_id', '') or '',
                format=fd.get('format', '') or '',
            ))
        tables.append(StandardTable(
            name=t.get('name', '') or '',
            chinese_name=t.get('chinese_name', '') or '',
            description=t.get('description', '') or '',
            fields=fields,
        ))

    return StandardDocument(
        source_file=data.get('source_file', path),
        tables=tables,
        metadata=data.get('metadata', {}) or {},
    )


def to_dict(obj):
    """CompareResult -> dict（兼容 dataclass / 已是 dict 两种情况）。"""
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, 'to_dict'):
        return obj.to_dict()
    from dataclasses import asdict, is_dataclass
    if is_dataclass(obj):
        return asdict(obj)
    return dict(obj.__dict__)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('temp_dir')
    ap.add_argument('--dump-leaks', type=int, default=0)
    ap.add_argument('--dump-suspects', type=int, default=0)
    args = ap.parse_args()

    temp = os.path.expanduser(args.temp_dir)
    src_path = os.path.join(temp, 'source_standard.json')
    tgt_path = os.path.join(temp, 'target_standard.json')
    for p in (src_path, tgt_path):
        if not os.path.exists(p):
            print(f'[ERR] 缺少 {p}，请先跑一次完整流程生成解析产物')
            return 1

    print('加载已解析标准...')
    source_doc = load_standard(src_path)
    target_doc = load_standard(tgt_path)
    print(f'  源: {len(source_doc.tables)} 表 / '
          f'{sum(len(t.fields) for t in source_doc.tables)} 字段')
    print(f'  目标: {len(target_doc.tables)} 表 / '
          f'{sum(len(t.fields) for t in target_doc.tables)} 字段')

    print('\n重跑比对...')
    comparator = StandardComparator()
    result = to_dict(comparator.compare(source_doc, target_doc))

    matched = result.get('matched', [])
    modified = result.get('modified', [])
    new_fields = result.get('new_fields', [])
    new_tables = result.get('new_tables', [])

    print('\n=== 匹配类型分布 ===')
    print('matched  :', dict(Counter(m.get('match_type', '?') for m in matched)))
    print('modified :', dict(Counter(m.get('match_type', '?') for m in modified)))
    print(f'new_fields : {len(new_fields)}')
    print(f'new_tables : {len(new_tables)}')

    with open(src_path, 'r', encoding='utf-8') as f:
        src_raw = json.load(f)
    with open(tgt_path, 'r', encoding='utf-8') as f:
        tgt_raw = json.load(f)

    print('\n自验证...')
    sv = self_validate(result, src_raw, tgt_raw)
    leaks = sv['leaks']
    suspects = sv['suspects']
    print(f"  leak(疑漏配)   : {len(leaks)}")
    print(f"  suspect(疑误配): {len(suspects)}")

    total = len(matched) + len(modified) + len(new_fields)
    correct = (len(matched) + len(modified) - len(suspects)) + (len(new_fields) - len(leaks))
    acc = correct / total * 100 if total else 0.0
    print('\n=== 准确率估算 ===')
    print(f'  总判定字段 : {total}')
    print(f'  可疑判定   : {len(leaks) + len(suspects)}')
    print(f'  准确率     : {acc:.2f}%')

    out_cmp = os.path.join(temp, 'iter_compare_result.json')
    out_sv = os.path.join(temp, 'iter_self_validation.json')
    with open(out_cmp, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    with open(out_sv, 'w', encoding='utf-8') as f:
        json.dump(sv, f, ensure_ascii=False, indent=2)
    print(f'\n结果已写入:\n  {out_cmp}\n  {out_sv}')

    # 条件式值域约束装配（condition_display，round6 固化）：
    # 读 temp/conditional_constraints.json 的 rules，给 matched/modified
    # 注入条件显示（地址族 03/01/06 + 电话族 01/02），HTML/MD/XLSX 同步生效。
    try:
        sys.path.insert(0, os.path.join(SKILL_DIR, 'scripts'))
        from apply_conditional_constraints import apply_condition_display
        apply_condition_display(temp)
    except Exception as e:  # 装配失败不影响主结果
        print(f'  ⚠ 条件装配跳过: {e}')

    if args.dump_leaks:
        print(f'\n=== 漏配样本（前 {args.dump_leaks} 条）===')
        for lk in leaks[:args.dump_leaks]:
            sug = lk['suggested_source'][0]
            print(f"  [{lk['table']}] {lk['chinese_name']} ({lk['field']}) "
                  f"→ 源: {sug['table']}.{sug['field']}")

    if args.dump_suspects:
        print(f'\n=== 疑误配样本（前 {args.dump_suspects} 条）===')
        for sp in suspects[:args.dump_suspects]:
            print(f"  [{sp['table']}] {sp['target_cn']} → {sp['source_cn']} "
                  f"({sp['match_type']})")

    return 0


if __name__ == '__main__':
    sys.exit(main())
