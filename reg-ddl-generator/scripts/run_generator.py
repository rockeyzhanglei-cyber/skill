#!/usr/bin/env python3
"""
一键执行脚本
整合Word文档解析和DDL/DML脚本生成流程

v4.0.0 更新：
- 新增增量/全量模式支持
- DDL和DML可独立选择增量/全量
- 参数变更：--ddl-mode (incremental/full), --dml-mode (none/incremental/full)
- 移除 --with-dml 参数，改用 --dml-mode

v3.0.0 更新：
- 新增DML标准库同步功能
- 支持 --with-dml 参数
- 输出文件分离：DDL文件 + DML文件
- 文件命名：{文档名}_DDL_{数据库类型}.sql 和 {文档名}_DML.sql

v2.2.0 更新：
- 支持修改字段解析和DDL生成
- 区分DDL变更（约束、表示格式）和注释变更（说明、备注等）
- 只有约束和表示格式的修改才生成ALTER TABLE脚本

v1.19.0 更新：
- 增加 --no-tran-log 和 --no-public-fields 命令行参数
- 使用 argparse 替代简单的 argv 解析
- 修复函数参数传递问题
"""

import sys
import os
import re
import argparse
from datetime import datetime

# 导入解析器和生成器
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from word_parser import parse_word_document, parse_word_document_full
from ddl_generator import generate_full_script
from dml_generator import generate_full_dml, generate_full_dml_full
from verify_sql import verify_sql, print_report

def get_doc_name(doc_path):
    """从文档路径提取文档名（用于文件命名）"""
    filename = os.path.basename(doc_path)
    name = filename.replace('.docx', '').replace('.DOCX', '')
    # 清理版本号等后缀
    name = re.sub(r'V[\d.]+', '', name)
    name = re.sub(r'[\s\-_]+$', '', name)
    return name[:50] if len(name) > 50 else name

def get_project_name(doc_path):
    """从文档路径提取项目名"""
    filename = os.path.basename(doc_path)
    # 常见格式：XXX平台标准规范-数据集标准-平台V3.0.0.docx
    match = re.search(r'([^\s\-]+(?:平台|医院|项目|系统|信息))', filename)
    if match:
        return match.group(1)
    name = filename.replace('.docx', '').replace('.DOCX', '')
    return name[:30] if len(name) > 30 else name

def run_generator(doc_path, db_type='oracle', case_style='lower',
                  ddl_mode='incremental', dml_mode='none',
                  include_tran_log=True, include_public_fields=True,
                  output_dir=None):
    """
    执行完整的生成流程

    v4.0.0 更新：
    - 支持 ddl_mode: incremental（增量）或 full（全量）
    - 支持 dml_mode: none（不生成）、incremental（增量）或 full（全量）

    参数:
        doc_path: Word文档路径
        db_type: 数据库类型 (oracle/mysql/sqlserver/postgresql)
        case_style: 大小写格式 (upper/lower/original)
        ddl_mode: DDL生成模式 (incremental/full)
        dml_mode: DML生成模式 (none/incremental/full)
        include_tran_log: 是否生成TRAN/LOG关联表（默认True）
        include_public_fields: 是否添加sczt公共字段（默认True）
        output_dir: 输出目录，默认为 ~/Downloads/

    返回:
        生成结果字典
    """

    # 根据DDL模式选择解析函数
    if ddl_mode == 'full':
        print(f"正在解析文档（全量模式）: {doc_path}")
        parse_result = parse_word_document_full(doc_path)
        print(f"文档共有 {parse_result['total_tables']} 个表格")
        print(f"数据库表结构表格: {len(parse_result['new_tables'])} 个（全量模式：所有表格视为新增表）")
    else:
        print(f"正在解析文档（增量模式）: {doc_path}")
        parse_result = parse_word_document(doc_path)

        print(f"文档共有 {parse_result['total_tables']} 个表格")
        print(f"新增分类: {len(parse_result['new_categories'])} 个")
        print(f"新增表: {len(parse_result['new_tables'])} 个")
        print(f"新增字段的表: {parse_result['changed_tables']} 个")
        print(f"修改字段的表: {parse_result['modified_tables']} 个")

        # 显示新增分类
        if parse_result['new_categories']:
            print("\n新增分类:")
            for cat in parse_result['new_categories'][:10]:
                print(f"  + {cat['category_name']}")

        # 显示新增表
        if parse_result['new_tables']:
            print("\n新增表:")
            for nt in parse_result['new_tables']:
                print(f"  - {nt['table_cn']}[{nt['table_en']}] ({len(nt['fields'])} 字段)")
                if nt.get('category_name'):
                    print(f"      分类: {nt['category_name']}")

        # 显示修改字段（区分DDL变更和注释变更）
        if parse_result['modified_fields']:
            print("\n修改字段:")
            for mod in parse_result['modified_fields'][:5]:
                print(f"  ~ {mod['table_cn']}[{mod['table_en']}]:")
                for f in mod['modified_fields'][:3]:
                    ddl_flag = "★需DDL" if f['has_ddl_change'] else "仅注释"
                    changed_cols = ', '.join(f['changed_columns'])
                    print(f"      {f['field_cn']}[{f['field_en']}] - {changed_cols} ({ddl_flag})")

    # 确定输出目录（默认 ~/Downloads）
    if output_dir is None:
        output_dir = os.path.expanduser('~/Downloads')

    os.makedirs(output_dir, exist_ok=True)

    # 生成文档名（用于文件命名）
    doc_name = get_doc_name(doc_path)

    results = {}

    # ========== 生成DDL脚本 ==========
    # 全量模式：所有表格都生成DDL
    # 增量模式：只有新增表、新增字段、修改字段才生成DDL
    should_generate_ddl = False
    if ddl_mode == 'full':
        should_generate_ddl = len(parse_result['new_tables']) > 0
    else:
        should_generate_ddl = len(parse_result['new_tables']) > 0 or parse_result['changed_tables'] > 0 or parse_result['modified_tables'] > 0 or parse_result.get('deleted_tables', 0) > 0

    if should_generate_ddl:
        mode_suffix = "_FULL" if ddl_mode == 'full' else ""
        print(f"\n正在生成 {db_type} DDL脚本（{ddl_mode}模式）...")

        ddl_filename = f"{doc_name}_DDL_{db_type}{mode_suffix}.sql"
        ddl_path = os.path.join(output_dir, ddl_filename)

        ddl_result = generate_full_script(
            parse_result,
            db_type,
            case_style,
            os.path.basename(doc_path),
            ddl_path,
            include_tran_log=include_tran_log,
            include_public_fields=include_public_fields
        )

        # 根据用户选择动态显示统计信息
        tran_log_suffix = "(含TRAN/LOG同步)" if include_tran_log else ""
        print(f"\n✓ DDL脚本已生成")
        print(f"  输出文件: {ddl_result['output_path']}")
        print(f"  新增表: {ddl_result['new_tables']} 个 {tran_log_suffix}")
        print(f"  新增字段: {ddl_result['field_count']} 个 {tran_log_suffix}")
        print(f"  修改字段: {ddl_result['modify_count']} 个")
        if ddl_result.get('delete_count'):
            print(f"  删除字段: {ddl_result['delete_count']} 个（置为非必填）{tran_log_suffix}")
        print(f"  DDL总数: {ddl_result['total_ddl']} 个")

        # ========== 语法验证 ==========
        print(f"\n正在验证SQL语法...")
        issues = verify_sql(ddl_result['output_path'], db_type)
        has_issues = print_report(issues, ddl_result['output_path'], db_type)
        if issues:
            print("\n⚠️ 脚本存在语法问题！请检查脚本生成逻辑中的bug并修复后重新生成。")
            print("   常见原因：parse_format_string 未覆盖的表示格式、类型映射错误等")
            results['verify_issues'] = issues
        else:
            print("✓ 语法验证通过")

        results['ddl'] = ddl_result
    else:
        print("未检测到红色标记的变更，无需生成DDL脚本（增量模式）")

    # ========== 生成DML脚本 ==========
    if dml_mode != 'none':
        dml_suffix = "_FULL" if dml_mode == 'full' else ""
        print(f"\n正在生成标准库DML同步脚本（{dml_mode}模式）...")

        dml_filename = f"{doc_name}_DML{dml_suffix}.sql"
        dml_path = os.path.join(output_dir, dml_filename)

        # 根据DML模式选择生成函数
        if dml_mode == 'full':
            dml_result = generate_full_dml_full(
                parse_result,
                doc_name,
                dml_path,
                include_metadata=True
            )
        else:
            dml_result = generate_full_dml(
                parse_result,
                doc_name,
                dml_path,
                include_metadata=True
            )

        print(f"\n✓ DML脚本已生成")
        print(f"  输出文件: {dml_result['output_path']}")
        print(f"  标准ID: {dml_result['standard_id']}")
        print(f"  新增分类: {dml_result['new_categories']} 个")
        print(f"  新增数据集: {dml_result['new_datasets']} 个")
        print(f"  新增数据集字段: {dml_result['new_table_elements']} 个")
        print(f"  已有表新增字段: {dml_result['new_elements']} 个")
        print(f"  修改字段: {dml_result['modified_elements']} 个")
        print(f"  DML总数: {dml_result['dml_count']} 条")

        results['dml'] = dml_result

    return results

def main():
    """主函数，用于命令行调用"""
    parser = argparse.ArgumentParser(description='根据Word文档生成DDL/DML脚本')
    parser.add_argument('doc_path', help='Word文档路径 (.docx)')
    parser.add_argument('--db', '-d', default='oracle',
                        choices=['oracle', 'mysql', 'sqlserver', 'postgresql'],
                        help='数据库类型 (默认: oracle)')
    parser.add_argument('--case', '-c', default='lower',
                        choices=['upper', 'lower', 'original'],
                        help='大小写格式 (默认: lower)')
    parser.add_argument('--ddl-mode', default='incremental',
                        choices=['incremental', 'full'],
                        help='DDL生成模式: incremental=增量(红色标记), full=全量(所有表格) (默认: incremental)')
    parser.add_argument('--dml-mode', default='none',
                        choices=['none', 'incremental', 'full'],
                        help='DML生成模式: none=不生成, incremental=增量(红色标记), full=全量(所有表格) (默认: none)')
    parser.add_argument('--no-tran-log', action='store_true',
                        help='不生成TRAN/LOG关联表')
    parser.add_argument('--no-public-fields', action='store_true',
                        help='不添加sczt公共字段')
    parser.add_argument('--output', '-o', default=None,
                        help='输出目录 (默认: ~/Downloads/)')
    # 兼容旧参数（已废弃，但保留向后兼容）
    parser.add_argument('--with-dml', action='store_true',
                        help='[已废弃] 请使用 --dml-mode incremental')

    args = parser.parse_args()

    # 处理向后兼容：--with-dml 等同于 --dml-mode incremental
    dml_mode = args.dml_mode
    if args.with_dml and dml_mode == 'none':
        dml_mode = 'incremental'

    run_generator(
        args.doc_path,
        args.db,
        args.case,
        ddl_mode=args.ddl_mode,
        dml_mode=dml_mode,
        include_tran_log=not args.no_tran_log,
        include_public_fields=not args.no_public_fields,
        output_dir=args.output
    )

if __name__ == '__main__':
    main()