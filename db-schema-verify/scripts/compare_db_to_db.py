#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基准库CSV vs 目标库CSV 结构对比脚本
用途：对比两个数据库的表结构差异，生成修复脚本
使用方式：
    python compare_db_to_db.py --base-csv <base_csv_path> --target-csv <target_csv_path> --target-name <name> --target-db-type <oracle|sqlserver> --task-dir <dir> [--tables-scope <tables_list>]

输入：
    --base-csv: 基准库导出的CSV文件路径
    --target-csv: 目标库导出的CSV文件路径
    --target-name: 目标库名称（用于生成输出文件名）
    --target-db-type: 目标库数据库类型（oracle | sqlserver）
    --task-dir: 任务目录路径
    --tables-scope: 可选，表清单文件路径（限制对比范围）

输出：
    修复脚本 SQL 文件：fix_<db_type>_<target_name>.sql

参考规则：
    references/compare_rules_db_to_db.md - 库vs库比对规则
    references/type_mapping.md - 数据类型映射
"""

import csv
import sys
import re
import argparse
from pathlib import Path
from collections import defaultdict


# ============================================================
# CSV文件解析
# ============================================================

def read_csv(csv_path, encoding='utf-8'):
    """读取CSV文件，返回按表名分组的结构"""
    with open(csv_path, 'r', encoding=encoding) as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            clean_row = {k.strip(): v.strip() if v else '' for k, v in row.items()}
            rows.append(clean_row)
    
    # 按表名分组
    tables = defaultdict(list)
    for row in rows:
        table_name = row.get('TABLE_NAME', '')
        if table_name:
            tables[table_name].append(row)
    
    return dict(tables)


def build_column_def(row, db_type):
    """构建列定义（类型+长度+精度）"""
    data_type = row.get('DATA_TYPE', '').strip()
    data_length = row.get('DATA_LENGTH', '')
    data_precision = row.get('DATA_PRECISION', '')
    data_scale = row.get('DATA_SCALE', '')
    char_length = row.get('CHAR_LENGTH', '')
    nullable = row.get('NULLABLE', '').strip().upper()
    data_default = row.get('DATA_DEFAULT', '').strip()
    
    # 构建类型定义
    type_def = data_type
    if data_type in ('VARCHAR2', 'NVARCHAR2', 'CHAR', 'NCHAR', 'VARCHAR', 'NVARCHAR'):
        length = char_length or data_length
        if length:
            type_def = f"{data_type}({length})"
    elif data_type in ('NUMBER', 'DECIMAL'):
        if data_precision and data_scale and int(data_scale) > 0:
            type_def = f"{data_type}({data_precision},{data_scale})"
        elif data_precision:
            type_def = f"{data_type}({data_precision})"
    
    return {
        'type': type_def,
        'raw_type': data_type,
        'length': int(char_length or data_length or 0),
        'precision': int(data_precision) if data_precision else None,
        'scale': int(data_scale) if data_scale else None,
        'nullable': nullable == 'Y',
        'default': data_default
    }


def load_table_scope(scope_path):
    """加载表范围限制

    从表清单MD文件中提取基础表名，并扩展为包含 _TRAN/_LOG 的完整列表
    （与 generate_export_sql.py 的 expand_tables_with_suffix 行为保持一致）。
    """
    if not scope_path or not Path(scope_path).exists():
        return None
    
    with open(scope_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 从MD文件中提取表名
    pattern = r'^\|\s*\d+\s*\|\s*[^|]+\s*\|\s*([A-Z][A-Z0-9_]+)\s*\|'
    matches = re.findall(pattern, content, re.MULTILINE)
    
    # 扩展为包含 _TRAN/_LOG 的完整列表
    result = set()
    for name in matches:
        result.add(name)
        result.add(f"{name}_TRAN")
        result.add(f"{name}_LOG")
    return result


# ============================================================
# 比对逻辑
# ============================================================

def compare_tables(base_columns, target_columns, table_name, target_db_type):
    """对比两个表的结构差异"""
    issues = []
    
    base_col_map = {col.get('COLUMN_NAME', '').strip(): col for col in base_columns}
    target_col_map = {col.get('COLUMN_NAME', '').strip(): col for col in target_columns}
    
    # 1. 检查缺失字段（基准库有，目标库没有）
    for col_name in base_col_map:
        if col_name not in target_col_map:
            base_def = build_column_def(base_col_map[col_name], 'oracle')
            issues.append({
                'type': 'missing_column',
                'table': table_name,
                'column': col_name,
                'base_def': base_def,
                'severity': 'safe',
                'fix': generate_add_column_sql(table_name, col_name, base_def, target_db_type)
            })
    
    # 2. 检查多余字段（目标库有，基准库没有）
    for col_name in target_col_map:
        if col_name not in base_col_map:
            target_def = build_column_def(target_col_map[col_name], target_db_type)
            # 判断是否影响入库
            if not target_def['nullable'] and not target_def['default']:
                issues.append({
                    'type': 'extra_required_column',
                    'table': table_name,
                    'column': col_name,
                    'target_def': target_def,
                    'severity': 'unsafe',
                    'fix': f"-- 多余必填字段（可能影响入库）\n-- {table_name}.{col_name} {target_def['type']}"
                })
            # 可空或有默认值的多余字段忽略
    
    # 3. 检查共同字段的差异
    for col_name in base_col_map:
        if col_name not in target_col_map:
            continue
        
        base_def = build_column_def(base_col_map[col_name], 'oracle')
        target_def = build_column_def(target_col_map[col_name], target_db_type)
        
        # 3a. 类型不一致
        if base_def['raw_type'] != target_def['raw_type']:
            issues.append({
                'type': 'type_mismatch',
                'table': table_name,
                'column': col_name,
                'base_def': base_def,
                'target_def': target_def,
                'severity': 'unsafe',
                'fix': generate_modify_sql(table_name, col_name, base_def, target_db_type)
            })
        
        # 3b. 长度/精度不足
        # 注意：使用独立if而非elif，避免类型/长度问题掩盖可空性和默认值差异
        if base_def['length'] > target_def['length'] or \
             (base_def['precision'] and target_def['precision'] and base_def['precision'] > target_def['precision']):
            issues.append({
                'type': 'length_insufficient',
                'table': table_name,
                'column': col_name,
                'base_def': base_def,
                'target_def': target_def,
                'severity': 'safe',
                'fix': generate_modify_sql(table_name, col_name, base_def, target_db_type)
            })
        
        # 3c. 可空性不一致
        if base_def['nullable'] != target_def['nullable']:
            issues.append({
                'type': 'nullable_mismatch',
                'table': table_name,
                'column': col_name,
                'base_def': base_def,
                'target_def': target_def,
                'severity': 'unsafe',
                'fix': generate_modify_sql(table_name, col_name, base_def, target_db_type)
            })
        
        # 3d. 默认值不一致
        if base_def['default'] != target_def['default'] and (base_def['default'] or target_def['default']):
            issues.append({
                'type': 'default_mismatch',
                'table': table_name,
                'column': col_name,
                'base_def': base_def,
                'target_def': target_def,
                'severity': 'unsafe',
                'fix': generate_modify_sql(table_name, col_name, base_def, target_db_type)
            })
    
    return issues


# ============================================================
# SQL生成
# ============================================================

def generate_add_column_sql(table_name, col_name, col_def, db_type):
    """生成ADD COLUMN语句"""
    if db_type == 'oracle':
        type_str = convert_type_to_oracle(col_def)
        return f'ALTER TABLE "{table_name}" ADD ("{col_name}" {type_str});'
    else:
        type_str = convert_type_to_sqlserver(col_def)
        return f"ALTER TABLE [{table_name}] ADD [{col_name}] {type_str} NULL;"


def generate_modify_sql(table_name, col_name, base_def, db_type):
    """生成MODIFY语句"""
    if db_type == 'oracle':
        type_str = convert_type_to_oracle(base_def)
        nullable_str = 'NULL' if base_def['nullable'] else 'NOT NULL'
        return f'ALTER TABLE "{table_name}" MODIFY ("{col_name}" {type_str} {nullable_str});'
    else:
        type_str = convert_type_to_sqlserver(base_def)
        nullable_str = 'NULL' if base_def['nullable'] else 'NOT NULL'
        return f"ALTER TABLE [{table_name}] ALTER COLUMN [{col_name}] {type_str} {nullable_str};"


def convert_type_to_oracle(col_def):
    """转换为Oracle类型"""
    raw_type = col_def['raw_type']
    if raw_type in ('VARCHAR', 'NVARCHAR'):
        return f"VARCHAR2({col_def['length']})"
    elif raw_type in ('DECIMAL',):
        if col_def['precision'] and col_def['scale']:
            return f"NUMBER({col_def['precision']},{col_def['scale']})"
        elif col_def['precision']:
            return f"NUMBER({col_def['precision']})"
        else:
            return "NUMBER"
    elif raw_type == 'DATETIME':
        return 'DATE'
    else:
        return raw_type


def convert_type_to_sqlserver(col_def):
    """转换为SQL Server类型"""
    raw_type = col_def['raw_type']
    if raw_type in ('VARCHAR2', 'VARCHAR'):
        return f"VARCHAR({col_def['length']})"
    elif raw_type in ('NUMBER', 'DECIMAL'):
        if col_def['precision'] and col_def['scale']:
            return f"DECIMAL({col_def['precision']},{col_def['scale']})"
        elif col_def['precision']:
            return f"DECIMAL({col_def['precision']})"
        else:
            return "DECIMAL(38)"
    elif raw_type in ('DATE', 'TIMESTAMP'):
        return 'DATETIME'
    else:
        return raw_type


# ============================================================
# 主流程
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description='对比基准库CSV与目标库CSV的结构差异',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python compare_db_to_db.py --base-csv base.csv --target-csv target.csv --target-name dev --target-db-type oracle --task-dir ./task
        """
    )
    
    parser.add_argument('--base-csv', required=True, help='基准库CSV文件路径')
    parser.add_argument('--target-csv', required=True, help='目标库CSV文件路径')
    parser.add_argument('--target-name', required=True, help='目标库名称（用于输出文件名）')
    parser.add_argument('--target-db-type', required=True, choices=['oracle', 'sqlserver'],
                        help='目标库数据库类型')
    parser.add_argument('--task-dir', required=True, help='任务目录路径')
    parser.add_argument('--tables-scope', default=None, help='表清单文件路径（可选）')
    
    args = parser.parse_args()
    
    # 读取CSV
    print(f"正在读取基准库CSV：{args.base_csv}", file=sys.stderr)
    base_tables = read_csv(args.base_csv)
    print(f"基准库包含 {len(base_tables)} 个表", file=sys.stderr)
    
    print(f"正在读取目标库CSV：{args.target_csv}", file=sys.stderr)
    target_tables = read_csv(args.target_csv)
    print(f"目标库包含 {len(target_tables)} 个表", file=sys.stderr)
    
    # 加载表范围
    table_scope = load_table_scope(args.tables_scope)
    if table_scope:
        print(f"表范围限制：{len(table_scope)} 个表", file=sys.stderr)
    
    # 对比
    all_issues = []
    tables_to_compare = table_scope if table_scope else set(base_tables.keys())
    
    for table_name in tables_to_compare:
        if table_name not in base_tables:
            print(f"警告：基准库中不存在表 {table_name}", file=sys.stderr)
            continue
        if table_name not in target_tables:
            all_issues.append({
                'type': 'missing_table',
                'table': table_name,
                'severity': 'unsafe',
                'fix': f"-- 缺失表：{table_name}（需要创建）"
            })
            continue
        
        issues = compare_tables(
            base_tables[table_name],
            target_tables[table_name],
            table_name,
            args.target_db_type
        )
        all_issues.extend(issues)
    
    # 生成修复脚本
    unsafe_count = sum(1 for i in all_issues if i['severity'] == 'unsafe')
    safe_count = sum(1 for i in all_issues if i['severity'] == 'safe')
    
    output_path = Path(args.task_dir) / f"fix_{args.target_db_type}_{args.target_name}.sql"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(f"-- 修复脚本：{args.target_name}\n")
        f.write(f"-- 生成时间：{__import__('datetime').datetime.now()}\n")
        f.write(f"-- 不安全修改：{unsafe_count}，安全修改：{safe_count}\n\n")
        
        # 不安全修改（注释状态）
        if unsafe_count > 0:
            f.write("-- ============================================================\n")
            f.write("-- 不安全修改（需人工确认后放开注释）\n")
            f.write("-- ============================================================\n\n")
            for issue in all_issues:
                if issue['severity'] == 'unsafe':
                    f.write(f"-- {issue['type']}：{issue['table']}")
                    if 'column' in issue:
                        f.write(f".{issue['column']}")
                    f.write(f"\n{issue['fix']}\n\n")
        
        # 安全修改
        if safe_count > 0:
            f.write("-- ============================================================\n")
            f.write("-- 安全修改（可直接执行）\n")
            f.write("-- ============================================================\n\n")
            for issue in all_issues:
                if issue['severity'] == 'safe':
                    f.write(f"-- {issue['type']}：{issue['table']}.{issue['column']}\n")
                    f.write(f"{issue['fix']}\n\n")
    
    print(f"✅ 修复脚本已生成：{output_path}", file=sys.stderr)
    print(f"   不安全修改：{unsafe_count}，安全修改：{safe_count}", file=sys.stderr)


if __name__ == '__main__':
    main()
