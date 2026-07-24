#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成Oracle DDL脚本
用途：从CSV生成Oracle的DDL脚本（重建/修复）
适用版本：Oracle 11g/12c/19c（DDL语法通用）

用法：
    python generate_oracle_ddl.py --csv <csv_path> --mode rebuild --output <output_path>
    python generate_oracle_ddl.py --csv <csv_path> --mode fix --output <output_path>

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
import re
from collections import defaultdict
from pathlib import Path


def read_csv(csv_path, encoding='utf-8'):
    """读取CSV文件，返回行列表"""
    with open(csv_path, 'r', encoding=encoding) as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
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


def parse_pk_from_docx(docx_path):
    """从table_structure.md解析主键定义
    返回: {表名: [(字段名, 序号), ...], ...}
    识别规则：说明列中包含"复合主键"或"联合主键"的字段
    """
    if not docx_path or not Path(docx_path).exists():
        return {}
    
    pk_map = {}
    
    with open(docx_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 按表分割：## 表36：JCJLB（检查记录表）
    table_sections = re.split(r'^## 表\d+：(\w+)', content, flags=re.MULTILINE)
    
    for i in range(1, len(table_sections), 2):
        table_name = table_sections[i]
        table_content = table_sections[i + 1] if i + 1 < len(table_sections) else ''
        
        # 只解析到下一个## 表或---分隔符
        table_content = re.split(r'^## 表\d+|^---', table_content, flags=re.MULTILINE)[0]
        
        # 解析字段表格行
        pk_fields = []
        for line in table_content.split('\n'):
            if not line.startswith('|'):
                continue
            parts = [p.strip() for p in line.split('|')]
            if len(parts) < 8 or parts[1] in ('', '序号', '---'):
                continue
            
            seq = parts[1]
            col_name = parts[2]
            description = parts[7] if len(parts) > 7 else ''
            
            try:
                seq_int = int(seq)
            except ValueError:
                continue
            
            if '复合主键' in description or '联合主键' in description:
                pk_fields.append((col_name, seq_int))
        
        if pk_fields:
            pk_map[table_name] = pk_fields
    
    return pk_map


def build_oracle_type(row):
    """根据CSV行构建Oracle类型定义
    兼容输入：Oracle原生类型（VARCHAR2/NUMBER）或 SQL Server原生类型（varchar/decimal/numeric）
    """
    data_type = row.get('DATA_TYPE', '').strip()
    char_length = row.get('CHAR_LENGTH', '').strip()
    data_precision = row.get('DATA_PRECISION', '').strip()
    data_scale = row.get('DATA_SCALE', '').strip()
    data_length = row.get('DATA_LENGTH', '').strip()
    
    data_type_upper = data_type.upper()
    
    # ===== 字符串类型 =====
    if data_type_upper in ('VARCHAR2', 'NVARCHAR2'):
        if char_length:
            return f"{data_type_upper}({char_length})"
        return data_type_upper
    if data_type_upper == 'VARCHAR':
        if char_length:
            cl = int(char_length)
            if cl <= 0:
                return "VARCHAR2(4000)"
            return f"VARCHAR2({char_length})"
        if data_length and int(data_length) <= 0:
            return "VARCHAR2(4000)"
        return "VARCHAR2(4000)"
    if data_type_upper == 'NVARCHAR':
        if char_length:
            cl = int(char_length)
            if cl <= 0:
                return "NVARCHAR2(4000)"
            return f"NVARCHAR2({char_length})"
        if data_length and int(data_length) <= 0:
            return "NVARCHAR2(4000)"
        return "NVARCHAR2(4000)"
    
    # ===== 字符类型 =====
    if data_type_upper in ('CHAR', 'NCHAR'):
        if char_length:
            return f"{data_type_upper}({char_length})"
        return f"{data_type_upper}(1)"
    
    # ===== 数值类型 =====
    if data_type_upper == 'NUMBER':
        if data_precision and data_scale and int(data_scale) > 0:
            return f"NUMBER({data_precision},{data_scale})"
        elif data_precision:
            return f"NUMBER({data_precision})"
        else:
            return "NUMBER"
    if data_type_upper in ('DECIMAL', 'NUMERIC'):
        if data_precision and data_scale and int(data_scale) > 0:
            return f"NUMBER({data_precision},{data_scale})"
        elif data_precision:
            return f"NUMBER({data_precision})"
        else:
            return "NUMBER(18,0)"
    if data_type_upper == 'INT':
        return "NUMBER(10)"
    if data_type_upper == 'BIGINT':
        return "NUMBER(19)"
    if data_type_upper == 'SMALLINT':
        return "NUMBER(5)"
    if data_type_upper == 'TINYINT':
        return "NUMBER(3)"
    if data_type_upper == 'FLOAT':
        return "NUMBER(38)"
    if data_type_upper == 'REAL':
        return "NUMBER(18)"
    if data_type_upper in ('MONEY', 'SMALLMONEY'):
        return "NUMBER(19,4)"
    if data_type_upper == 'BIT':
        return "NUMBER(1)"
    
    # ===== 日期时间类型 =====
    if data_type_upper == 'DATE':
        return "DATE"
    if data_type_upper in ('DATETIME', 'SMALLDATETIME'):
        return "DATE"
    if data_type_upper in ('DATETIME2', 'DATETIMEOFFSET'):
        return "TIMESTAMP"
    if data_type_upper == 'TIME':
        return "TIMESTAMP"
    
    # ===== 大对象类型 =====
    if data_type_upper in ('CLOB', 'LONG', 'NCLOB'):
        return "CLOB"
    if data_type_upper == 'BLOB':
        return "BLOB"
    if data_type_upper == 'TEXT':
        return "CLOB"
    if data_type_upper == 'NTEXT':
        return "NCLOB"
    if data_type_upper == 'IMAGE':
        return "BLOB"
    if data_type_upper in ('VARBINARY', 'BINARY'):
        if char_length:
            cl = int(char_length)
            if cl <= 0 or cl > 2000:
                return "BLOB"
            return f"RAW({char_length})"
        if data_length and int(data_length) <= 0:
            return "BLOB"
        return "BLOB"
    if data_type_upper == 'UNIQUEIDENTIFIER':
        return "RAW(16)"
    if data_type_upper == 'XML':
        return "XMLTYPE"
    
    return data_type


def build_default_value(default_val):
    """处理默认值（兼容Oracle/SQL Server CSV）"""
    if not default_val:
        return None
    val = default_val.strip()
    if not val or val == '<Long>' or val.upper() == 'NULL':
        return None
    
    # 去掉 SQL Server 默认值的外层括号
    if val.startswith('(') and val.endswith(')'):
        val = val[1:-1].strip()
        if val.startswith('(') and val.endswith(')'):
            val = val[1:-1].strip()
    
    # SQL Server 函数转换
    val_upper = val.upper()
    if val_upper == 'GETDATE()':
        return 'SYSDATE'
    if val_upper == 'CURRENT_TIMESTAMP':
        return 'SYSTIMESTAMP'
    
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
    result = []
    for base, members in groups.items():
        members.sort(key=lambda n: (0 if n == base else (1 if n.endswith('_TRAN') else 2)))
        result.append(members)
    result.sort(key=lambda g: g[0])
    return result


def parse_tables(rows, pk_map=None):
    """从CSV行解析所有表结构"""
    if pk_map is None:
        pk_map = {}
    
    tables = defaultdict(lambda: {'columns': [], 'pk_cols': [], 'pk_constraint': '', 'table_comment': ''})
    
    # 用于跟踪已添加的字段，避免重复
    added_columns = defaultdict(set)
    
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
        
        # 去重：如果该字段已添加，跳过
        if col_name in added_columns[table_name]:
            continue
        added_columns[table_name].add(col_name)
        
        col_def = {
            'name': col_name,
            'type_def': build_oracle_type(row),
            'nullable': row.get('NULLABLE', 'Y') == 'Y',
            'default': build_default_value(row.get('DATA_DEFAULT', '')),
            'col_comment': col_comment,
            'column_id': int(row.get('COLUMN_ID', '0') or '0'),
        }
        
        tables[table_name]['columns'].append(col_def)
        tables[table_name]['table_comment'] = table_comment or tables[table_name]['table_comment']
        
        # 主键判断：优先使用table_structure.md中的定义，其次使用CSV中的PK_FLAG
        if table_name in pk_map:
            for pk_col_name, pk_position_from_md in pk_map[table_name]:
                if pk_col_name == col_name:
                    tables[table_name]['pk_cols'].append({
                        'name': col_name,
                        'position': pk_position_from_md,
                    })
                    tables[table_name]['pk_constraint'] = f'PK_{table_name}'
                    break
        elif pk_flag == 'Y' and pk_constraint and pk_constraint.upper() != 'NULL':
            tables[table_name]['pk_cols'].append({
                'name': col_name,
                'position': int(pk_position) if pk_position else 9999,
            })
            tables[table_name]['pk_constraint'] = pk_constraint
    
    return tables


def generate_rebuild_script(rows, table_scope=None, pk_map=None):
    """生成重建DDL脚本（DROP + CREATE）"""
    if pk_map is None:
        pk_map = {}
    
    tables = parse_tables(rows, pk_map)
    
    # 确定表列表
    if table_scope:
        all_tables = table_scope.get('all_tables', [])
        ordered_table_names = [t for t in all_tables if t in tables]
    else:
        ordered_table_names = sorted(tables.keys())
    
    table_groups = group_tables(ordered_table_names)
    
    # 生成SQL
    lines = []
    lines.append("-- ============================================")
    lines.append("-- Oracle 重建DDL脚本")
    lines.append(f"-- 表数量: {len(ordered_table_names)}")
    lines.append("-- 生成方式: 从基准库CSV自动生成")
    lines.append("-- 适用版本: Oracle 11g/12c/19c")
    lines.append("-- 说明: 每张表（原表+TRAN+LOG）为一个独立执行块，表间互不影响")
    lines.append("-- ============================================")
    lines.append("")
    lines.append("-- 第一阶段: 删除现有表（忽略表不存在错误）")
    lines.append("")
    
    # DROP阶段：每个DROP语句独立执行，每个BEGIN/END块后都有/
    # 使用PL/SQL块是为了忽略表不存在的错误（ORA-00942），不是业务异常捕获
    for group in table_groups:
        for table_name in group:
            lines.append(f"BEGIN")
            lines.append(f"    EXECUTE IMMEDIATE 'DROP TABLE {table_name} CASCADE CONSTRAINTS';")
            lines.append(f"EXCEPTION")
            lines.append(f"    WHEN OTHERS THEN")
            lines.append(f"        IF SQLCODE != -942 THEN RAISE; END IF;")
            lines.append(f"END;")
            lines.append("/")
        lines.append("")
    
    lines.append("-- 第二阶段: 创建新表")
    lines.append("")
    
    for group in table_groups:
        base_name = group[0]
        lines.append(f"-- 表: {base_name}")
        
        for table_name in group:
            table = tables[table_name]
            columns = sorted(table['columns'], key=lambda x: x['column_id'])
            
            lines.append(f"CREATE TABLE {table_name} (")
            
            col_defs = []
            # 收集主键字段名
            pk_col_names = set(c['name'] for c in table['pk_cols'])
            
            for col in columns:
                parts = [f"    {col['name']} {col['type_def']}"]
                
                # DEFAULT必须在NOT NULL之前
                if col['default'] is not None:
                    parts.append(f"DEFAULT {col['default']}")
                # 主键字段强制NOT NULL
                if not col['nullable'] or col['name'] in pk_col_names:
                    parts.append("NOT NULL")
                
                col_defs.append(" ".join(parts))
            
            lines.append(",\n".join(col_defs))
            lines.append(");")
            lines.append("/")
            lines.append("")
            
            # 主键约束 - 只有原表有主键
            is_derived_table = table_name.endswith('_TRAN') or table_name.endswith('_LOG')
            if table['pk_cols'] and not is_derived_table:
                pk_cols = sorted(table['pk_cols'], key=lambda x: x['position'])
                pk_col_names = [c['name'] for c in pk_cols]
                pk_constraint = table['pk_constraint'] or f"PK_{table_name}"
                lines.append(f"ALTER TABLE {table_name} ADD CONSTRAINT {pk_constraint} PRIMARY KEY ({', '.join(pk_col_names)});")
                lines.append("/")
                lines.append("")
    
    return "\n".join(lines)


def generate_fix_script(rows, table_scope=None):
    """生成修复DDL脚本（ALTER TABLE ADD/MODIFY）"""
    
    tables = parse_tables(rows)
    
    # 确定原表列表
    if table_scope:
        base_tables = table_scope.get('base_tables', [])
    else:
        base_tables = [t for t in tables.keys() if not t.endswith('_TRAN') and not t.endswith('_LOG')]
    
    lines = []
    lines.append("-- ============================================")
    lines.append("-- Oracle 修复DDL脚本")
    lines.append("-- 生成方式: 从基准库CSV自动生成")
    lines.append("-- 适用版本: Oracle 11g/12c/19c")
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
                parts = [f"{col_name} {type_def}"]
                if col['default'] is not None:
                    parts.append(f"DEFAULT {col['default']}")
                if not col['nullable']:
                    parts.append("NOT NULL")
                lines.append(f"ALTER TABLE {derived_table} ADD ({' '.join(parts)});")
            
            # 检查长度/类型不一致
            common = set(base_cols.keys()) & set(derived_cols.keys())
            for col_name in sorted(common):
                base_col = base_cols[col_name]
                derived_col = derived_cols[col_name]
                
                if base_col['type_def'] != derived_col['type_def']:
                    parts = [f"{col_name} {base_col['type_def']}"]
                    if base_col['default'] is not None:
                        parts.append(f"DEFAULT {base_col['default']}")
                    lines.append(f"-- 类型不一致: {derived_table}.{col_name} 原表={base_col['type_def']}, {suffix}表={derived_col['type_def']}")
                    lines.append(f"-- ALTER TABLE {derived_table} MODIFY ({' '.join(parts)});")
    
    lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description='生成Oracle DDL脚本')
    parser.add_argument('--csv', required=True, help='CSV文件路径')
    parser.add_argument('--mode', required=True, choices=['rebuild', 'fix'], help='模式: rebuild或fix')
    parser.add_argument('--output', required=True, help='输出SQL文件路径')
    parser.add_argument('--task-dir', help='任务目录路径（用于读取table_scope.json）')
    parser.add_argument('--encoding', default='utf-8', help='CSV编码（默认utf-8）')
    parser.add_argument('--doc', help='table_structure.md文档路径（用于读取主键定义）')
    args = parser.parse_args()
    
    # 读取CSV
    rows = read_csv(args.csv, args.encoding)
    print(f"✓ 读取CSV: {len(rows)} 行")
    
    # 解析table_structure.md获取主键定义
    pk_map = {}
    if args.doc:
        pk_map = parse_pk_from_docx(args.doc)
        if pk_map:
            print(f"✓ 从文档解析主键: {len(pk_map)} 张表有主键定义")
    
    # 加载表范围
    table_scope = None
    if args.task_dir:
        table_scope = load_table_scope(args.task_dir)
        if table_scope:
            print(f"✓ 加载表范围: {len(table_scope.get('base_tables', []))} 张原表")
    
    # 生成脚本
    if args.mode == 'rebuild':
        sql = generate_rebuild_script(rows, table_scope, pk_map)
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
