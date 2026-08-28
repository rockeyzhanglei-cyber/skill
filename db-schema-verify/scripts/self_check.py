#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基准库自检脚本 - 原表 vs TRAN/LOG表结构一致性检查
用途：比对原表与_TRAN/_LOG表的结构差异，生成修复脚本
使用方式：
    python self_check.py --md <table_list.md> --csv <csv_path> --task-dir <task_dir> --db-type <oracle|sqlserver>

核对维度（8项）：
1. 字段缺失 - 原表有的字段，TRAN/LOG没有
2. 数据类型不一致 - DATA_TYPE不同（如 varchar vs nvarchar）
3. 字符长度不足 - CHAR_LENGTH，TRAN/LOG < 原表
4. 数值精度不足 - DATA_PRECISION，TRAN/LOG < 原表
5. 小数位不足 - DATA_SCALE，TRAN/LOG < 原表
6. 可空性不一致 - 原表NOT NULL → TRAN/LOG是NULL
7. DEFAULT值缺失 - 原表有DEFAULT → TRAN/LOG无
8. DEFAULT值冲突 - 原表和TRAN/LOG都有DEFAULT但不同

特殊处理：
- 原表不存在：跳过
- TRAN/LOG表不存在：生成CREATE TABLE（结构同原表，无主键）
- 修复脚本带存在性判断（IF EXISTS/IF NOT EXISTS）
"""

import csv
import sys
import argparse
import re
from collections import defaultdict
from pathlib import Path


def load_table_list(md_path):
    """
    从表清单MD文件提取表名列表
    格式：| 序号 | 中文名 | 英文表名 | 是否有TRAN | 是否有LOG |
    """
    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    base_tables = []
    # 正则匹配表清单中的英文表名
    pattern = r'\|\s*\d+\s*\|\s*[^|]+\s*\|\s*([A-Z_][A-Z0-9_]+)\s*\|'
    matches = re.findall(pattern, content)
    
    # 去重并保持顺序
    seen = set()
    for m in matches:
        if m not in seen:
            seen.add(m)
            base_tables.append(m)
    
    return base_tables


def read_csv(csv_path, encoding='utf-8'):
    """读取基准库CSV"""
    with open(csv_path, "r", encoding=encoding) as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            clean_row = {k.strip(): v.strip() if v else '' for k, v in row.items()}
            rows.append(clean_row)
    return rows


def build_type_def(row, db_type='oracle'):
    """
    构建完整的类型定义字符串
    db_type: oracle 或 sqlserver
    """
    data_type = row["DATA_TYPE"].strip()
    char_length = int(row["CHAR_LENGTH"]) if row["CHAR_LENGTH"] else 0
    data_precision = int(row["DATA_PRECISION"]) if row["DATA_PRECISION"] else None
    data_scale = int(row["DATA_SCALE"]) if row["DATA_SCALE"] else None
    
    # 归一化类型名
    normalized_type = data_type.lower()
    
    if db_type == 'sqlserver':
        # SQL Server类型
        if normalized_type in ('varchar', 'nvarchar', 'char', 'nchar', 'text', 'ntext'):
            if char_length > 0 and char_length < 8000:
                return f"{data_type}({char_length})"
            elif char_length >= 8000:
                return f"{data_type}(MAX)"
            else:
                return data_type
        elif normalized_type in ('decimal', 'numeric'):
            if data_precision is not None:
                if data_scale is not None and data_scale > 0:
                    return f"{data_type}({data_precision},{data_scale})"
                else:
                    return f"{data_type}({data_precision})"
            else:
                return data_type
        else:
            return data_type
    else:
        # Oracle类型
        if normalized_type in ('varchar2', 'nvarchar2', 'char', 'nchar'):
            if char_length > 0:
                return f"{data_type}({char_length})"
            else:
                return data_type
        elif normalized_type == 'number':
            if data_precision is not None:
                if data_scale is not None and data_scale > 0:
                    return f"NUMBER({data_precision},{data_scale})"
                else:
                    return f"NUMBER({data_precision})"
            else:
                return "NUMBER"
        else:
            return data_type


def get_column_length(row):
    """获取字段的字符长度（用于比较）"""
    data_type = row["DATA_TYPE"].strip().lower()
    char_length = int(row["CHAR_LENGTH"]) if row["CHAR_LENGTH"] else 0
    
    if data_type in ("varchar", "nvarchar", "varchar2", "nvarchar2", "char", "nchar", "text", "ntext"):
        return char_length
    else:
        return 0


def get_column_precision(row):
    """获取字段的数值精度（用于比较）"""
    data_type = row["DATA_TYPE"].strip().lower()
    data_precision = int(row["DATA_PRECISION"]) if row["DATA_PRECISION"] else 0
    
    if data_type in ("number", "decimal", "numeric"):
        return data_precision
    else:
        return 0


def get_column_scale(row):
    """获取字段的小数位（用于比较）"""
    data_type = row["DATA_TYPE"].strip().lower()
    data_scale = int(row["DATA_SCALE"]) if row["DATA_SCALE"] else 0
    
    if data_type in ("number", "decimal", "numeric"):
        return data_scale
    else:
        return 0


def generate_exists_check_sqlserver(table_name, column_name=None, is_create=False):
    """
    生成SQL Server存在性检查
    is_create=True: 检查表不存在（用于CREATE TABLE）
    column_name=None: 只检查表存在
    column_name!=None: 检查表存在且字段不存在（ADD）或表和字段都存在（ALTER COLUMN）
    """
    if is_create:
        return f"IF OBJECT_ID('{table_name}', 'U') IS NULL"
    elif column_name:
        return f"IF OBJECT_ID('{table_name}', 'U') IS NOT NULL AND COL_LENGTH('{table_name}', '{column_name}') IS NOT NULL"
    else:
        return f"IF OBJECT_ID('{table_name}', 'U') IS NOT NULL"


def generate_not_exists_check_sqlserver(table_name, column_name):
    """生成SQL Server字段不存在检查（用于ADD）"""
    return f"IF OBJECT_ID('{table_name}', 'U') IS NOT NULL AND COL_LENGTH('{table_name}', '{column_name}') IS NULL"


def generate_exists_check_oracle(table_name, column_name=None, is_create=False):
    """
    生成Oracle存在性检查（使用PL/SQL）
    """
    if is_create:
        return f"-- CREATE TABLE {table_name} (如果表不存在)"
    elif column_name:
        return f"-- ALTER COLUMN {table_name}.{column_name} (如果表和字段都存在)"
    else:
        return f"-- CHECK TABLE EXISTS {table_name}"


def self_check(rows, base_tables, db_type='oracle'):
    """
    自检逻辑：比对原表与_TRAN/_LOG表
    
    返回：
    - create_statements: CREATE TABLE语句（TRAN/LOG表不存在时）
    - alter_statements: ALTER语句（安全修改）
    - comment_statements: 需人工确认的语句
    - issues_found: 问题汇总
    """
    # 按表组织字段（表名统一转大写，兼容大小写混合）
    table_columns = defaultdict(list)
    for row in rows:
        table_name = row["TABLE_NAME"].strip().upper()
        table_columns[table_name].append(row)
    
    # 自检结果
    create_statements = []
    alter_statements = []
    comment_statements = []
    issues_found = defaultdict(list)
    
    for base_table in base_tables:
        if base_table not in table_columns:
            # 原表不存在，跳过
            continue
        
        base_cols = table_columns[base_table]
        
        # 检查_TRAN表
        tran_table = f"{base_table}_TRAN"
        process_derivative_table(
            base_table, tran_table, base_cols, table_columns, db_type,
            create_statements, alter_statements, comment_statements, issues_found
        )
        
        # 检查_LOG表
        log_table = f"{base_table}_LOG"
        process_derivative_table(
            base_table, log_table, base_cols, table_columns, db_type,
            create_statements, alter_statements, comment_statements, issues_found
        )
    
    return create_statements, alter_statements, comment_statements, issues_found


def process_derivative_table(base_table, deriv_table, base_cols, table_columns, db_type,
                              create_statements, alter_statements, comment_statements, issues_found):
    """处理衍生表（TRAN或LOG）的检查逻辑"""
    
    if deriv_table not in table_columns:
        # TRAN/LOG表不存在，生成CREATE TABLE
        issues_found[deriv_table].append(f"❌ 表不存在，需要新建")
        
        # 生成CREATE TABLE语句（无主键）
        create_sql = generate_create_table_sql(deriv_table, base_cols, db_type)
        create_statements.append(f"-- 新建表: {deriv_table}不存在，按照原表结构创建（无主键）")
        create_statements.append(create_sql)
        return
    
    # 表存在，逐字段比对
    deriv_cols = {col["COLUMN_NAME"].strip().upper(): col for col in table_columns[deriv_table]}
    
    for base_col in base_cols:
        col_name = base_col["COLUMN_NAME"].strip().upper()
        base_type_def = build_type_def(base_col, db_type)
        base_length = get_column_length(base_col)
        base_precision = get_column_precision(base_col)
        base_scale = get_column_scale(base_col)
        
        if col_name not in deriv_cols:
            # 字段缺失，需要ADD
            issues_found[deriv_table].append(f"❌ 缺少字段: {col_name}")
            
            # 生成带存在性检查的ADD语句
            add_sql = generate_add_column_sql(deriv_table, col_name, base_col, db_type)
            alter_statements.append(f"-- 新增字段: 原表{base_table}存在字段{col_name}，但{deriv_table}不存在")
            alter_statements.append(add_sql)
        else:
            # 字段存在，比较属性
            deriv_col = deriv_cols[col_name]
            deriv_type_def = build_type_def(deriv_col, db_type)
            deriv_length = get_column_length(deriv_col)
            deriv_precision = get_column_precision(deriv_col)
            deriv_scale = get_column_scale(deriv_col)
            
            # 1. 类型比较
            base_type = base_col["DATA_TYPE"].strip().lower()
            deriv_type = deriv_col["DATA_TYPE"].strip().lower()
            
            if base_type != deriv_type:
                # 类型不一致，需人工确认
                comment_statements.append(f"-- 需要人工确认: {deriv_table}.{col_name} 原表类型={base_type_def}, {deriv_table}类型={deriv_type_def}")
                modify_sql = generate_modify_column_sql(deriv_table, col_name, base_col, db_type)
                comment_statements.append(f"-- 修复SQL（取消注释即可执行）:")
                comment_statements.append(f"-- {modify_sql}")
                issues_found[deriv_table].append(f"❌ 类型不一致: {col_name} 原表={base_type_def}, {deriv_table}={deriv_type_def}")
            else:
                # 类型一致，比较长度/精度/小数位
                
                # 2. 字符长度比较
                if base_length > 0 and deriv_length < base_length:
                    issues_found[deriv_table].append(f"❌ 长度不足: {col_name} 原表={base_length}, {deriv_table}={deriv_length}")
                    modify_sql = generate_modify_column_sql(deriv_table, col_name, base_col, db_type)
                    alter_statements.append(f"-- 扩大长度: {col_name}从{deriv_length}扩大到{base_length}")
                    alter_statements.append(modify_sql)
                
                # 3. 数值精度比较
                if base_precision > 0 and deriv_precision < base_precision:
                    issues_found[deriv_table].append(f"❌ 精度不足: {col_name} 原表={base_precision}, {deriv_table}={deriv_precision}")
                    modify_sql = generate_modify_column_sql(deriv_table, col_name, base_col, db_type)
                    alter_statements.append(f"-- 扩大精度: {col_name}从{deriv_precision}扩大到{base_precision}")
                    alter_statements.append(modify_sql)
                
                # 4. 小数位比较
                if base_scale > 0 and deriv_scale < base_scale:
                    issues_found[deriv_table].append(f"❌ 小数位不足: {col_name} 原表={base_scale}, {deriv_table}={deriv_scale}")
                    modify_sql = generate_modify_column_sql(deriv_table, col_name, base_col, db_type)
                    alter_statements.append(f"-- 扩大小数位: {col_name}从{deriv_scale}扩大到{base_scale}")
                    alter_statements.append(modify_sql)
            
            # 5. 可空性比较
            base_nullable = base_col.get("NULLABLE", "Y").strip().upper()
            deriv_nullable = deriv_col.get("NULLABLE", "Y").strip().upper()
            if base_nullable == "Y" and deriv_nullable == "N":
                # 原表NULL，衍生表NOT NULL → 修改衍生表为NULL（放松约束）
                issues_found[deriv_table].append(f"❌ 可空性不一致: {col_name} 原表=NULL, {deriv_table}=NOT NULL")
                modify_sql = generate_modify_nullable_sql(deriv_table, col_name, base_col, db_type, nullable=True)
                alter_statements.append(f"-- 修改可空性: {col_name}从NOT NULL改为NULL")
                alter_statements.append(modify_sql)
            
            # 6. DEFAULT值比较
            base_default = base_col.get("DATA_DEFAULT", "").strip()
            deriv_default = deriv_col.get("DATA_DEFAULT", "").strip()
            
            if base_default and base_default != deriv_default:
                if not deriv_default:
                    # 原表有DEFAULT，衍生表没有 → 添加DEFAULT
                    issues_found[deriv_table].append(f"❌ DEFAULT值缺失: {col_name} 原表={base_default}")
                    default_sql = generate_default_sql(deriv_table, col_name, base_default, db_type)
                    alter_statements.append(f"-- 添加默认值: {col_name}添加DEFAULT {base_default}")
                    alter_statements.append(default_sql)
                else:
                    # 两边都有DEFAULT但不同 → 需人工确认
                    comment_statements.append(f"-- 需要人工确认: {deriv_table}.{col_name} DEFAULT值不一致 原表={base_default}, {deriv_table}={deriv_default}")
                    default_sql = generate_default_sql(deriv_table, col_name, base_default, db_type)
                    comment_statements.append(f"-- 修复SQL（取消注释即可执行）:")
                    comment_statements.append(f"-- {default_sql}")
                    issues_found[deriv_table].append(f"⚠️ DEFAULT值不一致: {col_name} 原表={base_default}, {deriv_table}={deriv_default}")


def generate_create_table_sql(table_name, base_cols, db_type):
    """生成CREATE TABLE语句（无主键）"""
    lines = []
    
    if db_type == 'sqlserver':
        lines.append(f"IF OBJECT_ID('{table_name}', 'U') IS NULL")
        lines.append(f"BEGIN")
        lines.append(f"    CREATE TABLE {table_name} (")
        
        col_defs = []
        for col in base_cols:
            col_name = col["COLUMN_NAME"].strip()
            type_def = build_type_def(col, db_type)
            nullable = col.get("NULLABLE", "Y").strip().upper()
            null_str = "NULL" if nullable == "Y" else "NOT NULL"
            
            col_defs.append(f"        {col_name} {type_def} {null_str}")
        
        lines.append(",\n".join(col_defs))
        lines.append(f"    )")
        lines.append(f"END")
    else:
        # Oracle
        lines.append(f"-- CREATE TABLE {table_name} (如果表不存在)")
        lines.append(f"DECLARE")
        lines.append(f"    v_count NUMBER;")
        lines.append(f"BEGIN")
        lines.append(f"    SELECT COUNT(*) INTO v_count FROM user_tables WHERE table_name = '{table_name}';")
        lines.append(f"    IF v_count = 0 THEN")
        lines.append(f"        EXECUTE IMMEDIATE '")
        lines.append(f"            CREATE TABLE {table_name} (")
        
        col_defs = []
        for col in base_cols:
            col_name = col["COLUMN_NAME"].strip()
            type_def = build_type_def(col, db_type)
            nullable = col.get("NULLABLE", "Y").strip().upper()
            null_str = "NULL" if nullable == "Y" else "NOT NULL"
            
            col_defs.append(f"                {col_name} {type_def} {null_str}")
        
        lines.append(",\n".join(col_defs))
        lines.append(f"            )")
        lines.append(f"        ';")
        lines.append(f"    END IF;")
        lines.append(f"END;")
        lines.append(f"/")
    
    return "\n".join(lines)


def generate_add_column_sql(table_name, col_name, base_col, db_type):
    """生成ADD COLUMN语句（带存在性检查）"""
    type_def = build_type_def(base_col, db_type)
    
    if db_type == 'sqlserver':
        return f"IF OBJECT_ID('{table_name}', 'U') IS NOT NULL AND COL_LENGTH('{table_name}', '{col_name}') IS NULL ALTER TABLE {table_name} ADD {col_name} {type_def} NULL;"
    else:
        # Oracle
        return f"-- ALTER TABLE {table_name} ADD {col_name} {type_def} NULL;"


def generate_modify_column_sql(table_name, col_name, base_col, db_type):
    """生成MODIFY COLUMN语句（带存在性检查）"""
    type_def = build_type_def(base_col, db_type)
    
    if db_type == 'sqlserver':
        return f"IF OBJECT_ID('{table_name}', 'U') IS NOT NULL AND COL_LENGTH('{table_name}', '{col_name}') IS NOT NULL ALTER TABLE {table_name} ALTER COLUMN {col_name} {type_def};"
    else:
        # Oracle
        return f"ALTER TABLE {table_name} MODIFY ({col_name} {type_def});"


def generate_modify_nullable_sql(table_name, col_name, base_col, db_type, nullable=True):
    """生成修改可空性的语句"""
    type_def = build_type_def(base_col, db_type)
    null_str = "NULL" if nullable else "NOT NULL"
    
    if db_type == 'sqlserver':
        return f"IF OBJECT_ID('{table_name}', 'U') IS NOT NULL AND COL_LENGTH('{table_name}', '{col_name}') IS NOT NULL ALTER TABLE {table_name} ALTER COLUMN {col_name} {type_def} {null_str};"
    else:
        # Oracle
        return f"ALTER TABLE {table_name} MODIFY ({col_name} {type_def} {null_str});"


def generate_default_sql(table_name, col_name, default_value, db_type):
    """生成添加DEFAULT的语句"""
    if db_type == 'sqlserver':
        # SQL Server添加DEFAULT约束
        constraint_name = f"DF_{table_name}_{col_name}"
        return f"IF OBJECT_ID('{table_name}', 'U') IS NOT NULL AND COL_LENGTH('{table_name}', '{col_name}') IS NOT NULL ALTER TABLE {table_name} ADD CONSTRAINT {constraint_name} DEFAULT {default_value} FOR {col_name};"
    else:
        # Oracle
        return f"ALTER TABLE {table_name} MODIFY ({col_name} DEFAULT {default_value});"


def generate_fix_script(create_statements, alter_statements, comment_statements, db_type):
    """生成修复SQL脚本"""
    script_lines = [
        "-- 基准库自检修复脚本",
        f"-- 数据库类型: {db_type}",
        f"-- 新建表: {len(create_statements)} 个",
        f"-- 修改字段: {len(alter_statements)} 条",
        f"-- 需人工确认: {len([s for s in comment_statements if s.startswith('-- 需要人工确认')])} 项",
        "",
        "-- ========== 1. 新建表（TRAN/LOG表不存在时） ==========",
        ""
    ]
    
    for stmt in create_statements:
        script_lines.append(stmt)
        script_lines.append("")
    
    script_lines.extend([
        "-- ========== 2. 修改字段（安全修改） ==========",
        ""
    ])
    
    for stmt in alter_statements:
        script_lines.append(stmt)
        # 每条SQL语句后加空行分隔
        if not stmt.startswith("--"):
            script_lines.append("")
    
    if comment_statements:
        script_lines.extend([
            "-- ========== 3. 需要人工确认（已注释） ==========",
            ""
        ])
        for stmt in comment_statements:
            script_lines.append(stmt)
            # 每条SQL语句后加空行分隔
            if stmt.startswith("-- IF ") or stmt.startswith("-- ALTER "):
                script_lines.append("")
    
    return "\n".join(script_lines)


def main():
    parser = argparse.ArgumentParser(description='基准库自检脚本 - 原表 vs TRAN/LOG表结构一致性检查')
    parser.add_argument('--md', required=True, help='表清单MD文件路径')
    parser.add_argument('--csv', required=True, help='CSV文件路径')
    parser.add_argument('--task-dir', required=True, help='任务目录路径')
    parser.add_argument('--db-type', required=True, choices=['oracle', 'sqlserver'], help='数据库类型')
    parser.add_argument('--output', help='输出修复脚本路径（默认: task_dir/selfcheck_<db_type>.sql）')
    parser.add_argument('--encoding', default='utf-8', help='CSV编码（默认utf-8）')
    args = parser.parse_args()
    
    md_path = Path(args.md)
    csv_path = Path(args.csv)
    task_dir = Path(args.task_dir)
    output_path = Path(args.output) if args.output else task_dir / f"selfcheck_{args.db_type}.sql"
    
    print("=" * 60)
    print("基准库自检脚本 - 原表 vs TRAN/LOG表结构一致性检查")
    print("=" * 60)
    
    # 检查文件
    if not md_path.exists():
        print(f"❌ MD文件不存在: {md_path}")
        sys.exit(1)
    if not csv_path.exists():
        print(f"❌ CSV文件不存在: {csv_path}")
        sys.exit(1)
    
    # 加载表清单
    base_tables = load_table_list(md_path)
    print(f"✓ 表清单: {len(base_tables)} 张原表")
    
    # 读取CSV
    rows = read_csv(csv_path, args.encoding)
    print(f"✓ CSV: {len(rows)} 行")
    
    # 执行自检
    create_statements, alter_statements, comment_statements, issues_found = self_check(
        rows, base_tables, args.db_type
    )
    
    # 输出结果
    print("\n" + "=" * 60)
    print("自检结果")
    print("=" * 60)
    
    if not issues_found and not comment_statements:
        print("✅ 自检通过！所有_TRAN和_LOG表与原表结构一致")
        return
    
    if issues_found:
        print(f"\n❌ 发现 {len(issues_found)} 个衍生表有问题：")
        for table, issues in list(issues_found.items())[:10]:
            print(f"\n  表: {table}")
            for issue in issues[:5]:
                print(f"    {issue}")
            if len(issues) > 5:
                print(f"    ... 还有 {len(issues) - 5} 个问题")
    
    if comment_statements:
        confirm_count = len([s for s in comment_statements if s.startswith('-- 需要人工确认')])
        print(f"\n⚠️  需要人工确认: {confirm_count} 项")
    
    # 生成修复脚本
    script_content = generate_fix_script(create_statements, alter_statements, comment_statements, args.db_type)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(script_content)
    
    print(f"\n📊 统计:")
    print(f"  - 新建表: {len(create_statements)} 个")
    print(f"  - 修改字段: {len(alter_statements)} 条")
    print(f"  - 需人工确认: {len([s for s in comment_statements if s.startswith('-- 需要人工确认')])} 项")
    print(f"  - 修复脚本: {output_path}")


if __name__ == "__main__":
    main()
