#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""审计"陈旧正向映射否决"的下游后果。

被 _user_custom_hard_conflict 否决的知识库映射，字段会改走常规匹配。
本脚本回答两个问题：
  1. 否决后字段最终落到哪里（matched / modified / new_fields）？
  2. 落到 new_fields 的，源标准里是否真的存在合适字段（=误杀）？

用法:
  python scripts/audit_kb_veto.py <temp_dir>
"""
import json
import sys
from collections import Counter
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_DIR))


def main():
    temp = Path(sys.argv[1])
    res = json.loads((temp / 'iter_compare_result.json').read_text(encoding='utf-8'))
    src = json.loads((temp / 'source_standard.json').read_text(encoding='utf-8'))

    conflicts = (res.get('kb_conflicts') or {}).get('stale_positive') or []

    # 目标字段 -> 最终归宿
    dest = {}
    for bucket in ('matched', 'modified'):
        for m in res.get(bucket) or []:
            key = (m.get('table_name') or '', m.get('target_field_cn')
                   or m.get('chinese_name') or '')
            dest[key] = (bucket, m.get('match_type', ''),
                         m.get('source_field_cn') or m.get('source_field') or '')
    for m in res.get('new_fields') or []:
        key = (m.get('table_name') or '', m.get('chinese_name') or '')
        dest.setdefault(key, ('new_field', '', ''))

    # 源标准全部字段中文名（用于判断误杀）
    src_cn = set()
    for t in src.get('tables', []):
        for f in t.get('fields', []):
            if f.get('chinese_name'):
                src_cn.add(f['chinese_name'])

    # 目标表中文名 -> 表英文名（结果里 table_name 是英文名）
    dist = Counter()
    rows = []
    seen = set()
    for c in conflicts:
        tf = c['target_field']
        sig = (c['target_table'], tf, c['kb_source_field'])
        if sig in seen:
            continue
        seen.add(sig)
        hit = None
        for (tn, fn), v in dest.items():
            if fn == tf:
                hit = v
                break
        if hit is None:
            hit = ('?', '', '')
        dist[hit[0]] += 1
        rows.append({
            'target_field': tf,
            'kb_source_field': c['kb_source_field'],
            'reason': c['reason'],
            'final': hit[0],
            'final_type': hit[1],
            'final_source': hit[2],
            'kb_src_exists_in_source_std': c['kb_source_field'] in src_cn,
        })

    print(f'去重后否决条目: {len(rows)}')
    print('最终归宿分布:', dict(dist))
    print()
    print('--- 否决后仍有匹配（网关生效且未丢覆盖）---')
    for r in rows:
        if r['final'] in ('matched', 'modified'):
            print(f"  {r['target_field']:<24} KB说:{r['kb_source_field']:<18}"
                  f" -> 实际:{r['final_source']:<18} ({r['final_type']})")
    print()
    print('--- 否决后变成新增（需人工确认是否误杀）---')
    for r in rows:
        if r['final'] not in ('matched', 'modified'):
            flag = '★源标准有同名字段' if r['kb_src_exists_in_source_std'] else ''
            print(f"  {r['target_field']:<24} KB说:{r['kb_source_field']:<18}"
                  f" [{r['reason']}] {flag}")

    out = temp / 'audit_kb_veto.json'
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'\n已写入 {out}')


if __name__ == '__main__':
    main()
