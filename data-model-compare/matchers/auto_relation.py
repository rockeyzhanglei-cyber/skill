#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P6 自动关联（多表关联通道）判定（P1-2 第二刀，拆分自 standard_comparator.py）

P6 通道语义：目标字段在当前对齐源表的所有常规通道都失败后，沿外键（FK）关联图
搜索关联子表，是判为 new_field 之前的最后一环。本模块收录该通道用到的
**零状态**辅助判定。

拆分依据（AST 分析确认）：
- 6 个函数全部不读写 StandardComparator 的实例状态（原为 classmethod / staticmethod）
- **不引用任何类常量**（第一刀踩过的坑：AST 只扫 self.xxx 会漏掉 ClassName.xxx）
- 组内互不调用；组外仅依赖随函数迁移的嵌套函数（_core / _paren）
- 嵌套辅助函数（_core / _paren）随各自函数一并迁移

原类 StandardComparator 保留**同名薄委托**（classmethod 仍为 classmethod），
调用方 `self._xxx(...)` 无需改动。

⚠️ 维护约定：保持无状态。需要 comparator 配置（如判别器表 auto_rel_discriminators）
时通过参数传入，不要反过去 import 主类（会循环依赖，且判定结果难以复现）。
"""

# ============================================================================
# P6 通道级常量（P1-2 第二刀，从 StandardComparator 下沉至此，单一事实来源）
#
# 说明：原类以 `_XXX = auto_relation.XXX` 别名引用，故 cls._XXX / self._XXX 的
#      既有用法均不受影响。这些同义关系只在"沿关联图搜索子表"通道内生效，
#      不污染全局匹配。
# ============================================================================

# ===== P6 自动外键关联通道：通道级专有同义词与复用判定 =====
# 源标准用"子表 + 类型代码"存多类数据（地址类别代码、卡证类型），目标省平台
# 把同一概念拆成多列（卡类型代码/卡号/社保卡号、出生地/户籍地/居住地-详细地址）。
# 这些同义关系只在"沿关联图搜索子表"这一通道内生效，不污染全局匹配。
AUTO_REL_SYNONYMS = {
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
AUTO_REL_LOC_PREFIXES = ['出生地', '户籍地', '居住地', '现住地', '常住地',
                          '工作地', '单位', '家庭', '联系人']
AUTO_REL_CARD_PREFIXES = ['居民健康卡', '社保', '医保', '就诊', '健康卡', '银行卡']
AUTO_REL_TAIL_KINDS = ['唯一标识', '流水号', '代码', '编码', '代号', '编号',
                        '序号', '标识', '标志', '名称', '号码']

# ===== 值域驱动匹配（P6v）：残基→层级关键词映射 =====
# 残基中出现的复合词（如"省市"）应映射到哪组层级关键词。
# 单独的"省"或"市"字在行政区划层级关键词集中已存在，
# 但"省市"作为复合词，预期匹配的是"省/自治区/直辖市"级别，
# 不应匹配"市/地区/州"级别。
AUTO_REL_RESIDUE_MAP = {
    '省市': {'省', '自治区', '直辖市'},
    '地市': {'市', '地区', '州'},
    '区县': {'县'},  # 不含"区"单字，避免误配"入院病区编码"等含"区"的非地址字段
    '乡镇': {'乡', '镇', '街道'},
    '街道': {'乡', '镇', '街道', '街道办事处'},
    '邮政编码': {'邮政编码', '邮编'},
    '详细地址': {'详细地址', '地址', '住址'},
    '门牌': {'门牌'},
}
AUTO_REL_ADDR_LEVEL_KEYWORDS = {
    '省', '自治区', '直辖市', '市', '地区', '州', '县', '区',
    '乡', '镇', '街道', '村', '街', '路', '弄', '门牌', '邮政编码',
    '详细地址',
}

# 值域驱动匹配：地址前缀→判别器代码（源标准地址类别代码表 CV02.01.205）
# 残基匹配命中后，从该映射查找判别器代码，记录到 match 结果供数据上传使用。
AUTO_REL_DISCRIMINATOR_MAP = {
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
# 值：(字段英文名, 注册用判别器中文名——与 AUTO_REL_DISCRIMINATOR_MAP
# 键对齐，保证 _resolve_discriminator_constraint 能解析出判别码)。
# 不用自动检测（"类别代码/类型代码 + 值域"）识别：源标准 value_domains
# 常未解析（全空），且事件子表（OUTP_ENCOUNTER.就诊类型代码、
# MAHP_MAIN.身份证类别代码等）同样含类型代码字段，自动检测会误判放行。
AUTO_REL_ATTR_TABLE_DISCS = {
    'PERSON_ADDRESS': ('ADDRESS_TYPE_CODE', '地址类别代码'),
    'PERSON_CONTACT': ('CONT_TYPE_CODE', '联系方式类别代码'),
    'PERSON_IDENTIFICATION': ('IDCARD_TYPE_CODE', '卡证类型代码'),
}

# 排除类限定词：目标字段以"其他/其它/其余"限定时，表示"排除特定类别后的
# 其余项"，与源字段的特定类别（如 初步诊断、西医诊断编码）语义冲突，
# keyword 层不应跨限定词匹配（其他西医诊断代码 ✗ 初步诊断--西医诊断编码）。
EXCLUSION_QUALIFIERS = ('其他', '其它', '其余', '另')


def residue_match(target_cn: str, source_cn: str) -> bool:
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
    for p in AUTO_REL_LOC_PREFIXES + AUTO_REL_CARD_PREFIXES:
        if target_stripped.startswith(p):
            target_stripped = target_stripped[len(p):]
            has_prefix = True
            break

    if not has_prefix:
        return False

    # 2. 剥离尾词种类
    for k in sorted(AUTO_REL_TAIL_KINDS, key=len, reverse=True):
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
    residue_kws = AUTO_REL_RESIDUE_MAP.get(target_stripped, set())
    if not residue_kws:
        # 未命中复合词映射，从 _AUTO_REL_ADDR_LEVEL_KEYWORDS 中提取子串
        residue_kws = {k for k in AUTO_REL_ADDR_LEVEL_KEYWORDS if k in target_stripped}
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

def resolve_discriminator_constraint(target_cn: str, rel_table: 'StandardTable',
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
    for p in AUTO_REL_LOC_PREFIXES + AUTO_REL_CARD_PREFIXES:
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
        disc_map = AUTO_REL_DISCRIMINATOR_MAP.get(disc_cn, {})
        if prefix in disc_map:
            result[disc_cn] = disc_map[prefix]
    return result

def exclusion_qualifier_conflict(cn: str, s_cn: str) -> bool:
    """排除类限定词冲突：目标含"其他/其它/其余"而源不含 -> True（应拒绝）。

    只在低置信 keyword 兜底层生效：目标字段声明了"排除特定类别"的语义，
    源字段是某一特定类别，二者不构成同概念。
    """
    if not cn or not s_cn:
        return False
    t_has = any(q in cn for q in EXCLUSION_QUALIFIERS)
    s_has = any(q in s_cn for q in EXCLUSION_QUALIFIERS)
    return t_has and not s_has

def channel_synonym_hit(name1: str, name2: str) -> bool:
    """通道级专有同义映射命中判定（不套用通用核心概念闸门）。

    classmethod：供 self_validator 复用以豁免人工确认的同义对
    （社保卡号↔卡证号码 等）的核心概念误报，避免两处规则漂移。
    """
    if not name1 or not name2:
        return False
    for w1, syns in AUTO_REL_SYNONYMS.items():
        for n1, n2 in ((name1, name2), (name2, name1)):
            if w1 in n1:
                for syn in syns:
                    if syn in n2:
                        r1 = n1.replace(w1, '').strip()
                        r2 = n2.replace(syn, '').strip()
                        if r1 == r2 or not r1 or not r2 or r1 in r2 or r2 in r1:
                            return True
    return False

def reuse_allowed(prev_cn: str, new_cn: str) -> bool:
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
        for p in AUTO_REL_LOC_PREFIXES + AUTO_REL_CARD_PREFIXES:
            if s.startswith(p):
                s = s[len(p):]
                break
        for k in sorted(AUTO_REL_TAIL_KINDS, key=len, reverse=True):
            if s.endswith(k) and len(s) > len(k):
                s = s[:-len(k)]
                break
        return s.strip(' -－—·、')

    c1, c2 = _core(prev_cn), _core(new_cn)
    return bool(c1 and c2 and c1 == c2)

def paren_content_compatible(cn: str, s_cn: str) -> bool:
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
