#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
根据已计算的比对结果（iter_compare_result.json）生成 HTML / MD / XLSX 三件套报告。

与 main.py 的区别：本脚本不重新跑 LLM 比对，仅复用已有比对结果 + 标准文档，
负责把报告"展示层"打磨好：
  1. 标准名称从标题动态推导（不再把版本号如 v5.5 写死在代码里）
  2. 通过字段描述中的 CV 代码关联值域字典，填充源标准字段 value_domains
  3. 新增字段对应列只展示 表中文[表英文].字段中文（不带英文字段名）

用法：
  python scripts/generate_report.py <temp_dir> [reports_dir]
"""
import os
import re
import sys
import json

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SKILL_DIR)

from parsers.standard_parser import (StandardDocument, StandardTable, StandardField,
                                      ValueDomain)
from parsers.value_domain_parser import (parse_value_domains_from_flat_md,
                                          build_value_domain_index)
from reporters.html_reporter import HTMLReporter
from reporters.markdown_reporter import MarkdownReporter

CV_RE = re.compile(r'CV[\d.]+\d\[([^\]]+)\]')


def load_standard(path):
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    tables = []
    for t in data.get('tables', []):
        fields = []
        for fd in t.get('fields', []):
            vds = [ValueDomain(code=str(vd.get('code', '')),
                               name=str(vd.get('name', '')),
                               description=str(vd.get('description', '') or ''))
                   for vd in (fd.get('value_domains') or [])]
            fields.append(StandardField(
                name=fd.get('name', ''), chinese_name=fd.get('chinese_name', ''),
                data_type=fd.get('data_type', ''), length=fd.get('length', 0),
                constraint=fd.get('constraint', ''),
                description=fd.get('description', ''), value_domains=vds,
                data_element_id=fd.get('data_element_id', ''),
                format=fd.get('format', '')))
        tables.append(StandardTable(name=t.get('name', ''),
                                    chinese_name=t.get('chinese_name', ''),
                                    description=t.get('description', ''),
                                    fields=fields))
    return StandardDocument(source_file=data.get('source_file', path),
                            tables=tables, metadata=data.get('metadata', {}))


def enrich_source_value_domains(source_doc, vd_md_path):
    """通过字段描述里的 'CVxx[域名]' 关联值域字典，填充 source_doc 字段的 value_domains。"""
    if not vd_md_path or not os.path.exists(vd_md_path):
        print("  [值域] 未找到值域字典，跳过富集")
        return 0
    domains = parse_value_domains_from_flat_md(vd_md_path)
    idx = build_value_domain_index(domains)
    by_name = idx['by_name']
    linked = 0
    for t in source_doc.tables:
        for f in t.fields:
            if f.value_domains:
                continue
            m = CV_RE.search(f.description or '')
            if not m:
                continue
            dname = m.group(1)
            codes = by_name.get(dname)
            if not codes:
                continue
            f.value_domains = [ValueDomain(code=c, name=n)
                               for c, n in codes.items()]
            linked += 1
    print(f"  [值域] 关联值域字典：解析 {len(domains)} 个域表，填充 {linked} 个源字段")
    return linked


def derive_names(title):
    source_name = target_name = None
    base = title
    if base.endswith('数据模型比对报告'):
        base = base[:-len('数据模型比对报告')].strip()
    if ' vs ' in base:
        a, b = base.split(' vs ', 1)
        source_name, target_name = a.strip(), b.strip()
    return source_name, target_name


def prep(cr, exclude_table_prefixes=('DIC_',)):
    """把比对结果整理为报告层数据。

    报告层过滤（exclude_table_prefixes）：目标标准中的字典表（DIC_*，如
    DIC_REGIST_CODE 登记注册类型代码表）不是业务表，其"字段"实为值域条目，
    不应在业务报告中体现——从 matched / modified / new_fields / new_tables
    四个分组中整体剔除，使摘要统计与表分组同步减少。
    Excel 可编辑件保留全量（直接读 iter_compare_result.json），便于工程核对。
    """

    def _excluded(tname):
        return any(str(tname or '').startswith(p) for p in exclude_table_prefixes)

    matched = [{
        'table_name': m['table_name'], 'target_field': m['target_field'],
        'target_comment': m['target_chinese_name'], 'source_table': m['source_table'],
        'source_table_comment': m.get('source_table_chinese_name', ''),
        'source_field': m['source_field'],
        'source_comment': m.get('source_field_chinese_name', ''),
        'match_type': m['match_type'],
        'condition_display': m.get('condition_display', ''),
    } for m in cr['matched'] if not _excluded(m['table_name'])]
    modified_fields = [{
        'table_name': m['table_name'], 'field_name': m['field_name'],
        'field_comment': m['field_chinese_name'], 'source_table': m['source_table'],
        'source_table_comment': m.get('source_table_chinese_name', ''),
        'source_field': m['source_field'],
        'source_comment': m.get('source_field_chinese_name', ''),
        'match_type': m.get('match_type', ''),
        'modifications': m['modifications'],
        'condition_display': m.get('condition_display', ''),
    } for m in cr['modified'] if not _excluded(m['table_name'])]
    new_fields = []
    for n in cr['new_fields']:
        if _excluded(n['table_name']):
            continue
        nf = {
            'table_name': n['table_name'], 'name': n['name'],
            'comment': n['chinese_name'], 'type': n.get('data_type', ''),
            'length': n.get('length', 0), 'constraint': n.get('constraint', 'O'),
            'generated_name': n.get('generated_name', ''),
            'chinese_name': n['chinese_name'],
            'new_field_target': n.get('new_field_target', n['table_name']),
            'source_table_name': n.get('source_table_name',
                                       n.get('new_field_target', n['table_name'])),
            'description': n.get('description', ''),
            'value_domains': n.get('value_domains', []),
        }
        if n.get('deduplicated'):
            nf['deduplicated'] = True
            nf['dedup_note'] = n.get('dedup_note', '')
            nf['dedup_source_table'] = n.get('dedup_source_table', '')
        if n.get('redirected_from'):
            nf['redirected_from'] = n['redirected_from']
            nf['redirect_reason'] = n.get('redirect_reason', '')
        new_fields.append(nf)
    new_tables = [{
        'table_name': t['table_name'], 'chinese_name': t.get('chinese_name', ''),
        'generated_name': t.get('generated_name', ''),
        'field_count': t.get('field_count', 0),
        'reason': t.get('reason', ''),
    } for t in cr['new_tables'] if not _excluded(t['table_name'])]
    return {'matched': matched, 'modified_fields': modified_fields,
            'new_fields': new_fields, 'new_tables': new_tables}


def main():
    if len(sys.argv) < 2:
        print("用法: python generate_report.py <temp_dir> [reports_dir]")
        sys.exit(1)
    temp_dir = sys.argv[1]
    out_dir = sys.argv[2] if len(sys.argv) > 2 else os.path.join(temp_dir, '..', 'reports')
    out_dir = os.path.abspath(out_dir)
    os.makedirs(out_dir, exist_ok=True)

    print("加载标准文档与比对结果 ...")
    source_doc = load_standard(os.path.join(temp_dir, 'source_standard.json'))
    target_doc = load_standard(os.path.join(temp_dir, 'target_standard.json'))

    # 条件式值域约束装配（round6 固化）：读 conditional_constraints.json 的
    # rules 给 matched/modified 注入 condition_display（地址族/电话族），
    # 幂等（重复运行覆盖同值），保证 HTML/MD/XLSX 三件套同步展示。
    sys.path.insert(0, os.path.join(SKILL_DIR, 'scripts'))
    from apply_conditional_constraints import apply_condition_display
    cmp = apply_condition_display(temp_dir)
    if cmp is None:
        with open(os.path.join(temp_dir, 'iter_compare_result.json'),
                  'r', encoding='utf-8') as f:
            cmp = json.load(f)

    # 值域字典富集
    vd_md = os.path.join(temp_dir, 'source_md', '区域卫生信息平台数据传输规范 值域字典.md')
    if not os.path.exists(vd_md):
        vd_md = os.path.join(temp_dir, 'source_md', '区域卫生信息平台数据传输规范 值域字典_V6.0.2606.md')
    enrich_source_value_domains(source_doc, vd_md)

    report_data = prep(cmp)
    title = ("区域卫生信息平台数据传输规范V6.0 vs "
             "云南省全民健康信息平台数据接口标准规范v1.4.1 数据模型比对报告")
    source_name, target_name = derive_names(title)

    html_path = os.path.join(out_dir, 'compare_report.html')
    md_path = os.path.join(out_dir, 'compare_report.md')
    HTMLReporter({}).generate(report_data, html_path, title, target_doc,
                             source_doc, source_name=source_name,
                             target_name=target_name)
    print("  ✓ HTML:", html_path)
    MarkdownReporter({}).generate(report_data, md_path, title, target_doc,
                                 source_doc, source_name=source_name,
                                 target_name=target_name)
    print("  ✓ MD:", md_path)

    sys.path.insert(0, os.path.join(SKILL_DIR, 'scripts'))
    from generate_excel import generate_excel
    excel_path = os.path.join(out_dir, 'compare_editable.xlsx')
    generate_excel(os.path.join(temp_dir, 'iter_compare_result.json'),
                   os.path.join(temp_dir, 'target_standard.json'),
                   os.path.join(temp_dir, 'source_standard.json'), excel_path)
    print("  ✓ Excel:", excel_path)
    print("DONE")


if __name__ == '__main__':
    main()
