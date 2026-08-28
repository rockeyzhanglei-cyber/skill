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


def normalize_concept(name: str) -> str:
    """误匹配判据前的归一化（仅自验证器使用）：去掉括号说明、噪音字符、同义字符替换。"""
    s = name or ''
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
    if norm is not None:
        c1 = strip_generic(norm(name1), extra_suffix, protect=True, prefixes=prefixes)
        c2 = strip_generic(norm(name2), extra_suffix, protect=True, prefixes=prefixes)
    else:
        c1 = strip_generic(name1, extra_suffix, protect=False, prefixes=prefixes)
        c2 = strip_generic(name2, extra_suffix, protect=False, prefixes=prefixes)
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