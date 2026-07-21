#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文档解析器基类
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class Field:
    """字段定义"""
    name: str  # 英文名
    comment: str  # 中文名
    field_type: str  # 数据类型
    length: int  # 长度
    constraint: str  # 约束（M/C/O）
    description: str = ""
    data_element_id: str = ""


@dataclass
class Table:
    """表定义"""
    name: str
    comment: str = ""
    fields: List[Field] = None

    def __post_init__(self):
        if self.fields is None:
            self.fields = []


@dataclass
class ParsedDocument:
    """解析后的文档"""
    source_file: str
    tables: List[Table] = None
    metadata: Dict = None

    def __post_init__(self):
        if self.tables is None:
            self.tables = []
        if self.metadata is None:
            self.metadata = {}


class BaseParser(ABC):
    """解析器基类"""

    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.name = self.__class__.__name__

    @abstractmethod
    def can_parse(self, file_path: str) -> bool:
        """判断是否可以解析该文件"""
        pass

    @abstractmethod
    def parse(self, file_path: str) -> ParsedDocument:
        """解析文件"""
        pass

    def get_file_extension(self, file_path: str) -> str:
        """获取文件扩展名"""
        import os
        _, ext = os.path.splitext(file_path)
        return ext.lower()
