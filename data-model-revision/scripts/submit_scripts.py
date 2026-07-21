#!/usr/bin/env python3
"""
脚本提交工具
将生成的DDL脚本和修订记录脚本提交到BMS后端程序的指定目录

使用方式：
    python submit_scripts.py --ddl <DDL脚本路径> --revise-record <修订记录脚本路径> --db-type <数据库类型>

或者批量提交：
    python submit_scripts.py --input-dir <输入目录> --db-type greenplum
"""

import os
import shutil
import argparse
from datetime import datetime

# 默认配置
DEFAULT_BMS_ROOT = "/Users/zhanglei/winning/git/winning-dps-rda-bms"
DEFAULT_DDL_PATHS = {
    "greenplum": "{BMS_ROOT}/winning-dps-rda-bms-server/src/main/resources/edsm_sql/greenplum",
    "oracle": "{BMS_ROOT}/winning-dps-rda-bms-server/src/main/resources/edsm_sql/oracle",
    "sqlserver": "{BMS_ROOT}/winning-dps-rda-bms-server/src/main/resources/edsm_sql/sqlserver",
    "postgresql": "{BMS_ROOT}/winning-dps-rda-bms-server/src/main/resources/edsm_sql/postgresql"
}
DEFAULT_REVISE_RECORD_PATH = "{BMS_ROOT}/winning-dps-rda-bms-server/src/main/resources/system_sql/rhdp_app/postgresql"


def get_ddl_target_path(db_type, bms_root=None):
    """获取DDL脚本的目标路径"""
    if not bms_root:
        bms_root = DEFAULT_BMS_ROOT
    template = DEFAULT_DDL_PATHS.get(db_type)
    if not template:
        raise ValueError(f"不支持的数据库类型: {db_type}")
    return template.replace("{BMS_ROOT}", bms_root)


def get_revise_record_target_path(bms_root=None):
    """获取修订记录脚本的目标路径"""
    if not bms_root:
        bms_root = DEFAULT_BMS_ROOT
    return DEFAULT_REVISE_RECORD_PATH.replace("{BMS_ROOT}", bms_root)


def submit_ddl_script(source_path, db_type, bms_root=None):
    """提交DDL脚本到目标目录

    Args:
        source_path: DDL脚本源路径
        db_type: 数据库类型（greenplum/oracle/sqlserver/postgresql）
        bms_root: BMS后端程序根目录（可选）

    Returns:
        目标路径
    """
    target_dir = get_ddl_target_path(db_type, bms_root)

    # 检查目标目录是否存在
    if not os.path.exists(target_dir):
        os.makedirs(target_dir, exist_ok=True)
        print(f"  创建目录: {target_dir}")

    # 获取文件名
    filename = os.path.basename(source_path)
    target_path = os.path.join(target_dir, filename)

    # 复制文件
    shutil.copy2(source_path, target_path)
    print(f"  DDL脚本已提交: {target_path}")

    return target_path


def submit_revise_record_script(source_path, bms_root=None):
    """提交修订记录脚本到目标目录

    Args:
        source_path: 修订记录脚本源路径
        bms_root: BMS后端程序根目录（可选）

    Returns:
        目标路径
    """
    target_dir = get_revise_record_target_path(bms_root)

    # 检查目标目录是否存在
    if not os.path.exists(target_dir):
        os.makedirs(target_dir, exist_ok=True)
        print(f"  创建目录: {target_dir}")

    # 获取文件名
    filename = os.path.basename(source_path)
    target_path = os.path.join(target_dir, filename)

    # 复制文件
    shutil.copy2(source_path, target_path)
    print(f"  修订记录脚本已提交: {target_path}")

    return target_path


def submit_all_scripts(input_dir, db_type, bms_root=None):
    """批量提交目录下的所有脚本

    Args:
        input_dir: 输入目录（包含DDL和修订记录脚本）
        db_type: 数据库类型
        bms_root: BMS后端程序根目录（可选）

    Returns:
        提交结果统计
    """
    results = {
        "ddl_scripts": [],
        "revise_record_scripts": [],
        "total": 0
    }

    # 扫描目录下的所有.sql文件
    for filename in os.listdir(input_dir):
        if not filename.endswith('.sql'):
            continue

        source_path = os.path.join(input_dir, filename)

        # 根据文件名判断类型
        if 'alter_table' in filename.lower() or 'create_table' in filename.lower():
            # DDL脚本
            target_path = submit_ddl_script(source_path, db_type, bms_root)
            results["ddl_scripts"].append(target_path)
        elif 'revise_record' in filename.lower():
            # 修订记录脚本
            target_path = submit_revise_record_script(source_path, bms_root)
            results["revise_record_scripts"].append(target_path)
        else:
            # 其他脚本，默认当作DDL处理
            target_path = submit_ddl_script(source_path, db_type, bms_root)
            results["ddl_scripts"].append(target_path)

        results["total"] += 1

    return results


def print_summary(results):
    """打印提交结果汇总"""
    print("\n" + "="*50)
    print("脚本提交结果汇总")
    print("="*50)

    print(f"\nDDL脚本 ({len(results['ddl_scripts'])} 个):")
    for path in results["ddl_scripts"]:
        print(f"  - {os.path.basename(path)}")

    print(f"\n修订记录脚本 ({len(results['revise_record_scripts'])} 个):")
    for path in results["revise_record_scripts"]:
        print(f"  - {os.path.basename(path)}")

    print(f"\n总计: {results['total']} 个脚本")
    print("="*50)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='脚本提交工具')
    parser.add_argument('--ddl', help='DDL脚本路径')
    parser.add_argument('--revise-record', help='修订记录脚本路径')
    parser.add_argument('--db-type', default='greenplum',
                        choices=['greenplum', 'oracle', 'sqlserver', 'postgresql'],
                        help='数据库类型')
    parser.add_argument('--input-dir', help='输入目录（批量提交）')
    parser.add_argument('--bms-root', default=DEFAULT_BMS_ROOT,
                        help='BMS后端程序根目录')

    args = parser.parse_args()

    results = {
        "ddl_scripts": [],
        "revise_record_scripts": [],
        "total": 0
    }

    # 批量提交模式
    if args.input_dir:
        print(f"批量提交目录: {args.input_dir}")
        results = submit_all_scripts(args.input_dir, args.db_type, args.bms_root)
        print_summary(results)
        return

    # 单文件提交模式
    if args.ddl:
        print(f"提交DDL脚本: {args.ddl}")
        target_path = submit_ddl_script(args.ddl, args.db_type, args.bms_root)
        results["ddl_scripts"].append(target_path)
        results["total"] += 1

    if args.revise_record:
        print(f"提交修订记录脚本: {args.revise_record}")
        target_path = submit_revise_record_script(args.revise_record, args.bms_root)
        results["revise_record_scripts"].append(target_path)
        results["total"] += 1

    if results["total"] > 0:
        print_summary(results)
    else:
        print("未指定要提交的脚本")
        print("使用 --ddl 或 --revise-record 指定单个文件")
        print("使用 --input-dir 指定目录批量提交")


if __name__ == '__main__':
    main()