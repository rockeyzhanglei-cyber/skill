#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
匹配策略基类

所有匹配策略都继承 MatchStrategy 基类，实现 match() 方法。
策略通过配置注册，支持热插拔。
"""

from abc import ABC, abstractmethod
from typing import Optional, Tuple, Dict


class MatchStrategy(ABC):
    """匹配策略基类

    子类必须实现:
    - name: 策略名称
    - priority: 优先级（数字越小越先执行）
    - match(): 匹配逻辑
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """策略名称，如 'exact_chinese', 'synonym' 等"""
        ...

    @property
    @abstractmethod
    def priority(self) -> int:
        """优先级，数字越小越先执行"""
        ...

    @abstractmethod
    def match(self, target_field, source_fields: dict, context: dict) -> Optional[Tuple]:
        """尝试匹配

        Args:
            target_field: 目标字段 (StandardField)
            source_fields: 源字段索引 {field_name: StandardField}
            context: 上下文信息，包含:
                - kb_manager: KnowledgeBaseManager
                - compatibility_engine: CompatibilityEngine
                - source_table: 当前源表
                - source_table_index: 所有源表索引
                - config: 匹配配置

        Returns:
            (source_field, match_type) 或 None（未匹配）
        """
        ...
