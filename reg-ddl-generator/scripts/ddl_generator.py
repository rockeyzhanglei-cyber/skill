#!/usr/bin/env python3
"""
DDL脚本生成器
根据解析结果生成多种数据库的DDL脚本
支持：MySQL、Oracle、SQL Server、PostgreSQL

v4.0.0 更新：
- 支持全量模式：generate_full_script 可处理全量模式解析结果
- 全量模式下 new_tables 包含所有表格，all_changes 和 modified_fields 为空

v2.4.3 更新：
- 修订记录格式完善：表名中文[表名]字段名中文[字段名]字段约束修改为"M"，表示格式修改为"AN..100"
- SQL注释格式与修订记录统一
- 所有数据库修改字段DDL注释格式统一
- 去除重复显示（data_type_category和data_type同时变红时只显示一次）
- 各列显示实际内容而非空引号

v2.4.2 更新：
- 使用存储的原始列值（required_value, format_value等）显示实际内容

v2.4.0 更新：
- 约束改为M（O→M）不生成DDL，只在修订记录注释中体现
- 约束显示改为"M"而非"必填"
- 修订记录格式改为：字段约束修改为""，表示格式修改为""，说明修改为""

v2.2.0 更新：
- 新增修改字段DDL生成函数（Oracle、MySQL、SQL Server、PostgreSQL）
- 新增 generate_revision_record_modified_fields 函数
- 区分DDL变更（约束、表示格式）和注释变更（说明、备注等）
- 只有约束和表示格式的修改才生成ALTER TABLE MODIFY脚本
"""

import re
from datetime import datetime

# 需要清理的不可见字符列表（从Word文档复制时可能带入）
INVISIBLE_CHARS = [
    '\u200b',  # 零宽空格 (ZERO WIDTH SPACE)
    '\u200c',  # 零宽非连接符 (ZERO WIDTH NON-JOINER)
    '\u200d',  # 零宽连接符 (ZERO WIDTH JOINER)
    '\u200e',  # 左至右标记 (LEFT-TO-RIGHT MARK)
    '\u200f',  # 右至左标记 (RIGHT-TO-LEFT MARK)
    '\u2060',  # 字连接符 (WORD JOINER)
    '\u2061',  # 函数应用 (FUNCTION APPLICATION)
    '\u2062',  # 不可见乘号 (INVISIBLE TIMES)
    '\u2063',  # 不可见分隔符 (INVISIBLE SEPARATOR)
    '\u2064',  # 不可见加号 (INVISIBLE PLUS)
    '\u206a',  # 抑止对称交换 (INHIBIT SYMMETRIC SWAPPING)
    '\u206b',  # 激活对称交换 (ACTIVATE SYMMETRIC SWAPPING)
    '\u206c',  # 抑止阿拉伯数字成形 (INHIBIT ARABIC FORM SHAPING)
    '\u206d',  # 激活阿拉伯数字成形 (ACTIVATE ARABIC FORM SHAPING)
    '\u206e',  # 国民数字形状 (NATIONAL DIGIT SHAPES)
    '\u206f',  # 欧洲数字形状 (EUROPEAN DIGIT SHAPES)
    '\ufeff',  # 零宽非断空格 (ZERO WIDTH NO-BREAK SPACE, BOM)
    '\u00ad',  # 软连字符 (SOFT HYPHEN)
]

def clean_invisible_chars(text):
    """清理文本中的不可见字符（从Word文档复制时可能带入的特殊字符）

    这些字符会导致Oracle等数据库解析报错，如 ORA-00911: invalid character

    参数:
        text: 输入文本

    返回:
        清理后的文本
    """
    if not text:
        return text
    result = text
    for char in INVISIBLE_CHARS:
        result = result.replace(char, '')
    return result

# 类型映射表
TYPE_MAP = {
    'mysql': {
        'VARCHAR': 'varchar',
        'VARCHAR2': 'varchar',
        'NUMBER': 'decimal',
        'NUMERIC': 'decimal',
        'INT': 'int',
        'INTEGER': 'int',
        'DATE': 'date',
        'DATETIME': 'datetime',
        'TIMESTAMP': 'timestamp',
        'TEXT': 'text',
        'CLOB': 'text',
        'BLOB': 'blob'
    },
    'oracle': {
        'VARCHAR': 'varchar2',
        'VARCHAR2': 'varchar2',
        'NUMBER': 'number',
        'NUMERIC': 'number',
        'INT': 'number',
        'INTEGER': 'number',
        'DATE': 'date',
        'DATETIME': 'date',
        'TIMESTAMP': 'timestamp',
        'TEXT': 'clob',
        'CLOB': 'clob',
        'BLOB': 'blob'
    },
    'sqlserver': {
        'VARCHAR': 'varchar',
        'VARCHAR2': 'varchar',
        'NUMBER': 'decimal',
        'NUMERIC': 'decimal',
        'INT': 'int',
        'INTEGER': 'int',
        'DATE': 'date',
        'DATETIME': 'datetime',
        'TIMESTAMP': 'datetime',
        'TEXT': 'nvarchar(max)',
        'CLOB': 'nvarchar(max)',
        'BLOB': 'varbinary(max)'
    },
    'postgresql': {
        'VARCHAR': 'varchar',
        'VARCHAR2': 'varchar',
        'NUMBER': 'numeric',
        'NUMERIC': 'numeric',
        'INT': 'integer',
        'INTEGER': 'integer',
        'DATE': 'date',
        'DATETIME': 'timestamp',
        'TIMESTAMP': 'timestamp',
        'TEXT': 'text',
        'CLOB': 'text',
        'BLOB': 'bytea',
        'L': 'varchar(1)'
    }
}

def map_type(data_type, length, db_type):
    """将原始类型映射为目标数据库类型

    会自动清理数据类型中的不可见字符
    """
    # 清理不可见字符
    data_type = clean_invisible_chars(data_type)
    length = clean_invisible_chars(length) if length else length

    data_type = data_type.upper().strip()
    length_str = length.strip() if length else ''

    db_type_lower = db_type.lower()
    type_mapping = TYPE_MAP.get(db_type_lower, TYPE_MAP['oracle'])

    # 特殊处理：如果length是大字段类型名称（TEXT/CLOB/BLOB等），则忽略原类型，使用大字段类型
    lob_types = ['TEXT', 'CLOB', 'BLOB', 'LONGTEXT', 'MEDIUMTEXT']
    if length_str.upper() in lob_types:
        data_type = length_str.upper()
        length_str = ''

    mapped_type = type_mapping.get(data_type, data_type.lower())

    # 处理长度 - TEXT/CLOB等大字段类型不需要长度
    if mapped_type in ['clob', 'text', 'blob', 'bytea', 'nvarchar(max)', 'varbinary(max)']:
        return mapped_type
    elif mapped_type in ['varchar', 'varchar2'] and length_str:
        return f"{mapped_type}({length_str})"
    elif mapped_type in ['varchar', 'varchar2'] and not length_str:
        # 格式列为空但类型为S1/S2/S3时，默认varchar(255)防止无长度报错
        return f"{mapped_type}(255)"
    elif mapped_type in ['number', 'decimal', 'numeric'] and length_str:
        return f"{mapped_type}({length_str})"
    elif mapped_type in ['number', 'decimal', 'numeric'] and not length_str:
        # 格式列为空但类型为N时，默认numeric(18,2)防止无精度报错
        return f"{mapped_type}(18,2)"
    elif mapped_type in ['date', 'timestamp', 'int', 'integer']:
        return mapped_type
    else:
        return mapped_type

def apply_case(name, case_style):
    """应用大小写格式（仅用于DDL中的表名/字段名）

    会自动清理不可见字符（零宽空格等），防止Oracle报 ORA-00911 错误

    参数:
        name: 表名或字段名
        case_style: 大小写格式 (upper/lower/original)

    返回:
        处理后的名称
    """
    # 先清理不可见字符
    name = clean_invisible_chars(name)
    if case_style == 'upper':
        return name.upper()
    elif case_style == 'lower':
        return name.lower()
    else:
        return name

def generate_oracle_new_table_ddl(table_en, table_cn, fields, case_style, primary_keys=None, include_tran_log=True, include_public_fields=True):
    """生成Oracle新增表DDL（参考PostgreSQL格式风格）

    v3.1.0 更新：
    - 添加清晰的分隔线和注释块
    - 简化代码结构，减少嵌套
    - 统一注释风格
    - TRAN/LOG表同步独立章节

    参数:
        include_tran_log: 是否生成TRAN/LOG关联表（默认True）
        include_public_fields: 是否添加sczt公共字段（默认True）
    """
    table_name = apply_case(table_en, case_style)
    tran_name = table_name + '_tran'
    log_name = table_name + '_log'

    # 清理表名中的不可见字符
    table_cn = clean_invisible_chars(table_cn)
    table_en = clean_invisible_chars(table_en)

    # 公共字段（有默认值）- 仅在include_public_fields=True时添加
    public_fields_main = []
    if include_public_fields:
        public_fields_main = [
            {'field_en': 'sczt', 'field_cn': '创建状态', 'db_type': 'varchar2(1)', 'constraint': "default ''0'' not null"},
            {'field_en': 'sczt_index', 'field_cn': '索引状态', 'db_type': 'varchar2(1)', 'constraint': 'null'},
            {'field_en': 'sczt_ggws', 'field_cn': '公共卫生状态', 'db_type': 'varchar2(1)', 'constraint': 'null'},
            {'field_en': 'sczt_ylfw', 'field_cn': '医疗服务状态', 'db_type': 'varchar2(1)', 'constraint': 'null'}
        ]

    # 主键约束（如果有）
    pk_constraint = ''
    if primary_keys and len(primary_keys) > 0:
        pk_fields = [apply_case(pk, case_style) for pk in primary_keys]
        pk_constraint = ",\n            constraint pk_" + table_name + " primary key (" + ', '.join(pk_fields) + ")"

    # 构建字段列表（非必填加null）
    def build_field_lines(fields_list, add_null=True):
        lines = []
        for f in fields_list:
            field_name = apply_case(f['field_en'], case_style)
            db_type = f['db_type']
            constraint = f['constraint'] if f['constraint'] else ('null' if add_null else '')
            lines.append("            " + field_name + " " + db_type + " " + constraint)
        return lines

    # 主表字段
    field_lines_main = build_field_lines(fields)
    for pf in public_fields_main:
        field_name = apply_case(pf['field_en'], case_style)
        field_lines_main.append("            " + field_name + " " + pf['db_type'] + " " + pf['constraint'])

    # TRAN/LOG字段（无约束）
    field_lines_sync = build_field_lines(fields, add_null=True)
    for pf in public_fields_main:
        field_name = apply_case(pf['field_en'], case_style)
        field_lines_sync.append("            " + field_name + " " + pf['db_type'] + " " + pf['constraint'])

    # 预计算join结果
    fields_main_str = ',\n'.join(field_lines_main)
    fields_sync_str = ',\n'.join(field_lines_sync)

    # 辅助函数：生成comment语句（正确处理单引号）
    def make_comment_sql(tbl, comment_text):
        comment_text = clean_invisible_chars(comment_text)
        return "        execute immediate 'comment on table " + tbl + " is ''" + comment_text + "''';\n"

    def make_column_comment_sql(tbl, col, comment_text):
        comment_text = clean_invisible_chars(comment_text)
        return "        execute immediate 'comment on column " + tbl + "." + col + " is ''" + comment_text + "''';\n"

    # 开始生成DDL（简化注释风格，CREATE TABLE保持多行）
    ddl = f"""-- {table_cn}[{table_en}] - 新增表
declare
    v_count number;
begin
    select count(*) into v_count from user_tables where table_name = upper('{table_name}');
    if v_count = 0 then
        execute immediate 'create table {table_name} (
{fields_main_str}{pk_constraint}
        )';
        execute immediate 'comment on table {table_name} is ''{table_cn}''';
"""

    # 主表字段注释（简化）
    for f in fields:
        field_name = apply_case(f['field_en'], case_style)
        field_cn = clean_invisible_chars(f['field_cn'])
        description = clean_invisible_chars(f.get('description', ''))[:100] if f.get('description') else ''
        comment_text = field_cn + '，' + description
        ddl += make_column_comment_sql(table_name, field_name, comment_text)

    for pf in public_fields_main:
        field_name = apply_case(pf['field_en'], case_style)
        ddl += make_column_comment_sql(table_name, field_name, pf['field_cn'])

    ddl += "    end if;\n"

    # TRAN表同步 - 简化注释，CREATE TABLE保持多行
    if include_tran_log:
        ddl += f"""    select count(*) into v_count from user_tables where table_name = upper('{tran_name}');
    if v_count = 0 then
        execute immediate 'create table {tran_name} (
{fields_sync_str}
        )';
        execute immediate 'comment on table {tran_name} is ''{table_cn}_事务''';
"""

        for f in fields:
            field_name = apply_case(f['field_en'], case_style)
            field_cn = clean_invisible_chars(f['field_cn'])
            description = clean_invisible_chars(f.get('description', ''))[:100] if f.get('description') else ''
            comment_text = field_cn + '，' + description
            ddl += make_column_comment_sql(tran_name, field_name, comment_text)

        for pf in public_fields_main:
            field_name = apply_case(pf['field_en'], case_style)
            ddl += make_column_comment_sql(tran_name, field_name, pf['field_cn'])

        ddl += "    end if;\n"

        # LOG表同步 - 简化注释，CREATE TABLE保持多行
        ddl += f"""    select count(*) into v_count from user_tables where table_name = upper('{log_name}');
    if v_count = 0 then
        execute immediate 'create table {log_name} (
{fields_sync_str}
        )';
        execute immediate 'comment on table {log_name} is ''{table_cn}_日志''';
"""

        for f in fields:
            field_name = apply_case(f['field_en'], case_style)
            field_cn = clean_invisible_chars(f['field_cn'])
            description = clean_invisible_chars(f.get('description', ''))[:100] if f.get('description') else ''
            comment_text = field_cn + '，' + description
            ddl += make_column_comment_sql(log_name, field_name, comment_text)

        for pf in public_fields_main:
            field_name = apply_case(pf['field_en'], case_style)
            ddl += make_column_comment_sql(log_name, field_name, pf['field_cn'])

        ddl += "    end if;\n"

    ddl += "end;\n"
    ddl += "/\n\n"

    return ddl

def generate_oracle_add_field_ddl(table_en, table_cn, field_en, field_cn, db_type, constraint, case_style):
    """生成Oracle新增字段DDL（单个字段）

    v3.1.0 更新：参考PostgreSQL格式风格
    - 添加分隔线和清晰注释
    - 简化代码结构，去除表存在检查（新增字段场景表应已存在）
    - 检查字段是否存在的逻辑更简洁
    """
    table_name = apply_case(table_en, case_style)
    field_name = apply_case(field_en, case_style)

    # 清理表名和字段名中的不可见字符（用于注释）
    table_cn_clean = clean_invisible_chars(table_cn)
    field_cn_clean = clean_invisible_chars(field_cn)

    ddl = f"""-- {table_cn_clean}[{table_en}] - 新增字段：{field_cn_clean}
declare
    v_count number;
begin
    select count(*) into v_count from user_tab_columns where table_name = upper('{table_name}') and column_name = upper('{field_name}');
    if v_count = 0 then
        execute immediate 'alter table {table_name} add {field_name} {db_type} null';
        execute immediate 'comment on column {table_name}.{field_name} is ''{field_cn_clean}''';
    end if;
end;
/
"""
    return ddl

def _build_field_type_str(orig_type, length):
    """构建字段类型字符串，处理无效长度

    会自动清理类型和长度中的不可见字符
    """
    # 清理不可见字符
    orig_type = clean_invisible_chars(orig_type)
    length = clean_invisible_chars(length) if length else length
    # 中文全角圆点（U+FF0E）→ 英文句点（U+002E）
    if length:
        length = length.replace('\uff0e', '.')

    is_valid_length = length and re.match(r'^[\d,\.\s]+$', str(length).strip())
    no_length_types = ['DATETIME', 'DATE', 'TIMESTAMP', 'TEXT', 'CLOB', 'BLOB']
    if orig_type.upper() in no_length_types:
        return orig_type
    elif is_valid_length:
        return f"{orig_type}({str(length).strip()})"
    else:
        return orig_type

def generate_oracle_combined_field_ddl(table_en, table_cn, fields, case_style, include_tran_log=True):
    """生成Oracle多字段合并DDL

    v3.2.0 更新：
    - 同一张表多个字段放到一个 begin-end 块
    - TRAN/LOG 也放入同一个 begin-end
    - 先判断表是否存在，再判断字段是否存在
    - 内容区域不加注释，只在脚本块前写简单描述
    - 大小写格式应用到所有字符（包括SQL语句）

    参数:
        include_tran_log: 是否生成TRAN/LOG关联表同步（默认True）
    """
    table_name = apply_case(table_en, case_style)
    tran_name = table_name + '_TRAN' if case_style == 'upper' else table_name + '_tran'
    log_name = table_name + '_LOG' if case_style == 'upper' else table_name + '_log'

    # 清理表名中的不可见字符
    table_cn = clean_invisible_chars(table_cn)
    table_en = clean_invisible_chars(table_en)

    # 大小写格式应用到所有关键字和语句
    KW_DECLARE = 'DECLARE' if case_style == 'upper' else 'declare'
    KW_BEGIN = 'BEGIN' if case_style == 'upper' else 'begin'
    KW_END = 'END' if case_style == 'upper' else 'end'
    KW_IF = 'IF' if case_style == 'upper' else 'if'
    KW_THEN = 'THEN' if case_style == 'upper' else 'then'
    KW_SELECT = 'SELECT' if case_style == 'upper' else 'select'
    KW_COUNT = 'COUNT' if case_style == 'upper' else 'count'
    KW_INTO = 'INTO' if case_style == 'upper' else 'into'
    KW_FROM = 'FROM' if case_style == 'upper' else 'from'
    KW_WHERE = 'WHERE' if case_style == 'upper' else 'where'
    KW_AND = 'AND' if case_style == 'upper' else 'and'
    KW_UPPER = 'UPPER' if case_style == 'upper' else 'upper'
    KW_EXECUTE = 'EXECUTE' if case_style == 'upper' else 'execute'
    KW_IMMEDIATE = 'IMMEDIATE' if case_style == 'upper' else 'immediate'
    KW_ALTER = 'ALTER' if case_style == 'upper' else 'alter'
    KW_TABLE = 'TABLE' if case_style == 'upper' else 'table'
    KW_ADD = 'ADD' if case_style == 'upper' else 'add'
    KW_NULL = 'NULL' if case_style == 'upper' else 'null'
    KW_COMMENT = 'COMMENT' if case_style == 'upper' else 'comment'
    KW_ON = 'ON' if case_style == 'upper' else 'on'
    KW_COLUMN = 'COLUMN' if case_style == 'upper' else 'column'
    KW_IS = 'IS' if case_style == 'upper' else 'is'
    KW_NUMBER = 'NUMBER' if case_style == 'upper' else 'number'
    KW_V_COUNT = 'V_COUNT' if case_style == 'upper' else 'v_count'
    KW_USER_TABLES = 'USER_TABLES' if case_style == 'upper' else 'user_tables'
    KW_USER_TAB_COLUMNS = 'USER_TAB_COLUMNS' if case_style == 'upper' else 'user_tab_columns'
    KW_TABLE_NAME = 'TABLE_NAME' if case_style == 'upper' else 'table_name'
    KW_COLUMN_NAME = 'COLUMN_NAME' if case_style == 'upper' else 'column_name'

    # 开始生成DDL - 构建字段描述
    field_desc_parts = []
    for f in fields:
        field_cn = clean_invisible_chars(f['field_cn'])
        field_en = clean_invisible_chars(f['field_en'])
        type_str = _build_field_type_str(f['data_type'], f['length'])
        required_cn = clean_invisible_chars(f['required_cn'])
        field_desc_parts.append(f"{field_cn}[{field_en},{type_str},{required_cn}]")
    field_desc = '、'.join(field_desc_parts)

    ddl = f"-- {table_cn}[{table_en}]新增字段：{field_desc}\n"
    ddl += f"{KW_DECLARE}\n"
    ddl += f"    {KW_V_COUNT} {KW_NUMBER};\n"
    ddl += f"{KW_BEGIN}\n"

    # 主表检查和字段添加
    ddl += f"    {KW_SELECT} {KW_COUNT}(*) {KW_INTO} {KW_V_COUNT} {KW_FROM} {KW_USER_TABLES} {KW_WHERE} {KW_TABLE_NAME} = {KW_UPPER}('{table_name}');\n"
    ddl += f"    {KW_IF} {KW_V_COUNT} > 0 {KW_THEN}\n"

    for f in fields:
        field_name = apply_case(f['field_en'], case_style)
        db_type = f['db_type'].upper() if case_style == 'upper' else f['db_type'].lower()
        field_cn = clean_invisible_chars(f['field_cn'])

        ddl += f"        {KW_SELECT} {KW_COUNT}(*) {KW_INTO} {KW_V_COUNT} {KW_FROM} {KW_USER_TAB_COLUMNS} {KW_WHERE} {KW_TABLE_NAME} = {KW_UPPER}('{table_name}') {KW_AND} {KW_COLUMN_NAME} = {KW_UPPER}('{field_name}');\n"
        ddl += f"        {KW_IF} {KW_V_COUNT} = 0 {KW_THEN}\n"
        ddl += f"            {KW_EXECUTE} {KW_IMMEDIATE} '{KW_ALTER} {KW_TABLE} {table_name} {KW_ADD} {field_name} {db_type} {KW_NULL}';\n"
        ddl += f"            {KW_EXECUTE} {KW_IMMEDIATE} '{KW_COMMENT} {KW_ON} {KW_COLUMN} {table_name}.{field_name} {KW_IS} ''{field_cn}''';\n"
        ddl += f"        {KW_END} {KW_IF};\n"

    ddl += f"    {KW_END} {KW_IF};\n"

    # TRAN表同步
    if include_tran_log:
        ddl += f"    {KW_SELECT} {KW_COUNT}(*) {KW_INTO} {KW_V_COUNT} {KW_FROM} {KW_USER_TABLES} {KW_WHERE} {KW_TABLE_NAME} = {KW_UPPER}('{tran_name}');\n"
        ddl += f"    {KW_IF} {KW_V_COUNT} > 0 {KW_THEN}\n"
        for f in fields:
            field_name = apply_case(f['field_en'], case_style)
            db_type = f['db_type'].upper() if case_style == 'upper' else f['db_type'].lower()
            ddl += f"        {KW_SELECT} {KW_COUNT}(*) {KW_INTO} {KW_V_COUNT} {KW_FROM} {KW_USER_TAB_COLUMNS} {KW_WHERE} {KW_TABLE_NAME} = {KW_UPPER}('{tran_name}') {KW_AND} {KW_COLUMN_NAME} = {KW_UPPER}('{field_name}');\n"
            ddl += f"        {KW_IF} {KW_V_COUNT} = 0 {KW_THEN}\n"
            ddl += f"            {KW_EXECUTE} {KW_IMMEDIATE} '{KW_ALTER} {KW_TABLE} {tran_name} {KW_ADD} {field_name} {db_type} {KW_NULL}';\n"
            ddl += f"        {KW_END} {KW_IF};\n"
        ddl += f"    {KW_END} {KW_IF};\n"

        # LOG表同步
        ddl += f"    {KW_SELECT} {KW_COUNT}(*) {KW_INTO} {KW_V_COUNT} {KW_FROM} {KW_USER_TABLES} {KW_WHERE} {KW_TABLE_NAME} = {KW_UPPER}('{log_name}');\n"
        ddl += f"    {KW_IF} {KW_V_COUNT} > 0 {KW_THEN}\n"
        for f in fields:
            field_name = apply_case(f['field_en'], case_style)
            db_type = f['db_type'].upper() if case_style == 'upper' else f['db_type'].lower()
            ddl += f"        {KW_SELECT} {KW_COUNT}(*) {KW_INTO} {KW_V_COUNT} {KW_FROM} {KW_USER_TAB_COLUMNS} {KW_WHERE} {KW_TABLE_NAME} = {KW_UPPER}('{log_name}') {KW_AND} {KW_COLUMN_NAME} = {KW_UPPER}('{field_name}');\n"
            ddl += f"        {KW_IF} {KW_V_COUNT} = 0 {KW_THEN}\n"
            ddl += f"            {KW_EXECUTE} {KW_IMMEDIATE} '{KW_ALTER} {KW_TABLE} {log_name} {KW_ADD} {field_name} {db_type} {KW_NULL}';\n"
            ddl += f"        {KW_END} {KW_IF};\n"
        ddl += f"    {KW_END} {KW_IF};\n"

    ddl += f"{KW_END};\n"
    ddl += "/\n\n"

    return ddl

def generate_oracle_sync_ddl(sync_table, table_cn, field_en, field_cn, db_type, case_style):
    """生成Oracle关联表同步DDL（简化注释）"""
    table_name = apply_case(sync_table, case_style)
    field_name = apply_case(field_en, case_style)

    ddl = f"""-- 关联表同步：{table_name} - {field_cn}
declare
    v_count number;
begin
    select count(*) into v_count from user_tab_columns where table_name = upper('{table_name}') and column_name = upper('{field_name}');
    if v_count = 0 then
        execute immediate 'alter table {table_name} add {field_name} {db_type} null';
    end if;
end;
/
"""
    return ddl

def generate_mysql_new_table_ddl(table_en, table_cn, fields, case_style, primary_keys=None, include_tran_log=True, include_public_fields=True):
    """生成MySQL新增表DDL（主表+TRAN+LOG合并到一个脚本块）

    参数:
        include_tran_log: 是否生成TRAN/LOG关联表（默认True）
        include_public_fields: 是否添加sczt公共字段（默认True）
    """
    table_name = apply_case(table_en, case_style)
    tran_name = table_name + '_tran'
    log_name = table_name + '_log'

    # 公共字段（有默认值）- 仅在include_public_fields=True时添加
    public_fields_main = []
    if include_public_fields:
        public_fields_main = [
            {'field_en': 'sczt', 'field_cn': '创建状态', 'db_type': 'varchar(1)', 'constraint': "default ''0'' not null"},
            {'field_en': 'sczt_index', 'field_cn': '索引状态', 'db_type': 'varchar(1)', 'constraint': 'null'},
            {'field_en': 'sczt_ggws', 'field_cn': '公共卫生状态', 'db_type': 'varchar(1)', 'constraint': 'null'},
            {'field_en': 'sczt_ylfw', 'field_cn': '医疗服务状态', 'db_type': 'varchar(1)', 'constraint': 'null'}
        ]

    # 主键约束（如果有）
    pk_constraint = ''
    if primary_keys and len(primary_keys) > 0:
        pk_fields = [apply_case(pk, case_style) for pk in primary_keys]
        pk_constraint = ',\n    primary key (' + ', '.join(pk_fields) + ')'

    # 构建字段列表函数（MySQL concat内部单引号需要用双单引号表示）
    def build_field_lines(fields_list, add_null=True):
        lines = []
        for f in fields_list:
            field_name = apply_case(f['field_en'], case_style)
            db_type = f['db_type']
            constraint = f['constraint'] if f['constraint'] else ('null' if add_null else '')
            lines.append("    " + field_name + " " + db_type + " " + constraint + " comment ''" + f['field_cn'] + "''")
        return lines

    # 主表字段
    field_lines_main = build_field_lines(fields)
    for pf in public_fields_main:
        field_name = apply_case(pf['field_en'], case_style)
        field_lines_main.append("    " + field_name + " " + pf['db_type'] + " " + pf['constraint'] + " comment ''" + pf['field_cn'] + "''")

    # TRAN/LOG字段（无约束）
    field_lines_sync = build_field_lines(fields, add_null=True)
    for pf in public_fields_main:
        field_name = apply_case(pf['field_en'], case_style)
        field_lines_sync.append("    " + field_name + " " + pf['db_type'] + " " + pf['constraint'] + " comment ''" + pf['field_cn'] + "''")

    fields_main_str = ',\n'.join(field_lines_main)
    fields_sync_str = ',\n'.join(field_lines_sync)

    # 开始生成DDL
    ddl = "-- 新增表：" + table_cn + "[" + table_en + "]\n"

    # 主表
    ddl += "set @tablename = '" + table_name + "';\n"
    ddl += "set @createTable = (select if(\n"
    ddl += "  (select count(*) from information_schema.tables where table_schema = database() and table_name = @tablename) > 0,\n"
    ddl += "  'select 1',\n"
    ddl += "  concat('create table ', @tablename, ' (\n"
    ddl += fields_main_str + pk_constraint + "\n"
    ddl += "  ) comment=''" + table_cn + "''')\n"
    ddl += "));\n"
    ddl += "prepare createIfNotExists from @createTable;\n"
    ddl += "execute createIfNotExists;\n"
    ddl += "deallocate prepare createIfNotExists;\n"

    # TRAN表和LOG表 - 仅在include_tran_log=True时生成
    if include_tran_log:
        ddl += "set @tablename = '" + tran_name + "';\n"
        ddl += "set @createTable = (select if(\n"
        ddl += "  (select count(*) from information_schema.tables where table_schema = database() and table_name = @tablename) > 0,\n"
        ddl += "  'select 1',\n"
        ddl += "  concat('create table ', @tablename, ' (\n"
        ddl += fields_sync_str + "\n"
        ddl += "  ) comment=''" + table_cn + "_事务''')\n"
        ddl += "));\n"
        ddl += "prepare createIfNotExists from @createTable;\n"
        ddl += "execute createIfNotExists;\n"
        ddl += "deallocate prepare createIfNotExists;\n"

        ddl += "set @tablename = '" + log_name + "';\n"
        ddl += "set @createTable = (select if(\n"
        ddl += "  (select count(*) from information_schema.tables where table_schema = database() and table_name = @tablename) > 0,\n"
        ddl += "  'select 1',\n"
        ddl += "  concat('create table ', @tablename, ' (\n"
        ddl += fields_sync_str + "\n"
        ddl += "  ) comment=''" + table_cn + "_日志''')\n"
        ddl += "));\n"
        ddl += "prepare createIfNotExists from @createTable;\n"
        ddl += "execute createIfNotExists;\n"
        ddl += "deallocate prepare createIfNotExists;\n"

    ddl += "\n"

    return ddl

def generate_mysql_add_field_ddl(table_en, table_cn, field_en, field_cn, db_type, constraint, case_style):
    """生成MySQL新增字段DDL（单个字段，保留向后兼容）"""
    table_name = apply_case(table_en, case_style)
    field_name = apply_case(field_en, case_style)

    # 清理表名和字段名中的不可见字符（用于注释）
    table_cn_clean = clean_invisible_chars(table_cn)
    field_cn_clean = clean_invisible_chars(field_cn)

    ddl = f"""-- {table_cn_clean}[{table_en}] 新增字段 {field_cn_clean}
set @dbname = database();
set @tablename = '{table_name}';
set @columnname = '{field_name}';
set @preparedStatement = (select if(
  (select count(*) from information_schema.columns
   where table_schema = @dbname and table_name = @tablename and column_name = @columnname) > 0,
  'select 1',
  concat('alter table ', @tablename, ' add column {field_name} {db_type} {constraint} comment ''{field_cn_clean}''')
));
prepare alterIfNotExists from @preparedStatement;
execute alterIfNotExists;
deallocate prepare alterIfNotExists;
"""
    return ddl

def generate_mysql_combined_field_ddl(table_en, table_cn, fields, case_style, include_tran_log=True):
    """生成MySQL多字段合并DDL

    v3.2.0 更新：
    - 同一张表多个字段合并处理
    - TRAN/LOG 同步紧跟主表
    - 内容区域不加注释，只在脚本块前写简单描述
    - 大小写格式应用到所有字符

    参数:
        include_tran_log: 是否生成TRAN/LOG关联表同步（默认True）
    """
    table_name = apply_case(table_en, case_style)
    tran_name = table_name + '_TRAN' if case_style == 'upper' else table_name + '_tran'
    log_name = table_name + '_LOG' if case_style == 'upper' else table_name + '_log'

    # 清理表名中的不可见字符
    table_cn = clean_invisible_chars(table_cn)
    table_en = clean_invisible_chars(table_en)

    # 开始生成DDL
    ddl = f"-- {table_cn}[{table_en}]新增字段\n"

    # 主表新增字段
    for f in fields:
        field_name = apply_case(f['field_en'], case_style)
        db_type = f['db_type'].upper() if case_style == 'upper' else f['db_type'].lower()
        field_cn = f['field_cn']
        ddl += f"set @preparedStatement = (select if(\n"
        ddl += f"  (select count(*) from information_schema.columns where table_schema = database() and table_name = '{table_name}' and column_name = '{field_name}') > 0,\n"
        ddl += f"  'select 1',\n"
        ddl += f"  concat('alter table {table_name} add column {field_name} {db_type} null comment ''{field_cn}''')\n"
        ddl += f"));\n"
        ddl += f"prepare alterIfNotExists from @preparedStatement;\n"
        ddl += f"execute alterIfNotExists;\n"
        ddl += f"deallocate prepare alterIfNotExists;\n"

    # TRAN表同步
    if include_tran_log:
        for f in fields:
            field_name = apply_case(f['field_en'], case_style)
            db_type = f['db_type'].upper() if case_style == 'upper' else f['db_type'].lower()
            ddl += f"set @preparedStatement = (select if(\n"
            ddl += f"  (select count(*) from information_schema.columns where table_schema = database() and table_name = '{tran_name}' and column_name = '{field_name}') > 0,\n"
            ddl += f"  'select 1',\n"
            ddl += f"  concat('alter table {tran_name} add column {field_name} {db_type} null')\n"
            ddl += f"));\n"
            ddl += f"prepare alterIfNotExists from @preparedStatement;\n"
            ddl += f"execute alterIfNotExists;\n"
            ddl += f"deallocate prepare alterIfNotExists;\n"

        # LOG表同步
        for f in fields:
            field_name = apply_case(f['field_en'], case_style)
            db_type = f['db_type'].upper() if case_style == 'upper' else f['db_type'].lower()
            ddl += f"set @preparedStatement = (select if(\n"
            ddl += f"  (select count(*) from information_schema.columns where table_schema = database() and table_name = '{log_name}' and column_name = '{field_name}') > 0,\n"
            ddl += f"  'select 1',\n"
            ddl += f"  concat('alter table {log_name} add column {field_name} {db_type} null')\n"
            ddl += f"));\n"
            ddl += f"prepare alterIfNotExists from @preparedStatement;\n"
            ddl += f"execute alterIfNotExists;\n"
            ddl += f"deallocate prepare alterIfNotExists;\n"

    ddl += "\n"
    return ddl

def generate_mysql_sync_ddl(sync_table, table_cn, field_en, field_cn, db_type, case_style):
    """生成MySQL关联表同步DDL"""
    table_name = apply_case(sync_table, case_style)
    field_name = apply_case(field_en, case_style)

    ddl = f"""-- {table_cn}[{table_name}] 同步新增字段 {field_cn}
set @dbname = database();
set @tablename = '{table_name}';
set @columnname = '{field_name}';
set @preparedStatement = (select if(
  (select count(*) from information_schema.columns
   where table_schema = @dbname and table_name = @tablename and column_name = @columnname) > 0,
  'select 1',
  concat('alter table ', @tablename, ' add column {field_name} {db_type}')
));
prepare alterIfNotExists from @preparedStatement;
execute alterIfNotExists;
deallocate prepare alterIfNotExists;
"""
    return ddl

def generate_sqlserver_new_table_ddl(table_en, table_cn, fields, case_style, primary_keys=None, include_tran_log=True, include_public_fields=True):
    """生成SQL Server新增表DDL（主表+TRAN+LOG合并）

    v4.2.0 更新：
    - 大小写格式应用到所有字符（SQL关键字、数据类型、表名、字段名）
    - 每个表（原表、TRAN、LOG）创建完后加GO分隔符

    参数:
        include_tran_log: 是否生成TRAN/LOG关联表（默认True）
        include_public_fields: 是否添加sczt公共字段（默认True）
    """
    table_name = apply_case(table_en, case_style)
    tran_name = table_name + '_TRAN' if case_style == 'upper' else table_name + '_tran'
    log_name = table_name + '_LOG' if case_style == 'upper' else table_name + '_log'

    # 公共字段 - 仅在include_public_fields=True时添加
    public_fields_main = []
    if include_public_fields:
        public_fields_main = [
            {'field_en': 'sczt', 'field_cn': '创建状态', 'db_type': 'varchar(1)', 'constraint': "default ''0'' not null"},
            {'field_en': 'sczt_index', 'field_cn': '索引状态', 'db_type': 'varchar(1)', 'constraint': 'null'},
            {'field_en': 'sczt_ggws', 'field_cn': '公共卫生状态', 'db_type': 'varchar(1)', 'constraint': 'null'},
            {'field_en': 'sczt_ylfw', 'field_cn': '医疗服务状态', 'db_type': 'varchar(1)', 'constraint': 'null'}
        ]

    # 大小写格式应用到所有关键字和系统对象
    KW_IF = 'IF' if case_style == 'upper' else 'if'
    KW_NOT = 'NOT' if case_style == 'upper' else 'not'
    KW_EXISTS = 'EXISTS' if case_style == 'upper' else 'exists'
    KW_CREATE = 'CREATE' if case_style == 'upper' else 'create'
    KW_TABLE = 'TABLE' if case_style == 'upper' else 'table'
    KW_CONSTRAINT = 'CONSTRAINT' if case_style == 'upper' else 'constraint'
    KW_PRIMARY = 'PRIMARY' if case_style == 'upper' else 'primary'
    KW_KEY = 'KEY' if case_style == 'upper' else 'key'
    KW_GO = 'GO' if case_style == 'upper' else 'go'
    KW_SELECT = 'SELECT' if case_style == 'upper' else 'select'
    KW_FROM = 'FROM' if case_style == 'upper' else 'from'
    KW_WHERE = 'WHERE' if case_style == 'upper' else 'where'
    KW_NAME = 'NAME' if case_style == 'upper' else 'name'
    SYS_TABLES = 'SYS.TABLES' if case_style == 'upper' else 'sys.tables'

    # 主键约束
    pk_constraint = ''
    if primary_keys and len(primary_keys) > 0:
        pk_fields = [apply_case(pk, case_style) for pk in primary_keys]
        pk_constraint = f',\n    {KW_CONSTRAINT} PK_{table_name} {KW_PRIMARY} {KW_KEY} (' + ', '.join(pk_fields) + ')'

    # 构建字段列表
    def build_field_lines(fields_list, add_null=True):
        lines = []
        for f in fields_list:
            field_name = apply_case(f['field_en'], case_style)
            db_type = f['db_type'].upper() if case_style == 'upper' else f['db_type'].lower()
            constraint = f['constraint'] if f['constraint'] else ('null' if add_null else '')
            # constraint也需要大小写处理
            if case_style == 'upper':
                constraint = constraint.upper()
            elif case_style == 'lower':
                constraint = constraint.lower()
            lines.append(f"    {field_name} {db_type} {constraint}")
        return lines

    field_lines_main = build_field_lines(fields)
    for pf in public_fields_main:
        field_name = apply_case(pf['field_en'], case_style)
        db_type = pf['db_type'].upper() if case_style == 'upper' else pf['db_type'].lower()
        constraint = pf['constraint'].upper() if case_style == 'upper' else pf['constraint'].lower()
        field_lines_main.append(f"    {field_name} {db_type} {constraint}")

    field_lines_sync = build_field_lines(fields, add_null=True)
    for pf in public_fields_main:
        field_name = apply_case(pf['field_en'], case_style)
        db_type = pf['db_type'].upper() if case_style == 'upper' else pf['db_type'].lower()
        constraint = pf['constraint'].upper() if case_style == 'upper' else pf['constraint'].lower()
        field_lines_sync.append(f"    {field_name} {db_type} {constraint}")

    fields_main_str = ',\n'.join(field_lines_main)
    fields_sync_str = ',\n'.join(field_lines_sync)

    ddl = f"-- 新增表：{table_cn}[{table_en}]\n"

    # 主表
    ddl += f"{KW_IF} {KW_NOT} {KW_EXISTS} ({KW_SELECT} * {KW_FROM} {SYS_TABLES} {KW_WHERE} {KW_NAME} = '{table_name}')\n"
    ddl += f"{KW_CREATE} {KW_TABLE} {table_name} (\n"
    ddl += fields_main_str + pk_constraint + "\n"
    ddl += ");\n"
    ddl += f"{KW_GO}\n\n"

    # TRAN表和LOG表 - 仅在include_tran_log=True时生成
    if include_tran_log:
        ddl += f"{KW_IF} {KW_NOT} {KW_EXISTS} ({KW_SELECT} * {KW_FROM} {SYS_TABLES} {KW_WHERE} {KW_NAME} = '{tran_name}')\n"
        ddl += f"{KW_CREATE} {KW_TABLE} {tran_name} (\n"
        ddl += fields_sync_str + "\n"
        ddl += ");\n"
        ddl += f"{KW_GO}\n\n"

        ddl += f"{KW_IF} {KW_NOT} {KW_EXISTS} ({KW_SELECT} * {KW_FROM} {SYS_TABLES} {KW_WHERE} {KW_NAME} = '{log_name}')\n"
        ddl += f"{KW_CREATE} {KW_TABLE} {log_name} (\n"
        ddl += fields_sync_str + "\n"
        ddl += ");\n"
        ddl += f"{KW_GO}\n\n"

    return ddl

def generate_sqlserver_add_field_ddl(table_en, table_cn, field_en, field_cn, db_type, constraint, case_style):
    """生成SQL Server新增字段DDL（单个字段，保留向后兼容）

    v4.2.0 更新：
    - 两层判断：先判断表是否存在，再判断字段是否存在
    - 大小写格式应用到所有字符
    - 加GO分隔符
    """
    table_name = apply_case(table_en, case_style)
    field_name = apply_case(field_en, case_style)

    # 清理表名和字段名中的不可见字符（用于注释）
    table_cn_clean = clean_invisible_chars(table_cn)
    field_cn_clean = clean_invisible_chars(field_cn)

    # 大小写格式应用到所有关键字和系统对象
    KW_IF = 'IF' if case_style == 'upper' else 'if'
    KW_EXISTS = 'EXISTS' if case_style == 'upper' else 'exists'
    KW_NOT = 'NOT' if case_style == 'upper' else 'not'
    KW_BEGIN = 'BEGIN' if case_style == 'upper' else 'begin'
    KW_END = 'END' if case_style == 'upper' else 'end'
    KW_ALTER = 'ALTER' if case_style == 'upper' else 'alter'
    KW_TABLE = 'TABLE' if case_style == 'upper' else 'table'
    KW_ADD = 'ADD' if case_style == 'upper' else 'add'
    KW_NULL = 'NULL' if case_style == 'upper' else 'null'
    KW_GO = 'GO' if case_style == 'upper' else 'go'
    KW_SELECT = 'SELECT' if case_style == 'upper' else 'select'
    KW_FROM = 'FROM' if case_style == 'upper' else 'from'
    KW_WHERE = 'WHERE' if case_style == 'upper' else 'where'
    KW_AND = 'AND' if case_style == 'upper' else 'and'
    KW_NAME = 'NAME' if case_style == 'upper' else 'name'
    KW_OBJECT_ID = 'OBJECT_ID' if case_style == 'upper' else 'object_id'
    SYS_TABLES = 'SYS.TABLES' if case_style == 'upper' else 'sys.tables'
    SYS_COLUMNS = 'SYS.COLUMNS' if case_style == 'upper' else 'sys.columns'

    # 数据类型和约束大小写处理
    db_type_case = db_type.upper() if case_style == 'upper' else db_type.lower()
    constraint_case = constraint.upper() if case_style == 'upper' else constraint.lower()

    ddl = f"-- {table_cn_clean}[{table_en}] 新增字段 {field_cn_clean}\n"
    ddl += f"{KW_IF} {KW_EXISTS} ({KW_SELECT} * {KW_FROM} {SYS_TABLES} {KW_WHERE} {KW_NAME} = '{table_name}')\n"
    ddl += f"{KW_BEGIN}\n"
    ddl += f"    {KW_IF} {KW_NOT} {KW_EXISTS} ({KW_SELECT} * {KW_FROM} {SYS_COLUMNS} {KW_WHERE} {KW_OBJECT_ID} = {KW_OBJECT_ID}('{table_name}') {KW_AND} {KW_NAME} = '{field_name}')\n"
    ddl += f"        {KW_ALTER} {KW_TABLE} {table_name} {KW_ADD} {field_name} {db_type_case} {constraint_case};\n"
    ddl += f"{KW_END}\n"
    ddl += f"{KW_GO}\n\n"

    return ddl

def generate_sqlserver_combined_field_ddl(table_en, table_cn, fields, case_style, include_tran_log=True):
    """生成SQL Server多字段合并DDL

    v4.2.0 更新：
    - 两层判断：先判断表是否存在，再判断字段是否存在
    - 大小写格式应用到所有字符（SQL关键字、数据类型、表名、字段名）
    - 同一行同一个语句不换行，保持紧凑
    - 每个表（原表、TRAN、LOG）更新完后加GO分隔符
    - 系统表查询使用SYS.TABLES和SYS.COLUMNS

    参数:
        include_tran_log: 是否生成TRAN/LOG关联表同步（默认True）
    """
    table_name = apply_case(table_en, case_style)
    tran_name = table_name + '_TRAN' if case_style == 'upper' else table_name + '_tran'
    log_name = table_name + '_LOG' if case_style == 'upper' else table_name + '_log'

    # 清理表名中的不可见字符
    table_cn = clean_invisible_chars(table_cn)
    table_en = clean_invisible_chars(table_en)

    # 大小写格式应用到所有关键字和系统对象
    KW_IF = 'IF' if case_style == 'upper' else 'if'
    KW_EXISTS = 'EXISTS' if case_style == 'upper' else 'exists'
    KW_NOT = 'NOT' if case_style == 'upper' else 'not'
    KW_SELECT = 'SELECT' if case_style == 'upper' else 'select'
    KW_FROM = 'FROM' if case_style == 'upper' else 'from'
    KW_WHERE = 'WHERE' if case_style == 'upper' else 'where'
    KW_AND = 'AND' if case_style == 'upper' else 'and'
    KW_BEGIN = 'BEGIN' if case_style == 'upper' else 'begin'
    KW_END = 'END' if case_style == 'upper' else 'end'
    KW_ALTER = 'ALTER' if case_style == 'upper' else 'alter'
    KW_TABLE = 'TABLE' if case_style == 'upper' else 'table'
    KW_ADD = 'ADD' if case_style == 'upper' else 'add'
    KW_NULL = 'NULL' if case_style == 'upper' else 'null'
    KW_GO = 'GO' if case_style == 'upper' else 'go'
    KW_NAME = 'NAME' if case_style == 'upper' else 'name'
    KW_OBJECT_ID = 'OBJECT_ID' if case_style == 'upper' else 'object_id'
    SYS_TABLES = 'SYS.TABLES' if case_style == 'upper' else 'sys.tables'
    SYS_COLUMNS = 'SYS.COLUMNS' if case_style == 'upper' else 'sys.columns'

    # 开始生成DDL - 构建字段描述
    field_desc_parts = []
    for f in fields:
        field_cn = clean_invisible_chars(f['field_cn'])
        field_en = clean_invisible_chars(f['field_en'])
        type_str = _build_field_type_str(f['data_type'], f['length'])
        required_cn = clean_invisible_chars(f['required_cn'])
        field_desc_parts.append(f"{field_cn}[{field_en},{type_str},{required_cn}]")
    field_desc = '、'.join(field_desc_parts)

    ddl = f"-- {table_cn}[{table_en}]新增字段：{field_desc}\n"

    # 主表新增字段（两层判断：表存在 + 字段不存在）
    ddl += f"{KW_IF} {KW_EXISTS} ({KW_SELECT} * {KW_FROM} {SYS_TABLES} {KW_WHERE} {KW_NAME} = '{table_name}')\n"
    ddl += f"{KW_BEGIN}\n"
    for f in fields:
        field_name = apply_case(f['field_en'], case_style)
        db_type = f['db_type'].upper() if case_style == 'upper' else f['db_type'].lower()
        ddl += f"    {KW_IF} {KW_NOT} {KW_EXISTS} ({KW_SELECT} * {KW_FROM} {SYS_COLUMNS} {KW_WHERE} {KW_OBJECT_ID} = {KW_OBJECT_ID}('{table_name}') {KW_AND} {KW_NAME} = '{field_name}')\n"
        ddl += f"        {KW_ALTER} {KW_TABLE} {table_name} {KW_ADD} {field_name} {db_type} {KW_NULL};\n"
    ddl += f"{KW_END}\n"
    ddl += f"{KW_GO}\n\n"

    # TRAN表同步
    if include_tran_log:
        ddl += f"{KW_IF} {KW_EXISTS} ({KW_SELECT} * {KW_FROM} {SYS_TABLES} {KW_WHERE} {KW_NAME} = '{tran_name}')\n"
        ddl += f"{KW_BEGIN}\n"
        for f in fields:
            field_name = apply_case(f['field_en'], case_style)
            db_type = f['db_type'].upper() if case_style == 'upper' else f['db_type'].lower()
            ddl += f"    {KW_IF} {KW_NOT} {KW_EXISTS} ({KW_SELECT} * {KW_FROM} {SYS_COLUMNS} {KW_WHERE} {KW_OBJECT_ID} = {KW_OBJECT_ID}('{tran_name}') {KW_AND} {KW_NAME} = '{field_name}')\n"
            ddl += f"        {KW_ALTER} {KW_TABLE} {tran_name} {KW_ADD} {field_name} {db_type} {KW_NULL};\n"
        ddl += f"{KW_END}\n"
        ddl += f"{KW_GO}\n\n"

        # LOG表同步
        ddl += f"{KW_IF} {KW_EXISTS} ({KW_SELECT} * {KW_FROM} {SYS_TABLES} {KW_WHERE} {KW_NAME} = '{log_name}')\n"
        ddl += f"{KW_BEGIN}\n"
        for f in fields:
            field_name = apply_case(f['field_en'], case_style)
            db_type = f['db_type'].upper() if case_style == 'upper' else f['db_type'].lower()
            ddl += f"    {KW_IF} {KW_NOT} {KW_EXISTS} ({KW_SELECT} * {KW_FROM} {SYS_COLUMNS} {KW_WHERE} {KW_OBJECT_ID} = {KW_OBJECT_ID}('{log_name}') {KW_AND} {KW_NAME} = '{field_name}')\n"
            ddl += f"        {KW_ALTER} {KW_TABLE} {log_name} {KW_ADD} {field_name} {db_type} {KW_NULL};\n"
        ddl += f"{KW_END}\n"
        ddl += f"{KW_GO}\n\n"

    return ddl

def generate_sqlserver_sync_ddl(sync_table, table_cn, field_en, field_cn, db_type, case_style):
    """生成SQL Server关联表同步DDL

    v4.2.0 更新：
    - 两层判断：先判断表是否存在，再判断字段是否存在
    - 大小写格式应用到所有字符
    - 加GO分隔符
    """
    table_name = apply_case(sync_table, case_style)
    field_name = apply_case(field_en, case_style)

    # 大小写格式应用到所有关键字和系统对象
    KW_IF = 'IF' if case_style == 'upper' else 'if'
    KW_EXISTS = 'EXISTS' if case_style == 'upper' else 'exists'
    KW_NOT = 'NOT' if case_style == 'upper' else 'not'
    KW_BEGIN = 'BEGIN' if case_style == 'upper' else 'begin'
    KW_END = 'END' if case_style == 'upper' else 'end'
    KW_ALTER = 'ALTER' if case_style == 'upper' else 'alter'
    KW_TABLE = 'TABLE' if case_style == 'upper' else 'table'
    KW_ADD = 'ADD' if case_style == 'upper' else 'add'
    KW_NULL = 'NULL' if case_style == 'upper' else 'null'
    KW_GO = 'GO' if case_style == 'upper' else 'go'
    KW_SELECT = 'SELECT' if case_style == 'upper' else 'select'
    KW_FROM = 'FROM' if case_style == 'upper' else 'from'
    KW_WHERE = 'WHERE' if case_style == 'upper' else 'where'
    KW_AND = 'AND' if case_style == 'upper' else 'and'
    KW_NAME = 'NAME' if case_style == 'upper' else 'name'
    KW_OBJECT_ID = 'OBJECT_ID' if case_style == 'upper' else 'object_id'
    SYS_TABLES = 'SYS.TABLES' if case_style == 'upper' else 'sys.tables'
    SYS_COLUMNS = 'SYS.COLUMNS' if case_style == 'upper' else 'sys.columns'

    # 数据类型大小写处理
    db_type_case = db_type.upper() if case_style == 'upper' else db_type.lower()

    ddl = f"-- {table_cn}[{table_name}] 同步新增字段 {field_cn}\n"
    ddl += f"{KW_IF} {KW_EXISTS} ({KW_SELECT} * {KW_FROM} {SYS_TABLES} {KW_WHERE} {KW_NAME} = '{table_name}')\n"
    ddl += f"{KW_BEGIN}\n"
    ddl += f"    {KW_IF} {KW_NOT} {KW_EXISTS} ({KW_SELECT} * {KW_FROM} {SYS_COLUMNS} {KW_WHERE} {KW_OBJECT_ID} = {KW_OBJECT_ID}('{table_name}') {KW_AND} {KW_NAME} = '{field_name}')\n"
    ddl += f"        {KW_ALTER} {KW_TABLE} {table_name} {KW_ADD} {field_name} {db_type_case} {KW_NULL};\n"
    ddl += f"{KW_END}\n"
    ddl += f"{KW_GO}\n\n"

    return ddl

def generate_postgresql_new_table_ddl(table_en, table_cn, fields, case_style, primary_keys=None, include_tran_log=True, include_public_fields=True):
    """生成PostgreSQL新增表DDL（主表+TRAN+LOG合并到一个do块）

    参数:
        include_tran_log: 是否生成TRAN/LOG关联表（默认True）
        include_public_fields: 是否添加sczt公共字段（默认True）
    """
    table_name = apply_case(table_en, case_style)
    tran_name = table_name + '_tran'
    log_name = table_name + '_log'

    # 公共字段 - 仅在include_public_fields=True时添加
    public_fields_main = []
    if include_public_fields:
        public_fields_main = [
            {'field_en': 'sczt', 'field_cn': '创建状态', 'db_type': 'varchar(1)', 'constraint': "default '0' not null"},
            {'field_en': 'sczt_index', 'field_cn': '索引状态', 'db_type': 'varchar(1)', 'constraint': 'null'},
            {'field_en': 'sczt_ggws', 'field_cn': '公共卫生状态', 'db_type': 'varchar(1)', 'constraint': 'null'},
            {'field_en': 'sczt_ylfw', 'field_cn': '医疗服务状态', 'db_type': 'varchar(1)', 'constraint': 'null'}
        ]

    # 主键约束
    pk_constraint = ''
    if primary_keys and len(primary_keys) > 0:
        pk_fields = [apply_case(pk, case_style) for pk in primary_keys]
        pk_constraint = ',\n            constraint pk_' + table_name + ' primary key (' + ', '.join(pk_fields) + ')'

    # 构建字段列表
    def build_field_lines(fields_list, add_null=True):
        lines = []
        for f in fields_list:
            field_name = apply_case(f['field_en'], case_style)
            db_type = f['db_type']
            constraint = f['constraint'] if f['constraint'] else ('null' if add_null else '')
            lines.append("            " + field_name + " " + db_type + " " + constraint)
        return lines

    field_lines_main = build_field_lines(fields)
    for pf in public_fields_main:
        field_name = apply_case(pf['field_en'], case_style)
        field_lines_main.append("            " + field_name + " " + pf['db_type'] + " " + pf['constraint'])

    field_lines_sync = build_field_lines(fields, add_null=True)
    for pf in public_fields_main:
        field_name = apply_case(pf['field_en'], case_style)
        field_lines_sync.append("            " + field_name + " " + pf['db_type'] + " " + pf['constraint'])

    fields_main_str = ',\n'.join(field_lines_main)
    fields_sync_str = ',\n'.join(field_lines_sync)

    ddl = "-- 新增表：" + table_cn + "[" + table_en + "]\n"
    ddl += "do $$\n"
    ddl += "begin\n"

    # 主表
    ddl += "    if not exists (select 1 from information_schema.tables where table_name = '" + table_name + "') then\n"
    ddl += "        create table " + table_name + " (\n"
    ddl += fields_main_str + pk_constraint + "\n"
    ddl += "        );\n"
    ddl += "        comment on table " + table_name + " is '" + table_cn + "';\n"
    # 字段注释格式: 字段名,备注
    for f in fields:
        field_name = apply_case(f['field_en'], case_style)  # apply_case 已包含清理
        # 清理注释中的不可见字符
        field_cn = clean_invisible_chars(f['field_cn'])
        description = clean_invisible_chars(f.get('description', ''))[:100] if f.get('description') else ''
        comment_text = field_cn + '，' + description
        ddl += "        comment on column " + table_name + "." + field_name + " is '" + comment_text + "';\n"
    for pf in public_fields_main:
        field_name = apply_case(pf['field_en'], case_style)
        ddl += "        comment on column " + table_name + "." + field_name + " is '" + pf['field_cn'] + "';\n"
    ddl += "    end if;\n"

    # TRAN表和LOG表 - 仅在include_tran_log=True时生成
    if include_tran_log:
        ddl += "    if not exists (select 1 from information_schema.tables where table_name = '" + tran_name + "') then\n"
        ddl += "        create table " + tran_name + " (\n"
        ddl += fields_sync_str + "\n"
        ddl += "        );\n"
        ddl += "        comment on table " + tran_name + " is '" + table_cn + "_事务';\n"
        for f in fields:
            field_name = apply_case(f['field_en'], case_style)
            comment_text = f['field_cn'] + '，' + (f.get('description', '')[:100] if f.get('description') else '')
            ddl += "        comment on column " + tran_name + "." + field_name + " is '" + comment_text + "';\n"
        for pf in public_fields_main:
            field_name = apply_case(pf['field_en'], case_style)
            ddl += "        comment on column " + tran_name + "." + field_name + " is '" + pf['field_cn'] + "';\n"
        ddl += "    end if;\n"

        ddl += "    if not exists (select 1 from information_schema.tables where table_name = '" + log_name + "') then\n"
        ddl += "        create table " + log_name + " (\n"
        ddl += fields_sync_str + "\n"
        ddl += "        );\n"
        ddl += "        comment on table " + log_name + " is '" + table_cn + "_日志';\n"
        for f in fields:
            field_name = apply_case(f['field_en'], case_style)
            comment_text = f['field_cn'] + '，' + (f.get('description', '')[:100] if f.get('description') else '')
            ddl += "        comment on column " + log_name + "." + field_name + " is '" + comment_text + "';\n"
        for pf in public_fields_main:
            field_name = apply_case(pf['field_en'], case_style)
            ddl += "        comment on column " + log_name + "." + field_name + " is '" + pf['field_cn'] + "';\n"
        ddl += "    end if;\n"

    ddl += "end $$;\n\n"

    return ddl

def generate_postgresql_add_field_ddl(table_en, table_cn, field_en, field_cn, db_type, constraint, case_style):
    """生成PostgreSQL新增字段DDL（单个字段，保留向后兼容）"""
    table_name = apply_case(table_en, case_style)
    field_name = apply_case(field_en, case_style)

    # 清理表名和字段名中的不可见字符（用于注释）
    table_cn_clean = clean_invisible_chars(table_cn)
    field_cn_clean = clean_invisible_chars(field_cn)

    ddl = f"""-- {table_cn_clean}[{table_en}] 新增字段 {field_cn_clean}
do $$\nbegin
    if not exists (select 1 from information_schema.columns
                   where table_name = '{table_name}' and column_name = '{field_name}') then
        alter table {table_name} add column {field_name} {db_type} {constraint};
        comment on column {table_name}.{field_name} is '{field_cn_clean}';
    end if;
end $$;
"""
    return ddl

def generate_postgresql_combined_field_ddl(table_en, table_cn, fields, case_style, include_tran_log=True):
    """生成PostgreSQL多字段合并DDL

    v3.2.0 更新：
    - 同一张表多个字段放到一个 do 块
    - TRAN/LOG 也放入同一个 do 块
    - 先判断表是否存在，再判断字段是否存在
    - 内容区域不加注释，只在脚本块前写简单描述
    - 大小写格式应用到所有字符

    参数:
        include_tran_log: 是否生成TRAN/LOG关联表同步（默认True）
    """
    table_name = apply_case(table_en, case_style)
    tran_name = table_name + '_TRAN' if case_style == 'upper' else table_name + '_tran'
    log_name = table_name + '_LOG' if case_style == 'upper' else table_name + '_log'

    # 清理表名中的不可见字符
    table_cn = clean_invisible_chars(table_cn)
    table_en = clean_invisible_chars(table_en)

    # 大小写格式应用到关键字
    KW_DO = 'DO' if case_style == 'upper' else 'do'
    KW_BEGIN = 'BEGIN' if case_style == 'upper' else 'begin'
    KW_END = 'END' if case_style == 'upper' else 'end'
    KW_IF = 'IF' if case_style == 'upper' else 'if'
    KW_THEN = 'THEN' if case_style == 'upper' else 'then'
    KW_EXISTS = 'EXISTS' if case_style == 'upper' else 'exists'
    KW_NOT = 'NOT' if case_style == 'upper' else 'not'

    # 开始生成DDL
    ddl = f"-- {table_cn}[{table_en}]新增字段\n"
    ddl += f"{KW_DO} $$\n"
    ddl += f"{KW_BEGIN}\n"

    # 主表检查和字段添加
    ddl += f"    {KW_IF} {KW_EXISTS} (select 1 from information_schema.tables where table_name = '{table_name}') {KW_THEN}\n"
    for f in fields:
        field_name = apply_case(f['field_en'], case_style)
        db_type = f['db_type'].upper() if case_style == 'upper' else f['db_type'].lower()
        field_cn = clean_invisible_chars(f['field_cn'])
        ddl += f"        {KW_IF} {KW_NOT} {KW_EXISTS} (select 1 from information_schema.columns where table_name = '{table_name}' and column_name = '{field_name}') {KW_THEN}\n"
        ddl += f"            alter table {table_name} add column {field_name} {db_type} null;\n"
        ddl += f"            comment on column {table_name}.{field_name} is '{field_cn}';\n"
        ddl += f"        {KW_END} {KW_IF};\n"
    ddl += f"    {KW_END} {KW_IF};\n"

    # TRAN表同步
    if include_tran_log:
        ddl += f"    {KW_IF} {KW_EXISTS} (select 1 from information_schema.tables where table_name = '{tran_name}') {KW_THEN}\n"
        for f in fields:
            field_name = apply_case(f['field_en'], case_style)
            db_type = f['db_type'].upper() if case_style == 'upper' else f['db_type'].lower()
            ddl += f"        {KW_IF} {KW_NOT} {KW_EXISTS} (select 1 from information_schema.columns where table_name = '{tran_name}' and column_name = '{field_name}') {KW_THEN}\n"
            ddl += f"            alter table {tran_name} add column {field_name} {db_type} null;\n"
            ddl += f"        {KW_END} {KW_IF};\n"
        ddl += f"    {KW_END} {KW_IF};\n"

        # LOG表同步
        ddl += f"    {KW_IF} {KW_EXISTS} (select 1 from information_schema.tables where table_name = '{log_name}') {KW_THEN}\n"
        for f in fields:
            field_name = apply_case(f['field_en'], case_style)
            db_type = f['db_type'].upper() if case_style == 'upper' else f['db_type'].lower()
            ddl += f"        {KW_IF} {KW_NOT} {KW_EXISTS} (select 1 from information_schema.columns where table_name = '{log_name}' and column_name = '{field_name}') {KW_THEN}\n"
            ddl += f"            alter table {log_name} add column {field_name} {db_type} null;\n"
            ddl += f"        {KW_END} {KW_IF};\n"
        ddl += f"    {KW_END} {KW_IF};\n"

    ddl += f"{KW_END} $$;\n\n"

    return ddl

def generate_postgresql_sync_ddl(sync_table, table_cn, field_en, field_cn, db_type, case_style):
    """生成PostgreSQL关联表同步DDL"""
    table_name = apply_case(sync_table, case_style)
    field_name = apply_case(field_en, case_style)

    ddl = f"""-- {table_cn}[{table_name}] 同步新增字段 {field_cn}
do $$
begin
    if not exists (select 1 from information_schema.columns
                   where table_name = '{table_name}' and column_name = '{field_name}') then
        alter table {table_name} add column {field_name} {db_type};
    end if;
end $$;
"""
    return ddl

# ========== 修改字段DDL生成函数 ==========

def generate_oracle_modify_field_ddl(table_en, table_cn, field_en, field_cn, db_type, constraint, case_style, has_constraint_change, has_format_change, required_value=None, format_value=None, include_tran_log=True):
    """生成Oracle修改字段DDL

    v4.3.6 更新：
    - 支持TRAN/LOG表同步
    - 简化注释格式（与SQL Server一致，去掉分隔线和内容区域注释）
    - 同一行SQL不换行
    - 大小写格式应用到所有字符

    参数:
        has_constraint_change: 是否修改约束（必填属性）
        has_format_change: 是否修改表示格式（类型/长度）
        required_value: 约束列的值（M/O）
        format_value: 表示格式列的值（AN..100等）
        include_tran_log: 是否生成TRAN/LOG关联表同步（默认True）
    """
    table_name = apply_case(table_en, case_style)
    tran_name = table_name + '_TRAN' if case_style == 'upper' else table_name + '_tran'
    log_name = table_name + '_LOG' if case_style == 'upper' else table_name + '_log'
    field_name = apply_case(field_en, case_style)

    table_cn_clean = clean_invisible_chars(table_cn)
    field_cn_clean = clean_invisible_chars(field_cn)
    table_en_clean = clean_invisible_chars(table_en)
    field_en_clean = clean_invisible_chars(field_en)

    # 如果没有DDL变更，返回空（只生成注释）
    if not has_constraint_change and not has_format_change:
        return ''

    # 构建修改属性描述
    attrs = []
    if has_constraint_change:
        if required_value:
            attrs.append(f'字段约束修改为"{required_value}"')
        else:
            attrs.append('字段约束修改为""')
    if has_format_change:
        if format_value:
            attrs.append(f'表示格式修改为"{format_value}"')
        else:
            attrs.append('表示格式修改为""')
    attrs_str = '，'.join(attrs)

    # 大小写格式应用到所有关键字
    KW_DECLARE = 'DECLARE' if case_style == 'upper' else 'declare'
    KW_BEGIN = 'BEGIN' if case_style == 'upper' else 'begin'
    KW_END = 'END' if case_style == 'upper' else 'end'
    KW_IF = 'IF' if case_style == 'upper' else 'if'
    KW_THEN = 'THEN' if case_style == 'upper' else 'then'
    KW_SELECT = 'SELECT' if case_style == 'upper' else 'select'
    KW_COUNT = 'COUNT' if case_style == 'upper' else 'count'
    KW_INTO = 'INTO' if case_style == 'upper' else 'into'
    KW_FROM = 'FROM' if case_style == 'upper' else 'from'
    KW_WHERE = 'WHERE' if case_style == 'upper' else 'where'
    KW_AND = 'AND' if case_style == 'upper' else 'and'
    KW_UPPER = 'UPPER' if case_style == 'upper' else 'upper'
    KW_EXECUTE = 'EXECUTE' if case_style == 'upper' else 'execute'
    KW_IMMEDIATE = 'IMMEDIATE' if case_style == 'upper' else 'immediate'
    KW_ALTER = 'ALTER' if case_style == 'upper' else 'alter'
    KW_TABLE = 'TABLE' if case_style == 'upper' else 'table'
    KW_MODIFY = 'MODIFY' if case_style == 'upper' else 'modify'
    KW_NUMBER = 'NUMBER' if case_style == 'upper' else 'number'
    KW_V_COUNT = 'V_COUNT' if case_style == 'upper' else 'v_count'
    KW_USER_TAB_COLUMNS = 'USER_TAB_COLUMNS' if case_style == 'upper' else 'user_tab_columns'
    KW_TABLE_NAME = 'TABLE_NAME' if case_style == 'upper' else 'table_name'
    KW_COLUMN_NAME = 'COLUMN_NAME' if case_style == 'upper' else 'column_name'

    # 数据类型和约束大小写处理
    db_type_case = db_type.upper() if case_style == 'upper' else db_type.lower()
    constraint_case = constraint.upper() if case_style == 'upper' else constraint.lower()

    ddl = f"-- {table_cn_clean}[{table_en_clean}]{field_cn_clean}[{field_en_clean}]{attrs_str}\n"
    ddl += f"{KW_DECLARE}\n"
    ddl += f"    {KW_V_COUNT} {KW_NUMBER};\n"
    ddl += f"{KW_BEGIN}\n"

    # 主表修改字段
    ddl += f"    {KW_SELECT} {KW_COUNT}(*) {KW_INTO} {KW_V_COUNT} {KW_FROM} {KW_USER_TAB_COLUMNS} {KW_WHERE} {KW_TABLE_NAME} = {KW_UPPER}('{table_name}') {KW_AND} {KW_COLUMN_NAME} = {KW_UPPER}('{field_name}');\n"
    ddl += f"    {KW_IF} {KW_V_COUNT} > 0 {KW_THEN}\n"
    ddl += f"        {KW_EXECUTE} {KW_IMMEDIATE} '{KW_ALTER} {KW_TABLE} {table_name} {KW_MODIFY} {field_name} {db_type_case} {constraint_case}';\n"
    ddl += f"    {KW_END} {KW_IF};\n"

    # TRAN表同步
    if include_tran_log:
        ddl += f"    {KW_SELECT} {KW_COUNT}(*) {KW_INTO} {KW_V_COUNT} {KW_FROM} {KW_USER_TAB_COLUMNS} {KW_WHERE} {KW_TABLE_NAME} = {KW_UPPER}('{tran_name}') {KW_AND} {KW_COLUMN_NAME} = {KW_UPPER}('{field_name}');\n"
        ddl += f"    {KW_IF} {KW_V_COUNT} > 0 {KW_THEN}\n"
        ddl += f"        {KW_EXECUTE} {KW_IMMEDIATE} '{KW_ALTER} {KW_TABLE} {tran_name} {KW_MODIFY} {field_name} {db_type_case} {constraint_case}';\n"
        ddl += f"    {KW_END} {KW_IF};\n"

        # LOG表同步
        ddl += f"    {KW_SELECT} {KW_COUNT}(*) {KW_INTO} {KW_V_COUNT} {KW_FROM} {KW_USER_TAB_COLUMNS} {KW_WHERE} {KW_TABLE_NAME} = {KW_UPPER}('{log_name}') {KW_AND} {KW_COLUMN_NAME} = {KW_UPPER}('{field_name}');\n"
        ddl += f"    {KW_IF} {KW_V_COUNT} > 0 {KW_THEN}\n"
        ddl += f"        {KW_EXECUTE} {KW_IMMEDIATE} '{KW_ALTER} {KW_TABLE} {log_name} {KW_MODIFY} {field_name} {db_type_case} {constraint_case}';\n"
        ddl += f"    {KW_END} {KW_IF};\n"

    ddl += f"{KW_END};\n"
    ddl += "/\n\n"

    return ddl

def generate_mysql_modify_field_ddl(table_en, table_cn, field_en, field_cn, db_type, constraint, case_style, has_constraint_change, has_format_change, required_value=None, format_value=None):
    """生成MySQL修改字段DDL

    v2.4.3: 注释格式与修订记录一致
    """
    table_name = apply_case(table_en, case_style)
    field_name = apply_case(field_en, case_style)

    table_cn_clean = clean_invisible_chars(table_cn)
    field_cn_clean = clean_invisible_chars(field_cn)

    if not has_constraint_change and not has_format_change:
        return ''

    # v2.4.3: 使用新格式
    attrs = []
    if has_constraint_change:
        if required_value:
            attrs.append(f'字段约束修改为"{required_value}"')
        else:
            attrs.append('字段约束修改为""')
    if has_format_change:
        if format_value:
            attrs.append(f'表示格式修改为"{format_value}"')
        else:
            attrs.append('表示格式修改为""')
    attrs_str = '，'.join(attrs)

    ddl = f"""-- {table_cn_clean}[{table_en}]{field_cn_clean}[{field_en}]{attrs_str}
set @dbname = database();
set @tablename = '{table_name}';
set @columnname = '{field_name}';
set @preparedStatement = (select if(
  (select count(*) from information_schema.columns
   where table_schema = @dbname and table_name = @tablename and column_name = @columnname) > 0,
  concat('alter table ', @tablename, ' modify column {field_name} {db_type} {constraint} comment ''{field_cn_clean}'''),
  'select 1'
));
prepare alterIfExists from @preparedStatement;
execute alterIfExists;
deallocate prepare alterIfExists;
"""
    return ddl

def generate_sqlserver_modify_field_ddl(table_en, table_cn, field_en, field_cn, db_type, constraint, case_style, has_constraint_change, has_format_change, required_value=None, format_value=None, include_tran_log=True):
    """生成SQL Server修改字段DDL

    v4.3.6 更新：
    - 支持TRAN/LOG表同步
    - 每个表修改完后加GO分隔符

    参数:
        has_constraint_change: 是否修改约束（必填属性）
        has_format_change: 是否修改表示格式（类型/长度）
        required_value: 约束列的值（M/O）
        format_value: 表示格式列的值（AN..100等）
        include_tran_log: 是否生成TRAN/LOG关联表同步（默认True）
    """
    table_name = apply_case(table_en, case_style)
    tran_name = table_name + '_TRAN' if case_style == 'upper' else table_name + '_tran'
    log_name = table_name + '_LOG' if case_style == 'upper' else table_name + '_log'
    field_name = apply_case(field_en, case_style)

    table_cn_clean = clean_invisible_chars(table_cn)
    field_cn_clean = clean_invisible_chars(field_cn)
    table_en_clean = clean_invisible_chars(table_en)
    field_en_clean = clean_invisible_chars(field_en)

    if not has_constraint_change and not has_format_change:
        return ''

    # 大小写格式应用到所有关键字和系统对象
    KW_IF = 'IF' if case_style == 'upper' else 'if'
    KW_EXISTS = 'EXISTS' if case_style == 'upper' else 'exists'
    KW_BEGIN = 'BEGIN' if case_style == 'upper' else 'begin'
    KW_END = 'END' if case_style == 'upper' else 'end'
    KW_ALTER = 'ALTER' if case_style == 'upper' else 'alter'
    KW_TABLE = 'TABLE' if case_style == 'upper' else 'table'
    KW_COLUMN = 'COLUMN' if case_style == 'upper' else 'column'
    KW_NULL = 'NULL' if case_style == 'upper' else 'null'
    KW_NOT_NULL = 'NOT NULL' if case_style == 'upper' else 'not null'
    KW_GO = 'GO' if case_style == 'upper' else 'go'
    KW_SELECT = 'SELECT' if case_style == 'upper' else 'select'
    KW_FROM = 'FROM' if case_style == 'upper' else 'from'
    KW_WHERE = 'WHERE' if case_style == 'upper' else 'where'
    KW_AND = 'AND' if case_style == 'upper' else 'and'
    KW_NAME = 'NAME' if case_style == 'upper' else 'name'
    KW_OBJECT_ID = 'OBJECT_ID' if case_style == 'upper' else 'object_id'
    SYS_TABLES = 'SYS.TABLES' if case_style == 'upper' else 'sys.tables'
    SYS_COLUMNS = 'SYS.COLUMNS' if case_style == 'upper' else 'sys.columns'

    # 使用新格式
    attrs = []
    if has_constraint_change:
        if required_value:
            attrs.append(f'字段约束修改为"{required_value}"')
        else:
            attrs.append('字段约束修改为""')
    if has_format_change:
        if format_value:
            attrs.append(f'表示格式修改为"{format_value}"')
        else:
            attrs.append('表示格式修改为""')
    attrs_str = '，'.join(attrs)

    # 数据类型大小写处理
    db_type_case = db_type.upper() if case_style == 'upper' else db_type.lower()
    constraint_case = constraint.upper() if case_style == 'upper' else constraint.lower()

    ddl = f"-- {table_cn_clean}[{table_en_clean}]{field_cn_clean}[{field_en_clean}]{attrs_str}\n"

    # 主表修改字段
    ddl += f"{KW_IF} {KW_EXISTS} ({KW_SELECT} * {KW_FROM} {SYS_TABLES} {KW_WHERE} {KW_NAME} = '{table_name}')\n"
    ddl += f"{KW_BEGIN}\n"
    ddl += f"    {KW_IF} {KW_EXISTS} ({KW_SELECT} * {KW_FROM} {SYS_COLUMNS} {KW_WHERE} {KW_OBJECT_ID} = {KW_OBJECT_ID}('{table_name}') {KW_AND} {KW_NAME} = '{field_name}')\n"
    ddl += f"        {KW_ALTER} {KW_TABLE} {table_name} {KW_ALTER} {KW_COLUMN} {field_name} {db_type_case} {constraint_case};\n"
    ddl += f"{KW_END}\n"
    ddl += f"{KW_GO}\n"

    # TRAN表同步
    if include_tran_log:
        ddl += f"{KW_IF} {KW_EXISTS} ({KW_SELECT} * {KW_FROM} {SYS_TABLES} {KW_WHERE} {KW_NAME} = '{tran_name}')\n"
        ddl += f"{KW_BEGIN}\n"
        ddl += f"    {KW_IF} {KW_EXISTS} ({KW_SELECT} * {KW_FROM} {SYS_COLUMNS} {KW_WHERE} {KW_OBJECT_ID} = {KW_OBJECT_ID}('{tran_name}') {KW_AND} {KW_NAME} = '{field_name}')\n"
        ddl += f"        {KW_ALTER} {KW_TABLE} {tran_name} {KW_ALTER} {KW_COLUMN} {field_name} {db_type_case} {constraint_case};\n"
        ddl += f"{KW_END}\n"
        ddl += f"{KW_GO}\n"

        # LOG表同步
        ddl += f"{KW_IF} {KW_EXISTS} ({KW_SELECT} * {KW_FROM} {SYS_TABLES} {KW_WHERE} {KW_NAME} = '{log_name}')\n"
        ddl += f"{KW_BEGIN}\n"
        ddl += f"    {KW_IF} {KW_EXISTS} ({KW_SELECT} * {KW_FROM} {SYS_COLUMNS} {KW_WHERE} {KW_OBJECT_ID} = {KW_OBJECT_ID}('{log_name}') {KW_AND} {KW_NAME} = '{field_name}')\n"
        ddl += f"        {KW_ALTER} {KW_TABLE} {log_name} {KW_ALTER} {KW_COLUMN} {field_name} {db_type_case} {constraint_case};\n"
        ddl += f"{KW_END}\n"
        ddl += f"{KW_GO}\n"

    ddl += "\n"

    return ddl

def generate_postgresql_modify_field_ddl(table_en, table_cn, field_en, field_cn, db_type, constraint, case_style, has_constraint_change, has_format_change, required_value=None, format_value=None):
    """生成PostgreSQL修改字段DDL

    v2.4.3: 注释格式与修订记录一致
    """
    table_name = apply_case(table_en, case_style)
    field_name = apply_case(field_en, case_style)

    table_cn_clean = clean_invisible_chars(table_cn)
    field_cn_clean = clean_invisible_chars(field_cn)

    if not has_constraint_change and not has_format_change:
        return ''

    # v2.4.3: 使用新格式
    attrs = []
    if has_constraint_change:
        if required_value:
            attrs.append(f'字段约束修改为"{required_value}"')
        else:
            attrs.append('字段约束修改为""')
    if has_format_change:
        if format_value:
            attrs.append(f'表示格式修改为"{format_value}"')
        else:
            attrs.append('表示格式修改为""')
    attrs_str = '，'.join(attrs)

    ddl = f"""-- {table_cn_clean}[{table_en}]{field_cn_clean}[{field_en}]{attrs_str}
do $$
begin
    if exists (select 1 from information_schema.columns
               where table_name = '{table_name}' and column_name = '{field_name}') then
        alter table {table_name} alter column {field_name} type {db_type};
        {f"alter table {table_name} alter column {field_name} set not null;" if constraint == 'not null' else f"alter table {table_name} alter column {field_name} drop not null;" if constraint == 'null' else ''}
    end if;
end $$;
"""
    return ddl

def generate_revision_record_new_tables(new_tables):
    """生成新增表修订记录

    会自动清理表名中的不可见字符
    """
    records = []
    for nt in new_tables:
        # 清理不可见字符
        table_cn = clean_invisible_chars(nt['table_cn'])
        table_en = clean_invisible_chars(nt['table_en'])
        # 新增表：表名中文[表名]（使用原文格式，不受大小写选项约束）
        record = f"新增表：{table_cn}[{table_en}]"
        records.append(record)
    return records

def generate_revision_record_add_fields(all_changes):
    """生成新增字段修订记录（使用原文档类型，不转换）

    会自动清理表名、字段名中的不可见字符
    """
    records = []
    for change in all_changes:
        # 表名和字段名使用原文格式（不受大小写选项约束）
        # 清理不可见字符
        table_cn = clean_invisible_chars(change['table_cn'])
        table_en = clean_invisible_chars(change['table_en'])  # 原文格式
        fields = change['new_fields']

        field_strs = []
        for f in fields:
            # 清理不可见字符
            field_cn = clean_invisible_chars(f['field_cn'])
            field_en = clean_invisible_chars(f['field_en'])
            orig_type = clean_invisible_chars(f['data_type'])
            length = clean_invisible_chars(f['length']) if f['length'] else ''
            # 检查length是否为有效数值（数字、逗号、小数点），否则忽略
            is_valid_length = length and re.match(r'^[\d,\.\s]+$', length.strip())
            # 特殊处理：DATETIME/DATE/TIMESTAMP类型不需要长度
            no_length_types = ['DATETIME', 'DATE', 'TIMESTAMP', 'TEXT', 'CLOB', 'BLOB']
            if orig_type.upper() in no_length_types:
                type_str = orig_type
            elif is_valid_length:
                type_str = f"{orig_type}({length.strip()})"
            else:
                type_str = orig_type
            # 字段名使用原文格式，必填/应填使用原文
            required_cn = clean_invisible_chars(f['required_cn'])
            field_str = f"{field_cn}[{field_en},{type_str},{required_cn}]"
            field_strs.append(field_str)

        fields_line = '、'.join(field_strs)
        record = f"{table_cn}[{table_en}]新增字段：{fields_line}"
        records.append(record)
    return records

def generate_revision_record_modified_fields(modified_fields):
    """生成修改字段修订记录

    v2.4.3 修改：
    - 格式改为：表名中文[表名]字段名中文[字段名]字段约束修改为""，表示格式修改为""，说明修改为""
    - 每个修改属性单独列出，用引号包含变更内容（如有）
    - 约束使用M/O表示（与文档一致）
    - 各列显示实际修改后的内容（数据类型、表示格式、说明等）
    - 去除重复显示（data_type_category和data_type同时变红时只显示一次）

    会自动清理表名、字段名中的不可见字符
    """
    records = []
    for mod_table in modified_fields:
        table_cn = clean_invisible_chars(mod_table['table_cn'])
        table_en = clean_invisible_chars(mod_table['table_en'])
        fields = mod_table['modified_fields']

        for f in fields:
            field_cn = clean_invisible_chars(f['field_cn'])
            field_en = clean_invisible_chars(f['field_en'])

            # 构建修改属性列表（新格式）
            attrs = []
            if f['has_constraint_change']:
                # 约束变更：使用M/O表示（与文档一致）
                required_value = f.get('required_value', '')
                if required_value:
                    attrs.append(f'字段约束修改为"{required_value}"')
                else:
                    attrs.append('字段约束修改为""')
            if f['has_format_change']:
                # 表示格式变更：显示实际内容
                format_value = f.get('format_value', '')
                if format_value:
                    attrs.append(f'表示格式修改为"{format_value}"')
                else:
                    attrs.append('表示格式修改为""')
            if f['has_other_change']:
                # 其他变更列映射到中文属性名
                other_cols = [col for col in f['changed_columns'] if col not in ['required', 'format']]

                # v2.4.3: 去除重复显示
                # 如果data_type_category和data_type同时存在，只显示一次
                has_data_type_category = 'data_type_category' in other_cols
                has_data_type = 'data_type' in other_cols

                # 处理显示顺序
                displayed_attrs = []

                for col in other_cols:
                    if col == 'data_type_category' and has_data_type:
                        # 跳过data_type_category，由data_type统一显示
                        continue

                    col_name_map = {
                        'field_cn': '字段名称',
                        'comment': '说明',
                        'field_en': '字段标识',
                        'data_type_category': '数据类型',
                        'data_type': '数据类型'
                    }
                    col_value_map = {
                        'comment': f.get('comment', ''),
                        'data_type_category': f.get('data_type_category_value', ''),
                        'data_type': f.get('data_type_value', '')
                    }

                    attr_name = col_name_map.get(col, col)
                    # 显示实际内容
                    col_value = col_value_map.get(col, '')
                    if col_value:
                        # 截取前50字符，避免过长
                        displayed_attrs.append(f'{attr_name}修改为"{col_value[:50]}"')
                    else:
                        displayed_attrs.append(f'{attr_name}修改为""')

                attrs.extend(displayed_attrs)

            attrs_str = '，'.join(attrs) if attrs else '未知属性修改为""'
            record = f"{table_cn}[{table_en}]{field_cn}[{field_en}]{attrs_str}"
            records.append(record)

    return records

def generate_full_script(parse_result, db_type, case_style, doc_name, output_path, include_tran_log=True, include_public_fields=True):
    """生成完整DDL脚本并保存到文件（精简格式，合并多字段）

    v4.0.0 更新：支持全量模式
    - 全量模式下 parse_result['new_tables'] 包含所有表格
    - parse_result['all_changes'] 和 parse_result['modified_fields'] 为空
    - 只生成 CREATE TABLE DDL，不生成 ALTER TABLE DDL

    参数:
        parse_result: 解析结果（增量模式或全量模式）
        db_type: 数据库类型
        case_style: 大小写格式
        doc_name: 文档名称
        output_path: 输出路径
        include_tran_log: 是否生成TRAN/LOG关联表（默认True）
        include_public_fields: 是否添加sczt公共字段（默认True）
    """

    new_tables = parse_result['new_tables']
    all_changes = parse_result['all_changes']
    modified_fields = parse_result.get('modified_fields', [])

    ddl_count_new_tables = 0
    ddl_count_add_fields = 0
    ddl_count_modify_fields = 0
    ddl_count_sync = 0
    db_type_lower = db_type.lower()

    # 生成器映射
    new_table_generators = {
        'oracle': generate_oracle_new_table_ddl,
        'mysql': generate_mysql_new_table_ddl,
        'sqlserver': generate_sqlserver_new_table_ddl,
        'postgresql': generate_postgresql_new_table_ddl
    }
    add_field_generators = {
        'oracle': generate_oracle_add_field_ddl,
        'mysql': generate_mysql_add_field_ddl,
        'sqlserver': generate_sqlserver_add_field_ddl,
        'postgresql': generate_postgresql_add_field_ddl
    }
    sync_generators = {
        'oracle': generate_oracle_sync_ddl,
        'mysql': generate_mysql_sync_ddl,
        'sqlserver': generate_sqlserver_sync_ddl,
        'postgresql': generate_postgresql_sync_ddl
    }

    # 合并字段DDL生成器映射
    combined_field_generators = {
        'oracle': generate_oracle_combined_field_ddl,
        'mysql': generate_mysql_combined_field_ddl,
        'sqlserver': generate_sqlserver_combined_field_ddl,
        'postgresql': generate_postgresql_combined_field_ddl
    }

    # 修改字段DDL生成器映射
    modify_field_generators = {
        'oracle': generate_oracle_modify_field_ddl,
        'mysql': generate_mysql_modify_field_ddl,
        'sqlserver': generate_sqlserver_modify_field_ddl,
        'postgresql': generate_postgresql_modify_field_ddl
    }

    new_table_gen = new_table_generators.get(db_type_lower, generate_oracle_new_table_ddl)
    combined_field_gen = combined_field_generators.get(db_type_lower, generate_oracle_combined_field_ddl)
    modify_field_gen = modify_field_generators.get(db_type_lower, generate_oracle_modify_field_ddl)

    # 预处理：转换类型
    for nt in new_tables:
        for f in nt['fields']:
            f['db_type'] = map_type(f['data_type'], f['length'], db_type)

    for change in all_changes:
        for f in change['new_fields']:
            f['db_type'] = map_type(f['data_type'], f['length'], db_type)

    for mod_table in modified_fields:
        for f in mod_table['modified_fields']:
            f['db_type'] = map_type(f['data_type'], f['length'], db_type)

    with open(output_path, 'w', encoding='utf-8') as f:
        # v3.2.0: 直接生成修订记录注释，无文件头信息
        f.write("/*\n")

        # 新增表记录
        if new_tables:
            for record in generate_revision_record_new_tables(new_tables):
                f.write(record + "\n")

        # 新增字段记录
        for record in generate_revision_record_add_fields(all_changes):
            f.write(record + "\n")

        # 修改字段记录
        for record in generate_revision_record_modified_fields(modified_fields):
            f.write(record + "\n")

        f.write("*/\n\n")

        # ========== 新增表DDL（包含TRAN和LOG）==========
        if new_tables:
            for nt in new_tables:
                ddl_count_new_tables += 1
                primary_keys = nt.get('primary_keys', [])
                # 所有数据库都支持primary_keys参数，传递include_tran_log和include_public_fields
                ddl = new_table_gen(nt['table_en'], nt['table_cn'], nt['fields'], case_style, primary_keys, include_tran_log, include_public_fields)
                f.write(ddl)

        # ========== 新增字段DDL（合并多字段，包含TRAN/LOG同步）==========
        for change in all_changes:
            table_en = change['table_en']
            table_cn = change['table_cn']
            fields = change['new_fields']

            # 所有数据库都使用合并DDL（原表+TRAN+LOG合并到一个块）
            ddl_count_add_fields += len(fields)
            if include_tran_log:
                ddl_count_sync += len(fields) * 2  # TRAN和LOG
            # 传递 include_tran_log 参数
            ddl = combined_field_gen(table_en, table_cn, fields, case_style, include_tran_log)
            f.write(ddl)

        # ========== 修改字段DDL（只有约束和表示格式变更才生成）==========
        for mod_table in modified_fields:
            table_en = mod_table['table_en']
            table_cn = mod_table['table_cn']

            for mod_field in mod_table['modified_fields']:
                # 只有DDL变更才生成脚本
                if mod_field['has_ddl_change']:
                    field_en = mod_field['field_en']
                    field_cn = mod_field['field_cn']
                    db_type = mod_field['db_type']
                    constraint = mod_field['constraint']
                    has_constraint_change = mod_field['has_constraint_change']
                    has_format_change = mod_field['has_format_change']
                    # v2.4.3: 新增参数
                    required_value = mod_field.get('required_value', '')
                    format_value = mod_field.get('format_value', '')

                    ddl = modify_field_gen(table_en, table_cn, field_en, field_cn, db_type, constraint, case_style, has_constraint_change, has_format_change, required_value, format_value, include_tran_log)
                    if ddl:
                        f.write(ddl)
                        ddl_count_modify_fields += 1

        # 统计信息（根据用户选择动态显示）
        tran_log_suffix = "(含TRAN/LOG同步)" if include_tran_log else ""
        public_suffix = "(含公共字段)" if include_public_fields else ""
        f.write(f"-- 新增表: {len(new_tables)} 个 {tran_log_suffix}{public_suffix}\n")
        f.write(f"-- 新增字段: {ddl_count_add_fields} 个 {tran_log_suffix}\n")
        f.write(f"-- 修改字段: {ddl_count_modify_fields} 个\n")
        f.write(f"-- DDL总数: {ddl_count_new_tables + ddl_count_add_fields + ddl_count_modify_fields} 个\n")

    return {
        'output_path': output_path,
        'new_tables': len(new_tables),
        'field_count': ddl_count_add_fields,
        'modify_count': ddl_count_modify_fields,
        'sync_count': ddl_count_sync,
        'total_ddl': ddl_count_new_tables * 3 + ddl_count_add_fields + ddl_count_modify_fields
    }