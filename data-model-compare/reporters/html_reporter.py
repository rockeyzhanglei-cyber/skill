#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HTML报告生成器
生成漂亮的逐字段对照表HTML报告
"""

from datetime import datetime
from typing import Dict, List


class HTMLReporter:
    """HTML报告生成器"""

    def __init__(self, config: Dict = None):
        self.config = config or {}

    def generate(self, results: Dict, output_path: str, title: str = "数据模型比对报告",
                 target_doc=None, source_doc=None):
        """生成HTML报告

        Args:
            results: 比对结果
            output_path: 输出路径
            title: 报告标题
            target_doc: 目标标准标准化文档
            source_doc: 原标准标准化文档
        """

        # 统计数据
        total_fields = len(results['matched']) + len(results['modified_fields']) + len(results['new_fields'])
        matched_count = len(results['matched'])
        modified_count = len(results['modified_fields'])

        # 计算新增字段数量（去重后的）
        new_count_total = len(results['new_fields'])  # 总新增字段数（包括去重的）
        new_count = 0
        dedup_count = 0
        for new_field in results['new_fields']:
            if new_field.get('deduplicated'):
                dedup_count += 1  # 去重的字段不计入实际新增数
            else:
                new_count += 1

        matched_pct = (matched_count / total_fields * 100) if total_fields > 0 else 0
        modified_pct = (modified_count / total_fields * 100) if total_fields > 0 else 0
        new_pct = (new_count / total_fields * 100) if total_fields > 0 else 0

        coverage_pct = matched_pct

        # 表级别统计
        total_tables = 0
        matched_tables = 0
        modified_tables = 0
        new_tables_count = len(results['new_tables'])

        if target_doc:
            total_tables = len(target_doc.tables)

        # 构建目标标准的表和字段索引
        target_table_order = []  # 按源文件顺序的表名列表
        target_table_index = {}  # 表名 -> 表对象
        target_field_index = {}  # 表名 -> 字段列表

        if target_doc:
            for table in target_doc.tables:
                target_table_order.append(table.name)
                target_table_index[table.name] = table
                target_field_index[table.name] = table.fields

        # 构建原标准的表和字段索引
        source_table_index = {}
        if source_doc:
            for table in source_doc.tables:
                source_table_index[table.name] = table

        # 构建比对结果索引
        matched_index = {}  # (table_name, field_name) -> match_result
        modified_index = {}  # (table_name, field_name) -> modified_result
        new_fields_index = {}  # (table_name, field_name) -> new_field_result
        redirected_fields_index = {}  # (original_table_name, field_name) -> new_field_result (for redirected fields)

        for match in results['matched']:
            key = (match['table_name'], match['target_field'])
            matched_index[key] = match

        for mod in results['modified_fields']:
            key = (mod['table_name'], mod['field_name'])
            modified_index[key] = mod

        for new in results['new_fields']:
            # 检查是否是重定向的字段
            redirected_from = new.get('redirected_from', '')
            if redirected_from:
                # 重定向字段：用原始表名作为key
                key = (redirected_from, new['name'])
                redirected_fields_index[key] = new
            else:
                # 普通新增字段
                key = (new['table_name'], new['name'])
                new_fields_index[key] = new

        # 收集所有涉及的目标表（按源文件顺序）
        # 只包含目标标准中的表，不包括源标准的子表
        all_target_tables = set()
        for match in results['matched']:
            table_name = match['table_name']
            # 只添加目标标准中存在的表
            if table_name in target_table_index:
                all_target_tables.add(table_name)
        for mod in results['modified_fields']:
            table_name = mod['table_name']
            if table_name in target_table_index:
                all_target_tables.add(table_name)
        for new in results['new_fields']:
            table_name = new.get('table_name', '')
            # 对于重定向的字段，使用原始表名
            redirected_from = new.get('redirected_from', '')
            if redirected_from and redirected_from in target_table_index:
                all_target_tables.add(redirected_from)
            elif table_name in target_table_index:
                all_target_tables.add(table_name)
        for new_table in results['new_tables']:
            table_name = new_table['table_name']
            if table_name in target_table_index:
                all_target_tables.add(table_name)

        # 按源文件顺序排列表（只包含目标标准的表）
        ordered_tables = []
        if target_doc:
            for table_name in target_table_order:
                if table_name in all_target_tables:
                    ordered_tables.append(table_name)
        else:
            ordered_tables = sorted(all_target_tables)

        # 按表分组统计
        tables_stats = {}
        for table_name in ordered_tables:
            tables_stats[table_name] = {'matched': 0, 'modified': 0, 'new': 0, 'new_dedup': 0}

        for match in results['matched']:
            table_name = match['table_name']
            if table_name in tables_stats:
                tables_stats[table_name]['matched'] += 1

        for mod in results['modified_fields']:
            table_name = mod['table_name']
            if table_name in tables_stats:
                tables_stats[table_name]['modified'] += 1

        for new in results['new_fields']:
            # 对于重定向的字段，统计在原始表中
            redirected_from = new.get('redirected_from', '')
            table_name = redirected_from if redirected_from else new.get('table_name', '')
            if table_name in tables_stats:
                if new.get('deduplicated'):
                    tables_stats[table_name]['new_dedup'] += 1
                else:
                    tables_stats[table_name]['new'] += 1

        for new_table in results['new_tables']:
            table_name = new_table['table_name']
            if table_name in tables_stats:
                # 新增表的所有字段都算作新增
                tables_stats[table_name]['new'] = new_table.get('field_count', 0)

        # 统计表级别分类
        modified_tables_fields_total = 0
        modified_tables_matched_fields = 0
        modified_tables_modified_fields = 0
        modified_tables_new_fields = 0
        new_tables_total_fields = 0

        for table_name in ordered_tables:
            stats = tables_stats.get(table_name, {'matched': 0, 'modified': 0, 'new': 0})
            if table_name in [t['table_name'] for t in results['new_tables']]:
                new_tables_total_fields += stats['new']
            elif stats['modified'] > 0 or stats['new'] > 0:
                # 有修改或新增字段的表，都算作"需要修改的表"
                modified_tables += 1
                modified_tables_fields_total += stats['matched'] + stats['modified'] + stats['new']
                modified_tables_matched_fields += stats['matched']
                modified_tables_modified_fields += stats['modified']
                modified_tables_new_fields += stats['new']
            elif stats['matched'] > 0 and stats['new'] == 0:
                matched_tables += 1

        # 需要修改的表数量应该是modified_tables，不是new_tables_count
        # new_tables_count已经在上面统计了

        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f5f5f5; padding: 20px; }}
h1 {{ text-align: center; margin-bottom: 10px; color: #1a237e; font-size: 24px; }}
.subtitle {{ text-align: center; color: #666; margin-bottom: 20px; font-size: 14px; }}
.summary {{ background: white; border-radius: 12px; padding: 24px; margin-bottom: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
.summary h2 {{ color: #1a237e; margin-bottom: 20px; font-size: 20px; border-bottom: 2px solid #e0e0e0; padding-bottom: 10px; }}
.summary h3 {{ color: #1a237e; margin: 20px 0 12px 0; font-size: 16px; }}

/* 嵌套统计样式 */
.nested-stats {{ background: white; border-radius: 12px; padding: 24px; margin-bottom: 60px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
.nested-stats h2 {{ color: #1a237e; margin-bottom: 20px; font-size: 20px; border-bottom: 2px solid #e0e0e0; padding-bottom: 10px; }}
.stats-tree {{ display: flex; flex-direction: column; gap: 16px; }}
.tree-node {{ border-left: 4px solid #e0e0e0; padding-left: 20px; position: relative; }}
.tree-node::before {{ content: ''; position: absolute; left: -4px; top: 0; width: 4px; height: 100%; background: #e0e0e0; }}
.tree-node.total {{ border-left-color: #667eea; }}
.tree-node.matched {{ border-left-color: #11998e; }}
.tree-node.modified {{ border-left-color: #f093fb; }}
.tree-node.new {{ border-left-color: #fa709a; }}
.tree-label {{ font-size: 16px; font-weight: bold; color: #333; margin-bottom: 8px; display: flex; align-items: center; gap: 10px; }}
.tree-label .count {{ font-size: 24px; color: #1a237e; }}
.tree-label .unit {{ font-size: 14px; color: #666; font-weight: normal; }}
.tree-children {{ margin-left: 20px; margin-top: 12px; display: flex; gap: 20px; flex-wrap: wrap; }}
.child-item {{ background: #f5f5f5; border-radius: 8px; padding: 12px 16px; min-width: 150px; }}
.child-item .label {{ font-size: 12px; color: #666; margin-bottom: 4px; }}
.child-item .value {{ font-size: 20px; font-weight: bold; color: #333; }}
.child-item.green .value {{ color: #11998e; }}
.child-item.orange .value {{ color: #f093fb; }}
.child-item.red .value {{ color: #fa709a; }}

/* 进度条样式 */
.progress-container {{ margin: 20px 0; }}
.progress-bar {{ height: 24px; border-radius: 12px; background: #e0e0e0; overflow: hidden; display: flex; box-shadow: inset 0 2px 4px rgba(0,0,0,0.1); }}
.progress-bar .green {{ background: linear-gradient(90deg, #11998e 0%, #38ef7d 100%); transition: width 0.3s ease; }}
.progress-bar .orange {{ background: linear-gradient(90deg, #f093fb 0%, #f5576c 100%); transition: width 0.3s ease; }}
.progress-bar .red {{ background: linear-gradient(90deg, #fa709a 0%, #fee140 100%); transition: width 0.3s ease; }}
.legend {{ display: flex; gap: 20px; margin-top: 12px; font-size: 13px; flex-wrap: wrap; }}
.legend span {{ display: flex; align-items: center; gap: 6px; }}
.legend .dot {{ width: 14px; height: 14px; border-radius: 4px; }}

/* 目录样式 */
.toc {{ background: white; border-radius: 12px; padding: 20px; margin-bottom: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
.toc h2 {{ color: #1a237e; margin-bottom: 16px; font-size: 20px; border-bottom: 2px solid #e0e0e0; padding-bottom: 10px; }}
.toc-list {{ columns: 2; column-gap: 40px; }}
.toc-item {{ padding: 6px 0; font-size: 13px; break-inside: avoid; display: flex; align-items: center; gap: 8px; }}
.toc-item a {{ color: #1565c0; text-decoration: none; flex: 1; }}
.toc-item a:hover {{ text-decoration: underline; }}

/* Tag样式 */
.tag {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; white-space: nowrap; }}
.tag-green {{ background: #2e7d32; color: white; }}
.tag-blue {{ background: #2196f3; color: white; }}
.tag-orange {{ background: #f9a825; color: white; }}
.tag-red {{ background: #c62828; color: white; }}

/* 表格样式 */
.table-section {{ background: white; border-radius: 12px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); overflow: hidden; }}
.table-header {{ padding: 16px 20px; background: #1a237e; color: white; display: flex; justify-content: space-between; align-items: center; }}
.table-header h3 {{ font-size: 16px; }}
.table-header .badge {{ background: rgba(255,255,255,0.2); padding: 4px 12px; border-radius: 12px; font-size: 12px; }}
.table-content {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; font-size: 12px; border: 1px solid #ddd; }}
th, td {{ border: 1px solid #ddd; }}
th {{ background: #37474f; color: white; padding: 10px 8px; text-align: left; position: sticky; top: 0; white-space: nowrap; }}
td {{ padding: 8px; border-bottom: 1px solid #eee; vertical-align: top; }}
tr:hover {{ filter: brightness(0.95); }}
.row-green {{ background: #e8f5e9; }}
.row-blue {{ background: #e3f2fd; }}
.row-orange {{ background: #fff3e0; }}
.row-red {{ background: #ffebee; }}
.status-tag {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; white-space: nowrap; }}
.status-green {{ background: #2e7d32; color: white; }}
.status-blue {{ background: #1565c0; color: white; }}
.status-orange {{ background: #f9a825; color: white; }}
.status-red {{ background: #c62828; color: white; }}

@media (max-width: 768px) {{
    .toc-list {{ columns: 1; }}
    .stats-grid {{ grid-template-columns: 1fr; }}
}}
</style>
</head>
<body>
<h1>{title}</h1>
<p class="subtitle">生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}</p>

<div class="nested-stats">
<h2>📊 汇总统计</h2>

<div class="stats-tree">
<!-- 总表数 -->
<div class="tree-node total">
<div class="tree-label">
<span class="count">{total_tables}</span>
<span class="unit">张表（目标标准总表数）</span>
</div>

<div class="tree-children">
<!-- 完全匹配表 -->
<div class="tree-node matched">
<div class="tree-label">
<span class="count">{matched_tables}</span>
<span class="unit">张表完全匹配 🟢</span>
</div>
</div>

<!-- 需要修改表 -->
<div class="tree-node modified">
<div class="tree-label">
<span class="count">{modified_tables}</span>
<span class="unit">张表需要修改 🟠</span>
</div>
<div class="tree-children">
<div class="child-item">
<div class="label">字段总数</div>
<div class="value">{modified_tables_fields_total}</div>
</div>
<div class="child-item green">
<div class="label">🟢 满足</div>
<div class="value">{modified_tables_matched_fields}</div>
</div>
<div class="child-item orange">
<div class="label">🟠 修改</div>
<div class="value">{modified_tables_modified_fields}</div>
</div>
<div class="child-item red">
<div class="label">🔴 新增总数</div>
<div class="value">{new_count_total}</div>
</div>
<div class="child-item red">
<div class="label">🔴 去重后新增总数</div>
<div class="value">{new_count}</div>
</div>
</div>
</div>

<!-- 需要新增表 -->
<div class="tree-node new">
<div class="tree-label">
<span class="count">{new_tables_count}</span>
<span class="unit">张表需要新增 🔴</span>
</div>
<div class="tree-children">
<div class="child-item">
<div class="label">字段总数</div>
<div class="value">{new_tables_total_fields}</div>
</div>
</div>
</div>
</div>
</div>
</div>
"""

        # 构建目标标准的表和字段索引
        target_table_order = []  # 按源文件顺序的表名列表
        target_table_index = {}  # 表名 -> 表对象
        target_field_index = {}  # 表名 -> 字段列表

        if target_doc:
            for table in target_doc.tables:
                target_table_order.append(table.name)
                target_table_index[table.name] = table
                target_field_index[table.name] = table.fields

        # 构建原标准的表和字段索引
        source_table_index = {}
        if source_doc:
            for table in source_doc.tables:
                source_table_index[table.name] = table

        # 构建比对结果索引
        matched_index = {}  # (table_name, field_name) -> match_result
        modified_index = {}  # (table_name, field_name) -> modified_result
        new_fields_index = {}  # (table_name, field_name) -> new_field_result
        redirected_fields_index = {}  # (original_table_name, field_name) -> new_field_result (for redirected fields)

        for match in results['matched']:
            key = (match['table_name'], match['target_field'])
            matched_index[key] = match

        for mod in results['modified_fields']:
            key = (mod['table_name'], mod['field_name'])
            modified_index[key] = mod

        for new in results['new_fields']:
            # 检查是否是重定向的字段
            redirected_from = new.get('redirected_from', '')
            if redirected_from:
                # 重定向字段：用原始表名作为key
                key = (redirected_from, new['name'])
                redirected_fields_index[key] = new
            else:
                # 普通新增字段
                key = (new['table_name'], new['name'])
                new_fields_index[key] = new

        # 收集所有涉及的目标表（按源文件顺序）
        # 只包含目标标准中的表，不包括源标准的子表
        all_target_tables = set()
        for match in results['matched']:
            table_name = match['table_name']
            # 只添加目标标准中存在的表
            if table_name in target_table_index:
                all_target_tables.add(table_name)
        for mod in results['modified_fields']:
            table_name = mod['table_name']
            if table_name in target_table_index:
                all_target_tables.add(table_name)
        for new in results['new_fields']:
            table_name = new.get('table_name', '')
            # 对于重定向的字段，使用原始表名
            redirected_from = new.get('redirected_from', '')
            if redirected_from and redirected_from in target_table_index:
                all_target_tables.add(redirected_from)
            elif table_name in target_table_index:
                all_target_tables.add(table_name)
        for new_table in results['new_tables']:
            table_name = new_table['table_name']
            if table_name in target_table_index:
                all_target_tables.add(table_name)

        # 按源文件顺序排列表（只包含目标标准的表）
        ordered_tables = []
        if target_doc:
            for table_name in target_table_order:
                if table_name in all_target_tables:
                    ordered_tables.append(table_name)
        else:
            ordered_tables = sorted(all_target_tables)

        # 按表分组统计
        tables_stats = {}
        for table_name in ordered_tables:
            tables_stats[table_name] = {'matched': 0, 'modified': 0, 'new': 0, 'new_dedup': 0}

        for match in results['matched']:
            table_name = match['table_name']
            if table_name in tables_stats:
                tables_stats[table_name]['matched'] += 1

        for mod in results['modified_fields']:
            table_name = mod['table_name']
            if table_name in tables_stats:
                tables_stats[table_name]['modified'] += 1

        for new in results['new_fields']:
            # 对于重定向的字段，统计在原始表中
            redirected_from = new.get('redirected_from', '')
            table_name = redirected_from if redirected_from else new.get('table_name', '')
            if table_name in tables_stats:
                if new.get('deduplicated'):
                    tables_stats[table_name]['new_dedup'] += 1
                else:
                    tables_stats[table_name]['new'] += 1

        for new_table in results['new_tables']:
            table_name = new_table['table_name']
            if table_name in tables_stats:
                # 新增表的所有字段都算作新增
                tables_stats[table_name]['new'] = new_table.get('field_count', 0)

        # 生成目录
        html += """
<div class="toc">
<h2>📋 目录</h2>
<div class="toc-list" style="columns:2">
"""

        for idx, table_name in enumerate(ordered_tables, 1):
            stats = tables_stats.get(table_name, {'matched': 0, 'modified': 0, 'new': 0})
            total = stats['matched'] + stats['modified'] + stats['new']

            # 获取表的中文名
            table_obj = target_table_index.get(table_name)
            display_name = table_name
            if table_obj:
                # 优先使用中文名
                if table_obj.chinese_name and table_obj.chinese_name != table_name:
                    display_name = f"{table_obj.chinese_name}({table_name})"
                elif table_obj.name:
                    display_name = table_obj.name

            # 确定表的类型和标记
            if table_name in [t['table_name'] for t in results['new_tables']]:
                tag_class = 'tag-red'
                tag_text = '新增'
            elif stats['modified'] > 0 or stats['new'] > 0:
                # 有修改或新增字段的表，标记为"修改"
                tag_class = 'tag-orange'
                tag_text = '修改'
            else:
                # 只有满足字段的表，标记为"匹配"
                tag_class = 'tag-green'
                tag_text = '满足'

            html += f'<div class="toc-item"><span class="tag {tag_class}">{tag_text}</span> <a href="#section-{idx}">{idx}. {display_name}</a> <span style="color:#666;font-size:11px">[{total}字段: 🟢{stats["matched"]} 🟠{stats["modified"]} 🔴{stats["new"]}]</span></div>\n'

        html += '</div></div>\n\n'

        # 生成每个表的详细内容
        for idx, table_name in enumerate(ordered_tables, 1):
            stats = tables_stats.get(table_name, {'matched': 0, 'modified': 0, 'new': 0})
            total = stats['matched'] + stats['modified'] + stats['new']

            # 检查是否是新增表
            is_new_table = any(t['table_name'] == table_name for t in results['new_tables'])

            # 根据表的状态设置表头背景色
            if is_new_table:
                header_class = 'new'
            elif stats['modified'] > 0 or stats['new'] > 0:
                header_class = 'modified'
            else:
                header_class = 'matched'

            # 确定表的类型和标记
            if is_new_table:
                tag_class = 'tag-red'
                tag_text = '新增'
                header_class = 'new'
            elif stats['modified'] > 0 or stats['new'] > 0:
                # 有修改或新增字段的表，标记为"修改"
                tag_class = 'tag-orange'
                tag_text = '修改'
                header_class = 'modified'
            else:
                # 只有满足字段的表，标记为"匹配"
                tag_class = 'tag-green'
                tag_text = '满足'
                header_class = 'matched'

            # 获取表的中文名
            table_obj = target_table_index.get(table_name)
            display_name = table_name
            if table_obj:
                # 优先使用中文名
                if table_obj.chinese_name and table_obj.chinese_name != table_name:
                    display_name = f"{table_obj.chinese_name}({table_name})"
                elif table_obj.name:
                    display_name = table_obj.name

            html += f"""
<div class="table-section" id="section-{idx}">
<div class="table-header">
<h3><span class="tag {tag_class}">{tag_text}</span> {idx}. {display_name}</h3>
<span class="badge">{total}字段 | 🟢{stats['matched']} 🟠{stats['modified']} 🔴{stats['new']}</span>
</div>
<div class="table-content">
<table>
<thead>
<tr>
<th rowspan="2" style="width:3%">#</th>
<th colspan="4" style="background:#2e7d32;text-align:center;width:42%">目标标准（省平台v1.4.1）</th>
<th rowspan="2" style="width:15%">比对结果</th>
<th colspan="4" style="background:#e65100;text-align:center;width:42%">原标准（云南区域v5.5）</th>
</tr>
<tr>
<th style="background:#388e3c;width:10%">字段名</th>
<th style="background:#388e3c;width:8%">类型/长度/约束</th>
<th style="background:#388e3c;width:12%">说明</th>
<th style="background:#388e3c;width:8%">值域</th>
<th style="background:#f57c00;width:10%">对应字段</th>
<th style="background:#f57c00;width:8%">类型/长度/约束</th>
<th style="background:#f57c00;width:12%">说明</th>
<th style="background:#f57c00;width:8%">值域</th>
</tr>
</thead>
<tbody>
"""

            row_num = 1

            # 如果是新增表，也列出所有字段
            if is_new_table:
                # 获取推荐的表名
                new_table_info = next((t for t in results['new_tables'] if t['table_name'] == table_name), None)
                generated_table_name = new_table_info.get('generated_name', '') if new_table_info else ''
                table_chinese = new_table_info.get('chinese_name', '') if new_table_info else ''

                # 从target_field_index中获取新增表的所有字段
                if table_name in target_field_index:
                    fields = target_field_index[table_name]
                    for field in fields:
                        field_name = field.name if hasattr(field, 'name') else field['name']
                        field_chinese_name = field.chinese_name if hasattr(field, 'chinese_name') else field.get('chinese_name', '')
                        field_data_type = field.data_type if hasattr(field, 'data_type') else field.get('data_type', '')
                        field_length = field.length if hasattr(field, 'length') else field.get('length', 0)
                        field_constraint = field.constraint if hasattr(field, 'constraint') else field.get('constraint', '')
                        field_description = field.description if hasattr(field, 'description') else field.get('description', '')
                        field_format = field.format if hasattr(field, 'format') else field.get('format', '')

                        # 目标标准区域：黑色字体
                        field_display = f"{field_chinese_name}[{field_name}]" if field_chinese_name else field_name
                        # 优先使用完整的格式信息
                        if field_format:
                            type_length_constraint = f"{field_data_type}/{field_format}/{field_constraint}" if field_data_type else f"{field_format}/{field_constraint}"
                        else:
                            type_length_constraint = f"{field_data_type}/{field_length}/{field_constraint}" if field_data_type else f"{field_length}/{field_constraint}"
                        desc_display = field_description
                        value_domain = ""

                        result_cell = '<span class="status-tag status-red">🔴 新增</span>'

                        # 原标准区域：红色加粗字体
                        if generated_table_name and field_chinese_name:
                            # 从new_fields中查找该字段的推荐字段名
                            new_field_info = next((nf for nf in results['new_fields']
                                                  if nf.get('table_name') == table_name and nf.get('name') == field_name), None)
                            generated_field_name = new_field_info.get('generated_name', '') if new_field_info else ''

                            if generated_field_name:
                                if table_chinese:
                                    source_display = f"<span style='color:red;font-weight:bold'>{table_chinese}[{generated_table_name}].{field_chinese_name}[{generated_field_name}]</span>"
                                    if field_format:
                                        source_type_length = f"<span style='color:red;font-weight:bold'>{field_data_type}/{field_format}/{field_constraint}</span>" if field_data_type else f"<span style='color:red;font-weight:bold'>{field_format}/{field_constraint}</span>"
                                    else:
                                        source_type_length = f"<span style='color:red;font-weight:bold'>{field_data_type}/{field_length}/{field_constraint}</span>" if field_data_type else f"<span style='color:red;font-weight:bold'>{field_length}/{field_constraint}</span>"
                                    source_desc = f"<span style='color:red;font-weight:bold'>{field_description}</span>" if field_description else ''
                                else:
                                    source_display = f"<span style='color:red;font-weight:bold'>{generated_table_name}.{field_chinese_name}[{generated_field_name}]</span>"
                                    if field_format:
                                        source_type_length = f"<span style='color:red;font-weight:bold'>{field_data_type}/{field_format}/{field_constraint}</span>" if field_data_type else f"<span style='color:red;font-weight:bold'>{field_format}/{field_constraint}</span>"
                                    else:
                                        source_type_length = f"<span style='color:red;font-weight:bold'>{field_data_type}/{field_length}/{field_constraint}</span>" if field_data_type else f"<span style='color:red;font-weight:bold'>{field_length}/{field_constraint}</span>"
                                    source_desc = f"<span style='color:red;font-weight:bold'>{field_description}</span>" if field_description else ''
                            else:
                                source_display = '-'
                                source_type_length = '-'
                                source_desc = ''
                        else:
                            source_display = '-'
                            source_type_length = '-'
                            source_desc = ''

                        html += f"""<tr class="row-red">
<td>{row_num}</td>
<td>{field_display}</td>
<td>{type_length_constraint}</td>
<td>{desc_display}</td>
<td>{value_domain}</td>
<td>{result_cell}</td>
<td>{source_display}</td>
<td>{source_type_length}</td>
<td>{source_desc}</td>
<td>-</td>
</tr>
"""
                        row_num += 1
            else:
                # 按目标标准的字段顺序排列
                if table_name in target_field_index:
                    fields = target_field_index[table_name]
                else:
                    # 如果不在目标标准中（新增表），从比对结果中获取字段
                    fields = []
                    for new in results['new_fields']:
                        if new['table_name'] == table_name:
                            fields.append(new)

                # 遍历目标标准的所有字段
                for field in fields:
                    field_name = field.name if hasattr(field, 'name') else field['name']
                    field_chinese_name = field.chinese_name if hasattr(field, 'chinese_name') else field.get('chinese_name', '')
                    field_data_type = field.data_type if hasattr(field, 'data_type') else field.get('data_type', '')
                    field_length = field.length if hasattr(field, 'length') else field.get('length', 0)
                    field_constraint = field.constraint if hasattr(field, 'constraint') else field.get('constraint', '')
                    field_description = field.description if hasattr(field, 'description') else field.get('description', '')
                    field_format = field.format if hasattr(field, 'format') else field.get('format', '')

                    key = (table_name, field_name)

                    # 检查是否有匹配结果
                    if key in matched_index:
                        match = matched_index[key]
                        # 获取原标准字段信息
                        source_table_name = match.get('source_table', '')
                        source_table_chinese = match.get('source_table_comment', '')
                        source_field_name = match.get('source_field', '')
                        source_field_chinese = match.get('source_comment', '')
                        source_field_type = ''
                        source_field_length = ''
                        source_field_constraint = ''
                        source_field_description = ''
                        source_field_format = ''
                        # 从source_doc中获取原标准字段的详细信息
                        if source_doc and source_table_name in source_table_index:
                            source_table = source_table_index[source_table_name]
                            for sf in source_table.fields:
                                if sf.name == source_field_name:
                                    source_field_type = sf.data_type
                                    source_field_length = sf.length
                                    source_field_constraint = sf.constraint
                                    source_field_description = sf.description
                                    source_field_format = sf.format if hasattr(sf, 'format') else ''
                                    break

                        # 根据match_type显示不同的状态标签（含具体匹配策略）
                        match_type = match.get('match_type', '')
                        _match_labels = {
                            'dictionary': '🟢 满足(字典)',
                            'control_field': '🟢 满足(映射)',
                            'semantic_mapping': '🟢 满足(语义映射)',
                            'standard_reference': '🟢 满足(标准引用)',
                            'field_mapping': '🟢 满足(映射)',
                            'exact_chinese': '🟢 满足(精确)',
                            'exact_english': '🟢 满足(精确)',
                            'synonym': '🟢 满足(同义词)',
                            'semantic': '🟢 满足(语义)',
                            'keyword': '🟢 满足(关键词)',
                            'cross_table': '🟢 满足(跨表)',
                        }
                        label = _match_labels.get(match_type, '🟢 满足')
                        result_cell = f'<span class="status-tag status-green">{label}</span>'

                        # 合并字段名：中文名[英文名]
                        field_display = f"{field_chinese_name}[{field_name}]" if field_chinese_name else field_name
                        # 原标准字段：表名[英文名].字段名[中文名]
                        if source_table_name and source_field_name:
                            # 从 source_table_name 中分离中文名和英文名
                            import re
                            table_match = re.match(r'^(.+?)\s+([A-Z][A-Z0-9_]+)$', source_table_name)
                            if table_match:
                                table_cn = table_match.group(1).strip()
                                table_en = table_match.group(2).strip()
                            else:
                                table_cn = source_table_chinese if source_table_chinese else source_table_name
                                table_en = source_table_name
                            field_cn = source_field_chinese if source_field_chinese else source_field_name
                            field_en = source_field_name
                            source_field_display = f"{table_cn}[{table_en}].{field_cn}[{field_en}]"
                        elif source_field_name:
                            source_field_display = f"-[{source_field_name}]"
                        else:
                            source_field_display = "-"
                        # 合并类型/长度/约束
                        if field_format:
                            type_length_constraint = f"{field_data_type}/{field_format}/{field_constraint}" if field_data_type else f"{field_format}/{field_constraint}"
                        else:
                            type_length_constraint = f"{field_data_type}/{field_length}/{field_constraint}" if field_data_type else ""
                        if source_field_format:
                            source_type_length_constraint = f"{source_field_type}/{source_field_format}/{source_field_constraint}" if source_field_type else f"{source_field_format}/{source_field_constraint}"
                        else:
                            source_type_length_constraint = f"{source_field_type}/{source_field_length}/{source_field_constraint}" if source_field_type else ""
                        # 值域（如果有）
                        value_domain = ""

                        html += f"""<tr class="row-green">
<td>{row_num}</td>
<td>{field_display}</td>
<td>{type_length_constraint}</td>
<td>{field_description}</td>
<td>{value_domain}</td>
<td>{result_cell}</td>
<td>{source_field_display}</td>
<td>{source_type_length_constraint}</td>
<td>{source_field_description}</td>
<td>-</td>
</tr>
"""
                        row_num += 1

                    # 检查是否有修改结果
                    elif key in modified_index:
                        mod = modified_index[key]
                        # 获取原标准字段信息
                        source_table_name = mod.get('source_table', '')
                        source_table_chinese = mod.get('source_table_comment', '')
                        source_field_name = mod.get('source_field', '')
                        source_field_chinese = mod.get('source_comment', '')
                        source_field_type = ''
                        source_field_length = ''
                        source_field_constraint = ''
                        source_field_description = ''
                        source_field_format = ''
                        # 从source_doc中获取原标准字段的详细信息
                        if source_doc and source_table_name in source_table_index:
                            source_table = source_table_index[source_table_name]
                            for sf in source_table.fields:
                                if sf.name == source_field_name:
                                    if not source_field_chinese:
                                        source_field_chinese = sf.chinese_name
                                    source_field_type = sf.data_type
                                    source_field_length = sf.length
                                    source_field_constraint = sf.constraint
                                    source_field_description = sf.description
                                    source_field_format = sf.format if hasattr(sf, 'format') else ''
                                    break

                        # 使用中文描述修改内容，包含格式信息
                        mod_parts = []
                        for m in mod['modifications']:
                            if m['type'] == 'length':
                                # 获取当前和要求的格式信息
                                current_format = source_field_format if source_field_format else str(m['current'])
                                required_format = field_format if field_format else str(m['required'])
                                mod_parts.append(f"长度：{current_format}→{required_format}")
                            elif m['type'] == 'constraint':
                                mod_parts.append(f"约束：{m['current']}→{m['required']}")
                            else:
                                mod_parts.append(f"{m['type']}：{m['current']}→{m['required']}")
                        modifications = '；'.join(mod_parts)

                        # 匹配策略标签
                        mod_match_type = mod.get('match_type', '')
                        _mod_match_labels = {
                            'exact_chinese': '精确',
                            'exact_english': '精确',
                            'synonym': '同义词',
                            'semantic': '语义',
                            'keyword': '关键词',
                            'cross_table': '跨表',
                        }
                        mod_strategy = _mod_match_labels.get(mod_match_type, '')
                        strategy_suffix = f'({mod_strategy})' if mod_strategy else ''
                        result_cell = f'<span class="status-tag status-orange">🟠 修改{strategy_suffix}</span><br><small style="font-size:12px">{modifications}</small>'

                        # 合并字段名：中文名[英文名]
                        field_display = f"{field_chinese_name}[{field_name}]" if field_chinese_name else field_name
                        # 原标准字段：表名[英文名].字段名[中文名]
                        if source_table_name and source_field_name:
                            import re
                            table_match = re.match(r'^(.+?)\s+([A-Z][A-Z0-9_]+)$', source_table_name)
                            if table_match:
                                table_cn = table_match.group(1).strip()
                                table_en = table_match.group(2).strip()
                            else:
                                table_cn = source_table_chinese if source_table_chinese else source_table_name
                                table_en = source_table_name
                            field_cn = source_field_chinese if source_field_chinese else source_field_name
                            field_en = source_field_name
                            source_field_display = f"{table_cn}[{table_en}].{field_cn}[{field_en}]"
                        elif source_field_name:
                            source_field_display = f"-[{source_field_name}]"
                        else:
                            source_field_display = "-"
                        # 合并类型/长度/约束
                        if field_format:
                            type_length_constraint = f"{field_data_type}/{field_format}/{field_constraint}" if field_data_type else f"{field_format}/{field_constraint}"
                        else:
                            type_length_constraint = f"{field_data_type}/{field_length}/{field_constraint}" if field_data_type else ""
                        if source_field_format:
                            source_type_length_constraint = f"{source_field_type}/{source_field_format}/{source_field_constraint}" if source_field_type else f"{source_field_format}/{source_field_constraint}"
                        else:
                            source_type_length_constraint = f"{source_field_type}/{source_field_length}/{source_field_constraint}" if source_field_type else ""
                        # 值域（如果有）
                        value_domain = ""

                        html += f"""<tr class="row-orange">
<td>{row_num}</td>
<td>{field_display}</td>
<td>{type_length_constraint}</td>
<td>{field_description}</td>
<td>{value_domain}</td>
<td>{result_cell}</td>
<td>{source_field_display}</td>
<td>{source_type_length_constraint}</td>
<td>{source_field_description}</td>
<td>-</td>
</tr>
"""
                        row_num += 1

                    # 检查是否有新增结果（包括重定向字段）
                    elif key in new_fields_index or key in redirected_fields_index:
                        new = new_fields_index.get(key) or redirected_fields_index.get(key)
                        is_redirected = key in redirected_fields_index
                        is_dedup = new.get('deduplicated', False) if new else False

                        # 获取生成的英文字段名和目标表
                        generated_name = new.get('generated_name', '') if new else ''
                        # 优先使用source_table_name（源标准表名），如果没有则使用new_field_target
                        new_field_target = new.get('source_table_name', new.get('new_field_target', new.get('table_name', ''))) if new else ''

                        # 从new字段信息获取类型、长度、约束、说明、格式（优先使用new中的信息）
                        field_type = new.get('type', field_data_type) if new else field_data_type
                        field_length = new.get('length', field_length) if new else field_length
                        field_constraint = new.get('constraint', field_constraint) if new else field_constraint
                        field_desc = new.get('description', field_description) if new else field_description
                        field_format = new.get('format', field_format) if new else field_format
                        # 如果new中没有description，尝试使用comment作为说明
                        if not field_desc and new and new.get('comment'):
                            field_desc = new.get('comment', '')

                        # 构建原标准对应字段显示（红色标注）
                        if new_field_target and generated_name:
                            # 从source_table_index获取原标准表的中文名
                            source_table_obj = source_table_index.get(new_field_target) if source_table_index else None
                            source_table_cn = ''
                            if source_table_obj:
                                source_table_cn = getattr(source_table_obj, 'chinese_name', '') or ''

                            # 构建显示格式：表名[表英文名].字段中文名[字段英文名]
                            source_display = f"<span style='color:red;font-weight:bold'>{source_table_cn}[{new_field_target}].{field_chinese_name}[{generated_name}]</span>"
                            # 原标准区域的类型/长度/约束和说明也显示为红色加粗
                            if field_format:
                                source_type_length = f"<span style='color:red;font-weight:bold'>{field_type}/{field_format}/{field_constraint}</span>" if field_type else f"<span style='color:red;font-weight:bold'>{field_format}/{field_constraint}</span>"
                            else:
                                source_type_length = f"<span style='color:red;font-weight:bold'>{field_type}/{field_length}/{field_constraint}</span>" if field_type else f"<span style='color:red;font-weight:bold'>{field_length}/{field_constraint}</span>"
                            source_desc = f"<span style='color:red;font-weight:bold'>{field_desc}</span>" if field_desc else ''
                        else:
                            source_display = '-'
                            source_type_length = '-'
                            source_desc = ''

                        if is_dedup:
                            # 去重字段：显示为新增但标注去重信息
                            dedup_source = new.get('dedup_source_table', '')
                            result_cell = '<span class="status-tag status-red">🔴 新增（去重）</span>'
                            note = f"该字段已在 {dedup_source} 中新增，通过关联获取"
                        else:
                            result_cell = '<span class="status-tag status-red">🔴 新增</span>'
                            # 备注
                            if is_redirected:
                                # 重定向字段：显示重定向信息
                                target_sub_table = new.get('table_name', '')
                                target_sub_field = new.get('name', '')
                                note = f"需新增（对应子表 {target_sub_table} 的字段 {target_sub_field}）"
                            else:
                                note = ""

                        # 目标标准区域：黑色字体
                        field_display = f"{field_chinese_name}[{field_name}]" if field_chinese_name else field_name
                        if field_format:
                            type_length_constraint = f"{field_type}/{field_format}/{field_constraint}" if field_type else f"{field_format}/{field_constraint}"
                        else:
                            type_length_constraint = f"{field_type}/{field_length}/{field_constraint}" if field_type else f"{field_length}/{field_constraint}"
                        desc_display = field_desc
                        # 值域（如果有）
                        value_domain = ""

                        html += f"""<tr class="row-red">
<td>{row_num}</td>
<td>{field_display}</td>
<td>{type_length_constraint}</td>
<td>{desc_display}</td>
<td>{value_domain}</td>
<td>{result_cell}</td>
<td>{source_display}</td>
<td>{source_type_length}</td>
<td>{source_desc}</td>
<td>{note}</td>
</tr>
"""
                        row_num += 1

            html += '</tbody></table></div></div>\n'

        html += '</body></html>'

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)

        return output_path
