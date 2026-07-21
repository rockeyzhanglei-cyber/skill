#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
标准化文档解析器
从MD文件中提取表结构、字段信息和值域，输出标准化格式
"""

import os
import re
import json
import yaml
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict


@dataclass
class ValueDomain:
    """值域定义"""
    code: str
    name: str
    description: str = ""


@dataclass
class StandardField:
    """标准化字段定义"""
    name: str  # 英文名
    chinese_name: str  # 中文名
    data_type: str  # 数据类型（S/N/D等）
    length: int  # 长度
    constraint: str  # 约束（M/C/O）
    description: str = ""  # 说明
    value_domains: List[ValueDomain] = None  # 值域列表
    data_element_id: str = ""  # 数据元标识符
    format: str = ""  # 完整格式信息（如 AN..50）

    def __post_init__(self):
        if self.value_domains is None:
            self.value_domains = []


@dataclass
class StandardTable:
    """标准化表定义"""
    name: str  # 表名
    chinese_name: str  # 中文名
    description: str = ""  # 说明
    fields: List[StandardField] = None  # 字段列表

    def __post_init__(self):
        if self.fields is None:
            self.fields = []


@dataclass
class StandardDocument:
    """标准化文档"""
    source_file: str  # 源文件
    tables: List[StandardTable] = None  # 表列表
    metadata: Dict = None  # 元数据

    def __post_init__(self):
        if self.tables is None:
            self.tables = []
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'source_file': self.source_file,
            'tables': [
                {
                    'name': table.name,
                    'chinese_name': table.chinese_name,
                    'description': table.description,
                    'fields': [
                        {
                            'name': field.name,
                            'chinese_name': field.chinese_name,
                            'data_type': field.data_type,
                            'length': field.length,
                            'constraint': field.constraint,
                            'description': field.description,
                            'value_domains': [asdict(vd) for vd in field.value_domains],
                            'data_element_id': field.data_element_id,
                            'format': field.format
                        }
                        for field in table.fields
                    ]
                }
                for table in self.tables
            ],
            'metadata': self.metadata
        }

    def to_json(self, output_path: str):
        """输出为JSON文件"""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    def to_yaml(self, output_path: str):
        """输出为YAML文件"""
        with open(output_path, 'w', encoding='utf-8') as f:
            yaml.dump(self.to_dict(), f, allow_unicode=True, default_flow_style=False)


class StandardParser:
    """标准化文档解析器"""

    def __init__(self, config: dict = None):
        self.config = config or {}

    def parse(self, md_file: str) -> StandardDocument:
        """解析MD文件，提取标准化文档

        Args:
            md_file: MD文件路径

        Returns:
            标准化文档
        """
        with open(md_file, 'r', encoding='utf-8') as f:
            content = f.read()

        doc = StandardDocument(source_file=md_file)
        lines = content.split('\n')

        # 第一步：找出所有表格的位置
        table_positions = []
        for i, line in enumerate(lines):
            if line.strip().startswith('|') and i + 1 < len(lines) and '---' in lines[i + 1]:
                table_positions.append(i)

        # 第二步：解析每个表格，判断是否是有效表
        for table_start in table_positions:
            table = self._parse_table_from_position(lines, table_start)
            if table and table.fields:
                doc.tables.append(table)

        return doc

    def _parse_table_from_position(self, lines: List[str], table_start: int) -> Optional[StandardTable]:
        """从表格位置开始解析表格

        Args:
            lines: 所有行
            table_start: 表格起始行索引

        Returns:
            解析出的表，如果不是有效表则返回None
        """
        # 解析表头
        header_line = lines[table_start].strip()
        headers = [h.strip() for h in header_line.split('|')[1:-1]]

        # 检查是否是数据表（表头必须包含"字段"、"数据元"、"类型"等关键词）
        header_text = ' '.join(headers).lower()
        if not any(keyword in header_text for keyword in ['字段', '数据元', '类型', '长度', '约束', '填报']):
            return None

        # 过滤掉只有"字段名"、"填写说明"、"说明"的控制字段表格
        if len(headers) <= 3 and all(h in ['字段名', '填写说明', '说明'] for h in headers):
            return None

        # 跳过分隔行
        i = table_start + 1
        if i < len(lines) and '---' in lines[i]:
            i += 1

        # 反向查找最近的标题作为表名
        heading_text = self._find_nearest_heading(lines, table_start)

        # 过滤掉非数据表
        skip_keywords = ['控制字段', '填写说明', '数据类型', '数据格式', '数据类型表示',
                        '数据上传顺序', '数据上传至前置机', '门急诊数据上传',
                        '住院数据上传', '体检数据上传',
                        '字符类型', '数值类型', '日期与时间类型',
                        '数据元属性解释']
        if any(keyword in heading_text for keyword in skip_keywords):
            return None

        # 拆分标题为中文名和英文名
        # 常见格式：
        #   "患者基本信息表 JBBRJBXXB" → chinese="患者基本信息表", name="JBBRJBXXB"
        #   "门(急)诊病历 EMR_MJZBL" → chinese="门(急)诊病历", name="EMR_MJZBL"
        #   "检查记录表 JCJLB" → chinese="检查记录表", name="JCJLB"
        table_name, table_chinese = self._split_table_name(heading_text)

        # 解析数据行
        table = StandardTable(
            name=table_name,
            chinese_name=table_chinese
        )

        while i < len(lines) and lines[i].strip().startswith('|'):
            row_line = lines[i].strip()
            cells = [c.strip() for c in row_line.split('|')[1:-1]]

            if len(cells) >= len(headers):
                field = self._parse_field(headers, cells)
                if field:
                    table.fields.append(field)

            i += 1

        # 如果没有解析到字段，返回None
        if not table.fields:
            return None

        return table

    def _find_nearest_heading(self, lines: List[str], table_start: int) -> str:
        """反向查找最近的标题作为表名

        Args:
            lines: 所有行
            table_start: 表格起始行索引

        Returns:
            最近的标题文本
        """
        # 从表格位置向上查找，找到最近的标题（任何级别）
        for i in range(table_start - 1, -1, -1):
            line = lines[i].strip()
            # 查找任何级别的标题（# 开头）
            if line.startswith('#'):
                # 提取标题文本（去掉 # 和空格）
                heading_text = line.lstrip('#').strip()
                return heading_text

        # 如果没找到标题，使用默认名称
        return f"表 {table_start}"

    @staticmethod
    def _split_table_name(heading: str) -> tuple:
        """拆分标题为英文名和中文名

        常见格式：
            "患者基本信息表 JBBRJBXXB" → ("JBBRJBXXB", "患者基本信息表")
            "门(急)诊病历 EMR_MJZBL" → ("EMR_MJZBL", "门(急)诊病历")
            "检查记录表 JCJLB" → ("JCJLB", "检查记录表")
            "西医病案首页 BA_SYJBK" → ("BA_SYJBK", "西医病案首页")

        Args:
            heading: 标题文本

        Returns:
            (table_name, chinese_name) 元组
            - table_name: 英文表名（如 JBBRJBXXB）；如果找不到英文名，使用完整标题
            - chinese_name: 中文表名（去掉英文部分）
        """
        if not heading:
            return ('', '')

        # 策略1：查找末尾的纯英文/数字/下划线标识符
        # 匹配模式：中文 + 空格 + 英文标识符
        match = re.search(r'^(.+?)\s+([A-Za-z][A-Za-z0-9_]*)\s*$', heading)
        if match:
            chinese = match.group(1).strip()
            english = match.group(2).strip()
            return (english, chinese)

        # 策略2：查找括号中的英文标识符
        # 例如 "门(急)诊病历(EMR_MJZBL)" → ("EMR_MJZBL", "门(急)诊病历")
        match = re.search(r'^(.+?)\(([A-Za-z][A-Za-z0-9_]*)\)\s*$', heading)
        if match:
            chinese = match.group(1).strip()
            english = match.group(2).strip()
            return (english, chinese)

        # 策略3：如果标题全部是英文/数字/下划线，则全部作为英文名
        if re.match(r'^[A-Za-z][A-Za-z0-9_]*$', heading):
            return (heading, '')

        # 无法拆分，全部作为中文名
        return (heading, heading)

    def _parse_field(self, headers: List[str], cells: List[str]) -> Optional[StandardField]:
        """解析单个字段"""
        field_dict = {}

        # 第一遍：提取所有可能的字段信息
        for idx, header in enumerate(headers):
            if idx >= len(cells):
                break

            cell = cells[idx]
            header_lower = header.lower()

            # 识别字段名（优先级：字段名 > 英文名 > 数据元标识符）
            if '字段名' in header or '英文名' in header or header == '字段名':
                field_dict['name'] = cell.strip()
            elif '标识' in header or '代码' in header:
                # 数据元标识符，作为备选
                if 'name' not in field_dict:
                    field_dict['name_backup'] = cell.strip()

            # 识别中文名
            elif '字段' == header or '中文名' in header or '数据元名称' in header or ('名称' in header and '数据元' not in header):
                chinese_name = cell.strip()
                if chinese_name.startswith('*'):
                    chinese_name = chinese_name[1:]
                    field_dict['constraint'] = 'M'
                field_dict['chinese_name'] = chinese_name

            # 识别数据类型
            elif '类型' in header or '数据类型' in header:
                field_dict['data_type'] = cell.strip()

            # 识别长度
            elif '长度' in header or '格式' in header or '表示格式' in header:
                length_str = cell.strip()
                # 保存完整的格式信息
                field_dict['format'] = length_str
                # 同时提取数字作为 length（向后兼容）
                match = re.search(r'(\d+)', length_str)
                if match:
                    field_dict['length'] = int(match.group(1))

            # 识别约束
            elif '约束' in header or '填报' in header or '必填' in header:
                constraint_str = cell.strip()
                if '必填' in constraint_str or constraint_str == 'M':
                    field_dict['constraint'] = 'M'
                elif '有则必填' in constraint_str or '条件' in constraint_str or constraint_str == 'C':
                    field_dict['constraint'] = 'C'
                else:
                    field_dict['constraint'] = 'O'

            # 识别说明
            elif '说明' in header or '描述' in header:
                field_dict['description'] = cell.strip()

            # 识别数据元标识符
            elif '数据元' in header and '标识符' in header:
                field_dict['data_element_id'] = cell.strip()

            # 识别值域
            elif '值域' in header or '字典' in header:
                field_dict['value_domain_str'] = cell.strip()

        # 如果主字段名为空，使用备选字段名
        if 'name' not in field_dict or not field_dict['name']:
            if 'name_backup' in field_dict:
                field_dict['name'] = field_dict['name_backup']

        # 必须有字段名
        if 'name' not in field_dict or not field_dict['name']:
            return None

        # 默认值
        if 'constraint' not in field_dict:
            field_dict['constraint'] = 'O'
        if 'length' not in field_dict:
            field_dict['length'] = 0

        # 解析值域
        value_domains = []
        if 'value_domain_str' in field_dict:
            value_domains = self._parse_value_domains(field_dict['value_domain_str'])

        return StandardField(
            name=field_dict.get('name', ''),
            chinese_name=field_dict.get('chinese_name', ''),
            data_type=field_dict.get('data_type', ''),
            length=field_dict.get('length', 0),
            constraint=field_dict.get('constraint', 'O'),
            description=field_dict.get('description', ''),
            value_domains=value_domains,
            data_element_id=field_dict.get('data_element_id', ''),
            format=field_dict.get('format', '')
        )

    def _parse_value_domains(self, value_domain_str: str) -> List[ValueDomain]:
        """解析值域字符串"""
        value_domains = []

        if not value_domain_str:
            return value_domains

        # 尝试分割值域（分号、逗号、换行等）
        parts = re.split(r'[;；,，\n]', value_domain_str)

        for part in parts:
            part = part.strip()
            if not part:
                continue

            # 尝试解析为 code-name 格式
            match = re.match(r'(\S+)[\s:：\-]+(.+)', part)
            if match:
                code = match.group(1).strip()
                name = match.group(2).strip()
                value_domains.append(ValueDomain(code=code, name=name))
            else:
                # 如果没有分隔符，整个作为名称
                value_domains.append(ValueDomain(code=part, name=part))

        return value_domains
