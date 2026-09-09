#!/usr/bin/env python3
"""读取用户修改后的Excel，与原始比对结果对比，输出差异清单

按新模式四设计，本脚本只负责「读」：
  1. 读出用户在 Excel 中修改的行（与原始比对结果的差异）；
  2. 把每处差异渲染成知识库写入指令（目标yaml + 条目内容），
     由模型执行写入（模型按 SKILL.md 模式四完成回写）。
脚本不直接改知识库，避免静默覆盖人工判断。
"""

import json
import openpyxl
import yaml
import sys
import os

def read_modified_excel(excel_path, compare_result_path, knowledge_base_path):
    """读取修改后的Excel，找出差异（只读，不改知识库；回写由模型按输出指令执行）"""
    
    # 读取Excel
    wb = openpyxl.load_workbook(excel_path)
    ws = wb['比对结果']
    
    # 收集Excel中的结果
    excel_results = {}
    for row in range(2, ws.max_row + 1):
        table_name = ws.cell(row=row, column=2).value
        field_display = ws.cell(row=row, column=3).value
        source_table = ws.cell(row=row, column=8).value
        source_field = ws.cell(row=row, column=9).value
        
        if table_name and field_display:
            field_cn = field_display.split('[')[0] if '[' in field_display else field_display
            key = (table_name, field_cn)
            excel_results[key] = {
                'source_table': source_table if source_table else '',
                'source_field': source_field if source_field else ''
            }
    
    # 读取原始比对结果
    with open(compare_result_path, 'r') as f:
        data = json.load(f)
    
    # 构建原始结果索引
    original_results = {}
    for item in data.get('matched', []):
        key = (item.get('table_chinese_name', ''), item.get('target_chinese_name', ''))
        original_results[key] = {
            'source_table': item.get('source_table_chinese_name', '') or '',
            'source_field': item.get('source_field_chinese_name', '') or ''
        }
    
    for item in data.get('modified', []):
        key = (item.get('table_chinese_name', ''), item.get('field_chinese_name', ''))
        original_results[key] = {
            'source_table': item.get('source_table_chinese_name', '') or '',
            'source_field': item.get('source_field_chinese_name', '') or ''
        }
    
    for item in data.get('new_fields', []):
        key = (item.get('table_chinese_name', ''), item.get('chinese_name', ''))
        original_results[key] = {
            'source_table': '',
            'source_field': ''
        }
    
    # 找出差异
    changes = []
    for key in excel_results:
        excel = excel_results[key]
        original = original_results.get(key)
        
        if not original:
            continue
        
        source_table_changed = excel['source_table'] != original['source_table']
        source_field_changed = excel['source_field'] != original['source_field']
        
        if source_table_changed or source_field_changed:
            changes.append({
                'key': key,
                'original': original,
                'excel': excel
            })
    
    print(f"发现 {len(changes)} 处修改")

    return changes

def render_kb_instructions(changes):
    """把差异渲染成知识库写入指令（供模型执行回写）"""
    instructions = []
    for change in changes:
        table_name, field_cn = change['key']
        excel = change['excel']
        original = change['original']

        if not excel['source_field'] and original['source_field']:
            # 用户清空了源字段 → 表示不应匹配 → user_custom_mappings 记否定结论
            instructions.append({
                'action': 'set_negative',
                'file': 'knowledge_base/user_custom_mappings.yaml',
                'entry': {
                    'target_table': table_name,
                    'target_field': field_cn,
                    'source_table': original['source_table'],
                    'source_field': '',
                    'status': 'negative',
                },
                'reason': f"用户在人工核对中清空映射（原: {original['source_table']}.{original['source_field']}）",
            })
        elif excel['source_field'] and not original['source_field']:
            # 用户新增了映射 → user_custom_mappings 记正向结论
            instructions.append({
                'action': 'set_positive',
                'file': 'knowledge_base/user_custom_mappings.yaml',
                'entry': {
                    'target_table': table_name,
                    'target_field': field_cn,
                    'source_table': excel['source_table'],
                    'source_field': excel['source_field'],
                    'status': 'confirmed',
                },
                'reason': '用户在人工核对中新增映射',
            })
        elif excel['source_field'] and original['source_field']:
            # 用户修改了映射 → 覆盖为新的正向结论
            instructions.append({
                'action': 'set_positive',
                'file': 'knowledge_base/user_custom_mappings.yaml',
                'entry': {
                    'target_table': table_name,
                    'target_field': field_cn,
                    'source_table': excel['source_table'],
                    'source_field': excel['source_field'],
                    'status': 'confirmed',
                },
                'reason': f"用户在人工核对中修改映射（原: {original['source_table']}.{original['source_field']}）",
            })
    return instructions


def print_instructions(changes):
    """打印差异清单与知识库写入指令（模型据此回写知识库）"""
    instructions = render_kb_instructions(changes)
    print(f"\n===== 知识库写入指令（共 {len(instructions)} 条，由模型执行） =====")
    for ins in instructions:
        e = ins['entry']
        print(f"\n[{ins['action']}] {e['target_table']}.{e['target_field']}")
        print(f"  文件: {ins['file']}")
        print(f"  条目: source_table={e['source_table']!r}, source_field={e['source_field']!r}, status={e['status']}")
        print(f"  依据: {ins['reason']}")
    return instructions

if __name__ == '__main__':
    if len(sys.argv) != 4:
        print("Usage: python3 read_modified_excel.py <excel_path> <compare_result.json> <knowledge_base_path>")
        print("输出差异清单与知识库写入指令（回写由模型按 SKILL.md 模式四执行）")
        sys.exit(1)

    changes = read_modified_excel(sys.argv[1], sys.argv[2], sys.argv[3])
    print_instructions(changes)
