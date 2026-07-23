#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
table_structure.md 与 CSV 库表结构对比脚本

用途：对比基准库CSV与Word文档解析出的MD标准，生成修复脚本

使用方式：
    python compare_with_docx.py --md <md_path> --csv <csv_path> --db-type <oracle|sqlserver> --task-dir <dir> [--output <path>] [--encoding <enc>]

输入：
    --md: table_structure.md 文件路径（从Word文档解析生成）
    --csv: 基准库导出的CSV文件路径
    --db-type: 目标数据库类型（oracle | sqlserver）
    --task-dir: 任务目录路径

输出：
    修复脚本 SQL 文件

参考规则：
    references/compare_rules.md - 比对规则
    references/type_mapping.md - 数据类型映射
"""

import csv
import sys
import re
import argparse
from pathlib import Path


# ============================================================
# MD文件解析
# ============================================================

def parse_md_file(md_path):
    """
    解析 table_structure.md 文件，提取表清单和字段定义。

    MD文件格式：

        # 表清单
        | 序号 | 中文名 | 英文表名 | 是否有TRAN | 是否有LOG |
        ...

        ## 表1：JBYHRYXXB（医护人员信息表）
        ### 字段定义
        | 序号 | 数据元标识 | 数据元名称 | 约束 | 数据类型 | 表示格式 | 说明 |
        | 1 | YLJGDM | 医疗机构代码 | M | S1 | AN..64 | ... |

    返回：{
        'tables': {
            'TABLE_NAME': {
                'cn_name': '中文名',
                'has_tran': True/False,
                'has_log': True/False,
                'columns': [
                    {'seq': 1, 'id': 'YLJGDM', 'name': '医疗机构代码',
                      'constraint': 'M', 'data_type': 'S1', 'format': 'AN..64', 'comment': '...'},
                    ...
                ]
            }
        }
    }
    """
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()

    tables = {}

    # 按 ## 分割各表的章节
    sections = re.split(r'\n## ', content)

    for section in sections:
        # 匹配表头：表1：TABLE_NAME（中文名） 或 表1：TABLE_NAME - 中文名
        header_match = re.match(
            r'表\d+[：:]\s*([A-Z][A-Z0-9_]+)[（(]([^）)]+)[）)]', section
        )
        if not header_match:
            header_match = re.match(
                r'表\d+[：:]\s*([A-Z][A-Z0-9_]+)\s*[-—]\s*(.+)', section
            )
        if not header_match:
            continue

        table_name = header_match.group(1).strip()
        cn_name = header_match.group(2).strip()

        # 检查是否有 TRAN/LOG
        has_tran = f'{table_name}_TRAN' in content
        has_log = f'{table_name}_LOG' in content

        # 提取字段表格
        columns = []
        # 找表格行（以 | 开头）
        lines = section.split('\n')
        in_field_table = False
        header_cols = []

        for line in lines:
            line = line.strip()
            if not line.startswith('|'):
                continue

            # 分割单元格
            cells = [c.strip() for c in line.split('|')]
            # 去掉首尾空元素
            cells = [c for c in cells if c != '']

            if not cells:
                continue

            # 检查是否为表头行
            if '数据元标识' in cells or '字段名' in cells:
                in_field_table = True
                header_cols = cells
                continue

            # 跳过分隔行
            if all(re.match(r'^[-:]+$', c) for c in cells):
                continue

            if not in_field_table:
                continue

            # 解析字段行
            if len(cells) >= 5:
                col = {}
                # 根据表头顺序赋值
                col['seq'] = len(columns) + 1
                col['id'] = cells[1] if len(cells) > 1 else ''
                col['name'] = cells[2] if len(cells) > 2 else ''
                col['constraint'] = cells[3] if len(cells) > 3 else ''
                col['data_type'] = cells[4] if len(cells) > 4 else ''
                col['format'] = cells[5] if len(cells) > 5 else ''
                col['comment'] = cells[6] if len(cells) > 6 else ''

                if col['id']:  # 确保有字段名
                    columns.append(col)

        if columns:
            tables[table_name] = {
                'cn_name': cn_name,
                'has_tran': has_tran,
                'has_log': has_log,
                'columns': columns
            }

    return {'tables': tables}


def is_primary_key_field(col):
    """判断字段是否是主键字段（基于文档中的说明列）"""
    comment = col.get('comment', '')
    return '复合主键' in comment


def is_pk_field_for_table(table_name, col, csv_structure, base_name_map=None):
    """
    判断字段在原表中是否是主键字段。

    对于TRAN/LOG表，回溯到原表的CSV数据来判断PK。
    如果原表不在数据库中（无CSV），则回退到文档的'复合主键'标记。
    对于普通表（原表名在文档表清单中），直接使用文档的'复合主键'标记。
    """
    if base_name_map and table_name in base_name_map:
        # TRAN/LOG表：优先用原表的CSV PK信息
        base_name = base_name_map[table_name]
        if base_name in csv_structure:
            base_cols = csv_structure[base_name]['columns']
            col_id = col['id'].upper()
            if col_id in base_cols:
                return base_cols[col_id].get('pk', 'N') == 'Y'
        # 原表不在数据库中，回退到文档主键标记
        return is_primary_key_field(col)
    else:
        # 普通表：使用文档主键标记
        return is_primary_key_field(col)



def calc_row_size(csv_cols):
    """
    计算表当前所有字段的总行大小（字节）。
    
    SQL Server 的 8060 字节限制在 ALTER TABLE 时会检查所有列的定义大小总和。
    当表中所有列定义大小超过 8060 时，ALTER COLUMN 改类型会报错：
    "更改表失败，因为添加的固定列可能引起现有数据超出允许的表行最大大小"
    
    VARCHAR(MAX) / NVARCHAR(MAX) 不计入行大小（支持行溢出到 LOB 存储）。
    
    计算规则：
    - VARCHAR(n): n 字节
    - NVARCHAR(n): n×2 字节（Unicode，SQL Server DATA_LENGTH 已是字节数）
    - CHAR(n): n 字节
    - NCHAR(n): n×2 字节
    - NUMERIC/DECIMAL: 按精度（1-9→5B，10-19→9B，20-28→13B，29-38→17B）
    - INT: 4, BIGINT: 8, SMALLINT: 2, TINYINT: 1, BIT: 1
    - DATETIME/DATETIME2: 8, DATE: 3, TIME: 5
    - FLOAT: 8, REAL: 4
    """
    total = 0
    for col_info in csv_cols.values():
        col_type = col_info.get('type', '').upper()
        length = col_info.get('length', 0)
        
        # VARCHAR(n) / NVARCHAR(n) 按定义大小计算字节数
        if col_type == 'VARCHAR':
            total += length
        elif col_type == 'NVARCHAR':
            total += length * 2  # Unicode: 2 bytes per char
        elif col_type == 'CHAR':
            total += length
        elif col_type == 'NCHAR':
            total += length * 2
        elif col_type in ('NUMERIC', 'DECIMAL'):
            precision = col_info.get('precision', 0)
            if precision <= 9:
                total += 5
            elif precision <= 19:
                total += 9
            elif precision <= 28:
                total += 13
            else:
                total += 17
        elif col_type in ('INT', 'INTEGER'):
            total += 4
        elif col_type in ('BIGINT',):
            total += 8
        elif col_type in ('SMALLINT',):
            total += 2
        elif col_type in ('TINYINT',):
            total += 1
        elif col_type in ('DATETIME', 'DATETIME2', 'SMALLDATETIME'):
            total += 8
        elif col_type in ('DATE',):
            total += 3
        elif col_type in ('TIME',):
            total += 5
        elif col_type in ('BIT',):
            total += 1
        elif col_type in ('FLOAT',):
            total += 8
        elif col_type in ('REAL',):
            total += 4
        else:
            total += length if length > 0 else 8
    
    return total


def generate_row_size_optimization(table_name, csv_cols, new_cols_info, db_type, base_name_map):
    """
    生成行大小超限优化语句。
    如果加上/修改字段后总行大小超过 8060 字节，把现有长文本字段改为 VARCHAR(MAX)。
    
    核心逻辑：
    1. 计算当前表所有字段按定义大小的总字节数（包括 VARCHAR/NVARCHAR）
    2. 加上新增/修改字段的大小
    3. 如果超过 8060，找现有的 VARCHAR/NVARCHAR 字段改为 VARCHAR(MAX) 来释放空间
    4. 按升序排序候选字段（优先改最短的，只改必要的）
    
    返回 (优化语句列表, 是否需要优化的标记)
    """
    is_sqlserver = db_type.lower() == 'sqlserver'
    if not is_sqlserver:
        return [], False
    
    ROW_SIZE_LIMIT = 8060
    
    # 计算当前行大小（所有字段类型都计入）
    current_size = calc_row_size(csv_cols)
    
    # 计算新字段会增加的大小（所有字段类型都计入，因为 ALTER TABLE 检查所有列定义大小）
    new_size = 0
    for col_id, col_info in new_cols_info.items():
        col_type = col_info.get('type', '').upper()
        length = col_info.get('length', 0)
        if col_type == 'VARCHAR':
            new_size += length
        elif col_type == 'NVARCHAR':
            new_size += length * 2
        elif col_type in ('CHAR',):
            new_size += length
        elif col_type in ('NCHAR',):
            new_size += length * 2
        elif col_type in ('NUMERIC', 'DECIMAL'):
            precision = col_info.get('precision', 0)
            if precision <= 9:
                new_size += 5
            elif precision <= 19:
                new_size += 9
            elif precision <= 28:
                new_size += 13
            else:
                new_size += 17
        elif col_type in ('INT', 'INTEGER'):
            new_size += 4
        elif col_type in ('DATETIME', 'DATETIME2'):
            new_size += 8
        else:
            new_size += length if length > 0 else 8
    
    total_size = current_size + new_size
    
    # 如果不超过限制，不需要优化
    if total_size <= ROW_SIZE_LIMIT:
        return [], False
    
    # 需要优化：找现有表中的所有 VARCHAR/NVARCHAR 字段（非主键）
    # 去掉 length > 100 的限制，因为表可能有很多短字段累计也很大
    optimization_stmts = []
    candidates = []
    
    for col_name, col_info in csv_cols.items():
        col_type = col_info.get('type', '').upper()
        length = col_info.get('length', 0)
        
        # 跳过主键字段
        if is_pk_by_csv_for_table(table_name, col_name, csv_cols, base_name_map):
            continue
        
        # 所有 VARCHAR/NVARCHAR 字段都是候选（不限制最小长度）
        if col_type in ('VARCHAR', 'NVARCHAR'):
            if col_type == 'NVARCHAR':
                freed = length * 2
            else:
                freed = length
            candidates.append((col_name, col_info, length, freed))
    
    # 按释放字节数升序排序，优先改最小的（只改必要的字段，避免过度优化）
    candidates.sort(key=lambda x: x[3])
    
    # 生成优化语句，直到估算行大小降到限制以下
    freed_bytes = 0
    needed_freed = total_size - ROW_SIZE_LIMIT
    
    for col_name, col_info, length, freed in candidates:
        if freed_bytes >= needed_freed:
            break
        
        # 改为 VARCHAR(MAX)
        nullable = col_info.get('nullable', 'Y').upper() == 'Y'
        null_str = 'NULL' if nullable else 'NOT NULL'
        t = _quote_identifier(table_name, db_type)
        c = _quote_identifier(col_name, db_type)
        
        # 生成 ALTER COLUMN 语句
        sql = (
            f"IF OBJECT_ID('{table_name}', 'U') IS NOT NULL "
            f"AND EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('{table_name}') AND name = '{col_name}')\n"
            f"    ALTER TABLE {t} ALTER COLUMN {c} VARCHAR(MAX) {null_str};"
        )
        
        comment = f"-- {table_name}.{col_name} 行大小超限，改为 VARCHAR(MAX) 不计入 8060 限制（原类型 {col_info.get('type')}({length})，释放 {freed} 字节）"
        optimization_stmts.append(f"{comment}\n{sql}")
        
        # 累加释放的字节数
        freed_bytes += freed
    
    return optimization_stmts, freed_bytes >= needed_freed

def is_pk_by_csv_for_table(table_name, col_name, csv_structure, base_name_map):
    """
    用CSV的PK_FLAG判断字段在原表中是否是主键。

    用于"多余字段"等基于CSV列名（而非文档col）的判断场景。
    对于TRAN/LOG表，回溯到原表的CSV PK来判断。
    对于普通表，直接使用自身CSV的PK。
    """
    if base_name_map and table_name in base_name_map:
        # TRAN/LOG表：用原表的CSV PK
        base_name = base_name_map[table_name]
        if base_name in csv_structure:
            base_cols = csv_structure[base_name]['columns']
            if col_name in base_cols:
                return base_cols[col_name].get('pk', 'N') == 'Y'
        return False
    else:
        # 普通表：直接用自身CSV的PK
        if table_name in csv_structure:
            cols = csv_structure[table_name]['columns']
            if col_name in cols:
                return cols[col_name].get('pk', 'N') == 'Y'
        return False


# ============================================================
# CSV解析
# ============================================================

def read_csv(csv_path, encoding='utf-8'):
    """读取CSV文件"""
    with open(csv_path, 'r', encoding=encoding) as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            clean_row = {k.strip().upper(): v.strip() if v else '' for k, v in row.items()}
            rows.append(clean_row)
    return rows


def build_csv_structure(rows):
    """从CSV构建表结构"""
    from collections import defaultdict

    tables = defaultdict(lambda: {'columns': {}})

    def safe_int(val, default=0):
        try:
            return int(val) if val else default
        except (ValueError, TypeError):
            return default

    for row in rows:
        table_name = row.get('TABLE_NAME', '').strip().upper()
        column_name = row.get('COLUMN_NAME', '').strip().upper()

        if not table_name or not column_name:
            continue

        col_info = {
            'type': row.get('DATA_TYPE', '').strip().upper(),
            'length': safe_int(row.get('CHAR_LENGTH', '0')),
            'precision': safe_int(row.get('DATA_PRECISION', '')),
            'scale': safe_int(row.get('DATA_SCALE', '')),
            'nullable': row.get('NULLABLE', 'Y').strip().upper(),
            'default': row.get('DATA_DEFAULT', '').strip(),
            'pk': row.get('PK_FLAG', 'N').strip().upper(),
        }

        tables[table_name]['columns'][column_name.upper()] = col_info

    return tables


# ============================================================
# 数据类型转换
# ============================================================

def doc_type_to_db(data_type, format_str, db_type):
    """
    将文档中的数据类型转换为数据库实际类型。

    文档DataType:
    - S1/S2/S3/S → 字符型
    - N → 数值型
    - D/DT → 日期型

    表示格式:
    - AN..n → VARCHAR(n)
    - N..n → VARCHAR(n)
    - A{n} → VARCHAR(n)
    - N{p,s} → DECIMAL(p,s)
    - D/DT + {n} → DATE/DATETIME
    """
    is_sqlserver = db_type.lower() == 'sqlserver'

    if data_type.upper() in ('S1', 'S2', 'S3', 'S'):
        # 字符型
        base_type = 'VARCHAR' if is_sqlserver else 'VARCHAR2'
        length = _parse_format_to_length(format_str)
        return base_type, length

    elif data_type.upper() == 'N':
        # 数值型
        base_type = 'NUMERIC' if is_sqlserver else 'NUMBER'
        precision, scale = _parse_format_to_precision(format_str)
        if precision is not None:
            return base_type, (precision, scale)
        return base_type, None

    elif data_type.upper() in ('D', 'DT'):
        # 日期型
        if is_sqlserver:
            return 'DATETIME', None
        else:
            return 'DATE', None

    return None, None


def _parse_format_to_length(format_str):
    """
    解析表示格式为长度（用于字符型）

    支持的格式：
    - AN..n 或 N..n → n
    - A{n} → n
    - N{n} → n
    - AN..* → None（不限制长度）
    - [NDT]+{n} 如 D10, DT19, N1, N2 → n
    """
    if not format_str:
        return None

    # AN..* → 不限制长度
    if format_str.strip() == 'AN..*':
        return None

    # AN..n 或 N..n
    m = re.match(r'(AN|N)\.\.(\d+)', format_str, re.IGNORECASE)
    if m:
        return int(m.group(2))

    # A{n}
    m = re.match(r'A\{(\d+)\}', format_str, re.IGNORECASE)
    if m:
        return int(m.group(1))

    # N{n}
    m = re.match(r'N\{(\d+)\}', format_str, re.IGNORECASE)
    if m:
        return int(m.group(1))

    # [NDT]+{n} 如 D10, DT19, N1, N2
    m = re.match(r'[NDT]+(\d+)', format_str, re.IGNORECASE)
    if m:
        return int(m.group(1))

    return None


def _parse_format_to_precision(format_str):
    """
    解析表示格式为精度和小数位（用于数值型，DataType=N）

    表示格式只标注精度信息，不改变本质类型（N 永远是数值型）。

    支持的格式：
    - N{p,s}  → (p, s)     如 N{10,2} → DECIMAL(10,2)
    - N{p}    → (p, 0)     如 N{10}   → DECIMAL(10,0)
    - N..n    → (n, 0)     如 N..3    → DECIMAL(3,0)
    """
    if not format_str:
        return None, None

    # N{p,s}
    m = re.match(r'N\{(\d+),(\d+)\}', format_str, re.IGNORECASE)
    if m:
        return int(m.group(1)), int(m.group(2))

    # N{p}
    m = re.match(r'N\{(\d+)\}', format_str, re.IGNORECASE)
    if m:
        return int(m.group(1)), 0

    # N..n 或 N..n,s（最大n位数字，可选小数位s）
    m = re.match(r'N\.\.(\d+)(?:,(\d+))?', format_str, re.IGNORECASE)
    if m:
        precision = int(m.group(1))
        scale = int(m.group(2)) if m.group(2) else 0
        return precision, scale

    return None, None


def _quote_identifier(name, db_type):
    """根据数据库类型引用标识符"""
    if db_type.lower() == 'oracle':
        return f'"{name}"'
    else:  # sqlserver
        return f'[{name}]'


def _generate_alter_sql(table_name, col_name, type_def, nullable, db_type, action='ADD', commented=False):
    """
    生成 ALTER TABLE 语句，带存在性判断。

    action: 'ADD' 或 'MODIFY'
    commented: 如果为True，整个语句都被注释（用于不安全修改）

    规则：
    - ADD: 判断表是否存在 + 字段是否不存在，两者满足才新增
    - MODIFY: 判断表是否存在 + 字段是否存在，两者满足才修改
    """
    t = _quote_identifier(table_name, db_type)
    c = _quote_identifier(col_name, db_type)
    null_str = 'NULL' if nullable else 'NOT NULL'

    if db_type.lower() == 'oracle':
        sql = f'ALTER TABLE {t} {action} ({c} {type_def} {null_str});'
        if commented:
            sql = '-- ' + sql
        return sql
    else:  # sqlserver
        if action == 'ADD':
            # SQL Server 新增字段：判断表存在 且 字段不存在
            inner_sql = f'ALTER TABLE {t} ADD {c} {type_def} {null_str};'
            if_line = (
                f"IF OBJECT_ID('{table_name}', 'U') IS NOT NULL "
                f"AND NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('{table_name}') AND name = '{col_name}')"
            )
            alter_line = f"    {inner_sql}"
            if commented:
                return f"-- {if_line}\n-- {alter_line}"
            return f"{if_line}\n{alter_line}"
        else:  # MODIFY → ALTER COLUMN
            # SQL Server 修改字段：判断表存在 且 字段存在
            inner_sql = f'ALTER TABLE {t} ALTER COLUMN {c} {type_def} {null_str};'
            if_line = (
                f"IF OBJECT_ID('{table_name}', 'U') IS NOT NULL "
                f"AND EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('{table_name}') AND name = '{col_name}')"
            )
            alter_line = f"    {inner_sql}"
            if commented:
                return f"-- {if_line}\n-- {alter_line}"
            return f"{if_line}\n{alter_line}"


def convert_default_to_sqlserver(default_val):
    """将Oracle默认值转换为SQL Server"""
    if not default_val:
        return default_val

    mapping = {
        'SYSDATE': 'GETDATE()',
        'SYSTIMESTAMP': 'SYSDATETIME()',
        'USER': 'SUSER_NAME()',
        'SYSGUID': 'NEWID()',
    }

    upper = default_val.upper().strip()
    for oracle_val, sqlserver_val in mapping.items():
        if oracle_val in upper:
            return sqlserver_val

    return default_val


# ============================================================
# 对比逻辑
# ============================================================

def compare_structures(md_structure, csv_structure, db_type):
    """
    对比MD文档标准与CSV库表结构。

    规则（来自 compare_rules.md）：
    1. 缺失字段 → 修复（ADD COLUMN，全部NULL）
    2. 多余字段 → 可空则忽略，必填无默认则标记问题
    3. 类型不一致 → 标记不安全修改
    4. 长度/精度不足 → 修复（扩大）
    """
    is_sqlserver = db_type.lower() == 'sqlserver'

    md_tables = md_structure['tables']

    unsafe_changes = []  # 需人工确认
    safe_changes = []    # 安全可执行

    # 公共字段定义（新建表时自动添加）
    common_columns = [
        {'name': 'SCZT', 'type_def': "VARCHAR(1) DEFAULT '0' NOT NULL"},
        {'name': 'SCZT_INDEX', 'type_def': "VARCHAR(1) DEFAULT '0' NOT NULL"},
        {'name': 'SCZT_GGWS', 'type_def': "VARCHAR(1) DEFAULT '0' NOT NULL"},
        {'name': 'SCZT_YLFW', 'type_def': "VARCHAR(1) DEFAULT '0' NOT NULL"},
        {'name': 'SYZT', 'type_def': "VARCHAR(1) DEFAULT '0' NOT NULL"},
    ]

    # 需要对比的表（原表 + _TRAN + _LOG）
    tables_to_check = {}
    tables_to_create_groups = []

    # 构建 TRAN/LOG 到原表的映射
    base_name_map = {}
    for table_name in md_tables.keys():
        base_name_map[f'{table_name}_TRAN'] = table_name
        base_name_map[f'{table_name}_LOG'] = table_name

    for table_name, table_info in md_tables.items():
        group = []
        if table_name in csv_structure:
            tables_to_check[table_name] = table_info['columns']
        else:
            group.append({
                'table_name': table_name,
                'columns': table_info['columns'],
                'cn_name': table_info['cn_name'],
                'suffix': ''
            })

        # TRAN表
        tran_name = f'{table_name}_TRAN'
        if tran_name in csv_structure:
            tables_to_check[tran_name] = table_info['columns']
        else:
            group.append({
                'table_name': tran_name,
                'columns': table_info['columns'],
                'cn_name': table_info['cn_name'],
                'suffix': '_TRAN'
            })

        # LOG表
        log_name = f'{table_name}_LOG'
        if log_name in csv_structure:
            tables_to_check[log_name] = table_info['columns']
        else:
            group.append({
                'table_name': log_name,
                'columns': table_info['columns'],
                'cn_name': table_info['cn_name'],
                'suffix': '_LOG'
            })

        if group:
            tables_to_create_groups.append(group)

    # ====== 生成建表语句（按组输出） ======
    def generate_create_table(tc):
        """生成单个表的CREATE语句"""
        tname = tc['table_name']
        suffix = tc['suffix']
        t = _quote_identifier(tname, db_type)

        col_defs = []
        for col in tc['columns']:
            col_id = col['id'].upper()
            db_type_str, type_param = doc_type_to_db(
                col['data_type'], col['format'], db_type
            )
            if not db_type_str:
                continue

            if type_param is None:
                full_type = db_type_str
            elif isinstance(type_param, tuple):
                p, s = type_param
                if s > 0:
                    full_type = f"{db_type_str}({p},{s})"
                else:
                    full_type = f"{db_type_str}({p})"
            else:
                full_type = f"{db_type_str}({type_param})"

            c = _quote_identifier(col_id, db_type)
            constraint = col.get('constraint', '').upper()
            null_str = 'NOT NULL' if constraint == 'M' else 'NULL'
            col_defs.append(f"    {c} {full_type} {null_str}")

        # 添加公共字段
        for cc in common_columns:
            c = _quote_identifier(cc['name'], db_type)
            col_defs.append(f"    {c} {cc['type_def']}")

        # 原表需要加主键约束，TRAN和LOG表不加
        is_base_table = (suffix == '')
        if is_base_table:
            pk_cols = []
            for col in tc['columns']:
                if is_primary_key_field(col):
                    pk_cols.append(
                        _quote_identifier(col['id'].upper(), db_type)
                    )

            if pk_cols:
                pk_cols_str = ", ".join(pk_cols)
                constraint_name = (
                    _quote_identifier(f"PK_{tname}", db_type)
                    if db_type.lower() == 'oracle'
                    else f"PK_{tname}"
                )
                col_defs.append(
                    f"    CONSTRAINT {constraint_name} PRIMARY KEY ({pk_cols_str})"
                )

        col_defs_str = ",\n".join(col_defs)
        create_sql = f"CREATE TABLE {t} (\n{col_defs_str}\n);"

        if is_sqlserver:
            return (
                f"IF OBJECT_ID('{tname}', 'U') IS NULL\n"
                f"BEGIN\n{create_sql}\nEND;"
            )
        else:
            return (
                f"BEGIN\n"
                f"    EXECUTE IMMEDIATE '{create_sql}';\n"
                f"EXCEPTION\n"
                f"    WHEN OTHERS THEN\n"
                f"        IF SQLCODE != -955 THEN\n"
                f"            RAISE;\n"
                f"        END IF;\n"
                f"END;\n/"
            )

    for group in tables_to_create_groups:
        cn_name = group[0]['cn_name']
        group_parts = []

        for tc in group:
            suffix = tc['suffix']
            suffix_label = f"({suffix})" if suffix else ""
            tname = tc['table_name']
            create_sql = generate_create_table(tc)
            comment = f"-- 新建表: {tname}{suffix_label}（{cn_name}），文档有定义但库中不存在"
            group_parts.append(f"{comment}\n{create_sql}")

        safe_changes.append("\n\n".join(group_parts))

    # ====== 对比已有表 ======
    row_size_optimizations = []

    for table_name, expected_columns in tables_to_check.items():
        if table_name not in csv_structure:
            continue

        csv_cols = csv_structure[table_name]['columns']

        # 1. 检查缺失字段（文档有，库没有）
        for col in expected_columns:
            col_id = col['id'].upper()
            if col_id not in csv_cols:
                db_type_str, type_param = doc_type_to_db(
                    col['data_type'], col['format'], db_type
                )
                if not db_type_str:
                    continue

                if type_param is None:
                    full_type = db_type_str
                elif isinstance(type_param, tuple):
                    p, s = type_param
                    if s > 0:
                        full_type = f"{db_type_str}({p},{s})"
                    else:
                        full_type = f"{db_type_str}({p})"
                else:
                    full_type = f"{db_type_str}({type_param})"

                sql = _generate_alter_sql(table_name, col_id, full_type, True, db_type, 'ADD')

                if is_pk_field_for_table(table_name, col, csv_structure, base_name_map):
                    comment = f"-- 主键字段新增，需人工确认"
                    unsafe_changes.append(f"{comment}\n" + "\n".join(f"-- {line}" for line in sql.split('\n')))
                else:
                    comment = f"-- 文档要求新增字段 {col_id}（{col['name']}）"
                    safe_changes.append(f"{comment}\n{sql}")

        # 2. 检查多余字段（库有，文档没有）
        doc_col_ids = {col['id'].upper() for col in expected_columns}
        for csv_col_name, csv_col_info in csv_cols.items():
            if csv_col_name not in doc_col_ids:
                nullable = csv_col_info['nullable']
                default = csv_col_info.get('default', '')

                if is_pk_by_csv_for_table(table_name, csv_col_name, csv_structure, base_name_map):
                    continue

                if nullable == 'Y':
                    pass
                elif default:
                    pass
                else:
                    actual_type = csv_col_info['type']
                    length = csv_col_info.get('length', 0)
                    if length > 0:
                        actual_full = f"{actual_type}({length})"
                    else:
                        actual_full = actual_type

                    comment = f"-- 多余字段 {csv_col_name}，改为可空"
                    sql = _generate_alter_sql(table_name, csv_col_name, actual_full, True, db_type, 'MODIFY')
                    safe_changes.append(f"{comment}\n{sql}")

        # 3. 检查共有字段的类型和长度
        for col in expected_columns:
            col_id = col['id'].upper()
            if col_id not in csv_cols:
                continue

            csv_col = csv_cols[col_id]
            expected_type, type_param = doc_type_to_db(
                col['data_type'], col['format'], db_type
            )
            if not expected_type:
                continue

            csv_type = csv_col['type'].upper()

            # 检查类型大类是否匹配
            type_match = False
            char_types = ('VARCHAR', 'VARCHAR2', 'CHAR', 'NVARCHAR', 'NCHAR')
            num_types = ('NUMBER', 'NUMERIC', 'INT', 'BIGINT', 'SMALLINT', 'DECIMAL')
            date_types = ('DATE', 'DATETIME', 'DATETIME2', 'SMALLDATETIME')

            if expected_type in char_types:
                if csv_type in char_types:
                    type_match = True
            elif expected_type in num_types:
                if csv_type in num_types:
                    type_match = True
            elif expected_type in date_types:
                if csv_type in date_types:
                    type_match = True

            if not type_match:
                if type_param is None:
                    expected_full = expected_type
                elif isinstance(type_param, tuple):
                    p, s = type_param
                    if s > 0:
                        expected_full = f"{expected_type}({p},{s})"
                    else:
                        expected_full = f"{expected_type}({p})"
                else:
                    expected_full = f"{expected_type}({type_param})"

                csv_len = csv_col.get('length', 0)
                if csv_len > 0:
                    actual_full = f"{csv_type}({csv_len})"
                else:
                    actual_full = csv_type

                comment = f"-- {table_name}.{col_id} 类型不一致（文档={expected_full}，库={actual_full}）"
                sql = _generate_alter_sql(table_name, col_id, expected_full, True, db_type, 'MODIFY')
                unsafe_changes.append(f"{comment}\n" + "\n".join(f"-- {line}" for line in sql.split('\n')))
                continue

            # 类型匹配，检查长度/精度
            if expected_type in char_types:
                if type_param is not None:
                    try:
                        expected_len = int(type_param)
                    except (ValueError, TypeError):
                        continue

                    csv_len = csv_col.get('length', 0)
                    if csv_len > 0 and csv_len < expected_len:
                        is_nullable = csv_col.get('nullable', 'Y').upper() == 'Y'
                        sql = _generate_alter_sql(
                            table_name, col_id,
                            f"{expected_type}({expected_len})",
                            is_nullable, db_type, 'MODIFY'
                        )

                        if is_pk_field_for_table(table_name, col, csv_structure, base_name_map):
                            comment = f"-- 主键字段 {table_name}.{col_id} 长度不足，需人工确认"
                            unsafe_changes.append(f"{comment}\n" + "\n".join(f"-- {line}" for line in sql.split('\n')))
                        else:
                            comment = f"-- {table_name}.{col_id} 长度从 {csv_len} 扩大到 {expected_len}"
                            safe_changes.append(f"{comment}\n{sql}")

            elif expected_type in num_types:
                if type_param is not None and isinstance(type_param, tuple):
                    expected_p, expected_s = type_param
                    csv_p = csv_col.get('precision', 0)
                    csv_s = csv_col.get('scale', 0)

                    if expected_p > 0 and (csv_p < expected_p or csv_s < expected_s):
                        is_nullable = csv_col.get('nullable', 'Y').upper() == 'Y'
                        sql = _generate_alter_sql(
                            table_name, col_id,
                            f"{expected_type}({expected_p},{expected_s})",
                            is_nullable, db_type, 'MODIFY'
                        )

                        if is_pk_field_for_table(table_name, col, csv_structure, base_name_map):
                            comment = f"-- 主键字段 {table_name}.{col_id} 精度不足，需人工确认"
                            unsafe_changes.append(f"{comment}\n" + "\n".join(f"-- {line}" for line in sql.split('\n')))
                        else:
                            comment = f"-- {table_name}.{col_id} 精度从 ({csv_p},{csv_s}) 扩大到 ({expected_p},{expected_s})"
                            safe_changes.append(f"{comment}\n{sql}")

            # 检查可空性
            doc_constraint = col.get('constraint', '').upper()
            db_nullable = csv_col.get('nullable', 'Y').upper()
            if doc_constraint in ('O', 'C') and db_nullable == 'N':
                cur_type = csv_col.get('type', '')
                cur_length = csv_col.get('length', 0)
                cur_precision = csv_col.get('precision', 0)
                cur_scale = csv_col.get('scale', 0)

                if cur_type in char_types:
                    cur_type_def = f"{cur_type}({cur_length})" if cur_length > 0 else cur_type
                elif cur_type in num_types:
                    if cur_precision > 0:
                        cur_type_def = f"{cur_type}({cur_precision},{cur_scale})" if cur_scale > 0 else f"{cur_type}({cur_precision})"
                    else:
                        cur_type_def = cur_type
                else:
                    cur_type_def = cur_type

                comment = f"-- {table_name}.{col_id} 文档约束={doc_constraint}，数据库为NOT NULL，改为可空"
                sql = _generate_alter_sql(table_name, col_id, cur_type_def, True, db_type, 'MODIFY')

                if is_pk_field_for_table(table_name, col, csv_structure, base_name_map):
                    comment = f"-- 主键字段 {table_name}.{col_id} 可空性冲突，需人工确认"
                    unsafe_changes.append(f"{comment}\n" + "\n".join(f"-- {line}" for line in sql.split('\n')))
                else:
                    safe_changes.append(f"{comment}\n{sql}")

        # 4. 检查主键约束是否一致（TRAN和LOG表跳过）
        if table_name in base_name_map:
            continue

        doc_pk_cols = []
        for col in expected_columns:
            col_id = col['id'].upper()
            if is_primary_key_field(col):
                doc_pk_cols.append(col_id)

        csv_pk_cols = []
        for col_name, col_info in csv_cols.items():
            if col_info.get('pk', 'N') == 'Y':
                csv_pk_cols.append(col_name)

        if set(doc_pk_cols) != set(csv_pk_cols):
            comment = f"-- {table_name} 主键不一致（文档={doc_pk_cols}，库={csv_pk_cols}），需人工确认"
            unsafe_changes.append(comment)

    return {
        'safe_changes': safe_changes,
        'unsafe_changes': unsafe_changes,
        'row_size_optimizations': row_size_optimizations
    }


# ============================================================
# 主入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description='对比 table_structure.md 与 CSV 库表结构，生成修复脚本'
    )
    parser.add_argument('--md', required=True, help='table_structure.md 文件路径')
    parser.add_argument('--csv', required=True, help='基准库导出的 CSV 文件路径')
    parser.add_argument('--db-type', required=True, choices=['oracle', 'sqlserver'], help='目标数据库类型')
    parser.add_argument('--task-dir', required=True, help='任务目录路径')
    parser.add_argument('--output', default=None, help='输出文件路径（可选）')
    parser.add_argument('--encoding', default='utf-8', help='CSV文件编码，默认 utf-8')

    args = parser.parse_args()

    md_path = Path(args.md)
    csv_path = Path(args.csv)
    task_dir = Path(args.task_dir)
    db_type = args.db_type

    if not md_path.exists():
        print(f"错误: MD文件不存在: {md_path}")
        sys.exit(1)
    if not csv_path.exists():
        print(f"错误: CSV文件不存在: {csv_path}")
        sys.exit(1)

    print(f"解析MD文件: {md_path}")
    md_structure = parse_md_file(str(md_path))
    print(f"  发现 {len(md_structure['tables'])} 张表定义")

    print(f"读取CSV文件: {csv_path}")
    rows = read_csv(str(csv_path), args.encoding)
    csv_structure = build_csv_structure(rows)
    print(f"  发现 {len(csv_structure)} 张数据库表")

    print(f"开始对比... (目标数据库: {db_type})")
    result = compare_structures(md_structure, csv_structure, db_type)

    safe = result['safe_changes']
    unsafe = result['unsafe_changes']
    row_opt = result['row_size_optimizations']

    print(f"安全修改: {len(safe)} 项")
    print(f"需人工确认: {len(unsafe)} 项")
    if row_opt:
        print(f"行大小优化: {len(row_opt)} 项")

    # 组装输出
    from datetime import datetime
    output_parts = []

    output_parts.append(
        "-- ========================================\n"
        "-- 数据库修复脚本\n"
        f"-- 目标: {db_type.upper()}\n"
        f"-- 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        "-- ========================================\n"
    )

    if row_opt:
        output_parts.append(
            "-- ========================================\n"
            "-- 行大小超限优化（请在加新字段前执行）\n"
            "-- ========================================\n\n"
        )
        output_parts.extend(row_opt)
        output_parts.append("\n")

    if safe:
        output_parts.append(
            "-- ========================================\n"
            "-- 安全修改（可自动执行）\n"
            "-- ========================================\n\n"
        )
        output_parts.extend(safe)
        output_parts.append("\n")

    if unsafe:
        output_parts.append(
            "-- ========================================\n"
            "-- 需人工确认的修改\n"
            "-- ========================================\n\n"
        )
        output_parts.extend(unsafe)
        output_parts.append("\n")

    output_content = "\n".join(output_parts)

    # 写入文件
    if args.output:
        output_path = Path(args.output)
    else:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = task_dir / f"fix_{db_type}_{timestamp}.sql"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(output_content, encoding='utf-8')
    print(f"\n修复脚本已生成: {output_path}")


if __name__ == '__main__':
    main()
