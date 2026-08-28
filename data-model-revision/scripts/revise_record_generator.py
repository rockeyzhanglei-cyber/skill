#!/usr/bin/env python3
"""
修订记录生成脚本
根据Word文档解析结果生成 edsm_revise_record 和 edsm_revise_detail 的INSERT脚本

使用方式：
    python revise_record_generator.py --doc-path <文档路径> --require-no <需求号> --output <输出路径>

输出：
    - 修订记录INSERT脚本（edsm_revise_record + edsm_revise_detail）
    - 修订摘要自动生成
"""

import os
import re
import json
import uuid
import argparse
from datetime import datetime
from docx import Document

# 导入reg-ddl-generator的解析器
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REG_DDL_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), '..', 'reg-ddl-generator', 'scripts')
if os.path.exists(REG_DDL_DIR):
    import sys
    sys.path.insert(0, REG_DDL_DIR)
    from word_parser import parse_word_document, clean_invisible_chars
else:
    # 如果reg-ddl-generator不存在，定义备用函数
    def clean_invisible_chars(text):
        if not text:
            return text
        invisible_chars = [
            '\u200b', '\u200c', '\u200d', '\u200e', '\u200f',
            '\u2060', '\u2061', '\u2062', '\u2063', '\u2064',
            '\u206a', '\u206b', '\u206c', '\u206d', '\u206e', '\u206f',
            '\ufeff', '\u00ad',
        ]
        result = text
        for char in invisible_chars:
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
    return 'winning-plat-01'


# 已知项目编码映射（与 model-revision.yaml 中 project_code.known_projects 保持同步）
KNOWN_PROJECT_CODES = {
    "001 深圳市罗湖区妇幼保健院": "PRJ-001-SZLH",
    "002 北京电子病历共享工程二期": "PRJ-002-BJDZ",
    "003 北京基层社区平台": "PRJ-003-BJJC",
    "004 郑州市区域平台项目": "PRJ-004-ZZ",
    "005 张家港市区域平台项目": "PRJ-005-ZJG",
    "006 盐都区区域平台项目": "PRJ-006-YD",
    "007 六合区区域平台项目": "PRJ-007-LH",
    "008 如东市区域平台项目": "PRJ-008-RD",
    "009 斗门区区域平台项目": "PRJ-009-DM",
    "010 浙江省电子健康档案项目": "PRJ-010-ZJ",
    "011 阳泉市区域平台项目": "PRJ-011-YQ",
    "012 汉中市区域平台项目": "PRJ-012-HZ",
    "013 武汉市疫情分析平台": "PRJ-013-WH",
    "014 安徽区域标准规范": "PRJ-014-AH",
    "015 岳阳市区域平台项目": "PRJ-015-YY",
    "016 马鞍山市区域平台项目": "PRJ-016-MAS",
}


def extract_project_code_from_path(doc_path):
    """从文档路径中提取项目编码

    项目化文档路径结构：.../02 标准规范（项目化）/{序号} {项目名}/...
    例如：/.../02 标准规范（项目化）/001 深圳市罗湖区妇幼保健院/第01部分：医疗服务.docx

    返回:
        (project_code, project_dir_name) 或 (None, None)
        project_code 格式: PRJ-{3位序号}-{大写简称}
    """
    # 匹配项目化目录模式：3位数字 + 空格 + 项目名
    match = re.search(r'[/\\](\d{3})\s+([^/\\]+)[/\\]', doc_path)
    if not match:
        return None, None

    seq = match.group(1)
    project_name = match.group(2).strip()
    dir_name = f"{seq} {project_name}"

    # 优先从已知映射中查找
    if dir_name in KNOWN_PROJECT_CODES:
        return KNOWN_PROJECT_CODES[dir_name], dir_name

    # 未命中时，用拼音首字母生成简称（取项目名中所有中文字符的首字母）
    # 这里返回 (None, dir_name)，让调用者提示用户确认
    return None, dir_name


def generate_project_code(seq, abbr):
    """生成项目编码

    Args:
        seq: 3位数字序号（如 "001"）
        abbr: 大写英文简称（如 "SZLH"）

    Returns:
        项目编码字符串，如 "PRJ-001-SZLH"
    """
    return f"PRJ-{seq}-{abbr}"


def generate_revise_summary(parse_result):
    """生成修订摘要

    字段项格式与批量排版以 `references/bms-script-spec.md`《注释规范》为准：
    - 新增表：表名中文[表名] - 新增表
    - 新增字段：表名中文[表名]新增字段：字段名中文[字段代码,填报要求,数据类型,表示格式]
    - 修改字段：表名中文[表名]修改字段：字段名中文[字段代码]（旧→新），每字段独立一行
    - 同表多字段顿号合一行
    """
    summary_lines = []

    # 新增表
    for nt in parse_result.get('new_tables', []):
        table_cn = clean_invisible_chars(nt['table_cn'])
        table_en = clean_invisible_chars(nt['table_en'])
        summary_lines.append(f"新增表：{table_cn}[{table_en}]")

    # 新增字段
    for change in parse_result.get('all_changes', []):
        table_cn = clean_invisible_chars(change['table_cn'])
        table_en = clean_invisible_chars(change['table_en'])
        field_strs = []
        for field in change['new_fields']:
            field_cn = clean_invisible_chars(field['field_cn'])
            field_en = clean_invisible_chars(field['field_en'])
            data_type = field['data_type']
            if field.get('length'):
                data_type = f"{data_type}({field['length']})"
            required_cn = field.get('required_cn', '应填')
            field_strs.append(f"{field_cn}[{field_en},{data_type},{required_cn}]")

        if field_strs:
            summary_lines.append(f"{table_cn}[{table_en}]新增字段：{','.join(field_strs)}")

    # 修改字段
    for mod in parse_result.get('modified_fields', []):
        table_cn = clean_invisible_chars(mod['table_cn'])
        table_en = clean_invisible_chars(mod['table_en'])
        for field in mod['modified_fields']:
            field_cn = clean_invisible_chars(field['field_cn'])
            field_en = clean_invisible_chars(field['field_en'])
            changed_cols = ', '.join(field['changed_columns'])
            summary_lines.append(f"{table_cn}[{table_en}]修改字段：{field_cn}[{field_en}] - 修改属性：{changed_cols}")

    return '\n'.join(summary_lines)


def generate_revise_record_insert(revise_id, standard_id, version, require_no, summary, is_standard=1, project_code=''):
    """生成edsm_revise_record的INSERT语句（单行格式）

    Args:
        revise_id: 修订记录ID
        standard_id: 标准ID
        version: 版本号
        require_no: 需求号
        summary: 修订摘要
        is_standard: 是否公版（1=公版, 0=项目化）
        project_code: 项目编码（is_standard=0时必填，如PRJ-001-SZLH）
    """
    published_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    created_at = published_at

    # 转义summary中的单引号；并把真实换行转成字面 \n，保证 INSERT 单行、DB 存储与头部 /* */ 清单逐字一致
    summary_escaped = summary.replace("'", "''") if summary else ''
    if summary_escaped:
        summary_escaped = summary_escaped.replace('\n', '\\n')

    # 项目化时加入project_code字段
    if is_standard == 0 and project_code:
        sql = f"insert into edsm_revise_record(revise_id,standard_id,version,require_no,summary,is_standard,project_code,published_at,is_upgraded,is_del,created_at)values('{revise_id}','{standard_id}','{version}','{require_no}','{summary_escaped}',{is_standard},'{project_code}','{published_at}',0,0,'{created_at}');"
    else:
        sql = f"insert into edsm_revise_record(revise_id,standard_id,version,require_no,summary,is_standard,published_at,is_upgraded,is_del,created_at)values('{revise_id}','{standard_id}','{version}','{require_no}','{summary_escaped}',{is_standard},'{published_at}',0,0,'{created_at}');"

    return sql


def generate_code_system_insert(revise_id, code_system_id, code_system_name, timestamp, definition=''):
    """生成codeSystem类型的修订明细INSERT语句

    Args:
        revise_id: 修订记录ID
        code_system_id: 值域ID（如CVA-0306）
        code_system_name: 值域名称
        definition: 值域定义
        timestamp: 时间戳

    Returns:
        INSERT语句
    """
    revise_detail_id = str(uuid.uuid4())
    business_code = 'codeSystem'
    business_id = code_system_id

    # 构建revise_after（edsm_code_system表字段）
    code_system_info = {
        "code_system_id": code_system_id,
        "namespace_id": "1",
        "code_system_no": code_system_id,
        "code_system_name": code_system_name,
        "definition": definition,
        "category": "CUSTOM",  # CVA类值域都是业务自定义部分
        "status": 1,
        "is_internal": 1,
        "is_del": 0,
        "created_at": timestamp,
        "modified_at": ""
    }
    revise_after_json = json.dumps(code_system_info, ensure_ascii=False).replace("'", "''")

    sql = f"insert into edsm_revise_detail(revise_detail_id,revise_id,business_code,business_id,revise_type_code,revise_before,revise_after,is_del,created_at)values('{revise_detail_id}','{revise_id}','{business_code}','{business_id}','add',null,'{revise_after_json}',0,'{timestamp}');"

    return sql


def generate_value_set_insert(revise_id, code_system_id, code_system_name, value_no, value_desc, timestamp, description=''):
    """生成valueSet类型的修订明细INSERT语句

    Args:
        revise_id: 修订记录ID
        code_system_id: 值域ID
        code_system_name: 值域名称
        value_no: 值编码
        value_desc: 值含义
        description: 值说明
        timestamp: 时间戳

    Returns:
        INSERT语句
    """
    revise_detail_id = str(uuid.uuid4())
    business_code = 'valueSet'
    business_id = f"{code_system_id}-{value_no}"

    # 构建revise_after（edsm_value_set表字段）
    value_info = {
        "value_id": business_id,
        "code_system_id": code_system_id,
        "code_system_no": code_system_id,
        "code_system_name": code_system_name,
        "value_no": value_no,
        "value_desc": value_desc,
        "description": description,
        "is_internal": 1,
        "status": 1,
        "is_del": 0,
        "created_at": timestamp,
        "modified_at": ""
    }
    revise_after_json = json.dumps(value_info, ensure_ascii=False).replace("'", "''")

    sql = f"insert into edsm_revise_detail(revise_detail_id,revise_id,business_code,business_id,revise_type_code,revise_before,revise_after,is_del,created_at)values('{revise_detail_id}','{revise_id}','{business_code}','{business_id}','add',null,'{revise_after_json}',0,'{timestamp}');"

    return sql


# ---- 数据元标识符(external_id) 自动生成（规则见 references/external-id-spec.md）----
_EXTERNAL_ID_INDEX = None


def load_external_id_index():
    """懒加载 Skill 内的 external_id_index.json（由 base_data 四表 CSV 全量构建）"""
    global _EXTERNAL_ID_INDEX
    if _EXTERNAL_ID_INDEX is None:
        p = os.path.join(SCRIPT_DIR, 'external_id_index.json')
        if os.path.exists(p):
            with open(p, encoding='utf-8') as f:
                _EXTERNAL_ID_INDEX = json.load(f)
    return _EXTERNAL_ID_INDEX


def compute_external_id(standard_id, dataset_code, element_seq_no):
    """按 external-id-spec.md 规则生成数据元标识符 external_id。

    HDS{standard_seq:02d}{category_seq:02d}.{dataset_seq:03d}.{element_seq:03d}
    返回 '' 表示索引缺失或查不到（不应发生于正常流程）。
    """
    idx = load_external_id_index()
    if not idx:
        return ''
    std_seq = idx.get('standards', {}).get(standard_id)
    ds = idx.get('datasets', {}).get(standard_id, {}).get(dataset_code)
    if std_seq is None or ds is None:
        return ''
    cat_seq = idx.get('categories', {}).get(standard_id, {}).get(ds.get('category_id'))
    if cat_seq is None:
        return ''
    def lp(n, w):
        return str(int(n)).zfill(w)
    return f"HDS{lp(std_seq, 2)}{lp(cat_seq, 2)}.{lp(ds['seq_no'], 3)}.{lp(element_seq_no, 3)}"


def generate_metadata_insert(revise_id, standard_id, element_id, metadata_name, definition,
                             data_type, representation_format, code_system_id='', allow='',
                             external_id='', timestamp=''):
    """生成metadata类型的修订明细INSERT语句（一对一：每个数据集元素一个元数据）

    metadata_id 与 metadata_code 均等于 element_id（数据集元素唯一标识），
    datasetElement.metadata_id 指向自己的 element_id，互不共用。

    Args:
        revise_id: 修订记录ID
        standard_id: 标准ID
        element_id: 数据集元素唯一标识（{standard_id}-{数据集代码}-{字段代码}）
        metadata_name: 数据元名称
        definition: 数据元定义
        data_type: 数据类型
        representation_format: 表示格式
        code_system_id: 值域ID
        allow: 允许值
        external_id: 外部ID（如HDS0223.001.186）
        timestamp: 时间戳

    Returns:
        INSERT语句
    """
    revise_detail_id = str(uuid.uuid4())
    business_code = 'metadata'
    business_id = element_id

    # 构建revise_after（edsm_metadata表字段）：metadata_id / metadata_code 均为 element_id
    metadata_info = {
        "metadata_id": element_id,
        "namespace_id": "1",
        "external_id": external_id,
        "metadata_code": element_id,
        "metadata_name": metadata_name,
        "definition": definition,
        "data_type": data_type,
        "representation_format": representation_format,
        "code_system_id": code_system_id,
        "allow": allow,
        "status": 1,
        "is_del": 0,
        "created_at": timestamp,
        "modified_at": ""
    }
    revise_after_json = json.dumps(metadata_info, ensure_ascii=False).replace("'", "''")

    sql = f"insert into edsm_revise_detail(revise_detail_id,revise_id,business_code,business_id,revise_type_code,revise_before,revise_after,is_del,created_at)values('{revise_detail_id}','{revise_id}','{business_code}','{business_id}','add',null,'{revise_after_json}',0,'{timestamp}');"

    return sql


def generate_dataset_element_insert(revise_id, dataset_id, element_code, element_name, definition,
                                    is_pk, notnull, data_type, representation_format, code_system_id='',
                                    allow='', seq_no='', metadata_id=None, internal_id='', timestamp=''):
    """生成datasetElement类型的修订明细INSERT语句（单行格式）

    Args:
        revise_id: 修订记录ID
        dataset_id: 数据集ID
        element_code: 数据集元素代码（字段名）
        element_name: 数据集元素名称
        definition: 数据集元素定义
        is_pk: 是否主键（0/1）
        notnull: 是否必填（0/1）
        data_type: 数据类型
        representation_format: 表示格式
        code_system_id: 值域ID
        allow: 允许值
        seq_no: 顺序号
        metadata_id: 引用数据元唯一标识（默认=element_id，即一对一专属元数据）
        internal_id: 内部标识符
        timestamp: 时间戳

    Returns:
        INSERT语句
    """
    revise_detail_id = str(uuid.uuid4())
    business_code = 'datasetElement'
    business_id = f"{dataset_id}-{element_code}"
    # 一对一：未显式传入时，metadata_id 默认指向自己的 element_id
    metadata_id = metadata_id or business_id

    # 构建revise_after（edsm_dataset_element表字段）
    element_info = {
        "element_id": business_id,
        "dataset_id": dataset_id,
        "metadata_id": metadata_id,
        "internal_id": internal_id,
        "element_code": element_code,
        "element_name": element_name,
        "definition": definition,
        "is_pk": is_pk,
        "notnull": notnull,
        "data_type": data_type,
        "representation_format": representation_format,
        "code_system_id": code_system_id,
        "allow": allow,
        "status": 1,
        "seq_no": seq_no,
        "is_del": 0,
        "created_at": timestamp,
        "modified_at": ""
    }
    revise_after_json = json.dumps(element_info, ensure_ascii=False).replace("'", "''")

    sql = f"insert into edsm_revise_detail(revise_detail_id,revise_id,business_code,business_id,revise_type_code,revise_before,revise_after,is_del,created_at)values('{revise_detail_id}','{revise_id}','{business_code}','{business_id}','add',null,'{revise_after_json}',0,'{timestamp}');"

    return sql


def generate_revise_detail_inserts(revise_id, parse_result, standard_id):
    """生成edsm_revise_detail的INSERT语句列表

    针对每个变更生成一条修订明细：
    - 新增表 → business_code='dataset', revise_type_code='add'
    - 新增字段 → business_code='datasetElement', revise_type_code='add'
    - 修改字段 → business_code='datasetElement', revise_type_code='edit'

    注意：如果新增字段涉及新增值域，还需要生成codeSystem和valueSet类型的修订明细
    """
    inserts = []
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # 新增表
    for nt in parse_result.get('new_tables', []):
        dataset_no = clean_invisible_chars(nt['table_en'])
        dataset_id = f'{standard_id}-{dataset_no}'
        business_code = 'dataset'

        # 构建revise_after（新增表的完整信息）- 单行格式
        dataset_info = {
            "dataset_id": dataset_id,
            "standard_id": standard_id,
            "category_id": f'{standard_id}-{clean_invisible_chars(nt.get("category_name", ""))}' if nt.get("category_name") else "",
            "dataset_no": dataset_no,
            "dataset_name": clean_invisible_chars(nt['table_cn']),
            "status": 1,
            "is_del": 0,
            "created_at": timestamp,
            "modified_at": ""
        }
        revise_after_json = json.dumps(dataset_info, ensure_ascii=False).replace("'", "''")

        sql = f"insert into edsm_revise_detail(revise_detail_id,revise_id,business_code,business_id,revise_type_code,revise_before,revise_after,is_del,created_at)values('{str(uuid.uuid4())}','{revise_id}','{business_code}','{dataset_id}','add',null,'{revise_after_json}',0,'{timestamp}');"
        inserts.append(sql)

        # 新增表的所有字段也需要生成修订明细
        for idx, field in enumerate(nt.get('fields', []), 1):
            element_code = clean_invisible_chars(field['field_en'])
            element_name = clean_invisible_chars(field['field_cn'])
            definition = clean_invisible_chars(field.get('comment', ''))
            element_id = f"{dataset_id}-{element_code}"
            # 按 external-id-spec.md 规则自动生成数据元标识符（新增表元素 seq 从 1 起）
            external_id = compute_external_id(standard_id, dataset_no, idx)

            # 一对一：每个数据集元素生成一个专属元数据（metadata_id = element_id）
            inserts.append(generate_metadata_insert(
                revise_id=revise_id,
                standard_id=standard_id,
                element_id=element_id,
                metadata_name=element_name,
                definition=definition,
                data_type=field.get('data_type_value', field.get('data_type', '')),
                representation_format=field.get('format_value', ''),
                code_system_id=field.get('code_system_id', ''),
                external_id=external_id,
                timestamp=timestamp
            ))

            sql = generate_dataset_element_insert(
                revise_id=revise_id,
                dataset_id=dataset_id,
                element_code=element_code,
                element_name=element_name,
                definition=definition,
                is_pk=field.get('is_pk', 0),
                notnull=1 if field.get('required_cn') == '必填' else 0,
                data_type=field.get('data_type_value', field.get('data_type', '')),
                representation_format=field.get('format_value', ''),
                code_system_id=field.get('code_system_id', ''),
                seq_no=str(idx),
                metadata_id=element_id,
                timestamp=timestamp
            )
            inserts.append(sql)

    # 新增字段（已有表新增字段）
    for change in parse_result.get('all_changes', []):
        dataset_no = clean_invisible_chars(change['table_en'])
        dataset_id = f'{standard_id}-{dataset_no}'

        # 已有表新增字段：元素序号 = 该数据集现有最大元素 seq_no + 本批序号
        base_seq = 0
        _eidx = load_external_id_index()
        if _eidx:
            base_seq = _eidx.get('datasets', {}).get(standard_id, {}).get(dataset_no, {}).get('max_element_seq', 0)
        for j, field in enumerate(change['new_fields']):
            element_code = clean_invisible_chars(field['field_en'])
            element_name = clean_invisible_chars(field['field_cn'])
            definition = clean_invisible_chars(field.get('comment', ''))
            element_id = f"{dataset_id}-{element_code}"
            element_seq = base_seq + (j + 1)
            # 按 external-id-spec.md 规则自动生成数据元标识符
            external_id = compute_external_id(standard_id, dataset_no, element_seq)

            # 一对一：每个数据集元素生成一个专属元数据（metadata_id = element_id）
            inserts.append(generate_metadata_insert(
                revise_id=revise_id,
                standard_id=standard_id,
                element_id=element_id,
                metadata_name=element_name,
                definition=definition,
                data_type=field.get('data_type_value', field.get('data_type', '')),
                representation_format=field.get('format_value', ''),
                code_system_id=field.get('code_system_id', ''),
                external_id=external_id,
                timestamp=timestamp
            ))

            sql = generate_dataset_element_insert(
                revise_id=revise_id,
                dataset_id=dataset_id,
                element_code=element_code,
                element_name=element_name,
                definition=definition,
                is_pk=0,
                notnull=1 if field.get('required_cn') == '必填' else 0,
                data_type=field.get('data_type_value', field.get('data_type', '')),
                representation_format=field.get('format_value', ''),
                code_system_id=field.get('code_system_id', ''),
                seq_no=str(element_seq),
                metadata_id=element_id,
                timestamp=timestamp
            )
            inserts.append(sql)

    # 修改字段
    for mod in parse_result.get('modified_fields', []):
        dataset_no = clean_invisible_chars(mod['table_en'])
        dataset_id = f'{standard_id}-{dataset_no}'

        for field in mod['modified_fields']:
            revise_detail_id = str(uuid.uuid4())
            element_code = clean_invisible_chars(field['field_en'])
            business_id = f'{dataset_id}-{element_code}'
            business_code = 'datasetElement'

            # 构建revise_after
            element_info = {
                "element_id": business_id,
                "dataset_id": dataset_id,
                "element_code": element_code,
                "element_name": clean_invisible_chars(field['field_cn']),
                "definition": clean_invisible_chars(field.get('comment', '')),
                "is_pk": 0,
                "notnull": 1 if field.get('required_cn') == '必填' else 0,
                "data_type": field.get('data_type_value', field.get('data_type', '')),
                "representation_format": field.get('format_value', ''),
                "code_system_id": field.get('code_system_id', ''),
                "status": 1,
                "is_del": 0,
                "created_at": timestamp,
                "modified_at": ""
            }

            # revise_before设为null（需要从现有数据查询）
            revise_after_json = json.dumps(element_info, ensure_ascii=False).replace("'", "''")

            sql = f"insert into edsm_revise_detail(revise_detail_id,revise_id,business_code,business_id,revise_type_code,revise_before,revise_after,is_del,created_at)values('{revise_detail_id}','{revise_id}','{business_code}','{business_id}','edit',null,'{revise_after_json}',0,'{timestamp}');"
            inserts.append(sql)

    return inserts


def generate_revise_script(doc_path, require_no, version, output_path, standard_id=None, is_standard=1, project_code=None):
    """生成完整的修订记录脚本

    参数:
        doc_path: Word文档路径
        require_no: 需求号
        version: 版本号
        output_path: 输出文件路径
        standard_id: 标准ID（可选，默认从文档名推断）
        is_standard: 是否公版（1=公版, 0=项目化）
        project_code: 项目编码（is_standard=0时必填；为None时自动从doc_path推断）

    返回:
        生成结果字典
    """
    # 解析文档
    if REG_DDL_DIR and os.path.exists(REG_DDL_DIR):
        parse_result = parse_word_document(doc_path)
    else:
        # 备用解析（简化版）
        parse_result = {'new_tables': [], 'all_changes': [], 'modified_fields': []}

    # 获取文档名
    doc_name = os.path.basename(doc_path).replace('.docx', '').replace('.DOCX', '')

    # 推断standard_id
    if not standard_id:
        standard_id = get_standard_prefix(doc_name)

    # 项目化时自动推断project_code
    if is_standard == 0 and not project_code:
        project_code, project_dir = extract_project_code_from_path(doc_path)
        if not project_code:
            print(f"⚠ 警告: 无法自动推断项目编码，项目目录: {project_dir}")
            print(f"  请通过 --project-code 参数手动指定，格式: PRJ-{{序号}}-{{简称}}")

    # 生成修订摘要
    summary = generate_revise_summary(parse_result)

    # 生成修订记录ID
    revise_id = str(uuid.uuid4())

    # 生成INSERT脚本
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open(output_path, 'w', encoding='utf-8') as f:
        # 文件头注释：统一 /* */ 编号清单（与配套 DDL 逐字一致），不写 -- 集合/需求/字段/说明 等辅助行
        f.write("/*\n")
        f.write(summary + "\n")
        f.write("*/\n\n")

        # edsm_revise_record（单行格式）
        record_sql = generate_revise_record_insert(
            revise_id, standard_id, version, require_no, summary,
            is_standard=is_standard, project_code=project_code or ''
        )
        f.write(record_sql + "\n\n")

        # edsm_revise_detail
        detail_inserts = generate_revise_detail_inserts(revise_id, parse_result, standard_id)
        for sql in detail_inserts:
            f.write(sql + "\n")

    # 返回统计信息
    new_tables_count = len(parse_result.get('new_tables', []))
    new_elements_count = sum(len(c['new_fields']) for c in parse_result.get('all_changes', []))
    modified_elements_count = sum(len(m['modified_fields']) for m in parse_result.get('modified_fields', []))
    new_table_elements_count = sum(len(nt['fields']) for nt in parse_result.get('new_tables', []))

    return {
        'output_path': output_path,
        'revise_id': revise_id,
        'standard_id': standard_id,
        'is_standard': is_standard,
        'project_code': project_code or '',
        'summary': summary,
        'record_count': 1,
        'detail_count': len(detail_inserts),
        'new_tables': new_tables_count,
        'new_elements': new_elements_count,
        'modified_elements': modified_elements_count,
        'new_table_elements': new_table_elements_count
    }


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='生成数据标准修订记录脚本')
    parser.add_argument('--doc-path', required=True, help='Word文档路径')
    parser.add_argument('--require-no', required=True, help='需求号')
    parser.add_argument('--version', default='6.0', help='版本号')
    parser.add_argument('--standard-id', default=None, help='标准ID（可选）')
    parser.add_argument('--is-standard', type=int, default=1, choices=[0, 1],
                        help='是否公版：1=公版（默认）, 0=项目化')
    parser.add_argument('--project-code', default=None,
                        help='项目编码（is_standard=0时填写，如PRJ-001-SZLH；不填则自动推断）')
    parser.add_argument('--output', default=None, help='输出路径（默认 ~/Downloads/）')

    args = parser.parse_args()

    # 确定输出路径
    if args.output:
        output_dir = args.output
    else:
        output_dir = os.path.expanduser('~/.Downloads')
    os.makedirs(output_dir, exist_ok=True)

    # 生成输出文件名
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    output_filename = f'V{timestamp}__insert_revise_record_{args.require_no}.sql'
    output_path = os.path.join(output_dir, output_filename)

    # 生成脚本
    print(f"正在解析文档: {args.doc_path}")
    print(f"版本类型: {'公版' if args.is_standard == 1 else '项目化'}")
    if args.is_standard == 0:
        print(f"项目编码: {args.project_code or '（自动推断）'}")
    result = generate_revise_script(
        args.doc_path,
        args.require_no,
        args.version,
        output_path,
        args.standard_id,
        is_standard=args.is_standard,
        project_code=args.project_code
    )

    print(f"\n✓ 修订记录脚本已生成")
    print(f"  输出文件: {result['output_path']}")
    print(f"  修订记录ID: {result['revise_id']}")
    print(f"  标准ID: {result['standard_id']}")
    print(f"  是否公版: {'是' if result['is_standard'] == 1 else '否'}")
    if result['is_standard'] == 0:
        print(f"  项目编码: {result['project_code']}")
    print(f"  修订摘要:\n{result['summary']}")
    print(f"\n统计:")
    print(f"  edsm_revise_record: {result['record_count']} 条")
    print(f"  edsm_revise_detail: {result['detail_count']} 条")
    print(f"  - 新增表: {result['new_tables']} 个（含 {result['new_table_elements']} 个字段）")
    print(f"  - 新增字段: {result['new_elements']} 个")
    print(f"  - 修改字段: {result['modified_elements']} 个")


if __name__ == '__main__':
    main()