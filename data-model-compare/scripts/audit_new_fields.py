#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""新增字段深度审计：用比 self_validator 更宽的判据搜剩余漏配。

self_validator 的漏配检测只查"源标准里存在完全同名字段"，
本脚本用"归一基名一致"这一更宽判据复查全部 new_fields，
把结果按可疑程度分档输出，供人工复核。

用法:
  python scripts/audit_new_fields.py <temp_dir> [--top N]
"""
import json
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from matchers.standard_comparator import StandardComparator as SC  # noqa: E402


def norm(cn: str) -> str:
    """归一化：全角括号、同义词、尾部种类词、噪音字符。"""
    s = cn or ''
    for a, b in [('（', '('), ('）', ')'), ('医师', '医生'), ('大夫', '医生'),
                 ('编码', '代码'), ('代号', '代码'), ('唯一标识', '标识'),
                 ('名字', '名称'), ('姓名', '名称'), ('科别', '科室'),
                 ('报告单', '报告')]:
        s = s.replace(a, b)
    for ch in '、，,；;／/·　 的已':
        s = s.replace(ch, '')
    for k in sorted(['唯一标识', '流水号', '名称', '代码', '编码', '代号',
                     '标识', '标志', '序号', '编号', '签名'], key=len, reverse=True):
        if s.endswith(k) and len(s) > len(k):
            s = s[:-len(k)]
            break
    return s.strip()


def strip_paren(s: str) -> str:
    return re.sub(r'[（(][^）)]*[）)]', '', s or '').strip()


def main():
    temp = sys.argv[1]
    top = 40
    if '--top' in sys.argv:
        top = int(sys.argv[sys.argv.index('--top') + 1])

    src = json.load(open(os.path.join(temp, 'source_standard.json')))
    res_path = os.path.join(temp, 'iter_compare_result.json')
    if not os.path.exists(res_path):
        res_path = os.path.join(temp, 'compare_result.json')
    res = json.load(open(res_path))

    # 源字段索引：归一基名 -> [(表, 字段, 中文名)]
    base_idx = defaultdict(list)
    exact_idx = defaultdict(list)
    for t in src.get('tables', []):
        tn = t.get('name') or t.get('chinese_name')
        for f in t.get('fields', []):
            cn = f.get('chinese_name')
            if not cn:
                continue
            exact_idx[cn].append((tn, f.get('name'), cn))
            b = norm(cn)
            if len(b) >= 3:
                base_idx[b].append((tn, f.get('name'), cn))

    new_tables = {nt.get('table_name') for nt in res.get('new_tables', [])}

    tier_exact, tier_base, tier_paren = [], [], []
    for nf in res.get('new_fields', []):
        tn = nf.get('table_name') or nf.get('new_field_target')
        if tn in new_tables:
            continue
        cn = nf.get('chinese_name')
        if not cn:
            continue

        if cn in exact_idx:
            tier_exact.append((tn, cn, exact_idx[cn]))
            continue

        b = norm(cn)
        if len(b) >= 3 and b in base_idx:
            # 括号说明不同的（主子表展开）单独分档，多为合理新增
            has_paren = bool(re.search(r'[（(]', cn))
            cands = base_idx[b]
            if has_paren and all(strip_paren(c[2]) != strip_paren(cn) for c in cands):
                tier_paren.append((tn, cn, cands))
            else:
                tier_base.append((tn, cn, cands))

    total_new = len(res.get('new_fields', []))
    print('=== 新增字段深度审计 ===')
    print(f'new_fields 总数            : {total_new}')
    print(f'A档 源标准存在完全同名     : {len(tier_exact)}  <- 确定漏配，必须修')
    print(f'B档 归一基名一致(无括号差) : {len(tier_base)}   <- 高度疑似漏配')
    print(f'C档 归一基名一致(括号差异) : {len(tier_paren)}  <- 多为主子表展开，通常合理')
    print()

    for label, tier in [('A档 确定漏配', tier_exact), ('B档 疑似漏配', tier_base),
                        ('C档 括号差异', tier_paren)]:
        if not tier:
            continue
        print(f'--- {label}（前 {top} 条）---')
        for tn, cn, cands in tier[:top]:
            c = cands[0]
            print(f'  [{tn}] {cn}  <?=  {c[2]}  (源 {c[0]}.{c[1]})' +
                  (f'  +{len(cands)-1}个候选' if len(cands) > 1 else ''))
        print()

    out = os.path.join(temp, 'audit_new_fields.json')
    json.dump({
        'summary': {'total_new_fields': total_new, 'tier_exact': len(tier_exact),
                    'tier_base': len(tier_base), 'tier_paren': len(tier_paren)},
        'tier_exact': [{'table': t, 'cn': c, 'candidates': d} for t, c, d in tier_exact],
        'tier_base': [{'table': t, 'cn': c, 'candidates': d} for t, c, d in tier_base],
        'tier_paren': [{'table': t, 'cn': c, 'candidates': d} for t, c, d in tier_paren],
    }, open(out, 'w'), ensure_ascii=False, indent=2)
    print(f'明细已写入: {out}')


if __name__ == '__main__':
    main()
