#!/usr/bin/env python3
"""
DML脚本生成器
根据解析结果生成标准库edsm_*表的同步DML脚本

支持表：
- edsm_dataset_category：数据集分类（新增分类）
- edsm_dataset：数据集（新增表、修改表）
- edsm_dataset_element：数据集元素（新增字段、修改字段）
- edsm_metadata：元数据（与dataset_element一一对应，每个元素独立生成一条，不共用、不去重）

v4.0.0 更新：
- 新增 generate_full_dml_full 函数：全量模式DML生成
- 支持增量模式（generate_full_dml）和全量模式（generate_full_dml_full）

v3.0.0 初始版本
"""

import re
from datetime import datetime

# 需要清理的不可见字符列表
INVISIBLE_CHARS = [
    '\u200b', '\u200c', '\u200d', '\u200e', '\u200f',
    '\u2060', '\u2061', '\u2062', '\u2063', '\u2064',
    '\u206a', '\u206b', '\u206c', '\u206d', '\u206e', '\u206f',
    '\ufeff', '\u00ad',
]

def clean_invisible_chars(text):
    """清理文本中的不可见字符"""
    if not text:
        return text
    result = text
    for char in INVISIBLE_CHARS:
        result = result.replace(char, '')
    return result

def get_standard_prefix(doc_name):
    """从文档名推断standard_id前缀

    根据文档名中的部分编号推断：
    - 包含"01部分" → winning-plat-01
    - 包含"02部分" → winning-plat-02
    - ...
    """
    match = re.search(r'第(\d+)部分', doc_name)
    if match:
        part_no = match.group(1)
        return f'winning-plat-{part_no}'
    return 'winning-plat-01'  # 默认

def generate_category_dml(new_categories, standard_id, doc_name):
    """生成edsm_dataset_category的DML

    参数:
        new_categories: 新增分类列表 [{'category_name': 'xxx', 'is_new': True}]
        standard_id: 标准ID
        doc_name: 文档名称

    返回:
        DML语句列表
    """
    dml_lines = []

    for cat in new_categories:
        category_name = clean_invisible_chars(cat['category_name'])
        category_id = f'{standard_id}-{category_name}'

        # 幂等INSERT语句
        sql = f"""insert into edsm_dataset_category(category_id, standard_id, parent_id, category_no, category_name, seq_no, is_del, created_at, modified_at) select '{category_id}', '{standard_id}', null, '{category_name}','{category_name}', (select count(1) from edsm_dataset_category)+1, 0, now(), null where not exists (select 1 from edsm_dataset_category where category_id = '{category_id}');"""
        dml_lines.append(sql)

    return dml_lines

def generate_dataset_dml(new_datasets, modified_datasets, standard_id, doc_name):
    """生成edsm_dataset的DML

    新增：直接INSERT
    修改：先DELETE再INSERT

    参数:
        new_datasets: 新增数据集列表
        modified_datasets: 修改数据集列表（字段变更的表）
        standard_id: 标准ID
        doc_name: 文档名称

    返回:
        DML语句列表
    """
    dml_lines = []

    # 新增数据集
    for ds in new_datasets:
        dataset_no = clean_invisible_chars(ds['table_en'])
        dataset_name = clean_invisible_chars(ds['table_cn'])
        dataset_id = f'{standard_id}-{dataset_no}'
        category_name = clean_invisible_chars(ds.get('category_name', ''))
        category_id = f'{standard_id}-{category_name}' if category_name else None

        if category_id:
            sql = f"""insert into edsm_dataset(dataset_id, standard_id, category_id, dataset_no, dataset_name, status, seq_no, is_del, created_at, modified_at) select '{dataset_id}','{standard_id}', '{category_id}', '{dataset_no}', '{dataset_name}', 1, (select count(1) from edsm_dataset)+1, 0, now(), null where not exists (select 1 from edsm_dataset where dataset_id = '{dataset_id}');"""
        else:
            sql = f"""insert into edsm_dataset(dataset_id, standard_id, category_id, dataset_no, dataset_name, status, seq_no, is_del, created_at, modified_at) select '{dataset_id}','{standard_id}', null, '{dataset_no}', '{dataset_name}', 1, (select count(1) from edsm_dataset)+1, 0, now(), null where not exists (select 1 from edsm_dataset where dataset_id = '{dataset_id}');"""
        dml_lines.append(sql)

    # 修改数据集（字段变更的表需要先删后插）
    for mod_ds in modified_datasets:
        dataset_no = clean_invisible_chars(mod_ds['table_en'])
        dataset_id = f'{standard_id}-{dataset_no}'

        # 先删除关联的element
        dml_lines.append(f"delete from edsm_dataset_element where dataset_id = '{dataset_id}';")
        # 再删除dataset（可选，视业务需求）
        # dml_lines.append(f"delete from edsm_dataset where dataset_id = '{dataset_id}';")
        # 注：修改场景通常只更新element，不删除dataset本身

    return dml_lines

def generate_element_dml(new_elements, modified_elements, standard_id, doc_name):
    """生成edsm_dataset_element的DML

    新增字段：直接INSERT
    修改字段：先DELETE再INSERT

    参数:
        new_elements: 新增字段列表 [{'table_en': 'xxx', 'table_cn': 'xxx', 'fields': [...]}]
        modified_elements: 修改字段列表 [{'table_en': 'xxx', 'modified_fields': [...]}]
        standard_id: 标准ID
        doc_name: 文档名称

    返回:
        DML语句列表
    """
    dml_lines = []

    # 新增字段
    for change in new_elements:
        dataset_no = clean_invisible_chars(change['table_en'])
        dataset_id = f'{standard_id}-{dataset_no}'
        category_name = clean_invisible_chars(change.get('category_name', ''))

        for field in change['new_fields']:
            element_code = clean_invisible_chars(field['field_en'])
            element_name = clean_invisible_chars(field['field_cn'])
            definition = clean_invisible_chars(field.get('comment', field.get('definition', '')))
            element_id = f'{dataset_id}-{element_code}'

            # 主键检测
            is_pk = 0
            if definition and ('复合主键' in definition or '联合主键' in definition or '主键' in definition):
                is_pk = 1

            # 必填检测
            notnull = 1 if field.get('required_cn') == '必填' or 'M' in str(field.get('required_value', '')) else 0

            # 数据类型 - 使用原始值（文档中的值，如S1/S2/S3/DATE），不转换
            data_type_raw = field.get('data_type_value', field.get('data_type_category_value', field.get('data_type', '')))
            data_type = clean_invisible_chars(data_type_raw) if data_type_raw else ''
            # 表示格式 - 使用原始值（文档中的值，如AN..64/N1/DT19），不转换
            representation_format = clean_invisible_chars(field.get('format_value', field.get('representation_format', '')))

            # 值域代码
            code_system_id = ''
            if definition and '参见：' in definition:
                match = re.search(r'参见：([^\[]+)\[', definition)
                if match:
                    code_system_id = match.group(1).strip()

            # seq_no 子查询
            seq_subquery = f"(select count(1) from edsm_dataset_element e, edsm_dataset a, edsm_dataset_category b, edsm_data_standard c where e.dataset_id = a.dataset_id and a.category_id = b.category_id and a.standard_id = c.standard_id and b.category_name ='{category_name}' and c.standard_name like '%{doc_name[:30]}%' and a.dataset_no='{dataset_no}')+1"

            sql = f"""insert into edsm_dataset_element(element_id, dataset_id, metadata_id, internal_id, element_code, element_name, definition, is_pk, "notnull", data_type, representation_format, code_system_id, allow, status, seq_no, is_del, created_at, modified_at) select '{element_id}', '{dataset_id}', null, null, '{element_code}', '{element_name}', '{definition}', {is_pk}, {notnull}, '{data_type}', '{representation_format}', '{code_system_id}', null, 1, {seq_subquery}, 0, now(), null where not exists (select 1 from edsm_dataset_element where element_id = '{element_id}');"""
            dml_lines.append(sql)

    # 修改字段（先删后插）
    for mod in modified_elements:
        dataset_no = clean_invisible_chars(mod['table_en'])
        dataset_id = f'{standard_id}-{dataset_no}'

        for field in mod['modified_fields']:
            element_code = clean_invisible_chars(field['field_en'])
            element_id = f'{dataset_id}-{element_code}'

            # 先删除
            dml_lines.append(f"delete from edsm_dataset_element where element_id = '{element_id}';")

            # 再插入（重新生成）
            element_name = clean_invisible_chars(field['field_cn'])
            definition = clean_invisible_chars(field.get('comment', field.get('definition', '')))

            is_pk = 0
            if definition and ('复合主键' in definition or '联合主键' in definition or '主键' in definition):
                is_pk = 1

            notnull = 1 if field.get('required_cn') == '必填' or 'M' in str(field.get('required_value', '')) else 0

            # 数据类型 - 使用原始值（文档中的值，如S1/S2/S3/DATE），不转换
            data_type_raw = field.get('data_type_value', field.get('data_type_category_value', field.get('data_type', '')))
            data_type = clean_invisible_chars(data_type_raw) if data_type_raw else ''
            # 表示格式 - 使用原始值（文档中的值，如AN..64/N1/DT19），不转换
            representation_format = clean_invisible_chars(field.get('format_value', field.get('representation_format', '')))

            code_system_id = ''
            if definition and '参见：' in definition:
                match = re.search(r'参见：([^\[]+)\[', definition)
                if match:
                    code_system_id = match.group(1).strip()

            category_name = clean_invisible_chars(mod.get('category_name', ''))
            seq_subquery = f"(select count(1) from edsm_dataset_element e, edsm_dataset a, edsm_dataset_category b, edsm_data_standard c where e.dataset_id = a.dataset_id and a.category_id = b.category_id and a.standard_id = c.standard_id and b.category_name ='{category_name}' and c.standard_name like '%{doc_name[:30]}%' and a.dataset_no='{dataset_no}')+1"

            sql = f"""insert into edsm_dataset_element(element_id, dataset_id, metadata_id, internal_id, element_code, element_name, definition, is_pk, "notnull", data_type, representation_format, code_system_id, allow, status, seq_no, is_del, created_at, modified_at) select '{element_id}', '{dataset_id}', null, null, '{element_code}', '{element_name}', '{definition}', {is_pk}, {notnull}, '{data_type}', '{representation_format}', '{code_system_id}', null, 1, {seq_subquery}, 0, now(), null;"""
            dml_lines.append(sql)

    return dml_lines

def generate_new_table_elements_dml(new_tables, standard_id, doc_name):
    """生成新增表所有字段的DML

    新增表时，需要生成该表所有字段的INSERT语句

    参数:
        new_tables: 新增表列表 [{'table_en': 'xxx', 'table_cn': 'xxx', 'fields': [...]}]
        standard_id: 标准ID
        doc_name: 文档名称

    返回:
        DML语句列表
    """
    dml_lines = []

    for nt in new_tables:
        dataset_no = clean_invisible_chars(nt['table_en'])
        dataset_id = f'{standard_id}-{dataset_no}'
        category_name = clean_invisible_chars(nt.get('category_name', ''))

        for field in nt['fields']:
            element_code = clean_invisible_chars(field['field_en'])
            element_name = clean_invisible_chars(field['field_cn'])
            definition = clean_invisible_chars(field.get('comment', field.get('definition', '')))
            element_id = f'{dataset_id}-{element_code}'

            # 主键检测
            is_pk = 1 if field.get('is_pk', False) else 0
            if is_pk == 0 and definition and ('复合主键' in definition or '联合主键' in definition or '主键' in definition):
                is_pk = 1

            # 必填检测
            notnull = 1 if field.get('required_cn') == '必填' or 'M' in str(field.get('required_value', '')) or field.get('constraint', '') == 'not null' else 0

            # 数据类型 - 使用原始值（文档中的值，如S1/S2/S3/DATE），不转换
            data_type_raw = field.get('data_type_value', field.get('data_type_category_value', field.get('data_type', '')))
            data_type = clean_invisible_chars(data_type_raw) if data_type_raw else ''
            # 表示格式 - 使用原始值（文档中的值，如AN..64/N1/DT19），不转换
            representation_format = clean_invisible_chars(field.get('format_value', field.get('representation_format', field.get('length', ''))))

            # 值域代码
            code_system_id = ''
            if definition and '参见：' in definition:
                match = re.search(r'参见：([^\[]+)\[', definition)
                if match:
                    code_system_id = match.group(1).strip()

            # seq_no 子查询
            seq_subquery = f"(select count(1) from edsm_dataset_element e, edsm_dataset a, edsm_dataset_category b, edsm_data_standard c where e.dataset_id = a.dataset_id and a.category_id = b.category_id and a.standard_id = c.standard_id and b.category_name ='{category_name}' and c.standard_name like '%{doc_name[:30]}%' and a.dataset_no='{dataset_no}')+1"

            sql = f"""insert into edsm_dataset_element(element_id, dataset_id, metadata_id, internal_id, element_code, element_name, definition, is_pk, "notnull", data_type, representation_format, code_system_id, allow, status, seq_no, is_del, created_at, modified_at) select '{element_id}', '{dataset_id}', null, null, '{element_code}', '{element_name}', '{definition}', {is_pk}, {notnull}, '{data_type}', '{representation_format}', '{code_system_id}', null, 1, {seq_subquery}, 0, now(), null where not exists (select 1 from edsm_dataset_element where element_id = '{element_id}');"""
            dml_lines.append(sql)

    return dml_lines

def generate_metadata_dml(parse_result, standard_id, doc_name):
    """生成edsm_metadata的DML

    与edsm_dataset_element一一对应，从已有数据生成

    参数:
        parse_result: 解析结果
        standard_id: 标准ID
        doc_name: 文档名称

    返回:
        DML语句列表
    """
    dml_lines = []

    # metadata从dataset_element自动生成（一对一：每个dataset_element对应一条独立的metadata）
    # metadata_id 与 metadata_code 均等于 dataset_element 的 element_id，彻底废除"按字段名共用/去重"逻辑
    sql = f"""insert into edsm_metadata(metadata_id, namespace_id, external_id, metadata_code, metadata_name, definition, data_type, representation_format, code_system_id, allow, status, is_del, created_at)
select a.element_id, '1', 'HDS'||lpad(d.seq_no::text, 2, '0')||lpad(c.seq_no::text, 2, '0')||'.'||lpad(b.seq_no::text, 3, '0')||'.'||lpad(a.seq_no::text, 3, '0'), a.element_id, a.element_name, a.element_name, a.data_type, a.representation_format, a.code_system_id, a.allow, 1, 0, now() from edsm_dataset_element a, edsm_dataset b, edsm_dataset_category c, edsm_data_standard d where a.dataset_id = b.dataset_id and b.category_id = c.category_id and c.standard_id = d.standard_id and d.standard_id = '{standard_id}' and not exists (select 1 from edsm_metadata where metadata_id = a.element_id);"""

    dml_lines.append(sql)

    # 更新dataset_element的metadata_id关联：按 element_id 一一对应（废除按 element_code 字段名共用/串号）
    sql2 = f"""update edsm_dataset_element a set metadata_id = (select metadata_id from edsm_metadata b where a.element_id = b.metadata_id and b.namespace_id = '1' limit 1) where a.dataset_id like '{standard_id}-%' and a.metadata_id is null;"""
    dml_lines.append(sql2)

    return dml_lines

def generate_full_dml(parse_result, doc_name, output_path, include_metadata=True):
    """生成完整DML脚本并保存到文件

    参数:
        parse_result: 解析结果
        doc_name: 文档名称
        output_path: 输出路径
        include_metadata: 是否生成metadata同步

    返回:
        生成结果字典
    """
    standard_id = get_standard_prefix(doc_name)

    # 提取变更数据
    new_tables = parse_result.get('new_tables', [])
    all_changes = parse_result.get('all_changes', [])  # 新增字段的表
    modified_fields = parse_result.get('modified_fields', [])  # 修改字段的表
    new_categories = parse_result.get('new_categories', [])  # 新增分类

    dml_count = 0

    with open(output_path, 'w', encoding='utf-8') as f:
        # 文件头注释
        f.write(f"-- 标准库同步DML脚本\n")
        f.write(f"-- 文档: {doc_name}\n")
        f.write(f"-- 标准ID: {standard_id}\n")
        f.write(f"-- 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        # ========== edsm_dataset_category（新增分类）==========
        if new_categories:
            f.write("-- ========== edsm_dataset_category（新增分类）==========\n\n")
            for sql in generate_category_dml(new_categories, standard_id, doc_name):
                f.write(sql + "\n")
                dml_count += 1
            f.write("\n")

        # ========== edsm_dataset（新增数据集）==========
        if new_tables:
            f.write("-- ========== edsm_dataset（新增数据集）==========\n\n")
            for sql in generate_dataset_dml(new_tables, [], standard_id, doc_name):
                f.write(sql + "\n")
                dml_count += 1
            f.write("\n")

        # ========== edsm_dataset_element（新增数据集的所有字段）==========
        if new_tables:
            f.write("-- ========== edsm_dataset_element（新增数据集字段）==========\n\n")
            for sql in generate_new_table_elements_dml(new_tables, standard_id, doc_name):
                f.write(sql + "\n")
                dml_count += 1
            f.write("\n")

        # ========== edsm_dataset_element（新增字段）==========
        if all_changes:
            f.write("-- ========== edsm_dataset_element（新增字段）==========\n\n")
            for sql in generate_element_dml(all_changes, [], standard_id, doc_name):
                f.write(sql + "\n")
                dml_count += 1
            f.write("\n")

        # ========== edsm_dataset_element（修改字段 - 先删后插）==========
        if modified_fields:
            f.write("-- ========== edsm_dataset_element（修改字段）==========\n\n")
            for sql in generate_element_dml([], modified_fields, standard_id, doc_name):
                f.write(sql + "\n")
                dml_count += 1
            f.write("\n")

        # ========== edsm_metadata（元数据汇总）==========
        if include_metadata and (new_tables or all_changes or modified_fields):
            f.write("-- ========== edsm_metadata（元数据汇总）==========\n\n")
            for sql in generate_metadata_dml(parse_result, standard_id, doc_name):
                f.write(sql + "\n")
                dml_count += 1
            f.write("\n")

    return {
        'output_path': output_path,
        'dml_count': dml_count,
        'standard_id': standard_id,
        'new_categories': len(new_categories),
        'new_datasets': len(new_tables),
        'new_table_elements': sum(len(nt['fields']) for nt in new_tables),  # 新增表的所有字段
        'new_elements': sum(len(c['new_fields']) for c in all_changes),  # 已有表的新增字段
        'modified_elements': sum(len(m['modified_fields']) for m in modified_fields)
    }

def generate_full_dml_full(parse_result, doc_name, output_path, include_metadata=True):
    """生成完整全量DML脚本并保存到文件

    v4.0.0 新增：用于全量模式，同步所有表格和字段到标准库

    参数:
        parse_result: 全量模式解析结果（来自 parse_word_document_full）
        doc_name: 文档名称
        output_path: 输出路径
        include_metadata: 是否生成metadata同步

    返回:
        生成结果字典
    """
    standard_id = get_standard_prefix(doc_name)

    # 全量模式：所有表格都是新增表
    new_tables = parse_result.get('new_tables', [])
    all_categories = parse_result.get('all_categories', [])

    dml_count = 0

    with open(output_path, 'w', encoding='utf-8') as f:
        # 文件头注释
        f.write(f"-- 标准库同步DML脚本（全量模式）\n")
        f.write(f"-- 文档: {doc_name}\n")
        f.write(f"-- 标准ID: {standard_id}\n")
        f.write(f"-- 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"-- 模式: 全量同步所有表格和字段\n\n")

        # ========== edsm_dataset_category（所有分类）==========
        if all_categories:
            f.write("-- ========== edsm_dataset_category（所有分类）==========\n\n")
            for cat in all_categories:
                category_name = clean_invisible_chars(cat['category_name'])
                category_id = f'{standard_id}-{category_name}'
                # 幂等INSERT语句（全量模式下分类已存在时不插入）
                sql = f"""insert into edsm_dataset_category(category_id, standard_id, parent_id, category_no, category_name, seq_no, is_del, created_at, modified_at) select '{category_id}', '{standard_id}', null, '{category_name}','{category_name}', (select count(1) from edsm_dataset_category)+1, 0, now(), null where not exists (select 1 from edsm_dataset_category where category_id = '{category_id}');"""
                f.write(sql + "\n")
                dml_count += 1
            f.write("\n")

        # ========== edsm_dataset（所有数据集）==========
        if new_tables:
            f.write("-- ========== edsm_dataset（所有数据集）==========\n\n")
            for ds in new_tables:
                dataset_no = clean_invisible_chars(ds['table_en'])
                dataset_name = clean_invisible_chars(ds['table_cn'])
                dataset_id = f'{standard_id}-{dataset_no}'
                category_name = clean_invisible_chars(ds.get('category_name', ''))
                category_id = f'{standard_id}-{category_name}' if category_name else None

                if category_id:
                    sql = f"""insert into edsm_dataset(dataset_id, standard_id, category_id, dataset_no, dataset_name, status, seq_no, is_del, created_at, modified_at) select '{dataset_id}','{standard_id}', '{category_id}', '{dataset_no}', '{dataset_name}', 1, (select count(1) from edsm_dataset)+1, 0, now(), null where not exists (select 1 from edsm_dataset where dataset_id = '{dataset_id}');"""
                else:
                    sql = f"""insert into edsm_dataset(dataset_id, standard_id, category_id, dataset_no, dataset_name, status, seq_no, is_del, created_at, modified_at) select '{dataset_id}','{standard_id}', null, '{dataset_no}', '{dataset_name}', 1, (select count(1) from edsm_dataset)+1, 0, now(), null where not exists (select 1 from edsm_dataset where dataset_id = '{dataset_id}');"""
                f.write(sql + "\n")
                dml_count += 1
            f.write("\n")

        # ========== edsm_dataset_element（所有数据集的所有字段）==========
        if new_tables:
            f.write("-- ========== edsm_dataset_element（所有数据集字段）==========\n\n")
            for sql in generate_new_table_elements_dml(new_tables, standard_id, doc_name):
                f.write(sql + "\n")
                dml_count += 1
            f.write("\n")

        # ========== edsm_metadata（元数据汇总）==========
        if include_metadata and new_tables:
            f.write("-- ========== edsm_metadata（元数据汇总）==========\n\n")
            for sql in generate_metadata_dml(parse_result, standard_id, doc_name):
                f.write(sql + "\n")
                dml_count += 1
            f.write("\n")

    return {
        'output_path': output_path,
        'dml_count': dml_count,
        'standard_id': standard_id,
        'new_categories': len(all_categories),
        'new_datasets': len(new_tables),
        'new_table_elements': sum(len(nt['fields']) for nt in new_tables),
        'new_elements': 0,  # 全量模式下无"已有表新增字段"概念
        'modified_elements': 0  # 全量模式下无"修改字段"概念
    }

def main():
    """主函数，用于命令行调用"""
    import sys
    import os
    import argparse

    parser = argparse.ArgumentParser(description='生成标准库DML同步脚本')
    parser.add_argument('doc_path', help='Word文档路径 (.docx)')
    parser.add_argument('--output', '-o', default=None, help='输出目录 (默认: ~/Downloads/)')
    parser.add_argument('--no-metadata', action='store_true', help='不生成metadata同步')

    args = parser.parse_args()

    # 导入解析器
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from word_parser import parse_word_document

    # 解析文档
    print(f"正在解析文档: {args.doc_path}")
    parse_result = parse_word_document(args.doc_path)

    # 确定输出目录
    output_dir = args.output if args.output else os.path.expanduser('~/.Downloads')
    os.makedirs(output_dir, exist_ok=True)

    # 生成输出文件名
    doc_name = os.path.basename(args.doc_path).replace('.docx', '').replace('.DOCX', '')
    output_filename = f'{doc_name}_DML.sql'
    output_path = os.path.join(output_dir, output_filename)

    # 生成DML
    result = generate_full_dml(
        parse_result,
        doc_name,
        output_path,
        include_metadata=not args.no_metadata
    )

    print(f"\n✓ DML脚本已生成")
    print(f"  输出文件: {result['output_path']}")
    print(f"  标准ID: {result['standard_id']}")
    print(f"  新增分类: {result['new_categories']} 个")
    print(f"  新增数据集: {result['new_datasets']} 个")
    print(f"  新增字段: {result['new_elements']} 个")
    print(f"  修改字段: {result['modified_elements']} 个")
    print(f"  DML总数: {result['dml_count']} 条")

if __name__ == '__main__':
    main()