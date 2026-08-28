# -*- coding: utf-8 -*-
"""
值域字典（代码表）比对器

对比"目标标准值域字典"与"源标准值域字典"两个维度：
- 哪些值域在两边都有（按 标准号 > 名称 匹配）
- 共有值域内部：目标代码是否被源标准覆盖、是否缺失、名称是否冲突
- 仅目标有 / 仅源有的值域

输出结构化的比对结果，供报告与自验证使用。
"""

import re

from parsers.value_domain_parser import _norm_meaning

# 名称前缀/修饰词（用于模糊名称匹配时忽略）
_NAME_PREFIXES = ['生理', '西医', '中医', '门急诊', '门诊', '住院', '急诊', '患者', '卫生']


def _norm_name_for_match(name: str) -> str:
    s = name or ''
    s = re.sub(r'[（(][^（）()]*[）)]', '', s)  # 去括号内容
    for p in _NAME_PREFIXES:
        if s.startswith(p):
            s = s[len(p):]
    s = s.replace('代码表', '').replace('代码', '').replace('表', '')
    return s.strip()


def _build_index(domains: dict):
    by_std = {}
    by_name = {}
    for key, d in domains.items():
        if d.get('std_no'):
            by_std.setdefault(d['std_no'], []).append((key, d))
        by_name.setdefault(_norm_name_for_match(d['name']), []).append((key, d))
    return by_std, by_name


def _match_domains(target: dict, source: dict):
    """为单个目标值域寻找源标准中的对应值域，返回 (source_key, source_domain) 或 None。"""
    # 1) 标准号优先
    if target.get('std_no') and target['std_no'] in _build_index(source)[0]:
        cands = _build_index(source)[0][target['std_no']]
        # 同名优先
        same_name = [c for c in cands if c[1]['name'] == target['name']]
        return (same_name or cands)[0]
    # 2) 归一化名称
    tn = _norm_name_for_match(target['name'])
    s_by_std, s_by_name = _build_index(source)
    if tn and tn in s_by_name:
        cands = s_by_name[tn]
        # 若有标准号，优先选标准号一致的
        if target.get('std_no'):
            same_std = [c for c in cands if c[1].get('std_no') == target['std_no']]
            if same_std:
                return same_std[0]
        return cands[0]
    return None


def _compare_codes(tgt_codes: dict, src_codes: dict):
    """比较两个代码集，返回覆盖情况。

    按**中文语义（归一化含义）**比对，忽略编码差异（用户要求：编码不同可忽略）：
    - 目标的某个值含义在源中存在（无论代码是否相同）→ 视为覆盖。
    - 含义相同但代码不同 → 记为 code_format_diff（编码格式差异，可忽略，仅供落地参考）。
    - 同代码但含义不同 → 仍记为 name_conflict（需人工核实）。
    - 目标含义在源中完全不存在 → missing（源需补充该值）。
    """
    # 源：归一化含义 -> 代码（假设 1:1，重复时后者覆盖）
    src_norm = {}
    for c, n in src_codes.items():
        src_norm[_norm_meaning(n)] = c
    src_meaning_set = set(src_norm.keys())
    # 目标：归一化含义 -> 代码
    tgt_norm = {}
    for c, n in tgt_codes.items():
        tgt_norm[_norm_meaning(n)] = c

    common = {}
    missing = {}            # 目标有含义、源无（按语义）
    name_conflict = {}      # 同代码、含义不同
    code_format_diff = {}   # 含义相同、代码不同（编码格式差异，可忽略）
    for tcode, tname in tgt_codes.items():
        tn = _norm_meaning(tname)
        # 同代码但含义不同：真实冲突
        if tcode in src_codes and _norm_meaning(src_codes[tcode]) != tn:
            name_conflict[tcode] = {'target': tname, 'source': src_codes[tcode]}
        # 语义覆盖（忽略编码）
        if tn in src_meaning_set:
            common[tcode] = tname
            scode = src_norm[tn]
            if scode != tcode:
                code_format_diff[tcode] = {
                    'target_code': tcode, 'source_code': scode, 'meaning': tname}
        else:
            missing[tcode] = tname
    extra = {c: n for c, n in src_codes.items()
             if _norm_meaning(n) not in set(tgt_norm.keys())}
    total = len(tgt_codes)
    covered = len(common)
    coverage = round(covered / total, 4) if total else 1.0
    return {
        'total': total,
        'covered': covered,
        'missing': missing,
        'name_conflict': name_conflict,
        'code_format_diff': code_format_diff,
        'extra': extra,
        'coverage': coverage,
    }


def compare_value_domains(target_domains: dict, source_domains: dict) -> dict:
    """比对两份值域字典。"""
    matched = []
    target_only = []
    src_keys_matched = set()

    for tkey, td in target_domains.items():
        m = _match_domains(td, source_domains)
        if m:
            skey, sd = m
            src_keys_matched.add(skey)
            cmp = _compare_codes(td['codes'], sd['codes'])
            matched.append({
                'target_name': td['name'],
                'target_std_no': td['std_no'],
                'source_name': sd['name'],
                'source_std_no': sd['std_no'],
                'target_code_count': len(td['codes']),
                'source_code_count': len(sd['codes']),
                'coverage': cmp['coverage'],
                'covered': cmp['covered'],
                'missing_codes': cmp['missing'],
                'name_conflicts': cmp['name_conflict'],
                'code_format_diffs': cmp['code_format_diff'],
                'extra_codes': cmp['extra'],
                'fully_covered': cmp['coverage'] >= 1.0 and not cmp['name_conflict'],
            })
        else:
            target_only.append({
                'target_name': td['name'],
                'target_std_no': td['std_no'],
                'code_count': len(td['codes']),
            })

    source_only = []
    for skey, sd in source_domains.items():
        if skey not in src_keys_matched:
            # 排除已被匹配占用；源有但目标没有的值域
            source_only.append({
                'source_name': sd['name'],
                'source_std_no': sd['std_no'],
                'code_count': len(sd['codes']),
            })

    # 统计
    fully = [m for m in matched if m['fully_covered']]
    partial = [m for m in matched if not m['fully_covered']]
    return {
        'summary': {
            'target_domain_count': len(target_domains),
            'source_domain_count': len(source_domains),
            'matched_count': len(matched),
            'fully_covered_count': len(fully),
            'partial_covered_count': len(partial),
            'target_only_count': len(target_only),
            'source_only_count': len(source_only),
            'avg_coverage': round(
                sum(m['coverage'] for m in matched) / len(matched), 4) if matched else 0.0,
        },
        'matched': matched,
        'target_only': target_only,
        'source_only': source_only,
    }
