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

        # 检查是否是数据表（稳健判定：含"命名/标识列" 且 含"类型/长度列"）
        # 自治区格式：序号|数据元标识符|字段编码|字段名称|主键|非空|数据类型|长度|说明
        # 乌鲁木齐格式A：数据元标识符|数据项|字段名|类型|长度|填报要求|说明
        # 乌鲁木齐格式B：字段|字段名|类型|长度|填报要求|说明（无数据元标识符列）
        header_text = ' '.join(headers)
        naming_keywords = ['数据元标识符', '字段编码', '字段名称', '数据项',
                           '字段名', '英文名', '标识符']
        type_keywords = ['类型', '长度', '数据类型']
        has_naming = any(k in header_text for k in naming_keywords)
        has_type = any(k in header_text for k in type_keywords)
        if not (has_naming and has_type):
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

        # 解析数据行（支持跨页/跨空白断开的碎片合并）
        # 转换器把大表切成非常规结构：表头后每个数据行都紧跟一个 "| --- |" 分隔行，
        # 且跨页处会重复出现「表头 + 分隔行」。处理规则：
        #   1) 纯分隔行（| --- |...）直接跳过，不能当数据行解析；
        #   2) 与首表头列结构相同的「重复表头」→ 跳过表头+分隔行，继续吃后续数据；
        #   3) 列结构不同、且确为表头签名（含“数据元标识符/字段名”列头）的行 → 进入下一张表，停止；
        #   4) 数据行后即便紧跟 “| --- |” 也按普通数据行正常解析（不 break）。
        table = StandardTable(
            name=table_name,
            chinese_name=table_chinese
        )

        code_marker_re = re.compile(r'(?:★\s*)?([A-Za-z_][A-Za-z0-9_]*)\s*\[(.*?)\]')
        base_headers = [h for h in headers if h]
        consumed_any = False
        while i < len(lines):
            l = lines[i].strip()
            if not l.startswith('|'):
                # 非表格行：空白/页眉页脚；遇到新表名标题（# 标题 或 CODE[名] 标记）则本表结束
                # 注意：同一标准内所有表的表头列结构可能完全相同（如乌鲁木齐统一为
                # “数据元标识符|数据项|字段名|类型|长度|填报要求|说明”），不能靠表头
                # 列结构区分“跨页重复表头”与“下一张表的表头”，必须以表名标题为边界。
                if l.startswith('#') or code_marker_re.search(l):
                    break
                i += 1
                continue
            row_cells = [c.strip() for c in l.split('|')[1:-1]]
            # 1) 纯分隔行（与表头等列数且单元格全为 - / : / 空格）→ 跳过
            is_sep_row = bool(row_cells) and len(row_cells) == len(base_headers) \
                and all(re.fullmatch(r'[-\s:]+', c) for c in row_cells)
            if is_sep_row:
                i += 1
                continue
            row_headers = [c for c in row_cells if c]
            is_sep_next = (i + 1 < len(lines) and '---' in lines[i + 1])
            # 2) 重复表头（列结构与首表头相同）→ 跳过表头 + 分隔行
            if is_sep_next and row_headers == base_headers:
                i += 2
                continue
            # 3) 不同列结构且确为表头签名 → 下一张表，停止
            if is_sep_next and row_headers and row_headers != base_headers \
                    and ('数据元标识符' in l or '字段名' in l):
                break
            # 4) 普通数据行
            if len(row_cells) >= len(headers):
                field = self._parse_field(headers, row_cells)
                if field:
                    table.fields.append(field)
                    consumed_any = True
            i += 1

        # 如果没有解析到字段，返回None
        if not table.fields:
            return None

        return table

    def _find_nearest_heading(self, lines: List[str], table_start: int) -> str:
        """反向查找最近的标题作为表名

        支持两类表名标记：
        1. Markdown 标题（# 开头），如 "# 患者基本信息表 JBBRJBXXB"
        2. 段落式 CODE[中文名] 标记（自治区标准常见，可能带 ★ 或章节号前缀），
           如 "5.1  ★BASEINFO[个人基本信息]" 或 "5.4  BASEINFO_BLOODTRANS[个人基本信息_输血史]"

        Args:
            lines: 所有行
            table_start: 表格起始行索引

        Returns:
            最近的标题文本
        """
        # CODE[中文名] 标记（英文表码 + 中文名，可能带 ★ / 章节号前缀）
        code_marker = re.compile(r'(?:★\s*)?([A-Za-z_][A-Za-z0-9_]*)\s*\[(.*?)\]')
        heading_text = None
        code_name = None
        for i in range(table_start - 1, -1, -1):
            line = lines[i].strip()
            if not line:
                continue
            # 遇到表内容行（| 开头）继续上翻，可能跨过被断开的表片段
            if line.startswith('|'):
                continue
            # 优先使用 Markdown 标题
            if line.startswith('#'):
                heading_text = line.lstrip('#').strip()
                break
            # 段落式 CODE[中文名] 标记
            m = code_marker.search(line)
            if m:
                code_name = (m.group(1).strip(), m.group(2).strip())
                break

        if heading_text:
            return heading_text
        if code_name:
            # 返回 "中文名 英文名" 形式，交给 _split_table_name 拆出 (英文名, 中文名)
            return f"{code_name[1]} {code_name[0]}"
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

            cell = cells[idx].strip()
            if not cell:
                continue

            # 英文名 / 字段编码（注意：必须用精确匹配，避免"字段编码"误命中"字段名"、
            # "字段名称"误命中"中文名"等子串问题）
            if '字段编码' in header or header == '字段名' or '英文名' in header:
                field_dict['name'] = cell
            # 中文名 / 字段名称 / 数据项 / 字段（乌鲁木齐「字段|字段名」表头，字段=中文名、字段名=英文名）
            elif '字段名称' in header or header == '数据项' or '中文名' in header \
                    or header == '数据元名称' or (header.endswith('名称') and '数据元' not in header) \
                    or header == '字段':
                cn = cell
                if cn.startswith('*'):
                    cn = cn[1:]
                    field_dict['constraint'] = 'M'
                field_dict['chinese_name'] = cn
            # 数据元标识符
            elif '数据元' in header and '标识符' in header:
                field_dict['data_element_id'] = cell
            # 数据类型
            elif '类型' in header or '数据类型' in header:
                field_dict['data_type'] = cell
            # 长度 / 格式
            elif '长度' in header or '格式' in header or '表示格式' in header:
                field_dict['format'] = cell
                match = re.search(r'(\d+)', cell)
                if match:
                    field_dict['length'] = int(match.group(1))
            # 主键
            elif '主键' in header:
                if cell in ('√', '是', 'Y', 'y', '1', 'true', 'TRUE'):
                    field_dict['primary_key'] = True
            # 非空 / 必填
            elif '非空' in header or '必填' in header:
                if cell in ('√', '是', 'Y', 'y', '1', 'M', 'true', 'TRUE'):
                    field_dict['constraint'] = 'M'
                elif cell in ('C', '条件', '有则必填'):
                    field_dict['constraint'] = 'C'
            # 约束 / 填报要求
            elif '约束' in header or '填报' in header:
                if cell == 'M' or '必填' in cell:
                    field_dict['constraint'] = 'M'
                elif '条件' in cell or '有则必填' in cell or cell == 'C':
                    field_dict['constraint'] = 'C'
                else:
                    field_dict['constraint'] = 'O'
            # 说明 / 描述
            elif '说明' in header or '描述' in header:
                field_dict['description'] = cell
            # 值域 / 字典
            elif '值域' in header or '字典' in header:
                field_dict['value_domain_str'] = cell

        # 兜底：无中文名但字段名本身含中文时，将中文字段名作为中文名
        # （解决新疆标准字段名即为中文、chinese_name 为空导致匹配器中文路径失效的问题）
        if not field_dict.get('chinese_name'):
            _nm = field_dict.get('name', '')
            if _nm and re.search(r'[一-鿿]', _nm):
                field_dict['chinese_name'] = _nm

        # 如果主字段名为空，降级使用数据元标识符作为字段名
        if 'name' not in field_dict or not field_dict.get('name'):
            if field_dict.get('data_element_id'):
                field_dict['name'] = field_dict['data_element_id']

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
