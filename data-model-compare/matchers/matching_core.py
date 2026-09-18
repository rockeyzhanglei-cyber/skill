# -*- coding: utf-8 -*-
"""
匹配规则核心模块（规则单一事实来源）

背景
----
此前"核心概念判定 / 显式同义判定"在 standard_comparator.py 与 self_validator.py
各有一份实现，词表与归一化步骤存在细微漂移（如 '唯一' 后缀、'_norm_concept'
前置归一化），同一规则两个事实来源，任一侧改动都会造成行为分叉。

本模块把两处共用的判定骨架与权威词表收敛为一处，行为差异改为**显式参数**：

- standard_comparator._core_concept_compatible
    core_compatible(name1, name2)
    = 不前置归一 + 不带 extra_suffix（行为与旧版完全一致）

- self_validator._core
    core_compatible(name1, name2, extra_suffix=('唯一',), norm=normalize_concept)
    = 前置归一（医师→医生、去括号等降噪）+ 额外剥 '唯一'（行为与旧版完全一致）

差异是**显式声明**的（带注释说明为什么降噪侧要多剥），不再是暗地里两套实现。
"""

import re

# ===== 通用前后缀（权威词表，两处共用） =====
# 注意：比对器（匹配决策侧）与自验证器（体检降噪侧）的历史词表**并不完全相同**：
# 自验证器额外包含 '医疗机构' 前缀（降噪更激进）。此差异经实测确认（医疗机构名称~
# 转入医疗机构代码、医疗机构代码~机构代码 等对在两侧判定不同），必须显式保留，
# 否则合并词表会改变已沉淀的匹配结果。
COMPARATOR_PREFIXES = ['机构内部', '门急诊', '门诊', '住院', '急诊', '患者', '医院',
                       '卫生', '区域', '标准', '记录', '信息', '数据']
VALIDATOR_PREFIXES = COMPARATOR_PREFIXES + ['医疗机构']

# 注意：'唯一' 不在默认后缀里（比对器旧行为即如此）。
# 自验证器（体检降噪侧）需要额外剥 '唯一'（见 core_compatible 的 extra_suffix 参数）。
GENERIC_SUFFIXES = ['代码', '编码', '代号', '编号', '名称', '名字', '姓名',
                    '标识', '标志', '类型', '类别', '种类', '流水号', '英文名', '英文']

# ===== 归一化（仅自验证器使用：误匹配判据降噪） =====
# 明显同义的字符对（用于误匹配判据的归一化，减少"医师/医生"类误报）
# 均为已人工复核确认的等价表述，登记在此只影响"疑误配"告警的降噪，
# 不参与实际匹配决策（匹配仍由 standard_comparator 的网关把关）。
NORMALIZE_MAP = {
    '医师': '医生', '医生': '医生', '大夫': '医生',
    # 动作角色的"者"即对应人员："医嘱执行者" = "医嘱执行医师"
    '执行者': '执行医生', '申请者': '申请医生', '报告者': '报告医生',
    '开立者': '开立医生', '审核者': '审核医生', '录入者': '录入医生',
    # 卫生信息标准中"科别"即科室名称（中医病案首页 out_dep_name）
    '科别': '科室',
    # "报告单"与"报告"在标识类字段中指同一实体
    '报告单': '报告',
    # "唯一标识"即"标识"：检验报告唯一标识 = 检验报告标识（同字段不同尾词写法）。
    # 归一后可由"主题词网关"的空残基规则放行（报告单编号 vs 报告唯一标识 同一报告ID），
    # 避免把同义标识符误判为不同主题。
    '唯一标识': '标识',
    # "内码"即"标识"：主键/记录唯一标识的同义写法。山东标准普遍用"内码"(如 内码[ID]、
    # 住院就诊记录内码) 作表主键，V6.0 区域平台用"XX唯一标识"/"系统编码"作主键。
    # 归一后 内码 ≡ 标识 ≡ 唯一标识，使 XX内码 ↔ XX唯一标识 在 keyword 通道命中
    # （住院就诊记录内码 ↔ 住院就诊记录唯一标识）。裸"内码"归一为空残基，由
    # _is_keyword_match 的空残基早退(行3703)拦截，不会串配 患者标识 等空残基字段。
    '内码': '标识',
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
NOISE_CHARS = '、，,；;／/·　 的已:：'


# ===== 字形归一化（v2.0.3）：匹配侧与体检侧共用的最底层归一 =====
# 背景：目标/源标准对同一数据元存在三类"写法级"差异——
#   1) 全角/半角混写    产后宫底高度（cm） vs 产后宫底高度(cm)、地址-省（自治区、直辖市） vs (...)
#   2) 异体字           査(U+67FB) vs 查(U+67E5)（CT检査结果 vs CT检查结果，山东实测 6 组字段因此漏配）
#   3) 异形词           适应证 vs 适应症（药理学规范写法 vs 习惯写法）、结论 vs 结果
# 后果是双重的：exact 通道漏配（该中不失）→ 跌落到 keyword/n-gram 通道误配到别的字段。
# 在字形层统一归一，让最高优先级的 exact 通道回收这些字段，是全局收益最大的单点。
#
# 维护约定：本层只收录"无歧义的等价写法"。拿不准的等价关系（如 结果/信息）
# 一律不收，交给上层网关与知识库判断。

# 1) 全角 ASCII 区（U+FF01–U+FF5E）与全角空格 → 半角。显式区段转换而非
#    unicodedata.NFKC：NFKC 会连带转换 ㎎/㎡/① 等非 ASCII 全角字符，过于激进。
def _build_fullwidth_table() -> dict:
    tbl = {0x3000: 0x20}  # 全角空格
    for cp in range(0xFF01, 0xFF5F):
        tbl[cp] = cp - 0xFEE0
    return tbl

_FULLWIDTH_TABLE = _build_fullwidth_table()

# 2) 异体字：纯字形差异，读音字义完全相同，可放心整字替换。数据驱动，可扩充。
VARIANT_GLYPHS = {
    '査': '查',   # U+67FB 异体 → U+67E5 常用（CT检査结果 vs CT检查结果）
}

# 3) 异形词：人工确认的等价写法，词级整词替换（顺序：长词优先由调用方保证——
#    normalize_glyphs 内部按键长降序应用）。只收医学/标准语境下无歧义的对。
VARIANT_WORDS = {
    '适应证': '适应症',   # 药理学规范写法 = 习惯写法（麻醉适应证 ↔ 麻醉适应症）
    '禁忌证': '禁忌症',   # 同上（禁忌证 ↔ 禁忌症）
    '结论': '结果',       # 总检结论 = 总检结果、会诊结论 = 会诊结果
}


def normalize_glyphs(name: str) -> str:
    """字形层归一化：全角→半角 + 异体字 + 异形词。

    幂等（可重复调用）；位于所有语义判断之前的最底层，匹配决策侧
    （exact/keyword/semantic/synonym/core_compatible）与体检降噪侧
    （normalize_concept）共用，禁止在调用方再做一份平行实现。
    """
    s = (name or '').translate(_FULLWIDTH_TABLE)
    for k, v in VARIANT_GLYPHS.items():
        s = s.replace(k, v)
    for k in sorted(VARIANT_WORDS, key=len, reverse=True):
        s = s.replace(k, VARIANT_WORDS[k])
    return s


def cn_key(name: str) -> str:
    """exact 通道比对键：字形归一化 + 去空白。

    用于"中文名精确匹配"的两侧归一：产后宫底高度（cm） 与 产后宫底高度(cm)
    的键相等，从而在 exact 通道直接命中，不再跌落到模糊通道。
    """
    return re.sub(r'\s+', '', normalize_glyphs(name))


def normalize_concept(name: str) -> str:
    """误匹配判据前的归一化（仅自验证器使用）：去掉括号说明、噪音字符、同义字符替换。"""
    s = name or ''
    # v2.0.3: 字形层先行（全角/异体字/异形词），再做既有降噪
    s = normalize_glyphs(s)
    # 去掉括号及内部说明，如 "入院病情(对应其他诊断1)"
    s = re.sub(r'[（(][^）)]*[）)]', '', s)
    for k, v in NORMALIZE_MAP.items():
        s = s.replace(k, v)
    for ch in NOISE_CHARS:
        s = s.replace(ch, '')
    return s


def strip_generic(name: str, extra_suffix=(), protect=False, prefixes=None) -> str:
    """去掉通用前后缀，保留核心概念串。

    extra_suffix: 额外追加的后缀词表（自验证器传 ('唯一',)，比对器不传）。
    protect: 剥前缀后若只剩后缀词（或为空）则回退该前缀，避免把核心概念剥空。
             True = 自验证器旧行为（有回退保护）；
             False = 比对器旧行为（简单顺序剥，不回退）。
    prefixes: 使用的通用前缀词表。None = 比对器词表（COMPARATOR_PREFIXES）；
              自验证器必须显式传 VALIDATOR_PREFIXES（含 '医疗机构'，降噪更激进）。
    """
    if prefixes is None:
        prefixes = COMPARATOR_PREFIXES
    s = name or ''
    for p in prefixes:
        if s.startswith(p):
            stripped = s[len(p):]
            if protect:
                # 剥前缀后若只剩后缀词（或为空），前缀很可能是字段核心词的一部分
                # （医疗机构代码 → 代码），回退该前缀，避免把核心概念剥空导致
                # 转入医疗机构代码 vs 医疗机构代码 这类同概念字段被误判。
                # 注意：回退判断基准 = GENERIC_SUFFIXES + extra_suffix。
                # 旧 self_validator._strip_generic 的 _GENERIC_SUFFIXES 本身含 '唯一'
                # （'患者唯一标识' 剥前缀后剩 '唯一标识'，其字符都在后缀表中 → 回退，
                #  继续剥后缀得 '患者'；若回退判断不含 '唯一' 则不会回退、直接剥空，
                #  行为即发生漂移）。此基准必须与旧行为严格一致，禁止改回。
                all_suffix = ''.join(GENERIC_SUFFIXES) + ''.join(extra_suffix)
                if stripped and all(ch in all_suffix for ch in stripped):
                    continue
            s = stripped
    for suf in list(GENERIC_SUFFIXES) + list(extra_suffix):
        s = s.replace(suf, '')
    return s.strip()


def core_compatible(name1: str, name2: str, extra_suffix=(), norm=None,
                    prefixes=None) -> bool:
    """判断两个字段名是否指向同一核心概念（拦截同义词/语义的跨概念误匹配）。

    规则：
    - 去掉通用前后缀后，若核心串完全相同 -> 兼容（如 科室代码 / 科室编码）
    - 若一个核心串是另一个的子串（更具体/更笼统的同义）-> 兼容
      （如 门急诊科室代码 / 门诊科室编码、患者姓名 / 姓名）
    - 一方核心为空、另一方有实质概念 -> 不兼容（如 院区名称 / 姓名）
    - 否则视为不同概念 -> 不兼容
      （如 机构内部药品通用名代码 / 医疗机构代码、检查流水号 / 就诊流水号、
        患者复诊标志 / 患者标识）

    参数：
    - extra_suffix: 额外后缀词表（自验证器传 ('唯一',) 降噪）
    - norm: 前置归一化函数（自验证器传 normalize_concept 降噪，比对器不传）
    - prefixes: 通用前缀词表（比对器不传=COMPARATOR_PREFIXES；
                自验证器显式传 VALIDATOR_PREFIXES，含 '医疗机构'）
    """
    if not name1 or not name2:
        return True
    # v2.0.3 字形层归一：所有语义判定之前统一处理异体字/全半角/异形词。
    # norm 路径（体检侧）的 normalize_concept 已内含字形层，无需重复；
    # 比对器路径（norm=None）在此显式补齐，保证两侧概念判定同源。
    if norm is not None:
        c1 = strip_generic(norm(name1), extra_suffix, protect=True, prefixes=prefixes)
        c2 = strip_generic(norm(name2), extra_suffix, protect=True, prefixes=prefixes)
    else:
        c1 = strip_generic(normalize_glyphs(name1), extra_suffix, protect=False, prefixes=prefixes)
        c2 = strip_generic(normalize_glyphs(name2), extra_suffix, protect=False, prefixes=prefixes)
    if not c1 and not c2:
        return True
    if not c1 or not c2:
        return False
    # 归一化后再比：去空格 + 统一小写。
    # RH 血型 vs Rh血型、ABO 血型 vs ABO血型 这类纯大小写/空格差异属同一概念，
    # 此前仅因大小写或空格不同被判不兼容（RH 漏配、ABO 靠子串巧合才过）。
    n1 = re.sub(r'\s+', '', c1).lower()
    n2 = re.sub(r'\s+', '', c2).lower()
    if n1 == n2:
        return True
    if n1 in n2 or n2 in n1:
        return True
    return False


def in_explicit_synonym_dict(name1: str, name2: str, synonyms: dict) -> bool:
    """name1↔name2 是否在显式同义词字典中声明（双向，子串匹配）。

    只检查全名精确匹配（name1 是字典 key 且 name2 在其 value 列表中，
    或 name2 是字典 key 且 name1 在其 value 列表中）。
    不做宽松子串展开，但 value 命中用子串判断：
    身份证件号码 与 证件号码 通过 证件号码 的 value「身份证」是
    「身份证件号码」的子串而命中（两处实现需保持一致，禁止漂移）。
    """
    if not synonyms or not name1 or not name2:
        return False
    # 正向：name1 是 key，name2 在其 value 列表中（value 用子串匹配）
    if name1 in synonyms:
        for syn in synonyms.get(name1, ()):
            if syn in name2 or name2 in syn:
                return True
    # 反向：name2 是 key，name1 在其 value 列表中
    if name2 in synonyms:
        for syn in synonyms.get(name2, ()):
            if syn in name1 or name1 in syn:
                return True
    return False