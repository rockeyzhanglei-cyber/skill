#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
table_structure.md 与 CSV 库表结构对比脚本

用途：对比基准库CSV与Word文档解析出的MD标准，生成修复脚本

使用方式：
    python compare_with_docx.py --md <md_path> --csv <csv_path> --db-type <oracle|sqlserver> --task-dir <dir> [--output <path>] [--encoding <enc>] [--tran-log-mode field_compare|rebuild]

输入：
    --md: table_structure.md 文件路径（从Word文档解析生成）
    --csv: 基准库导出的CSV文件路径
    --db-type: 目标数据库类型（oracle | sqlserver）
    --task-dir: 任务目录路径
    --tran-log-mode: TRAN/LOG表处理方式（默认 field_compare）
        field_compare - 文档结构分别与原表/TRAN表/LOG表三表逐字段核对（默认，兼容旧行为）
        rebuild      - 只核对原表与文档差异；TRAN/LOG表不做逐字段比对，
                       直接生成"按原表（文档）结构重建"语句（DROP + CREATE，无主键、不加公共字段），
                       重建语句默认注释状态，需人工确认

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

# 模块级：当前脚本对应的 schema owner（从 CSV 首行 OWNER 列提取）
_script_owner = None


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

def read_csv(csv_path, encoding='utf-8', delimiter=','):
    """读取CSV文件"""
    with open(csv_path, 'r', encoding=encoding) as f:
        reader = csv.DictReader(f, delimiter=delimiter)
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

        raw_default = row.get('DATA_DEFAULT', '').strip()
        # CSV 中 'NULL' 字符串表示无默认值，统一转空
        if raw_default.upper() == 'NULL':
            raw_default = ''

        col_info = {
            'type': row.get('DATA_TYPE', '').strip().upper(),
            'length': safe_int(row.get('CHAR_LENGTH', '0')),
            'precision': safe_int(row.get('DATA_PRECISION', '')),
            'scale': safe_int(row.get('DATA_SCALE', '')),
            'nullable': row.get('NULLABLE', 'Y').strip().upper(),
            'default': raw_default,
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
        # AN..* → CLOB (Oracle) / VARCHAR(MAX) (SQL Server)
        if format_str and format_str.strip() == 'AN..*':
            if is_sqlserver:
                return 'VARCHAR', 'MAX'
            else:
                return 'CLOB', None
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

    # [A-Z]\d+$ 如 A1, KSLB格式A1 → VARCHAR2(1)
    m = re.match(r'[A-Z](\d+)$', format_str, re.IGNORECASE)
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

    # AN..n（DataType=N 时，表示最多n位数字）
    m = re.match(r'AN\.\.(\d+)$', format_str, re.IGNORECASE)
    if m:
        return int(m.group(1)), 0

    # N{n,s} 如 N3,1（无大括号写法，= NUMBER(3,1)）
    m = re.match(r'N(\d+),(\d+)$', format_str, re.IGNORECASE)
    if m:
        return int(m.group(1)), int(m.group(2))

    # N{n} 如 N3（无大括号写法，= NUMBER(3)）
    m = re.match(r'N(\d+)$', format_str, re.IGNORECASE)
    if m:
        return int(m.group(1)), 0

    return None, None


def _table_ref(table_name, db_type):
    """带 owner 前缀的表引用；owner 从模块级 _script_owner 获取"""
    global _script_owner
    if db_type.lower() == 'oracle' and _script_owner:
        return f'"{_script_owner}"."{table_name}"'
    return _quote_identifier(table_name, db_type)


def _quote_identifier(name, db_type):
    """根据数据库类型引用标识符"""
    if db_type.lower() == 'oracle':
        return f'"{name}"'
    else:  # sqlserver
        return f'[{name}]'


def _generate_alter_sql(table_name, col_name, type_def, nullable, db_type, action='ADD', commented=False, nullability_only=False):
    """
    生成 ALTER TABLE 语句，带存在性判断。

    action: 'ADD' 或 'MODIFY'
    commented: 如果为True，整个语句都被注释（用于不安全修改）
    nullability_only: MODIFY 时仅改可空性，不写类型（Oracle: MODIFY (c NULL)）

    规则：
    - ADD: 判断表是否存在 + 字段是否不存在，两者满足才新增
    - MODIFY: 判断表是否存在 + 字段是否存在，两者满足才修改
      - nullability_only=True 时只写 NULL/NOT NULL，省略类型定义
    """
    t = _table_ref(table_name, db_type)
    c = _quote_identifier(col_name, db_type)
    null_str = 'NULL' if nullable else 'NOT NULL'

    if db_type.lower() == 'oracle':
        if action == 'ADD':
            sql = (
                f"DECLARE\n"
                f"    v_count NUMBER;\n"
                f"BEGIN\n"
                f"    SELECT COUNT(*) INTO v_count FROM user_tables WHERE table_name = '{table_name}';\n"
                f"    IF v_count > 0 THEN\n"
                f"        SELECT COUNT(*) INTO v_count FROM user_tab_columns WHERE table_name = '{table_name}' AND column_name = '{col_name}';\n"
                f"        IF v_count = 0 THEN\n"
                f"            EXECUTE IMMEDIATE 'ALTER TABLE {t} ADD ({c} {type_def} {null_str})';\n"
                f"        END IF;\n"
                f"    END IF;\n"
                f"END;\n/"
            )
        else:  # MODIFY
            if nullability_only:
                modify_clause = f"{c} {null_str}"
            else:
                # 仅改类型/长度/精度时不写 NULL/NOT NULL，保留 DB 现有可空性
                modify_clause = f"{c} {type_def}"
            sql = (
                f"DECLARE\n"
                f"    v_count NUMBER;\n"
                f"BEGIN\n"
                f"    SELECT COUNT(*) INTO v_count FROM user_tables WHERE table_name = '{table_name}';\n"
                f"    IF v_count > 0 THEN\n"
                f"        SELECT COUNT(*) INTO v_count FROM user_tab_columns WHERE table_name = '{table_name}' AND column_name = '{col_name}';\n"
                f"        IF v_count > 0 THEN\n"
                f"            EXECUTE IMMEDIATE 'ALTER TABLE {t} MODIFY ({modify_clause})';\n"
                f"        END IF;\n"
                f"    END IF;\n"
                f"END;\n/"
            )
        if commented:
            sql = '\n'.join(f'-- {line}' if line.strip() else '--' for line in sql.split('\n'))
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
            if nullability_only:
                inner_sql = f'ALTER TABLE {t} ALTER COLUMN {c} {type_def} {null_str};'
            else:
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

def compare_structures(md_structure, csv_structure, db_type, tran_log_mode='field_compare'):
    """
    对比MD文档标准与CSV库表结构。

    规则（来自 compare_rules.md）：
    1. 缺失字段 → 修复（ADD COLUMN，全部NULL）
    2. 多余字段 → 可空则忽略，必填无默认则标记问题
    3. 类型不一致 → 标记不安全修改
    4. 长度/精度不足 → 修复（扩大）

    tran_log_mode:
        field_compare - 三表（原表/TRAN/LOG）各自独立逐字段核对（默认）
        rebuild      - 只核对原表；TRAN/LOG表直接按原表（文档）结构重建（DROP + CREATE，无主键、无公共字段）
    """
    is_sqlserver = db_type.lower() == 'sqlserver'
    rebuild_mode = (tran_log_mode == 'rebuild')

    md_tables = md_structure['tables']

    unsafe_changes = []  # 需人工确认
    safe_changes = []    # 安全可执行
    rebuild_statements = []  # TRAN/LOG重建语句（rebuild模式）

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

    # rebuild模式下需要重建的 TRAN/LOG 表（原表名 -> 文档字段列表）
    tables_to_rebuild = []

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
        if rebuild_mode:
            # 重建模式：TRAN表不逐字段比对，直接进入重建清单
            # base_table_name 用于在 generate_rebuild_sql 中读取原表 CSV 结构
            tables_to_rebuild.append({
                'table_name': tran_name,
                'base_table_name': table_name,
                'columns': table_info['columns'],
                'cn_name': table_info['cn_name'],
                'suffix': '_TRAN'
            })
        elif tran_name in csv_structure:
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
        if rebuild_mode:
            # 重建模式：LOG表不逐字段比对，直接进入重建清单
            tables_to_rebuild.append({
                'table_name': log_name,
                'base_table_name': table_name,
                'columns': table_info['columns'],
                'cn_name': table_info['cn_name'],
                'suffix': '_LOG'
            })
        elif log_name in csv_structure:
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
    def build_column_defs(tc, include_common=True, include_pk=True):
        """
        构建表的字段定义列表（不含最终拼接）。
        include_common: 是否追加公共字段（SCZT/SYZT等）
        include_pk: 是否追加主键约束（原表加，TRAN/LOG不加）
        """
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
                full_type = f"{db_type_str}({p},{s})"
            else:
                full_type = f"{db_type_str}({type_param})"

            c = _quote_identifier(col_id, db_type)
            constraint = col.get('constraint', '').upper()
            null_str = 'NOT NULL' if constraint == 'M' else 'NULL'
            col_defs.append(f"    {c} {full_type} {null_str}")

        # 添加公共字段
        if include_common:
            for cc in common_columns:
                c = _quote_identifier(cc['name'], db_type)
                col_defs.append(f"    {c} {cc['type_def']}")

        # 原表需要加主键约束，TRAN和LOG表不加
        if include_pk:
            suffix = tc.get('suffix', '')
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
                    pk_tname = tc['table_name']
                    constraint_name = (
                        _quote_identifier(f"PK_{pk_tname}", db_type)
                        if db_type.lower() == 'oracle'
                        else f"PK_{pk_tname}"
                    )
                    col_defs.append(
                        f"    CONSTRAINT {constraint_name} PRIMARY KEY ({pk_cols_str})"
                    )

        return col_defs

    def generate_create_table(tc, include_common=True, include_pk=True):
        """生成单个表的CREATE语句"""
        tname = tc['table_name']
        t = _table_ref(tname, db_type)

        col_defs = build_column_defs(tc, include_common=include_common, include_pk=include_pk)

        col_defs_str = ",\n".join(col_defs)

        if is_sqlserver:
            create_sql = f"CREATE TABLE {t} (\n{col_defs_str}\n);"
            return (
                f"IF OBJECT_ID('{tname}', 'U') IS NULL\n"
                f"BEGIN\n{create_sql}\nEND;"
            )
        else:
            # Oracle EXECUTE IMMEDIATE 内 DDL 末尾不可带分号，否则 ORA-00911
            create_sql = f"CREATE TABLE {t} (\n{col_defs_str}\n)"
            create_sql_escaped = create_sql.replace("'", "''")
            return (
                f"BEGIN\n"
                f"    EXECUTE IMMEDIATE '{create_sql_escaped}';\n"
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

    # ====== 生成TRAN/LOG重建语句（rebuild模式） ======
    def _build_default_str(raw_default, full_type):
        """根据原始默认值字符串和列类型构建DEFAULT子句，处理引号转义"""
        if not raw_default:
            return None
        dv = raw_default.strip()
        if not dv:
            return None
        # NULL 值无实际默认意义，跳过 DEFAULT 子句
        if dv.upper() == 'NULL':
            return None

        # 已知 SQL 函数/关键字（不区分大小写，不引用号）
        sql_keywords = {'SYSDATE', 'SYSTIMESTAMP', 'CURRENT_TIMESTAMP', 'USER',
                        'GETDATE', 'GETUTCDATE', 'CURRENT_DATE', 'CURRENT_USER',
                        'SESSION_USER', 'SYSTEM_USER', 'HOST_NAME',
                        'NEWID', 'NEWSEQUENTIALID',
                        'NEXT VALUE FOR'}

        if dv.upper() in sql_keywords:
            return dv.upper()

        # 检测是否包含已知函数名（如 getdate() 被外层括号包裹情况例外）
        # 先去外层引号
        if dv.startswith("'") and dv.endswith("'"):
            dv = dv[1:-1]
            # 去引号后重新检查已知关键字
            if dv.upper() in sql_keywords:
                return dv.upper()

        # 检测是否为数值型列
        is_numeric_type = any(t in full_type.upper() for t in ('NUMBER', 'NUMERIC', 'INT', 'BIGINT', 'SMALLINT', 'DECIMAL', 'FLOAT', 'REAL', 'MONEY', 'SMALLMONEY', 'TINYINT'))

        # 纯数值：不加引号（仅数值列）
        if dv.replace('.', '').replace('-', '').isdigit() and is_numeric_type:
            return dv

        # 无括号的函数调用（如 getdate() → 返回原值不加引号）
        func_match = re.match(r'^(\w+)\s*\(.*\)$', dv)
        if func_match and func_match.group(1).upper() in sql_keywords:
            return dv

        # 带括号表达式
        if dv.startswith('(') and dv.endswith(')'):
            inner = dv[1:-1].strip()

            # 检测括号内是否为 SQL 函数调用（如 getdate() / newid() 返回完整括号表达式）
            if re.match(r'^\w+\s*\(\)$', inner, re.IGNORECASE):
                return dv

            # 括号内是已知 SQL 关键字（如 (sysdate) / (getdate)）
            if inner.upper() in sql_keywords:
                return dv

            # 括号内是引号包裹的字符串（如 ('0') → 就是 '0'）
            # CSV 转换时引号值可能被包进括号，这是引号转义产物，括号应剥离
            if inner.startswith("'") and inner.endswith("'"):
                return inner

            # 递归剥离外层括号取核心值，判断是否为纯数值表达式
            temp = dv
            while temp.startswith('(') and temp.endswith(')'):
                temp = temp[1:-1]
            if temp.replace('.', '').replace('-', '').isdigit() and is_numeric_type:
                return dv

            # 非数值非函数括号表达式 → 字符串，加引号+转义
            dv_escaped = dv.replace("'", "''")
            return f"'{dv_escaped}'"

        # 非括号非数值 → 字符串，加引号+转义
        dv_escaped = dv.replace("'", "''")
        return f"'{dv_escaped}'"

    def _build_full_type(data_type, fmt, csv_col_info=None, db_type='oracle'):
        """文档类型+格式 → 完整数据库类型字符串；csv_col_info 作为兜底精度"""
        db_type_str, type_param = doc_type_to_db(data_type, fmt, db_type)
        if not db_type_str:
            return None
        if type_param is None:
            return db_type_str
        elif isinstance(type_param, tuple):
            p, s = type_param
            return f"{db_type_str}({p},{s})"
        # type_param 是 int (如 VARCHAR2 长度)
        return f"{db_type_str}({type_param})"

    def _build_full_type_csv(csv_col_info):
        """从 CSV 列信息构建完整类型字符串（兜底用）"""
        csv_type = csv_col_info.get('type', 'VARCHAR2')
        csv_len = csv_col_info.get('length', 0)
        csv_prec = csv_col_info.get('precision', 0)
        csv_scale = csv_col_info.get('scale', 0)
        t = csv_type.upper()
        if t in ('NUMBER', 'NUMERIC', 'DECIMAL'):
            if csv_scale > 0:
                return f"{t}({csv_prec},{csv_scale})"
            elif csv_prec > 0:
                return f"{t}({csv_prec},{csv_scale})"
            else:
                return f"{t}(18,0)"  # 无精度时使用默认精度，避免生成裸 NUMERIC
        elif t in ('VARCHAR', 'VARCHAR2', 'NVARCHAR', 'CHAR', 'NCHAR'):
            # CSV 中 length=-1 表示 SQL Server 的 MAX 类型（varchar(max)）
            if csv_len == -1:
                if is_sqlserver:
                    return f"{t}(MAX)"
                else:
                    # Oracle 下对应大对象类型
                    return 'CLOB' if t == 'VARCHAR' else 'NCLOB'
            elif csv_len > 0:
                return f"{t}({csv_len})"
            else:
                return t
        elif csv_len > 0:
            return f"{t}({csv_len})"
        else:
            return t

    def _merge_type_wider(csv_info, doc_col):
        """
        合并CSV类型和文档类型，取较宽者。
        字符类型比较长度；数值类型比较精度/标度。
        返回修改后的 csv_info（原地修改）。
        """
        csv_type = csv_info.get('type', '').upper()
        doc_db_type, doc_type_param = doc_type_to_db(
            doc_col['data_type'], doc_col['format'], db_type
        )
        if not doc_db_type:
            return csv_info

        char_types = ('VARCHAR', 'VARCHAR2', 'CHAR', 'NVARCHAR', 'NCHAR')
        num_types = ('NUMBER', 'NUMERIC', 'INT', 'BIGINT', 'SMALLINT', 'DECIMAL')

        if doc_db_type in char_types and csv_type in char_types:
            if isinstance(doc_type_param, int):
                csv_len = csv_info.get('length', 0)
                # CSV 为 -1（MAX/CLOB）时保持 MAX，不允许被文档长度缩小
                if csv_len == -1:
                    return csv_info
                if doc_type_param > csv_len:
                    csv_info['length'] = doc_type_param
            return csv_info

        if doc_db_type in num_types and csv_type in num_types:
            if isinstance(doc_type_param, tuple):
                doc_p, doc_s = doc_type_param
                csv_p = csv_info.get('precision', 0)
                csv_s = csv_info.get('scale', 0)
                if doc_p > csv_p or doc_s > csv_s:
                    csv_int = csv_p - csv_s
                    doc_int = doc_p - doc_s
                    if doc_int >= csv_int:
                        csv_info['precision'] = doc_p
                        csv_info['scale'] = doc_s
            return csv_info

        return csv_info

    def _derive_final_base_columns(base_table):
        """
        推导原表最终结构：CSV列 + 原表实际会执行的修改。

        安全修改（原表实际执行）包括：
        - 文档约束为 O/C 但 CSV 中为 NOT NULL → 改为 NULL（主键字段除外，主键可空性冲突需人工确认）
        - CSV 有、文档无的必填无默认值列 → 改为 NULL
        - 类型取 CSV 与文档中较宽者（主键字段长度/精度不足、整数位缩小等"需人工确认"场景除外）
        - 文档有、CSV 无的新增列（文档标记为主键的新增列除外，需人工确认）

        关键约束：主流程中"需人工确认"的修改会被注释、原表不执行，
        TRAN/LOG 重建必须同步这一事实——即 unsafe 修改不体现在重建结构中。

        返回: (final_csv_cols, new_docx_cols)
        - final_csv_cols: {col_name_upper: {csv字段值, _name=原始列名}}
        - new_docx_cols: [(col_id_upper, doc_col), ...] 纯文档新增列
        """
        final_csv_cols = {}
        new_docx_cols = []

        if not base_table or base_table not in csv_structure:
            return final_csv_cols, new_docx_cols

        csv_cols = csv_structure[base_table]['columns']
        doc_table = md_structure['tables'].get(base_table, {})
        doc_cols = {col['id'].upper(): col for col in doc_table.get('columns', [])}

        # 与主流程一致的类型家族
        char_types = ('VARCHAR', 'VARCHAR2', 'CHAR', 'NVARCHAR', 'NCHAR', 'CLOB', 'NCLOB')
        num_types = ('NUMBER', 'NUMERIC', 'INT', 'BIGINT', 'SMALLINT', 'DECIMAL')
        date_types = ('DATE', 'DATETIME', 'DATETIME2', 'SMALLDATETIME')

        for col_name, csv_info in csv_cols.items():
            col_upper = col_name.upper()
            final_info = dict(csv_info)
            final_info['_name'] = col_name  # 保留原始列名以便 _quote_identifier

            if col_upper in doc_cols:
                doc_col = doc_cols[col_upper]
                doc_constraint = doc_col.get('constraint', '').upper()
                # 用 CSV 的 PK_FLAG 判断原表列是否主键（数据库真实主键）
                is_pk = is_pk_by_csv_for_table(base_table, col_upper, csv_structure, base_name_map)

                # 先判断类型大类是否匹配；不匹配属于"需人工确认"，保留 CSV 原类型
                doc_db_type, doc_type_param = doc_type_to_db(
                    doc_col['data_type'], doc_col['format'], db_type
                )
                csv_type = csv_info.get('type', '').upper()
                type_mismatch = False
                if doc_db_type:
                    if doc_db_type in char_types:
                        type_mismatch = csv_type not in char_types
                    elif doc_db_type in num_types:
                        type_mismatch = csv_type not in num_types
                    elif doc_db_type in date_types:
                        type_mismatch = csv_type not in date_types
                    else:
                        type_mismatch = csv_type != doc_db_type
                else:
                    # 文档类型无法映射到目标库，原表不会执行该修改
                    type_mismatch = True

                if not type_mismatch:
                    # 字符长度扩大：主键字段长度不足 → 需人工确认，不应用
                    if (doc_db_type in char_types and csv_type in char_types
                            and isinstance(doc_type_param, int)):
                        csv_len = csv_info.get('length', 0)
                        if csv_len > 0 and csv_len < doc_type_param and is_pk:
                            pass  # 主键长度不足，原表注释，保留 CSV 原样
                        else:
                            final_info = _merge_type_wider(final_info, doc_col)
                    # 数值精度扩大：主键精度不足或整数位缩小 → 需人工确认，不应用
                    elif (doc_db_type in num_types and csv_type in num_types
                          and isinstance(doc_type_param, tuple)):
                        doc_p, doc_s = doc_type_param
                        csv_p = csv_info.get('precision', 0)
                        csv_s = csv_info.get('scale', 0)
                        if doc_p > 0 and (csv_p < doc_p or csv_s < doc_s):
                            csv_int = csv_p - csv_s
                            exp_int = doc_p - doc_s
                            integer_shrinking = csv_int > exp_int
                            if is_pk or integer_shrinking:
                                pass  # 原表注释，保留 CSV 原样
                            else:
                                final_info = _merge_type_wider(final_info, doc_col)
                        else:
                            final_info = _merge_type_wider(final_info, doc_col)
                    else:
                        final_info = _merge_type_wider(final_info, doc_col)

                # 可空性：文档 O/C 但 CSV NOT NULL → 主键冲突需人工确认，保留原样
                if doc_constraint in ('O', 'C') and csv_info.get('nullable', 'Y').upper() == 'N':
                    if not is_pk:
                        final_info['nullable'] = 'Y'
            else:
                # CSV 有、文档无：必填且无默认值 → 改为可空（主键字段除外，
                # 主流程中主键多余字段不处理，保持原样）
                is_pk = is_pk_by_csv_for_table(base_table, col_upper, csv_structure, base_name_map)
                if (csv_info.get('nullable', 'Y').upper() == 'N'
                        and not csv_info.get('default', '').strip()
                        and not is_pk):
                    final_info['nullable'] = 'Y'

            final_csv_cols[col_upper] = final_info

        # 文档有、CSV 无的列（文档标记为主键的新增列 → 需人工确认，原表不执行，TRAN/LOG 不添加）
        for col_upper, doc_col in sorted(doc_cols.items()):
            if col_upper not in csv_cols:
                if is_primary_key_field(doc_col):
                    continue
                new_docx_cols.append((col_upper, doc_col))

        return final_csv_cols, new_docx_cols

    def generate_rebuild_sql(tc):
        """
        生成TRAN/LOG表重建语句：表存在则 DROP，再 CREATE。
        重建结构 = TRAN/LOG 表自身 CSV 列 ∪ Word 文档基表列（字段并集 | 冲突按 Word）。
        无主键，不额外添加公共字段（公共字段已在 TRAN/LOG 自身 CSV 中）。
        """
        tname = tc['table_name']
        cn_name = tc['cn_name']
        suffix = tc['suffix']
        base_table = tc.get('base_table_name', '')
        t = _table_ref(tname, db_type)

        # 构建文档列映射: col_id -> col 全量信息
        doc_type_map = {}
        for col in tc['columns']:
            doc_type_map[col['id'].upper()] = col

        # ----- 第一步：推导原表最终结构（CSV + 安全修改）-----
        # TRAN/LOG 表重建应基于原表最终结构而非原始 CSV。
        # 原表安全修改（多余必填→可空、类型扩大、文档 O/C 改可空）需同步到 TRAN/LOG。
        final_csv_cols, new_docx_cols = _derive_final_base_columns(base_table)

        # ----- 第二步：按最终结构构建列定义 -----
        col_defs = []
        processed_cols = set()

        if final_csv_cols:
            for col_name_upper, csv_col_info in final_csv_cols.items():
                col_name = csv_col_info.get('_name', col_name_upper)
                c = _quote_identifier(col_name, db_type)

                if col_name_upper in doc_type_map:
                    # 文档有定义：类型已在 _derive_final_base_columns 中通过
                    # _merge_type_wider 与文档类型合并（取较宽者），这里直接用推导结果，
                    # 避免文档类型覆盖 CSV 已存在的更宽类型（如 CSV VARCHAR(32) 被文档 N3 覆盖为 VARCHAR(3)）。
                    full_type = _build_full_type_csv(csv_col_info)
                else:
                    # 文档无定义：保留 CSV 类型，nullability 用修改后的值
                    full_type = _build_full_type_csv(csv_col_info)

                null_str = 'NOT NULL' if csv_col_info.get('nullable', 'Y').upper() == 'N' else 'NULL'
                default_str = _build_default_str(csv_col_info.get('default', ''), full_type)

                parts = [f"    {c} {full_type}"]
                if default_str is not None:
                    parts.append(f"DEFAULT {default_str}")
                parts.append(null_str)
                col_defs.append(' '.join(parts))
                processed_cols.add(col_name_upper)
        else:
            # 无 CSV 结构时的兜底：纯用文档列
            for col in tc['columns']:
                col_id = col['id'].upper()
                full_type = _build_full_type(col['data_type'], col['format'], None, db_type)
                if not full_type:
                    continue
                c = _quote_identifier(col_id, db_type)
                null_str = 'NOT NULL' if col.get('constraint', '').upper() == 'M' else 'NULL'
                col_defs.append(f"    {c} {full_type} {null_str}")
                processed_cols.add(col_id)

        # ----- 第三步：文档有、最终结构无的列（纯文档新增列）-----
        for col_id_upper, doc_col in new_docx_cols:
            if col_id_upper not in processed_cols:
                full_type = _build_full_type(doc_col['data_type'], doc_col['format'], None, db_type)
                if not full_type:
                    continue
                c = _quote_identifier(col_id_upper, db_type)
                null_str = 'NOT NULL' if doc_col.get('constraint', '').upper() == 'M' else 'NULL'
                col_defs.append(f"    {c} {full_type} {null_str}")
                processed_cols.add(col_id_upper)

        # ----- 第四步：补充公共字段（SCZT等）-----
        # TRAN/LOG 重建表结构应与原表一致。仅当原表在 CSV 中时，补充"原表
        # CSV 中存在且未处理的公共字段"（保证 TRAN/LOG 与原表列集完全一致，
        # 不补原表没有的字段）。
        # 若原表不在 CSV 中（纯文档场景），公共字段作为新表默认字段补充。
        base_in_csv = base_table in csv_structure
        for cc in common_columns:
            col_name_upper = cc['name'].upper()
            if col_name_upper not in processed_cols:
                if base_in_csv:
                    # 原表 CSV 中有该公共字段才补
                    if col_name_upper in csv_structure[base_table]['columns']:
                        c = _quote_identifier(cc['name'], db_type)
                        col_defs.append(f"    {c} {cc['type_def']}")
                        processed_cols.add(col_name_upper)
                else:
                    c = _quote_identifier(cc['name'], db_type)
                    col_defs.append(f"    {c} {cc['type_def']}")
                    processed_cols.add(col_name_upper)

        col_defs_str = ",\n".join(col_defs)

        if is_sqlserver:
            create_sql = f"CREATE TABLE {t} (\n{col_defs_str}\n);"
        else:
            # EXECUTE IMMEDIATE 内单引号需双写转义（如 DEFAULT '0' → DEFAULT ''0''）
            col_defs_str_escaped = col_defs_str.replace("'", "''")
            create_sql = (
                f"BEGIN\n"
                f"    EXECUTE IMMEDIATE 'CREATE TABLE {t} (\n"
                f"{col_defs_str_escaped}\n"
                f")';\n"
                f"EXCEPTION\n"
                f"    WHEN OTHERS THEN\n"
                f"        IF SQLCODE != -955 THEN\n"
                f"            RAISE;\n"
                f"        END IF;\n"
                f"END;\n/"
            )

        if is_sqlserver:
            drop_part = (
                f"IF OBJECT_ID('{tname}', 'U') IS NOT NULL\n"
                f"    DROP TABLE {t};"
            )
            header = (
                f"-- ============================================\n"
                f"-- 重建 {tname}（{cn_name}）{suffix}表：按原表结构重建，无主键\n"
                f"-- ⚠️ 会清空该表全部数据\n"
                f"-- ============================================"
            )
            raw_block = drop_part + "\n\n" + create_sql
            return header + "\n" + raw_block
        else:
            header = (
                f"-- ============================================\n"
                f"-- 重建 {tname}（{cn_name}）{suffix}表：按原表结构重建，无主键\n"
                f"-- ⚠️ 会清空该表全部数据，请确认后执行\n"
                f"-- ============================================"
            )
            oracle_block = (
                f"BEGIN\n"
                f"    EXECUTE IMMEDIATE 'DROP TABLE {t}';\n"
                f"EXCEPTION\n"
                f"    WHEN OTHERS THEN\n"
                f"        IF SQLCODE != -942 THEN\n"
                f"            RAISE;\n"
                f"        END IF;\n"
                f"END;\n/\n"
                f"{create_sql}"
            )
            return header + "\n" + oracle_block

    for tc in tables_to_rebuild:
        rebuild_statements.append(generate_rebuild_sql(tc))

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
                    full_type = f"{db_type_str}({p},{s})"
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
                    comment = f"-- 多余字段 {csv_col_name}，改为可空"
                    csv_full_type = _build_full_type_csv(csv_col_info)
                    sql = _generate_alter_sql(table_name, csv_col_name, csv_full_type, True, db_type, 'MODIFY', nullability_only=True)
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
            char_types = ('VARCHAR', 'VARCHAR2', 'CHAR', 'NVARCHAR', 'NCHAR', 'CLOB', 'NCLOB')
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
                    expected_full = f"{expected_type}({p},{s})"
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
                        csv_int = csv_p - csv_s
                        exp_int = expected_p - expected_s
                        integer_shrinking = csv_int > exp_int

                        is_nullable = csv_col.get('nullable', 'Y').upper() == 'Y'
                        sql = _generate_alter_sql(
                            table_name, col_id,
                            f"{expected_type}({expected_p},{expected_s})",
                            is_nullable, db_type, 'MODIFY'
                        )

                        if is_pk_field_for_table(table_name, col, csv_structure, base_name_map) or integer_shrinking:
                            if is_pk_field_for_table(table_name, col, csv_structure, base_name_map):
                                comment = f"-- 主键字段 {table_name}.{col_id} 精度不足，需人工确认"
                            else:
                                comment = f"-- {table_name}.{col_id} 整数位从 {csv_int} 缩小到 {exp_int}，需人工确认"
                            unsafe_changes.append(f"{comment}\n" + "\n".join(f"-- {line}" for line in sql.split('\n')))
                        else:
                            comment = f"-- {table_name}.{col_id} 精度从 ({csv_p},{csv_s}) 扩大到 ({expected_p},{expected_s})"
                            safe_changes.append(f"{comment}\n{sql}")

            # 检查可空性
            doc_constraint = col.get('constraint', '').upper()
            db_nullable = csv_col.get('nullable', 'Y').upper()
            if doc_constraint in ('O', 'C') and db_nullable == 'N':
                comment = f"-- {table_name}.{col_id} 文档约束={doc_constraint}，数据库为NOT NULL，改为可空"
                csv_full_type = _build_full_type_csv(csv_col)
                sql = _generate_alter_sql(table_name, col_id, csv_full_type, True, db_type, 'MODIFY', nullability_only=True)

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
        'row_size_optimizations': row_size_optimizations,
        'rebuild_statements': rebuild_statements,
        'rebuild_mode': rebuild_mode
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
    parser.add_argument('--delimiter', default=',', help='CSV分隔符，默认逗号。Tab分隔使用 $\'\\t\'')
    parser.add_argument('--tran-log-mode', default='field_compare',
                        choices=['field_compare', 'rebuild'],
                        help='TRAN/LOG表处理方式：field_compare=逐字段核对（默认），rebuild=直接按原表结构重建')

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
    rows = read_csv(str(csv_path), args.encoding, args.delimiter)

    # 从CSV首行提取OWNER，后续DDL中表名自动加 owner 前缀
    global _script_owner
    if rows:
        _script_owner = rows[0].get('OWNER', '').strip().upper()
        if _script_owner:
            print(f"  Schema owner: {_script_owner}（ALTER/CREATE/DROP 中表名将加 \"{_script_owner}\". 前缀）")

    csv_structure = build_csv_structure(rows)
    print(f"  发现 {len(csv_structure)} 张数据库表")

    print(f"开始对比... (目标数据库: {db_type}, TRAN/LOG模式: {args.tran_log_mode})")
    result = compare_structures(md_structure, csv_structure, db_type, tran_log_mode=args.tran_log_mode)

    safe = result['safe_changes']
    unsafe = result['unsafe_changes']
    row_opt = result['row_size_optimizations']
    rebuild = result['rebuild_statements']
    rebuild_mode = result['rebuild_mode']

    print(f"安全修改: {len(safe)} 项")
    print(f"需人工确认: {len(unsafe)} 项")
    if row_opt:
        print(f"行大小优化: {len(row_opt)} 项")
    if rebuild_mode:
        print(f"TRAN/LOG重建: {len(rebuild)} 项")

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

    if rebuild_mode and rebuild:
        output_parts.append(
            "-- ========================================\n"
            "-- TRAN/LOG表重建（按原表结构，无主键）\n"
            "-- ⚠️ 重建会清空表数据，默认注释状态，确认后放开执行\n"
            "-- ========================================\n\n"
        )
        output_parts.extend(rebuild)
        output_parts.append("\n")

    # 统计行
    stat_line = f"-- 统计: 不安全={len(unsafe)}, 安全={len(safe)}"
    if row_opt:
        stat_line += f", 行大小优化={len(row_opt)}"
    if rebuild_mode:
        stat_line += f", TRAN/LOG重建={len(rebuild)}"
    output_parts.append(
        f"-- ========================================\n"
        f"{stat_line}\n"
        f"-- ========================================\n"
    )

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
