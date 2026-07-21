#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
字段兼容性规则引擎

将 _is_description_compatible 中的硬编码规则配置化。
每条规则定义一对"不应该匹配"的语义冲突场景。

支持规则类型:
- keyword_check: 关键词组合检查
- prefix_check: 前缀提取后比较
- granularity_check: 粒度级别检查
- precision_check: 精度检查（如日期 vs 日期时间）
"""

import os
import yaml
from typing import Dict, List, Optional, Tuple


class CompatibilityRule:
    """单条兼容性规则"""

    def __init__(self, name: str, config: dict):
        self.name = name
        self.priority = config.get('priority', 0)
        self.enabled = config.get('enabled', True)
        self.rule_type = config.get('type', 'keyword_check')
        self.action = config.get('action', 'reject')
        self.description = config.get('description', '')
        self.note = config.get('note', '')
        self.config = config

    def check(self, target_field, source_field) -> bool:
        """检查两个字段是否兼容

        Returns:
            True = 兼容（通过此规则），False = 不兼容（被此规则拒绝）
        """
        if not self.enabled:
            return True

        if self.rule_type == 'keyword_check':
            return self._keyword_check(target_field, source_field)
        elif self.rule_type == 'prefix_check':
            return self._prefix_check(target_field, source_field)
        elif self.rule_type == 'granularity_check':
            return self._granularity_check(target_field, source_field)
        elif self.rule_type == 'precision_check':
            return self._precision_check(target_field, source_field)
        return True

    def _keyword_check(self, target_field, source_field) -> bool:
        """关键词组合检查"""
        target_cn = target_field.chinese_name or ''
        source_cn = source_field.chinese_name or ''
        target_name = (target_field.name or '').lower()
        source_name = (source_field.name or '').lower()

        conditions = self.config.get('conditions', [])
        for cond in conditions:
            if self._match_condition(cond, target_cn, source_cn, target_name, source_name,
                                     target_field, source_field):
                return False  # 命中条件，不兼容
        return True

    def _match_condition(self, cond: dict, target_cn: str, source_cn: str,
                          target_name: str, source_name: str,
                          target_field=None, source_field=None) -> bool:
        """检查单个条件是否命中"""
        # target_has_any: 目标字段必须包含其中任一关键词
        target_has = cond.get('target_has_any', [])
        if target_has:
            target_match = any(kw in target_cn or kw in target_name for kw in target_has)
            if not target_match:
                return False

        # source_has_any: 源字段必须包含其中任一关键词
        source_has = cond.get('source_has_any', [])
        if source_has:
            source_match = any(kw in source_cn or kw in source_name for kw in source_has)
            if not source_match:
                return False

        # target_not_has_any: 目标字段不应包含其中任一关键词
        target_not_has = cond.get('target_not_has_any', [])
        if target_not_has:
            if any(kw in target_cn or kw in target_name for kw in target_not_has):
                return False

        # source_not_has_any: 源字段不应包含其中任一关键词
        source_not_has = cond.get('source_not_has_any', [])
        if source_not_has:
            if any(kw in source_cn or kw in source_name for kw in source_not_has):
                return False

        # target_has_attr_any: 目标字段包含属性关键词（如出生地的属性）
        target_has_attr = cond.get('target_has_attr_any', [])
        if target_has_attr:
            if not any(kw in target_cn for kw in target_has_attr):
                return False

        # target_not_has_attr_any
        target_not_has_attr = cond.get('target_not_has_attr_any', [])
        if target_not_has_attr:
            if any(kw in target_cn for kw in target_not_has_attr):
                return False

        # source_has_attr_any
        source_has_attr = cond.get('source_has_attr_any', [])
        if source_has_attr:
            if not any(kw in source_cn for kw in source_has_attr):
                return False

        # source_not_has_attr_any
        source_not_has_attr = cond.get('source_not_has_attr_any', [])
        if source_not_has_attr:
            if any(kw in source_cn for kw in source_not_has_attr):
                return False

        return True

    def _prefix_check(self, target_field, source_field) -> bool:
        """前缀提取后比较（如电话字段的前缀）"""
        target_cn = target_field.chinese_name or ''
        source_cn = source_field.chinese_name or ''

        trigger_keywords = self.config.get('trigger_keywords', [])
        extract_before = self.config.get('extract_before', '')

        # 检查是否触发
        target_triggered = any(kw in target_cn for kw in trigger_keywords)
        source_triggered = any(kw in source_cn for kw in trigger_keywords)

        if not (target_triggered and source_triggered):
            return True  # 至少一方不包含触发关键词，不适用此规则

        # 提取前缀
        if extract_before:
            target_prefix = target_cn.split(extract_before)[0].strip() if extract_before in target_cn else ''
            source_prefix = source_cn.split(extract_before)[0].strip() if extract_before in source_cn else ''
        else:
            target_prefix = target_cn
            source_prefix = source_cn

        # 前缀不同则不兼容
        if target_prefix != source_prefix:
            return False

        return True

    def _granularity_check(self, target_field, source_field) -> bool:
        """粒度级别检查（如行政区划代码的粒度）"""
        target_cn = target_field.chinese_name or ''
        source_cn = source_field.chinese_name or ''

        granularity_levels = self.config.get('granularity_levels', [])
        trigger_keywords = self.config.get('trigger_keywords', [])

        # 检查源字段是否包含触发关键词
        source_triggered = any(kw in source_cn for kw in trigger_keywords)
        if not source_triggered:
            return True

        # 检查目标是否有特定粒度
        target_has_granularity = any(kw in target_cn for kw in granularity_levels)
        source_has_granularity = any(kw in source_cn for kw in granularity_levels)

        if target_has_granularity and not source_has_granularity:
            # 目标有特定粒度但源没有，不兼容
            return False

        return True

    def _precision_check(self, target_field, source_field) -> bool:
        """精度检查（日期 vs 日期时间）"""
        target_cn = target_field.chinese_name or ''
        source_cn = source_field.chinese_name or ''

        date_keywords = self.config.get('date_keywords', [])
        time_keywords = self.config.get('time_keywords', [])
        date_types = [t.lower() for t in self.config.get('date_types', [])]
        datetime_types = [t.lower() for t in self.config.get('datetime_types', [])]

        target_has_time = any(kw in target_cn for kw in time_keywords) or \
                          (target_field.data_type or '').lower() in datetime_types
        source_has_time = any(kw in source_cn for kw in time_keywords) or \
                          (source_field.data_type or '').lower() in datetime_types
        target_is_date_only = any(kw in target_cn for kw in date_keywords) and \
                              (target_field.data_type or '').lower() in date_types
        source_is_date_only = any(kw in source_cn for kw in date_keywords) and \
                              (source_field.data_type or '').lower() in date_types

        # 一个是日期时间，另一个只是日期，不兼容
        if target_has_time and source_is_date_only:
            return False
        if target_is_date_only and source_has_time:
            return False

        return True


class CompatibilityEngine:
    """兼容性规则引擎

    从 YAML 配置文件加载规则，按优先级排序执行。
    支持动态添加、禁用规则。

    使用方式：
        engine = CompatibilityEngine(skill_dir)
        is_compatible, rule_name = engine.is_compatible(target_field, source_field)
    """

    def __init__(self, skill_dir: str):
        self.skill_dir = skill_dir
        self.rules: List[CompatibilityRule] = []
        self._load_rules()

    def _load_rules(self):
        """从 YAML 加载规则"""
        config_path = os.path.join(self.skill_dir, 'knowledge_base', 'compatibility_rules.yaml')
        if not os.path.exists(config_path):
            return

        with open(config_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        if not data:
            return

        for name, config in data.get('compatibility_rules', {}).items():
            self.rules.append(CompatibilityRule(name, config))

        # 按优先级排序（高优先级先执行）
        self.rules.sort(key=lambda r: r.priority, reverse=True)

    def is_compatible(self, target_field, source_field) -> Tuple[bool, Optional[str]]:
        """检查两个字段是否兼容

        Returns:
            (is_compatible, rule_name): 是否兼容，以及命中（拒绝）的规则名
        """
        for rule in self.rules:
            if not rule.check(target_field, source_field):
                return False, rule.name
        return True, None

    def add_rule(self, name: str, config: dict):
        """动态添加规则"""
        rule = CompatibilityRule(name, config)
        self.rules.append(rule)
        self.rules.sort(key=lambda r: r.priority, reverse=True)

    def disable_rule(self, name: str):
        """禁用某条规则"""
        for rule in self.rules:
            if rule.name == name:
                rule.enabled = False
                return True
        return False

    def enable_rule(self, name: str):
        """启用某条规则"""
        for rule in self.rules:
            if rule.name == name:
                rule.enabled = True
                return True
        return False

    def get_rule(self, name: str) -> Optional[CompatibilityRule]:
        """获取指定规则"""
        for rule in self.rules:
            if rule.name == name:
                return rule
        return None

    def list_rules(self) -> List[dict]:
        """列出所有规则概要"""
        return [
            {
                'name': r.name,
                'priority': r.priority,
                'enabled': r.enabled,
                'type': r.rule_type,
                'description': r.description,
            }
            for r in self.rules
        ]
