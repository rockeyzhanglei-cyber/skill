#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Markdown报告生成器
生成逐字段对照表MD报告
"""

from datetime import datetime
from typing import Dict, List


class MarkdownReporter:
    """Markdown报告生成器"""

    def __init__(self, config: Dict = None):
        self.config = config or {}

    def _parse_table_name(self, table_name: str, table_chinese: str = None) -> tuple:
        """解析表名，分离中文名和英文名

        Args:
            table_name: 表名（可能是"中文名 英文名"或纯英文名）
            table_chinese: 表的中文名（可能与table_name相同）

        Returns:
            (中文名, 英文名) 元组
        """
        import re
        # 尝试匹配 "中文名 英文名" 格式
        match = re.match(r'^([^\s]+(?:\s+[^\s]+)?)\s+([A-Z][A-Z0-9_]+)$', table_name)
        if match:
            cn_name = match.group(1).strip()
            en_name = match.group(2).strip()
            return cn_name, en_name

        # 尝试匹配 "中文名[英文名]" 格式
        match = re.match(r'^(.+?)\[([A-Z][A-Z0-9_]+)\]$', table_name)
        if match:
            cn_name = match.group(1).strip()
            en_name = match.group(2).strip()
            return cn_name, en_name

        # 如果table_chinese和table_name相同，尝试从中提取
        if table_chinese and table_chinese == table_name:
            # 尝试从中文名中提取英文名（通常英文名在后面）
            match = re.match(r'^(.+?)\s+([A-Z][A-Z0-9_]+)$', table_chinese)
            if match:
                return match.group(1).strip(), match.group(2).strip()

        # 如果全是英文，返回空中文名
        if re.match(r'^[A-Z][A-Z0-9_]+$', table_name):
            return '', table_name

        # 默认情况
        return table_name, table_name

    def generate(self, results: Dict, output_path: str, title: str = "数据模型比对报告",
                 target_doc=None, source_doc=None):
        """生成MD报告

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
        new_total_pct = (new_count_total / total_fields * 100) if total_fields > 0 else 0

        md = f"""# {title}

**生成时间**：{datetime.now().strftime('%Y-%m-%d %H:%M')}
**比对原则**：原标准 ≥ 目标标准

## 📊 汇总统计

| 统计项 | 数量 | 占比 |
|--------|------|------|
| 总字段数 | {total_fields} | 100% |
| ✓ 满足 | {matched_count} | {matched_pct:.1f}% |
| ⚠ 修改 | {modified_count} | {modified_pct:.1f}% |
| ✗ 新增总数 | {new_count_total} | {new_total_pct:.1f}% |
| ✗ 去重后新增总数 | {new_count} | {new_pct:.1f}% |

**覆盖率**：{matched_pct:.1f}% | **需修改**：{modified_pct:.1f}% | **需新增**：{new_pct:.1f}%

"""

        if dedup_count > 0:
            md += f'**注**：新增字段总数为 {new_count_total} 个，其中 {dedup_count} 个字段已在其他表中新增（标记为"新增（去重）"），通过关联获取。去重后实际需新增 {new_count} 个字段。\n\n'

        md += "---\n\n## 📋 目录\n\n"

        # 构建目标标准的表和字段索引
        target_table_order = []  # 按源文件顺序的表名列表
        target_table_index = {}  # 表名 -> 表对象
        target_field_index = {}  # 表名 -> 字段列表

        if target_doc:
            for table in target_doc.tables:
                target_table_order.append(table.name)
                target_table_index[table.name] = table
                target_field_index[table.name] = table.fields

        # 构建原标准的表索引
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
        for idx, table_name in enumerate(ordered_tables, 1):
            stats = tables_stats.get(table_name, {'matched': 0, 'modified': 0, 'new': 0, 'new_dedup': 0})
            total = stats['matched'] + stats['modified'] + stats['new'] + stats['new_dedup']
            new_display = f"{stats['new']}"
            if stats['new_dedup'] > 0:
                new_display = f"{stats['new']}+{stats['new_dedup']}去重"

            # 获取表的中文名
            table_obj = target_table_index.get(table_name)
            display_name = table_name
            if table_obj:
                # 优先使用中文名
                if table_obj.chinese_name and table_obj.chinese_name != table_name:
                    display_name = f"{table_obj.chinese_name}({table_name})"
                elif table_obj.name:
                    display_name = table_obj.name

            md += f"{idx}. [{display_name}](#{table_name.replace(' ', '-').lower()}) - {total}字段 (🟢{stats['matched']} 🟠{stats['modified']} 🔴{new_display})\n"

        md += "\n---\n\n"

        # 生成每个表的详细内容
        for idx, table_name in enumerate(ordered_tables, 1):
            stats = tables_stats.get(table_name, {'matched': 0, 'modified': 0, 'new': 0, 'new_dedup': 0})
            total = stats['matched'] + stats['modified'] + stats['new'] + stats['new_dedup']
            new_display = f"{stats['new']}"
            if stats['new_dedup'] > 0:
                new_display = f"{stats['new']}+{stats['new_dedup']}去重"

            # 获取表的中文名
            table_obj = target_table_index.get(table_name)
            display_name = table_name
            if table_obj:
                # 优先使用中文名
                if table_obj.chinese_name and table_obj.chinese_name != table_name:
                    display_name = f"{table_obj.chinese_name}({table_name})"
                elif table_obj.name:
                    display_name = table_obj.name

            md += f"""## {idx}. {display_name}

**字段统计**：{total}字段 | 🟢{stats['matched']} 🟠{stats['modified']} 🔴{new_display}

| # | 目标字段 | 目标注释 | 目标类型 | 目标长度 | 目标约束 | 匹配结果 | 原标准表 | 原标准字段 | 原标准注释 | 备注 |
|---|---------|---------|---------|---------|---------|---------|---------|-----------|-----------|------|
"""

            row_num = 1

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

                key = (table_name, field_name)

                # 检查是否有匹配结果
                if key in matched_index:
                    match = matched_index[key]
                    source_table = match.get('source_table', '')
                    source_table_chinese = match.get('source_table_comment', '')
                    source_field = match.get('source_field', '')
                    source_field_chinese = match.get('source_comment', '')
                    match_type = match.get('match_type', '')
                    # 构建完整的原标准字段显示：表名[表英文名].字段名[字段中文名]
                    if source_table and source_field:
                        # 从 source_table 中分离中文名和英文名
                        # 格式可能是 "中文名 英文名" 或 "中文名[英文名]" 或纯英文名
                        table_cn, table_en = self._parse_table_name(source_table, source_table_chinese)
                        # 字段名直接使用
                        field_cn = source_field_chinese if source_field_chinese else source_field
                        field_en = source_field
                        source_display = f"{table_cn}[{table_en}].{field_cn}[{field_en}]"
                    elif source_field:
                        source_display = source_field
                    else:
                        source_display = '-'
                    md += f"| {row_num} | {field_name} | {field_chinese_name} | {field_data_type} | {field_length} | {field_constraint} | 🟢 满足 | {source_display} | {match_type} |\n"
                    row_num += 1

                # 检查是否有修改结果
                elif key in modified_index:
                    mod = modified_index[key]
                    source_table = mod.get('source_table', '')
                    source_table_chinese = mod.get('source_table_comment', '')
                    source_field = mod.get('source_field', '')
                    source_field_chinese = mod.get('source_comment', '')
                    modifications = ', '.join([f"{m['type']}:{m['current']}→{m['required']}" for m in mod['modifications']])
                    # 构建完整的原标准字段显示：表名[表英文名].字段名[字段中文名]
                    if source_table and source_field:
                        table_cn, table_en = self._parse_table_name(source_table, source_table_chinese)
                        field_cn = source_field_chinese if source_field_chinese else source_field
                        field_en = source_field
                        source_display = f"{table_cn}[{table_en}].{field_cn}[{field_en}]"
                    elif source_field:
                        source_display = source_field
                    else:
                        source_display = '-'
                    md += f"| {row_num} | {field_name} | {field_chinese_name} | {field_data_type} | {field_length} | {field_constraint} | 🟠 修改 | {source_display} | {modifications} |\n"
                    row_num += 1

                # 检查是否有新增结果
                elif key in new_fields_index or key in redirected_fields_index:
                    new = new_fields_index.get(key) or redirected_fields_index.get(key)
                    is_redirected = key in redirected_fields_index
                    is_dedup = new.get('deduplicated', False) if new else False

                    # 获取生成的英文字段名和目标表
                    generated_name = new.get('generated_name', '') if new else ''
                    # 优先使用source_table_name（源标准表名），如果没有则使用new_field_target
                    new_field_target = new.get('source_table_name', new.get('new_field_target', new.get('table_name', ''))) if new else ''

                    # 从new字段信息获取类型、长度、约束、说明（优先使用new中的信息）
                    field_type = new.get('type', field_data_type) if new else field_data_type
                    field_length = new.get('length', field_length) if new else field_length
                    field_constraint = new.get('constraint', field_constraint) if new else field_constraint
                    field_desc = new.get('description', field_description) if new else field_description
                    # 如果new中没有description，尝试使用comment作为说明
                    if not field_desc and new and new.get('comment'):
                        field_desc = new.get('comment', '')

                    # 目标标准区域：黑色字体
                    field_display = f"{field_chinese_name}[{field_name}]" if field_chinese_name else field_name
                    type_length_constraint = f"{field_type}/{field_length}/{field_constraint}" if field_type else f"{field_length}/{field_constraint}"
                    desc_display = field_desc

                    # 构建原标准对应字段显示（红色标注）
                    # 格式：原标准表名[表英文名].原标准字段名[字段中文名]
                    # 但因为是新增字段，所以显示建议的表名和字段名
                    if new_field_target and generated_name:
                        # 从source_table_index获取原标准表的中文名
                        source_table_obj = source_table_index.get(new_field_target) if source_table_index else None
                        source_table_cn = ''
                        if source_table_obj:
                            source_table_cn = getattr(source_table_obj, 'chinese_name', '') or ''

                        # 原标准区域：红色加粗字体
                        source_display = f"**<font color='red'>{source_table_cn}[{new_field_target}].{field_chinese_name}[{generated_name}]</font>**"
                        source_type_length = f"**<font color='red'>{field_type}/{field_length}/{field_constraint}</font>**" if field_type else f"**<font color='red'>{field_length}/{field_constraint}</font>**"
                        source_desc = f"**<font color='red'>{field_desc}</font>**" if field_desc else ''

                        if is_dedup:
                            # 去重字段：显示为新增但标注去重信息
                            dedup_source = new.get('dedup_source_table', '')
                            note = f"该字段已在 {dedup_source} 中新增，通过关联获取"
                            md += f"| {row_num} | {field_display} | {type_length_constraint} | {desc_display} | 🔴 新增（去重） | {source_display} | {source_type_length} | {source_desc} | {note} |\n"
                        elif is_redirected:
                            # 重定向字段：显示重定向信息
                            target_sub_table = new.get('table_name', '')
                            target_sub_field = new.get('name', '')
                            note = f"需新增（对应子表 {target_sub_table} 的字段 {target_sub_field}）"
                            md += f"| {row_num} | {field_display} | {type_length_constraint} | {desc_display} | 🔴 新增 | {source_display} | {source_type_length} | {source_desc} | {note} |\n"
                        else:
                            # 普通新增字段
                            note = ""
                            md += f"| {row_num} | {field_display} | {type_length_constraint} | {desc_display} | 🔴 新增 | {source_display} | {source_type_length} | {source_desc} | {note} |\n"
                    else:
                        # 如果没有生成字段名或目标表，使用原来的显示方式
                        source_display = '-'
                        source_type_length = '-'
                        source_desc = ''

                        if is_dedup:
                            dedup_source = new.get('dedup_source_table', '')
                            note = f"该字段已在 {dedup_source} 中新增，通过关联获取"
                            md += f"| {row_num} | {field_display} | {type_length_constraint} | {desc_display} | 🔴 新增（去重） | {source_display} | {source_type_length} | {source_desc} | {note} |\n"
                        elif is_redirected:
                            target_sub_table = new.get('table_name', '')
                            target_sub_field = new.get('name', '')
                            note = f"需新增（对应子表 {target_sub_table} 的字段 {target_sub_field}）"
                            md += f"| {row_num} | {field_display} | {type_length_constraint} | {desc_display} | 🔴 新增 | {source_display} | {source_type_length} | {source_desc} | {note} |\n"
                        else:
                            note = ""
                            md += f"| {row_num} | {field_display} | {type_length_constraint} | {desc_display} | 🔴 新增 | {source_display} | {source_type_length} | {source_desc} | {note} |\n"
                    row_num += 1

            # 处理新增表的情况（没有目标标准字段）
            if table_name not in target_field_index:
                for new_table in results['new_tables']:
                    if new_table['table_name'] == table_name:
                        # 新增表，显示推荐的表名
                        generated_table_name = new_table.get('generated_name', '')
                        table_chinese = new_table.get('chinese_name', '')
                        if generated_table_name and table_chinese:
                            table_display = f"**<font color='red'>{table_chinese}[{generated_table_name}]</font>**"
                        else:
                            table_display = f"**<font color='red'>{table_name}</font>**"

                        # 新增表，所有字段都是新增
                        md += f"| {row_num} | {table_display} | - | - | - | - | 🔴 新增表 | - | - | - | 原标准中没有对应的表，需新增 {new_table.get('field_count', 0)} 个字段 |\n"
                        row_num += 1
                        break

            md += "\n---\n\n"

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(md)

        return output_path
