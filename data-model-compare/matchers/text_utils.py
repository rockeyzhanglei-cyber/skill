#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文本处理工具与角色词判定（P1-2 第三刀，拆分自 standard_comparator.py）

一族**零状态**的纯文本工具：最长公共子串（LCS）、子序列判定、角色尾词剥离、
角色关键词提取、序号字段族的过程名规整等，供各条匹配通道复用。

拆分依据（AST 分析，三种引用形式 self.X / ClassName.X / cls.X 全查）：
- 11 个函数全部不读写实例状态（原均为 staticmethod）
- 引用的 5 个常量（ROLE_TAILS / GEN_PREFIXES / ROLE_KEYWORDS /
  PROC_ROMAN / PROC_FLAG_KEYS）已一并下沉，类内无其他使用点
- 组内互不调用

原类 StandardComparator 保留同名薄委托，调用方无需改动。

⚠️ 维护约定：保持无状态与无副作用，不 import 主类（避免循环依赖）。
"""


import re


# ============================================================================
# 常量（P1-2 从 StandardComparator 下沉至此，单一事实来源）
# 原类以 `_XXX = <mod>.XXX` 别名引用，故 XXX / self._XXX 既有用法不变。
# ============================================================================

# 字段角色尾词（从基础名中剥离，用于提取「域概念」）。按长度降序排列。
ROLE_TAILS = [
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
GEN_PREFIXES = ['是否', '有无', '需']

# 字段角色 → 关键词（按关键词长度降序，用于从字段名后缀判定角色）。
# 角色用于把「目标序号字段」映射到子表里「同角色」的字段
# （如 诊断代码 → 子表 诊断代码 字段；诊断名称 → 诊断名称 字段）。
ROLE_KEYWORDS = [
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
PROC_ROMAN = {'Ⅰ': '一', 'Ⅱ': '二', 'Ⅲ': '三', 'Ⅳ': '四', 'Ⅴ': '五'}

PROC_FLAG_KEYS = ('唯一标识', '流水号', '序号', '标志')



def strip_role_tail(text: str) -> str:
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
    for pfx in GEN_PREFIXES:
        if t.startswith(pfx):
            t = t[len(pfx):].strip()
            break
    changed = True
    while changed:
        changed = False
        for tail in ROLE_TAILS:
            if t.endswith(tail) and len(t) > len(tail):
                t = t[: -len(tail)].strip()
                changed = True
                break
    return t
def has_common_substr(a: str, b: str, min_len: int = 2) -> bool:
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
def lcs_substr_len(a: str, b: str) -> int:
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
def lcs_len(a: str, b: str) -> int:
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
def is_subseq(short: str, long: str) -> bool:
    """short 是否是 long 的子序列（保持顺序即可，不必连续）。
    例：手术代码 ⊂ 其他手术操作代码 ✓；手术切口类别代码 ⊄ 其他手术操作代码。"""
    if not short:
        return True
    if not long:
        return False
    it = iter(long)
    return all(ch in it for ch in short)
def en_suffix_signal(target_en: str, sf_en: str) -> int:
    """目标英文字段名后缀（_code/_name/_id）与源英文字段名（CODE/NAME/ID）对齐 → +15。"""
    t = (target_en or '').lower()
    s = (sf_en or '').upper()
    for tok in ('_code', '_name', '_id'):
        if tok in t and tok[1:].upper() in s:
            return 15
    return 0
def field_role(cn: str) -> str:
    """从字段中文名后缀判定角色（code/name/date/doctor/...）。"""
    if not cn:
        return ''
    for role, kws in ROLE_KEYWORDS:
        for kw in kws:
            if cn.endswith(kw) and len(cn) > len(kw):
                return role
    return ''
def role_keyword(cn: str) -> str:
    """返回字段中文名末尾命中的具体角色关键词（如 Ⅰ助/麻醉方式/切口类别/代码）。"""
    if not cn:
        return ''
    for role, kws in ROLE_KEYWORDS:
        for kw in kws:
            if cn.endswith(kw) and len(cn) > len(kw):
                return kw
    return ''
def norm_proc_name(cn: str) -> str:
    """序号字段匹配用名称规范化：
    罗马数字→中文数字（Ⅰ助→一助）；手术/操作同族（操作→手术）；
    类型/类别同义（类型→类别）；医生/术者归入医师（麻醉医生→麻醉医师）。
    全部为卫生信息标准的通用同族约定，不涉及具体表名。"""
    if not cn:
        return ''
    s = ''.join(PROC_ROMAN.get(ch, ch) for ch in cn)
    s = s.replace('操作', '手术')
    s = s.replace('类型', '类别')
    s = s.replace('医生', '医师')
    s = s.replace('术者', '医师')
    return s
def proc_family(cn: str) -> str:
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
def is_flagish(cn: str) -> bool:
    """是否/有无/需 前缀或 唯一标识/流水号/序号/标志 类（标志性字段）。"""
    if not cn:
        return False
    if cn.startswith(('是否', '有无', '需')):
        return True
    return any(k in cn for k in PROC_FLAG_KEYS)