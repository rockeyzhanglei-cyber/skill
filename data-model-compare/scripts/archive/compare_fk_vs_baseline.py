#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FK 方向检查效果对比脚本
分别运行"基线（无 FK 检查）"和"带 FK 检查"两个版本，对比指标差异。
"""
import sys
import os
import json
import importlib.util
import shutil
from collections import Counter

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMP = os.path.expanduser('~/data-model-compare-docs/V6.0医疗服务_vs_省平台v1.4.1医疗部分/temp')
MATCHERS_DIR = os.path.join(SKILL_DIR, 'matchers')

sys.path.insert(0, SKILL_DIR)

from parsers.standard_parser import StandardDocument, StandardTable, StandardField, ValueDomain
from matchers.self_validator import self_validate


def load_standard(path: str) -> StandardDocument:
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    tables = []
    for t in data.get('tables', []):
        fields = []
        for fd in t.get('fields', []):
            vds = [
                ValueDomain(code=str(vd.get('code', '') or ''),
                            name=str(vd.get('name', '') or ''),
                            description=str(vd.get('description', '') or ''))
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
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, 'to_dict'):
        return obj.to_dict()
    from dataclasses import asdict, is_dataclass
    if is_dataclass(obj):
        return asdict(obj)
    return dict(obj.__dict__)


def clean_module_cache():
    """清除所有 standard_comparator 相关模块缓存。"""
    keys = list(sys.modules.keys())
    for key in keys:
        if 'standard_comparator' in key:
            del sys.modules[key]


def load_comparator(comparator_file):
    """动态加载指定 comparator 文件，返回 StandardComparator 类。"""
    clean_module_cache()
    spec = importlib.util.spec_from_file_location(
        'standard_comparator', comparator_file,
        # 确保子模块也能被正确解析
        submodule_search_locations=[MATCHERS_DIR]
    )
    mod = importlib.util.module_from_spec(spec)
    # 先加载依赖模块
    sys.modules['matchers.standard_comparator'] = mod
    spec.loader.exec_module(mod)
    return mod.StandardComparator


def run_comparator(comparator_file, label):
    """运行一次比对，返回统计结果。"""
    StandardComparator = load_comparator(comparator_file)
    
    src_path = os.path.join(TEMP, 'source_standard.json')
    tgt_path = os.path.join(TEMP, 'target_standard.json')
    source_doc = load_standard(src_path)
    target_doc = load_standard(tgt_path)
    
    comparator = StandardComparator()
    result = to_dict(comparator.compare(source_doc, target_doc))
    
    matched = result.get('matched', [])
    modified = result.get('modified', [])
    new_fields = result.get('new_fields', [])
    new_tables = result.get('new_tables', [])
    
    match_types = Counter(m.get('match_type', '?') for m in matched)
    mod_types = Counter(m.get('match_type', '?') for m in modified)
    
    with open(src_path, 'r', encoding='utf-8') as f:
        src_raw = json.load(f)
    with open(tgt_path, 'r', encoding='utf-8') as f:
        tgt_raw = json.load(f)
    
    sv = self_validate(result, src_raw, tgt_raw)
    leaks = sv['leaks']
    suspects = sv['suspects']
    
    total = len(matched) + len(modified) + len(new_fields)
    correct = (len(matched) + len(modified) - len(suspects)) + (len(new_fields) - len(leaks))
    acc = correct / total * 100 if total else 0.0
    
    leak_by_table = Counter(lk['table'] for lk in leaks)
    suspect_by_table = Counter(sp['table'] for sp in suspects)
    
    m_patient_leaks = [lk for lk in leaks if lk['table'] == 'm_patient']
    
    print(f'\n{"="*60}')
    print(f'  {label}')
    print(f'{"="*60}')
    print(f'  matched: {len(matched)}, modified: {len(modified)}')
    print(f'  new_fields: {len(new_fields)}, new_tables: {len(new_tables)}')
    print(f'  leak: {len(leaks)}, suspect: {len(suspects)}')
    print(f'  准确率: {acc:.2f}%')
    print(f'  m_patient 泄漏: {len(m_patient_leaks)} 条')
    print(f'\n  matched 类型: {dict(match_types)}')
    print(f'  modified 类型: {dict(mod_types)}')
    print(f'\n  泄漏按表分布:')
    for t, c in leak_by_table.most_common(20):
        print(f'    {t}: {c}')
    
    if m_patient_leaks:
        print(f'\n  m_patient 泄漏详情:')
        for lk in m_patient_leaks:
            sug = lk['suggested_source'][0]
            print(f'    {lk["chinese_name"]}({lk["field"]}) → {sug["table"]}.{sug["field"]}')
    
    return {
        'matched_count': len(matched),
        'modified_count': len(modified),
        'new_fields_count': len(new_fields),
        'new_tables_count': len(new_tables),
        'leaks': leaks,
        'suspects': suspects,
        'acc': acc,
        'match_types': match_types,
        'mod_types': mod_types,
        'leak_by_table': leak_by_table,
        'suspect_by_table': suspect_by_table,
    }


def cleanup_pycache():
    for d in [os.path.join(MATCHERS_DIR, '__pycache__'),
              os.path.join(SKILL_DIR, 'matchers', '__pycache__')]:
        if os.path.exists(d):
            for f in os.listdir(d):
                if f.endswith('.pyc'):
                    os.remove(os.path.join(d, f))


if __name__ == '__main__':
    BASE_PATH = os.path.join(MATCHERS_DIR, 'standard_comparator.py.bak_20260825_fk_dirfix')
    FK_PATH = os.path.join(MATCHERS_DIR, 'standard_comparator.py.with_fk_check')
    
    # 清理缓存
    cleanup_pycache()
    
    # 1. 运行基线（无 FK 检查）
    base = run_comparator(BASE_PATH, '基线版本（无 FK 方向检查）')
    
    # 清理缓存避免串扰
    clean_module_cache()
    cleanup_pycache()
    
    # 2. 运行带 FK 检查
    fk = run_comparator(FK_PATH, '带 FK 方向检查')
    
    # 3. 对比总结
    print(f'\n{"="*60}')
    print(f'  对比总结')
    print(f'{"="*60}')
    metrics = ['matched_count', 'modified_count', 'new_fields_count', 'new_tables_count']
    for m in metrics:
        bv = base[m]
        fv = fk[m]
        diff = fv - bv
        print(f'  {m:20s}: {bv:5d} → {fv:5d}  ({diff:+d})')
    print(f'  leak:                   {len(base["leaks"]):5d} → {len(fk["leaks"]):5d}  ({len(fk["leaks"]) - len(base["leaks"]):+d})')
    print(f'  suspect:                {len(base["suspects"]):5d} → {len(fk["suspects"]):5d}  ({len(fk["suspects"]) - len(base["suspects"]):+d})')
    print(f'  准确率:                 {base["acc"]:6.2f}% → {fk["acc"]:6.2f}%  ({fk["acc"] - base["acc"]:+.2f}%)')
    
    # 泄漏差异分析
    base_leak_set = set(lk['table'] + '.' + lk['field'] for lk in base['leaks'])
    fk_leak_set = set(lk['table'] + '.' + lk['field'] for lk in fk['leaks'])
    new_leak_items = fk_leak_set - base_leak_set
    removed_leak_items = base_leak_set - fk_leak_set
    
    # 新泄漏详情
    new_leaks = [lk for lk in fk['leaks'] if lk['table'] + '.' + lk['field'] in new_leak_items]
    removed_leaks = [lk for lk in base['leaks'] if lk['table'] + '.' + lk['field'] in removed_leak_items]
    
    print(f'\n  FK 检查新增泄漏: {len(new_leaks)} 条')
    for lk in new_leaks[:20]:
        sug = lk['suggested_source'][0]
        print(f'    + [{lk["table"]}] {lk["chinese_name"]}({lk["field"]}) → {sug["table"]}.{sug["field"]}')
    
    print(f'\n  FK 检查消除泄漏: {len(removed_leaks)} 条')
    for lk in removed_leaks[:20]:
        sug = lk['suggested_source'][0]
        print(f'    - [{lk["table"]}] {lk["chinese_name"]}({lk["field"]}) → {sug["table"]}.{sug["field"]}')
    
    # 恢复带 FK 检查到工作位置
    shutil.copy2(FK_PATH, os.path.join(MATCHERS_DIR, 'standard_comparator.py'))
    cache_path = os.path.expanduser('~/.cache/WinCode/skill/data-model-compare/matchers/standard_comparator.py')
    if os.path.exists(os.path.dirname(cache_path)):
        shutil.copy2(FK_PATH, cache_path)
    cleanup_pycache()
    print(f'\n  已恢复带 FK 检查版本到工作位置')