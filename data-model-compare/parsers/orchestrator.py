#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
解析器编排器
管理多个解析器，自动选择合适的解析器
"""

import os
from typing import Dict, List, Optional
from .base import BaseParser, ParsedDocument
from .word_parser import WordParser
from .excel_parser import ExcelParser
from .markdown_parser import MarkdownParser


class ParserOrchestrator:
    """解析器编排器"""

    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.parsers = self._init_parsers()

    def _init_parsers(self) -> List[BaseParser]:
        """初始化解析器列表"""
        return [
            WordParser(self.config),
            ExcelParser(self.config),
            MarkdownParser(self.config),
        ]

    def parse(self, file_path: str) -> ParsedDocument:
        """解析文件，自动选择合适的解析器"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")

        # 查找合适的解析器
        for parser in self.parsers:
            if parser.can_parse(file_path):
                print(f"使用 {parser.name} 解析: {os.path.basename(file_path)}")
                return parser.parse(file_path)

        # 如果没有找到合适的解析器，抛出异常
        ext = os.path.splitext(file_path)[1].lower()
        raise ValueError(f"不支持的文件格式: {ext}")

    def parse_multiple(self, file_paths: List[str]) -> Dict[str, ParsedDocument]:
        """解析多个文件"""
        results = {}
        for file_path in file_paths:
            try:
                parsed_doc = self.parse(file_path)
                results[file_path] = parsed_doc
                print(f"✓ 解析成功: {os.path.basename(file_path)} - {len(parsed_doc.tables)} 张表")
            except Exception as e:
                print(f"✗ 解析失败: {os.path.basename(file_path)} - {e}")
        return results
