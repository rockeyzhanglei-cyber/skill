#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""单字段匹配流程追踪：诊断某个目标字段为什么被判为新增。

用法:
  python scripts/trace_field.py <temp_dir> <目标表英文名> <字段中文名>
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.fast_iterate import load_standard  # noqa: E402
from matchers.standard_comparator import StandardComparator  # noqa: E402


def main():
    temp, tb, cn = sys.argv[1], sys.argv[2], sys.argv[3]
    src = load_standard(os.path.join(temp, 'source_standard.json'))
    tgt = load_standard(os.path.join(temp, 'target_standard.json'))

    comp = StandardComparator()

    print(f'match_priority = {comp.match_priority}')
    print(f'cross_table_fuzzy 开关 = {getattr(comp, "cross_table_fuzzy", None)}')
    print(f'stale_negative_override = {getattr(comp, "stale_negative_override", None)}')
    print()

    target_table = None
    for t in tgt.tables:
        if t.name == tb or t.chinese_name == tb:
            target_table = t
            break
    if target_table is None:
        print(f'未找到目标表 {tb}')
        return

    target_field = None
    for f in target_table.fields:
        if f.chinese_name == cn:
            target_field = f
            break
    if target_field is None:
        print(f'未找到字段 {cn}，该表字段示例: {[f.chinese_name for f in target_table.fields[:12]]}')
        return

    src_table_index = {t.name: t for t in src.tables}
    src_table_index.update({t.chinese_name: t for t in src.tables if t.chinese_name})

    # 找对应源表
    src_table = None
    tm = comp.table_mappings or {}
    mapped = tm.get(target_table.name) or tm.get(target_table.chinese_name)
    if isinstance(mapped, dict):
        mapped = mapped.get('source_table')
    if mapped:
        src_table = src_table_index.get(mapped)
    print(f'目标表 {target_table.name} / {target_table.chinese_name}')
    print(f'表映射 -> {mapped}  (源表对象 {"有" if src_table else "无"})')
    print(f'目标字段 {target_field.name} / {target_field.chinese_name} / 类型={target_field.data_type}')
    print()

    src_field_index = {}
    if src_table:
        for f in src_table.fields:
            src_field_index[f.name] = f

    # 1) 直接调 _global_fuzzy_lookup 看能不能捞到
    comp._gfz_cache = None
    gf = comp._global_fuzzy_lookup(target_field, src_table_index)
    print(f'[A] _global_fuzzy_lookup 直接调用 -> ' +
          (f'命中 {gf.chinese_name} ({gf.name})' if gf else '未命中'))
    base = comp._global_norm_base(cn)
    print(f'    归一基名 = 「{base}」')
    cache = comp._gfz_cache or {}
    hits = cache.get(base) or []
    print(f'    源侧同基名候选 {len(hits)} 个: {[h.chinese_name for h in hits[:8]]}')
    for h in hits[:8]:
        print(f'      - {h.chinese_name}: kind={comp._field_kind_compatible(cn, h.chinese_name)} '
              f'role={comp._is_role_compatible_for_keyword(cn, h.chinese_name)} '
              f'subj={comp._composite_subject_compatible(cn, h.chinese_name)} '
              f'desc={comp._is_description_compatible(target_field, h)}')
    print()

    # 2) 走完整 _find_matching_field
    r = comp._find_matching_field(target_field, src_field_index, src_table,
                                  src_table_index, target_table)
    print(f'[B] _find_matching_field 完整流程 -> ' +
          (f'命中 {r[0].chinese_name} ({r[0].name}) via {r[1]}' if r else '未命中（判为新增）'))
    print()
    print(f'[C] stale_negative_conflicts 记录数 = {len(comp.stale_negative_conflicts)}')
    for c in comp.stale_negative_conflicts[:3]:
        print('   ', json.dumps(c, ensure_ascii=False)[:200])


if __name__ == '__main__':
    main()
