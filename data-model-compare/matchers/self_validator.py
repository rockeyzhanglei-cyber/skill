# -*- coding: utf-8 -*-
"""
自验证模块（P3）

在不依赖人工的前提下，对 compare_result.json 做一轮"质量体检"：
- 漏配检测（leak）：本应匹配却落入新增字段的——例如目标字段中文名与
  某个源字段中文名完全一致（或核心概念一致），却被判为新增。
- 误匹配检测（suspect）：模糊匹配（同义词/语义/关键词）命中的字段，
  若核心概念不一致，疑似误匹配，需人工复核。
- 产出 KB 修复建议：漏配 -> 建议补充一条字段映射；误匹配 -> 建议人工复核。

输出结构化 JSON，供报告与"人工确认"流程直接消费。
"""

import os
import re

# 规则核心模块（唯一事实来源）：核心概念/显式同义判定与词表统一来自 matching_core。
# 自验证器为"体检降噪侧"，与比对器相比显式声明两处差异：
#   1) 额外剥 '唯一' 后缀（extra_suffix=('唯一',)）
#   2) 前置归一化（normalize_concept：医师→医生、去括号等；仅影响疑误配告警降噪，
#      不参与实际匹配决策——匹配仍由 standard_comparator 的网关把关）
try:
    from .matching_core import (core_compatible, in_explicit_synonym_dict,
                                normalize_concept, strip_generic, VALIDATOR_PREFIXES)
except ImportError:
    try:
        from matchers.matching_core import (core_compatible, in_explicit_synonym_dict,
                                            normalize_concept, strip_generic,
                                            VALIDATOR_PREFIXES)
    except ImportError:
        from matching_core import (core_compatible, in_explicit_synonym_dict,
                                   normalize_concept, strip_generic, VALIDATOR_PREFIXES)

# 兼容入口（薄封装，词表/逻辑在 matching_core，禁止再改这里）
def _norm_concept(name: str) -> str:
    """误匹配判据前的归一化（降噪侧专用）。"""
    return normalize_concept(name)

def _strip_generic(name: str) -> str:
    """去掉通用前后缀（自验证器旧行为：VALIDATOR_PREFIXES 含 '医疗机构'，带前缀回退
    保护 + 额外剥 '唯一'）。"""
    return strip_generic(name, extra_suffix=('唯一',), protect=True,
                         prefixes=VALIDATOR_PREFIXES)

def _core(name1: str, name2: str) -> bool:
    """核心概念判定（自验证器降噪侧：前置归一 + '医疗机构' 前缀 + 额外剥 '唯一'）。"""
    return core_compatible(name1, name2, extra_suffix=('唯一',), norm=normalize_concept,
                           prefixes=VALIDATOR_PREFIXES)

def _is_explicit_synonym(name1: str, name2: str, synonyms: dict) -> bool:
    """name1/name2 是否在 field_synonyms.yaml 中显式声明为同义对（双向子串匹配）。"""
    return in_explicit_synonym_dict(name1, name2, synonyms)

# (词表已迁移至 matchers/matching_core.py，此处不再重复定义)

# 过于通用的字段名，不应作为漏配/误匹配判据
_AMBIGUOUS = {'姓名', '名称', '性别', '日期', '时间', '标志', '标识', '状态', '类型', '备注', '说明'}




# ===== field_synonyms.yaml 人工确认同义豁免（供误匹配体检降噪） =====
# 复用与 standard_comparator 完全一致的双向同义词字典。命中该字典的同义对
# （如 业务数据产生日期时间↔创建日期时间、个人基本信息标识号↔患者标识）属于
# 人工确认的同义关系，通用核心概念检查不应将其标记为 suspect。
_SYNONYMS_CACHE = None


def _load_field_synonyms() -> dict:
    """从 field_synonyms.yaml 加载双向同义词字典（与 standard_comparator 一致）。"""
    global _SYNONYMS_CACHE
    if _SYNONYMS_CACHE is not None:
        return _SYNONYMS_CACHE
    synonyms: dict = {}
    base = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(base, '..', 'knowledge_base', 'field_synonyms.yaml'),
        os.path.join(base, '..', '..', 'knowledge_base', 'field_synonyms.yaml'),
        os.path.expanduser('~/.workbuddy/skills/data-model-compare/knowledge_base/field_synonyms.yaml'),
        os.path.expanduser('~/.cache/WinCode/skill/data-model-compare/knowledge_base/field_synonyms.yaml'),
    ]
    path = None
    for c in candidates:
        if os.path.exists(c):
            path = os.path.abspath(c)
            break
    if path:
        try:
            import yaml
            with open(path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
            field_synonyms = data.get('field_synonyms', {}) or {}
            for cn_name, info in field_synonyms.items():
                if isinstance(info, dict) and 'synonyms' in info:
                    syn_list = list(info['synonyms'])
                    synonyms.setdefault(cn_name, [])
                    for s in syn_list:
                        if s not in synonyms[cn_name]:
                            synonyms[cn_name].append(s)
                        synonyms.setdefault(s, [])
                        if cn_name not in synonyms[s]:
                            synonyms[s].append(cn_name)
        except Exception:
            synonyms = {}
    _SYNONYMS_CACHE = synonyms
    return synonyms


def _build_source_cn_index(source_standard: dict):
    """构建 源字段中文名 -> [(table, field, cn, name)] 索引。"""
    idx = {}
    for t in source_standard.get('tables', []):
        t_cn = t.get('chinese_name') or t.get('name')
        t_en = t.get('name') or t.get('chinese_name')
        for f in t.get('fields', []):
            cn = f.get('chinese_name') or f.get('field_chinese_name')
            en = f.get('field_name') or f.get('name')
            if cn:
                idx.setdefault(cn, []).append((t_cn, t_en, cn, en))
    return idx


def self_validate(compare_result: dict, source_standard: dict, target_standard: dict,
                  synonyms=None) -> dict:
    """对一次比对结果做质量体检。"""
    leaks = []
    suspects = []

    # 人工确认同义豁免所需的双向同义词字典（默认从 field_synonyms.yaml 加载）
    if synonyms is None:
        synonyms = _load_field_synonyms()

    # 源字段中文名索引（用于漏配检测）
    src_cn_idx = _build_source_cn_index(source_standard)

    # 1) 漏配检测：新增字段中，目标中文名能在源标准里找到同名（且非歧义）字段
    # 排除"整表新增"的表：这些表在源标准中无对应表，其字段判为新增是正确的，不算漏配。
    new_table_names = {nt.get('table_name') for nt in compare_result.get('new_tables', [])}
    for nf in compare_result.get('new_fields', []):
        # nf 的表名：new_fields 用 table_name，也可能用 new_field_target
        nf_table = nf.get('table_name') or nf.get('new_field_target')
        if nf_table in new_table_names:
            continue
        t_cn = nf.get('chinese_name') or nf.get('name')
        if not t_cn or t_cn in _AMBIGUOUS:
            continue
        cands = src_cn_idx.get(t_cn)
        if cands:
            # 仅当核心概念一致（同名即一致）时记为漏配
            leaks.append({
                'table': nf.get('table_name'),
                'field': nf.get('name'),
                'chinese_name': t_cn,
                'suggested_source': [{'table': c[0], 'field': c[3], 'cn': c[2]} for c in cands],
                'reason': f'目标字段中文名「{t_cn}」在源标准中存在同名/同义字段，但被判为新增',
                'kb_suggestion': f"为字段「{nf.get('table_name')}.{t_cn}」补充源映射："
                                f"{cands[0][0]}.{cands[0][3]}",
            })

    # 2) 误匹配检测：模糊匹配命中的字段，核心概念 + 字段种类是否一致
    # 注意：cross_table / cross_table_fuzzy 也必须纳入体检范围，
    # 否则跨表兜底引入的误配不会被发现，准确率会虚高。
    fuzzy_types = {'synonym', 'semantic', 'keyword',
                   'synonym_modified', 'semantic_modified', 'keyword_modified',
                   'cross_table_fuzzy', 'cross_table_fuzzy_modified'}

    def _is_fuzzy(mt: str) -> bool:
        if mt in fuzzy_types:
            return True
        # cross_table(1hop) / cross_table(2hop) 之类带跳数后缀
        if mt.startswith('cross_table'):
            return True
        # 自动外键关联通道（P6）：auto_relation* 同样纳入体检，
        # 防止跨表/关联子表兜底引入的误配逃过自验证
        return mt.startswith('auto_relation')

    # 字段种类网关复用 comparator 的实现，避免两处规则漂移
    try:
        from .standard_comparator import StandardComparator as _SC
        _kind_ok = _SC._field_kind_compatible
        _channel_hit = _SC._auto_rel_channel_synonym_hit
    except Exception:
        _kind_ok = None
        _channel_hit = None

    # matched 用 target_chinese_name/target_field；modified 用 field_chinese_name/field_name
    for item in list(compare_result.get('matched', [])) + list(compare_result.get('modified', [])):
        mt = item.get('match_type', '')
        if not _is_fuzzy(mt):
            continue
        t_cn = (item.get('target_chinese_name')
                or item.get('field_chinese_name')
                or item.get('chinese_name'))
        s_cn = item.get('source_field_chinese_name') or item.get('source_field')
        if not t_cn or not s_cn:
            continue

        reason = None
        if not _core(t_cn, s_cn):
            # 通道级专有同义映射豁免（P6）：社保卡号↔卡证号码、卡号↔卡证号码
            # 等是人工确认的同义关系，核心词差异（卡 vs 卡证）不代表误配，
            # 不应被通用核心概念检查标记为 suspect。
            if (_channel_hit is not None and mt.startswith('auto_relation')
                    and _channel_hit(t_cn, s_cn)):
                continue
            # 人工确认同义豁免（field_synonyms.yaml）：业务数据产生/更新日期时间↔创建/修改
            # 日期时间、个人基本信息标识号↔患者标识 等已在知识库显式声明为同义对，
            # 核心概念差异不代表误配，不应标记为 suspect。
            if _is_explicit_synonym(t_cn, s_cn, synonyms):
                continue
            reason = f'模糊匹配「{t_cn}」→「{s_cn}」核心概念不一致，疑似误匹配'
        elif _kind_ok is not None and not _kind_ok(t_cn, s_cn):
            # 核心概念一致但字段种类冲突：主治医师代码 vs 主治医师姓名
            # 显式同义词字典声明（如 身份证件号码↔证件号码）是人工确认的等价
            # 关系，与 standard_comparator._is_synonym_match 的 A 修复保持一致，
            # 豁免种类网关——否则"身份证"被 _FIELD_KIND_QUAL 当限定词否决，
            # 人工确认的同义对依然被标为种类冲突。
            if _is_explicit_synonym(t_cn, s_cn, synonyms):
                continue
            reason = f'模糊匹配「{t_cn}」→「{s_cn}」核心概念一致但字段种类冲突（代码/名称/标识/签名不可混用）'

        if reason:
            suspects.append({
                'table': item.get('table_name'),
                'target_field': item.get('target_field') or item.get('field_name'),
                'target_cn': t_cn,
                'source_field': item.get('source_field'),
                'source_cn': s_cn,
                'match_type': mt,
                'reason': reason,
                'action': '建议人工复核；若确认错误，在 Excel 中修改为正确源字段',
            })

    return {
        'summary': {
            'leak_count': len(leaks),
            'suspect_count': len(suspects),
        },
        'leaks': leaks,
        'suspects': suspects,
    }
