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
from collections import deque, defaultdict
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass, field
from parsers.standard_parser import StandardDocument, StandardTable, StandardField

# 规则核心模块（唯一事实来源）：核心概念/显式同义判定统一入口
from matchers.matching_core import core_compatible, in_explicit_synonym_dict, strip_generic
from matchers.matching_core import COMPARATOR_PREFIXES as _CORE_GENERIC_PREFIXES
from matchers.matching_core import GENERIC_SUFFIXES as _CORE_GENERIC_SUFFIXES

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
    kb_conflicts: Dict = None  # 知识库陈旧结论冲突（供人工复核与知识库订正）
    ghost_source_tables: List = None  # 幽灵来源告警：映射指定源表在源标准中不存在

    def __post_init__(self):
        if self.matched is None:
            self.matched = []
        if self.modified is None:
            self.modified = []
        if self.new_fields is None:
            self.new_fields = []
        if self.new_tables is None:
            self.new_tables = []
        if self.kb_conflicts is None:
            self.kb_conflicts = {'stale_negative': [], 'stale_positive': []}
        if self.ghost_source_tables is None:
            self.ghost_source_tables = []


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
        # ===== 自动外键关联通道（P6：多表关联）=====
        # 源标准字段说明里写明了外键关联（"外键，SYS_SOID+X与XX表[T]中的Y字段关联"），
        # 可自动解析成"源表关联图"：目标表字段在当前对齐源表找不到时，沿关联图
        # 到子表/关联表（卡证子表、地址子表等）里找同概念字段。这是"表不只是一对一，
        # 可能是多表关联"的结构化支撑——relations 知识库只覆盖人工显式建模的关系，
        # 而源标准说明中的外键关系（实测 495 条）几乎全量可解析。
        self.auto_relation_enabled = fm_config.get('auto_relation_enabled', True)
        self._auto_adjacency = {}   # 表名 -> set(相邻表名)，双向
        self._auto_fk_edges = []    # (本表, 本表中文, 本表字段, 目标表, 目标表中文, 目标字段)
        # 无 FK 边的主词表集合（如 PERSON 患者基本信息）：主词表不可反向借业务子表字段，
        # 仅属性子表（表名以主表名+"_"开头，如 PERSON_ADDRESS）例外。
        # 由 _build_auto_relations 在 FK 解析后填充。
        self._master_tables = set()
        # 同一目标表内"一个源字段只归一个目标字段"占用保护（auto_relation 通道专用）。
        # dict[target_table_name] -> {(rel_table, src_field): 占用者目标字段中文名}
        # 记录占用者中文名是为了支持"子表类型代码区分场景"下的合法复用判定。
        self._auto_relation_used = None  # compare() 内 _build_auto_relations 时初始化为 {}

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
        # 跨表全局复用索引（key=字段语义，value=源字段信息，不绑定源表）
        self.user_custom_field_mappings_global = self.kb._cache.get(
            'user_custom_field_mappings_global', {}) or {}

        # ===== 陈旧否定确认治理（P4）=====
        # 知识库中"确认无对应源字段（=新增）"的条目是相对特定源标准的否定结论，
        # 换源标准后不再成立。开启后：若本次源标准中确实存在同名字段，
        # 以标准原文为准撤销该确认，并登记冲突供人工复核。
        self.stale_negative_override = fm_config.get('stale_negative_override', True)
        # 撤销陈旧否定确认时，是否允许"同义变体"也作为事实证据
        # （麻醉分级代码 ← 麻醉分级、医嘱开立科室代码 ← 医嘱开立科室编码）
        self.stale_negative_override_fuzzy = fm_config.get(
            'stale_negative_override_fuzzy', True)
        # 撤销陈旧否定确认时，是否允许"语义基名"也作为事实证据
        # （患者电子邮件地址←电子邮件地址、出生地-省市代码←出生地（省市）等
        #   前缀/地址组件差异只有语义基名能对齐，norm/fuzzy 基名都识别不了）
        self.stale_negative_override_semantic = fm_config.get(
            'stale_negative_override_semantic', True)
        self.stale_negative_conflicts = []

        # ===== 陈旧/脏正向映射治理（P5）=====
        # 知识库中"确认字段A对应源字段B"是**人工领域判断**，人是权威，不能被
        # 启发式规则静默否决。实测（区域平台60 vs 云南v1.4.1）表明：
        #   语义硬冲突网关只抓到 3 个真错中的 1 个，却误杀约 40 条正确人工确认
        #   （医嘱停止医师姓名←停嘱医生姓名、人员代码←职工编码、
        #     身份证件类别代码←证件类型、居住地-邮政代码←现住址邮编 …）
        # 因此默认**只检测、不否决**：可疑映射登记到 user_custom_conflicts，
        # 随比对结果外带（kb_conflicts.stale_positive），交人工复核并订正知识库
        # ——脏数据要修在知识库里，而不是在匹配期猜。
        # 仅在明确需要"强网关"时才置 True（会牺牲覆盖率）。
        self.user_custom_hard_gate = fm_config.get('user_custom_hard_gate', False)
        self.user_custom_conflicts = []

        # ===== 跨表同义级兜底（P4）=====
        # relations 知识库只覆盖显式建模的表间关系，很多同义变体落在未建关系的表里。
        # 开启后在 cross_table 阶段按"基名"做一次全局兜底查找。
        self.cross_table_fuzzy = fm_config.get('cross_table_fuzzy', True)

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

    # ======================================================================
    # 序号字段组（主子表展开）— 通用自动检测
    # ----------------------------------------------------------------------
    # 规律：目标标准把"原标准的主子表"展开成多列序号字段
    #   （如 出院西医其他诊断疾病代码1..N / 其他手术操作代码1..N），
    #   而原标准用「主表 + 子表（一行一记录）」存储。
    # 通用做法（不依赖任何硬编码表名 / 正则 pattern）：
    #   1) 自动检测目标表中带数字后缀的序号字段
    #      （中文名尾随 1..N / 一二三…；英文名尾随 _1 / 1）；
    #   2) 按「基础名」（剥离尾随数字与字段角色尾词）聚类；
    #   3) 对每个聚类，从其「对齐源主表」的候选子表中，用「域概念关键词
    #      重叠」选出最匹配的子表（中文名前缀兄弟 / P6 外键邻接 / 英文名族前缀）；
    #   4) 命中子表 → 整组字段标注为「主子表映射」，归属该子表
    #      （不计入主表新增字段；统计字段数时视为被子表覆盖）；
    #   5) 找不到匹配子表（如 重症监护 / 新生儿 在本标准无对应子表）→
    #      这些序号字段保持为普通字段，由原常规通道判断匹配或新增。
    # 这样换一套标准（不同表名、不同子表命名）也能自动适配。
    # ======================================================================

    # 序号后缀检测
    _NUM_SUFFIX_RE = re.compile(r'^(.*?)\s*([一二三四五六七八九十\d]+)\s*[）)]?\s*$')
    _NUM_SUFFIX_PAREN_RE = re.compile(r'^(.*?)[（(]\s*[一二三四五六七八九十]+\s*孩\s*[）)]\s*$')
    _EN_NUM_SUFFIX_RE = re.compile(r'^(.*?)[_ ]?(?:[a-z]*\d+|[一二三四五六七八九十]+)$')

    # 字段角色尾词（从基础名中剥离，用于提取「域概念」）。按长度降序排列。
    _ROLE_TAILS = [
        'Ⅰ助', 'Ⅱ助', '一助', '二助', '三助',
        '唯一标识', '流水号', '序号', '编号', '标识', '标志',
        '持续时间', '日期时间', '日期', '时间',
        '麻醉方式', '麻醉医师', '麻醉分级',
        '切口愈合等级', '切口类别', '愈合等级',
        '助', '级别', '等级', '类别', '类型',
        '医师', '名称', '姓名', '编码', '代码', '号',
    ]

    # 通用布尔前缀（从基础名开头剥离，避免「是否…」与子表「是否主要诊断」等
    # 弱子串误匹配，导致操作类字段误映射到诊断子表）。
    _GEN_PREFIXES = ['是否', '有无', '需']

    # 字段角色 → 关键词（按关键词长度降序，用于从字段名后缀判定角色）。
    # 角色用于把「目标序号字段」映射到子表里「同角色」的字段
    # （如 诊断代码 → 子表 诊断代码 字段；诊断名称 → 诊断名称 字段）。
    _ROLE_KEYWORDS = [
        ('code', ['代码', '编码']),
        ('name', ['名称', '姓名']),
        ('datetime', ['日期时间']),
        ('date', ['日期']),
        ('time', ['时间']),
        ('doctor', ['Ⅰ助', 'Ⅱ助', '一助', '二助', '三助', '麻醉医师', '医师', '助']),
        ('anaesthesia', ['麻醉方式', '麻醉分级']),
        ('incision', ['切口愈合等级', '切口类别', '愈合等级']),
        ('type', ['类型', '类别', '级别', '等级']),
        ('duration', ['持续时间']),
        ('id', ['唯一标识', '流水号', '序号', '编号', '标识', '标志', '号']),
    ]

    def _strip_number_suffix(self, cn: str, en: str):
        """返回 (base_cn, base_en)：剥离尾随序号后的基础名；无序号返回 (None, None)。"""
        base_cn = None
        if cn:
            m = self._NUM_SUFFIX_RE.match(cn)
            if m and m.group(2):
                base_cn = m.group(1).strip()
            else:
                m2 = self._NUM_SUFFIX_PAREN_RE.match(cn)
                if m2:
                    base_cn = m2.group(1).strip()
        base_en = None
        if en:
            m = self._EN_NUM_SUFFIX_RE.match(en)
            if m:
                base_en = m.group(1)
        return base_cn, base_en

    @staticmethod
    def _strip_role_tail(text: str) -> str:
        """剥离字段角色尾词与括号内说明，提取域概念。

        例：'出院西医其他诊断疾病代码'→'出院西医其他诊断疾病'
            '其他手术操作Ⅰ助'→'其他手术操作'
            '入院病情(对应其他诊断1)'→'入院病情'
        """
        if not text:
            return ''
        t = re.sub(r'[（(][^）)]*[）)]', '', text)  # 去括号内说明
        t = t.strip()
        # 剥离开头通用布尔前缀（是否 / 有无 / 需）
        for pfx in StandardComparator._GEN_PREFIXES:
            if t.startswith(pfx):
                t = t[len(pfx):].strip()
                break
        changed = True
        while changed:
            changed = False
            for tail in StandardComparator._ROLE_TAILS:
                if t.endswith(tail) and len(t) > len(tail):
                    t = t[: -len(tail)].strip()
                    changed = True
                    break
        return t

    def _cluster_numbered_fields(self, target_table, min_group: int) -> Dict[str, list]:
        """检测目标表序号字段并按基础名聚类。返回 {base_key: [field,...]}（仅 >= min_group）。"""
        groups = defaultdict(list)
        for f in target_table.fields:
            base_cn, base_en = self._strip_number_suffix(
                f.chinese_name or '', f.name or '')
            if base_cn or base_en:
                key = base_cn or base_en
                groups[key].append(f)
        return {k: v for k, v in groups.items() if len(v) >= min_group}

    def _find_sub_table_candidates(self, source_table, source_table_index) -> list:
        """从对齐源主表出发，找出候选子表（主子表关系）。

        主子表的可靠信号是「子表中文名以主表中文名为前缀」
        （如 病案首页 → 病案首页出院诊断 / 病案首页手术），这是中文卫生信息标准
        的普遍命名约定，可跨标准复用、不依赖硬编码表名。

        仅当按中文前缀找不到任何兄弟子表时，才回退到「英文名族前缀」
        （MAHP_MAIN ↔ MAHP_DIAGNOSIS 同族）。

        注意：P6 外键邻接表多为「目录 / 信息表 / 代码表」等参照表
        （疾病诊断目录、医护人员信息表、科室信息…），它们不是主子表意义上的
        子表，若纳入候选会因弱子串匹配导致误映射，故不纳入候选。
        """
        main_cn = source_table.chinese_name or ''
        main_en = source_table.name or ''

        # 1) 首选：中文名前缀兄弟表
        cands = []
        seen = set()
        if main_cn:
            for name, st in source_table_index.items():
                if name == source_table.name:
                    continue
                st_cn = st.chinese_name or ''
                if st_cn.startswith(main_cn) and len(st_cn) > len(main_cn):
                    seen.add(name)
                    cands.append(st)

        # 2) 回退：仅当中文前缀未命中时，才用英文名族前缀（如 MAHP_*）
        if not cands and main_en and '_' in main_en:
            fam = main_en.split('_')[0]
            for name, st in source_table_index.items():
                if name == source_table.name or name in seen:
                    continue
                st_en = st.name or ''
                if ('_' in st_en and st_en.split('_')[0] == fam
                        and st_en != main_en):
                    seen.add(name)
                    cands.append(st)
        return cands

    @staticmethod
    def _has_common_substr(a: str, b: str, min_len: int = 2) -> bool:
        """a、b 是否存在长度 >= min_len 的公共子串。"""
        if not a or not b:
            return False
        dp = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
        best = 0
        for i in range(1, len(a) + 1):
            ai = a[i - 1]
            for j in range(1, len(b) + 1):
                if ai == b[j - 1]:
                    dp[i][j] = dp[i - 1][j - 1] + 1
                    if dp[i][j] > best:
                        best = dp[i][j]
        return best >= min_len

    def _domain_subtable_score(self, domain: str, sub_table) -> int:
        """域概念与子表的重叠得分：子表中含域概念（>=2 字公共子串）的字段数。

        round7：比较前做「手术/操作同族归一」——目标标准多用「手术及操作」，
        源标准子表名/字段名只用「手术」，若不归一，「是否为日间操作」这类
        手术族序号组会被误判为无匹配子表而漏出组外。
        """
        if not domain:
            return 0
        dom = self._norm_proc_name(domain)
        score = 0
        sub_cn = self._strip_role_tail(self._norm_proc_name(sub_table.chinese_name or ''))
        if self._has_common_substr(dom, sub_cn, 2):
            score += 1
        for sf in sub_table.fields:
            sf_base = self._strip_role_tail(self._norm_proc_name(sf.chinese_name or ''))
            if not sf_base:
                continue
            if self._has_common_substr(dom, sf_base, 2):
                score += 1
        return score

    @staticmethod
    def _field_role(cn: str) -> str:
        """从字段中文名后缀判定角色（code/name/date/doctor/...）。"""
        if not cn:
            return ''
        for role, kws in StandardComparator._ROLE_KEYWORDS:
            for kw in kws:
                if cn.endswith(kw) and len(cn) > len(kw):
                    return role
        return ''

    @staticmethod
    def _role_keyword(cn: str) -> str:
        """返回字段中文名末尾命中的具体角色关键词（如 Ⅰ助/麻醉方式/切口类别/代码）。"""
        if not cn:
            return ''
        for role, kws in StandardComparator._ROLE_KEYWORDS:
            for kw in kws:
                if cn.endswith(kw) and len(cn) > len(kw):
                    return kw
        return ''

    # ---- round7：手术族多序号字段匹配修复 ----
    # 病案首页手术族（其他手术操作Ⅰ助/Ⅱ助/麻醉方式/切口类别/麻醉分级/手术类型…、
    # 是否为日间手术/日间操作）大面积错配的根因：
    #   旧 `_map_numbered_field_to_subfield` 只用「角色硬过滤 + 剥离后的域概念
    #   公共子串(>=2)」打分。角色硬过滤把 Ⅰ助→doctor 的正确候选
    #   （手术一助姓名 role=name / 手术一助标识 role=id）全部跳过，反而放行
    #   role='' 的「是否是主要手术」；域概念又只剥到「其他手术操作」，与所有
    #   手术子表字段共享「手术」子串(=2)，无法区分具体字段 → 整族错配到
    #   主字段/唯一标识（MAIN_OP_FLAG x234、OPERATION_ID x39）。
    # 新方案（通用，不硬编码表名）：
    #   1) 全名规范化（Ⅰ/Ⅱ/Ⅲ→一/二/三、操作→手术、类型→类别、医生/术者→医师）
    #      后按「最长公共子串」打分，不再剥光角色尾词——「其他手术操作一助」vs
    #      「手术一助姓名」直接命中「手术一助」=4，天然区分「是否是主要手术」=2；
    #   2) 目标末尾角色关键词（_role_keyword：Ⅰ助/麻醉方式/切口类别/代码…）在
    #      源字段名中出现 → +30（切口类别→手术切口类别代码，而不是切口愈合等级）；
    #   3) 源字段全名是目标基础名的「子序列」→ +30，且平局时短名（通用字段）优先
    #      （其他手术操作代码→手术代码[OP_NO]，而非手术切口类别代码）；
    #   4) 手术角色族术语对齐（麻醉/一助/二助/术者·医师）→ +40，把
    #      「其他手术医师」正确导向「术者姓名」而非「麻醉医师标识」；
    #   5) 目标英文后缀（_code/_name/_id）与源英文名（CODE/NAME/ID）对齐 → +15
    #      （一助三字段、麻醉方式 code/name 间消歧）；
    #   6) 角色一致 → +30；目标非标志类、源为唯一标识/序号/标志 → -30；
    #   7) 总分 < _PROC_MIN_SCORE(=4) 视为无对应源字段 → sub_field=''，
    #      归属子表新增（如 是否为日间手术/日间操作：源标准只有病案级
    #      是否日间手术病例[AMBL_OP_FLAG]，无逐记录日间标志）。
    _PROC_ROMAN = {'Ⅰ': '一', 'Ⅱ': '二', 'Ⅲ': '三', 'Ⅳ': '四', 'Ⅴ': '五'}
    _PROC_MIN_SCORE = 4
    _PROC_FLAG_KEYS = ('唯一标识', '流水号', '序号', '标志')

    @staticmethod
    def _norm_proc_name(cn: str) -> str:
        """序号字段匹配用名称规范化：
        罗马数字→中文数字（Ⅰ助→一助）；手术/操作同族（操作→手术）；
        类型/类别同义（类型→类别）；医生/术者归入医师（麻醉医生→麻醉医师）。
        全部为卫生信息标准的通用同族约定，不涉及具体表名。"""
        if not cn:
            return ''
        s = ''.join(StandardComparator._PROC_ROMAN.get(ch, ch) for ch in cn)
        s = s.replace('操作', '手术')
        s = s.replace('类型', '类别')
        s = s.replace('医生', '医师')
        s = s.replace('术者', '医师')
        return s

    @staticmethod
    def _proc_family(cn: str) -> str:
        """手术角色族术语（作用于规范化后的名称）：
        麻醉 / 一助 / 二助 / 术者·医师（默认手术执行者），用于族内对齐。"""
        if not cn:
            return ''
        if '麻醉' in cn:
            return 'anes'
        if '一助' in cn:
            return 'assist1'
        if '二助' in cn:
            return 'assist2'
        if '术者' in cn or '医师' in cn or '医生' in cn:
            return 'doctor'
        return ''

    @staticmethod
    def _is_flagish(cn: str) -> bool:
        """是否/有无/需 前缀或 唯一标识/流水号/序号/标志 类（标志性字段）。"""
        if not cn:
            return False
        if cn.startswith(('是否', '有无', '需')):
            return True
        return any(k in cn for k in StandardComparator._PROC_FLAG_KEYS)

    @staticmethod
    def _lcs_substr_len(a: str, b: str) -> int:
        """最长公共子串长度。"""
        if not a or not b:
            return 0
        dp = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
        best = 0
        for i in range(1, len(a) + 1):
            ai = a[i - 1]
            for j in range(1, len(b) + 1):
                if ai == b[j - 1]:
                    dp[i][j] = dp[i - 1][j - 1] + 1
                    if dp[i][j] > best:
                        best = dp[i][j]
        return best

    @staticmethod
    def _lcs_len(a: str, b: str) -> int:
        """最长公共子序列长度（空间优化版，仅作平局再分）。"""
        if not a or not b:
            return 0
        m, n = len(a), len(b)
        dp = [0] * (n + 1)
        for i in range(1, m + 1):
            prev = 0
            ai = a[i - 1]
            for j in range(1, n + 1):
                temp = dp[j]
                if ai == b[j - 1]:
                    dp[j] = prev + 1
                else:
                    if dp[j - 1] > dp[j]:
                        dp[j] = dp[j - 1]
                prev = temp
        return dp[n]

    @staticmethod
    def _is_subseq(short: str, long: str) -> bool:
        """short 是否是 long 的子序列（保持顺序即可，不必连续）。
        例：手术代码 ⊂ 其他手术操作代码 ✓；手术切口类别代码 ⊄ 其他手术操作代码。"""
        if not short:
            return True
        if not long:
            return False
        it = iter(long)
        return all(ch in it for ch in short)

    @staticmethod
    def _en_suffix_signal(target_en: str, sf_en: str) -> int:
        """目标英文字段名后缀（_code/_name/_id）与源英文字段名（CODE/NAME/ID）对齐 → +15。"""
        t = (target_en or '').lower()
        s = (sf_en or '').upper()
        for tok in ('_code', '_name', '_id'):
            if tok in t and tok[1:].upper() in s:
                return 15
        return 0

    def _map_numbered_field_to_subfield(self, target_field: StandardField, sub_table):
        """把目标序号字段映射到子表里「名称最重叠 + 手术角色族对齐」的具体字段。

        返回子表字段对象（StandardField）或 None。
        例：目标「其他手术操作Ⅰ助_1」→ 病案首页手术[MAHP_OPERATION].手术一助姓名[ASSISTANT_NAME1]
            「其他手术操作麻醉方式_1」→ 麻醉方式代码[ANES_METHOD_CODE]
            「是否为日间操作_1」（源标准无逐记录日间标志）→ None（归属子表新增）
        """
        if not sub_table or not sub_table.fields:
            return None
        base_cn, _ = self._strip_number_suffix(
            target_field.chinese_name or '', target_field.name or '')
        raw = base_cn or target_field.chinese_name or ''
        norm_base = self._norm_proc_name(raw)
        role = self._field_role(raw)
        kw = self._norm_proc_name(self._role_keyword(raw))  # 规范化后的角色关键词
        target_en = target_field.name or ''
        fam_t = self._proc_family(norm_base)

        best = None
        best_score = -1
        best_lcs = -1
        best_lcss = -1
        best_len = 999
        best_idx = -1
        for idx, sf in enumerate(sub_table.fields):
            sf_cn = sf.chinese_name or ''
            norm_sf = self._norm_proc_name(sf_cn)
            sf_role = self._field_role(sf_cn)
            # 排除公共表头字段：医疗机构/院区代码·名称 等通用表头不可能成为
            # 业务序号字段（如 出院西医其他诊断疾病代码N）的语义来源。
            # 例：m_dis_code_1..20 曾被 HOSP_CODE（院区代码）凭 _code/CODE
            # 后缀信号 +15 伪高分抢占，而正确的 西医出院诊断代码 仅 2 分被门槛拦下。
            if any(k in sf_cn for k in ('医疗机构代码', '医疗机构名称', '院区代码', '院区名称')):
                continue
            # 西/中医互斥：目标明确「西医」时排除「中医」字段，反之亦然。
            # 例：出院西医其他诊断疾病名称 → 西医出院诊断名称，而非 中医疾病名称。
            if ('西医' in norm_base) and ('中医' in norm_sf):
                continue
            if ('中医' in norm_base) and ('西医' in norm_sf):
                continue
            # 强概念词门槛：目标基础名含领域概念词（病理等），候选必须含同一
            # 概念词，否则拒绝——例：其他病理诊断代码 不应硬配 西医出院诊断代码，
            # 源表无病理字段时应归属子表新增（返回 None）。
            if ('病理' in norm_base) and ('病理' not in norm_sf):
                continue
            lcs = self._lcs_substr_len(norm_base, norm_sf)   # 主得分：公共子串
            lcss = self._lcs_len(norm_base, norm_sf)         # 平局再分：公共子序列
            score = lcs
            if role and sf_role and role == sf_role:
                score += 30
            fam_s = self._proc_family(norm_sf)
            if fam_t and fam_s and fam_t == fam_s:
                score += 40
            if kw and kw in norm_sf:
                score += 30
            if self._is_subseq(norm_sf, norm_base):
                score += 30
            # 英文后缀信号：中文名有实质重叠（lcs>=3）或 目标末位角色关键词命中
# 候选（kw in norm_sf）时生效：
#  - 防 _code/CODE 后缀在无中文重叠时伪加分（HOSP_CODE 抢诊断字段）
#  - 手术角色族字段（其他手术医师→术者姓名）kw='医师'命中，后缀 +15
#    使 术者姓名 胜 术者标识（否则仅靠 lcs=2 平局按短名选错）
#  - 诊断代码字段 kw='代码' 仅命中含"代码"的候选，西医出院诊断代码胜出
            score += (self._en_suffix_signal(target_en, sf.name or '')
                      if (lcs >= 3 or (kw and kw in norm_sf)) else 0)
            if (not self._is_flagish(norm_base)) and self._is_flagish(norm_sf):
                score -= 30
            if (score > best_score or (
                    score == best_score and (
                        lcss > best_lcss or (
                            lcss == best_lcss and (
                                len(norm_sf) < best_len or (
                                    len(norm_sf) == best_len and idx < best_idx)))))):
                best = sf
                best_score = score
                best_lcs = lcs
                best_lcss = lcss
                best_len = len(norm_sf)
                best_idx = idx
        if best is None or best_score < self._PROC_MIN_SCORE:
            return None
        # 防弱匹配：名称几乎无重叠且既无角色族对齐、又无英文后缀信号的候选不采纳
        # （如 是否为日间手术 → 手术记录唯一标识 的 lcs=2 误配被此门槛拦下）
        if best_lcs < 2:
            fam_b = self._proc_family(self._norm_proc_name(best.chinese_name or ''))
            if fam_t != fam_b and not self._en_suffix_signal(target_en, best.name or ''):
                return None
        return best

    def _detect_numbered_field_groups(self, target_table: StandardTable,
                                      source_table: StandardTable,
                                      source_table_index: Dict) -> Dict[str, Dict]:
        """通用自动检测目标表序号字段组，并匹配到原标准子表（不依赖硬编码表名/正则）。

        返回: {target_field_name: {group_name, sub_table, sub_table_chinese, match_info, new_fields_target}}
        """
        result = {}

        if not self.numbered_field_groups:
            return result
        cfg = self.numbered_field_groups
        min_group = int(cfg.get('min_group_size', 2))
        min_overlap = int(cfg.get('min_domain_overlap', 1))

        # 1) 自动检测并聚类序号字段
        groups = self._cluster_numbered_fields(target_table, min_group)
        if not groups:
            return result

        # 2) 候选子表（来自对齐源主表）
        candidates = self._find_sub_table_candidates(source_table, source_table_index)
        if not candidates:
            return result

        # 3) 每个聚类 → 域概念 → 最匹配子表
        for base_key, fields in groups.items():
            domain = self._strip_role_tail(base_key)
            best = None
            best_score = 0
            for sub in candidates:
                sc = self._domain_subtable_score(domain, sub)
                if sc > best_score:
                    best_score = sc
                    best = sub
            if best is None or best_score < min_overlap:
                # 无匹配子表 → 这些序号字段保持为普通字段（由常规通道处理）
                continue
            sub_table_chinese = best.chinese_name or best.name
            for f in fields:
                # 映射到子表里「同角色 + 域概念最重叠」的具体字段，
                # 使报告能展示该字段的类型/长度/约束/值域（而非留空）。
                sub_field = self._map_numbered_field_to_subfield(f, best)
                result[f.name] = {
                    'group_name': domain or base_key,
                    'sub_table': best.name,
                    'sub_table_chinese': sub_table_chinese,
                    'sub_field': sub_field.name if sub_field else '',
                    'sub_field_chinese': sub_field.chinese_name if sub_field else '',
                    'match_info': f'主子表映射: 序号字段组[{base_key}]→子表[{best.name}]',
                    'new_fields_target': best.name,  # 新增字段应添加到此子表
                }
                self.stats['numbered_field_group'] += 1

        return result

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

        # P6：解析源标准字段"说明"中声明的外键关联，构建自动关联图（表名级双向邻接）。
        # 目标表字段在当前对齐源表找不到时，可沿此图到关联子表（卡证/地址/联系方式等）
        # 搜索同概念字段——支撑"表不只是一对一，可能是多表关联"的结构化匹配。
        self._build_auto_relations(source_doc)

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

                # 字段级跨表匹配：同概念数据元（医疗机构代码、患者姓名等）在源标准
                # 其它表中存在时记为 matched，避免把共享数据元误判为新增。
                # （"整表新增"确认来自其它比对任务的知识库，表是新的，
                #   但字段级数据元是否新增仍应以本次源标准原文为准。）
                self._match_new_table_fields(
                    target_table, result, source_table_index, generated_table_name)
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

                # 字段级跨表匹配：表结构是新的，但共享数据元（医疗机构代码、
                # 患者姓名、就诊流水号 等）在源标准其它表中存在时记为 matched。
                self._match_new_table_fields(
                    target_table, result, source_table_index, generated_table_name)
                continue

            # 比对字段
            self._compare_fields(source_table, target_table, result, source_table_index=source_table_index)

        # 后处理：字段去重标注（患者基本信息 vs 病案首页）
        self._deduplicate_new_fields_via_relation(result)

        # 后处理：地址族新增字段重归属到地址子表（见下方方法说明）
        self._reattribute_address_new_fields(result, getattr(source_doc, 'tables', None))

        # 知识库陈旧结论冲突随结果外带，供人工复核与知识库订正
        result.kb_conflicts = {
            'stale_negative': list(self.stale_negative_conflicts),
            'stale_positive': list(self.user_custom_conflicts),
        }

        # P6 判别器约束注入：残基匹配命中后，在 matched/modified 结果字典中
        # 添加 discriminator_constraint 字段，记录子表类型代码约束。
        # 如"常住地-省市代码"→ discriminate= {地址类别代码: 03}[家庭常住住址]，
        # 供数据上传时生成 WHERE 筛选条件（地址类别代码='03'）。
        if getattr(self, '_p6_discriminator_constraints', None):
            for grp in (result.matched, result.modified):
                for item in grp:
                    tf_cn = (item.get('target_chinese_name')
                             or item.get('field_chinese_name') or '')
                    if not tf_cn:
                        continue
                    dc = self._p6_discriminator_constraints.get(
                        item.get('table_name', ''), {}).get(tf_cn)
                    if dc:
                        item['discriminator_constraint'] = dc

        # 幽灵来源告警随结果外带：映射指定的源表在源标准中不存在，
        # 已拦截其生成新增字段（防止"西医病案首页手术"这类幽灵表名污染 new_fields）
        result.ghost_source_tables = list(
            getattr(self, '_ghost_source_tables', None) or [])

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

    def _reattribute_address_new_fields(self, result: CompareResult, source_tables=None):
        """地址族新增字段重归属：把落在患者主表（m_patient/患者基本信息表）等非地址
        子表的"地址类"新增字段，重新归属到源标准的地址子表（PERSON_ADDRESS/患者地址信息），
        使其与已通过 P6 跨表通道正确匹配到地址子表的 45 个同胞字段保持一致——
        地址信息应进入地址子表，而非患者基本信息表。

        设计要点：
        - 仅作用于 new_fields（保持"新增"性质不变，不伪造匹配，也不触发自验证
          代码/名称种类冲突告警）；原始归属表记录到 rerouted_from 以便追溯。
        - 归属判定只看"地址族"信号（英文名前缀 addr_/reg_/permanent_，或中文前缀
          居住地/户籍地/出生地/常住地，或中文地址关键词），不会误伤 出生日期 这类
          非地址字段（出生日期 不以"出生地"开头、也无地址关键词）。
        - 若当前已归属到地址子表则跳过；找不到源标准地址子表则安全跳过。
        """
        if not source_tables:
            return
        # 1) 定位源标准地址子表（PERSON_ADDRESS / 患者地址信息）
        addr_name = None
        addr_cn = None
        for t in source_tables:
            tn = getattr(t, 'name', None) or (t.get('name') if isinstance(t, dict) else '') or ''
            tcn = (getattr(t, 'chinese_name', None)
                   or (t.get('chinese_name') if isinstance(t, dict) else '') or '')
            if 'ADDRESS' in str(tn).upper() or '地址' in str(tcn):
                addr_name, addr_cn = tn, tcn
                break
        if not addr_name:
            return

        # 2) 地址族判定（仅以中文前缀为准，避免英文名前缀歧义）
        # 说明：本标准中 addr_/reg_ 等英文前缀存在歧义——reg_ 既指"户籍地"也指"挂号"
        # （挂号午别代码 reg_noon_code），addr_ 既指"居住地"也指"行政区划名称"
        # （hos_org.addr_districts_name）。而"居住地/户籍地/出生地/常住地"四个中文
        # 前缀在本标准中专指患者地址族，无歧义，故只以此判定，确保不误伤挂号/机构字段。
        def _is_address(name, cn):
            cn = cn or ''
            for p in ('居住地', '户籍地', '出生地', '常住地', '现住址', '户口地址'):
                if cn.startswith(p):
                    return True
            return False

        # 3) 重归属：当前非地址子表、且属于地址族的 new_field
        # 注意：仅把"应新增到的子表"指向地址子表（source_table_name / new_field_target），
        # 不改动 table_name —— 报告按目标表(table_name)分节，若改成 PERSON_ADDRESS 会因
        # PERSON_ADDRESS 不是目标表而无对应章节，导致字段从报告中消失。保留 table_name
        # 为原目标表(如 m_patient)可保证字段仍在正确章节，而红字"新增到"显示指向
        # PERSON_ADDRESS，恰好表达"字段物理上在患者主表、逻辑上应归入地址子表"。
        for fi in result.new_fields:
            cur = fi.get('table_name', '') or ''
            if cur == addr_name:
                continue
            cn = fi.get('chinese_name') or fi.get('name') or ''
            if _is_address(fi.get('name'), cn):
                fi['rerouted_from'] = cur
                fi['new_field_target'] = addr_name
                fi['source_table_name'] = addr_name
                fi['address_subtable_rerouted'] = True

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

    def _locate_field_table(self, source_field, source_table_index):
        """定位 source_field 实际所属的源表。

        P6 自动外键通道 / cross_table 通道 / 全局查找返回的源字段可能来自
        关联子表（如 患者卡证信息.卡证号码），而非当前对齐的主表。记录组装
        前必须还原真实来源表，否则会串表：
        患者基本信息[PERSON].卡证号码[IDCARD_NO] ← 实为 患者卡证信息 的字段。
        结果按 id(sf) 缓存；未命中返回 None（调用方回退到当前对齐主表）。
        """
        if source_field is None or not source_table_index:
            return None
        cache = getattr(self, '_field_origin_cache', None)
        if cache is None:
            cache = {}
            for st in source_table_index.values():
                for sf in st.fields:
                    cache[id(sf)] = st
            self._field_origin_cache = cache
        return cache.get(id(source_field))

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

        # ===== 新增：序号字段组检测（主子表展开策略，通用自动检测）=====
        numbered_field_matches = self._detect_numbered_field_groups(
            target_table, source_table, source_table_index)
        # numbered_field_matches: {field_name: {group_name, sub_table, match_info}}
        # 缓存供第三遍未匹配字段查询（_find_numbered_group_for_field 复用，避免硬编码）
        self._numbered_group_map = numbered_field_matches

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
                # P6 跨通道占用登记：记录本表已通过**非 P6 通道**占用的源字段。
                # P6 自身的占用仍由 _auto_relation_used（按 rel_table+sf）管理，
                # 避免"初步/修正/确定诊断"等同类子项共享同一源编码字段时被误拒。
                if getattr(self, '_p6_occupied', None) is not None:
                    _mt = match_result[1] if len(match_result) > 1 else ''
                    if not str(_mt).startswith('auto_relation'):
                        self._p6_occupied.setdefault(target_table.name, {})[
                            source_field.chinese_name or source_field.name] = (
                                target_field.chinese_name or target_field.name)
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
        target_field_by_name = {f.name: f for f in target_table.fields}
        for field_name, code_field_name in dictionary_name_fields.items():
            # 修正（Issue 3）：名称字段优先走常规匹配，匹配不到再降级为字典关联。
            # 原逻辑：代码字段已匹配 → 名称字段直接标记为 dictionary（跳过常规匹配）
            # 但源表中可能本身就存在名称字段（如"地址名称"），不应跳过。
            name_field = target_field_by_name.get(field_name)
            if name_field is None:
                continue

            # 先尝试常规匹配（名称 vs 名称：包括精确/同义/语义/关键词/P6）
            match_result = self._find_matching_field(
                name_field, source_field_index, source_table, source_table_index, target_table)
            source_field = match_result[0] if match_result else None
            if source_field:
                # 常规匹配成功 → 直接匹配（不是字典关联）
                if getattr(self, '_p6_occupied', None) is not None:
                    _mt = match_result[1] if len(match_result) > 1 else ''
                    if not str(_mt).startswith('auto_relation'):
                        self._p6_occupied.setdefault(target_table.name, {})[
                            source_field.chinese_name or source_field.name] = (
                                name_field.chinese_name or name_field.name)
                modifications = self._check_modifications(source_field, name_field)
                field_match_results[field_name] = (match_result, modifications)
                field_match_status[field_name] = 'modified' if modifications else 'matched'
            else:
                # 常规匹配失败 → 检查代码字段是否已匹配，降级为字典关联
                code_field_status = field_match_status.get(code_field_name)
                if code_field_status in ['matched', 'modified']:
                    # 代码字段已匹配，名称字段可以通过字典关联获取
                    field_match_status[field_name] = 'dictionary'
                else:
                    field_match_results[field_name] = (match_result, [])
                    field_match_status[field_name] = None

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
            # 关键修复（P0）：第一遍已经匹配成功的字段（含全局跨表复用匹配到的源字段），
            # 切勿再用“可能陈旧的表级映射”二次解析——否则会把它误判为新增字段（new_fields）。
            # 这类字段直接沿用第一遍的缓存结果（下方 match_status in ['matched','modified'] 分支）。
            if (field_mapping and not has_special_status
                    and (is_user_custom or match_status is None)
                    and match_status not in ('matched', 'modified')):
                # 这是一个配置了映射关系的字段
                source_field_name = field_mapping.get('source_field')
                source_field_cn = field_mapping.get('source_field_cn', '')
                source_table_name = field_mapping.get('source_table', '')

                # 查找源字段 - 优先从用户指定的源表中查找
                source_field = None
                actual_source_table = source_table  # 默认使用当前源表
                # 用户映射指定的源表是否真实存在于源标准（防幽灵来源：
                # 映射指向的表名不在源标准中时，不得据此凭空生成新增字段）
                source_table_found = not source_table_name  # 未指定源表时无需校验

                # 1. 如果指定了源表名，从该表中查找
                # 匹配支持双向包含 + 前后缀清洗（"患者基本信息表"→"患者基本信息"；
                # "西医病案首页手术"→"病案首页手术"，即 WS445 表名体系归一到区域平台表名）
                if source_table_name and source_table_index:
                    src_tn = source_table_name.strip().lstrip('*').strip()
                    for st_name, st in source_table_index.items():
                        # 匹配源表名（支持中文名和英文名）
                        st_cn = (st.chinese_name or '').strip().lstrip('*').strip()
                        st_name_val = st.name or ''
                        if (st_cn == src_tn or
                            st_name_val == src_tn or
                            (st_cn and src_tn and (src_tn in st_cn or st_cn in src_tn))):
                            actual_source_table = st
                            source_table_found = True
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
                        # 幽灵来源拦截：映射指定了源表，但源标准中不存在该表，
                        # 说明映射来源（知识库/旧版本）与当前源标准不匹配，
                        # 不得凭空生成新增字段，记录告警后跳过
                        if source_table_name and not source_table_found:
                            if not hasattr(self, '_ghost_source_tables'):
                                self._ghost_source_tables = []
                            self._ghost_source_tables.append({
                                'target_table': target_table.name,
                                'target_field': target_field.name,
                                'target_chinese_name': target_field.chinese_name or '',
                                'source_table': source_table_name,
                                'reason': '映射指定的源表在源标准中不存在'
                            })
                            continue
                        # 用户指定了源表但没有源字段，表示这个字段需要新增到指定的源表
                        from utils.pinyin_utils import generate_english_field_name

                        # 获取版本信息，默认为5.0
                        standard_version = getattr(self, 'source_version', '5.0')
                        generated_en_name = generate_english_field_name(
                            target_field.chinese_name,
                            standard_version=standard_version
                        )

                        # 使用用户指定的源表，如果没有指定则使用当前匹配的源表
                        # 若映射源表已在源标准中解析命中，优先用源表规范名
                        # （"西医病案首页手术"→ 病案首页手术，避免 WS445 表名污染输出）
                        if source_table_found and actual_source_table is not None:
                            new_field_target = (actual_source_table.name
                                                or actual_source_table.chinese_name
                                                or source_table_name)
                        else:
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

            if is_name_field and match_status not in ('matched', 'modified'):
                # 标记为字典关联匹配（仅对真正未匹配的字段生效，避免覆盖
                # 已通过 exact_chinese/synonym 等通道正确匹配的字段）
                # 例：org_name(医疗机构名称) 已在第一遍被 exact_chinese 正确匹配到
                # PERSON.ORG_NAME，但第三遍字典检测误判为 dictionary 导致来源信息丢失。
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
                sub_field = group_info.get('sub_field', '')
                sub_field_chinese = group_info.get('sub_field_chinese', '')
                result.matched.append({
                    'table_name': target_table.name,
                    'table_chinese_name': target_table.chinese_name,
                    'target_field': target_field.name,
                    'target_chinese_name': target_field.chinese_name,
                    'source_table': sub_table_name,
                    'source_table_chinese_name': sub_table_chinese,
                    'source_field': sub_field,
                    'source_field_chinese_name': sub_field_chinese or f'[主子表映射:{group_name}]',
                    'match_type': 'numbered_field_group'
                })
            elif match_status in ['matched', 'modified']:
                # 正常匹配 — 使用第一遍缓存的匹配结果和修改检查（避免重复调用）
                cached = field_match_results.get(target_field.name)
                if cached:
                    match_result, modifications = cached
                    if match_result:
                        source_field, internal_match_type = match_result
                        # 还原源字段真实来源表：P6/cross_table 通道返回的字段
                        # 可能来自关联子表，不能用主表名（否则串表，如
                        # 患者基本信息[PERSON].卡证号码 ← 实为 患者卡证信息）。
                        src_origin = self._locate_field_table(
                            source_field, source_table_index)
                        src_tbl = src_origin if src_origin is not None else source_table

                    if modifications:
                        result.modified.append({
                            'table_name': target_table.name,
                            'table_chinese_name': target_table.chinese_name,
                            'field_name': target_field.name,
                            'field_chinese_name': target_field.chinese_name,
                            'source_table': src_tbl.name,
                            'source_table_chinese_name': src_tbl.chinese_name,
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
                            'source_table': src_tbl.name,
                            'source_table_chinese_name': src_tbl.chinese_name,
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
        """第三遍：未匹配字段若属于已检测的序号字段组，返回应新增到的子表名。

        直接复用本表比对阶段缓存的通用检测结果（self._numbered_group_map），
        不再依赖任何硬编码表名 / 正则。若该字段不在已检测组内，返回 None
        （表示它不属于任何序号字段组，按普通新增字段处理）。
        """
        cached = getattr(self, '_numbered_group_map', None)
        if cached:
            info = cached.get(target_field.name)
            if info:
                return info.get('new_fields_target') or info.get('sub_table')
        return None

    # ======================================================================
    # P6：自动外键关联通道（多表关联）
    # 源标准字段说明里写明了外键关系（"外键，SYS_SOID+X与XX表[T]中的Y字段关联"），
    # 可自动解析成"源表关联图"。目标表字段在当前对齐源表找不到时，沿关联图
    # 到子表/关联表（卡证子表、地址子表等）里找同概念字段——支撑"表不只是一对一，
    # 可能是多表关联"的结构化匹配。
    # ======================================================================
    _FK_PATTERN = re.compile(
        r'外键\s*[，,]\s*([A-Z0-9_+]+)\s*与\s*'
        r'([\u4e00-\u9fa5（）()A-Za-z0-9_]+)\s*[\[（(]\s*'
        r'([A-Z][A-Z0-9_]+)\s*[\]）)]\s*中\s*的\s*'
        r'([A-Z0-9_+]+)\s*字段关联')

    def _build_auto_relations(self, source_doc: StandardDocument):
        """从源标准字段说明解析外键关联，构建双向表关联图。

        - self._auto_adjacency: 表名 -> set(相邻表名)（双向，含主子表）
        - self._auto_fk_edges: (本表, 本表中文, 本表字段, 目标表, 目标表中文, 目标字段)
        """
        self._auto_adjacency = {}
        self._auto_fk_edges = []
        self._auto_relation_used = {}
        # P6 占用登记（跨通道）：compare() 主流程每次匹配成功后登记
        # 目标表名 -> {源字段中文名(或英文名) -> 占用者目标字段中文名}，供 P6 通道检查
        # "该源字段是否已被本表其他字段通过任意通道占用"，防止把已被
        # user_custom/exact 等通道用掉的外键再次 kw 兜底占用
        # （如 治疗用药记录流水号 ✗ 治疗记录流水号[已被user_custom占用]）。
        self._p6_occupied = {}
        # P6 意图登记（user_custom 声明但解析失败）：目标表名 -> set(目标字段中文名)。
        # user_custom 是人工确认（"该目标字段对应某源字段"），即使知识库中源字段名
        # 与源标准实际不符导致解析失败，P6 兜底也不应猜配抢占（如 治疗用药记录流水号
        # 声明→用药明细流水号[错名]，P6 不得 kw 匹配 治疗记录流水号；入院记录诊断流水号
        # 同理保持 new_field）。解析失败应暴露为知识库待订正项，而非被 P6 低置信覆盖。
        self._p6_uc_declared = {}
        # P6 判别器约束记录（残基匹配命中后，记录子表判别器字段与代码值）
        self._p6_discriminator_constraints = {}  # target_table.name -> {tf_cn: {disc_field: code}}
        # 自动检测子表判别器字段（类别代码/类型代码+值域），供残基匹配记录约束。
        self._auto_rel_discriminators = {}  # table_name -> {chinese_name: {code: name}}
        if not self.auto_relation_enabled:
            return
        for t in source_doc.tables:
            for f in t.fields:
                d = f.description or ''
                m = self._FK_PATTERN.search(d)
                if not m:
                    continue
                _src_fk, tgt_cn, tgt_tbl, _tgt_fk = m.groups()
                edge = (t.name, t.chinese_name, f.chinese_name or f.name,
                        tgt_tbl, tgt_cn, _tgt_fk)
                self._auto_fk_edges.append(edge)
                self._auto_adjacency.setdefault(t.name, set()).add(tgt_tbl)
                self._auto_adjacency.setdefault(tgt_tbl, set()).add(t.name)

        # 第三遍：计算无 FK 边的主词表集合。
        # 主词表（如 PERSON 患者基本信息）没有 FK 指向其他表，不可反向借
        # 业务子表字段，仅属性子表（表名以主表名+"_"开头）例外。
        children = {e[0] for e in self._auto_fk_edges}
        self._master_tables = set()
        for t in source_doc.tables:
            if t.name not in children:
                self._master_tables.add(t.name)

        # 第二遍：注册属性子表判别器字段（显式名单，见 _AUTO_REL_ATTR_TABLE_DISCS）。
        # 注册名与 _AUTO_REL_DISCRIMINATOR_MAP 键对齐；value_domains 未解析时
        # code_map 为空不影响方向否决豁免（只看表名是否存在）与约束解析
        # （_resolve_discriminator_constraint 用静态映射查码）。
        for t in source_doc.tables:
            spec = self._AUTO_REL_ATTR_TABLE_DISCS.get(t.name)
            if not spec:
                continue
            fname, reg_cn = spec
            for f in t.fields:
                if f.name == fname:
                    code_map = {}
                    for vd in (f.value_domains or []):
                        if vd.code and vd.name:
                            code_map[vd.code] = vd.name
                    self._auto_rel_discriminators.setdefault(
                        t.name, {})[reg_cn] = code_map
                    break

    # ===== P6 自动外键关联通道：通道级专有同义词与复用判定 =====
    # 源标准用"子表 + 类型代码"存多类数据（地址类别代码、卡证类型），目标省平台
    # 把同一概念拆成多列（卡类型代码/卡号/社保卡号、出生地/户籍地/居住地-详细地址）。
    # 这些同义关系只在"沿关联图搜索子表"这一通道内生效，不污染全局匹配。
    _AUTO_REL_SYNONYMS = {
        '卡类型': ['卡证类型', '卡片类型'],
        '卡号': ['卡证号码', '卡片号码'],
        '社保卡号': ['卡证号码'],
        '居民健康卡卡号': ['卡证号码'],
        '证件号码': ['卡证号码'],
        '身份证件类别': ['卡证类型'],
        '联系人关系': ['与患者关系'],
        # 系统审计时间字段（人工确认同义，V6.0医疗服务 vs 省平台v1.4.1医疗部分）：
        # 目标省平台 m_patient.业务数据产生/更新日期时间 == 源标准 PERSON.SYS_CREATED_AT/
        # SYS_MODIFIED_AT(创建/修改日期时间)。核心词"产生/创建"不同会被 core 闸门误拒，
        # 此处作为人工确认同义逃逸（跳过角色/核心概念闸门），落到主表 PERSON。
        '业务数据产生日期时间': ['创建日期时间'],
        '业务数据更新日期时间': ['修改日期时间'],
    }
    # 复用判定用的前缀/尾词：剥离后基名一致才允许"同源字段服务多目标列"。
    _AUTO_REL_LOC_PREFIXES = ['出生地', '户籍地', '居住地', '现住地', '常住地',
                              '工作地', '单位', '家庭', '联系人']
    _AUTO_REL_CARD_PREFIXES = ['居民健康卡', '社保', '医保', '就诊', '健康卡', '银行卡']
    _AUTO_REL_TAIL_KINDS = ['唯一标识', '流水号', '代码', '编码', '代号', '编号',
                            '序号', '标识', '标志', '名称', '号码']

    # ===== 值域驱动匹配（P6v）：残基→层级关键词映射 =====
    # 残基中出现的复合词（如"省市"）应映射到哪组层级关键词。
    # 单独的"省"或"市"字在行政区划层级关键词集中已存在，
    # 但"省市"作为复合词，预期匹配的是"省/自治区/直辖市"级别，
    # 不应匹配"市/地区/州"级别。
    _AUTO_REL_RESIDUE_MAP = {
        '省市': {'省', '自治区', '直辖市'},
        '地市': {'市', '地区', '州'},
        '区县': {'县'},  # 不含"区"单字，避免误配"入院病区编码"等含"区"的非地址字段
        '乡镇': {'乡', '镇', '街道'},
        '街道': {'乡', '镇', '街道', '街道办事处'},
        '邮政编码': {'邮政编码', '邮编'},
        '详细地址': {'详细地址', '地址', '住址'},
        '门牌': {'门牌'},
    }
    _AUTO_REL_ADDR_LEVEL_KEYWORDS = {
        '省', '自治区', '直辖市', '市', '地区', '州', '县', '区',
        '乡', '镇', '街道', '村', '街', '路', '弄', '门牌', '邮政编码',
        '详细地址',
    }

    # 值域驱动匹配：地址前缀→判别器代码（源标准地址类别代码表 CV02.01.205）
    # 残基匹配命中后，从该映射查找判别器代码，记录到 match 结果供数据上传使用。
    _AUTO_REL_DISCRIMINATOR_MAP = {
        '地址类别代码': {  # discriminator chinese_name -> prefix->code
            '出生地': '01', '户籍地': '02', '常住地': '03',
            '居住地': '04', '现住地': '04', '工作地': '05',
            '联系人': '06', '家庭': '03',
        },
        '卡证类型代码': {
            '身份证': '01', '社保卡': '02', '居民健康卡': '03',
            '医保卡': '04', '护照': '05', '军官证': '06',
        },
    }

    # 属性子表显式名单：源标准中"按类别代码 1:N 取唯一值"的属性/从属子表
    # （地址/联系方式/卡证），主表可借其字段（一对多方向成立，需配合判别器
    # 约束取唯一值）；其余外键子表一律视为事件/业务子表（就诊/医嘱/诊断/
    # 病案/转诊等），一对多方向不成立，主表反向借字段一律否决。
    # 值：(字段英文名, 注册用判别器中文名——与 _AUTO_REL_DISCRIMINATOR_MAP
    # 键对齐，保证 _resolve_discriminator_constraint 能解析出判别码)。
    # 不用自动检测（"类别代码/类型代码 + 值域"）识别：源标准 value_domains
    # 常未解析（全空），且事件子表（OUTP_ENCOUNTER.就诊类型代码、
    # MAHP_MAIN.身份证类别代码等）同样含类型代码字段，自动检测会误判放行。
    _AUTO_REL_ATTR_TABLE_DISCS = {
        'PERSON_ADDRESS': ('ADDRESS_TYPE_CODE', '地址类别代码'),
        'PERSON_CONTACT': ('CONT_TYPE_CODE', '联系方式类别代码'),
        'PERSON_IDENTIFICATION': ('IDCARD_TYPE_CODE', '卡证类型代码'),
    }

    # 排除类限定词：目标字段以"其他/其它/其余"限定时，表示"排除特定类别后的
    # 其余项"，与源字段的特定类别（如 初步诊断、西医诊断编码）语义冲突，
    # keyword 层不应跨限定词匹配（其他西医诊断代码 ✗ 初步诊断--西医诊断编码）。
    _EXCLUSION_QUALIFIERS = ('其他', '其它', '其余', '另')

    @classmethod
    def _auto_rel_residue_match(cls, target_cn: str, source_cn: str) -> bool:
        """残基匹配：剥离地址/卡类型前缀后，按行政区划层级关键词匹配源字段。

        目标字段如"常住地-省市代码"→剥离前缀"常住地"→残基"省市代码"→
        去尾词"代码"→"省市"含{省,市}关键词；
        源字段如"省（自治区、直辖市）编码"→含{省,自治区,直辖市}关键词 → 匹配。

        rank=4（低于keyword的3），配合rank全局最佳决策处理歧义。
        """
        if not target_cn or not source_cn:
            return False

        # 1. 剥离前缀
        target_stripped = target_cn
        has_prefix = False
        for p in cls._AUTO_REL_LOC_PREFIXES + cls._AUTO_REL_CARD_PREFIXES:
            if target_stripped.startswith(p):
                target_stripped = target_stripped[len(p):]
                has_prefix = True
                break

        if not has_prefix:
            return False

        # 2. 剥离尾词种类
        for k in sorted(cls._AUTO_REL_TAIL_KINDS, key=len, reverse=True):
            if target_stripped.endswith(k) and len(target_stripped) > len(k):
                target_stripped = target_stripped[:-len(k)]
                break

        import re
        # 3. 清理噪音（括号、分隔符）
        for ch in '-－—·、:： ':
            target_stripped = target_stripped.replace(ch, '')
        target_stripped = re.sub(r'[（(][^）)]*[）)]', '', target_stripped)

        # 4. 提取残基中的层级关键词
        # 优先查 _AUTO_REL_RESIDUE_MAP 复合词映射（如"省市"→{省,自治区,直辖市}）
        # 确保"省市"只匹配省级别，不匹配市级别
        residue_kws = cls._AUTO_REL_RESIDUE_MAP.get(target_stripped, set())
        if not residue_kws:
            # 未命中复合词映射，从 _AUTO_REL_ADDR_LEVEL_KEYWORDS 中提取子串
            residue_kws = {k for k in cls._AUTO_REL_ADDR_LEVEL_KEYWORDS if k in target_stripped}
            if not residue_kws:
                return False

        # 5. 提取源字段主干+括号内容中的层级关键词
        src_main = re.sub(r'[（(][^）)]*[）)]', '', source_cn)
        src_parens = ' '.join(re.findall(r'[（(][^）)]*[）)]', source_cn))
        src_all = src_main + ' ' + src_parens

        # 6. 检查是否有任意层级关键词出现在源字段中
        # 复合词映射模式（如"省市"→{省,自治区,直辖市}）：任一映射词命中即匹配；
        # 单字符提取模式（如"省"）：子串级命中即匹配。
        # 单字符关键词（如"市"、"县"、"区"）只检查括号外主干，避免误配括号内容
        # （如"直辖市"含"市"导致"地市"误配"省（自治区、直辖市）编码"）。
        for kw in residue_kws:
            if len(kw) == 1:
                # 单字关键词只检查括号外主干（括号内内容如"直辖市"含"市"为误配源）
                if kw in src_main:
                    return True
            else:
                # 多字关键词检查完整字段（括号内也可能包含关键信息）
                if kw in src_all:
                    return True
        return False

    @classmethod
    def _resolve_discriminator_constraint(cls, target_cn: str, rel_table: 'StandardTable',
                                          auto_rel_discriminators: dict) -> dict:
        """残基匹配命中后，解析子表判别器约束。

        目标字段"常住地-省市代码"通过残基匹配命中 PERSON_ADDRESS.省编码后，
        查 _AUTO_REL_DISCRIMINATOR_MAP 中"地址类别代码"前缀→代码映射，
        返回 {地址类别代码: 03}，供数据上传约束使用。

        Args:
            target_cn: 目标字段中文名（如"常住地-省市代码"）
            rel_table: 源关联子表对象
            auto_rel_discriminators: _build_auto_relations 自动检测的判别器映射

        Returns:
            dict: {判别器字段名: 代码值}，如 {} 表示无约束
        """
        if not target_cn or not rel_table or not auto_rel_discriminators:
            return {}

        # 1. 提取目标字段前缀
        prefix = None
        for p in cls._AUTO_REL_LOC_PREFIXES + cls._AUTO_REL_CARD_PREFIXES:
            if target_cn.startswith(p):
                prefix = p
                break
        if not prefix:
            return {}

        # 2. 查子表是否有自动检测到的判别器
        discriminators = auto_rel_discriminators.get(rel_table.name, {})
        if not discriminators:
            return {}

        # 3. 对每个判别器，查 _AUTO_REL_DISCRIMINATOR_MAP 中该前缀→代码
        result = {}
        for disc_cn, code_map in discriminators.items():
            disc_map = cls._AUTO_REL_DISCRIMINATOR_MAP.get(disc_cn, {})
            if prefix in disc_map:
                result[disc_cn] = disc_map[prefix]
        return result

    @classmethod
    def _exclusion_qualifier_conflict(cls, cn: str, s_cn: str) -> bool:
        """排除类限定词冲突：目标含"其他/其它/其余"而源不含 -> True（应拒绝）。

        只在低置信 keyword 兜底层生效：目标字段声明了"排除特定类别"的语义，
        源字段是某一特定类别，二者不构成同概念。
        """
        if not cn or not s_cn:
            return False
        t_has = any(q in cn for q in cls._EXCLUSION_QUALIFIERS)
        s_has = any(q in s_cn for q in cls._EXCLUSION_QUALIFIERS)
        return t_has and not s_has

    def _auto_rel_synonym_match(self, name1: str, name2: str) -> bool:
        """关联子表通道同义判定：全局同义词 + 通道级专有映射。

        通道级专有映射（_AUTO_REL_SYNONYMS）是人工确认的同义关系
        （社保卡号↔卡证号码、卡号↔卡证号码、卡类型↔卡证类型），
        命中即视为同概念，**不套用通用核心概念闸门**——否则 社保卡号/卡号
        会被 卡证号码 的核心词差异（卡 vs 卡证）误拒，永远落不到卡证子表。
        专有映射自身的"词对子串 + 余部兼容"判定已足够精确（卡号 vs 卡证类型
        因 卡证号码 不是 卡证类型 的子串而不会命中），无需 role/core 前置。
        通用同义词（_is_synonym_match）与角色/核心概念闸门只约束未在
        专有映射中登记的泛化判定。
        """
        if not name1 or not name2:
            return False
        if self._is_synonym_match(name1, name2):
            return True
        # 通道级专有映射（人工确认）优先：命中即同概念。
        if self._auto_rel_channel_synonym_hit(name1, name2):
            return True
        if not self._is_role_compatible_for_synonym(name1, name2):
            return False
        if not self._core_concept_compatible(name1, name2):
            return False
        return False

    @classmethod
    def _auto_rel_channel_synonym_hit(cls, name1: str, name2: str) -> bool:
        """通道级专有同义映射命中判定（不套用通用核心概念闸门）。

        classmethod：供 self_validator 复用以豁免人工确认的同义对
        （社保卡号↔卡证号码 等）的核心概念误报，避免两处规则漂移。
        """
        if not name1 or not name2:
            return False
        for w1, syns in cls._AUTO_REL_SYNONYMS.items():
            for n1, n2 in ((name1, name2), (name2, name1)):
                if w1 in n1:
                    for syn in syns:
                        if syn in n2:
                            r1 = n1.replace(w1, '').strip()
                            r2 = n2.replace(syn, '').strip()
                            if r1 == r2 or not r1 or not r2 or r1 in r2 or r2 in r1:
                                return True
        return False

    @classmethod
    def _auto_relation_reuse_allowed(cls, prev_cn: str, new_cn: str) -> bool:
        """同源字段是否允许被第二个目标字段复用（子表类型代码区分场景）。

        源标准用一张子表+类型代码存多类数据（ADDRESS 子表存多类地址、
        IDENTIFICATION 子表存多类卡证），同一源字段可服务多个目标列：
          出生地-详细地址 与 居住地-详细地址 都取自 ADDRESS 子表"详细地址"；
          卡号/社保卡号 都取自 IDENTIFICATION 子表"卡证号码"。
        允许条件：剥离各自的地址位置/卡类型前缀与尾部种类词后基名一致且非空；
        基名不同（如 卡类型 vs 证件类型）则禁止复用，防跨概念抢占。
        """
        if not prev_cn or not new_cn:
            return False

        def _core(s):
            for p in cls._AUTO_REL_LOC_PREFIXES + cls._AUTO_REL_CARD_PREFIXES:
                if s.startswith(p):
                    s = s[len(p):]
                    break
            for k in sorted(cls._AUTO_REL_TAIL_KINDS, key=len, reverse=True):
                if s.endswith(k) and len(s) > len(k):
                    s = s[:-len(k)]
                    break
            return s.strip(' -－—·、')

        c1, c2 = _core(prev_cn), _core(new_cn)
        return bool(c1 and c2 and c1 == c2)

    def _match_in_auto_relation_table(self, target_field: StandardField,
                                      rel_table: StandardTable,
                                      target_table: StandardTable,
                                      defer_claim: bool = False):
        """在单张关联子表/关联表内查找目标字段的同概念字段。

        匹配序列：精确中文名 → 同义词（全局+通道级） → 语义相似 → 关键词（n-gram）
        → 残基匹配（剥离地址/卡类型前缀后按层级关键词匹配）。
        每级都复用现有安全网关（描述兼容/字段种类/角色/复合主体），
        并遵守"同一目标表内一个源字段只归一个目标字段"的占用保护——
        但源标准用子表+类型代码区分多类数据（如 ADDRESS 子表的"详细地址"
        同时对应目标"出生地/户籍地/居住地-详细地址"）时，允许"前缀不同、
        基名相同"的目标字段复用同一源字段，避免只放行最先命中者造成漏配。

        defer_claim=True（跨表收集模式）：不写入占用、不累计统计，
        返回 (rank, source_field, match_type)，rank 为整数优先级
        （0=exact, 1=synonym, 2=semantic, 3=keyword, 4=residue），供调用方
        跨表比较后统一决策；
        否则直接占用并返回 (source_field, match_type)。
        未命中返回 None。
        """
        cn = target_field.chinese_name or ''
        used = self._auto_relation_used.setdefault(target_table.name, {})
        best = None  # (rank, sf, mtype)
        for sf in rel_table.fields:
            s_cn = sf.chinese_name or ''
            if not s_cn:
                continue
            if not self._is_description_compatible(target_field, sf):
                # 人工确认同义豁免描述闸门：已登记为同义（通道级 _AUTO_REL_SYNONYMS
                # 或 field_synonyms.yaml 显式条目）的对，描述措辞差异（如"业务数据
                # 产生时间" vs "落库日期时间"）不应否决，否则人工确认同义逃逸失效
                # （业务数据产生日期时间↔创建日期时间、业务数据更新日期时间↔修改日期时间）。
                if not (self._auto_rel_channel_synonym_hit(cn, s_cn)
                        or self._in_explicit_synonym_dict(cn, s_cn, self.synonyms)):
                    continue
            if not self._field_kind_compatible(cn, s_cn):
                continue
            if not self._composite_subject_compatible(cn, s_cn):
                continue
            key = (rel_table.name, sf.name)
            claimed_cn = used.get(key)
            if claimed_cn is not None and not defer_claim:
                # 占用保护（仅 defer_claim=False 直接占用模式生效）：
                # 默认禁止复用；仅当两个目标字段"前缀不同、基名相同"时允许
                # （子表类型代码区分场景，见 _auto_relation_reuse_allowed）。
                # defer_claim=True（跨表收集模式）跳过占用检查，由 P6 调用方
                # 统一去重（_p6_occupied 占用保护 + 候选消歧属性子表优先），
                # 避免先匹配字段（如 card_type_code 卡类型代码）提前占住
                # 属性子表槽位，导致后匹配字段（如 id_type_code 身份证件类别
                # 代码→卡证类型）因 _auto_relation_reuse_allowed 基名不同而
                # 被跳过收集，最终属性子表候选缺失→歧义误杀。
                if not self._auto_relation_reuse_allowed(claimed_cn, cn):
                    continue
            rank = None
            if cn and cn == s_cn:
                rank = (0, sf, 'auto_relation_exact')
            elif self.use_synonym and self._auto_rel_synonym_match(cn, s_cn):
                rank = (1, sf, 'auto_relation_synonym')
            elif self.use_similarity and self._is_semantic_match(cn, s_cn):
                rank = (2, sf, 'auto_relation_semantic')
            elif self.use_keyword and self._is_keyword_match(cn, s_cn):
                # 括号消歧门禁：目标字段括号内容是主子表展开的消歧关键
                # （如 治疗转归(对应中医诊断N)），keyword 层 n-gram 会把
                # 括号内子串当特征跨括号误配（如 → 是否中医诊断）。
                if not self._paren_content_compatible(cn, s_cn):
                    continue
                # 排除类限定词冲突门禁：目标含"其他/其它/其余"而源不含
                # （其他西医诊断代码 vs 初步诊断--西医诊断编码）。
                if self._exclusion_qualifier_conflict(cn, s_cn):
                    continue
                if not self._is_type_compatible_for_keyword(target_field, sf):
                    continue
                if not self._is_code_name_compatible(cn, s_cn):
                    continue
                rank = (3, sf, 'auto_relation_keyword')
            if rank is None:
                # 残基匹配（rank=4）：剥离地址/卡类型前缀后，按层级关键词匹配。
                # 低于 keyword 的 3，确保精确/同义/语义/keyword 优先。
                if cn and self._auto_rel_residue_match(cn, s_cn):
                    rank = (4, sf, 'auto_relation_residue')
            if rank is None:
                continue
            # 取最高优先级命中（整数 rank 比较：0 < 1 < 2 < 3，避免字符串
            # 字典序把 semantic('sem' < 'syn') 误判为优于 synonym）；
            # 同优先级多个不同候选 -> 歧义，不自动匹配
            if best is None or rank[0] < best[0]:
                best = rank
            elif rank[0] == best[0] and best[1] is not sf:
                return None  # 同等级多候选，交给人工/自验证
        if best is None:
            return None
        _, sf, mtype = best
        if not defer_claim:
            # 记录占用者目标字段中文名，供后续复用判定。
            # 注意 key 必须取自 best[1]（曾误用循环最后迭代字段的 key）。
            used[(rel_table.name, sf.name)] = cn
            self.stats[mtype] = self.stats.get(mtype, 0) + 1
            return (sf, mtype)
        return (best[0], sf, mtype)

    @staticmethod
    def _paren_content_compatible(cn: str, s_cn: str) -> bool:
        """括号消歧门禁：目标字段括号内容是主子表展开的消歧关键。

        治疗转归(对应中医诊断N) 这类字段，括号内是"对应哪类诊断"的消歧
        编号；keyword 层 n-gram 会把括号内子串（如 中医诊断）当特征，
        跨括号误配到 是否中医诊断。规则：
          - 目标不含括号          -> 放行（无消歧语义需要保护）
          - 目标含括号、源不含括号 -> 禁止 keyword（不允许跨括号匹配）
          - 两者都含括号           -> 括号内容（归一化后）一致才放行
        """
        import re

        def _paren(s):
            m = re.search(r'[（(]([^（）()]*)[）)]', s or '')
            if not m:
                return None
            return m.group(1).replace('（', '(').replace('）', ')').strip()

        tp, sp = _paren(cn), _paren(s_cn)
        if tp is None:
            return True
        if sp is None:
            return False
        return tp == sp

    def _match_new_table_fields(self, target_table: StandardTable, result: CompareResult,
                                source_table_index: Dict[str, StandardTable],
                                new_field_target: str = None):
        """整表新增路径下仍做字段级跨表匹配（P4d）。

        用户确认整表新增 / 原标准无对应表时，此前所有字段一律落为新增——
        但"表是新的"不等于"每个字段都是新数据元"：医疗机构代码、患者姓名、
        就诊流水号 这类共享数据元在源标准其它表中普遍存在，应记为 matched
        （数据元复用），而非新增。沿用 _find_matching_field 全部安全网关
        （字段类型/角色/复合主体/描述兼容/唯一候选），只回收等概念字段。
        """
        from utils.pinyin_utils import generate_english_field_name
        standard_version = getattr(self, 'source_version', '5.0')

        # 源表去重（source_table_index 有 name / name|cn / cn 三键，同一表出现多次）
        seen_tables = set()
        unique_tables = []
        for st in source_table_index.values():
            if id(st) in seen_tables:
                continue
            seen_tables.add(id(st))
            unique_tables.append(st)

        def _locate_source_table(source_field):
            for st in unique_tables:
                if any(sf is source_field for sf in st.fields):
                    return st
            return None

        for field in target_table.fields:
            match_result = self._find_matching_field(
                field, {}, None, source_table_index, target_table)
            if match_result:
                source_field, match_type = match_result
                if getattr(self, '_p6_occupied', None) is not None:
                    if not str(match_type).startswith('auto_relation'):
                        self._p6_occupied.setdefault(target_table.name, {})[
                            source_field.chinese_name or source_field.name] = (
                                field.chinese_name or field.name)
                source_table = _locate_source_table(source_field)
                source_table_name = source_table.name if source_table else ''
                source_table_cn = source_table.chinese_name if source_table else ''
                modifications = self._check_modifications(source_field, field)
                if modifications:
                    result.modified.append({
                        'table_name': target_table.name,
                        'table_chinese_name': target_table.chinese_name,
                        'field_name': field.name,
                        'field_chinese_name': field.chinese_name,
                        'source_table': source_table_name,
                        'source_table_chinese_name': source_table_cn,
                        'source_field': source_field.name,
                        'source_field_chinese_name': source_field.chinese_name,
                        'match_type': match_type,
                        'modifications': modifications
                    })
                else:
                    result.matched.append({
                        'table_name': target_table.name,
                        'table_chinese_name': target_table.chinese_name,
                        'target_field': field.name,
                        'target_chinese_name': field.chinese_name,
                        'source_table': source_table_name,
                        'source_table_chinese_name': source_table_cn,
                        'source_field': source_field.name,
                        'source_field_chinese_name': source_field.chinese_name,
                        'match_type': match_type
                    })
                continue
            # 未匹配：新增字段
            generated_field_name = generate_english_field_name(
                field.chinese_name, standard_version=standard_version)
            result.new_fields.append({
                'table_name': target_table.name,
                'table_chinese_name': target_table.chinese_name,
                'name': field.name,
                'generated_name': generated_field_name,
                'chinese_name': field.chinese_name,
                'data_type': field.data_type,
                'length': field.length,
                'constraint': field.constraint,
                'description': field.description or '',
                'value_domains': [
                    {'code': vd.code, 'name': vd.name}
                    for vd in field.value_domains
                ],
                'new_field_target': new_field_target or target_table.name,
                'source_table_name': new_field_target or target_table.name
            })

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

    def _global_cn_lookup(self, cn: str, source_table_index: Dict[str, StandardTable]):
        """在全部源表中按中文名查找字段（用于跨表精确匹配复用）。结果按源表索引缓存。"""
        cache = getattr(self, '_gcn_cache', None)
        if cache is None:
            cache = {}
            for st in source_table_index.values():
                for sf in st.fields:
                    if sf.chinese_name:
                        cache.setdefault(sf.chinese_name, []).append(sf)
            self._gcn_cache = cache
        hits = cache.get(cn)
        if not hits:
            return None
        # 优先返回与描述兼容的字段；否则返回首个
        for sf in hits:
            return sf
        return None

    # ===== 跨表同义级兜底（P4）=====
    # 只做"同义变体"归一，不剥离括号说明——括号里的内容（如"对应其他诊断13"）
    # 恰恰是区分主子表展开字段的关键，剥离会造成大面积误配。
    _GLOBAL_NORM_PAIRS = [
        ('（', '('), ('）', ')'),          # 全角括号归一
        ('医师', '医生'), ('大夫', '医生'),
        ('编码', '代码'), ('代号', '代码'),
        ('唯一标识', '标识'),
        ('名字', '名称'), ('姓名', '名称'),
    ]
    # 结尾的"种类词"——比较时剥离，改由 _field_kind_compatible 单独把关，
    # 这样 "麻醉分级代码" 才能匹配到源标准里没有后缀的 "麻醉分级"。
    _GLOBAL_TAIL_KINDS = ['唯一标识', '流水号', '名称', '代码', '编码', '代号',
                          '标识', '标志', '序号', '编号', '签名']
    # 纯噪音字符：分隔符、标点、结构助词。两个标准对同一数据元的写法差异
    # 大量集中在这里，不去掉会造成大面积漏配：
    #   收退费日期时间      == 收/退费日期时间
    #   损伤、中毒的外部原因 == 损伤中毒外部原因
    _GLOBAL_NOISE_CHARS = '、，,；;／/·　 的'

    # 全局语义兜底用的"前缀"——比较时剥离，使组件字段匹配其基名：
    #   患者电子邮件地址 -> 电子邮件地址（匹配源"电子邮件地址"）
    #   住院主要诊断 -> 主要诊断（匹配源"主要诊断"）
    # 仅在 _global_semantic_lookup 中使用，不影响精确/同义主链路。
    # 注意：
    #  - 就诊/急诊 不在剥离列表：剥离后只剩"流水号/费用总金额"等通用词，
    #    会把 就诊流水号 错配到 住院流水号（角色闸门不覆盖 就诊vs住院）。
    #  - 出生地/户籍地/居住地/常住地/工作地 等"地址位置前缀"受保护（见
    #    _ADDR_PROTECTED_PREFIXES），不剥离——它们是地址组件族（省市/地市/
    #    区县/街道/村路弄/门牌/邮编）的**消歧关键**：出生地-省市代码 只能
    #    匹配 出生地（省市），不能匹配 户籍地址（省市）。
    _GLOBAL_LEAD_PREFIXES = ['患者', '本人', '住院', '门诊', '入院', '出院',
                             '产前', '产后', '主诉', '既往', '关键']
    # 地址位置前缀（不剥离，保留作消歧）：来源 V6.0 用"现住址/户籍地址/
    # 单位地址/联系人地址"，目标省平台用"居住地/户籍地/常住地/工作单位及
    # 地址"，通过 _ADDR_LOC_PAIRS 归一为同一前缀。
    _ADDR_PROTECTED_PREFIXES = ['出生地', '户籍地', '居住地', '现住地', '常住地',
                                '工作地', '单位', '家庭', '联系人']
    # 地址组件同义词（先括号归一、再整词替换）。两个标准对同一地址组件的
    # 写法差异集中在这里：
    #   省（自治区、直辖市） == 省市    市(地区、州) == 地市
    #   县(区) == 区县                  乡(镇、街道办事处)/乡镇、街道 == 街道乡镇
    #   村(街、路、弄等)/村、街、路、弄 == 村街路弄
    #   门牌号码 == 门牌                邮政编码/邮编 == 邮政代码
    # 顺序敏感：长词在前（省（自治区、直辖市） 先于 省市 无关，但 门牌号码
    # 先于 门牌；邮编 与 邮政编码 互不包含，任意顺序）。
    _ADDR_COMPONENT_PAIRS = [
        ('省（自治区、直辖市）', '省市'),
        ('省(自治区、直辖市)', '省市'),
        ('市(地区、州)', '地市'),
        ('市（地区、州）', '地市'),
        ('乡(镇、街道办事处)', '街道乡镇'),
        ('乡（镇、街道办事处）', '街道乡镇'),
        ('乡镇、街道', '街道乡镇'),
        ('村、街、路、弄', '村街路弄'),
        ('村(街、路、弄等)', '村街路弄'),
        ('村（街、路、弄等）', '村街路弄'),
        ('门牌号码', '门牌'),
        ('邮政编码', '邮政代码'),
        ('邮编', '邮政代码'),
    ]
    # 地址位置同义词（先长后短）：源标准的写法 -> 目标省平台的写法。
    #   现住址/现住 == 居住地     户籍地址 == 户籍地
    #   单位地址/工作单位及地址 == 单位    联系人地址 == 联系人
    _ADDR_LOC_PAIRS = [
        ('工作单位及地址', '单位'),
        ('联系人地址', '联系人'),
        ('户籍地址', '户籍地'),
        ('单位地址', '单位'),
        ('家庭地址', '家庭'),
        ('现住址', '居住地'),
        ('现住', '居住地'),
    ]

    @classmethod
    def _global_norm_base(cls, cn: str) -> str:
        """归一化并剥离尾部种类词，得到跨表比对用的基名。"""
        s = cn or ''
        for a, b in cls._GLOBAL_NORM_PAIRS:
            s = s.replace(a, b)
        for ch in cls._GLOBAL_NOISE_CHARS:
            s = s.replace(ch, '')
        for k in sorted(cls._GLOBAL_TAIL_KINDS, key=len, reverse=True):
            if s.endswith(k) and len(s) > len(k):
                s = s[:-len(k)]
                break
        return s.strip()

    @classmethod
    def _global_semantic_base(cls, cn: str) -> str:
        """归一化并剥离前缀，得到全局语义兜底用的基名。

        与 _global_norm_base 的差异（针对实测 3429 新增字段的三大漏配源）：
        1. 地址组件/位置同义词归一：出生地-省市代码 == 出生地（省市）、
           户籍地-门牌号码 == 户籍地址（门牌号码）、居住地-详细地址 == 现住详细地址。
        2. 尾部种类词"有条件剥离"：剩余基名 >= 4 字才剥。避免 就诊流水号 ->
           就诊（源 26 个候选、歧义）、患者姓名 -> 患者（源 118 个候选）这类
           过度剥离把唯一性闸门直接废掉。
        3. 前缀"有条件剥离"：剩余基名 >= 4 字才剥，且地址位置前缀（出生地/
           户籍地/居住地/常住地…）受保护不剥——它们是地址组件族的消歧关键。
        """
        s = cn or ''
        # 1. 基础同义归一 + 全角括号归一
        for a, b in cls._GLOBAL_NORM_PAIRS:
            s = s.replace(a, b)
        # 2. 地址组件同义词（长词在前）
        for a, b in cls._ADDR_COMPONENT_PAIRS:
            s = s.replace(a, b)
        # 3. 地址位置同义词（长词在前）
        for a, b in cls._ADDR_LOC_PAIRS:
            s = s.replace(a, b)
        # 4. 去噪（含括号与连字符：出生地-省市代码 -> 出生地省市代码）
        for ch in cls._GLOBAL_NOISE_CHARS + '()（）-－—':
            s = s.replace(ch, '')
        # 5. 尾部种类词：仅当剩余基名 >= 4 才剥离
        for k in sorted(cls._GLOBAL_TAIL_KINDS, key=len, reverse=True):
            if s.endswith(k) and len(s) - len(k) >= 4:
                s = s[:-len(k)]
                break
        # 6. 前缀剥离：仅当剩余基名 >= 4；地址位置前缀受保护
        changed = True
        while changed:
            changed = False
            s2 = re.sub(r'^[\-—、·\s]+', '', s)
            for p in cls._GLOBAL_LEAD_PREFIXES:
                if s2.startswith(p) and len(s2) - len(p) >= 4:
                    s2 = s2[len(p):]
                    s2 = re.sub(r'^[\-—、·\s]+', '', s2)
                    changed = True
                    break
            s = s2
        return s.strip()

    # ===== 陈旧正向映射治理（P5）=====
    _EN_NORM_PAIRS = [('doctor', 'dr'), ('department', 'dept'), ('number', 'no'),
                      ('code', 'no'), ('identity', 'id'), ('identifier', 'id')]

    # P5 局部同义归一：只用于"知识库映射体检"，不影响主匹配链路。
    # 覆盖实测中导致误报的同义写法差异。
    # 顺序敏感：长词在前（身份证件 -> 证件，避免 身份证 先命中留下"证件件"）
    _P5_NORM_PAIRS = [('病人', '患者'), ('号码', '号'),
                      ('职工', '人员'), ('员工', '人员'), ('工号', '人员代码'),
                      ('身份证件', '证件'), ('身份证', '证件'),
                      ('药物', '药品'), ('药械', '药品')]

    @classmethod
    def _en_core(cls, n: str) -> str:
        s = (n or '').lower().replace('_', '')
        for a, b in cls._EN_NORM_PAIRS:
            s = s.replace(a, b)
        return s

    @classmethod
    def _p5_norm(cls, cn: str) -> str:
        """体检用同义归一（全局归一对 + P5 局部补充）。"""
        s = cn or ''
        for a, b in cls._GLOBAL_NORM_PAIRS:
            s = s.replace(a, b)
        for a, b in cls._P5_NORM_PAIRS:
            s = s.replace(a, b)
        return s

    def _user_custom_hard_conflict(self, target_field: StandardField,
                                   source_field: StandardField) -> str:
        """判断一条知识库正向映射是否与本次标准原文**硬冲突**。

        知识库的正向映射同样是相对特定源标准的结论（见 user_custom_mappings.yaml
        的 created_from）。换源标准后，同名表/字段可能指向完全不同的数据元，
        例如实测发现的：
            门(急)诊号        ← 姓名
            责任护士代码      ← 责任护士执业证书编码
        因此在采用前做一次硬冲突体检。

        返回冲突原因字符串；无冲突返回 ''。
        判据保持保守——只在"证据明确矛盾"时报冲突，避免否决正确的人工确认：
          1. 中文名相同         -> 一定不冲突
          2. 英文名核心相同     -> 标准自身命名不一致（医师姓名/doc_sign），不冲突
          3. 字段种类硬冲突     -> 冲突（代码 vs 执业证书编码、名称 vs 代码）
          4. 核心概念完全不相干 -> 冲突（门(急)诊号 vs 姓名）
        """
        t_cn = target_field.chinese_name or ''
        s_cn = source_field.chinese_name or ''
        if not t_cn or not s_cn or t_cn == s_cn:
            return ''
        # 英文名同源：以英文名为准，认可该映射
        if self._en_core(target_field.name) and \
                self._en_core(target_field.name) == self._en_core(source_field.name):
            return ''
        # 先做同义归一，避免"病人/患者""号码/号""职工/人员"这类写法差异造成误报
        t_n, s_n = self._p5_norm(t_cn), self._p5_norm(s_cn)
        if t_n == s_n:
            return ''
        # 签名 ↔ 姓名：主体相同时属标准命名习惯差异，人工这样对齐是合理的
        # （麻醉医师姓名 ← 麻醉医师签名、申请医师签名 ← 申请医师姓名）
        k1 = self._field_kind_of(t_n)
        k2 = self._field_kind_of(s_n)
        kinds = {k1, k2}
        if (kinds & self._FIELD_KIND_SIGN) and (kinds & self._FIELD_KIND_NAME):
            b1 = t_n[:-len(k1)] if k1 else t_n
            b2 = s_n[:-len(k2)] if k2 else s_n
            # 主体相同或一方是另一方的限定（接诊医师姓名 ← 医师签名）均认可
            if b1 and b2 and (b1 == b2 or b1 in b2 or b2 in b1):
                return ''
        if not self._field_kind_compatible(t_n, s_n):
            return '字段种类冲突'
        c1 = self._strip_generic(t_n)
        c2 = self._strip_generic(s_n)
        # 一方核心被剥空、另一方仍有实质限定 -> 不相干
        # （门(急)诊号 ← 姓名、第一助手姓名 ← 病人姓名）
        if bool(c1) != bool(c2):
            # 强信号：一侧是"裸通用词"（姓名/编号），另一侧带实质限定。
            # 这正是人工误点最典型的形态（主治医师姓名 ← 姓名）。
            return '核心概念缺失'
        # 双方都有核心且互不为子串时，用"公共汉字数"作软判据：
        # ≤1 个公共字才算不相干（第一助手/患者=0 -> 冲突；证件号/身份证号=2 -> 放行）
        if c1 and c2 and c1 not in c2 and c2 not in c1:
            if len(set(c1) & set(c2)) <= 1:
                return '核心概念不相干'
        return ''

    def _p6_declare_uc_intent(self, target_table: StandardTable, target_field: StandardField) -> None:
        """登记 user_custom 意图：声明了来源但解析失败（陈旧/错名/硬冲突）。

        user_custom 是人工确认结论，即使知识库中源字段名与源标准实际不符，
        P6 兜底通道也不应低置信猜配抢占该目标字段（保持 new_field 并暴露
        待订正项），而不是 kw 匹配到另一个同名源字段。
        """
        if getattr(self, '_p6_uc_declared', None) is not None:
            self._p6_uc_declared.setdefault(target_table.name, set()).add(
                target_field.chinese_name or target_field.name)

    def _accept_user_custom(self, target_table: StandardTable,
                            target_field: StandardField,
                            source_field: StandardField,
                            source_field_table: StandardTable = None,
                            aligned_source_table: StandardTable = None):
        """采用一条知识库正向映射前的硬体检：语义硬冲突 + 外键方向。

        - 语义硬冲突（_user_custom_hard_conflict）：默认（hard_gate=False）
          只登记可疑、仍采用人工确认（人是权威）；强网关（True）登记并否决。
        - 外键方向冲突（_user_custom_direction_conflict）：**永远否决**——
          主表反向借子表字段是数据模型层面的硬约束（一对多方向不成立），
          不存在"人工确认优先"，否决后由调用方继续走常规匹配。
        """
        conflict = self._user_custom_hard_conflict(target_field, source_field)
        direction = None
        if not conflict and source_field_table is not None:
            direction = self._user_custom_direction_conflict(
                source_field_table, aligned_source_table)
        if not conflict and not direction:
            return (source_field, 'user_custom')
        hard = getattr(self, 'user_custom_hard_gate', False)
        reason = direction or conflict
        self.user_custom_conflicts.append({
            'target_table': target_table.chinese_name or target_table.name,
            'target_field': target_field.chinese_name or target_field.name,
            'kb_source_field': source_field.chinese_name or source_field.name,
            'kb_source_table': ((source_field_table.chinese_name
                                 or source_field_table.name)
                                if source_field_table is not None else ''),
            'reason': reason,
            'action': ('已否决，改走常规匹配'
                       if (hard or direction)
                       else '仍采用人工确认，仅登记待复核'),
        })
        return None if (hard or direction) else (source_field, 'user_custom')

    def _user_custom_direction_conflict(self, source_field_table: StandardTable,
                                        aligned_source_table: StandardTable) -> str:
        """外键方向校验：子表可借主表字段，主表不可反向借子表字段。

        方向判定基于源标准字段"说明"中声明的外键关系（_auto_fk_edges，
        每条边 = (子表, 子表中文, 子表字段, 主表, 主表中文, 主表字段)）：
          - 同表：合法
          - 目标对齐表(子表) → 源字段表(主表)：取业务表时关联主数据，合法
          - 源字段表(子表) → 目标对齐表(主表)：主数据反向借业务表字段，
            一对多方向不成立（一个患者可有多份病案首页），非法
          - 无外键关系：不判非法（由知识库声明背书）
        """
        if source_field_table is None or aligned_source_table is None:
            return ''
        sft = source_field_table.name or ''
        ast = aligned_source_table.name or ''
        if not sft or not ast or sft == ast:
            return ''
        edges = getattr(self, '_auto_fk_edges', None)
        if not edges:
            return ''
        fk_child_to_parent = {(e[0], e[3]) for e in edges}
        # 目标对齐表(子表) → 源字段表(主表)：取X时关联Y，合法
        if (ast, sft) in fk_child_to_parent:
            return ''
        # 源字段表(子表) → 目标对齐表(主表)：反向借用，非法
        if (sft, ast) in fk_child_to_parent:
            sft_cn = source_field_table.chinese_name or sft
            ast_cn = aligned_source_table.chinese_name or ast
            return (f'外键方向反向：目标表（{ast_cn}）为被引用主表，'
                    f'不得反向借用子表（{sft_cn}）字段')
        # 无外键关系：不判非法
        return ''

    def _resolve_source_table(self, source_table_name: str,
                              source_table_index: Dict[str, StandardTable]):
        """解析知识库声明的源表名，返回 StandardTable 或 None。

        支持三级匹配：
          1. 表名/中文名精确匹配（最可靠，立即返回）
          2. 包含匹配：声明名与某表中文名互为子串
             （如 患者基本信息表 → 患者基本信息），要求**唯一**命中
          3. 匹配失败返回 None（调用方视为"源表声明失效"→ 作废走常规匹配）

        只做解析、不做降级；宁可返回 None 也不做模糊猜测——
        歧义包含命中（多个表都含该子串）同样返回 None。
        """
        if not source_table_name or not source_table_index:
            return None
        seen = set()
        contains = []
        for st in source_table_index.values():
            if id(st) in seen:
                continue
            seen.add(id(st))
            nm = st.name or ''
            cn = st.chinese_name or ''
            # 1. 精确匹配（英文名 / 中文名）
            if nm == source_table_name or cn == source_table_name:
                return st
            # 2. 中文名包含匹配（双向），仅积累候选
            if cn and (source_table_name in cn or cn in source_table_name):
                contains.append(st)
        # 唯一包含命中才返回；多候选视为歧义，返回 None
        if len(contains) == 1:
            return contains[0]
        return None

    def _global_fuzzy_lookup(self, target_field: StandardField,
                             source_table_index: Dict[str, StandardTable]):
        """跨表同义级查找：基名一致 + 字段种类兼容 + 角色兼容 + 说明兼容。

        回收"代码/编码"、"医师/医生"、"标识/代码"这类同义变体的跨表漏配：
        - 入院科室代码  ← 住院就诊记录表.入院科室编码
        - 麻醉分级代码  ← 病案首页手术.麻醉分级
        - 医嘱执行人代码 ← 住院医嘱明细表.医嘱执行人标识

        同时被下列约束挡住（保持精度）：
        - 主治医师代码 ✗ 主治医师姓名（种类 CODE vs NAME）
        - 治疗转归(对应其他诊断13) ✗ 治疗转归(对应西医诊断)（括号说明不同）
        """
        cn = target_field.chinese_name
        if not cn:
            return None
        cache = getattr(self, '_gfz_cache', None)
        if cache is None:
            cache = {}
            for st in source_table_index.values():
                for sf in st.fields:
                    if not sf.chinese_name:
                        continue
                    base = self._global_norm_base(sf.chinese_name)
                    if len(base) >= 3:
                        cache.setdefault(base, []).append(sf)
            self._gfz_cache = cache

        base = self._global_norm_base(cn)
        if len(base) < 3:
            return None
        hits = cache.get(base)
        if not hits:
            return None

        best = None
        for sf in hits:
            if not self._field_kind_compatible(cn, sf.chinese_name):
                continue
            if not self._is_role_compatible_for_keyword(cn, sf.chinese_name):
                continue
            if not self._composite_subject_compatible(cn, sf.chinese_name):
                continue
            if not self._is_description_compatible(target_field, sf):
                continue
            # 种类完全一致的优先（代码↔代码 优于 代码↔标识）
            if (self._field_kind_of(cn) == self._field_kind_of(sf.chinese_name)):
                return sf
            if best is None:
                best = sf
        return best

    def _global_semantic_lookup(self, target_field: StandardField,
                                source_table_index: Dict[str, StandardTable]):
        """跨表语义兜底（P4c）：归一化基名一致 + 四道闸门 + 唯一候选（按概念去重）。

        回收三类跨表漏配：
        - 前缀型：患者电子邮件地址 ← 电子邮件地址、住院主要诊断 ← 主要诊断
        - 地址组件族：出生地-省市代码 ← 出生地（省市）、户籍地-门牌号码 ←
          户籍地址（门牌号码）、居住地-详细地址 ← 现住详细地址
        - 同义变体：药品代码 ← 药品编码、症状名称 ← 症状名称（跨表同名）

        候选按"中文名去重"：同一中文名出现在多张源表 = 同一概念，只算一个候选，
        避免 医疗机构代码（113 个候选）、就诊类型代码（N 个候选）这类高频字段
        因"表内同名"被唯一性闸门误拒。多候选（不同概念）仍不自动匹配。
        """
        cn = target_field.chinese_name
        if not cn:
            return None
        cache = getattr(self, '_gsz_cache', None)
        if cache is None:
            cache = {}
            for st in source_table_index.values():
                for sf in st.fields:
                    if not sf.chinese_name:
                        continue
                    base = self._global_semantic_base(sf.chinese_name)
                    if len(base) >= 2:
                        cache.setdefault(base, []).append(sf)
            self._gsz_cache = cache

        base = self._global_semantic_base(cn)
        if len(base) < 2:
            return None
        hits = cache.get(base)
        if not hits:
            return None

        cands = []
        seen = set()
        for sf in hits:
            if not self._field_kind_compatible(cn, sf.chinese_name):
                continue
            if not self._is_role_compatible_for_keyword(cn, sf.chinese_name):
                continue
            if not self._composite_subject_compatible(cn, sf.chinese_name):
                continue
            if not self._is_description_compatible(target_field, sf):
                continue
            # 同一中文名去重（同一概念跨表出现，不算歧义候选）
            if sf.chinese_name in seen:
                continue
            seen.add(sf.chinese_name)
            cands.append(sf)
        if not cands:
            return None
        # 唯一最佳：种类完全一致者优先；仍有多候选则视为歧义，不自动匹配。
        if len(cands) == 1:
            return cands[0]
        tk = self._field_kind_of(cn)
        exact_kind = [c for c in cands if self._field_kind_of(c.chinese_name) == tk]
        if len(exact_kind) == 1:
            return exact_kind[0]
        return None

    def _get_field_tables(self, sf, source_table_index):
        """查找字段在所有源表中出现的表名集合（按 (name, chinese_name) 配对）。"""
        if not sf or not source_table_index:
            return set()
        names = set()
        for st in source_table_index.values():
            for f in st.fields:
                if (f.name == sf.name
                        and f.chinese_name == sf.chinese_name):
                    names.add(st.name)
                    break
        return names

    def _check_master_table_direction(self, source_table, target_table, sf, source_table_index):
        """主词表方向校验：主词表（无 FK 边，如 PERSON）不可反向借业务子表字段。

        仅属性子表（表名以主表名+"_"开头，如 PERSON_ADDRESS）例外。
        仅在源表匹配为精确匹配时执行（模糊匹配时表映射不可靠，放行），
        避免 m_cli_advices_undrug→BASE_DRUG 等误匹配导致 FK 方向误伤。
        返回 True 表示允许（合法或无需检查），False 表示拒绝。
        """
        if source_table is None or target_table is None or sf is None:
            return True

        # 源表匹配精确性检查：仅当源表中文名与目标表中文名一致时，
        # FK 方向检查才可靠。模糊匹配时表映射不可靠，跳过检查。
        src_cn = (source_table.chinese_name or '').strip('*').strip()
        tgt_cn = (target_table.chinese_name or '').strip('*').strip()
        if src_cn != tgt_cn:
            return True  # 模糊匹配，表映射不可靠，放行

        st_name = source_table.name
        if st_name not in getattr(self, '_master_tables', set()):
            return True  # 非主词表，放行
        candidate_names = self._get_field_tables(sf, source_table_index)
        if not candidate_names:
            return True  # 无法确定候选表，放行
        for ct_name in candidate_names:
            if ct_name == st_name:
                return True  # 同表
            if ct_name.startswith(st_name + '_'):
                return True  # 属性子表
        return False  # 非法：主词表反向借业务子表字段

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
        # 知识库声明解析失败标志：声明源表/源字段在本源标准中不存在 →
        # 跳过 gmap 全局跨表复用通道（杜绝幽灵映射），直接走程序常规匹配。
        # 必须在函数级初始化：非 user_custom 字段也要走 gmap 通道。
        uc_failed = False
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
            # 1. 若指定了源表且能在当前标准中解析，则从该表取字段（最高优先）
            # 2. 若源表/源字段在当前标准中无法解析（多为历史陈旧表名/旧版本字段名），
            #    不再"降级"到全局跨表复用（gmap）——那正是幽灵映射的来源：
            #    知识库 A 条目的目标字段被知识库 B 条目的源字段跨表顶替
            #    （患者基本信息.居民健康卡卡号 被 gmap 撞成 病案首页.健康卡号，
            #     且违反外键方向）。改为：声明解析失败即作废，交给程序常规
            #    匹配通道（exact/semantic/cross_table/P6）裁决。
            # 3. 仅当用户明确确认该字段"无对应源字段"（source_field 为空）时，才判为新增。

            has_source = bool(source_field_name or source_field_cn)

            if has_source:
                if source_table_name:
                    resolved_table = None
                    if source_table_index:
                        resolved_table = self._resolve_source_table(
                            source_table_name, source_table_index)
                    if resolved_table is not None:
                        # 声明的源表可解析：源字段必须真实存在于该表
                        for sf in resolved_table.fields:
                            if (sf.name == source_field_name or
                                sf.chinese_name == source_field_name or
                                sf.chinese_name == source_field_cn):
                                r = self._accept_user_custom(
                                    target_table, target_field, sf,
                                    source_field_table=resolved_table,
                                    aligned_source_table=source_table)
                                if r:
                                    return r
                                break  # 硬冲突/方向非法：弃用该映射，继续常规匹配
                        # 表在但声明字段在原标准该表中不存在：存在性校验失败，
                        # 作废走常规匹配（不登记 P6 意图——用户要求走程序逻辑）
                        uc_failed = True
                    else:
                        # 声明的源表不可解析（陈旧表名）：源表声明失效，
                        # 作废走常规匹配，不降级 gmap（杜绝幽灵映射）
                        uc_failed = True
                else:
                    # 没有指定源表，但有源字段：尝试在当前对齐源表按字段名查找
                    if source_field_index:
                        sf = source_field_index.get(source_field_name)
                        if not sf and source_field_cn:
                            for s in source_table.fields:
                                if s.chinese_name == source_field_cn:
                                    sf = s
                                    break
                        if sf:
                            r = self._accept_user_custom(
                                target_table, target_field, sf,
                                source_field_table=source_table,
                                aligned_source_table=source_table)
                            if r:
                                return r
                    # 当前对齐表未命中或硬冲突：作废走常规匹配（不降级 gmap）
                    uc_failed = True
            else:
                # 用户明确确认：该字段无对应源字段 -> 倾向保持为新增字段。
                #
                # 但"新增"是一个**相对于特定源标准**的否定性结论，不具备跨源标准的
                # 复用价值：知识库中的确认可能来自另一对标准的比对任务
                # （见 user_custom_mappings.yaml 的 created_from）。若照搬，会把
                # 本次源标准中确实存在的同名字段错判为新增（漏配）。
                #
                # 因此采用"事实优先 / 弱否决 + 强否定"双轨策略（P4）：
                #   弱否决（fact 命中）：当本次源标准中存在与目标字段**中文名完全一致**
                #     或同义/同概念且说明兼容的字段时，以标准原文这一硬证据为准，
                #     撤销该条陈旧否定确认，继续走后续匹配；
                #     同时把冲突登记到 stale_negative_conflicts，供人工复核与知识库订正。
                #   强否定（fact 全 miss + 表可解析）：否定确认指向的源表在当前
                #     源标准中存在（知识库明确表示"该表无此字段"），且全库三级事实
                #     查找全部 miss —— 这是人工确认的强否定，应判死为新增，
                #     否则 keyword / auto_relation 低置信通道会猜配抢占
                #     （会诊所见 ✗ 会诊所在医疗机构名称、术前用药 ✗ 麻醉前用药、
                #      补充诊断-中医病名代码 ✗ 初步诊断--中医病名编码）。
                #   表不可解析（陈旧表名，如 患者基本信息表 已被 患者基本信息 取代）：
                #     知识库来源可疑，不判死，交给完整流水线
                #     （P6 多表关联仍可回收 出生地-详细地址 等）。
                neg_table_resolved = False
                if source_table_name and source_table_index:
                    for _stn, _st in source_table_index.items():
                        if (_st.chinese_name == source_table_name or
                                _st.name == source_table_name or
                                source_table_name in _st.chinese_name):
                            neg_table_resolved = True
                            break
                if getattr(self, 'stale_negative_override', True) and target_field.chinese_name:
                    fact = None
                    if source_field_index:
                        for sf in source_field_index.values():
                            if sf.chinese_name == target_field.chinese_name:
                                fact = sf
                                break
                    if fact is None and source_table_index:
                        fact = self._global_cn_lookup(
                            target_field.chinese_name, source_table_index)
                    # 第三级事实：同义变体（代码↔编码、医师↔医生、代码↔标识、
                    # 流水号↔唯一标识 等）。陈旧否定确认同样不该压过
                    # "源标准中存在同义字段"这一硬证据——否则 麻醉分级代码、
                    # 医嘱开立科室代码 这类字段会被永久钉死为新增，且因为提前
                    # return 而连 cross_table 兜底都走不到。
                    # 注意：这里只用于"撤销否定确认"，并不直接采用 fact，
                    # 后续仍要过 gmap / exact_chinese / cross_table 的全部网关。
                    fuzzy_fact = False
                    if (fact is None and source_table_index
                            and getattr(self, 'stale_negative_override_fuzzy', True)):
                        fact = self._global_fuzzy_lookup(target_field, source_table_index)
                        fuzzy_fact = fact is not None
                    # 第四级事实：语义基名（前缀剥离 + 地址组件归一 + 同义变体）。
                    # _global_fuzzy_lookup 只做基础归一（不去前缀、不拆地址组件），
                    # 像 "患者电子邮件地址←电子邮件地址"、"出生地-省市代码←出生地（省市）"
                    # 这类前缀/组件差异只有语义基名能对齐。陈旧否定确认同样不该压过
                    # "源标准中存在同概念字段"这一硬证据——否则这类字段会在优先级
                    # 循环之前被提前 return None，连 cross_table 语义兜底都走不到。
                    semantic_fact = False
                    if (fact is None and source_table_index
                            and getattr(self, 'stale_negative_override_semantic', True)):
                        fact = self._global_semantic_lookup(target_field, source_table_index)
                        semantic_fact = fact is not None
                    if fact is not None and self._is_description_compatible(target_field, fact):
                        if semantic_fact:
                            match_level, reason = (
                                'semantic', '源标准中存在同概念字段（语义基名一致），陈旧否定确认已撤销')
                        elif fuzzy_fact:
                            match_level, reason = (
                                'synonym', '源标准中存在同义字段，陈旧否定确认已撤销')
                        else:
                            match_level, reason = (
                                'exact', '源标准中存在同名字段，陈旧否定确认已撤销')
                        self.stale_negative_conflicts.append({
                            'target_table': target_table.chinese_name or target_table.name,
                            'target_field': target_field.chinese_name or target_field.name,
                            'kb_key': table_field_key,
                            'kb_said': '新增（无对应源字段）',
                            'fact_source_field': fact.chinese_name or fact.name,
                            'match_level': match_level,
                            'reason': reason,
                        })
                        # 不 return，继续往下走 gmap / exact_chinese 等常规匹配
                    # fact 未找到或描述不兼容：
                    if fact is None and neg_table_resolved:
                        # 强否定判死：否定确认指向的源表可解析，且全库三级事实
                        # （同名/同义/语义基名）全部 miss —— 人工"该表无此字段"的
                        # 确认成立。登记 P6 意图（人工明确无来源），P6 keyword
                        # 不得猜配抢占（会诊所见 ✗ 会诊所在医疗机构名称）。
                        # 同时直接判死为新增，避免 keyword/auto_relation 低置信
                        # 通道继续猜配（术前用药 ✗ 麻醉前用药）。
                        self._p6_declare_uc_intent(target_table, target_field)
                        return None
                    # 表名陈旧（患者基本信息表 等）或 fact 描述冲突：不判死，
                    # 交给 gmap / exact_chinese / cross_table / P6 完整流水线，
                    # 由各通道门禁与自验证做最终裁决（出生地-详细地址 ←
                    # 患者地址信息.详细地址 即靠 P6 沿 FK 关联图精确命中）。
                else:
                    # stale_negative_override 关闭或目标无中文名：同样不提前判死，
                    # 交给完整流水线裁决（与上方一致，避免开关差异导致行为分裂）。
                    pass

        # 全局字段映射（跨表复用）：已确认过的字段映射一次学习、全表复用。
        # 不带源表约束，按"当前对齐的源表"解析源字段，从而在不同表中自动生效。
        # 注意：仅当知识库映射声明**未被判定失败**（uc_failed=False）时才允许复用；
        # 声明解析失败时跳过本通道，避免 gmap 用其它映射的源字段跨表顶替
        # （幽灵映射：患者基本信息.居民健康卡卡号 被 病案首页.健康卡号 顶替）。
        gmap = getattr(self, 'user_custom_field_mappings_global', {})
        if not uc_failed:
            for gkey in (target_field.chinese_name, target_field.name):
                gm = gmap.get(gkey) if gkey else None
                if not gm:
                    continue
                # 人工确认同义优先（覆盖陈旧 user_custom 通用映射）：
                # 若目标字段在 field_synonyms.yaml 中显式声明了同义词（人工确认的
                # 等价关系，如 业务数据产生日期时间↔创建日期时间），而本 gmap 候选
                # 源字段并非这些确认同义词之一，则跳过该 gmap 候选，让后续 synonym
                # 通道按人工确认同义匹配（避免 数据生成日期时间 越权抢占 创建日期时间）。
                exp = self.synonyms.get(target_field.chinese_name)
                if exp is not None:
                    gm_src = gm.get('source_field_cn') or gm.get('source_field') or ''
                    if (gm_src not in exp
                            and target_field.chinese_name
                            not in (self.synonyms.get(gm_src) or ())):
                        continue
                sf_name = gm.get('source_field')
                sf_cn = gm.get('source_field_cn', '')
                found = None
                found_table = None
                if source_field_index:
                    found = source_field_index.get(sf_name)
                    if not found and sf_cn:
                        for s in source_table.fields:
                            if s.chinese_name == sf_cn:
                                found = s
                                break
                    if found:
                        found_table = source_table
                # 当前源表找不到时，允许在其它源表中查找，但源字段所在表
                # 必须通过外键方向校验（子表可借主表；主表不可反向借子表）。
                if not found and source_table_index:
                    for st in source_table_index.values():
                        if st is source_table:
                            continue
                        for s in st.fields:
                            if s.name == sf_name or s.chinese_name == sf_cn or s.chinese_name == sf_name:
                                found = s
                                found_table = st
                                break
                        if found:
                            break
                if found:
                    r = self._accept_user_custom(
                        target_table, target_field, found,
                        source_field_table=found_table,
                        aligned_source_table=source_table)
                    if r:
                        return r
                break

        for priority in self.match_priority:
            if priority == 'new_field':
                # 新增字段 - 不匹配，留给调用方处理
                continue

            if priority == 'exact_chinese':
                # 1. 精确匹配中文名（当前对齐源表内）
                for source_field in source_field_index.values():
                    if target_field.chinese_name and target_field.chinese_name == source_field.chinese_name:
                        # 验证：如果字段说明不兼容，则跳过
                        if not self._is_description_compatible(target_field, source_field):
                            continue
                        self.stats['exact_chinese'] += 1
                        return (source_field, 'exact_chinese')

                # 1b. 全局跨表精确匹配：回收"同名异表"漏配。
                # 目标字段中文名在其它源表中也存在 -> 视为同一概念，跨表匹配。
                # 仅在当前对齐表未命中时触发，且要求字段说明兼容，避免误匹配。
                # 注意：主词表（如 PERSON 患者基本信息）不可反向借业务子表字段，
                # 仅属性子表（表名以主表名+"_"开头）例外。
                if source_table_index and target_field.chinese_name:
                    gf = self._global_cn_lookup(target_field.chinese_name, source_table_index)
                    if gf is not None and self._is_description_compatible(target_field, gf):
                        if self._check_master_table_direction(source_table, target_table, gf, source_table_index):
                            self.stats['exact_chinese'] += 1
                            return (gf, 'exact_chinese')

            elif priority == 'exact_english':
                # 2. 精确匹配英文名（大小写敏感）
                if target_field.name in source_field_index:
                    source_field = source_field_index[target_field.name]
                    # 验证：如果字段说明不兼容，则跳过
                    if not self._is_description_compatible(target_field, source_field):
                        continue
                    self.stats['exact_english'] += 1
                    return (source_field, 'exact_english')
                # 2b. 大小写不敏感兜底（rh_code ↔ RH_CODE）
                target_upper = target_field.name.upper()
                for sf_name, sf in source_field_index.items():
                    if sf_name.upper() == target_upper:
                        if not self._is_description_compatible(target_field, sf):
                            continue
                        self.stats['exact_english'] += 1
                        return (sf, 'exact_english')

            elif priority == 'semantic_chinese':
                # 3. 同义词匹配
                if self.use_synonym:
                    for source_field in source_field_index.values():
                        if self._is_synonym_match(target_field.chinese_name, source_field.chinese_name):
                            # 人工确认同义专属闸门（authoritative）：
                            # 若目标字段在 field_synonyms.yaml 中显式声明了同义词
                            # （人工确认的等价关系，如 业务数据产生日期时间↔创建日期时间），
                            # 则 synonym 通道只接受这些显式声明的源字段，杜绝子串模糊
                            # 同义误配（业务数据产生日期时间 被子串规则误配到 出生日期：
                            # PERSON 字段顺序 出生日期 先于 创建日期时间，循环先命中前者）。
                            # 未显式声明同义词的字段不受影响，仍走常规子串模糊匹配。
                            exp = self.synonyms.get(target_field.chinese_name)
                            if exp is not None:
                                if (source_field.chinese_name not in exp
                                        and target_field.chinese_name
                                        not in (self.synonyms.get(source_field.chinese_name) or ())):
                                    continue
                            if not self._is_description_compatible(target_field, source_field):
                                # 人工确认同义豁免描述闸门（与 P6 通道一致）：
                                # 已登记为同义的对（业务数据产生日期时间↔创建日期时间、
                                # 业务数据更新日期时间↔修改日期时间 等）描述措辞差异
                                # 不应否决，否则人工确认同义逃逸——create_time 会绕到
                                # PERSON_ADDRESS.SYS_CREATED_AT 而非主表 PERSON.SYS_CREATED_AT。
                                if not (self._auto_rel_channel_synonym_hit(target_field.chinese_name, source_field.chinese_name)
                                        or self._in_explicit_synonym_dict(target_field.chinese_name, source_field.chinese_name, self.synonyms)):
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

                # 跨表同义级兜底（P4）：relations BFS 未命中时，按"基名"全局再捞一遍。
                # relations 知识库只覆盖了显式建模的表间关系，很多同义变体
                # （入院科室代码←入院科室编码）落在没建关系的表里，只能靠全局兜底。
                # 注意：主词表（如 PERSON 患者基本信息）不可反向借业务子表字段，
                # 仅属性子表（表名以主表名+"_"开头）例外。
                if source_table_index and self.cross_table_fuzzy:
                    gf = self._global_fuzzy_lookup(target_field, source_table_index)
                    if gf is not None and self._check_master_table_direction(source_table, target_table, gf, source_table_index):
                        self.stats['cross_table_fuzzy'] = self.stats.get('cross_table_fuzzy', 0) + 1
                        return (gf, 'cross_table_fuzzy')

                    # 跨表语义兜底（P4c）：前缀剥离后基名一致 + 唯一最佳候选。
                    # 回收"患者电子邮件地址←电子邮件地址"等前缀型漏配；
                    # 多候选不自动匹配，留待自验证登记。
                    gs = self._global_semantic_lookup(target_field, source_table_index)
                    if gs is not None and self._check_master_table_direction(source_table, target_table, gs, source_table_index):
                        self.stats['cross_table_semantic'] = self.stats.get('cross_table_semantic', 0) + 1
                        return (gs, 'cross_table_semantic')

        # 自动外键关联通道（P6）：主表内与全局兜底均未命中时，沿源标准字段"说明"
        # 中声明的外键关联图搜索关联子表（如 患者卡证信息/患者地址信息），
        # 回收 卡类型代码←卡证类型、卡号/社保卡号←卡证号码、
        # 出生地/居住地-详细地址←详细地址 这类"目标表字段存在于源关联子表"的漏配。
        # 仅在全部常规通道失败后触发（本通道是 new_field 前的最后一道闸）。
        # 跨表收集候选、全局取最高优先级等级（exact<synonym<semantic<keyword），
        # 避免"邻接表按名排序、首表命中即返回"导致低置信抢占：如 社保卡号
        # 曾被字母序靠前表内的 医保卡号(keyword) 抢占，而 PERSON_IDENTIFICATION
        # 的 卡证号码(synonym) 永远走不到。通道内全部复用安全网关 + 占用保护。
        if (source_table and source_table_index
                and getattr(self, '_auto_adjacency', None)
                and getattr(self, 'auto_relation_enabled', True)):
            candidates = []
            for nb in sorted(self._auto_adjacency.get(source_table.name, ())):
                nb_table = source_table_index.get(nb)
                if nb_table is None:
                    continue
                r = self._match_in_auto_relation_table(
                    target_field, nb_table, target_table, defer_claim=True)
                if r:
                    candidates.append((r[0], nb_table, r[1], r[2]))
            if candidates:
                best_rank = min(c[0] for c in candidates)
                best = [c for c in candidates if c[0] == best_rank]
                # 按源字段身份（中文名+英文名）去重：同一概念可能出现在多张
                # 子表的外键列（如 治疗记录流水号 在医嘱表/用药记录表等都有），
                # 不算歧义；只有同优先级下确实存在"不同概念"候选才拒绝。
                unique = {}
                for rank, rtb, sf, mtype in best:
                    key = (sf.chinese_name, sf.name)
                    unique.setdefault(key, (rank, rtb, sf, mtype))
                if len(unique) == 1:
                    _, rtb, sf, mtype = next(iter(unique.values()))
                elif len(unique) > 1 and best_rank == 4:
                    # 残基匹配歧义：多个表有同概念源字段时，优先选择
                    # 与目标字段语义域最匹配的专用子表。
                    # 如地址源字段同时出现在 PERSON_ADDRESS（地址专用子表）
                    # 和 EMR_INP_ADM（事件表展平字段）时，优先采子表。
                    tf_cn = target_field.chinese_name or ''
                    is_addr = any(tf_cn.startswith(p)
                                  for p in self._AUTO_REL_LOC_PREFIXES)
                    if is_addr:
                        addr_candidates = [v for v in unique.values()
                                           if 'ADDRESS' in v[1].name]
                        if addr_candidates:
                            _, rtb, sf, mtype = addr_candidates[0]
                        else:
                            # 无地址专用子表候选，歧义未解决 -> 不匹配
                            return None
                    else:
                        # 非地址字段的歧义，目前无法解决 -> 不匹配
                        return None
                else:
                    # 非残基歧义（rank 0~3）：优先查找属性子表候选。
                    # 目标字段（如 身份证件类别代码→卡证类型）在事件表中有大量
                    # 同概念展平字段（证件类型），但语义归属是属性子表
                    # （PERSON_IDENTIFICATION.卡证类型），事件表候选虽多但
                    # 方向不成立（P6 外键方向否决）。属性子表候选唯一且命中
                    # 判别器注册时，优先采纳属性子表，避免歧义误杀。
                    attr_cands = [v for v in unique.values()
                                  if v[1].name in self._AUTO_REL_ATTR_TABLE_DISCS]
                    if len(attr_cands) == 1:
                        _, rtb, sf, mtype = attr_cands[0]
                    else:
                        # 歧义无法解决 -> 不匹配
                        return None
                # 属性子表优先（P6 方向兼容）：消歧命中事件/业务子表
                # （方向不成立、下一步将被否决）而候选池存在显式属性子表
                # 候选时，改采属性子表——事件子表（如 病案首页.户籍地址编码）
                # 即使等级更高也会被方向否决，属性子表残基命中 + 判别器
                # 约束（01/03/06）才是语义归属（户籍地-省市代码 ←
                # PERSON_ADDRESS.省编码 + 地址类别代码=01）。
                if (rtb.name not in self._AUTO_REL_ATTR_TABLE_DISCS
                        and getattr(self, '_auto_fk_edges', None)):
                    attr_cands = [
                        c for c in candidates
                        if c[1].name in self._AUTO_REL_ATTR_TABLE_DISCS]
                    if attr_cands:
                        a_rank = min(c[0] for c in attr_cands)
                        a_best = [c for c in attr_cands if c[0] == a_rank]
                        a_unique = {}
                        for a_rank_, atb, asf, amtype in a_best:
                            key = (asf.chinese_name, asf.name)
                            a_unique.setdefault(key,
                                                (a_rank_, atb, asf, amtype))
                        if len(a_unique) == 1:
                            _, rtb, sf, mtype = next(iter(a_unique.values()))
                        elif len(a_unique) > 1:
                            tf_cn = target_field.chinese_name or ''
                            is_addr = any(tf_cn.startswith(p)
                                          for p in self._AUTO_REL_LOC_PREFIXES)
                            if is_addr:
                                addr_c = [v for v in a_unique.values()
                                          if 'ADDRESS' in v[1].name]
                                if addr_c:
                                    _, rtb, sf, mtype = addr_c[0]
                                else:
                                    return None
                            else:
                                return None
                # 外键方向否决（P6 通道）：主表反向借子表字段时，仅允许
                # "判别器属性子表"（地址/卡证/联系方式等 1:N 但按类型代码
                # 取唯一值，如 PERSON_ADDRESS/PERSON_CONTACT/
                # PERSON_IDENTIFICATION），事件/业务子表（转诊记录/就诊
                # 记录/病案首页等）一对多方向不成立，永远否决——与
                # _accept_user_custom 的方向硬约束一致，堵住 P6 绕行口。
                if (rtb.name != source_table.name
                        and getattr(self, '_auto_fk_edges', None)):
                    fk_child_to_parent = {(e[0], e[3])
                                          for e in self._auto_fk_edges}
                    if (rtb.name, source_table.name) in fk_child_to_parent:
                        # 属性子表（PERSON_ADDRESS/PERSON_CONTACT/
                        # PERSON_IDENTIFICATION）的 1:N 方向是语义归属
                        # （按类型代码取唯一值），方向合法，豁免否决。
                        if rtb.name in self._AUTO_REL_ATTR_TABLE_DISCS:
                            pass  # 属性子表方向兼容，跳过否决
                        else:
                            disc = (self._auto_rel_discriminators or {}).get(
                                rtb.name)
                            if not disc:
                                self.user_custom_conflicts.append({
                                    'target_table': (target_table.chinese_name
                                                     or target_table.name),
                                    'target_field': (target_field.chinese_name
                                                     or target_field.name),
                                    'kb_source_field': sf.chinese_name or sf.name,
                                    'kb_source_table': (rtb.chinese_name
                                                        or rtb.name),
                                    'reason': (
                                        'P6 外键方向冲突：主表[{}] 反向借'
                                        '事件子表[{}] 字段，一对多方向不成立'
                                        .format(source_table.chinese_name
                                                or source_table.name,
                                                rtb.chinese_name or rtb.name)),
                                    'action': '已否决，改走常规匹配',
                                })
                                return None
                # P6 意图保护与占用登记（候选消歧成功后执行）
                uc_decl = (self._p6_uc_declared or {}).get(
                    target_table.name, set())
                if ((target_field.chinese_name or target_field.name) in uc_decl
                        and str(mtype).endswith('keyword')):
                    return None
                occ = (self._p6_occupied or {}).get(target_table.name, {})
                claimed_cn = occ.get(sf.chinese_name or sf.name)
                if not (claimed_cn is not None
                        and not self._auto_relation_reuse_allowed(
                            claimed_cn, target_field.chinese_name or '')):
                    used = self._auto_relation_used.setdefault(
                        target_table.name, {})
                    used[(rtb.name, sf.name)] = target_field.chinese_name or ''
                    self.stats[mtype] = self.stats.get(mtype, 0) + 1
                    if str(mtype) == 'auto_relation_residue' and getattr(
                            self, '_p6_discriminator_constraints', None) is not None:
                        dc = self._resolve_discriminator_constraint(
                            target_field.chinese_name or '', rtb,
                            self._auto_rel_discriminators)
                        if dc:
                            self._p6_discriminator_constraints.setdefault(
                                target_table.name, {})[
                                target_field.chinese_name or target_field.name] = dc
                    return (sf, mtype)

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

        # 完全相同的字段名必然是同一概念，直接兼容（避免被下方规则误拒，
        # 这是精确中文匹配不应被过度拒绝的关键）
        if target_cn == source_cn:
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
                # 检查源字段名是否包含粒度信息（含单字粒度：省/市/县/区/乡/镇/街道/村）
                source_granularity_keywords = ['省市', '地市', '区县', '街道',
                                               '省', '市', '县', '区', '乡', '镇', '村', '街道']
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
            # 尾词种类（"号""号码""码"）作为前缀时视为无真正前缀——
            # "电话号码"的 split('电话')→['号','号码']，'号'不是语义前缀。
            _tail_kinds = {'号', '码', '名称', '代码', '编码', '编号', '序号', '标识', '号码', '流水号'}
            if target_prefix in _tail_kinds:
                target_prefix = ''
            if source_prefix in _tail_kinds:
                source_prefix = ''
            # 前缀不同但允许一方无前缀或子串匹配：
            # "电话"匹配"联系电话"、"联系人电话"匹配"联系电话"
            if target_prefix != source_prefix and target_prefix and source_prefix:
                if target_prefix not in source_prefix and source_prefix not in target_prefix:
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

        # 字段种类网关：名称/代码/流水号 等类型不一致不兼容
        if not self._field_kind_compatible(name1, name2):
            return False

        # 复合名主体网关：子表主键不得错配到主表主键
        if not self._composite_subject_compatible(name1, name2):
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
            # 检查类别互斥：放射/影像 与 临床 是不同的诊断来源，
            # 防止 放射与病理诊断符合标识 ≠ 临床与病理诊断符合情况
            ('放射', '临床'), ('影像', '临床'), ('放射', '检验'), ('影像', '检验'),
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

        # 3.1 动作修饰词的"有无"本身即构成冲突：
        # "会诊医师" 是参与会诊的医师，"会诊申请医师" 是发起会诊的医师，二者不同。
        # 仅靠包含关系（会诊 ⊂ 会诊申请）会漏判，故单独检查动作词。
        action_modifiers = ['申请', '执行', '审核', '报告', '开立', '录入', '登记', '复核', '接诊']
        if mod1 is not None and mod2 is not None:
            a1 = {a for a in action_modifiers if a in mod1}
            a2 = {a for a in action_modifiers if a in mod2}
            if a1 != a2:
                return False

        if mod1 and mod2 and mod1 != mod2:
            # 如果修饰词不同且都有意义（长度>=2），则不兼容
            if len(mod1) >= 2 and len(mod2) >= 2:
                # 检查修饰词之间是否是包含关系（如"申请医师" vs "申请医师"）
                if mod1 not in mod2 and mod2 not in mod1:
                    # 额外检查：有些修饰词差异是可接受的（如"责任" vs "主治"）
                    # 但如果完全无关（如"住院" vs "转出"），则不兼容
                    return False

        # 4. 主体冲突：会诊记录 vs 会诊医师
        # 如果一个指向"记录"实体，一个指向"人员"实体，且都包含"会诊"，则不兼容。
        # 注意：必须先判"人员"。"会诊医师流水号"里的"流水号"只是种类词，
        # 主体仍是医师，与"会诊医师标识"是同一数据元；
        # 若按含"流水号"就算记录，会把它误判成与"会诊记录"冲突而漏配。
        if '会诊' in name1 and '会诊' in name2:
            person_kw = ['医师', '医生', '签名', '护士', '专家']
            record_kw = ['记录', '申请单', '报告']
            n1_is_person = any(k in name1 for k in person_kw)
            n2_is_person = any(k in name2 for k in person_kw)
            # 双方主体一致（都是人员）-> 兼容，不再看记录类词
            if not (n1_is_person and n2_is_person):
                n1_is_record = any(k in name1 for k in record_kw) or (
                    not n1_is_person and '流水号' in name1)
                n2_is_record = any(k in name2 for k in record_kw) or (
                    not n2_is_person and '流水号' in name2)
                if (n1_is_record and n2_is_person) or (n1_is_person and n2_is_record):
                    return False

        return True

    # ===== P1：核心概念兼容性网关 =====
    # 通用前缀（实体/机构修饰，去掉后不影响“核心概念”判断）
    _GENERIC_PREFIXES = _CORE_GENERIC_PREFIXES
    # 通用后缀（类型/命名修饰）。注意：'唯一' 不在默认后缀里（比对器行为保持旧版）。
    _GENERIC_SUFFIXES = _CORE_GENERIC_SUFFIXES

    def _strip_generic(self, name: str) -> str:
        """去掉通用前后缀，保留核心概念串（比对器行为：COMPARATOR_PREFIXES，简单顺序剥，
        无 '医疗机构' 前缀、不回退保护——与旧版完全一致）。"""
        return strip_generic(name)

    def _core_concept_compatible(self, name1: str, name2: str) -> bool:
        """判断两个字段名是否指向同一核心概念（拦截同义词/语义的跨概念误匹配）。

        规则（详细说明见 matchers/matching_core.core_compatible）：
        - 去掉通用前后缀后，若核心串完全相同 -> 兼容（如 科室代码 / 科室编码）
        - 若一个核心串是另一个的子串（更具体/更笼统的同义）-> 兼容
          （如 门急诊科室代码 / 门诊科室编码、患者姓名 / 姓名）
        - 一方核心为空、另一方有实质概念 -> 不兼容（如 院区名称 / 姓名）
        - 否则视为不同概念 -> 不兼容
          （如 机构内部药品通用名代码 / 医疗机构代码、检查流水号 / 就诊流水号、
            患者复诊标志 / 患者标识）

        实现：委托 matchers.matching_core.core_compatible，行为 = 比对器旧版
        （不前置归一 + 不额外剥 '唯一'），由匹配核心模块统一维护，self_validator
        通过参数显式声明降噪差异（见其 _core）。
        """
        return core_compatible(name1, name2)

    # 字段"种类"兼容网关：名称/代码/流水号 等类型不一致应判为不兼容，
    # 防止 临床路径流水号≠临床路径名称、科主任代码≠科主任执业证书编码 等跨种类误匹配。
    # 签名类：存的是人名（医师签名/护士签名），语义上属于"名称"族，
    # 与 代码/流水号/标识 互不兼容（医嘱执行医师代码 ≠ 医嘱执行者签名）。
    # "科别/病别"在卫生信息标准中即科室名称（中医病案首页"出院科别"英文名 out_dep_name、
    # 长度 S3100 与"出院科室名称"一致），归入名称族，避免被错配到"出院科室编码"。
    _FIELD_KIND_NAME = {'名称', '名字', '姓名', '简称', '全称', '科别'}
    _FIELD_KIND_CODE = {'代码', '编码', '代号', '码'}
    _FIELD_KIND_SERIAL = {'流水号', '序号', '编号'}
    _FIELD_KIND_IDENT = {'标识', '标志', '唯一标识'}
    # 签名独立成类：签名字段存的是签名图像/签名数据（或签署动作留痕），
    # 与"姓名/名称"这种纯文本标识不是同一数据元
    # （报告医师签名 ≠ 报告医生姓名），更不与代码/标识/流水号等价。
    _FIELD_KIND_SIGN = {'签名', '签章', '签字'}
    _FIELD_KIND_QUAL = {'执业证书', '身份证', '证书', '登记证', '执业证', '注册证'}
    # 地址类：地址文本与名称/代码/标识/流水号是完全不同的数据元
    # （工作单位地址 ≠ 工作单位名称——实测 keyword 曾错配）
    _FIELD_KIND_ADDR = {'地址', '住址'}
    # 人口学/描述性属性：不可能与"流水号/标识"这类主键型字段等价
    # （严重不良事件报告流水号 ≠ 不良事件报告人职业）
    _FIELD_KIND_ATTR = {'职业', '性别', '年龄', '民族', '国籍', '学历',
                        '婚姻状况', '职务', '职称', '籍贯'}

    @staticmethod
    def _field_kind_of(name: str) -> str:
        """从原名字（不剥离通用前后缀）提取尾部类型词。

        注意：先匹配长词，避免 '出院科室代码' 之类同时命中 '代码'/'码' 时结果不稳定。
        """
        kinds = (StandardComparator._FIELD_KIND_NAME | StandardComparator._FIELD_KIND_CODE |
                 StandardComparator._FIELD_KIND_SERIAL | StandardComparator._FIELD_KIND_IDENT |
                 StandardComparator._FIELD_KIND_ATTR | StandardComparator._FIELD_KIND_SIGN |
                 StandardComparator._FIELD_KIND_ADDR)
        for k in sorted(kinds, key=len, reverse=True):
            if name.endswith(k):
                return k
        return ''

    @staticmethod
    def _field_kind_compatible(name1: str, name2: str) -> bool:
        # 证书/证件类限定词只在一侧出现 -> 概念不同（代码 ≠ 执业证书编码）
        # 但"类别/类型"字段（如"身份证件类别代码"）不受此限——"类别"字段
        # 表示的是分类/枚举意义，不是证书原件本身（卡证类型 ≠ 身份证号码）。
        if '类别' not in name1 and '类别' not in name2 and '类型' not in name1 and '类型' not in name2:
            q1 = any(q in name1 for q in StandardComparator._FIELD_KIND_QUAL)
            q2 = any(q in name2 for q in StandardComparator._FIELD_KIND_QUAL)
            if q1 != q2:
                return False

        def _cat(k):
            if k in StandardComparator._FIELD_KIND_NAME:
                return 'NAME'
            if k in StandardComparator._FIELD_KIND_CODE:
                return 'CODE'
            if k in StandardComparator._FIELD_KIND_SERIAL:
                return 'SERIAL'
            if k in StandardComparator._FIELD_KIND_IDENT:
                return 'IDENT'
            if k in StandardComparator._FIELD_KIND_ATTR:
                return 'ATTR'
            if k in StandardComparator._FIELD_KIND_SIGN:
                return 'SIGN'
            if k in StandardComparator._FIELD_KIND_ADDR:
                return 'ADDR'
            return 'OTHER'

        c1, c2 = _cat(StandardComparator._field_kind_of(name1)), _cat(StandardComparator._field_kind_of(name2))
        # 名称 vs 代码/流水号 不兼容
        if 'NAME' in (c1, c2) and ('CODE' in (c1, c2) or 'SERIAL' in (c1, c2)):
            return False
        # 流水号 vs 名称/代码 不兼容
        if 'SERIAL' in (c1, c2) and ('NAME' in (c1, c2) or 'CODE' in (c1, c2)):
            return False
        # 地址 vs 名称/代码/流水号/标识 不兼容：
        # 工作单位地址 ≠ 工作单位名称（实测 keyword 错配）、联系地址 ≠ 联系编码、
        # 户籍地址 ≠ 户籍标识。地址文本与主键/名称型数据元是完全不同的概念。
        if 'ADDR' in (c1, c2) and ('NAME' in (c1, c2) or 'CODE' in (c1, c2)
                                   or 'SERIAL' in (c1, c2) or 'IDENT' in (c1, c2)):
            return False
        # 签名 vs 任何其他种类均不兼容：
        # 报告医师签名 ≠ 报告医生姓名（签名数据 vs 文本姓名）
        # 严重不良事件报告流水号 ≠ 不良事件报告人签名
        if ('SIGN' in (c1, c2)) and c1 != c2:
            return False
        # 描述性属性 vs 流水号/标识 不兼容。
        # 只拦 SERIAL/IDENT，不拦 CODE——因为"性别代码"与"性别"在标准中常指同一数据元，
        # 拦 CODE 会造成漏配。
        if 'ATTR' in (c1, c2) and ('SERIAL' in (c1, c2) or 'IDENT' in (c1, c2)):
            return False
        return True

    # 复合字段名（"主表-子表xxx"）的语义主体取最后一段：
    # "手术记录-麻醉用药记录唯一标识" 的主体是"麻醉用药记录"，不是"手术记录"。
    @staticmethod
    def _composite_subject(name: str) -> str:
        s = name or ''
        for sep in ('-', '－', '—'):
            if sep in s:
                s = s.split(sep)[-1]
        return s.strip()

    def _composite_subject_compatible(self, name1: str, name2: str) -> bool:
        """复合名主体兼容性：仅在至少一侧是复合名时生效。

        防止子表主键被错配到主表主键：
        - 手术记录-麻醉用药记录唯一标识 ≠ 手术唯一标识
        - 手术记录-麻醉唯一标识 ≠ 手术唯一标识

        注意：地址/卡类型前缀字段（常住地-省市代码）的 "-" 是"前缀-残基"分隔符，
        不是"主表-子表"复合名模式，跳过兼容性检查。
        """
        has_sep = any(sep in (name1 or '') or sep in (name2 or '')
                      for sep in ('-', '－', '—'))
        if not has_sep:
            return True
        # 地址/卡类型前缀字段的 "-" 不是主表-子表复合名模式
        prefix_patterns = (StandardComparator._AUTO_REL_LOC_PREFIXES +
                           StandardComparator._AUTO_REL_CARD_PREFIXES)
        for n in (name1, name2):
            if n and any(n.startswith(p) for p in prefix_patterns):
                return True
        c1 = self._strip_generic(self._composite_subject(name1))
        c2 = self._strip_generic(self._composite_subject(name2))
        if not c1 or not c2:
            return True
        return c1 == c2 or c1 in c2 or c2 in c1

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

        # 显式同义词字典映射 > 核心概念网关：如果 field_synonyms.yaml 中显式声明了
        # 这对映射（如 个人基本信息标识号↔患者唯一标识），则跳过核心概念检查。
        # 核心概念网关的 _strip_generic 会剥离通用前后缀，可能把"个人基本信息标识号"
        # 剥离为"个人基本信息号"、"患者唯一标识"剥离为"唯一"——两者完全不同，
        # 但显式同义词映射是人工确认的等价关系，不应被通用剥离逻辑否决。
        synonyms = self.synonyms
        if self._in_explicit_synonym_dict(name1, name2, synonyms):
            pass  # 跳过核心概念网关
        elif not self._core_concept_compatible(name1, name2):
            return False

        # 字段种类网关：名称/代码/流水号 等类型不一致不兼容。
        # 显式同义词字典声明（如 身份证件号码↔证件号码）是人工确认的等价关系，
        # 与核心概念网关同理豁免种类网关——否则"身份证"会被 _FIELD_KIND_QUAL
        # 当限定词否决，人工确认的同义对依然被拦（实测：身份证件号码↔证件号码
        # 已在字典中但被种类网关拒绝）。
        if not self._in_explicit_synonym_dict(name1, name2, synonyms):
            if not self._field_kind_compatible(name1, name2):
                return False

        # 复合名主体网关：子表主键不得错配到主表主键
        if not self._composite_subject_compatible(name1, name2):
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

    def _in_explicit_synonym_dict(self, name1: str, name2: str,
                                  synonyms: dict) -> bool:
        """检查 name1↔name2 是否在显式同义词字典中声明。

        实现：委托 matchers.matching_core.in_explicit_synonym_dict（唯一事实来源）。
        只检查全名精确匹配 + value 子串命中，与 self_validator._is_explicit_synonym
        保持一致（禁止漂移）。
        """
        return in_explicit_synonym_dict(name1, name2, synonyms)

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
        # 大小写归一化后相等也视为同概念（RH 血型代码 vs Rh血型代码），
        # 与核心概念网关的归一化保持一致，避免 core 判定兼容而语义通道
        # 却因相似度阈值不足拒绝的矛盾。
        if name1_clean.lower() == name2_clean.lower():
            return True

        # 核心概念网关：语义相似但概念不同（如 检查vs就诊、药品vs医疗）不应匹配
        if not self._core_concept_compatible(name1, name2):
            return False

        # 字段种类网关：名称/代码/流水号 等类型不一致不兼容
        if not self._field_kind_compatible(name1, name2):
            return False

        # 复合名主体网关：子表主键不得错配到主表主键
        if not self._composite_subject_compatible(name1, name2):
            return False

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
