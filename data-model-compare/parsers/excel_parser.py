#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Excel文档解析器
使用pandas和openpyxl解析Excel文档
"""

import os
import re
from typing import Dict, List
import pandas as pd
from .base import BaseParser, ParsedDocument, Table, Field


class ExcelParser(BaseParser):
    """Excel文档解析器"""

    def __init__(self, config: Dict = None):
        super().__init__(config)
        self.name = "excel_parser"

    def can_parse(self, file_path: str) -> bool:
        """判断是否可以解析该文件"""
        ext = self.get_file_extension(file_path)
        return ext in ['.xlsx', '.xls']

    def parse(self, file_path: str) -> ParsedDocument:
        """解析Excel文件"""
        try:
            import openpyxl
        except ImportError:
            raise ImportError("需要安装openpyxl: pip install openpyxl")

        parsed_doc = ParsedDocument(source_file=file_path)

        # 读取所有sheet
        excel_file = pd.ExcelFile(file_path)

        for sheet_name in excel_file.sheet_names:
            try:
                df = pd.read_excel(file_path, sheet_name=sheet_name)

                if df.empty:
                    continue

                # 解析表格
                table = self._parse_sheet(sheet_name, df)
                if table and table.fields:
                    parsed_doc.tables.append(table)

            except Exception as e:
                print(f"警告：解析sheet '{sheet_name}' 失败: {e}")
                continue

        return parsed_doc

    def _parse_sheet(self, sheet_name: str, df: pd.DataFrame) -> Table:
        """解析单个sheet"""
        # 创建表
        table = Table(name=sheet_name, comment=sheet_name)

        # 获取列名
        columns = df.columns.tolist()

        # 检测是否是数据标准表格
        field_indicators = ['字段', '数据元', '名称', '标识', '类型', '长度', '约束']
        header_match_count = sum(1 for col in columns if any(ind in str(col) for ind in field_indicators))

        # 如果表头匹配的字段少于2个，可能不是数据标准表格
        if header_match_count < 2:
            return None

        # 解析每一行
        for idx, row in df.iterrows():
            row_data = [str(val) if pd.notna(val) else "" for val in row]
            field = self._parse_field_row(columns, row_data)
            if field:
                table.fields.append(field)

        return table

    def _parse_field_row(self, headers: List[str], cells: List[str]) -> Field:
        """从表格行解析字段"""
        field_dict = {}

        for idx, header in enumerate(headers):
            if idx >= len(cells):
                break

            cell = cells[idx]
            header_str = str(header)

            # 识别数据元标识/英文名
            if '数据元标识' in header_str or '标识' in header_str or '英文名' in header_str or '字段名' in header_str:
                field_dict['name'] = cell.strip()

            # 识别数据元名称/中文名
            elif '数据元名称' in header_str or '名称' in header_str or '中文名' in header_str:
                comment = cell.strip()
                if comment.startswith('*'):
                    comment = comment[1:]
                    field_dict['constraint'] = 'M'
                field_dict['comment'] = comment

            # 识别约束
            elif '约束' in header_str or '必填' in header_str:
                constraint_str = cell.strip()
                if constraint_str == 'M' or '必填' in constraint_str:
                    field_dict['constraint'] = 'M'
                elif constraint_str == 'C' or '条件' in constraint_str:
                    field_dict['constraint'] = 'C'
                else:
                    field_dict['constraint'] = 'O'

            # 识别数据类型
            elif '数据类型' in header_str or '类型' in header_str:
                field_dict['field_type'] = cell.strip()

            # 识别表示格式/长度
            elif '表示格式' in header_str or '格式' in header_str or '长度' in header_str:
                length_str = cell.strip()
                match = re.search(r'(\d+)', length_str)
                if match:
                    field_dict['length'] = int(match.group(1))

            # 识别说明
            elif '说明' in header_str or '描述' in header_str:
                field_dict['description'] = cell.strip()

        # 必须有英文名
        if 'name' not in field_dict or not field_dict['name']:
            return None

        # 默认约束为O
        if 'constraint' not in field_dict:
            field_dict['constraint'] = 'O'

        return Field(
            name=field_dict.get('name', ''),
            comment=field_dict.get('comment', ''),
            field_type=field_dict.get('field_type', ''),
            length=field_dict.get('length', 0),
            constraint=field_dict.get('constraint', 'O'),
            description=field_dict.get('description', '')
        )
