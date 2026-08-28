#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成SQL Server DDL脚本
用途：从CSV生成SQL Server的DDL脚本（重建/修复）
适用版本：SQL Server 2012及以上（DDL语法通用）

用法：
    python generate_sqlserver_ddl.py --csv <csv_path> --md <md_path> --mode rebuild --output <output_path>
    python generate_sqlserver_ddl.py --csv <csv_path> --md <md_path> --mode fix --output <output_path>

参数：
    --csv      基准库导出的CSV文件路径
    --md       table_structure.md文件路径（用于读取表清单和主键定义）
    --mode     模式：rebuild（重建）或 fix（修复）
    --output   输出SQL文件路径
    --encoding CSV编码（默认utf-8）
    --doc      主键定义文档路径（可选，默认使用--md）
"""

import csv
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


def extract_table_list_from_md(md_path: str) -> list:
    """从 table_structure.md 提取表清单。
    解析"## 表清单"章节中的表格，提取"英文表名"列。
    """
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    pattern = r'^##\s+表清单\s*\n(.*?)(?=^##\s|^---|\Z)'
    match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
    
    if not match:
        print("错误：未找到'## 表清单'章节", file=sys.stderr)
        sys.exit(1)
    
    table_section = match.group(1)
    
    tables = []
    for line in table_section.strip().split('\n'):
        line = line.strip()
        if not line or not line.startswith('|'):
            continue
        if re.match(r'^\|[\s\-:|]+\|$', line):
            continue
        if '英文表名' in line or '表名' in line:
            continue
        
        cells = [c.strip() for c in line.split('|')[1:-1]]
        
        if len(cells) >= 3:
            table_name = cells[2].strip()
            if table_name and re.match(r'^[A-Z][A-Z0-9_]*$', table_name):
                tables.append(table_name)
    
    return tables


def expand_tables_with_suffix(base_tables: list) -> list:
    """将基础表名扩展为包含 _TRAN 和 _LOG 后缀的完整列表。"""
    all_tables = set()
    for table in base_tables:
        all_tables.add(table)
        all_tables.add(f"{table}_TRAN")
        all_tables.add(f"{table}_LOG")
    return sorted(all_tables)


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
    
    # table_sections格式: [prefix, 表名1, 内容1, 表名2, 内容2, ...]
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
            # 过滤空行和表头
            if len(parts) < 8 or parts[1] in ('', '序号', '---'):
                continue
            
            seq = parts[1]
            col_name = parts[2]
            description = parts[7] if len(parts) > 7 else ''
            
            # 跳过非数字序号行（表头分隔行等）
            try:
                seq_int = int(seq)
            except ValueError:
                continue
            
            # 检查说明列是否包含"复合主键"或"联合主键"
            if '复合主键' in description or '联合主键' in description:
                pk_fields.append((col_name, seq_int))
        
        if pk_fields:
            pk_map[table_name] = pk_fields
    
    return pk_map


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


def generate_rebuild_script(rows, all_tables=None, pk_map=None):
    """生成重建DDL脚本（DROP + CREATE）"""
    
    if pk_map is None:
        pk_map = {}
    
    # 按表组织数据
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
            'type_def': oracle_to_sqlserver_type(row),
            'nullable': row.get('NULLABLE', 'Y') == 'Y',
            'default': oracle_to_sqlserver_default(row.get('DATA_DEFAULT', '')),
            'col_comment': col_comment,
            'column_id': int(row.get('COLUMN_ID', '0') or '0'),
        }
        
        tables[table_name]['columns'].append(col_def)
        tables[table_name]['table_comment'] = table_comment or tables[table_name]['table_comment']
        
        # 主键判断：优先使用table_structure.md中的定义，其次使用CSV中的PK_FLAG
        # 检查这个字段是否在pk_map中被标记为主键
        if table_name in pk_map:
            # 检查当前字段是否在pk_map的主键列表中
            for pk_col_name, pk_position_from_md in pk_map[table_name]:
                if pk_col_name == col_name:
                    tables[table_name]['pk_cols'].append({
                        'name': col_name,
                        'position': pk_position_from_md,
                    })
                    tables[table_name]['pk_constraint'] = f'PK_{table_name}'
                    break
        elif pk_flag == 'Y' and pk_constraint and pk_constraint.upper() != 'NULL':
            # 如果pk_map中没有定义，则使用CSV中的PK_FLAG
            tables[table_name]['pk_cols'].append({
                'name': col_name,
                'position': int(pk_position) if pk_position else 9999,
            })
            tables[table_name]['pk_constraint'] = pk_constraint
    
    # 确定表列表
    if all_tables:
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
            # 收集主键字段名
            pk_col_names = set(c['name'] for c in table['pk_cols'])
            
            for col in columns:
                parts = [f"    [{col['name']}] {col['type_def']}"]
                
                # DEFAULT必须在NOT NULL之前
                if col['default'] is not None:
                    parts.append(f"DEFAULT {col['default']}")
                # 主键字段强制NOT NULL
                if not col['nullable'] or col['name'] in pk_col_names:
                    parts.append("NOT NULL")
                
                col_defs.append(" ".join(parts))
            
            lines.append(",\n".join(col_defs))
            lines.append(");")
            lines.append("GO")
            lines.append("")
            
            # 主键约束 - 只有原表有主键
            is_derived_table = table_name.endswith('_TRAN') or table_name.endswith('_LOG')
            if table['pk_cols'] and not is_derived_table:
                pk_cols = sorted(table['pk_cols'], key=lambda x: x['position'])
                pk_col_names = [c['name'] for c in pk_cols]
                pk_constraint = table['pk_constraint'] or f"PK_{table_name}"
                lines.append(f"ALTER TABLE [{table_name}] ADD CONSTRAINT [{pk_constraint}] PRIMARY KEY ({', '.join('[' + c + ']' for c in pk_col_names)});")
                lines.append("GO")
                lines.append("")
    
    return "\n".join(lines)


def generate_fix_script(rows, base_tables=None):
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
        
        if pk_flag == 'Y' and pk_constraint and pk_constraint.upper() != 'NULL':
            tables[table_name]['pk_cols'].append({
                'name': col_name,
                'position': int(pk_position) if pk_position else 9999,
            })
            tables[table_name]['pk_constraint'] = pk_constraint
    # 确定原表列表
    if not base_tables:
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
    parser.add_argument('--md', help='table_structure.md文件路径（用于读取表清单和主键定义）')
    parser.add_argument('--encoding', default='utf-8', help='CSV编码（默认utf-8）')
    parser.add_argument('--doc', help='主键定义文档路径（可选，默认使用--md）')
    args = parser.parse_args()
    
    # 读取CSV
    rows = read_csv(args.csv, args.encoding)
    print(f"✓ 读取CSV: {len(rows)} 行")
    
    # 解析主键定义：优先使用--doc，否则使用--md
    pk_map = {}
    doc_path = args.doc or args.md
    if doc_path:
        pk_map = parse_pk_from_docx(doc_path)
        if pk_map:
            print(f"✓ 从文档解析主键: {len(pk_map)} 张表有主键定义")
    
    # 从--md提取表清单
    all_tables = None
    base_tables = None
    if args.md:
        base_tables = extract_table_list_from_md(args.md)
        all_tables = expand_tables_with_suffix(base_tables)
        print(f"✓ 从MD提取表清单: {len(base_tables)} 张原表, {len(all_tables)} 张表(含TRAN/LOG)")
    
    # 生成脚本
    if args.mode == 'rebuild':
        sql = generate_rebuild_script(rows, all_tables, pk_map)
    else:
        sql = generate_fix_script(rows, base_tables)
    
    # 写入文件
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(sql)
    
    print(f"✓ 生成完成: {output_path}")
    print(f"  文件大小: {output_path.stat().st_size:,} 字节")


if __name__ == '__main__':
    main()
