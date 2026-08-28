#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
字段兼容性判定（P1-2 拆分自 standard_comparator.py）

一族**零状态**的纯判定函数：判断两个字段在语义 / 种类 / 角色 / 类型等维度上
是否兼容，供同义词、关键词、语义、P6 关联等各条匹配通道复用。

拆分依据（由 AST 分析确认）：
- 9 个函数全部不读写 StandardComparator 的实例状态（无 self）
- 不依赖 matchers.matching_core，自包含
- 组内仅 `field_kind_compatible` 调用 `field_kind_of`，其余互不依赖
- 嵌套的辅助函数（type_group / extract_subject / extract_role_modifier /
  get_identity / _cat）随各自函数一并迁移

原类 StandardComparator 保留**同名薄委托**方法，调用方无需任何改动。

⚠️ 维护约定：本文件的函数必须保持无状态。若某个判定需要读取 comparator
的配置（如阈值、开关），应通过参数传入，而不是反过去 import 主类
（那会形成循环依赖，也让判定结果难以复现）。
"""

# ============================================================================
# 字段"种类"常量（P1-2 从 StandardComparator 下沉至此，保持单一事实来源）
#
# 用途：名称/代码/流水号 等类型不一致应判为不兼容，防止
#       临床路径流水号≠临床路径名称、科主任代码≠科主任执业证书编码 等跨种类误匹配。
# 说明：原类以 `_FIELD_KIND_X = field_compatibility.FIELD_KIND_X` 别名引用，
#       因此 self._FIELD_KIND_X 的既有用法不受影响。
# ============================================================================

# 签名类：存的是人名（医师签名/护士签名），语义上属于"名称"族，
# 与 代码/流水号/标识 互不兼容（医嘱执行医师代码 ≠ 医嘱执行者签名）。
# "科别/病别"在卫生信息标准中即科室名称（中医病案首页"出院科别"英文名 out_dep_name、
# 长度 S3100 与"出院科室名称"一致），归入名称族，避免被错配到"出院科室编码"。
FIELD_KIND_NAME = {'名称', '名字', '姓名', '简称', '全称', '科别'}
FIELD_KIND_CODE = {'代码', '编码', '代号', '码'}
FIELD_KIND_SERIAL = {'流水号', '序号', '编号'}
FIELD_KIND_IDENT = {'标识', '标志', '唯一标识'}
# 签名独立成类：签名字段存的是签名图像/签名数据（或签署动作留痕），
# 与"姓名/名称"这种纯文本标识不是同一数据元
# （报告医师签名 ≠ 报告医生姓名），更不与代码/标识/流水号等价。
FIELD_KIND_SIGN = {'签名', '签章', '签字'}
FIELD_KIND_QUAL = {'执业证书', '身份证', '证书', '登记证', '执业证', '注册证'}
# 地址类：地址文本与名称/代码/标识/流水号是完全不同的数据元
# （工作单位地址 ≠ 工作单位名称——实测 keyword 曾错配）
FIELD_KIND_ADDR = {'地址', '住址'}
# 人口学/描述性属性：不可能与"流水号/标识"这类主键型字段等价
# （严重不良事件报告流水号 ≠ 不良事件报告人职业）
FIELD_KIND_ATTR = {'职业', '性别', '年龄', '民族', '国籍', '学历',
                   '婚姻状况', '职务', '职称', '籍贯'}


def is_field_mapping_compatible(target_field, source_field, field_mapping) -> bool:
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

def is_type_compatible_for_keyword(target_field, source_field) -> bool:
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

def is_code_name_compatible(name1: str, name2: str) -> bool:
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

def is_role_compatible_for_keyword(name1: str, name2: str) -> bool:
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

def field_kind_of(name: str) -> str:
    """从原名字（不剥离通用前后缀）提取尾部类型词。

    注意：先匹配长词，避免 '出院科室代码' 之类同时命中 '代码'/'码' 时结果不稳定。
    """
    kinds = (FIELD_KIND_NAME | FIELD_KIND_CODE |
             FIELD_KIND_SERIAL | FIELD_KIND_IDENT |
             FIELD_KIND_ATTR | FIELD_KIND_SIGN |
             FIELD_KIND_ADDR)
    for k in sorted(kinds, key=len, reverse=True):
        if name.endswith(k):
            return k
    return ''

def field_kind_compatible(name1: str, name2: str) -> bool:
    # 证书/证件类限定词只在一侧出现 -> 概念不同（代码 ≠ 执业证书编码）
    # 但"类别/类型"字段（如"身份证件类别代码"）不受此限——"类别"字段
    # 表示的是分类/枚举意义，不是证书原件本身（卡证类型 ≠ 身份证号码）。
    if '类别' not in name1 and '类别' not in name2 and '类型' not in name1 and '类型' not in name2:
        q1 = any(q in name1 for q in FIELD_KIND_QUAL)
        q2 = any(q in name2 for q in FIELD_KIND_QUAL)
        if q1 != q2:
            return False

    def _cat(k):
        if k in FIELD_KIND_NAME:
            return 'NAME'
        if k in FIELD_KIND_CODE:
            return 'CODE'
        if k in FIELD_KIND_SERIAL:
            return 'SERIAL'
        if k in FIELD_KIND_IDENT:
            return 'IDENT'
        if k in FIELD_KIND_ATTR:
            return 'ATTR'
        if k in FIELD_KIND_SIGN:
            return 'SIGN'
        if k in FIELD_KIND_ADDR:
            return 'ADDR'
        return 'OTHER'

    c1, c2 = _cat(field_kind_of(name1)), _cat(field_kind_of(name2))
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

def composite_subject(name: str) -> str:
    s = name or ''
    for sep in ('-', '－', '—'):
        if sep in s:
            s = s.split(sep)[-1]
    return s.strip()

def is_role_compatible_for_synonym(name1: str, name2: str) -> bool:
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

def is_concept_compatible_for_synonym(name1: str, name2: str) -> bool:
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
