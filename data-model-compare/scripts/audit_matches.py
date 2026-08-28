#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全量匹配分层置信度审核。

self_validator 只体检"模糊匹配"，user_custom / dictionary / exact_* 不进体检，
这些恰恰是数量最大的部分。本脚本对**全部**匹配按证据强度分档，
把需要人工看的挑出来，给出可信的准确率区间。

分档:
  L1 中文名完全相同                 -> 确定正确
  L2 归一基名相同 + 字段种类相同    -> 高置信正确
  LE 英文名核心相同                 -> 高置信正确（中文名不一致但英文名同源，
                                       如 医师姓名/doc_sign ← 医师签名/DR_SIGN）
  LD 字典派生（源侧本无对应字段）   -> 正确（目标把代码拆成 代码+名称 两列）
  L3 归一基名相同 + 种类不同        -> 需复核（代码↔名称 这类）
  L4 基名不同但通过某网关           -> 需复核（最可疑）

用法:
  python scripts/audit_matches.py <temp_dir> [--sample N]
"""
import json
import os
import random
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from matchers.standard_comparator import StandardComparator as SC  # noqa: E402


def main():
    temp = sys.argv[1]
    sample_n = 25
    if '--sample' in sys.argv:
        sample_n = int(sys.argv[sys.argv.index('--sample') + 1])

    res_path = os.path.join(temp, 'iter_compare_result.json')
    if not os.path.exists(res_path):
        res_path = os.path.join(temp, 'compare_result.json')
    res = json.load(open(res_path))

    items = []
    for r in res.get('matched', []):
        items.append((r.get('table_name'), r.get('target_chinese_name'),
                      r.get('source_field_chinese_name'), r.get('match_type'),
                      r.get('target_field'), r.get('source_field')))
    for r in res.get('modified', []):
        items.append((r.get('table_name'), r.get('field_chinese_name'),
                      r.get('source_field_chinese_name'), r.get('match_type'),
                      r.get('field_name') or r.get('target_field'), r.get('source_field')))

    def en_core(n: str) -> str:
        """英文名归一：去下划线、去常见前缀差异，用于同源判断。"""
        s = (n or '').lower().replace('_', '')
        for a, b in [('doctor', 'dr'), ('department', 'dept'), ('number', 'no'),
                     ('code', 'no'), ('identity', 'id'), ('identifier', 'id')]:
            s = s.replace(a, b)
        return s

    tiers = defaultdict(list)
    tier_by_type = defaultdict(Counter)

    for tb, t_cn, s_cn, mt, t_en, s_en in items:
        # 字典派生：源侧本无对应字段（目标标准把代码拆成 代码+名称 两列）
        if not s_cn and not s_en:
            tiers['LD'].append((tb, t_cn, s_cn, mt))
            tier_by_type[mt]['LD'] += 1
            continue
        if not t_cn or not s_cn:
            tiers['L0'].append((tb, t_cn, s_cn, mt))
            tier_by_type[mt]['L0'] += 1
            continue
        if t_cn == s_cn:
            tier = 'L1'
        else:
            b1, b2 = SC._global_norm_base(t_cn), SC._global_norm_base(s_cn)
            same_base = bool(b1) and b1 == b2
            same_kind = SC._field_kind_of(t_cn) == SC._field_kind_of(s_cn)
            e1, e2 = en_core(t_en), en_core(s_en)
            same_en = bool(e1) and e1 == e2
            if same_base and same_kind:
                tier = 'L2'
            elif same_en:
                # 中文名不一致但英文名同源 -> 标准自身命名不一致，映射可信
                tier = 'LE'
            elif same_base:
                tier = 'L3'
            else:
                tier = 'L4'
        tiers[tier].append((tb, t_cn, s_cn, mt))
        tier_by_type[mt][tier] += 1

    total = len(items)
    print('=== 全量匹配分层置信度审核 ===')
    print(f'匹配总数: {total}')
    print()
    labels = {'L1': '中文名完全相同（确定正确）',
              'L2': '归一基名相同+种类相同（高置信）',
              'LE': '英文名同源（高置信）',
              'LD': '字典派生/源侧无对应字段（正确）',
              'L3': '归一基名相同+种类不同（需复核）',
              'L4': '基名不同（最可疑，需复核）',
              'L0': '单侧缺中文名（无法判定）'}
    for t in ['L1', 'L2', 'LE', 'LD', 'L3', 'L4', 'L0']:
        n = len(tiers.get(t, []))
        print(f'  {t:4s} {labels[t]:36s} {n:5d}  ({n/total*100:5.2f}%)')
    high = len(tiers['L1']) + len(tiers['L2']) + len(tiers['LE']) + len(tiers['LD'])
    need = len(tiers['L3']) + len(tiers['L4']) + len(tiers['L0'])
    print()
    print(f'  高置信合计 : {high} ({high/total*100:.2f}%)')
    print(f'  需复核合计 : {need} ({need/total*100:.2f}%)')
    print()

    print('=== 各 match_type 的分档构成 ===')
    for mt, c in sorted(tier_by_type.items(), key=lambda x: -sum(x[1].values())):
        tot = sum(c.values())
        hi = c['L1'] + c['L2'] + c['LE'] + c['LD']
        print(f'  {mt:20s} 共{tot:5d}  高置信{hi:5d} ({hi/tot*100:5.1f}%)  '
              f'L3={c["L3"]:4d} L4={c["L4"]:4d} LE={c["LE"]:4d} LD={c["LD"]:4d}')
    print()

    random.seed(42)
    for t in ['L3', 'L4']:
        pool = tiers.get(t, [])
        if not pool:
            continue
        print(f'--- {t} 随机抽样 {min(sample_n, len(pool))} / {len(pool)} 条 ---')
        for tb, t_cn, s_cn, mt in random.sample(pool, min(sample_n, len(pool))):
            print(f'  [{tb}] {t_cn}  <=  {s_cn}   ({mt})')
        print()

    out = os.path.join(temp, 'audit_matches.json')
    json.dump({
        'summary': {'total': total,
                    **{k: len(v) for k, v in tiers.items()},
                    'high_confidence': high, 'need_review': need},
        'tiers': {k: [{'table': a, 'target_cn': b, 'source_cn': c, 'match_type': d}
                      for a, b, c, d in v] for k, v in tiers.items()},
    }, open(out, 'w'), ensure_ascii=False, indent=2)
    print(f'明细已写入: {out}')


if __name__ == '__main__':
    main()
