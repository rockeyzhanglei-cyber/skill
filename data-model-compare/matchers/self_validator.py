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

# 通用前后缀（与 standard_comparator._core_concept_compatible 保持一致）
_GENERIC_PREFIXES = ['机构内部', '医疗机构', '门急诊', '门诊', '住院', '急诊', '患者', '医院',
                     '卫生', '区域', '标准', '记录', '信息', '数据']
_GENERIC_SUFFIXES = ['代码', '编码', '代号', '编号', '名称', '名字', '姓名',
                     '标识', '标志', '类型', '类别', '种类', '流水号', '英文名', '英文',
                     '唯一']

# 过于通用的字段名，不应作为漏配/误匹配判据
_AMBIGUOUS = {'姓名', '名称', '性别', '日期', '时间', '标志', '标识', '状态', '类型', '备注', '说明'}

# 明显同义的字符对（用于误匹配判据的归一化，减少"医师/医生"类误报）
# 均为已人工复核确认的等价表述，登记在此只影响"疑误配"告警的降噪，
# 不参与实际匹配决策（匹配仍由 standard_comparator 的网关把关）。
_NORMALIZE_MAP = {
    '医师': '医生', '医生': '医生', '大夫': '医生',
    # 动作角色的"者"即对应人员："医嘱执行者" = "医嘱执行医师"
    '执行者': '执行医生', '申请者': '申请医生', '报告者': '报告医生',
    '开立者': '开立医生', '审核者': '审核医生', '录入者': '录入医生',
    # 卫生信息标准中"科别"即科室名称（中医病案首页 out_dep_name）
    '科别': '科室',
    # "报告单"与"报告"在标识类字段中指同一实体
    '报告单': '报告',
    # 中医"辩证/辨证"异形词归一（其中:中医辩证论治会诊费 ↔ 中医辨证论治会诊费）
    '辩证': '辨证',
    # 词序变体：就诊结束 ↔ 结束就诊（语义相同）
    '结束就诊': '就诊结束',
    # "治疗处理意见" = "治疗意见"（处理为冗余修饰）
    '治疗处理': '治疗',
    # "是否是" ↔ "是否"（是否主要手术或操作 ↔ 是否是主要手术）
    '是否是': '是否',
    # "药品" ↔ "药物"（机构内部麻醉药品名称 ↔ 麻醉药物名称）
    '药品': '药物',
    # 地址族字段前缀归一：出生地/居住地 均复用源标准 ADDRESS 地址子表层级
    '出生地-': '地址-', '居住地-': '地址-',
    # 申请单类型修饰归一：手术申请单编号 ↔ 电子申请单编号（同实体）
    '手术申请单': '申请单', '电子申请单': '申请单',
    # 长描述归一：手术后可能出现的意外及并发症 = 手术并发症（并发症标志）
    '手术后可能出现的意外及并发症': '手术并发症',
    # "其中:"是费用构成类字段的引导词，删除不改变字段语义
    # （其中:中药制剂费 ↔ 其中：医疗机构中药制剂费）
    '其中': '',
}

# 纯噪音字符：标点与结构助词，去掉不改变字段语义
# 损伤、中毒的外部原因代码 == 损伤中毒外部原因编码
# 半角/全角冒号（其中:中医外治 ↔ 其中：中医外治费）均属噪音
_NOISE_CHARS = '、，,；;／/·　 的已:：'


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


def _is_explicit_synonym(name1: str, name2: str, synonyms: dict) -> bool:
    """name1/name2 是否在 field_synonyms.yaml 中显式声明为同义对（双向）。

    子串匹配与 standard_comparator._in_explicit_synonym_dict 保持一致（避免两处
    规则漂移）：身份证件号码 与 证件号码 通过 证件号码 的 value「身份证」是
    「身份证件号码」的子串而命中。
    """
    if not synonyms or not name1 or not name2:
        return False
    if name1 in synonyms:
        for syn in synonyms.get(name1, ()):
            if syn in name2 or name2 in syn:
                return True
    if name2 in synonyms:
        for syn in synonyms.get(name2, ()):
            if syn in name1 or name1 in syn:
                return True
    return False


def _norm_concept(name: str) -> str:
    """误匹配判据前的归一化：去掉括号说明、噪音字符、同义字符替换。"""
    import re
    s = name or ''
    # 去掉括号及内部说明，如 "入院病情(对应其他诊断1)"
    s = re.sub(r'[（(][^）)]*[）)]', '', s)
    for k, v in _NORMALIZE_MAP.items():
        s = s.replace(k, v)
    for ch in _NOISE_CHARS:
        s = s.replace(ch, '')
    return s


def _strip_generic(name: str) -> str:
    s = name or ''
    for p in _GENERIC_PREFIXES:
        if s.startswith(p):
            stripped = s[len(p):]
            # 剥前缀后若只剩后缀词（或为空），前缀很可能是字段核心词的一部分
            # （医疗机构代码 → 代码），回退该前缀，避免把核心概念剥空导致
            # 转入医疗机构代码 vs 医疗机构代码 这类同概念字段被误判。
            if stripped and all(ch in ''.join(_GENERIC_SUFFIXES) for ch in stripped):
                continue
            s = stripped
    for suf in _GENERIC_SUFFIXES:
        s = s.replace(suf, '')
    return s.strip()


def _core(name1: str, name2: str) -> bool:
    if not name1 or not name2:
        return True
    c1 = _strip_generic(_norm_concept(name1))
    c2 = _strip_generic(_norm_concept(name2))
    if not c1 and not c2:
        return True
    if not c1 or not c2:
        return False
    # 归一化后再比：去空格 + 统一小写（与 standard_comparator._core_concept_compatible
    # 的 B 修复同步）。RH 血型 vs Rh血型、ABO 血型 vs ABO血型 等纯大小写/空格
    # 差异属同一概念，不应被自验证标为"核心概念不一致"。
    n1 = re.sub(r'\s+', '', c1).lower()
    n2 = re.sub(r'\s+', '', c2).lower()
    if n1 == n2 or n1 in n2 or n2 in n1:
        return True
    return False


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
