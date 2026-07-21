---
name: data-model-revision
description: |
  数据模型修订自动化 - 完整流程：需求分析→文档修订→DDL生成→修订记录脚本→提交BMS。

  **务必使用本Skill的场景**：
  - 用户提到"数据模型修订"、"改表"、"加字段"、"加表"、"修订需求"
  - 用户给出需求号并涉及数据标准/数据模型
  - 用户提供Word文档路径+修订关键词（如"修订这个文档"、"给这张表加字段"）
  - 用户说"生成DDL"、"生成修订记录"、"数据标准修订"
  - 用户提到"6.0模型"、"5.x模型"、"60模型"、"公版"、"项目化"
  - 用户询问值域编码、CVA编码、数据元定义
  - 用户提到"值域修订"、"值域更新"、"代码表修订"、"GB/T"、"国标"
  - 任何涉及edsm_*表、数据标准基础数据的操作

metadata:
  author: 张磊
  version: 2.0.0
tags: [数据模型, DDL, 修订记录, 数据标准, 值域修订, Word文档, PDF提取, Flyway]
keywords: 数据模型修订 改表 加字段 加表 修订需求 生成DDL 修订记录 数据标准 数据标准基础数据 值域修订 值域更新
---

# 数据模型修订自动化Skill

## 概述

本Skill用于自动化数据模型修订流程，从需求分析到脚本提交一站式完成。支持两种修订场景：

### 场景A：数据模型修订（常规）
根据PDF/Word标准文档，修订数据模型Word文档，生成DDL脚本和修订记录。详见"核心工作流"。

### 场景B：标准比对修订（省平台对接）
将区域标准规范与省平台标准规范进行比对，按"只增不减不更名"原则修订。详见"标准比对修订"章节。

---

## 核心工作流

```
Stage 1: 需求分析 → 解析需求、确定版本、匹配文档路径
Stage 2: PDF数据提取 → 从PDF标准文档提取表结构
Stage 3: Word文档修订 → 填充表格数据、设置格式
Stage 4: 逐行核对 → 手工逐行比对PDF与Word（核心！不可跳过）
Stage 5: DDL脚本生成 → 调用reg-ddl-generator
Stage 6: 修订记录生成 → edsm_revise_record + edsm_revise_detail
Stage 7: 修订记录Word维护 → 复制行→填充→新numId
Stage 8: 生成summary.md → 输出修订总结到{DOCS_DIR}/summary.md
```

**重要**：在auto-dev流水线中，git操作由Step 4统一处理，本Skill不执行git add/commit。

---

## 标准比对修订（场景B：省平台对接场景）

### 适用场景

将区域标准规范（如5x云南区域标准规范）与省平台/国家平台标准规范进行比对修订，确保区域标准能向省平台正常传输数据。

### 核心修订原则（绝对规则）

**只增不减不更名**：云南标准/区域标准以覆盖省平台为目标，遵循以下原则：

| 差异类型 | 处理方式 |
|----------|----------|
| 字段缺失（省平台有，区域无） | ✅ 标记"需新增字段" |
| 字段多余（区域有，省平台无） | ❌ **不删除**（兼容历史项目） |
| 字段名不同（同一语义字段名称不同） | ❌ **不改名**（意思相近即可，能传输数据） |
| 数据类型不同（同一字段类型/长度不同） | ⚠️ 标记"类型差异"（仅影响传输时修正） |
| 约束不同（必填/可选条件不同） | ⚠️ 标记"约束差异"（区域标准可更宽松） |
| 说明不同（字段说明/备注不同） | ⚠️ 标记"说明差异"（可参考省平台完善） |
| 表缺失（省平台有表，区域无表） | ✅ 标记"需新增表" |
| 表多余（区域有表，省平台无表） | ❌ **不删除** |

### 值域修订原则

**值域按语义匹配，不做强制修订**：

| 情况 | 处理方式 |
|------|----------|
| 值域名称含义相近 | ✅ 视为可映射，**不修改** |
| 代码值不一致 | ✅ 能映射即可，**不修改**云南标准的代码值 |
| 省平台引用了一个区域标准完全没有的值域 | ✅ 考虑新增值域条目（扩充值域明细） |
| 值域独立比对 | ❌ 不作为独立比对项，仅在表字段引用时参考 |

### 标准比对修订流程

```
Stage 1: 文档结构映射 → 建立两个规范的表名/数据集对照映射
Stage 2: 指纹索引 → 通过关键字段精确定位表（如YYDAH定位JBBRJBXXB）
Stage 3: 逐项差异比对 → 按上述原则逐表逐字段比对
Stage 4: 修订执行 → 新增字段/表/值域，不删除不改名
Stage 5: 复核交付 → 确认差异项已全部处理
```

### 索引映射规则（必须使用指纹匹配）

不能用顺序分配，必须通过关键字段定位：

| 表 | 关键指纹 | 说明 |
|-----|---------|------|
| JBBRJBXXB(患者基本信息) | YYDAH | tables[10], 50行 |
| MZJZJLB(门诊就诊记录) | JZLSH | tables[12], 49行 |
| MZGHB(门诊挂号) | YTYBZ | tables[11], 23行 |
| BA_SYSSK(病案首页手术信息) | BAHM | tables[27], 264行大表 |
| BA_SYJBK(西医病案首页) | BAH | tables[18], 42行 |
| YP_JBXXK(药品基本信息) | YPDM | tables[9], 40行 |
| MZYZMXB(门诊医嘱明细) | CFH | tables[14], 108行 |

### 匹配方法（按优先级）

| 优先级 | 方法 | 说明 |
|--------|------|------|
| ① | 英文名语义映射 | 在**同一医共体表**内查找对应字段，如 local_id→YYDAH |
| ② | 中文名映射 | 中文名相同或同义词匹配（如"院区代码"="分院代码"） |
| ③ | 业务逻辑推导 | 部分字段可从医共体现有字段推导 |
| ④ | 跨表关联获取 | 通过已验证的关联键从其他表获取 |
| ⑤ | 公共覆盖 | 标识→XGBZ/TBRQ，地址多级→XZQHDM+JZDZ |
| ⑥ | 其余→新增 | 拿不准的一律新增，不跨表/跨系统乱关联 |

### 业务逻辑推导规则

| 省平台字段 | 推导方式 | 示例 |
|-----------|---------|------|
| 是否就诊(visit_flag) | 就诊状态(JZZT)判断 | JZZT=已就诊→是 |
| 是否急诊(emerg_flag) | 是否急诊挂号(SFJZGH) | 字段值直接对应 |
| 预约挂号标识(appo_flag) | 预约挂号标识(SFYY) | 字段值直接对应 |
| 预约日期时间(appo_date) | 预约开始日期时间(YYKSSJ) | 通过YYLSH→MZGHB关联 |
| 就诊类型代码(med_type_code) | 就诊类型代码(JZLXDM) | MZYZMXB中有，通过JZLSH关联 |
| 患者复诊标志(first_flag) | 初复诊标志 | 医共体标准中需确认是否有此字段 |
| 退号标志(reg_status) | 退号标志(GTHBZ) | 直接对应 |

### 关联路径（已验证）

| 关联键 | 源表→目标表 | 说明 |
|--------|-----------|------|
| JZLSH | MZJZJLB→MZYZMXB | 门诊就诊→医嘱 |
| YYLSH | MZJZJLB→MZGHB/MZYYB | 门诊就诊→挂号/预约 |
| YYDAH | 各表→JBBRJBXXB | 患者身份关联 |
| JZLSH | ZYJZJLB→BA_SYSSK | 住院就诊→病案首页 |
| JZLSH | 各表→MZJZJLB | 获取就诊基本信息 |
| CISID | 各表→ZYJZJLB | 住院号关联 |

### 三条地址的对应关系

| 地址类型 | 省平台字段 | 医共体字段 | 说明 |
|---------|-----------|-----------|------|
| 出生地 | birth_* (14个子字段) | CSD(出生地, N6) | 6位行政区划码，无法展开省/市/县/乡/村多级 → 新增 |
| 户籍地 | reg_* (14个子字段) | HKDZ(户口地址) + HKDZYB(户口邮编) | 地址+邮编覆盖 |
| 居住地/常住地 | permanent_addr_* / addr_* | XZQHDM(6位码) + JZDZ(详细地址) | 行政区划码+详细地址覆盖 |

### 名称字段规则

名称字段（如 card_type_name、id_type_name、gender_name 等）**不检查约束和长度**，直接判定为"满足（字典查询）"。

### 约束检查规则

| 医共体→省平台 | 判定 | 说明 |
|--------------|------|------|
| O→M | 修改 | 需要升级约束 |
| O→C | 不修改 | O的数据可以填到C里 |
| C→M | 不修改 | C的数据可以填到M里 |
| 其他 | 不修改 | 无需处理 |

### 类型差异不处理

S1→S3、S2→S3 等纯数据类型变更不需要修改。

### 修订单条件

只有以下情况才标记为"修改"：
1. 约束升级：医共体O + 省平台M → 需要修改
2. 长度扩展：医共体长度 < 省平台长度 → 需要修改

### 修订汇总输出格式

按**医共体表**组织，不按省平台表：

```
一、需新增的表
  过敏原信息表（29字段）→ 医共体只有GMS文本字段

二、需新增的字段（按医共体表分类）
  JBBRJBXXB（患者基本信息表）
    - health_rec_no(健康档案编号) S1(AN17) C
    - email(电子邮件地址) S1(AN..40) O
    - work_place_tel(工作单位电话号码) S1(AN..20) C
  ...

三、需修改的字段（按医共体表分类）
  JBBRJBXXB（患者基本信息表）
    - id_type_code(证件类型) O/N2 → M/N2  约束升级O→M
    - birthday(出生日期) O/D10 → M/D10    约束升级O→M
    - company(工作单位名称) O/AN..128 → C/AN..300  长度扩展
  ...
```

### 交付物

| 交付物 | 说明 |
|--------|------|
| 差异对照表 | 按"只增不减不更名"原则标注的差异明细，含逐表对照 |
| 修订汇总（置顶） | 针对医共体标准的修改方案（新增表/新增字段/修改字段） |
| 修订后规范文档 | 新增字段/表已同步 |
| 修订记录 | 变更内容可追溯 |

### 通用语义匹配引擎

#### 适用场景
将区域标准规范与省平台/国家平台标准规范进行比对，按"只增不减不更名"原则修订。

#### 核心算法

```
省字段名 → normalize → 同义词替换 → 去后缀(TECH_SUFFIXES) → core
医字段名 → normalize → 同义词替换 → 去后缀(TECH_SUFFIXES) → core
                       ↓
          比较core（精确 > 同义词核心 > 同义包含≥30% > 同义词全名）
```

#### 关键规则

**跨类别禁止**：代码/编码类 ≠ 名称/日期/金额/标志类（同核心例外）
**包含比限制**：被包含部分/总长度 ≥ 30% 才接受
**短核心兜底**：核心≤3字时回退到同义词全名匹配

#### 可复用的知识库

| 组件 | 说明 |
|------|------|
| TECH_SUFFIXES(技术后缀) | 约60个，所有文档通用 |
| SYNONYM(同义词) | 约500对，医疗行业通用 |
| BLOCK_LIST(阻塞列表) | 少量字段特定，每个文档需过一遍 |

#### 技术后缀列表

```python
TECH_SUFFIXES = [
    '代码','名称','编码','标志','标识','类别','号码','编号','日期','时间',
    '金额','费用','类型','方式','途径','级别','描述','原因','说明','单位',
    '情况','来源','标准','分类','格式','数据','信息','记录','明细','结果',
    '报告','项目','指标','参数','值域','范围','流水号','状态','编码','规格',
    '品级','归类','密码','账号','途径','工号','编号','性质','特征','操作','姓名'
]
```

#### 同义词示例

```python
SYNONYM = {
    '患者':'病人','病人':'患者','院区':'分院','分院':'院区',
    '社保卡':'医保卡','医保卡':'社保卡','预约':'挂号','挂号':'预约',
    '就诊':'诊疗','诊疗':'就诊','门诊':'门急诊','门急诊':'门诊',
    '就诊状态':'是否就诊','是否就诊':'就诊状态',
    '是否专家':'专家号','专家号':'是否专家',
    '科室':'科室代码','科室代码':'科室','费用':'金额','金额':'费用',
    '诊察费':'挂号费','挂号费':'诊察费','个人支付':'自付','自付':'个人支付',
    '身份证号':'证件号码','证件号码':'身份证号',
    '身份证件':'证件','证件':'身份证件','身份证':'证件',
    '联系电话':'电话','电话':'联系电话','手机':'手机号','手机号':'手机',
    '预约途径':'挂号途径','挂号途径':'预约途径',
    '出生地':'出生地','工作单位电话':'电话',
    '医疗费用支付方式':'支付方式','支付方式':'医疗费用支付方式',
    '医保':'医保','个人医保账户':'个人支付','个人支付':'个人医保账户',
    '院内科室':'科室','平台科室':'科室','病人性别':'性别','性别':'病人性别',
    '新生儿出生体重':'新生儿体重','住院天数':'住院天数','住院日':'住院天数',
    '住院次数':'入院次数','入院次数':'住院次数','住院':'住院','入院':'住院',
    '出院':'出院','修改标志':'修改','数据状态':'修改',
    '预约挂号':'预约','预约挂号标识':'预约','退号标志':'退号','退号':'退号标志',
    '是否急诊':'急诊','急诊':'是否急诊','是否急诊挂号':'急诊',
    '挂号操作员':'操作员','操作员':'挂号操作员',
    '是否专家号':'专家','专家':'是否专家号',
    # ... 完整版见skill references/semantic-match-engine.py
}
```

#### 语义类别判断

```python
def sem_cat(name):
    """判断字段语义类别"""
    if name.endswith(('代码','编码','工号','号码')): return 'code'
    if name.endswith(('名称','名字')): return 'name'
    if name.endswith(('日期','时间')): return 'date'
    if name.endswith(('金额','费用','费')): return 'amount'
    if name.endswith(('标志','标识')): return 'flag'
    return 'other'
```

#### 匹配函数

```python
def match(prov_name, yn_name):
    """语义匹配，返回(score, reason)"""
    p = core(prov_name)  # normalize + 同义词 + 去后缀
    y = core(yn_name)
    
    # 1. 跨类别禁止
    pc, yc = sem_cat(prov_name), sem_cat(yn_name)
    # 代码类 ≠ 名称/日期/金额/描述/级别/状态/单位
    if pc == 'code' and yc in ('name','date','amount','desc','level','status','unit'):
        if p == y: return 95, '跨类别同核心'
        return 0, '跨类别'
    # 名称类 ≠ 代码/编码
    if pc == 'name' and yc == 'code':
        if p == y: return 95, '跨类别同核心'
        return 0, '跨类别'
    # 日期类 ≠ 代码/编码
    if pc == 'date' and yc == 'code': return 0, '跨类别'
    # 金额类 ≠ 代码/编码/标志
    if pc == 'amount' and yc in ('code','flag'): return 0, '跨类别'
    # 标志类 ≠ 金额
    if pc == 'flag' and yc == 'amount': return 0, '跨类别'
    
    # 2. 同义词核心匹配
    ps = synonyms(p); ys = synonyms(y)
    for sp in ps:
        for sy in ys:
            if sp == sy: return 90, f'同义词核心:{sp}'
            # 包含关系（双方核心≥3字）
            if len(sp) >= 3 and len(sy) >= 3:
                if sp in sy or sy in sp:
                    ratio = len(min(sp,sy,key=len))/len(max(sp,sy,key=len))
                    if ratio >= 0.3: return 80, f'同义包含(比{ratio:.0%})'
    
    # 3. 同义词全名匹配（无后缀剥离）
    pn = syn_full(prov_name); yn = syn_full(yn_name)
    if pn == yn: return 85, '同义词全名匹配'
    if pn in yn or yn in pn:
        ratio = len(min(pn,yn,key=len))/len(max(pn,yn,key=len))
        if ratio >= 0.3: return 75, f'同义词全名包含(比{ratio:.0%})'
    
    return 0, ''
```

---

### 颜色规范

| 判定 | 行背景色 | 文字颜色 |
|------|---------|---------|
| 满足 | 浅绿 #c8e6c9 | 深绿 #2e7d32 |
| 修改 | 浅橙 #ffe0b2 | 深橙 #e65100 |
| 新增 | 浅粉 #ffcdd2 | 深红 #c62828 |

---

## 阶段2：PDF数据提取（重要经验）

### 工具选择

| 工具 | 质量 | 问题 |
|-----|------|------|
| **MinerU**（mineru-open-api） | ⭐⭐⭐⭐⭐ | 分页导致表格被拆分，表名错位 |
| **pdftotext** | ⭐⭐⭐ | 字段名截断、合并行、噪声多 |
| OCR | ⭐⭐⭐ | 中文识别一般，速度慢 |

**推荐方案**：MinerU提取主数据 + 人工核对补充

### MinerU分页问题（关键！）

MinerU按页提取，一个跨页的表格会被拆成多个HTML片段，导致：
- 同一个表的数据被分割到不同页
- 部分表的字段丢失（如T_HD_PATIENT_QUIT只有15个字段，因为分页只抓到了部分）
- 继承表的字段不完整

**应对策略**：
1. 从MinerU提取所有HTML表格
2. 对继承表（如T_HD_PATIENT_QUIT继承T_HD_PATIENT）用基表数据补充
3. 对pdftotext截断的字段名，对照PDF原文修复

### 已知的字段名截断问题（pdftotext导致）

```
EQUIP → EQUIP_ID
EQUIPMENT_BR → EQUIPMENT_BRAND
EQUIPMENT_MO → EQUIPMENT_MODEL
EQUIPMENT_TY → EQUIPMENT_TYPE
DIAGNOSIS_TI → DIAGNOSIS_TIME
DIAGNOSIS_TY → DIAGNOSIS_TYPE
NEOPATHY_TIM → NEOPATHY_TIME
NEOPATHY_TYP → NEOPATHY_TYPE
NEOPATHY_DES → NEOPATHY_DESC
FOR_EMERGENC → FOR_EMERGENCY
ADMISSION_TI → ADMISSION_TIME
ADMISSION_CAUSE_DE → ADMISSION_CAUSE_DESC
SNSTAT_DDATEATE → SN
DIC_KE → DIC_KEY
DIC_UN → DIC_UNIT
END_TI → END_TIME
EMG_START_TI → EMG_START_TIME
DIVISION_NAM → DIVISION_NAME
RRT_TY → RRT_TYPE
RRT_TYPE_NAM → RRT_TYPE_NAME
BICARBONATE_RADICA → BICARBONATE_RADICAL
DIALYSIS_DAT → DIALYSIS_DATE
DOWN_NURSE_I → DOWN_NURSE_ID
CARD_N → CARD_NO
MZ_FLA → MZ_FLAG
INSPECTED_TY → INSPECTED_TYPE
REPORT_CATEG → REPORT_CATEGORY
RECORD_CCOUN → RECORD_COUNT
DIAGNOSE_COD → DIAGNOSE_CODE
DIAGNOSE_NAM → DIAGNOSE_NAME
INSPECTED_RESULT_N → INSPECTED_RESULT_NO
UNIT_T → UNIT_TYPE
INSPECTED_RE → INSPECTED_RESULT
SORTIN → SORTING
YEAR_C → YEAR_CNT
DAY_CN → DAY_CNT
MAX_DA → MAX_DATE
HOSPITAL_NAM → HOSPITAL_NAME
PATIENT_NKSEQUELDATEAE_DAT → PATIENT_NK（合并行）
SEQUELAE_TYP → SEQUELAE_TYPE
SUB_TY → SEQUELAE_SUB_TYPE
EQUIP_TYPE_I → EQUIP_TYPE_ID / INSPECT_ID
END_DA → END_DATE
INSPECTED_ITEM_EN → INSPECTED_ITEM_EN_NAME
ZZJHLS → ZZJHLSH
ZZJHSD → ZZJHSDM
ZZJHSM → ZZJHSMC
ICUJRR → ICUJRRQ
ICUTCR → ICUTCRQ
```

### 已知的合并行修复

```
PERMANENT_TYIN_DATDATEOUT_DADATE → PERMANENT_TYPE + IN_DATE + OUT_DATE
LOCAL_INSURANCEDIALYSDATEIS_START_TIM → LOCAL_INSURANCE + DIALYSIS_START_TIME
BORN_DATEDIALYSDATEIS_START_TIM → BORN_DATE + DIALYSIS_START_TIME
REMOVE_REASON_DESCSETUP_DATE → REMOVE_REASON_DESC + SETUP_DATE
```

---

## 阶段3：Word文档修订（核心经验）

### 表格格式要求（必须遵守）

| 属性 | 要求 |
|------|------|
| 字体 | Times New Roman |
| 字号 | 10pt（sz=20，不是sz=24/小四） |
| 颜色 | 红色（FF0000） |
| 行距 | 单倍行距（line=240, lineRule=auto） |
| 说明列"复合主键" | 加粗（b=1） |
| 中文字体 | eastAsia=Times New Roman |

### 修改方式：复制行替换内容（重要！）

**不要重写整表，不要用etree创建新元素！**

正确做法：
1. 取已有行的 `_tr` 元素做模板
2. `deepcopy(template_tr)` 复制
3. 修改 `<w:t>` 元素的 text 内容
4. 确保每个 `<w:r>` 下有 `<w:rPr>`（字体属性）
5. 追加到 `tbl._tbl`

### 新增表的继承关系（常见错误）

以下表是"继承表"，只包含特有字段，不包含基表字段：

| 继承表 | 基表 | 特有字段数 |
|--------|------|----------|
| T_HD_STAFF_LOGIN | T_HD_STAFF | 11个（不含STAFF_ID/STAFF_NAME等人员信息） |
| T_HD_PATIENT_QUIT | T_HD_PATIENT | 15个（不含患者基本信息字段） |
| T_HD_PATIENT_LINE | T_HD_PATIENT | 13个（标签属性表） |
| T_HD_INHOSPITAL_LINE | T_HD_INHOSPITAL | 13个 |
| T_PD_STAFF_LOGIN | T_PD_STAFF | 11个 |
| T_PD_PATIENT_LINE | T_PD_PATIENT | 13个 |
| T_PD_INHOSPITAL_LINE | T_PD_INHOSPITAL | 11个 |

**注意**：如果Word中这些表有基表字段，说明是错误填充，需要移除！

---

## 阶段4：逐行核对（最重要！不可跳过！）

### 不要用自动化脚本替代人工核对

自动化脚本的常见bug：
- 约束映射顺序错误（"有则必填"包含"必填"，先判"有则必填"再判"必填"）
- MinerU遗漏字段导致错误判断"无PDF参考数据"
- 字段名大小写匹配问题

### 核对流程

1. 用MinerU数据作为参考
2. 对每条记录检查：字段名、数据元名称、约束、数据类型、表示格式、说明
3. 对继承表用基表数据补充
4. 修复后重新核对，直至无错误

### 约束映射规则

```
有则必填 → C（条件必填，先判断）
条件必填 → C
必填 → M
可选 → O
```

**注意**：`"有则必填" in cr` 必须在 `"必填" in cr` 之前判断，否则"有则必填"会被误判为M！

---

## 阶段6：修订记录SQL生成（重要经验）

### 修订摘要格式（summary字段）

**如果修订多项内容，必须分条列出，删除的字段要具体说明**：

```sql
-- 正确示例：
'1. 新增检查检验项目目录表[BASE_INS_EXAM_ITEM]
2. 新增值域：检查检验类别[CVA-0307]，值：1-检查、2-检验
3. 删除MEDTECH_LIS_REPORT_RSLT表的4个字段：
   - PLAT_INDEX_NO（平台检验项目编码）
   - PLAT_INDEX_NAME（平台检验项目名称）
   - RECOGN_INDEX_NO（互认项目编码）
   - RECOGN_INDEX_NAME（互认项目名称）'

-- 错误示例：
'新增检查检验项目目录表，删除4个字段'  -- 太模糊，不知道删了啥
```

### 完整的修订记录内容

一条完整的修订记录SQL应包含：
1. `edsm_revise_record` × 1条
2. `edsm_revise_detail`（business_code='codeSystem'） × 值域代码系统（新增值域时）
3. `edsm_revise_detail`（business_code='valueSet'） × 值域条目（新增值域时）
4. `edsm_revise_detail`（business_code='datasetCategory'） × 分类数（新增分类时）
5. `edsm_revise_detail`（business_code='dataset'） × 新增表数（**必须包含seqNo字段**）
6. `edsm_revise_detail`（business_code='metadata'） × 元数据（新字段需要添加元数据）
7. `edsm_revise_detail`（business_code='datasetElement'） × 所有字段数

### 数据集序号（seqNo）确定规则

- 数据集记录必须包含seqNo字段
- 序号要和文档中的顺序一致
- 查看Word文档中新表的位置，确定前一个表的序号
- 新表序号 = 前一个表序号 + 1

### 元数据（metadata）添加规则

**核心原则**：每个新字段都需要对应的元数据记录，datasetElement通过metadataId引用元数据

**元数据去重规则**：
- **仅以下公共字段使用公共元数据（不去重，直接引用）**：
  - sys_soid - 系统编码
  - org_code - 医疗机构代码
  - org_name - 医疗机构名称
  - status - 记录状态
  - is_del / jlzt / scbz - 删除标志
  - sys_created_at / created_at - 创建日期时间
  - sys_modified_at / modified_at - 修改日期时间

- **其他字段一律添加新的元数据**，即使字段名相同也不去重
  - 例如：item_id在收费项目目录和检查检验项目目录中含义不同，不能共用元数据

**元数据字段结构**：
```json
{
  "metadataId": "winning-plat-01-{字段名}",
  "namespaceId": "1",
  "metadataCode": "{字段名}",
  "metadataName": "{中文名}",
  "definition": "{定义说明}",
  "dataType": "{数据类型}",
  "representationFormat": "{表示格式}",
  "codeSystemId": "{值域代码系统ID}",
  "allow": "",
  "status": 1,
  "isDel": 0,
  "createdAt": "{时间戳}",
  "modifiedAt": ""
}
```

**datasetElement引用元数据**：
```json
{
  "elementId": "winning-plat-01-{表名}-{字段名}",
  "datasetId": "winning-plat-01-{表名}",
  "metadataId": "winning-plat-01-{字段名}",  // 引用元数据
  "elementCode": "{字段名}",
  "elementName": "{中文名}",
  "definition": "{定义说明}",
  "isPk": 0,
  "notnull": 0,
  "dataType": "{数据类型}",
  "representationFormat": "{表示格式}",
  "codeSystemId": "{值域代码系统ID}",
  "allow": "",
  "status": 1,
  "seqNo": {序号},
  "isDel": 0,
  "createdAt": "{时间戳}",
  "modifiedAt": ""
}
```

### SQL脚本格式

**不需要写太多注释，直接生成即可**。参考格式：

```sql
-- 需求: {需求号}

insert into edsm_revise_record(revise_id,standard_id,version,require_no,summary,is_standard,published_at,is_upgraded,is_del,created_at)
values('{UUID}','{集合}','{版本号}','{需求号}','{摘要}',1,'{时间戳}',0,0,'{时间戳}');

-- 新增值域（如有）
insert into edsm_revise_detail(...)values(...);

-- 新增数据集
insert into edsm_revise_detail(...)values(...);

-- 新增元数据（如有）
insert into edsm_revise_detail(...)values(...);

-- 新增数据集字段
insert into edsm_revise_detail(...)values(...);
```

---

## 阶段7：修订记录Word文档维护

### 修订历史内容要求

修订记录Word文档中，修订内容要写清楚：

**如果修订多项内容，必须分条列出**：

```
1. 新增检查检验项目目录表[BASE_INS_EXAM_ITEM]
2. 新增值域：检查检验类别[CVA-0307]，值：1-检查、2-检验
3. 删除MEDTECH_LIS_REPORT_RSLT表的4个字段：
   - PLAT_INDEX_NO（平台检验项目编码）
   - PLAT_INDEX_NAME（平台检验项目名称）
   - RECOGN_INDEX_NO（互认项目编码）
   - RECOGN_INDEX_NAME（互认项目名称）
```

**不能只写概括性描述**，如"新增表、删除字段"，必须具体列出修订的内容。

### 正确做法

1. 备份原始修订记录Word文档
2. 取最后一行作为模板：`last_row = tbl.rows[-1]`
3. 复制行：`new_tr = deepcopy(last_row._tr)`
4. 追加：`tbl._tbl.append(new_tr)`
5. 替换内容：修改 `<w:t>` 的text
6. 设置新numId：`prev_numId + 1`（重新编号）

### 错误做法

- 不要用etree创建新段落（格式丢失）
- 不要删除所有行重新添加（破坏原有编号）
- 不要修改regenerate_all.py中的修订记录Word部分（用户可能自己改过）

---

## 标准比对常见错误清单

### 语义匹配误匹配（V1-V8迭代经验）

| 问题 | 根因 | 修复 |
|------|------|------|
| 患者姓名→患者类型 | 去后缀"姓名"→"患者"，去后缀"类型"→"患者"，核心相同 | 去后缀后核心≤3字需原始名称担保 |
| 性别代码→病人性别 | 同义词"性别"="病人性别" | 正确匹配，但需注意同义词方向 |
| 挂号类别代码→挂号途径 | 同义词链"挂号类别"→"挂号"→"挂号途径"，核心"挂号"2字 | 短核心同义匹配需原始名称包含支持 |
| 是否就诊→就诊类型代码 | 同义词"就诊"="就诊类型"，核心"就诊"2字 | 短核心同义匹配需原始名称包含支持 |
| 预约编号→预约挂号标识 | 同义词"预约"="预约挂号"，核心"预约"2字 | 短核心同义匹配需原始名称包含支持 |
| 是否专家→专家级别 | "专家"包含在"专家级别"中 | 包含比≥30%太宽松，需提高至≥50% |
| 工作单位电话号码→电话号码 | "电话号码"包含在"工作单位电话号码"中 | 加BLOCK_LIST |
| 出生地-详细地址→出生地 | "出生地"包含在"出生地-详细地址"中 | 加BLOCK_LIST |
| 证件号码不详其他原因说明→证件类型 | "证件"包含在"证件号码不详其他原因说明"中 | 包含比≥30%太宽松，需提高至≥50% |
| 医疗机构名称→医疗机构代码 | 去后缀"名称"→"医疗机构"，去后缀"代码"→"医疗机构"，核心相同 | 跨类别：名称≠代码，即使核心相同也不允许 |
| 院区代码→分院名称 | 同义词"院区"="分院"，去后缀"代码"→"院区"，"名称"→"分院"→核心"院区"≠"分院" | 跨类别禁止后解决 |

### 语义匹配引擎最佳实践

1. **先同义词替换，再去后缀**：避免"院区代码"→"分院代码"→"分院"（正确）vs "院区"→"分院"（错误）
2. **短核心(≤3字)必须由原始名称包含担保**：防止"挂号"匹配到"挂号类别"和"挂号日期时间"
3. **跨类别禁止**：代码/编码/工号/号码 ≠ 名称/日期/金额/标志（核心相同也不允许）
4. **包含比≥50%**（不是30%）：防止"证件"→"证件号码不详其他原因说明"
5. **BLOCK_LIST**：工作单位电话、出生地-详细地址、证件号码不详等，需手动维护
6. **已匹配字段独占**：一个医共体字段只能匹配一个省平台字段

### 多值SEM映射（弃用）

**不再使用硬编码的SEM字典**，改用语义匹配引擎。每个字段自动匹配，不需要手动维护英文名映射关系。

### 可复用的知识库体系

| 组件 | 规模 | 维护方式 |
|------|------|---------|
| TECH_SUFFIXES(技术后缀) | 约60个 | 一劳永逸，几乎不修改 |
| SYNONYM(同义词) | 约500对 | 每次新文档比对后补充 |
| BLOCK_LIST(阻塞列表) | 约20个 | 每个文档需过一遍 |
| 匹配算法 | 1个函数 | 稳定后不修改 |

### 新增字段的合理性判断

| 新增原因 | 示例 | 说明 |
|---------|------|------|
| 省平台独有字段 | 新生儿标志、挂号午别代码 | 医共体确实没有 |
| 语义不同 | 工作单位电话号码→DHHM(个人电话) | 语义不属于同一事物 |
| 地址多级拆分 | 出生地-省市代码→CSD(6位码) | 6位码无法展开多级 |
| 表缺失 | 过敏原信息表(29字段) | 医共体只有GMS文本字段 |
| 重复组展开 | 诊断1~39 | 省平台按1~39展开，医共体没有 |

### 版本迭代记录

| 版本 | 日期 | 变更 |
|------|------|------|
| V1 | 初版 | 硬编码SEM映射，匹配率低 |
| V2 | 去后缀语义匹配 | 包含关系太宽松，误匹配多 |
| V3 | 跨类别禁止 | 短核心误匹配 |
| V4 | 包含比限制 | 同义词链导致误匹配 |
| V5 | 先同义再去后缀 | 短核心问题 |
| V6 | 原始名称兜底 | 同义词链导致误匹配 |
| V7 | 短核心优化 | 仍有误匹配 |
| V8 | 最终版 | 去后缀+同义词+跨类别限制+原始名称包含 |

---

## 常见错误清单

### 数据错误

| 错误 | 原因 | 修复 |
|------|------|------|
| 约束M/C混淆 | "有则必填"在"必填"前判断 | 先判C再判M |
| 字段名截断 | pdftotext提取不完整 | 对照PDF原文修复 |
| 合并行 | pdftotext多列合并 | 拆分为独立行 |
| 继承表多字段 | 误把基表字段加入继承表 | 删除多余字段 |
| 数据类型错误 | IS_CRF应该是L(T/F)不是S2(N1) | 对照PDF核实 |
| 数据元名不完整 | "身高"缺"(cm)" | 对照PDF补全 |

### 格式错误

| 错误 | 原因 | 修复 |
|------|------|------|
| 字体不是Times New Roman | 用etree创建元素没复制rPr | 复制模板行的rPr |
| 字号不是10pt | 没设置sz=20 | 设置sz=20 |
| 不是红色 | 没设置color=FF0000 | 设置color=FF0000 |
| 行距1.5 | 默认行距 | 设置spacing line=240 |
| "复合主键"没加粗 | 没设置b=1 | 设置b=1 |

### DDL类型映射（PostgreSQL）

| Word数据类型 | 映射类型 | 说明 |
|-------------|---------|------|
| S1/S2/S3 | varchar(n) | 字符串类型 |
| N | numeric(p,s) | 数字类型 |
| D | date | 日期类型 |
| DT | timestamp | 日期时间类型 |
| L | varchar(1) | 逻辑类型！**不能映射为 l**，PostgreSQL不支持l类型 |

**注意**：`L`（逻辑/布尔）类型必须映射为 `varchar(1)`，而不是 `l` 或 `boolean`。因为Greenplum中T/F是用字符串存储的，不是布尔类型。

### 修订记录SQL错误

| 错误 | 原因 | 修复 |
|------|------|------|
| 日期格式不对 | 空格代替T | 用ISO格式yyyy-MM-dd'T'HH:mm:ss |
| 版本号不对 | 没按历史格式 | V6.0.{yymmddHHMMSS} |
| datasetName是英文 | 填了表名 | 填中文名 |
| business_id超长 | 合并行字段名太长 | 拆分后缩短 |
| 缺少分类记录 | 没生成datasetCategory | 补充3条分类 |
| 缺少叶子记录 | 只有dataset没有datasetElement | 补充所有字段 |


## 项目编码规则

### 编码格式

```
PRJ-{3位序号}-{大写拼音简称}
```

### 已知项目编码

| 项目文件夹 | project_code |
|-----------|-------------|
| 001 深圳市罗湖区妇幼保健院 | PRJ-001-SZLH |
| 002 北京电子病历共享工程二期 | PRJ-002-BJDZ |
| 003 北京基层社区平台 | PRJ-003-BJJC |
| 004 郑州市区域平台项目 | PRJ-004-ZZ |
| 005 张家港市区域平台项目 | PRJ-005-ZJG |
| 006 盐都区区域平台项目 | PRJ-006-YD |
| 007 六合区区域平台项目 | PRJ-007-LH |
| 008 如东市区域平台项目 | PRJ-008-RD |
| 009 斗门区区域平台项目 | PRJ-009-DM |
| 010 浙江省电子健康档案项目 | PRJ-010-ZJ |
| 011 阳泉市区域平台项目 | PRJ-011-YQ |
| 012 汉中市区域平台项目 | PRJ-012-HZ |
| 013 武汉市疫情分析平台 | PRJ-013-WH |
| 014 安徽区域标准规范 | PRJ-014-AH |
| 015 岳阳市区域平台项目 | PRJ-015-YY |
| 016 马鞍山市区域平台项目 | PRJ-016-MAS |

---

## 前端代码规范

### 文件命名规则

前端代码文件名必须和后端保持一致：
- 后端表名：`base_ins_exam_item` → 前端文件名：`BaseInsExamItem*.vue/js`
- 后端Entity名：`BaseInsExamItem` → 前端Service名：`BaseInsExamItemService`
- 后端Controller路径：`/api/bms/ins-exam-item` → 前端API调用路径保持一致

### 功能模块范围

根据需求确定需要哪些前端模块：
- **目录维护模块**：用于维护基础目录数据（新增/编辑/删除）
- **映射模块**：用于维护数据映射关系（医院项目→平台项目）

如果需求只涉及映射功能，则只需要映射模块，不需要目录维护模块。

### 文件结构示例

```
src/
├── apis/
│   └── masterData/
│       └── terminology/
│           ├── {TableName}Service.js      # API服务
│           └── {TableName}MappingService.js  # 映射API服务（如有）
└── views/
    └── standard/
        ├── {tableName}Catalog.vue         # 目录维护页面（如有）
        └── {tableName}Mapping.vue         # 映射页面
```

### 多套映射关系的处理

如果一个表需要维护多套映射关系（如检查检验项目→收费项目、检查检验项目→互认项目）：
- 可以在同一个页面使用Tab切换
- 或者创建多个映射页面
- 根据业务需求决定

---

## 常见错误清单

### 修订记录SQL错误

| 错误 | 原因 | 修复 |
|------|------|------|
| 缺少元数据记录 | 只添加了datasetElement | 新字段需要同时添加metadata和datasetElement |
| 元数据重复添加 | item_id等非公共字段被去重 | 只有sys_soid、org_code等公共字段才去重 |
| 数据集缺少seqNo | 数据集记录没有序号 | 必须包含seqNo，且和文档顺序一致 |
| 修订摘要太模糊 | 只写"删除4个字段" | 必须具体列出字段名和中文名 |
| business_id超长 | 合并行字段名太长 | 拆分后缩短 |

### 前端代码错误

| 错误 | 原因 | 修复 |
|------|------|------|
| 文件名和后端不一致 | 后端调整了命名但前端没改 | 检查后端表名/Entity名，保持前端一致 |
| 添加了不需要的模块 | 需求只需要映射，却加了目录维护 | 根据需求确定功能范围 |
| API路径不一致 | 前端路径和后端Controller不匹配 | 检查后端@RequestMapping路径 |

---

## 日期格式

```sql
-- 正确：ISO格式带T
'2026-07-07T16:58:33'

-- 错误：空格分隔
'2026-07-07 16:58:33'
```

Jackson反序列化要求ISO格式，空格分隔会导致：
```
Cannot parse date "2026-07-07 16:58:33": while it seems to fit format 'yyyy-MM-dd'T'HH:mm:ss.SSSX', parsing fails
```

## 版本号格式

```sql
-- 公版
'V6.0.260707152022'

-- 项目化（含项目编码）
'V6.0.PRJ-001-SZLH.260707152022'
```

格式：`V6.0.{project_code}.{yymmddHHMMSS}`（项目化）或 `V6.0.{yymmddHHMMSS}`（公版）

## 数据集名称（datasetName）

**必须使用中文名！** 不能使用英文表名。

```json
// 正确
{"datasetName": "血透机构信息表"}

// 错误
{"datasetName": "T_HD_HOSPITAL"}
```

## 字段长度限制

- `business_id` 字段是 `varchar(64)`，拼接后的ID（如 `winning-plat-01-T_HD_STAFF_LOGIN-PERMANENT_TYIN_DATDATEOUT_DADATE`）可能超长！
- 删除合并行后要确保修订记录SQL中不再包含超长ID

---

## 目录结构

```
data-model-revision/
├── SKILL.md ← 本文件
├── references/
│   ├── 6.0-spec.md ← 6.0版本详细规范
│   └── common-errors.md ← 常见错误清单
└── scripts/
    └── revise_record_generator.py ← 修订记录生成脚本
```