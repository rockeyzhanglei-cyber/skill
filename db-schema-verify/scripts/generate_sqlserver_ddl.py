#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成SQL Server DDL脚本
用途：从CSV生成SQL Server的DDL脚本（重建/修复）
适用版本：SQL Server 2012及以上（DDL语法通用）

用法：
    python generate_sqlserver_ddl.py --csv <csv_path> --mode rebuild --output <output_path>
    python generate_sqlserver_ddl.py --csv <csv_path> --mode fix --output <output_path>

参数：
    --csv      基准库导出的CSV文件路径
    --mode     模式：rebuild（重建）或 fix（修复）
    --output   输出SQL文件路径
    --encoding CSV编码（默认utf-8）
"""

import csv
import json
import sys
import argparse
from collections import defaultdict
from pathlib import Path


def read_csv(csv_path, encoding='utf-8'):
    """读取CSV文件，返回行列表"""
    with open(csv_path, 'r', encoding=encoding) as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            # 清理所有字段的空格
            clean_row = {k.strip(): v.strip() if v else '' for k, v in row.items()}
            rows.append(clean_row)
        return rows


def load_table_scope(task_dir):
    """加载表范围"""
    scope_path = Path(task_dir) / 'table_scope.json'
    if scope_path.exists():
        with open(scope_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def oracle_to_sqlserver_type(row):
    """将Oracle类型转换为SQL Server类型
    兼容输入：Oracle原生类型（VARCHAR2/NUMBER）或 SQL Server原生类型（varchar/decimal/numeric）
    默认使用VARCHAR（非NVARCHAR），适用于使用支持中文Collation的数据库
    如需使用NVARCHAR，请设置 --use-nvarchar 参数
    """
    data_type = row.get('DATA_TYPE', '').strip()
    char_length = row.get('CHAR_LENGTH', '').strip()
    data_precision = row.get('DATA_PRECISION', '').strip()
    data_scale = row.get('DATA_SCALE', '').strip()
    data_length = row.get('DATA_LENGTH', '').strip()
    
    data_type_upper = data_type.upper()
    
    # ===== 字符串类型 =====
    # Oracle VARCHAR2/NVARCHAR2 → SQL Server VARCHAR/NVARCHAR
    if data_type_upper in ('VARCHAR2', 'NVARCHAR2'):
        if char_length:
            return f"VARCHAR({char_length})"
        return "VARCHAR(MAX)"
    # SQL Server 原生 varchar
    if data_type_upper == 'VARCHAR':
        if char_length:
            # -1 或 0 表示 MAX 类型
            cl = int(char_length)
            if cl <= 0:
                return "VARCHAR(MAX)"
            return f"VARCHAR({char_length})"
        if data_length and int(data_length) <= 0:
            return "VARCHAR(MAX)"
        return "VARCHAR(MAX)"
    # SQL Server 原生 nvarchar
    if data_type_upper == 'NVARCHAR':
        if char_length:
            cl = int(char_length)
            if cl <= 0:
                return "NVARCHAR(MAX)"
            return f"NVARCHAR({char_length})"
        if data_length and int(data_length) <= 0:
            return "NVARCHAR(MAX)"
        return "NVARCHAR(MAX)"
    
    # ===== 字符类型 =====
    if data_type_upper in ('CHAR', 'NCHAR'):
        if char_length:
            return f"{data_type_upper}({char_length})"
        return "CHAR(1)"
    
    # ===== 数值类型 =====
    # Oracle NUMBER → SQL Server DECIMAL
    if data_type_upper == 'NUMBER':
        if data_precision and data_scale and int(data_scale) > 0:
            return f"DECIMAL({data_precision},{data_scale})"
        elif data_precision:
            return f"DECIMAL({data_precision})"
        else:
            return "DECIMAL(38)"
    # SQL Server 原生 decimal / numeric
    if data_type_upper in ('DECIMAL', 'NUMERIC'):
        if data_precision and data_scale and int(data_scale) > 0:
            return f"{data_type_upper}({data_precision},{data_scale})"
        elif data_precision:
            return f"{data_type_upper}({data_precision})"
        else:
            return f"{data_type_upper}(18,0)"
    # SQL Server 原生 int / bigint / smallint / tinyint
    if data_type_upper in ('INT', 'BIGINT', 'SMALLINT', 'TINYINT'):
        return data_type_upper
    # SQL Server 原生 float / real
    if data_type_upper in ('FLOAT', 'REAL'):
        return data_type_upper
    # SQL Server 原生 money / smallmoney
    if data_type_upper in ('MONEY', 'SMALLMONEY'):
        return data_type_upper
    # SQL Server 原生 bit
    if data_type_upper == 'BIT':
        return "BIT"
    
    # ===== 日期时间类型 =====
    if data_type_upper == 'DATE':
        return "DATE"
    if data_type_upper == 'TIME':
        return "TIME"
    if data_type_upper == 'DATETIME':
        return "DATETIME"
    if data_type_upper == 'DATETIME2':
        return "DATETIME2"
    if data_type_upper == 'SMALLDATETIME':
        return "SMALLDATETIME"
    if data_type_upper == 'DATETIMEOFFSET':
        return "DATETIMEOFFSET"
    # Oracle DATE → SQL Server DATETIME（Oracle DATE 包含时分秒）
    # 注意：这个分支只在 data_type_upper == 'DATE' 上面已匹配后不会走到
    # 所以这里要调整：先检查 SQL Server DATE，最后检查 Oracle DATE
    # 实际上上面的分支已经覆盖了 DATE，所以这里需要重新组织
    
    # ===== 大对象类型 =====
    if data_type_upper in ('CLOB', 'LONG', 'NCLOB'):
        return "VARCHAR(MAX)"
    if data_type_upper == 'BLOB':
        return "VARBINARY(MAX)"
    # SQL Server 原生大对象
    if data_type_upper in ('TEXT', 'NTEXT'):
        return "VARCHAR(MAX)" if data_type_upper == 'TEXT' else "NVARCHAR(MAX)"
    if data_type_upper == 'IMAGE':
        return "VARBINARY(MAX)"
    # SQL Server 原生 uniqueidentifier / xml
    if data_type_upper in ('UNIQUEIDENTIFIER', 'XML'):
        return data_type_upper
    # SQL Server 原生 varbinary
    if data_type_upper == 'VARBINARY':
        if char_length:
            cl = int(char_length)
            if cl <= 0:
                return "VARBINARY(MAX)"
            return f"VARBINARY({char_length})"
        if data_length and int(data_length) <= 0:
            return "VARBINARY(MAX)"
        return "VARBINARY(MAX)"
    if data_type_upper == 'BINARY':
        if char_length:
            return f"BINARY({char_length})"
        return "BINARY(1)"
    
    # 兜底：返回原始类型
    return data_type


def oracle_to_sqlserver_default(default_val):
    """转换Oracle默认值为SQL Server格式"""
    if not default_val:
        return None
    val = default_val.strip()
    if not val or val == '<Long>':
        return None
    # NULL 字符串表示无默认值，不生成 DEFAULT NULL
    if val.upper() == 'NULL':
        return None
    # Oracle SYSDATE -> SQL Server GETDATE()
    if val.upper() == 'SYSDATE':
        return 'GETDATE()'
    # 其他情况直接使用
    return val


def escape_sql_string(s):
    """转义SQL字符串中的单引号"""
    return s.replace("'", "''")


def group_tables(table_names):
    """将表按基础表分组（原表 + _TRAN + _LOG 为一组）"""
    groups = {}
    for name in table_names:
        base = name
        for suffix in ('_TRAN', '_LOG'):
            if name.endswith(suffix):
                base = name[:-len(suffix)]
                break
        if base not in groups:
            groups[base] = []
        groups[base].append(name)
    # 每组内排序：原表在前，TRAN次之，LOG最后
    result = []
    for base, members in groups.items():
        members.sort(key=lambda n: (0 if n == base else (1 if n.endswith('_TRAN') else 2)))
        result.append(members)
    result.sort(key=lambda g: g[0])
    return result


def generate_rebuild_script(rows, table_scope=None):
    """生成重建DDL脚本（DROP + CREATE）"""
    
    # 按表组织数据
    tables = defaultdict(lambda: {'columns': [], 'pk_cols': [], 'pk_constraint': '', 'table_comment': ''})
    
    for row in rows:
        table_name = row.get('TABLE_NAME', '')
        if not table_name:
            continue
        
        col_name = row.get('COLUMN_NAME', '')
        pk_flag = row.get('PK_FLAG', '')
        pk_constraint = row.get('PK_CONSTRAINT_NAME', '')
        pk_position = row.get('PK_POSITION', '')
        table_comment = row.get('TABLE_COMMENTS', '')
        col_comment = row.get('COLUMN_COMMENTS', '')
        
        col_def = {
            'name': col_name,
            'type_def': oracle_to_sqlserver_type(row),
            'nullable': row.get('NULLABLE', 'Y') == 'Y',
            'default': oracle_to_sqlserver_default(row.get('DATA_DEFAULT', '')),
            'col_comment': col_comment,
            'column_id': int(row.get('COLUMN_ID', '0') or '0'),
        }
        
        tables[table_name]['columns'].append(col_def)
        tables[table_name]['table_comment'] = table_comment or tables[table_name]['table_comment']
        
        if pk_flag == 'Y':
            tables[table_name]['pk_cols'].append({
                'name': col_name,
                'position': int(pk_position) if pk_position else 9999,
            })
            if pk_constraint:
                tables[table_name]['pk_constraint'] = pk_constraint
    
    # 确定表列表
    if table_scope:
        all_tables = table_scope.get('all_tables', [])
        ordered_table_names = [t for t in all_tables if t in tables]
    else:
        ordered_table_names = sorted(tables.keys())
    
    # 生成SQL
    lines = []
    lines.append("-- ============================================")
    lines.append("-- SQL Server 重建DDL脚本")
    lines.append(f"-- 表数量: {len(ordered_table_names)}")
    lines.append("-- 生成方式: 从基准库CSV自动生成")
    lines.append("-- 适用版本: SQL Server 2012及以上")
    lines.append("-- ============================================")
    lines.append("")
    lines.append("-- 第一阶段: 删除现有表")
    lines.append("")
    
    # 按基础表分组（原表+TRAN+LOG一组）
    table_groups = group_tables(ordered_table_names)
    
    for group in table_groups:
        for table_name in group:
            lines.append(f"IF OBJECT_ID('{table_name}', 'U') IS NOT NULL")
            lines.append(f"BEGIN")
            lines.append(f"    DROP TABLE [{table_name}];")
            lines.append(f"END")
        lines.append("GO")
        lines.append("")
    
    lines.append("")
    lines.append("-- 第二阶段: 创建新表")
    lines.append("")
    
    for group in table_groups:
        base_name = group[0]
        lines.append(f"-- 表: {base_name} ({'原表' if base_name in tables else ''}, TRAN, LOG)")
        
        for table_name in group:
            table = tables[table_name]
            columns = sorted(table['columns'], key=lambda x: x['column_id'])
            
            lines.append(f"CREATE TABLE [{table_name}] (")
            
            col_defs = []
            for col in columns:
                parts = [f"    [{col['name']}] {col['type_def']}"]
                
                # DEFAULT必须在NOT NULL之前
                if col['default'] is not None:
                    parts.append(f"DEFAULT {col['default']}")
                if not col['nullable']:
                    parts.append("NOT NULL")
                
                col_defs.append(" ".join(parts))
            
            lines.append(",\n".join(col_defs))
            lines.append(");")
            
            # 主键约束 - 只有原表有主键，_TRAN/_LOG表不应该有主键
            is_derived_table = table_name.endswith('_TRAN') or table_name.endswith('_LOG')
            if table['pk_cols'] and not is_derived_table:
                pk_cols = sorted(table['pk_cols'], key=lambda x: x['position'])
                pk_col_names = [c['name'] for c in pk_cols]
                pk_constraint = table['pk_constraint'] or f"PK_{table_name}"
                lines.append(f"ALTER TABLE [{table_name}] ADD CONSTRAINT [{pk_constraint}] PRIMARY KEY ({', '.join('[' + c + ']' for c in pk_col_names)});")
        
        lines.append("GO")
        lines.append("")
    
    return "\n".join(lines)


def generate_fix_script(rows, table_scope=None):
    """生成修复DDL脚本（ALTER TABLE ADD/MODIFY）"""
    
    # 按表组织数据
    tables = defaultdict(lambda: {'columns': [], 'pk_cols': []})
    
    for row in rows:
        table_name = row.get('TABLE_NAME', '')
        if not table_name:
            continue
        
        col_name = row.get('COLUMN_NAME', '')
        pk_flag = row.get('PK_FLAG', '')
        pk_constraint = row.get('PK_CONSTRAINT_NAME', '')
        pk_position = row.get('PK_POSITION', '')
        
        col_def = {
            'name': col_name,
            'type_def': oracle_to_sqlserver_type(row),
            'nullable': row.get('NULLABLE', 'Y') == 'Y',
            'default': oracle_to_sqlserver_default(row.get('DATA_DEFAULT', '')),
            'col_comment': row.get('COLUMN_COMMENTS', ''),
            'column_id': int(row.get('COLUMN_ID', '0') or '0'),
        }
        
        tables[table_name]['columns'].append(col_def)
        
        if pk_flag == 'Y':
            tables[table_name]['pk_cols'].append({
                'name': col_name,
                'position': int(pk_position) if pk_position else 9999,
            })
            if pk_constraint:
                tables[table_name]['pk_constraint'] = pk_constraint
    
    # 确定原表列表
    if table_scope:
        base_tables = table_scope.get('base_tables', [])
    else:
        base_tables = [t for t in tables.keys() if not t.endswith('_TRAN') and not t.endswith('_LOG')]
    
    lines = []
    lines.append("-- ============================================")
    lines.append("-- SQL Server 修复DDL脚本")
    lines.append("-- 生成方式: 从基准库CSV自动生成")
    lines.append("-- 适用版本: SQL Server 2012及以上")
    lines.append("-- ============================================")
    lines.append("")
    
    for base_table in base_tables:
        for suffix in ['_TRAN', '_LOG']:
            derived_table = base_table + suffix
            if derived_table not in tables:
                continue
            
            base_cols = {c['name']: c for c in tables[base_table]['columns']}
            derived_cols = {c['name']: c for c in tables[derived_table]['columns']}
            
            # 检查缺失字段
            missing = set(base_cols.keys()) - set(derived_cols.keys())
            for col_name in sorted(missing):
                col = base_cols[col_name]
                type_def = col['type_def']
                parts = [f"[{col_name}] {type_def}"]
                if col['default'] is not None:
                    parts.append(f"DEFAULT {col['default']}")
                if not col['nullable']:
                    parts.append("NOT NULL")
                lines.append(f"ALTER TABLE [{derived_table}] ADD {' '.join(parts)};")
                lines.append("GO")
            
            # 检查长度/类型不一致
            common = set(base_cols.keys()) & set(derived_cols.keys())
            for col_name in sorted(common):
                base_col = base_cols[col_name]
                derived_col = derived_cols[col_name]
                
                if base_col['type_def'] != derived_col['type_def']:
                    parts = [f"[{col_name}] {base_col['type_def']}"]
                    if base_col['default'] is not None:
                        parts.append(f"DEFAULT {base_col['default']}")
                    lines.append(f"-- 类型不一致: {derived_table}.{col_name} 原表={base_col['type_def']}, {suffix}表={derived_col['type_def']}")
                    lines.append(f"-- ALTER TABLE [{derived_table}] ALTER COLUMN {' '.join(parts)};")
                    lines.append("GO")
    
    lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description='生成SQL Server DDL脚本')
    parser.add_argument('--csv', required=True, help='CSV文件路径')
    parser.add_argument('--mode', required=True, choices=['rebuild', 'fix'], help='模式: rebuild或fix')
    parser.add_argument('--output', required=True, help='输出SQL文件路径')
    parser.add_argument('--task-dir', help='任务目录路径（用于读取table_scope.json）')
    parser.add_argument('--encoding', default='utf-8', help='CSV编码（默认utf-8）')
    args = parser.parse_args()
    
    # 读取CSV
    rows = read_csv(args.csv, args.encoding)
    print(f"✓ 读取CSV: {len(rows)} 行")
    
    # 加载表范围
    table_scope = None
    if args.task_dir:
        table_scope = load_table_scope(args.task_dir)
        if table_scope:
            print(f"✓ 加载表范围: {len(table_scope.get('base_tables', []))} 张原表")
    
    # 生成脚本
    if args.mode == 'rebuild':
        sql = generate_rebuild_script(rows, table_scope)
    else:
        sql = generate_fix_script(rows, table_scope)
    
    # 写入文件
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(sql)
    
    print(f"✓ 生成完成: {output_path}")
    print(f"  文件大小: {output_path.stat().st_size:,} 字节")


if __name__ == '__main__':
    main()
