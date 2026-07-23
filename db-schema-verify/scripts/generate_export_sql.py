#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 table_structure.md 生成导出 SQL 脚本
输入：table_structure.md（固定格式，参考 references/table_structure_template.md）
输出：导出 SQL 文件（Oracle 或 SQL Server）

用法：
  python generate_export_sql.py --md <md路径> --db-type <oracle|sqlserver> --output <输出路径>
  python generate_export_sql.py --md table_structure.md --db-type sqlserver --output export_sqlserver.sql

说明：
  从 MD 的"## 表清单"章节提取所有英文表名，扩展为 _TRAN/_LOG 后缀，
  替换到对应的 SQL 模板中生成导出脚本。
"""

import argparse
import re
import sys
from pathlib import Path


def extract_table_list_from_md(md_path: str) -> list:
    """
    从 table_structure.md 提取表清单。
    解析"## 表清单"章节中的表格，提取"英文表名"列。
    """
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 定位"## 表清单"章节
    # 匹配从 "## 表清单" 开始到下一个 "## " 或 "---" 之间的内容
    pattern = r'^##\s+表清单\s*\n(.*?)(?=^##\s|^---|\Z)'
    match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
    
    if not match:
        print("错误：未找到'## 表清单'章节", file=sys.stderr)
        print("请确保 MD 文件包含固定格式的表清单章节", file=sys.stderr)
        sys.exit(1)
    
    table_section = match.group(1)
    
    # 解析 Markdown 表格
    # 格式：| 序号 | 中文名 | 英文表名 | 是否有TRAN | 是否有LOG |
    #       |------|--------|----------|------------|-----------|
    #       | 1    | xxx    | XXX_XX   | 是/否      | 是/否     |
    
    tables = []
    lines = table_section.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        if not line or not line.startswith('|'):
            continue
        # 跳过分隔行（|---|---|...）
        if re.match(r'^\|[\s\-:|]+\|$', line):
            continue
        # 跳过表头行
        if '英文表名' in line or '表名' in line:
            continue
        
        # 解析表格行
        cells = [c.strip() for c in line.split('|')[1:-1]]  # 去掉首尾空元素
        
        if len(cells) >= 3:
            # 第3列是英文表名（索引2）
            table_name = cells[2].strip()
            if table_name and re.match(r'^[A-Z][A-Z0-9_]*$', table_name):
                tables.append(table_name)
    
    return tables


def expand_tables_with_suffix(base_tables: list) -> list:
    """
    将基础表名扩展为包含 _TRAN 和 _LOG 后缀的完整列表。
    """
    all_tables = set()
    for table in base_tables:
        all_tables.add(table)
        all_tables.add(f"{table}_TRAN")
        all_tables.add(f"{table}_LOG")
    return sorted(all_tables)


def generate_sql(tables: list, db_type: str, skill_dir: str) -> str:
    """
    根据数据库类型读取对应的 SQL 模板，替换表名列表。
    """
    # 定位 SQL 模板文件
    skill_path = Path(skill_dir)
    if db_type == 'oracle':
        template_path = skill_path / 'scripts' / 'export_table_structure_oracle.sql'
    elif db_type == 'sqlserver':
        template_path = skill_path / 'scripts' / 'export_table_structure_sqlserver.sql'
    else:
        print(f"错误：不支持的数据库类型 '{db_type}'", file=sys.stderr)
        sys.exit(1)
    
    if not template_path.exists():
        print(f"错误：SQL 模板文件不存在 '{template_path}'", file=sys.stderr)
        sys.exit(1)
    
    with open(template_path, 'r', encoding='utf-8') as f:
        template = f.read()
    
    # 构建 IN 子句的表名列表
    table_names = ',\n        '.join([f"'{t}'" for t in tables])
    
    # 替换模板中的占位符
    # Oracle 和 SQL Server 模板都用 {TABLE_LIST}
    sql_content = template.replace('{TABLE_LIST}', table_names)
    
    return sql_content


def main():
    parser = argparse.ArgumentParser(
        description='从 table_structure.md 生成导出 SQL 脚本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python generate_export_sql.py --md table_structure.md --db-type sqlserver --output export.sql
  python generate_export_sql.py --md ./docs/table_structure.md --db-type oracle --output export.sql
        """
    )
    
    parser.add_argument('--md', required=True, help='table_structure.md 文件路径')
    parser.add_argument('--db-type', required=True, choices=['oracle', 'sqlserver'], 
                        help='数据库类型：oracle 或 sqlserver')
    parser.add_argument('--output', required=True, help='输出 SQL 文件路径')
    parser.add_argument('--skill-dir', default=None,
                        help='Skill 目录路径（默认自动检测）')
    
    args = parser.parse_args()
    
    # 自动检测 Skill 目录
    if args.skill_dir:
        skill_dir = args.skill_dir
    else:
        # 脚本位于 scripts/ 目录，Skill 根目录在上一级
        script_dir = Path(__file__).parent
        skill_dir = str(script_dir.parent)
    
    # 检查 MD 文件
    md_path = Path(args.md)
    if not md_path.exists():
        print(f"错误：MD 文件不存在 '{md_path}'", file=sys.stderr)
        sys.exit(1)
    
    # 提取表清单
    print(f"正在解析 MD 文件：{md_path}", file=sys.stderr)
    base_tables = extract_table_list_from_md(str(md_path))
    
    if not base_tables:
        print("错误：未从'## 表清单'章节提取到任何表名", file=sys.stderr)
        print("请检查 MD 文件格式是否符合 references/table_structure_template.md 定义", file=sys.stderr)
        sys.exit(1)
    
    print(f"提取到 {len(base_tables)} 个基础表", file=sys.stderr)
    
    # 扩展表名（添加 _TRAN/_LOG 后缀）
    all_tables = expand_tables_with_suffix(base_tables)
    print(f"扩展为 {len(all_tables)} 个表（含 _TRAN/_LOG）", file=sys.stderr)
    
    # 生成 SQL
    print(f"数据库类型：{args.db_type}", file=sys.stderr)
    sql_content = generate_sql(all_tables, args.db_type, skill_dir)
    
    # 写入输出文件
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(sql_content)
    
    print(f"✅ 导出 SQL 已生成：{output_path}", file=sys.stderr)
    print(f"   共 {len(all_tables)} 个表", file=sys.stderr)


if __name__ == '__main__':
    main()
