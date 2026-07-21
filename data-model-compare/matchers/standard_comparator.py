#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
标准化文档比对器
基于标准化后的文档进行比对
"""

import json
import os
import re
import yaml
from collections import deque
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass, field
from parsers.standard_parser import StandardDocument, StandardTable, StandardField

# 引入缓存
from utils.cache import get_similarity_from_cache, put_similarity_to_cache


# ============================================================================
# 模块级工具函数：相似度计算、跨表关联、值域比对
# ============================================================================

def _calculate_similarity(name1: str, name2: str) -> float:
    """
    计算两个字段的相似度（编辑距离 + n-gram + 包含关系的加权公式）
    权重：编辑距离 0.4 + bigram Jaccard 0.4 + 包含关系 0.2

    带 LRU 缓存，避免重复计算。
    """
    if not name1 or not name2:
        return 0.0

    # 查缓存
    cached = get_similarity_from_cache(name1, name2)
    if cached is not None:
        return cached

    # 1. 编辑距离相似度
    edit_sim = 1 - (_edit_distance(name1, name2) / max(len(name1), len(name2), 1))

    # 2. 字符重叠相似度（2-gram Jaccard）
    ngram_sim = _ngram_similarity(name1, name2, n=2)

    # 3. 包含关系
    contain_sim = 0.9 if (name1 in name2 or name2 in name1) else 0.0

    result = edit_sim * 0.4 + ngram_sim * 0.4 + contain_sim * 0.2

    # 存缓存
    put_similarity_to_cache(name1, name2, result)

    return result


def _edit_distance(s1: str, s2: str) -> int:
    """计算编辑距离（Levenshtein距离）"""
    if len(s1) < len(s2):
        return _edit_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)

    previous_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]


def _ngram_similarity(s1: str, s2: str, n: int = 2) -> float:
    """计算n-gram Jaccard相似度"""
    if len(s1) < n or len(s2) < n:
        return 0.0
    ngrams1 = set(s1[i:i+n] for i in range(len(s1) - n + 1))
    ngrams2 = set(s2[i:i+n] for i in range(len(s2) - n + 1))
    intersection = ngrams1 & ngrams2
    union = ngrams1 | ngrams2
    return len(intersection) / len(union) if union else 0.0


def _load_relations(skill_dir: str) -> Dict:
    """从 relations/ 目录加载表关联关系

    返回格式:
    {
        'joins': [                          # SQL精度关联列表
            {'from': 'TABLE_A', 'to': 'TABLE_B',
             'conditions': [{'left': 'TABLE_A.field', 'right': 'TABLE_B.field'}, ...],
             'type': '1:N', 'note': '...'},
            ...
        ],
        'table_roles': {'角色名': '实际表名', ...},
        'key_mappings': {'业务概念': {'en': 'FIELD', 'cn': '中文名', ...}, ...},
        'adjacency': {'TABLE_A': [{'to': 'TABLE_B', 'conditions': [...], 'type': '1:N'}, ...], ...}
    }
    """
    relations_dir = os.path.join(skill_dir, 'knowledge_base', 'relations')
    if not os.path.isdir(relations_dir):
        return {'joins': [], 'table_roles': {}, 'key_mappings': {}, 'adjacency': {}}

    result = {'joins': [], 'table_roles': {}, 'key_mappings': {}, 'adjacency': {}}

    for filename in sorted(os.listdir(relations_dir)):
        if not filename.endswith('.yaml'):
            continue
        filepath = os.path.join(relations_dir, filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            if not data:
                continue

            # 加载 table_roles
            roles = data.get('table_roles', {})
            if roles:
                result['table_roles'].update(roles)

            # 加载 key_mappings
            keys = data.get('key_mappings', {})
            if keys:
                result['key_mappings'].update(keys)

            # 加载 joins 列表
            joins = data.get('joins', [])
            for j in joins:
                if not isinstance(j, dict) or not j.get('join'):
                    continue
                # 解析 join 条件
                conditions = []
                for cond_str in j['join']:
                    clean = cond_str.split('#')[0].strip()
                    if '=' not in clean:
                        continue
                    parts = clean.split('=')
                    if len(parts) == 2:
                        left = parts[0].strip()
                        right = parts[1].strip()
                        if '.' in left and '.' in right:
                            conditions.append({'left': left, 'right': right})

                if conditions:
                    join_entry = {
                        'from': j['from'],
                        'to': j['to'],
                        'conditions': conditions,
                        'type': j.get('type', ''),
                        'note': j.get('note', '')
                    }
                    result['joins'].append(join_entry)

                    # 构建邻接表（双向）
                    frm = j['from']
                    to = j['to']
                    if frm not in result['adjacency']:
                        result['adjacency'][frm] = []
                    if to not in result['adjacency']:
                        result['adjacency'][to] = []
                    result['adjacency'][frm].append({
                        'to': to, 'conditions': conditions, 'type': j.get('type', '')
                    })
                    result['adjacency'][to].append({
                        'to': frm, 'conditions': conditions, 'type': j.get('type', '')
                    })

        except Exception:
            pass

    return result


def _find_cross_table_paths(
    start_tables: List[str],
    target_field_name: str,
    target_field_cn: str,
    relations: Dict,
    source_tables: Dict[str, StandardTable],
    max_depth: int = 3
) -> List[Dict]:
    """BFS搜索跨表关联路径，找到能提供目标字段的表"""
    paths = []
    queue = deque()

    for table_name in start_tables:
        queue.append({
            'current_table': table_name,
            'path': [table_name],
            'join_keys': [],
            'visited': {table_name}
        })

    while queue:
        state = queue.popleft()
        current_table = state['current_table']

        # 检查当前表是否包含目标字段
        if current_table in source_tables:
            tbl = source_tables[current_table]
            for fld in tbl.fields:
                if (fld.name.lower() == target_field_name.lower() or
                    (target_field_cn and fld.chinese_name and
                     target_field_cn in fld.chinese_name)):
                    paths.append({
                        'path': state['path'],
                        'join_keys': state['join_keys'],
                        'field': fld.name
                    })
                    break

        # 深度限制
        if max_depth > 0 and len(state['path']) > max_depth:
            continue

        # 扩展关联表
        if current_table in relations:
            related = relations[current_table].get('related_tables', [])
            for rel in related:
                next_table = rel.get('table', '')
                join_key = rel.get('key', '')
                if next_table and next_table not in state['visited']:
                    queue.append({
                        'current_table': next_table,
                        'path': state['path'] + [next_table],
                        'join_keys': state['join_keys'] + [[(join_key, join_key)]],
                        'visited': state['visited'] | {next_table}
                    })

    return paths


@dataclass
class ValueDomainMatchResult:
    """值域匹配结果"""
    exact_matches: List[Dict] = field(default_factory=list)
    semantic_matches: List[Dict] = field(default_factory=list)
    uncertain: List[Dict] = field(default_factory=list)
    additions: List[Dict] = field(default_factory=list)
    mappings: List[Dict] = field(default_factory=list)


def _compare_value_domains_advanced(
    source_values: List[Dict],
    target_values: List[Dict],
    synonyms: Dict = None,
    similarity_threshold: float = 0.95,
    uncertain_lower_bound: float = 0.7
) -> ValueDomainMatchResult:
    """
    值域三层比对策略：精确 -> 词库语义 -> 相似度
    不确定区间（0.7~threshold）标记为需人工确认
    """
    if synonyms is None:
        synonyms = {}
    result = ValueDomainMatchResult()

    for target_val in target_values:
        target_code = target_val.get('code', '')
        target_name = target_val.get('name', '')
        matched = False

        # 第1层：精确匹配（编码+名称都相同）
        for source_val in source_values:
            if source_val.get('code') == target_code and source_val.get('name') == target_name:
                result.exact_matches.append({
                    'source': source_val, 'target': target_val,
                    'confidence': 1.0, 'match_type': 'exact'
                })
                matched = True
                break

        # 第2层：词库语义匹配
        if not matched:
            for source_val in source_values:
                source_name = source_val.get('name', '')
                if _is_in_synonym_dict(source_name, target_name, synonyms):
                    result.semantic_matches.append({
                        'source': source_val, 'target': target_val,
                        'confidence': 0.98, 'match_type': 'dictionary'
                    })
                    result.mappings.append({
                        'source_code': source_val.get('code', ''),
                        'target_code': target_code,
                        'source_name': source_name,
                        'target_name': target_name
                    })
                    matched = True
                    break

        # 第3层：相似度匹配
        if not matched:
            best_match, best_sim = None, 0.0
            for source_val in source_values:
                sim = _calculate_similarity(source_val.get('name', ''), target_name)
                if sim > best_sim:
                    best_sim = sim
                    best_match = source_val

            if best_sim >= similarity_threshold and best_match:
                result.semantic_matches.append({
                    'source': best_match, 'target': target_val,
                    'confidence': best_sim, 'match_type': 'similarity'
                })
                result.mappings.append({
                    'source_code': best_match.get('code', ''),
                    'target_code': target_code,
                    'source_name': best_match.get('name', ''),
                    'target_name': target_name
                })
                matched = True
            elif best_sim >= uncertain_lower_bound and best_match:
                # 不确定区间：标记为需人工确认
                result.uncertain.append({
                    'source': best_match, 'target': target_val,
                    'similarity': best_sim, 'action': 'need_manual_review'
                })

        # 未匹配，需要新增
        if not matched:
            result.additions.append({
                'target': target_val,
                'action': 'add_to_source',
                'reason': f'目标标准值域"{target_name}"在原标准中未找到匹配'
            })

    return result


def _is_in_synonym_dict(name1: str, name2: str, synonyms: Dict) -> bool:
    """检查两个名称是否在词库中是同义词"""
    if not name1 or not name2:
        return False
    if name1 == name2:
        return True
    if name1.replace(' ', '') == name2.replace(' ', ''):
        return True

    # 词库交集检查
    syn1 = set(synonyms.get(name1, []))
    syn2 = set(synonyms.get(name2, []))
    if syn1 & syn2:
        return True

    # 双向查找：name1 的同义词列表是否包含 name2
    for word, syn_list in synonyms.items():
        if isinstance(syn_list, list):
            if word in name1 or word in name2:
                for syn in syn_list:
                    if (syn in name1 and syn in name2):
                        return True

    # 包含关系
    if name1 in name2 or name2 in name1:
        return True

    return False


@dataclass
class CompareResult:
    """比对结果"""
    matched: List[Dict] = None  # 匹配的字段
    modified: List[Dict] = None  # 需要修改的字段
    new_fields: List[Dict] = None  # 需要新增的字段
    new_tables: List[Dict] = None  # 需要新增的表

    def __post_init__(self):
        if self.matched is None:
            self.matched = []
        if self.modified is None:
            self.modified = []
        if self.new_fields is None:
            self.new_fields = []
        if self.new_tables is None:
            self.new_tables = []


class StandardComparator:
    """标准化文档比对器

    实现5条核心原则：
    1. 覆盖原则：原标准必须覆盖目标标准的所有字段
    2. 约束保护：目标M→原标准必须M；目标O→原标准M/C/O均可
    3. 长度保护：原标准长度≥目标标准长度
    4. 值域覆盖：原标准值域必须覆盖目标标准（只能扩充，不能修改已有）
    5. 只增不减：不删除、不重命名原标准已有字段
    """

    def __init__(self, config: dict = None):
        self.config = config or {}

        # 读取配置中的匹配优先级
        fm_config = self.config.get('field_matching', {})
        self.match_priority = fm_config.get('match_priority', [
            'exact_chinese',      # 中文名精确匹配
            'exact_english',      # 英文名精确匹配
            'semantic_chinese',   # 中文语义匹配
            'cross_table',        # 跨表关联匹配
            'new_field',          # 新增字段
        ])

        # 读取同义词匹配配置
        cn_config = fm_config.get('chinese_synonym', {})
        self.use_synonym = cn_config.get('enabled', True) and cn_config.get('use_dictionary', True)
        self.use_similarity = cn_config.get('enabled', True) and cn_config.get('use_similarity', True)

        # 读取关键词匹配配置
        kw_config = fm_config.get('keyword_matching', {})
        self.use_keyword = kw_config.get('enabled', True)
        self.ngram_size = kw_config.get('ngram_size', 2)
        self.overlap_threshold = kw_config.get('overlap_threshold', 0.5)

        # 读取语义匹配阈值
        self.semantic_threshold = fm_config.get('semantic_threshold', 0.6)

        # 读取字典名称字段识别关键词
        dict_config = fm_config.get('dictionary_field', {})
        self.dictionary_name_keywords = dict_config.get('name_keywords', ['名称', 'name'])
        self.dictionary_code_keywords = dict_config.get('code_keywords', ['代码', '编码', '代号', '编号', 'code', 'id'])
        self.dictionary_exclude_patterns = dict_config.get('exclude_patterns', [
            'filename', 'username', 'tablename', 'hostname', 'database_name',
            'schema_name', 'column_name', 'field_name', 'class_name'
        ])

        # 读取约束保护配置
        cp_config = self.config.get('constraint_protection', {})
        cp_levels = cp_config.get('levels', {'M': 3, 'C': 2, 'O': 1})
        self.constraint_levels = cp_levels
        cp_rules = cp_config.get('rules', {})
        self.target_M_requires_source_M = cp_rules.get('target_M_requires_source_M', True)
        self.target_O_no_restriction = cp_rules.get('target_O_no_restriction', True)

        # 读取长度保护配置
        lp_config = self.config.get('length_protection', {})
        self.length_protection_enabled = lp_config.get('enabled', True)
        self.length_unit = lp_config.get('unit', 'char')

        # 读取值域匹配配置
        vd_config = self.config.get('value_domain_matching', {})
        self.vd_strategy = vd_config.get('strategy', 'conservative')
        self.vd_threshold = vd_config.get('similarity_threshold', 0.95)
        self.vd_uncertain_lower = vd_config.get('uncertain_lower_bound', 0.7)
        self.vd_semantic_priority = vd_config.get('semantic_priority', True)
        self.vd_auto_learn = vd_config.get('auto_learn', True)

        # 读取跨表关联配置
        ct_config = self.config.get('cross_table_relation', {})
        self.cross_table_max_depth = ct_config.get('max_depth', 3)
        self.cross_table_enabled = 'cross_table' in self.match_priority

        # ===== 使用 KnowledgeBaseManager 统一管理知识库 =====
        skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        from knowledge_base.manager import KnowledgeBaseManager
        self.kb = KnowledgeBaseManager(skill_dir)

        # 通过 kb 管理器访问知识库（保持原有接口兼容）
        self.table_mappings = self._load_table_mappings()
        self.synonyms = self.kb.synonyms
        self.synonym_exclude_list = getattr(self.kb, 'field_synonyms_exclude', []) or self.kb._cache.get('field_synonyms_exclude', [])
        self.table_synonyms = self.kb.table_synonyms
        self.field_mappings = self.kb.field_mappings
        self.numbered_field_groups = self.kb.numbered_field_groups
        self.relations = self.kb.relations

        # 加载用户自定义整表新增
        self.user_custom_new_tables = []
        user_kb = self.kb._cache.get('user_custom_mappings', {})
        if user_kb and 'new_tables' in user_kb:
            for nt in user_kb['new_tables']:
                self.user_custom_new_tables.append({
                    'table_name': nt.get('table_name', ''),
                    'chinese_name': nt.get('table_name', ''),
                    'reason': nt.get('reason', '用户确认整表新增')
                })

        # 兼容性规则引擎
        from rules.compatibility_engine import CompatibilityEngine
        self.compatibility_engine = CompatibilityEngine(skill_dir)

        # 匹配结果缓存（避免 _find_matching_field 重复调用）
        from utils.cache import LRUCache
        self._match_cache = LRUCache(maxsize=50000)

        # 比对统计（用于质量报告）
        self.stats = {
            'exact_english': 0,
            'exact_chinese': 0,
            'synonym': 0,
            'semantic': 0,
            'keyword': 0,
            'cross_table': 0,
            'numbered_field_group': 0,
            'new_field': 0,
            'user_custom': 0,
            'constraint_issues': 0,
            'length_issues': 0,
            'value_domain_issues': 0,
        }

    def _load_synonyms(self) -> Dict[str, List[str]]:
        """从统一的 field_synonyms.yaml 加载同义词映射"""
        import yaml
        import os

        skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        synonyms = {}
        exclude_list = []  # 排除列表

        # 加载统一同义词库
        synonyms_path = os.path.join(skill_dir, 'knowledge_base', 'field_synonyms.yaml')
        if os.path.exists(synonyms_path):
            with open(synonyms_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                field_synonyms = data.get('field_synonyms', {})
                for cn_name, info in field_synonyms.items():
                    if isinstance(info, dict) and 'synonyms' in info:
                        syn_list = list(info['synonyms'])
                        synonyms[cn_name] = syn_list
                        # 加载exclude列表
                        if 'exclude' in info:
                            exclude_list.extend(info['exclude'])
                        # 反向映射：同义词 -> 主词
                        for syn in syn_list:
                            if syn not in synonyms:
                                synonyms[syn] = []
                            if cn_name not in synonyms[syn]:
                                synonyms[syn].append(cn_name)

        # 保存exclude列表供后续使用
        self.synonym_exclude_list = list(set(exclude_list))

        # 加载已学习的表映射（供跨表匹配使用）
        self.learned_mappings = {}
        learned_path = os.path.join(skill_dir, 'knowledge_base', 'learned_mappings.yaml')
        if os.path.exists(learned_path):
            with open(learned_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                mappings = data.get('table_mappings', {})
                if isinstance(mappings, dict):
                    for source_name, info in mappings.items():
                        if isinstance(info, dict) and info.get('target'):
                            self.learned_mappings[source_name] = info['target']
                            if info.get('target_alt'):
                                self.learned_mappings[source_name + '_alt'] = info['target_alt']

        return synonyms

    def _load_table_synonyms(self) -> Dict[str, List[str]]:
        """加载表名同义词映射"""
        import yaml
        skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        table_synonyms_path = os.path.join(skill_dir, 'knowledge_base', 'table_synonyms.yaml')
        if os.path.exists(table_synonyms_path):
            with open(table_synonyms_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                return data.get('table_synonyms', {}) if data else {}
        return {}

    def _load_field_mappings(self) -> Dict[str, Dict]:
        """加载字段映射配置"""
        import yaml
        skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        field_mappings_path = os.path.join(skill_dir, 'knowledge_base', 'field_mappings.yaml')
        if os.path.exists(field_mappings_path):
            with open(field_mappings_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                mappings = data.get('field_mappings', []) if data else []
                # 转换为目标字段名 -> 映射规则的索引
                result = {}
                for mapping in mappings:
                    target_fields = mapping.get('target_fields', [])
                    for target_field in target_fields:
                        result[target_field] = mapping
                return result
        return {}

    def _load_numbered_field_groups(self) -> Dict:
        """加载序号字段组配置（主子表展开策略）"""
        skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(skill_dir, 'knowledge_base', 'numbered_field_groups.yaml')
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                return data if data else {}
        return {}

    def _detect_numbered_field_groups(self, target_table: StandardTable,
                                      source_table: StandardTable,
                                      source_table_index: Dict) -> Dict[str, Dict]:
        """检测目标表中的序号字段组，并匹配到原标准的子表。

        返回: {target_field_name: {group_name, sub_table, sub_table_chinese, match_info}}

        处理场景：
        目标标准用序号字段（如"诊断1代码"、"诊断2代码"），
        原标准用主子表（如"病案首页"主表 + "病案首页诊断"子表）。
        如果子表包含对应的字段结构，则认为序号字段组被覆盖。
        """
        result = {}

        if not self.numbered_field_groups:
            return result

        groups_config = self.numbered_field_groups.get('numbered_field_groups', {})
        target_tables_config = self.numbered_field_groups.get('target_tables', {})

        # 检查当前目标表是否配置了序号字段组
        applicable_groups = []
        for table_pattern, config in target_tables_config.items():
            # 支持模糊匹配表名
            table_name = target_table.name or ''
            table_cn = target_table.chinese_name or ''
            if table_pattern in table_name or table_pattern in table_cn:
                applicable_groups = config.get('groups', [])
                break
            # 也尝试提取括号中的英文名
            en_match = re.search(r'\(([^)]+)\)', table_name)
            if en_match and table_pattern in en_match.group(1):
                applicable_groups = config.get('groups', [])
                break

        if not applicable_groups:
            return result

        for group_name in applicable_groups:
            group_config = groups_config.get(group_name)
            if not group_config:
                continue

            # 支持新的 patterns 列表格式，也兼容旧的 pattern/alt_pattern 格式
            patterns = group_config.get('patterns', [])
            if not patterns:
                # 兼容旧格式
                old_pattern = group_config.get('pattern', '')
                alt_pattern = group_config.get('alt_pattern', '')
                cn_pattern = group_config.get('cn_pattern', '')
                if old_pattern:
                    patterns.append(old_pattern)
                if alt_pattern:
                    patterns.append(alt_pattern)
                if cn_pattern:
                    patterns.append(cn_pattern)

            sub_table_name = group_config.get('source_sub_table', '')
            new_fields_target = group_config.get('new_fields_target', sub_table_name)

            if not patterns:
                continue

            # 查找匹配的目标字段（属于此序号组的字段）
            numbered_fields = []
            for field in target_table.fields:
                field_cn = field.chinese_name or ''
                field_name = field.name or ''
                # 检查是否匹配任一模式
                matched = False
                for pattern in patterns:
                    if re.search(pattern, field_cn) or re.search(pattern, field_name):
                        matched = True
                        break
                if matched:
                    numbered_fields.append(field)

            if not numbered_fields:
                continue

            # 查找原标准中的对应子表
            sub_table = None
            sub_table_chinese = ''

            if sub_table_name and source_table_index:
                sub_table = source_table_index.get(sub_table_name)
                if not sub_table:
                    # 尝试模糊查找
                    for st_name, st in source_table_index.items():
                        if sub_table_name in st_name or sub_table_name in (st.chinese_name or ''):
                            sub_table = st
                            break

            if sub_table:
                sub_table_chinese = sub_table.chinese_name or sub_table.name

                # 验证子表是否包含对应的字段结构
                sub_table_has_structure = self._verify_sub_table_structure(
                    sub_table, group_config.get('sub_table_fields', []))

                if sub_table_has_structure:
                    # 所有序号字段都标记为匹配
                    for field in numbered_fields:
                        result[field.name] = {
                            'group_name': group_name,
                            'sub_table': sub_table.name,
                            'sub_table_chinese': sub_table_chinese,
                            'match_info': f'主子表映射: {group_config.get("description", "")}',
                            'new_fields_target': new_fields_target  # 新增字段应添加到此子表
                        }
                        self.stats['numbered_field_group'] += 1

        return result

    @staticmethod
    def _verify_sub_table_structure(sub_table: StandardTable, expected_fields: list) -> bool:
        """验证子表是否包含预期的字段结构。

        expected_fields 格式:
        [
            {'chinese_keywords': ['诊断', '代码'], 'field_role': 'code'},
            {'chinese_keywords': ['诊断', '名称'], 'field_role': 'name'},
        ]

        如果子表至少有一个字段匹配每个 role，则返回 True。
        """
        if not expected_fields:
            return True  # 没有预期字段配置，默认通过

        roles_found = set()
        for field in sub_table.fields:
            field_cn = field.chinese_name or ''
            for expected in expected_fields:
                keywords = expected.get('chinese_keywords', [])
                role = expected.get('field_role', '')
                # 检查字段名是否包含所有关键词
                if all(kw in field_cn for kw in keywords):
                    roles_found.add(role)

        # 检查是否所有预期的 role 都找到了
        expected_roles = {e.get('field_role', '') for e in expected_fields if e.get('field_role')}
        return len(roles_found & expected_roles) >= len(expected_roles) * 0.5  # 至少匹配一半

    def _load_table_mappings(self) -> Dict[str, Dict]:
        """从 table_synonyms.yaml 加载多对一表映射配置"""
        import yaml
        skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        table_synonyms_path = os.path.join(skill_dir, 'knowledge_base', 'table_synonyms.yaml')
        if os.path.exists(table_synonyms_path):
            with open(table_synonyms_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                multi = data.get('multi_source_tables', {})
                if multi:
                    # 展开 aliases 为独立的 key，都指向同一个映射配置
                    result = {}
                    for table_name, info in multi.items():
                        if isinstance(info, dict):
                            result[table_name] = info
                            for alias in info.get('aliases', []):
                                result[alias] = info
                    return result
        return {}

    def _find_table_mapping(self, target_table) -> Optional[Dict]:
        """查找目标表的表映射配置，支持多种key格式"""
        if not self.table_mappings:
            return None
        # 1. 完整表名匹配
        mapping = self.table_mappings.get(target_table.name)
        if mapping:
            return mapping
        # 2. 从 "中文名(英文名)" 中提取英文名
        en_match = re.search(r'\(([^)]+)\)', target_table.name)
        if en_match:
            mapping = self.table_mappings.get(en_match.group(1))
            if mapping:
                return mapping
        # 3. 提取中文名匹配
        cn_match = re.match(r'^([^(]+)', target_table.name)
        if cn_match:
            cn_name = cn_match.group(1).strip().rstrip('*')
            mapping = self.table_mappings.get(cn_name)
            if mapping:
                return mapping
        # 4. 中文名匹配（用target_table.chinese_name）
        if target_table.chinese_name:
            mapping = self.table_mappings.get(target_table.chinese_name)
            if mapping:
                return mapping
        return None

    def _fuzzy_find_source_table(self, name: str, source_table_index: Dict) -> Optional[object]:
        """模糊查找源表：支持中文名、英文名、或组合名的模糊匹配"""
        # 精确匹配
        if name in source_table_index:
            return source_table_index[name]
        # 模糊匹配：名称片段包含在源表名中
        for st_name, st in source_table_index.items():
            if name in st_name or name in (st.chinese_name or ''):
                return st
            # 反向：源表名包含在给定名称中
            if st_name in name or (st.chinese_name and st.chinese_name in name):
                return st
        return None

    def _normalize_table_name(self, name: str) -> str:
        """标准化表名：去除通用后缀和特殊字符"""
        if not name:
            return ""
        # 去除*号
        name = re.sub(r'\*', '', name)
        # 去除括号内容（包括英文标识符如(m_cli_advices_undrug)）
        name = re.sub(r'\([^)]*\)', '', name)
        # 去除末尾的拼音缩写（如 "MZYZMXB"、"ZYYZMXB" 等）
        name = re.sub(r'\s+[A-Z][A-Z0-9_]+\s*$', '', name)
        # 去除通用后缀
        for suffix in ['信息表', '信息', '记录表', '记录', '明细表', '明细', '报告', '表']:
            if name.endswith(suffix):
                name = name[:-len(suffix)]
                break
        return name.strip()

    def _is_table_synonym(self, name1: str, name2: str) -> bool:
        """检查两个表名是否通过同义词库匹配"""
        if not name1 or not name2:
            return False

        # 标准化表名
        norm1 = self._normalize_table_name(name1)
        norm2 = self._normalize_table_name(name2)

        if not norm1 or not norm2:
            return False

        # 精确匹配
        if norm1 == norm2:
            return True

        # 通过同义词库匹配
        for standard_name, synonyms in self.table_synonyms.items():
            # 检查 name1 是否在同义词组中
            name1_in_group = (standard_name == norm1 or norm1 in synonyms or
                            any(norm1 in syn for syn in synonyms) or
                            any(syn in norm1 for syn in synonyms))
            # 检查 name2 是否在同义词组中
            name2_in_group = (standard_name == norm2 or norm2 in synonyms or
                            any(norm2 in syn for syn in synonyms) or
                            any(syn in norm2 for syn in synonyms))

            if name1_in_group and name2_in_group:
                return True

        # 直接包含关系（如"门急诊挂号"包含"门诊挂号"）
        if len(norm1) > len(norm2):
            # name1 更长，检查 name1 是否包含 name2 的核心词
            # 处理"门急诊"包含"门诊"的情况
            if norm2 in norm1:
                return True
            # 处理"门急诊" = "门诊" + "急诊"的情况
            for syn_group in self.table_synonyms.values():
                for syn in syn_group:
                    if syn in norm1 and norm2.replace(syn, '') in norm1:
                        return True
        else:
            if norm1 in norm2:
                return True

        # 基于业务核心概念的匹配（通用策略）
        # 提取核心业务概念，如果两个表的核心概念相同，则认为匹配
        core_concepts = [
            '医嘱', '诊断', '收费', '病历', '检验', '检查', '手术', '药品',
            '护理', '治疗', '输血', '麻醉', '挂号', '就诊', '入院', '出院',
            '病案首页', '摘要', '症状', '体征'
        ]
        core1 = [c for c in core_concepts if c in norm1]
        core2 = [c for c in core_concepts if c in norm2]
        if core1 and core2 and set(core1) & set(core2):
            # 核心概念有交集，检查是否属于同一业务域（门诊/住院）
            # 提取业务域前缀
            domain_keywords = ['门诊', '住院', '门急诊', '急诊', '出院']
            domain1 = [d for d in domain_keywords if d in norm1]
            domain2 = [d for d in domain_keywords if d in norm2]
            # 如果业务域相同或兼容，则匹配
            if not domain1 or not domain2 or set(domain1) & set(domain2):
                return True
            # "门急诊" 兼容 "门诊" 和 "急诊"
            if '门急诊' in domain1 and ('门诊' in domain2 or '急诊' in domain2):
                return True
            if '门急诊' in domain2 and ('门诊' in domain1 or '急诊' in domain1):
                return True

        return False

    def compare(self, source_doc: StandardDocument, target_doc: StandardDocument) -> CompareResult:
        """比对两份标准化文档

        Args:
            source_doc: 原标准文档
            target_doc: 目标标准文档

        Returns:
            比对结果
        """
        result = CompareResult()

        # 构建原标准的表索引（支持同名表：用 name 和 name|chinese_name 两个key）
        source_table_index = {}
        for table in source_doc.tables:
            # 主键：英文名（如果有）
            if table.name and table.name not in source_table_index:
                source_table_index[table.name] = table
            # 副键：name|chinese_name（处理同名表，如 西医/中医 病案首页）
            composite_key = f"{table.name}|{table.chinese_name}" if table.name and table.chinese_name else table.name or table.chinese_name
            source_table_index[composite_key] = table
            # 也加入中文名索引
            if table.chinese_name and table.chinese_name not in source_table_index:
                source_table_index[table.chinese_name] = table

        # 遍历目标标准的每个表
        for target_table in target_doc.tables:
            # 优先检查表映射（目标表→多个源表，按优先级排列）
            mapping = self._find_table_mapping(target_table)

            if mapping:
                # 表映射命中：第一个源表为主，其余为补充
                source_names = mapping.get('sources', [])
                primary_source = None
                extra_source_tables = []
                for src_name in source_names:
                    matched_table = self._fuzzy_find_source_table(src_name, source_table_index)
                    if matched_table:
                        if primary_source is None:
                            primary_source = matched_table
                        else:
                            extra_source_tables.append(matched_table)

                if primary_source:
                    self._compare_fields(primary_source, target_table, result, extra_source_tables, source_table_index)
                    continue

            # 检查用户自定义整表新增
            is_user_new_table = any(
                nt.get('table_name') == target_table.chinese_name or
                nt.get('table_name') == target_table.name
                for nt in self.user_custom_new_tables
            )

            if is_user_new_table:
                # 用户确认整表新增
                from utils.pinyin_utils import generate_english_field_name
                standard_version = getattr(self, 'source_version', '5.0')
                generated_table_name = generate_english_field_name(
                    target_table.chinese_name or target_table.name,
                    standard_version=standard_version
                )

                result.new_tables.append({
                    'table_name': target_table.name,
                    'chinese_name': target_table.chinese_name,
                    'generated_name': generated_table_name,
                    'field_count': len(target_table.fields),
                    'reason': '用户确认整表新增'
                })

                # 将所有字段记录为新增字段
                for field in target_table.fields:
                    generated_field_name = generate_english_field_name(
                        field.chinese_name,
                        standard_version=standard_version
                    )

                    result.new_fields.append({
                        'table_name': target_table.name,
                        'name': field.name,
                        'chinese_name': field.chinese_name,
                        'generated_name': generated_field_name,
                        'data_type': field.data_type,
                        'length': field.length,
                        'constraint': field.constraint,
                        'description': field.description,
                        'value_domains': getattr(field, 'value_domains', []) or []
                    })
                continue

            # 无表映射时，走常规表匹配
            source_table = self._find_matching_table(target_table, source_table_index)

            if not source_table:
                # 原标准中没有对应的表
                # 生成推荐的英文表名
                from utils.pinyin_utils import generate_english_field_name
                standard_version = getattr(self, 'source_version', '5.0')
                generated_table_name = generate_english_field_name(
                    target_table.chinese_name or target_table.name,
                    standard_version=standard_version
                )

                result.new_tables.append({
                    'table_name': target_table.name,
                    'chinese_name': target_table.chinese_name,
                    'generated_name': generated_table_name,  # 推荐的英文表名
                    'field_count': len(target_table.fields),
                    'reason': '原标准中没有对应的表'
                })

                # 将所有字段记录为新增字段
                for field in target_table.fields:
                    # 生成推荐的英文字段名
                    generated_field_name = generate_english_field_name(
                        field.chinese_name,
                        standard_version=standard_version
                    )

                    result.new_fields.append({
                        'table_name': target_table.name,
                        'name': field.name,
                        'chinese_name': field.chinese_name,
                        'generated_name': generated_field_name,  # 推荐的英文字段名
                        'data_type': field.data_type,
                        'length': field.length,
                        'constraint': field.constraint,
                        'description': field.description,
                        'new_field_target': generated_table_name,  # 新增字段的目标表（使用推荐的表名）
                        'source_table_name': generated_table_name  # 源标准表名（使用推荐的表名）
                    })
                continue

            # 比对字段
            self._compare_fields(source_table, target_table, result, source_table_index=source_table_index)

        # 后处理：字段去重标注（患者基本信息 vs 病案首页）
        self._deduplicate_new_fields_via_relation(result)

        return result

    def _deduplicate_new_fields_via_relation(self, result: CompareResult):
        """字段去重标注：当患者基本信息表和病案首页表都缺失同一字段时，
        只在患者基本信息表中实际新增，病案首页表通过关联获取。

        规则：
        - 如果某个字段同时出现在 患者基本信息 和 病案首页/中医病案首页 的 new_fields 中
        - 保留所有字段在 new_fields 中（都显示为"新增"）
        - 对病案首页中的重复字段添加标注：标记为 deduplicated=True，
          说明通过关联患者基本信息表获取
        - 在统计新增字段数量时，去重后的重复字段不计入
        """
        # 定义表名模式
        patient_table_patterns = ['患者基本信息', 'm_patient']
        emr_hp_table_patterns = ['病案首页', 'm_emr_hp', 'm_emr_hp_tcm']

        def match_table_name(table_name, patterns):
            if not table_name:
                return False
            return any(p in table_name for p in patterns)

        # 收集患者基本信息表中的 new_fields（按中文名称索引）
        patient_new_fields = {}  # chinese_name -> field_info
        for field_info in result.new_fields:
            table_name = field_info.get('table_name', '')
            if match_table_name(table_name, patient_table_patterns):
                cn_name = field_info.get('chinese_name', '') or field_info.get('name', '')
                if cn_name:
                    patient_new_fields[cn_name] = field_info

        if not patient_new_fields:
            return

        # 对病案首页的 new_fields 中的重复字段添加去重标注
        for field_info in result.new_fields:
            table_name = field_info.get('table_name', '')
            if match_table_name(table_name, emr_hp_table_patterns):
                cn_name = field_info.get('chinese_name', '') or field_info.get('name', '')
                if cn_name and cn_name in patient_new_fields:
                    # 标记为去重字段，显示为"新增"但统计时去重
                    field_info['deduplicated'] = True
                    field_info['dedup_note'] = f'该字段已在患者基本信息表中新增，通过关联获取'
                    field_info['dedup_source_table'] = patient_new_fields[cn_name].get('table_name', '')

    def _find_matching_table(self, target_table: StandardTable,
                            source_table_index: Dict[str, StandardTable]) -> Optional[StandardTable]:
        """查找匹配的原标准表

        优先级：已学习映射 → 精确匹配 → 中文名匹配 → 表同义词匹配 → 语义匹配
        """
        # 0. 使用已学习的映射（最高优先级）
        if hasattr(self, 'learned_mappings') and self.learned_mappings:
            for source_name, target_name in self.learned_mappings.items():
                if target_name == target_table.name and source_name in source_table_index:
                    return source_table_index[source_name]
                if target_name == target_table.name and '_alt' not in source_name:
                    # 反向查找：用target_table.name找source
                    for s_name, t_name in self.learned_mappings.items():
                        if t_name == target_table.name and s_name in source_table_index:
                            return source_table_index[s_name]

        # 1. 精确匹配表名
        if target_table.name in source_table_index:
            return source_table_index[target_table.name]

        # 2. 匹配中文名
        for source_table in source_table_index.values():
            if target_table.chinese_name and target_table.chinese_name == source_table.chinese_name:
                return source_table

        # 3. 表同义词匹配（新增）
        for source_table in source_table_index.values():
            # 检查中文名
            if self._is_table_synonym(target_table.chinese_name, source_table.chinese_name):
                return source_table
            # 检查英文名
            if self._is_table_synonym(target_table.name, source_table.name):
                return source_table
            # 交叉检查
            if self._is_table_synonym(target_table.chinese_name, source_table.name):
                return source_table
            if self._is_table_synonym(target_table.name, source_table.chinese_name):
                return source_table

        # 4. 提取表名中的中文名进行匹配（保留原有逻辑）
        target_chinese = self._extract_chinese_name(target_table.name)
        target_chinese2 = self._extract_chinese_name(target_table.chinese_name)

        for source_table in source_table_index.values():
            source_chinese = self._extract_chinese_name(source_table.name)
            source_chinese2 = self._extract_chinese_name(source_table.chinese_name)

            # 匹配提取出的中文名
            if target_chinese and source_chinese and target_chinese in source_chinese:
                return source_table
            if target_chinese and source_chinese2 and target_chinese in source_chinese2:
                return source_table
            if target_chinese2 and source_chinese and target_chinese2 in source_chinese:
                return source_table
            if target_chinese2 and source_chinese2 and target_chinese2 in source_chinese2:
                return source_table

        # 5. 语义匹配（基于表名相似度）
        # TODO: 可以实现更复杂的语义匹配

        return None

    def _extract_chinese_name(self, name: str) -> str:
        """从表名中提取中文名"""
        import re
        # 去除*号、括号、英文等，只保留中文
        chinese_chars = re.findall(r'[一-龥]+', name)
        return ''.join(chinese_chars)

    def _compare_fields(self, source_table: StandardTable, target_table: StandardTable,
                       result: CompareResult, extra_source_tables: list = None,
                       source_table_index: Dict[str, StandardTable] = None):
        """比对两个表的字段"""
        # 构建原标准的字段索引（主表优先）
        source_field_index = {field.name: field for field in source_table.fields}

        # 合并额外源表的字段（不覆盖主表已有的同名字段）
        if extra_source_tables:
            for extra_table in extra_source_tables:
                for field in extra_table.fields:
                    if field.name not in source_field_index:
                        source_field_index[field.name] = field

        # ===== 新增：序号字段组检测（主子表展开策略）=====
        numbered_field_matches = self._detect_numbered_field_groups(
            target_table, source_table, source_table_index)
        # numbered_field_matches: {field_name: {group_name, sub_table, match_info}}

        # 第一遍：收集所有字段的匹配状态（不包括字典名称字段）
        field_match_status = {}  # field_name -> 'matched' | 'modified' | 'numbered_group' | None
        dictionary_name_fields = {}  # field_name -> related_code_field_name
        field_match_results = {}  # field_name -> (source_field, match_type) — 缓存匹配结果

        # 先识别字典名称字段
        for target_field in target_table.fields:
            related_code_field = self._find_related_code_field(target_field, target_table.fields, {})
            if related_code_field:
                dictionary_name_fields[target_field.name] = related_code_field.name

        # 匹配非字典名称字段
        for target_field in target_table.fields:
            # 如果是字典名称字段，先跳过，等代码字段匹配后再处理
            if target_field.name in dictionary_name_fields:
                field_match_status[target_field.name] = None
                continue

            # 如果是序号字段组中的字段，标记为已匹配
            if target_field.name in numbered_field_matches:
                field_match_status[target_field.name] = 'numbered_group'
                continue

            match_result = self._find_matching_field(
                target_field, source_field_index, source_table, source_table_index, target_table)
            source_field = match_result[0] if match_result else None
            if source_field:
                modifications = self._check_modifications(source_field, target_field)
                # 缓存匹配结果和修改检查，避免第三遍重复调用
                field_match_results[target_field.name] = (match_result, modifications)
                if modifications:
                    field_match_status[target_field.name] = 'modified'
                else:
                    field_match_status[target_field.name] = 'matched'
            else:
                field_match_results[target_field.name] = (match_result, [])
                field_match_status[target_field.name] = None

        # 第二遍：处理字典名称字段
        for field_name, code_field_name in dictionary_name_fields.items():
            # 检查对应的代码字段是否已匹配
            code_field_status = field_match_status.get(code_field_name)

            if code_field_status in ['matched', 'modified']:
                # 代码字段已匹配，名称字段可以通过字典关联获取
                field_match_status[field_name] = 'dictionary'

        # 第三遍：生成结果
        for target_field in target_table.fields:
            match_status = field_match_status.get(target_field.name)

            # 检查是否是字段映射配置中的字段（使用表名.字段名作为key，同时检查英文名和中文名）
            table_field_key = f"{target_table.chinese_name or target_table.name}.{target_field.chinese_name or target_field.name}"
            field_mapping = (self.kb.field_mappings.get(table_field_key) or
                           self.kb.field_mappings.get(target_field.name) or
                           self.kb.field_mappings.get(target_field.chinese_name))

            # 优先处理用户自定义映射（忽略match_status）
            is_user_custom = field_mapping and field_mapping.get('match_type') == 'user_custom'

            # 只有在字段未被匹配（match_status为None）或者是用户自定义映射时，才应用field_mapping
            # 但是，numbered_group和dictionary状态的字段已经有特殊的处理方式，不应该被field_mapping覆盖
            # 即使是user_custom的field_mapping也不应该覆盖这些特殊状态
            has_special_status = match_status in ['numbered_group', 'dictionary']
            if field_mapping and not has_special_status and (is_user_custom or match_status is None):
                # 这是一个配置了映射关系的字段
                source_field_name = field_mapping.get('source_field')
                source_field_cn = field_mapping.get('source_field_cn', '')
                source_table_name = field_mapping.get('source_table', '')

                # 查找源字段 - 优先从用户指定的源表中查找
                source_field = None
                actual_source_table = source_table  # 默认使用当前源表

                # 1. 如果指定了源表名，从该表中查找
                if source_table_name and source_table_index:
                    for st_name, st in source_table_index.items():
                        # 匹配源表名（支持中文名和英文名）
                        st_cn = st.chinese_name or ''
                        st_name_val = st.name or ''
                        if (st_cn == source_table_name or
                            st_name_val == source_table_name or
                            source_table_name in st_cn or
                            source_table_name == st_cn):
                            actual_source_table = st
                            # 从指定的源表中查找字段
                            if source_field_name or source_field_cn:
                                for sf in st.fields:
                                    sf_cn = sf.chinese_name or ''
                                    sf_name = sf.name or ''
                                    if (sf_name == source_field_name or
                                        sf_cn == source_field_name or
                                        sf_cn == source_field_cn):
                                        source_field = sf
                                        break
                            break

                # 2. 如果没找到源字段，且用户没有指定源表，从当前源表中查找
                # 注意：如果用户指定了源表但没有源字段，不应该从当前源表中查找（作为新增字段处理）
                if not source_field and not source_table_name:
                    source_field = source_field_index.get(source_field_name)
                    if not source_field and source_field_cn:
                        for sf in source_table.fields:
                            if sf.chinese_name == source_field_cn:
                                source_field = sf
                                break
                    elif not source_field:
                        for sf in source_table.fields:
                            if sf.chinese_name == source_field_name:
                                source_field = sf
                                break

                if source_field:

                    # 兼容性检查：代码字段不应映射到名称/文本字段
                    if self._is_field_mapping_compatible(target_field, source_field, field_mapping):
                        # 检查是否需要修改
                        modifications = self._check_modifications(source_field, target_field)

                        if modifications:
                            result.modified.append({
                                'table_name': target_table.name,
                                'table_chinese_name': target_table.chinese_name,
                                'field_name': target_field.name,
                                'field_chinese_name': target_field.chinese_name,
                                'source_table': actual_source_table.name,
                                'source_table_chinese_name': actual_source_table.chinese_name,
                                'source_field': source_field.name,
                                'source_field_chinese_name': source_field.chinese_name,
                                'match_type': field_mapping.get('match_type', 'field_mapping'),
                                'modifications': modifications
                            })
                        else:
                            result.matched.append({
                                'table_name': target_table.name,
                                'table_chinese_name': target_table.chinese_name,
                                'target_field': target_field.name,
                                'target_chinese_name': target_field.chinese_name,
                                'source_table': actual_source_table.name,
                                'source_table_chinese_name': actual_source_table.chinese_name,
                                'source_field': source_field.name,
                                'source_field_chinese_name': source_field.chinese_name,
                                'match_type': field_mapping.get('match_type', 'field_mapping')
                            })
                        # 更新field_match_status，以便后续字典检测能够识别
                        field_match_status[target_field.name] = 'modified' if modifications else 'matched'
                        continue
                    # 兼容性检查未通过，不应用此映射，让后续逻辑处理
                else:
                    # 用户自定义映射中没有源字段，作为新增字段处理
                    if is_user_custom:
                        # 用户指定了源表但没有源字段，表示这个字段需要新增到指定的源表
                        from utils.pinyin_utils import generate_english_field_name

                        # 获取版本信息，默认为5.0
                        standard_version = getattr(self, 'source_version', '5.0')
                        generated_en_name = generate_english_field_name(
                            target_field.chinese_name,
                            standard_version=standard_version
                        )

                        # 使用用户指定的源表，如果没有指定则使用当前匹配的源表
                        new_field_target = source_table_name if source_table_name else (source_table.name if source_table else target_table.name)

                        result.new_fields.append({
                            'table_name': target_table.name,
                            'table_chinese_name': target_table.chinese_name,
                            'name': target_field.name,
                            'generated_name': generated_en_name,
                            'chinese_name': target_field.chinese_name,
                            'data_type': target_field.data_type,
                            'length': target_field.length,
                            'constraint': target_field.constraint,
                            'description': target_field.description or '',
                            'value_domains': [
                                {'code': vd.code, 'name': vd.name}
                                for vd in target_field.value_domains
                            ],
                            'new_field_target': new_field_target,
                            'source_table_name': new_field_target
                        })
                        continue
                    # 其他field_mapping让后续逻辑处理

            # 新增：检查是否是通过field_mappings匹配的代码字段的名称字段
            # 例如：insurance_type_code 通过field_mappings匹配到BXLX，
            #       那么 insurance_type_name 应该被识别为字典项
            is_name_field = False
            field_name_lower = target_field.name.lower()
            field_chinese = target_field.chinese_name or ''

            # 检查是否是名称字段
            if 'name' in field_name_lower or '名称' in field_chinese:
                # 提取基础名称
                base_name = field_chinese
                for kw in self.dictionary_name_keywords:
                    base_name = base_name.replace(kw, '')
                base_name = base_name.strip()
                base_name_en = target_field.name.lower()
                for suffix in ['_name', 'name']:
                    if base_name_en.endswith(suffix):
                        base_name_en = base_name_en[:-len(suffix)]
                        break

                if base_name and len(base_name) >= 2:
                    # 查找对应的代码字段
                    for other_field in target_table.fields:
                        if other_field.name == target_field.name:
                            continue

                        other_field_name_lower = other_field.name.lower()
                        other_chinese = other_field.chinese_name or ''

                        # 检查是否是代码字段且已匹配
                        is_code_field = ('_code' in other_field_name_lower or
                                        other_field_name_lower.endswith('code') or
                                        '代码' in other_chinese or
                                        '编码' in other_chinese)

                        if is_code_field:
                            # 改进：要求更精确的基础名称匹配
                            # 基础名称应该占代码字段名称的主要部分
                            other_base_name = other_chinese
                            for kw in ['代码', '编码', '类别', '类型']:
                                other_base_name = other_base_name.replace(kw, '')
                            other_base_name = other_base_name.strip()

                            # 检查基础名称是否相同或高度相似
                            # 名称字段的基础名称也需要去除"类别"/"类型"，与代码字段保持一致
                            clean_base_name = base_name
                            for kw in ['类别', '类型']:
                                clean_base_name = clean_base_name.replace(kw, '')
                            clean_base_name = clean_base_name.strip()
                            if clean_base_name == other_base_name or clean_base_name in other_base_name:
                                # 检查代码字段是否已匹配
                                if field_match_status.get(other_field.name) in ['matched', 'modified']:
                                    is_name_field = True
                                    break

            if is_name_field:
                # 标记为字典关联匹配
                result.matched.append({
                    'table_name': target_table.name,
                    'table_chinese_name': target_table.chinese_name,
                    'target_field': target_field.name,
                    'target_chinese_name': target_field.chinese_name,
                    'source_table': '',
                    'source_table_chinese_name': '',
                    'source_field': '',
                    'source_field_chinese_name': '',
                    'match_type': 'dictionary'
                })
                continue

            if match_status == 'dictionary':
                # 字典关联匹配（没有直接对应的源字段，通过代码字段关联获取）
                result.matched.append({
                    'table_name': target_table.name,
                    'table_chinese_name': target_table.chinese_name,
                    'target_field': target_field.name,
                    'target_chinese_name': target_field.chinese_name,
                    'source_table': '',
                    'source_table_chinese_name': '',
                    'source_field': '',
                    'source_field_chinese_name': '',
                    'match_type': 'dictionary'
                })
            elif match_status == 'numbered_group':
                # 序号字段组匹配（主子表展开策略）
                group_info = numbered_field_matches.get(target_field.name, {})
                sub_table_name = group_info.get('sub_table', '')
                sub_table_chinese = group_info.get('sub_table_chinese', '')
                group_name = group_info.get('group_name', '')
                result.matched.append({
                    'table_name': target_table.name,
                    'table_chinese_name': target_table.chinese_name,
                    'target_field': target_field.name,
                    'target_chinese_name': target_field.chinese_name,
                    'source_table': sub_table_name,
                    'source_table_chinese_name': sub_table_chinese,
                    'source_field': '',
                    'source_field_chinese_name': f'[主子表映射:{group_name}]',
                    'match_type': 'numbered_field_group'
                })
            elif match_status in ['matched', 'modified']:
                # 正常匹配 — 使用第一遍缓存的匹配结果和修改检查（避免重复调用）
                cached = field_match_results.get(target_field.name)
                if cached:
                    match_result, modifications = cached
                    if match_result:
                        source_field, internal_match_type = match_result

                    if modifications:
                        result.modified.append({
                            'table_name': target_table.name,
                            'table_chinese_name': target_table.chinese_name,
                            'field_name': target_field.name,
                            'field_chinese_name': target_field.chinese_name,
                            'source_table': source_table.name,
                            'source_table_chinese_name': source_table.chinese_name,
                            'source_field': source_field.name,
                            'source_field_chinese_name': source_field.chinese_name,
                            'match_type': internal_match_type,
                            'modifications': modifications
                        })
                    else:
                        result.matched.append({
                            'table_name': target_table.name,
                            'table_chinese_name': target_table.chinese_name,
                            'target_field': target_field.name,
                            'target_chinese_name': target_field.chinese_name,
                            'source_table': source_table.name,
                            'source_table_chinese_name': source_table.chinese_name,
                            'source_field': source_field.name,
                            'source_field_chinese_name': source_field.chinese_name,
                            'match_type': internal_match_type
                        })
            else:
                # 未匹配，检查是否属于序号字段组（应重定向到子表）
                sub_table_target = self._find_numbered_group_for_field(target_field, target_table)

                if sub_table_target:
                    # 属于序号字段组，添加到子表的新增字段
                    # 生成英文字段名
                    from utils.pinyin_utils import generate_english_field_name

                    # 获取版本信息，默认为5.0
                    standard_version = getattr(self, 'source_version', '5.0')
                    generated_en_name = generate_english_field_name(
                        target_field.chinese_name,
                        standard_version=standard_version
                    )

                    result.new_fields.append({
                        'table_name': sub_table_target,  # 使用子表名
                        'table_chinese_name': target_table.chinese_name,
                        'name': target_field.name,
                        'generated_name': generated_en_name,  # 生成的英文字段名
                        'chinese_name': target_field.chinese_name,
                        'data_type': target_field.data_type,
                        'length': target_field.length,
                        'constraint': target_field.constraint,
                        'description': target_field.description or '',
                        'value_domains': [
                            {'code': vd.code, 'name': vd.name}
                            for vd in target_field.value_domains
                        ],
                        'redirected_from': target_table.name,  # 标记来源
                        'redirect_reason': '序号字段组',
                        'new_field_target': sub_table_target,  # 明确标注需要新增的表（源标准表名）
                        'source_table_name': sub_table_target  # 源标准表名，用于报告展示
                    })
                else:
                    # 普通新增字段
                    # 生成英文字段名
                    from utils.pinyin_utils import generate_english_field_name

                    # 获取版本信息，默认为5.0
                    standard_version = getattr(self, 'source_version', '5.0')
                    generated_en_name = generate_english_field_name(
                        target_field.chinese_name,
                        standard_version=standard_version
                    )

                    # 获取对应的源标准表名
                    # 优先使用用户自定义映射中的source_table
                    user_mapping = self.kb.field_mappings.get(f"{target_table.chinese_name or target_table.name}.{target_field.chinese_name or target_field.name}") or \
                                  self.kb.field_mappings.get(target_field.name) or \
                                  self.kb.field_mappings.get(target_field.chinese_name)

                    if user_mapping and user_mapping.get('match_type') == 'user_custom' and user_mapping.get('source_table'):
                        # 使用用户自定义映射中的源表名
                        source_table_chinese_name = user_mapping.get('source_table', '')
                        # 查找对应的源标准表，获取英文名
                        source_table_obj = source_table_index.get(source_table_chinese_name) if source_table_index else None
                        if source_table_obj:
                            # 优先使用英文名，如果英文名是空的，使用中文名
                            source_table_name = source_table_obj.name if source_table_obj.name else source_table_chinese_name
                        else:
                            # 如果找不到源表，使用中文名
                            source_table_name = source_table_chinese_name
                    else:
                        # 如果source_table存在，使用其名称；否则使用target_table的名称作为fallback
                        source_table_name = source_table.name if source_table else target_table.name

                    result.new_fields.append({
                        'table_name': target_table.name,
                        'table_chinese_name': target_table.chinese_name,
                        'name': target_field.name,
                        'generated_name': generated_en_name,  # 生成的英文字段名
                        'chinese_name': target_field.chinese_name,
                        'data_type': target_field.data_type,
                        'length': target_field.length,
                        'constraint': target_field.constraint,
                        'description': target_field.description or '',
                        'value_domains': [
                            {'code': vd.code, 'name': vd.name}
                            for vd in target_field.value_domains
                        ],
                        'new_field_target': target_table.name,  # 目标表名（用于统计）
                        'source_table_name': source_table_name  # 源标准表名，用于报告展示
                    })

    def _find_numbered_group_for_field(self, target_field: StandardField, target_table: StandardTable) -> Optional[str]:
        """检查未匹配字段是否属于序号字段组

        如果字段属于序号字段组，返回应该添加到的子表名称
        否则返回 None

        Args:
            target_field: 目标字段
            target_table: 目标表

        Returns:
            子表名称或 None
        """
        if not hasattr(self, 'numbered_field_groups') or not self.numbered_field_groups:
            return None

        groups_config = self.numbered_field_groups.get('numbered_field_groups', {})
        target_tables_config = self.numbered_field_groups.get('target_tables', {})

        # 检查当前目标表是否配置了序号字段组
        applicable_groups = []
        table_name = target_table.name or ''
        table_cn = target_table.chinese_name or ''

        for table_pattern, config in target_tables_config.items():
            if table_pattern in table_name or table_pattern in table_cn:
                applicable_groups = config.get('groups', [])
                break

        if not applicable_groups:
            return None

        # 检查字段是否匹配任何序号字段组的模式
        field_cn = target_field.chinese_name or ''
        field_name = target_field.name or ''

        for group_name in applicable_groups:
            group_config = groups_config.get(group_name)
            if not group_config:
                continue

            # 支持 patterns 列表格式
            patterns = group_config.get('patterns', [])
            if not patterns:
                # 兼容旧格式
                old_pattern = group_config.get('pattern', '')
                alt_pattern = group_config.get('alt_pattern', '')
                cn_pattern = group_config.get('cn_pattern', '')
                if old_pattern:
                    patterns.append(old_pattern)
                if alt_pattern:
                    patterns.append(alt_pattern)
                if cn_pattern:
                    patterns.append(cn_pattern)

            # 检查是否匹配任一模式
            for pattern in patterns:
                if re.search(pattern, field_cn) or re.search(pattern, field_name):
                    # 匹配成功，返回子表名称
                    return group_config.get('new_fields_target', group_config.get('source_sub_table', ''))

        return None

    def _find_related_code_field(self, name_field: StandardField, all_fields: List[StandardField],
                                 field_match_status: Dict[str, str]) -> Optional[StandardField]:
        """查找与名称字段对应的代码字段

        规则：如果字段名包含 name_keywords，查找对应的 code_keywords 字段
        例如："证件类型名称" -> "证件类型代码"
        """
        import re

        # 检查是否是名称字段
        is_name_field = False
        field_name_lower = name_field.name.lower()
        field_chinese = name_field.chinese_name or ''

        # 新增：排除特定的字段名模式
        # 例如：contact_name（联系人姓名）、patient_name（患者姓名）等不是字典项
        exclude_patterns = [
            'contact_name', 'patient_name', 'user_name', 'doctor_name',
            'nurse_name', 'org_name', 'dept_name', 'hosp_name'
        ]
        if field_name_lower in exclude_patterns:
            return None

        # 新增：排除中文名称中包含特定模式的字段
        # 例如："联系人姓名"、"患者姓名"等不是字典项
        exclude_chinese_patterns = ['联系人姓名', '患者姓名', '用户姓名', '医生姓名', '护士姓名']
        if field_chinese in exclude_chinese_patterns:
            return None

        # 英文名包含 name 且不是排除的类型
        if 'name' in field_name_lower and not any(x in field_name_lower for x in self.dictionary_exclude_patterns):
            is_name_field = True

        # 中文名包含名称关键词
        for kw in self.dictionary_name_keywords:
            if kw in field_chinese:
                is_name_field = True
                break

        if not is_name_field:
            return None

        # 提取基础名称（去掉名称关键词）
        base_name = field_chinese
        for kw in self.dictionary_name_keywords:
            base_name = base_name.replace(kw, '')
        base_name = base_name.strip()
        base_name_en = re.sub(r'_?name$', '', field_name_lower, flags=re.IGNORECASE)

        # 新增：基础名称必须达到最小长度，避免过于通用的名称被误识别
        min_base_length = 2  # 基础名称至少2个字符
        if len(base_name) < min_base_length:
            return None

        # 查找对应的代码字段
        best_match = None
        best_score = 0

        for field in all_fields:
            if field.name == name_field.name:
                continue

            field_chinese_other = field.chinese_name or ''
            field_name_other_lower = field.name.lower()
            score = 0

            # 检查中文名是否包含代码关键词
            if base_name and base_name in field_chinese_other:
                if any(kw in field_chinese_other for kw in ['代码', '编码']):
                    score += 10
                elif '代号' in field_chinese_other:
                    score += 8
                elif '编号' in field_chinese_other:
                    score += 6

            # 检查英文名是否包含代码关键词
            if base_name_en and base_name_en in field_name_other_lower:
                if '_code' in field_name_other_lower or field_name_other_lower.endswith('code'):
                    score += 10
                elif '_id' in field_name_other_lower or field_name_other_lower.endswith('id'):
                    score += 8
                elif 'code' in field_name_other_lower:
                    score += 6
                elif 'id' in field_name_other_lower:
                    score += 5

            if score > best_score:
                best_score = score
                best_match = field

        # 如果找到了匹配的字段，检查是否已匹配或即使未匹配也认为是字典字段
        if best_match and best_score >= 5:
            # 即使代码字段没有被匹配，只要存在对应的代码字段，就认为名称字段可以通过字典获取
            return best_match

        return None

    def _find_matching_field(self, target_field: StandardField,
                            source_field_index: Dict[str, StandardField],
                            source_table: StandardTable = None,
                            source_table_index: Dict[str, StandardTable] = None,
                            target_table: StandardTable = None):
        """查找匹配的原标准字段

        按配置的优先级执行匹配：
        exact_chinese → exact_english → semantic_chinese → cross_table → new_field

        返回 (source_field, match_type) 元组，未匹配返回 None。
        match_type 保留内部匹配策略名，供输出和核验使用。
        """
        # 优先检查用户自定义映射（最高优先级）
        # 使用表名.字段名作为key查找
        table_field_key = f"{target_table.chinese_name or target_table.name}.{target_field.chinese_name or target_field.name}"
        # 直接使用self.kb.field_mappings获取最新映射，而不是self.field_mappings（初始化时的快照）
        user_mapping = self.kb.field_mappings.get(table_field_key) or self.kb.field_mappings.get(target_field.name) or self.kb.field_mappings.get(target_field.chinese_name)
        if user_mapping and user_mapping.get('match_type') == 'user_custom':
            source_field_name = user_mapping.get('source_field')
            source_field_cn = user_mapping.get('source_field_cn', '')
            source_table_name = user_mapping.get('source_table', '')

            # 用户自定义映射优先级最高：
            # 1. 如果指定了源表和源字段，尝试从指定源表中查找
            # 2. 如果只指定了源表没有源字段，返回None（作为新增字段处理，但保留源表信息）
            # 3. 如果都没有指定，返回None

            if source_table_name:
                # 用户指定了源表，从该表中查找字段
                if source_field_name or source_field_cn:
                    # 有源字段，从指定源表中查找
                    if source_table_index:
                        for st_name, st in source_table_index.items():
                            if (st.chinese_name == source_table_name or
                                st.name == source_table_name or
                                source_table_name in st.chinese_name):
                                # 找到指定的源表，从中查找字段
                                for sf in st.fields:
                                    if (sf.name == source_field_name or
                                        sf.chinese_name == source_field_name or
                                        sf.chinese_name == source_field_cn):
                                        return (sf, 'user_custom')
                # 没有源字段或没找到，返回None（作为新增字段处理）
                return None
            elif source_field_name or source_field_cn:
                # 没有指定源表，但指定了源字段，从当前源表中查找
                if source_field_index:
                    sf = source_field_index.get(source_field_name)
                    if sf:
                        return (sf, 'user_custom')
                    if source_field_cn:
                        for s in source_table.fields:
                            if s.chinese_name == source_field_cn:
                                return (s, 'user_custom')
                return None
            else:
                # 都没有指定，返回None
                return None

        for priority in self.match_priority:
            if priority == 'new_field':
                # 新增字段 - 不匹配，留给调用方处理
                continue

            if priority == 'exact_chinese':
                # 1. 精确匹配中文名
                for source_field in source_field_index.values():
                    if target_field.chinese_name and target_field.chinese_name == source_field.chinese_name:
                        # 验证：如果字段说明不兼容，则跳过
                        if not self._is_description_compatible(target_field, source_field):
                            continue
                        self.stats['exact_chinese'] += 1
                        return (source_field, 'exact_chinese')

            elif priority == 'exact_english':
                # 2. 精确匹配英文名
                if target_field.name in source_field_index:
                    source_field = source_field_index[target_field.name]
                    # 验证：如果字段说明不兼容，则跳过
                    if not self._is_description_compatible(target_field, source_field):
                        continue
                    self.stats['exact_english'] += 1
                    return (source_field, 'exact_english')

            elif priority == 'semantic_chinese':
                # 3. 同义词匹配
                if self.use_synonym:
                    for source_field in source_field_index.values():
                        if self._is_synonym_match(target_field.chinese_name, source_field.chinese_name):
                            if not self._is_description_compatible(target_field, source_field):
                                continue
                            self.stats['synonym'] += 1
                            return (source_field, 'synonym')

                # 4. 语义匹配（相似度）
                if self.use_similarity:
                    for source_field in source_field_index.values():
                        if self._is_semantic_match(target_field.chinese_name, source_field.chinese_name):
                            if not self._is_description_compatible(target_field, source_field):
                                continue
                            self.stats['semantic'] += 1
                            return (source_field, 'semantic')

                # 5. 关键词匹配（n-gram）
                if self.use_keyword:
                    for source_field in source_field_index.values():
                        if self._is_keyword_match(target_field.chinese_name, source_field.chinese_name):
                            if not self._is_type_compatible_for_keyword(target_field, source_field):
                                continue
                            if not self._is_code_name_compatible(target_field.chinese_name, source_field.chinese_name):
                                continue
                            if not self._is_description_compatible(target_field, source_field):
                                continue
                            self.stats['keyword'] += 1
                            return (source_field, 'keyword')

            elif priority == 'cross_table':
                # 跨表关联匹配：通过 relations 知识库查找关联表中的字段
                # 支持多跳查找（最多 cross_table_max_depth 跳）
                if source_table and source_table_index and self.relations:
                    adjacency = self.relations.get('adjacency', {})
                    source_name = source_table.name

                    # 使用 BFS 进行多跳查找
                    visited = {source_name}
                    queue = [(source_name, 0)]  # (table_name, depth)

                    while queue:
                        current_table_name, depth = queue.pop(0)

                        if depth >= self.cross_table_max_depth:
                            continue

                        if current_table_name not in adjacency:
                            continue

                        for neighbor in adjacency[current_table_name]:
                            related_table_name = neighbor['to']

                            if related_table_name in visited:
                                continue
                            visited.add(related_table_name)

                            if related_table_name not in source_table_index:
                                continue

                            related_table = source_table_index[related_table_name]
                            hop_info = f"({depth + 1}hop)"

                            for rel_field in related_table.fields:
                                # 中文名精确匹配
                                if target_field.chinese_name and rel_field.chinese_name:
                                    if target_field.chinese_name == rel_field.chinese_name:
                                        if self._is_description_compatible(target_field, rel_field):
                                            self.stats['cross_table'] += 1
                                            return (rel_field, f'cross_table{hop_info}')
                                # 英文名精确匹配
                                if target_field.name and target_field.name == rel_field.name:
                                    if self._is_description_compatible(target_field, rel_field):
                                        self.stats['cross_table'] += 1
                                        return (rel_field, f'cross_table{hop_info}')
                                # 同义词匹配（更严格）
                                if self.use_synonym and target_field.chinese_name and rel_field.chinese_name:
                                    if self._is_synonym_match(target_field.chinese_name, rel_field.chinese_name):
                                        if self._is_description_compatible(target_field, rel_field):
                                            # 额外校验：同义词匹配时要求字段类型相同
                                            if target_field.data_type == rel_field.data_type:
                                                self.stats['cross_table'] += 1
                                                return (rel_field, f'cross_table{hop_info}')

                            # 继续搜索下一跳
                            queue.append((related_table_name, depth + 1))

        # 未匹配到
        self.stats['new_field'] += 1
        return None

    def _is_description_compatible(self, target_field: StandardField, source_field: StandardField) -> bool:
        """检查两个字段的说明是否兼容

        通过字段说明和字段名判断两个字段是否真的可以对应：
        - 如果源字段说明明确指出只存储某类数据（如"行政区划代码"），
          则目标字段如果是其他类型（如"省市名称"），则不兼容
        - 基于字段名的语义冲突检查（即使没有描述也要检查）

        优先使用兼容性规则引擎（从 compatibility_rules.yaml 加载），
        引擎未覆盖的场景再由下面的硬编码规则补充。
        """
        if not hasattr(target_field, 'chinese_name') or not hasattr(source_field, 'chinese_name'):
            return True

        target_cn = target_field.chinese_name or ''
        source_cn = source_field.chinese_name or ''

        # 如果没有中文名，无法进行语义检查
        if not target_cn or not source_cn:
            return True

        # ===== 前置过滤：使用兼容性规则引擎 =====
        if hasattr(self, 'compatibility_engine') and self.compatibility_engine:
            is_compatible, rule_name = self.compatibility_engine.is_compatible(
                target_field, source_field)
            if not is_compatible:
                return False

        # ===== 基于字段名的语义冲突检查（始终执行）=====

        # 规则1：代码 vs 名称 冲突
        code_keywords = ['代码', '编码', '代号', '编号']
        name_keywords = ['名称', '名字']

        target_is_code = any(kw in target_cn for kw in code_keywords)
        target_is_name = any(kw in target_cn for kw in name_keywords)
        source_is_code = any(kw in source_cn for kw in code_keywords)
        source_is_name = any(kw in source_cn for kw in name_keywords)

        # 如果一个是代码字段，另一个是名称字段，检查说明
        target_desc = target_field.description or ''
        source_desc = source_field.description or ''

        if target_is_code and source_is_name:
            if '字典' not in source_desc and '映射' not in source_desc:
                return False
        elif target_is_name and source_is_code:
            if '字典' not in source_desc and '映射' not in source_desc:
                return False

        # 规则2：行政区划代码的粒度匹配
        # 如果源字段是通用的"行政区划代码"（如CSD），目标是更细粒度的"省市代码"/"地市代码"等，则不兼容
        if '行政区划代码' in source_desc or 'GB/T 2260' in source_desc:
            # 源字段是行政区划代码
            target_granularity_keywords = ['省市', '地市', '区县', '街道']
            if any(kw in target_cn for kw in target_granularity_keywords):
                # 目标要求更细粒度的代码，但源字段只是通用的行政区划代码
                # 检查源字段名是否包含粒度信息
                source_granularity_keywords = ['省市', '地市', '区县', '街道']
                if not any(kw in source_cn for kw in source_granularity_keywords):
                    return False

        # 规则3：检查字段说明中的存储内容限制
        if '存储的是' in source_desc or '存储' in source_desc:
            if '省市' in target_cn and '行政区划' not in target_cn:
                if '行政区划' in source_desc and '省市' not in source_desc:
                    return False

        # 规则4：控制字段映射 - status/up_flag/del_flag 应该映射到修改标志类字段
        control_field_names = ['status', 'up_flag', 'del_flag', '数据状态标识', '数据上传标识', '数据删除标识']
        if target_field.name in control_field_names or any(kw in target_cn for kw in ['状态标识', '上传标识', '删除标识']):
            # 目标字段是控制字段，检查源字段是否是修改标志类字段
            source_control_keywords = ['修改标志', '修改标识', 'XGBZ', '状态', '标志']
            if not any(kw in source_cn for kw in source_control_keywords):
                if source_cn and source_desc:
                    # 源字段不是控制字段，不兼容
                    return False

        # 规则5：字段类型语义冲突检查
        # 检查目标字段和源字段是否表达完全不同的概念

        # 5.1 身份证件类别代码 vs 证件号码
        if '身份证件类别代码' in target_cn or 'id_type_code' in target_field.name.lower():
            if '证件号码' in source_cn or '身份证号' in source_cn or '身份证' in source_cn:
                if '类别' not in source_cn and '类型' not in source_cn:
                    return False

        # 5.2 工作单位电话 vs 手机号码
        if '工作单位电话' in target_cn or 'work_place_tel' in target_field.name.lower():
            if '手机号码' in source_cn or '手机号' in source_cn:
                if '工作单位' not in source_cn and '工作电话' not in source_cn:
                    return False

        # 5.3 联系人电话 vs 手机号码
        if '联系人电话' in target_cn or 'contact_phone' in target_field.name.lower():
            if '手机号码' in source_cn or '手机号' in source_cn:
                if '联系人' not in source_cn:
                    return False

        # 5.4 出生地邮政代码 vs 出生地
        if '邮政代码' in target_cn or '邮编' in target_cn:
            if '出生地' in source_cn and '邮政' not in source_cn and '邮编' not in source_cn:
                return False

        # 5.5 行政区划代码 vs 完整地址或不同粒度的代码
        # 检查目标字段是否是特定粒度的代码（省市、地市、区县）
        target_granularity_keywords = ['省市代码', '地市代码', '区县代码', '街道代码']
        has_target_granularity = any(kw in target_cn for kw in target_granularity_keywords)

        if has_target_granularity or '行政区划代码' in target_cn:
            # 如果源字段是完整地址（不是代码），则不兼容
            if ('居住地址' in source_cn or '住址' in source_cn):
                if '代码' not in source_cn and '编码' not in source_cn:
                    return False
            # 如果源字段是通用的行政区划代码（没有指定粒度），且目标有特定粒度，则不兼容
            elif '行政区划代码' in source_cn:
                # 检查源字段是否有粒度信息
                source_granularity_keywords = ['省市', '地市', '区县', '街道']
                has_source_granularity = any(kw in source_cn for kw in source_granularity_keywords)
                if not has_source_granularity:
                    # 源字段是通用代码，目标是特定粒度代码，可能不兼容
                    # 但如果前缀相同（如"居住地"），则可能兼容
                    target_prefix = target_cn.split('-')[0].strip() if '-' in target_cn else target_cn.split('代码')[0].strip()
                    source_prefix = source_cn.split('-')[0].strip() if '-' in source_cn else source_cn.split('代码')[0].strip()
                    if target_prefix != source_prefix:
                        return False

        # 5.6 检查字段名中的关键差异
        # 如果目标字段包含"电话"，源字段也包含"电话"，但前缀不同，则不兼容
        if '电话' in target_cn and '电话' in source_cn:
            # 提取前缀（电话之前的部分）
            target_prefix = target_cn.split('电话')[0].strip()
            source_prefix = source_cn.split('电话')[0].strip()
            # 如果前缀不同（包括一个有一个没有的情况），则不兼容
            # 例如："联系人电话" vs "电话号码"（一个有前缀"联系人"，一个没有）
            if target_prefix != source_prefix:
                return False

        # 5.7 检查"出生地"相关字段的语义冲突
        # 出生地-邮政代码 不应该匹配到 出生地（区域）
        if '出生地' in target_cn and '出生地' in source_cn:
            # 如果目标字段有具体属性（如邮政、省市、区县），但源字段没有，则不兼容
            target_attrs = ['邮政', '省市', '地市', '区县', '街道']
            source_attrs = ['邮政', '省市', '地市', '区县', '街道']
            target_has_attr = any(attr in target_cn for attr in target_attrs)
            source_has_attr = any(attr in source_cn for attr in source_attrs)
            if target_has_attr and not source_has_attr:
                return False
            if not target_has_attr and source_has_attr:
                return False

        # 5.8 检查"手机号码"相关字段的语义冲突
        # 工作单位电话、联系人电话 不应该匹配到 手机号码
        if '手机号码' in source_cn or '手机号' in source_cn:
            # 源字段是手机号码，检查目标字段是否也是手机相关
            target_phone_keywords = ['手机', '移动']
            if not any(kw in target_cn for kw in target_phone_keywords):
                # 目标字段不是手机相关，但有特定前缀（如工作单位、联系人），则不兼容
                target_prefixes = ['工作单位', '联系人', '家庭', '办公室', '单位']
                if any(prefix in target_cn for prefix in target_prefixes):
                    return False

        # 5.9 检查"固定电话"与"手机号码"的语义冲突
        if ('固定电话' in target_cn or '座机' in target_cn) and ('手机' in source_cn):
            return False
        if ('手机' in target_cn) and ('固定电话' in source_cn or '座机' in source_cn):
            return False

        # 5.10 检查"出生地"与"常住地址"的语义冲突
        # 出生地相关的代码字段不应该匹配到常住地址相关的代码字段
        if '出生地' in target_cn and '常住地址' in source_cn:
            return False
        if '常住地址' in target_cn and '出生地' in source_cn:
            return False

        # 5.11 电话 vs 邮编冲突检查
        # 电话号码不应该匹配到邮政编码字段
        if '电话' in target_cn and ('邮编' in source_cn or '邮政编码' in source_cn):
            return False
        if ('邮编' in target_cn or '邮政编码' in target_cn) and '电话' in source_cn:
            return False

        # 5.12 代码字段 vs 地址字段冲突检查
        # 代码字段（包含"代码"、"编码"）不应该匹配到地址字段（包含"地址"但不包含"代码"）
        if ('代码' in target_cn or '编码' in target_cn):
            if '地址' in source_cn and '代码' not in source_cn and '编码' not in source_cn:
                return False
        if '地址' in target_cn and '代码' not in target_cn and '编码' not in target_cn:
            if ('代码' in source_cn or '编码' in source_cn):
                return False

        # 5.13 日期时间字段语义检查
        # 业务时间字段（create_time, update_time等）不应该匹配到个人日期字段（出生日期等）
        business_time_keywords = ['业务', '系统', '创建', '更新', '产生']
        personal_time_keywords = ['出生', '生日', '年龄']

        is_target_business_time = any(kw in target_cn for kw in business_time_keywords)
        is_source_personal_time = any(kw in source_cn for kw in personal_time_keywords)
        is_target_personal_time = any(kw in target_cn for kw in personal_time_keywords)
        is_source_business_time = any(kw in source_cn for kw in business_time_keywords)

        if is_target_business_time and is_source_personal_time:
            return False
        if is_target_personal_time and is_source_business_time:
            return False

        # 5.13.1 日期 vs 日期时间 精度检查
        # "日期时间" 不应该匹配到 "日期"（精度不同）
        target_has_time = '时间' in target_cn or target_field.data_type in ('DT', 'D19', 'datetime')
        source_has_time = '时间' in source_cn or source_field.data_type in ('DT', 'D19', 'datetime')
        target_is_date_only = ('日期' in target_cn and '时间' not in target_cn and
                               target_field.data_type in ('D', 'D10', 'date'))
        source_is_date_only = ('日期' in source_cn and '时间' not in source_cn and
                               source_field.data_type in ('D', 'D10', 'date'))

        # 如果一个是日期时间，另一个只是日期，则不兼容
        if target_has_time and source_is_date_only:
            return False
        if target_is_date_only and source_has_time:
            return False

        # 5.13.2 住院号 vs 病案号 区分
        # 这两个是不同的标识符，不应该互相匹配
        if '住院号' in target_cn and '病案号' in source_cn:
            return False
        if '病案号' in target_cn and '住院号' in source_cn:
            return False

        # 5.13.3 证件号码 vs 身份证类别代码 区分
        # 一个是号码，一个是类别代码，完全不同
        target_is_number = '号码' in target_cn or '证号' in target_cn
        source_is_type = '类别' in source_cn or '类型' in source_cn
        target_is_type = '类别' in target_cn or '类型' in target_cn
        source_is_number = '号码' in source_cn or '证号' in source_cn

        if target_is_number and source_is_type:
            return False
        if target_is_type and source_is_number:
            return False

        # 5.14 标准引用识别
        # 如果目标字段引用了某个标准（如GB/T 2260），源字段也引用了相同标准，则可以匹配
        # 这是一个正向规则，允许匹配而不是阻止匹配
        if 'GB/T 2260' in target_desc and 'GB/T 2260' in source_desc:
            # 都引用了行政区划标准，可能是兼容的，允许继续匹配
            pass

        # 5.15 电话字段类型检查
        # 电话字段（包含"电话"）应该只匹配到电话相关字段
        if '电话' in target_cn or 'phone' in target_field.name.lower() or 'tel' in target_field.name.lower():
            # 目标字段是电话字段，源字段也应该是电话相关
            source_phone_keywords = ['电话', '手机', '联系电话', 'phone', 'tel', 'mobile']
            if not any(kw in source_cn for kw in source_phone_keywords):
                # 源字段不是电话相关，不兼容
                if source_cn:  # 如果有源字段名，才检查
                    return False

        # 5.16 姓名字段检查
        # 5.17 地址粒度检查 - 子地址组件不应匹配完整地址
        # 5.17 地址粒度检查 - 子地址组件不应匹配完整地址或不同位置的子地址
        # 子地址组件关键词（地址的一部分，不是完整地址）
        sub_addr_kw = ['详细地址', '门牌号', '门牌号码']
        # 完整地址关键词（完整的地址字段）
        full_addr_kw = ['户口地址', '居住地址', '户籍地址', '现住址', '联系地址', '住址']
        # 位置前缀（区分不同位置的地址）
        location_prefixes = ['出生地', '现住', '户籍', '居住地', '常住']

        target_is_sub = any(kw in target_cn for kw in sub_addr_kw)
        source_is_full = any(kw in source_cn for kw in full_addr_kw)
        target_is_full = any(kw in target_cn for kw in full_addr_kw)
        source_is_sub = any(kw in source_cn for kw in sub_addr_kw)

        # 子地址组件不应匹配不同类型的完整地址
        if target_is_sub and source_is_full:
            return False
        if target_is_full and source_is_sub:
            return False

        # 两个子地址字段如果位置前缀不同，不应匹配
        if target_is_sub and source_is_sub:
            target_loc = next((p for p in location_prefixes if p in target_cn), None)
            source_loc = next((p for p in location_prefixes if p in source_cn), None)
            if target_loc and source_loc and target_loc != source_loc:
                return False

        return True

    def _is_field_mapping_compatible(self, target_field, source_field, field_mapping) -> bool:
        """检查field_mapping配置的目标字段和源字段是否兼容。

        用于在应用field_mapping之前进行最终校验，防止：
        - 代码字段映射到名称/文本字段
        - 类型严重不匹配的字段

        Args:
            target_field: 目标字段
            source_field: 源字段
            field_mapping: field_mappings.yaml 中的映射配置

        Returns:
            True=兼容，可以应用映射；False=不兼容，跳过此映射
        """
        target_cn = target_field.chinese_name or ''
        source_cn = source_field.chinese_name or ''

        # 规则1：代码字段不应映射到名称/文本字段
        code_keywords = ['代码', '编码', '代号']
        name_keywords = ['名称', '姓名']

        target_is_code = any(kw in target_cn for kw in code_keywords)
        source_is_name = any(kw in source_cn for kw in name_keywords)
        source_is_code = any(kw in source_cn for kw in code_keywords)
        target_is_name = any(kw in target_cn for kw in name_keywords)

        if target_is_code and source_is_name and not source_is_code:
            # 目标是代码字段，源是纯名称字段（不含代码关键词），不兼容
            return False
        if target_is_name and source_is_code and not target_is_code:
            # 目标是名称字段，源是纯代码字段，不兼容
            return False

        # 规则2：检查数据类型兼容性（代码类型 vs 文本类型）
        # control_field和user_custom类型的映射跳过类型检查（因为控制字段可能类型不同但语义相同）
        match_type = field_mapping.get('match_type', '')
        if match_type not in ('control_field', 'user_custom'):
            target_type = (target_field.data_type or '').upper()
            source_type = (source_field.data_type or '').upper()

            def type_group(t):
                if t in ('DT', 'D'):
                    return 'datetime'
                if t == 'N':
                    return 'numeric'
                if t == 'S3':
                    return 'code'
                if t in ('S1', 'S2'):
                    return 'text'
                return 'other'

            tg, sg = type_group(target_type), type_group(source_type)
            # 日期/数值类型与任何其他类型都不兼容
            strict = {'datetime', 'numeric'}
            if tg in strict or sg in strict:
                if tg != sg:
                    return False

        # 规则3：粒度冲突 - 通用的源字段不应映射到特定粒度的目标字段
        # 例如：CSD（通用出生地）不应映射到 birth_province_code（出生地-省市代码）
        # 除非源字段本身包含粒度信息
        match_type = field_mapping.get('match_type', '')
        if match_type == 'standard_reference':
            target_granularity = ['省市', '地市', '区县', '街道', '村']
            source_granularity = ['省市', '地市', '区县', '街道', '村']
            target_has_granularity = any(kw in target_cn for kw in target_granularity)
            source_has_granularity = any(kw in source_cn for kw in source_granularity)
            if target_has_granularity and not source_has_granularity:
                # 目标有特定粒度但源字段没有，不兼容
                return False

        return True

    def _is_type_compatible_for_keyword(self, target_field, source_field) -> bool:
        """keyword匹配时的数据类型兼容性检查。
        防止类型完全不同的字段因关键词重叠而被误匹配，
        例如 '就诊类型代码'(S3) 误匹配 '就诊日期时间'(DT)。
        """
        target_type = (target_field.data_type or '').upper()
        source_type = (source_field.data_type or '').upper()

        if not target_type or not source_type:
            return True  # 类型信息缺失时不阻断

        def type_group(t):
            if t in ('DT', 'D'):
                return 'datetime'
            if t == 'N':
                return 'numeric'
            if t == 'S3':
                return 'code'
            if t in ('S1', 'S2'):
                return 'text'
            return 'other'

        tg, sg = type_group(target_type), type_group(source_type)
        if tg == sg:
            return True
        # 日期/数值类型与任何其他类型都不兼容
        strict = {'datetime', 'numeric'}
        if tg in strict or sg in strict:
            return False
        return True

    @staticmethod
    def _is_code_name_compatible(name1: str, name2: str) -> bool:
        """代码字段与名称字段不应通过keyword匹配。
        例如 '责任医师代码' 不应匹配 '责任医师姓名'。

        同时检查更多语义冲突：
        - 代码/编码 vs 用法/方法（关键药品代码 ≠ 关键药物用法）
        - 姓名/签名 vs 工号/编号（检验医师姓名 ≠ 检验医师工号）
        - 代码/编码 vs 描述/所见（检查报告结果客观所见 ≠ 检查结果代码）
        - 流水号 vs 工号（会诊医师流水号 ≠ 会诊记录流水号）
        """
        code_kw = ('代码', '编码')
        name_kw = ('名称', '姓名')
        usage_kw = ('用法', '方法', '途径')
        work_no_kw = ('工号', '编号', '员工号', '身份证号码', '身份证号')
        desc_kw = ('描述', '所见', '综述', '意见', '情况')
        sign_kw = ('签名', '签章')
        serial_kw = ('流水号', '序列号')
        org_kw = ('机构', '医院', '单位', '科室', '部门')

        # 代码 vs 名称
        n1_is_code = any(k in name1 for k in code_kw)
        n1_is_name = any(k in name1 for k in name_kw)
        n2_is_code = any(k in name2 for k in code_kw)
        n2_is_name = any(k in name2 for k in name_kw)
        if (n1_is_code and n2_is_name) or (n1_is_name and n2_is_code):
            return False

        # 代码/编码 vs 用法/方法（关键药品代码 ≠ 关键药物用法）
        n1_is_usage = any(k in name1 for k in usage_kw)
        n2_is_usage = any(k in name2 for k in usage_kw)
        if (n1_is_code and n2_is_usage) or (n1_is_usage and n2_is_code):
            return False

        # 姓名/签名 vs 工号/编号（检验医师姓名 ≠ 检验医师工号）
        # 包含"人"字的字段（如"发布人"、"操作人"）也视为人员标识
        person_name_indicators = name_kw + sign_kw + ('发布人', '操作人', '签名人', '记录人')
        n1_is_person_name = any(k in name1 for k in person_name_indicators)
        n2_is_person_name = any(k in name2 for k in person_name_indicators)
        n1_is_work_no = any(k in name1 for k in work_no_kw)
        n2_is_work_no = any(k in name2 for k in work_no_kw)
        if (n1_is_person_name and n2_is_work_no) or (n1_is_work_no and n2_is_person_name):
            return False

        # 代码 vs 工号/身份证号码（报告医师代码 ≠ 报告医生身份证号码）
        if (n1_is_code and n2_is_work_no) or (n1_is_work_no and n2_is_code):
            return False

        # 描述/所见 vs 代码/编码（检查报告结果客观所见 ≠ 检查结果代码）
        n1_is_desc = any(k in name1 for k in desc_kw)
        n2_is_desc = any(k in name2 for k in desc_kw)
        if (n1_is_desc and n2_is_code) or (n1_is_code and n2_is_desc):
            return False

        # 流水号 vs 工号/编号（会诊医师流水号 ≠ 会诊记录流水号）
        n1_is_serial = any(k in name1 for k in serial_kw)
        n2_is_serial = any(k in name2 for k in serial_kw)
        if (n1_is_serial and n2_is_work_no) or (n1_is_work_no and n2_is_serial):
            return False

        # 主体冲突检查：医师代码 ≠ 机构代码，科室代码 ≠ 工号
        # 提取主体前缀（代码/编码/工号等关键词之前的部分）
        def extract_subject(name):
            for kw in code_kw + work_no_kw + serial_kw:
                if kw in name:
                    return name.split(kw)[0].strip()
            return name

        subj1 = extract_subject(name1)
        subj2 = extract_subject(name2)

        # 医师 vs 机构（报告医师代码 ≠ 报告医疗机构代码）
        person_keywords = ['医师', '医生', '护士', '操作员', '操作员', '技师']
        org_keywords = ['机构', '医院', '科室', '部门', '单位']
        sub1_is_person = any(k in subj1 for k in person_keywords)
        sub2_is_person = any(k in subj2 for k in person_keywords)
        sub1_is_org = any(k in subj1 for k in org_keywords)
        sub2_is_org = any(k in subj2 for k in org_keywords)
        if (sub1_is_person and sub2_is_org) or (sub1_is_org and sub2_is_person):
            return False

        # 科室 vs 人员（会诊医师所属科室代码 ≠ 会诊医师工号）
        dep_keywords = ['科室', '部门', '病区']
        sub1_is_dep = any(k in subj1 for k in dep_keywords)
        sub2_is_dep = any(k in subj2 for k in dep_keywords)
        if (sub1_is_dep and sub2_is_person) or (sub1_is_person and sub2_is_dep):
            return False

        # 关系/类型 vs 代码（严重不良事件与实验药的关系代码 ≠ 不良事件报告类型代码）
        relation_kw = ('关系', '关联', '因果')
        type_kw = ('类型', '类别', '种类')
        n1_is_relation = any(k in name1 for k in relation_kw)
        n2_is_relation = any(k in name2 for k in relation_kw)
        n1_is_type = any(k in name1 for k in type_kw)
        n2_is_type = any(k in name2 for k in type_kw)
        if (n1_is_relation and n2_is_type) or (n1_is_type and n2_is_relation):
            return False

        return True

    def _is_keyword_match(self, name1: str, name2: str) -> bool:
        """基于n-gram关键词重叠匹配"""
        if not name1 or not name2:
            return False

        # 先检查角色兼容性（住院医师 ≠ 转出医师，退号 ≠ 挂号，记录医师 ≠ 患者）
        if not self._is_role_compatible_for_keyword(name1, name2):
            return False

        # 清理：去除常见后缀和通用词
        suffixes = ['名称', '代码', '编码', '标识', '标志', '日期', '时间']
        common_words = ['类型', '信息', '记录', '表']  # 通用词，不应作为匹配依据
        clean1 = name1
        clean2 = name2
        for s in suffixes + common_words:
            clean1 = clean1.replace(s, '')
            clean2 = clean2.replace(s, '')

        if not clean1 or not clean2:
            return False

        # 精确匹配（清理后完全相同）
        if clean1 == clean2:
            return True

        # 要求清理后的字符串必须达到最小长度，避免过短导致误匹配
        min_length = 3  # 至少3个字符
        if len(clean1) < min_length or len(clean2) < min_length:
            return False

        # 避免一个字符串是另一个的子串导致误匹配
        # 如果较短的字符串完全包含在较长的字符串中，且长度差异超过50%，则不匹配
        shorter, longer = (clean1, clean2) if len(clean1) <= len(clean2) else (clean2, clean1)
        if shorter in longer and len(shorter) / len(longer) < 0.5:
            return False

        # 提取n-gram
        def get_ngrams(s, n):
            return set(s[i:i+n] for i in range(len(s)-n+1)) if len(s) >= n else {s}

        grams1 = get_ngrams(clean1, self.ngram_size)
        grams2 = get_ngrams(clean2, self.ngram_size)

        if not grams1 or not grams2:
            return False

        # 计算重叠率
        overlap = len(grams1 & grams2)
        min_grams = min(len(grams1), len(grams2))
        overlap_ratio = overlap / min_grams if min_grams > 0 else 0

        # 提高阈值到0.6，减少误匹配
        return overlap_ratio >= 0.6

    @staticmethod
    def _is_role_compatible_for_keyword(name1: str, name2: str) -> bool:
        """检查keyword匹配时两个字段名的角色是否兼容。

        防止以下情况：
        - 住院医师签名 ≠ 转出医师签名（角色不同）
        - 退号操作员 ≠ 挂号操作员（操作类型不同）
        - 记录医师姓名 ≠ 患者姓名（身份不同）
        - 申请医师 ≠ 申请医疗机构（主体不同）
        - 会诊记录流水号 ≠ 会诊医师流水号（主体不同）
        """
        # 角色修饰词（出现在"医师"/"操作员"等之前的词）
        # 提取方式：找到核心角色词之前的部分作为角色修饰

        # 1. 操作类型冲突：退号 vs 挂号，转入 vs 转出
        action_pairs = [
            ('退号', '挂号'), ('转出', '转入'), ('入院', '出院'),
            ('门诊', '住院'), ('申请', '审核'), ('报告', '申请'),
            ('主刀', '助手'), ('第一助手', '第二助手'),
        ]
        for a1, a2 in action_pairs:
            if (a1 in name1 and a2 in name2) or (a2 in name1 and a1 in name2):
                return False

        # 2. 身份冲突：医师 vs 患者，医师 vs 机构
        identity_keywords = {
            'person': ['医师', '医生', '护士', '操作员', '技师', '药师', '检查员'],
            'patient': ['患者', '病人', '患者'],
            'org': ['机构', '医院', '科室', '部门'],
        }
        def get_identity(name):
            for identity, keywords in identity_keywords.items():
                if any(kw in name for kw in keywords):
                    return identity
            return None

        id1 = get_identity(name1)
        id2 = get_identity(name2)
        if id1 and id2 and id1 != id2:
            # 医师 vs 患者 不兼容
            if (id1 == 'person' and id2 == 'patient') or (id1 == 'patient' and id2 == 'person'):
                return False

        # 3. 角色修饰词冲突：住院医师 vs 转出医师，记录医师 vs 患者
        # 提取核心角色（医师/操作员/护士等）之前的修饰词
        core_roles = ['医师', '医生', '护士', '操作员', '技师', '药师']
        def extract_role_modifier(name):
            """提取核心角色词之前的修饰词"""
            for role in core_roles:
                if role in name:
                    # 获取角色词之前的内容
                    prefix = name.split(role)[0].strip()
                    return prefix
            return None

        mod1 = extract_role_modifier(name1)
        mod2 = extract_role_modifier(name2)
        if mod1 and mod2 and mod1 != mod2:
            # 如果修饰词不同且都有意义（长度>=2），则不兼容
            if len(mod1) >= 2 and len(mod2) >= 2:
                # 检查修饰词之间是否是包含关系（如"申请医师" vs "申请医师"）
                if mod1 not in mod2 and mod2 not in mod1:
                    # 额外检查：有些修饰词差异是可接受的（如"责任" vs "主治"）
                    # 但如果完全无关（如"住院" vs "转出"），则不兼容
                    return False

        # 4. 主体冲突：会诊记录 vs 会诊医师
        # 如果一个是"记录"相关，一个是"人员"相关，且都包含"会诊"，则不兼容
        if '会诊' in name1 and '会诊' in name2:
            record_kw = ['记录', '流水号']
            person_kw = ['医师', '医生', '签名']
            n1_is_record = any(k in name1 for k in record_kw)
            n2_is_record = any(k in name2 for k in record_kw)
            n1_is_person = any(k in name1 for k in person_kw)
            n2_is_person = any(k in name2 for k in person_kw)
            if (n1_is_record and n2_is_person) or (n1_is_person and n2_is_record):
                return False

        return True

    def _is_synonym_match(self, name1: str, name2: str) -> bool:
        """检查是否是同义词匹配

        增加角色和语义校验，防止以下误匹配：
        - 检查结果参考值(定性) ≠ 检查所见（参考值≠所见）
        - 记录医师姓名 ≠ 患者姓名（医师≠患者）
        - 退号操作员姓名 ≠ 挂号操作员姓名（退号≠挂号）
        - 电子邮件地址 ≠ 居住地址（通过exclude列表排除）
        """
        if not name1 or not name2:
            return False

        # 检查exclude列表 - 如果任意一个名称在排除列表中，则不匹配
        exclude_list = getattr(self, 'synonym_exclude_list', [])
        if name1 in exclude_list or name2 in exclude_list:
            return False

        # 前置校验：角色/操作类型兼容性
        if not self._is_role_compatible_for_synonym(name1, name2):
            return False

        # 前置校验：语义概念兼容性
        if not self._is_concept_compatible_for_synonym(name1, name2):
            return False

        # 使用配置文件中的同义词映射
        synonyms = self.synonyms

        # 检查是否包含同义词
        for word1, syn_list in synonyms.items():
            if word1 in name1:
                for syn in syn_list:
                    if syn in name2:
                        # 检查剩余部分是否匹配（更宽松的检查）
                        remaining1 = name1.replace(word1, '').strip()
                        remaining2 = name2.replace(syn, '').strip()
                        # 如果剩余部分相同，或者其中一个为空，则认为匹配
                        if remaining1 == remaining2 or not remaining1 or not remaining2:
                            return True
                        # 如果剩余部分有包含关系，也认为匹配
                        if remaining1 in remaining2 or remaining2 in remaining1:
                            return True

            # 反向检查：name2 包含 word1，name1 包含 syn
            if word1 in name2:
                for syn in syn_list:
                    if syn in name1:
                        remaining1 = name2.replace(word1, '').strip()
                        remaining2 = name1.replace(syn, '').strip()
                        if remaining1 == remaining2 or not remaining1 or not remaining2:
                            return True
                        if remaining1 in remaining2 or remaining2 in remaining1:
                            return True

        return False

    @staticmethod
    def _is_role_compatible_for_synonym(name1: str, name2: str) -> bool:
        """检查synonym匹配时的角色兼容性。

        防止：
        - 记录医师姓名 ≠ 患者姓名
        - 退号操作员 ≠ 挂号操作员
        """
        # 1. 操作类型冲突
        action_pairs = [
            ('退号', '挂号'), ('转出', '转入'), ('入院', '出院'),
            ('门诊', '住院'), ('申请', '审核'),
        ]
        for a1, a2 in action_pairs:
            if (a1 in name1 and a2 in name2) or (a2 in name1 and a1 in name2):
                return False

        # 2. 身份冲突：医师/操作员 vs 患者
        person_kw = ['医师', '医生', '护士', '操作员', '技师']
        patient_kw = ['患者', '病人']
        n1_is_person = any(k in name1 for k in person_kw)
        n2_is_person = any(k in name2 for k in person_kw)
        n1_is_patient = any(k in name1 for k in patient_kw)
        n2_is_patient = any(k in name2 for k in patient_kw)
        if (n1_is_person and n2_is_patient) or (n1_is_patient and n2_is_person):
            return False

        return True

    @staticmethod
    def _is_concept_compatible_for_synonym(name1: str, name2: str) -> bool:
        """检查synonym匹配时的语义概念兼容性。

        防止：
        - 检查结果参考值(定性) ≠ 检查所见（参考值是正常范围，所见是实际观察）
        - 关系代码 ≠ 类型代码
        """
        # 1. 参考值 vs 所见/结果
        ref_val_kw = ['参考值', '正常值', '标准值', '范围']
        observation_kw = ['所见', '观察', '描述', '综述']
        n1_is_ref = any(k in name1 for k in ref_val_kw)
        n2_is_ref = any(k in name2 for k in ref_val_kw)
        n1_is_obs = any(k in name1 for k in observation_kw)
        n2_is_obs = any(k in name2 for k in observation_kw)
        if (n1_is_ref and n2_is_obs) or (n1_is_obs and n2_is_ref):
            return False

        # 2. 关系 vs 类型
        relation_kw = ['关系', '关联', '因果']
        type_kw = ['类型', '类别', '种类']
        n1_is_rel = any(k in name1 for k in relation_kw)
        n2_is_rel = any(k in name2 for k in relation_kw)
        n1_is_type = any(k in name1 for k in type_kw)
        n2_is_type = any(k in name2 for k in type_kw)
        if (n1_is_rel and n2_is_type) or (n1_is_type and n2_is_rel):
            return False

        return True

    def _is_semantic_match(self, name1: str, name2: str) -> bool:
        """判断是否语义匹配（使用加权相似度：编辑距离+n-gram+包含关系）"""
        if not name1 or not name2:
            return False

        # 去除空格后比较（快速路径）
        name1_clean = name1.replace(' ', '')
        name2_clean = name2.replace(' ', '')

        if name1_clean == name2_clean:
            return True

        # 使用加权相似度计算
        similarity = _calculate_similarity(name1_clean, name2_clean)
        return similarity >= self.semantic_threshold

    def _check_modifications(self, source_field: StandardField,
                            target_field: StandardField) -> List[Dict]:
        """检查是否需要修改（遵循核心原则2、3、4）"""
        modifications = []

        # 原则2：约束保护 - 目标M → 原标准必须M
        if self.target_M_requires_source_M:
            if target_field.constraint == 'M' and source_field.constraint != 'M':
                modifications.append({
                    'type': 'constraint',
                    'current': source_field.constraint,
                    'required': target_field.constraint,
                    'reason': f'目标标准要求必填(M)，但原标准为{source_field.constraint}'
                })
                self.stats['constraint_issues'] += 1

        # 原则3：长度保护 - 原标准长度 >= 目标标准长度
        if self.length_protection_enabled:
            if source_field.length > 0 and target_field.length > 0 and source_field.length < target_field.length:
                modifications.append({
                    'type': 'length',
                    'current': source_field.length,
                    'required': target_field.length,
                    'reason': f'目标标准长度为{target_field.length}，但原标准长度为{source_field.length}'
                })
                self.stats['length_issues'] += 1

        # 原则4：值域覆盖 - 原标准值域必须覆盖目标标准
        if target_field.value_domains:
            value_domain_issues = self._check_value_domains(source_field, target_field)
            if value_domain_issues:
                modifications.extend(value_domain_issues)
                self.stats['value_domain_issues'] += len(value_domain_issues)

        return modifications

    def _check_value_domains(self, source_field: StandardField,
                            target_field: StandardField) -> List[Dict]:
        """
        检查值域覆盖（原则4：值域覆盖 - 只能扩充，不能修改已有）
        使用三层比对策略：精确 -> 词库语义 -> 相似度
        不确定区间（0.7~threshold）标记为需人工确认
        """
        issues = []

        # 转换值域为字典格式
        source_vds = [{'code': vd.code, 'name': vd.name} for vd in (source_field.value_domains or [])]
        target_vds = [{'code': vd.code, 'name': vd.name} for vd in (target_field.value_domains or [])]

        if not target_vds:
            return issues

        # 如果没有原标准值域，所有目标值域都需要新增
        if not source_vds:
            for tv in target_vds:
                issues.append({
                    'type': 'value_domain',
                    'current': '缺少',
                    'required': f'{tv["code"]}:{tv["name"]}',
                    'reason': f'目标标准包含值域 {tv["code"]}:{tv["name"]}，但原标准缺少（需扩充）'
                })
            return issues

        # 使用三层比对策略
        result = _compare_value_domains_advanced(
            source_values=source_vds,
            target_values=target_vds,
            synonyms=self.synonyms,
            similarity_threshold=self.vd_threshold,
            uncertain_lower_bound=self.vd_uncertain_lower
        )

        # 收集不确定项（需人工确认）
        for item in result.uncertain:
            src = item.get('source', {})
            tgt = item.get('target', {})
            issues.append({
                'type': 'value_domain',
                'current': f'{src.get("code", "")}:{src.get("name", "")}',
                'required': f'{tgt.get("code", "")}:{tgt.get("name", "")}',
                'reason': f'值域语义相似(相似度{item.get("similarity", 0):.2f})但含义可能不同，需人工确认'
            })

        # 收集需新增项
        for item in result.additions:
            tgt = item.get('target', {})
            issues.append({
                'type': 'value_domain',
                'current': '缺少',
                'required': f'{tgt.get("code", "")}:{tgt.get("name", "")}',
                'reason': f'目标标准包含值域 {tgt.get("code", "")}:{tgt.get("name", "")}，但原标准缺少（需扩充）'
            })

        return issues

    def get_stats(self) -> Dict:
        """获取比对统计信息"""
        return dict(self.stats)
