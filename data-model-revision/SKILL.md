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
  version: 2.1.2
  changes:
    - "v2.1.2: elementCode 大小写规则——跟随标准文档字段英文名（文档大写则大写、小写则小写，不做任何转换）；bms-revise-record-spec.md 相应字段说明已更新（原先『数据库列名，小写』的描述作废）"
    - "v2.1.1: 注释规范彻底统一——废除『简式/详式二选一』，统一采用详细式字段项[代码,填报要求,数据类型,表示格式,…]（仅代码必填，无属性时只写代码，非另一套格式）；修订记录头部统一为 /* */ 块（不再有单条三行式）；SKILL 正文加『正确优先、不靠校验兜底』原则；重复校验块已删"
    - "v2.1.0: 注释规范补『字段项详细式语法[代码,填报要求,数据类型,表示格式,…]』与『批量排版』（同表加/删多字段顿号合一行、修改字段逐行）；校验脚本 check_comment_consistency.py 新增字段项语法 + 批量排版规则；示例改用张磊真实样例（INP_DISCHARGE/TELEMED_* 等）"
    - "v2.1.0: 新增《注释规范（DDL 与修订记录统一约束）》——四类操作（加字段/加表/修改/删除）统一变更描述模板、DDL 与修订记录注释结构、summary=头部清单逐字一致、配套一致性铁律（含物理落地差异的唯一例外）；新增 scripts/check_comment_consistency.py 自动校验（生成后必跑）；修正『新增字段统一 null』误述为『以数据模型定义为准』"
    - "v2.0.1: 修正Flyway铁律——base_data CSV 是初始化种子、只读不可变，基础数据变更一律走修订记录（标准升级模块升级后写入基础数据表），绝不改动CSV；新增『需求号规则』（修订记录必填需求号，无则主动追问）与『两条增量流程』架构说明"
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

## 绝对规则：Flyway 增量脚本（禁止修改历史）

所有标准修订产出的脚本**必须**是**增量脚本**，**严禁修改任何已经提交/执行过的历史脚本**。这是 Flyway 的硬性约束——历史版本号一旦执行就会记录在 `flyway_schema_history`，回改历史文件会导致校验失败、Flyway 无法正常执行。

- **DDL 脚本**（`edsm_sql/{库类型}/` 下的 `V{YYYYMMDDHHMMSS}__*.sql`）：每次变更生成**新的**版本化文件，**绝不**回改已有文件。
- **修订记录脚本**（`system_sql/rhdp_app/postgresql/` 下的 `V*__insert_revise_record_*.sql`）：同理，新增版本号文件，不改动已存在的修订记录脚本。
- **数据标准基础数据 CSV（`base_data/*__*.csv`）＝初始化种子，只读、不可变**：
  - 这些 CSV 仅在**系统初始化**时由 `BaseDataInitServiceImpl` 一次性灌入基础数据表（`edsm_dataset_element` / `edsm_metadata` / …），**之后迭代更新绝不动它，也不追加增量 CSV**。
  - 初始化之后的**基础数据变更**（新增/修改数据集元素、元数据、值域等）→ 一律走**修订记录**流程（见下方"修订记录脚本"），由"标准升级模块"将修订记录升级后写入基础数据表。**不要**通过改 CSV 或新建增量 CSV 来表达基础数据变更。
- **修订记录脚本（`system_sql/rhdp_app/postgresql/` 下的 `V*__insert_revise_record_*.sql`）＝基础数据增量的唯一正确载体**：
  - 每次基础数据变更生成**新的**版本化 INSERT 脚本（不改动已存在的修订记录脚本），向 `edsm_revise_record` + `edsm_revise_detail` 插入记录。
  - 在系统"标准升级模块"执行"升级修订记录"时，`DataStandardReviseServiceImpl` 解析 `revise_detail.revise_after` JSON 并 **INSERT/UPDATE 到对应的基础数据表**（如 `edsm_dataset_element`），完成基础数据的增量更新。**需求号必填**（见下方"需求号规则"）。
- **基础数据同步脚本（`system_sql/rhdp_dw/greenplum/` 的 DML）**：新增同步逻辑用**新的增量脚本**表达，不回改原始文件。
- **参考同目录既有脚本**：生成/增加新脚本（`V*.sql`、DML）前，先 `Read` 同目录下已有的同类脚本，复制其**命名风格、SQL 写法与内容约定**（如 `comment on column ... is '...'` 写法、`base_data/*.csv` 的列顺序与表头）；但**注释头统一用 `bms-script-spec.md`《注释规范》的 `/* */` 块格式，不套用旧脚本里的 `-- 集合:` / `-- 需求:` 头注释**，避免与既有历史脚本的格式混用。
- 任何情况下都**不允许**为"图省事"去编辑历史 `V` 文件或原始 CSV。若历史脚本有问题，应**新增一个修复脚本**（版本号更新的新文件）来纠正，而不是改历史文件。

> 详见 `references/bms-script-spec.md`。

---

## 需求号规则（每条修订记录必须携带）

生成/编写 **修订记录脚本**（`system_sql/rhdp_app/postgresql/V*__insert_revise_record_*.sql`）时，`edsm_revise_record.require_no`（以及文件名中的 `{需求号}`）**必须**填写真实的**需求号**（如 `234683`），不得留空，也不得用一句描述性文字（如"数据标准修订-增加记录状态字段"）代替。脚本头部**不写** `-- 需求:` 注释行。

- 用户在对话中给出的需求号直接使用；本系统修订通常都带需求号。
- **主动追问（硬性纪律）**：如果在生成修订记录时发现**没有需求号**，**必须主动询问用户**要需求号，不要自行编造、不要跳过、不要拿描述性文字顶替。缺需求号会导致修订记录在"标准升级模块"里无法与需求关联、无法追溯。
- 需求号是本系统修订追溯的主键之一。

> 已记录的需求号（非穷举，供参考）：`234683`（STATUS 记录状态字段修订，CVA-0166）。

---

## 数据标准修订的两条增量流程（核心架构）

本系统的标准修订有两条彼此独立的增量通道，生成脚本前必须先判断变更属于哪一类：

### 流程一：基础数据变更（数据集元素 / 元数据 / 值域等）→ 修订记录
1. **初始化**：基础数据由 `base_data/*__*.csv` 在系统初始化时一次性灌入（种子数据，**之后不再动**）。
2. **迭代变更**：要新增/修改基础数据 → 写 `system_sql/rhdp_app/postgresql/V*__insert_revise_record_*.sql`，向 `edsm_revise_record` + `edsm_revise_detail` 插入记录（`revise_detail.revise_after` 为变更后的完整 JSON，含 `elementId`/`metadataId` 等）。
3. **升级应用**：在系统"标准升级模块"执行"升级修订记录"，`DataStandardReviseServiceImpl` 解析 `revise_after` 并 **INSERT/UPDATE 到基础数据表**（如 `edsm_dataset_element`）。
4. **要点**：CSV 只负责"第一次"；之后所有基础数据增量都走修订记录，绝不动 CSV、也不新建增量 CSV。

### 流程二：表结构变更（加字段 / 加表 / 改列）→ 增量 DDL
1. **初始化**：建表 DDL 在 `edsm_sql/{库类型}/V{初始}__create_*.sql`（已提交，不动）。
2. **迭代变更**：要改表结构 → 在 `edsm_sql/{库类型}/` 下新增 `V{新时间戳}__*.sql` 增量脚本（Greenplum 用 `do $$` 幂等判断列存在再 ADD；Doris 按 reg-ddl-generator v4.6.0 Doris 规范生成，裸 ALTER + 同表合并单条）。
3. **升级应用**：由"标准升级模块"的 Flyway 对 `edsm_sql/{库类型}` 目录执行增量迁移，落到对应数据源。
4. **要点**：表结构增量永远是新文件，绝不回改历史 `V` 文件。

> **判断口诀**：**"动数据（元素/元数据/值域）走修订记录，动表结构走增量 DDL，CSV 只初始化一次。"**

---

## 核心工作流

> 完整链路如下，**阶段1-5** 在本文档下方各有专章详述；前置/委托/收尾三个环节为衔接步骤，不单独设章。

```
[前置] 需求分析 → 解析需求、确定版本、匹配文档路径
阶段1: PDF数据提取 → 从PDF标准文档提取表结构
阶段2: Word文档修订 → 填充表格数据、设置格式
阶段3: 逐行核对 → 手工逐行比对PDF与Word（核心！不可跳过）
[委托] DDL脚本生成 → 调用 reg-ddl-generator（见该 Skill）
阶段4: 修订记录SQL生成 → edsm_revise_record + edsm_revise_detail
阶段5: 修订记录Word维护 → 复制行→填充→新numId
[收尾] 生成summary.md → 输出修订总结到{DOCS_DIR}/summary.md
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

**适用场景**：将区域标准规范与省平台/国家平台标准规范比对，按"只增不减不更名"原则修订。

**核心算法**：`省字段名 → normalize → 同义词替换 → 去后缀(TECH_SUFFIXES) → core`；双方 core 比较（精确 > 同义词核心 > 同义包含≥30% > 同义词全名）。

**关键规则**：
- **跨类别禁止**：代码/编码类 ≠ 名称/日期/金额/标志类（同核心例外）
- **包含比限制**：被包含部分/总长度 ≥ 30% 才接受
- **短核心兜底**：核心≤3字时回退到同义词全名匹配

**可复用知识库**：TECH_SUFFIXES（约60个技术后缀，通用）/ SYNONYM（约500对同义词，医疗行业通用）/ BLOCK_LIST（少量字段特定，每文档需过一遍）

> 技术后缀完整列表、同义词示例、`sem_cat` 语义类别判断、`match` 匹配函数等详细实现见 [references/semantic_matching_engine.md](references/semantic_matching_engine.md)。
> **可直接执行的完整引擎（V8）见 `references/semantic-match-engine.py`** —— 实际使用以该 .py 为准，文档为精简示例。

---

### 颜色规范

| 判定 | 行背景色 | 文字颜色 |
|------|---------|---------|
| 满足 | 浅绿 #c8e6c9 | 深绿 #2e7d32 |
| 修改 | 浅橙 #ffe0b2 | 深橙 #e65100 |
| 新增 | 浅粉 #ffcdd2 | 深红 #c62828 |

---

## 阶段1：PDF数据提取（重要经验）

**工具选择**：MinerU（mineru-open-api）⭐⭐⭐⭐⭐ 质量最佳，缺点是分页会拆分表格；pdftotext ⭐⭐⭐（字段名截断、合并行、噪声多）；OCR ⭐⭐⭐（中文识别一般、速度慢）。**推荐**：MinerU 提取主数据 + 人工核对补充。

**MinerU 分页问题（关键！）**：按页提取会把跨页表格拆成多个 HTML 片段，导致同一表数据分割、部分字段丢失（如 T_HD_PATIENT_QUIT 只剩 15 个字段）、继承表字段不完整。应对：① 提取所有 HTML 表格；② 继承表用基表数据补充；③ pdftotext 截断的字段名对照 PDF 原文修复。

> pdftotext 导致的**字段名截断对照表**（约 48 条）与**合并行修复清单**（4 条）见 [references/pdf_extraction.md](references/pdf_extraction.md)。

---

## 阶段2：Word文档修订（核心经验）

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

## 阶段3：逐行核对（最重要！不可跳过！）

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

## 阶段4：修订记录SQL生成（重要经验）

### 修订摘要格式（summary字段）

> **注释规范以 `references/bms-script-spec.md`《注释规范（DDL 与修订记录统一约束）》为准**。核心规则：
> - 字段写在 `[]` 内，分量用半角逗号分隔，顺序为 `[字段代码, 填报要求, 数据类型, 表示格式, 定义, 值域, 约束, 默认值]`（仅字段代码必填，其余有值才写）；表英文名 `]` 后**不加空格**。
> - 四类操作 + 值域：`{表}[{EN}]新增字段：…` / ` - 新增表` / `修改字段：…（旧→新）` / `删除字段：…`；值域用 `值域-{代码表}[{CVA}]新增值：…` / `值修改为：…`。
> - **批量排版**：同表**加/删**多个字段用**顿号合一行**；**修改**字段**不得合在一行**，每个字段独立一行。
> - **DDL 脚本与修订记录脚本的变更描述必须逐字一致**（同一份 `/* */` 清单）。

**规则**：
1. `summary` **必须等于**修订记录脚本头部 `/* */` 编号清单，多条用 `\n` 连接，单条即那一行描述。
2. 条数与顺序、文字必须与配套 DDL 顶部清单一致。
3. 加/删字段顿号合并；修改字段逐行。

```sql
-- 正确示例（与 DDL 顶部 /* */ 清单逐字一致）：
'1. 出院登记信息[INP_DISCHARGE]新增字段：日间手术病例标志[DAY_OP_FLAG,O,S3,N1]\n2. 远程会诊[TELEMED_CONSULT]删除字段：流程状态[PROCESS_STATUS_CODE]\n3. 远程检验[TELEMED_LAB]修改字段：检验类别代码[LAB_CATEGORY_CODE]（值域 CVA-0199→CT04.50.001）\n4. 远程检验[TELEMED_LAB]修改字段：标本类型代码[SPECIMEN_TYPE_CODE]（值域 CVA-0200→CVA-0255）\n5. 值域-编制情况代码表[CVA-0165]新增值：6[核酸岗]、7[员额岗]\n6. 新增表：机构数据统计表[ORG_STATISTICAL]\n7. 值域-双向转诊流程状态代码[CVA-0282]值修改为：01[已提交]、02[转出审核通过]、03[转出审核驳回]、04[转入审核通过]、05[转入审核驳回]、06[已接诊]、07[已取消]'

-- 错误示例：
'1. 增加字段 STATUS'                              -- 缺表中文名/英文名、措辞与 DDL 漂移
'远程检验[TELEMED_LAB]修改字段：A[..]（…）、B[..]（…）'  -- 修改字段不得用顿号合并，应每行一个
```

**正确优先（一次写对，不靠校验兜底）**：生成 DDL / 修订记录脚本时，**直接按 `references/bms-script-spec.md`《注释规范》把注释写对**——四类操作模板、字段项详细式 `[代码,填报要求,数据类型,表示格式]`、批量排版（加/删顿号合一行、修改逐行）、DDL↔修订记录逐字一致，全部在落盘前就满足。把校验脚本当成"最后一道门禁"，而不是"写错了再改"的循环。**任何情况下都不要把不合规的注释先写进去再等校验报错**。

**生成后必跑校验**（门禁，不通过不得交付）：

```bash
python3 scripts/check_comment_consistency.py \
    --ddl  edsm_sql/doris/V{ts}__xxx.sql edsm_sql/greenplum/V{ts}__xxx.sql \
    --revise system_sql/rhdp_app/postgresql/V{ts}__insert_revise_record_{需求号}.sql
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

### 元数据（metadata）添加规则（一对一，废除共用）

**核心原则（绝对规则）**：每个数据集元素（datasetElement）对应**唯一一个**元数据（metadata），二者**一一对应**。

- **废除"元数据共用 / 去重"逻辑**：不再有任何"公共字段共用同一份元数据"的例外。
- **元数据的代码（metadataCode）与数据集元素的唯一标识（element_id）保持一致**：
  - `element_id` = `{standard_id}-{数据集代码}-{字段代码}`（如 `winning-plat-02-BASE_EMPLOYEE-STATUS`）
  - `metadata_id` = `element_id`（元数据主键 = 元素唯一标识）
  - `metadata_code` = `element_id`（与数据集元素唯一标识一致，便于追踪）
  - `datasetElement.metadata_id` = 自己的 `element_id`（指向专属元数据）
- **同一字段名出现在不同表/数据集中，各自生成独立的元数据**。例如 `winning-plat-02-BASE_DEPARTMENT-STATUS` 与 `winning-plat-02-BASE_EMPLOYEE-STATUS` 是两条**不同**的元数据，互不共享。
- **管理优势**：元数据 ID 直接由元素唯一标识推导得出，**不再需要去历史元数据里查 ID**。

**历史已存在的元数据**：不做任何改动，保持原样。本规则仅对**本次及以后**的新增 / 修订生效。

**元数据字段结构**：
```json
{
  "metadataId": "winning-plat-02-{数据集代码}-{字段名}",
  "namespaceId": "1",
  "externalId": "<由 generator 按 external-id-spec.md 规则自动生成，禁止留空>",
  "metadataCode": "winning-plat-02-{数据集代码}-{字段名}",
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
  "elementId": "winning-plat-02-{数据集代码}-{字段名}",
  "datasetId": "winning-plat-02-{数据集代码}",
  "metadataId": "winning-plat-02-{数据集代码}-{字段名}",  // 引用自己的专属元数据（= element_id）
  "elementCode": "{字段名}",  // 与文档字段英文名大小写一致，不转换
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

**注释头统一遵循 `references/bms-script-spec.md`《注释规范（DDL 与修订记录统一约束）》**：生成前先 `Read` 一条最近的同类脚本，参考其**命名风格、SQL 写法、JSON 结构**，但**注释头必须用统一的 `/* */` 编号清单**（不套用旧脚本里的 `-- 集合:` / `-- 需求:` 头注释）：

**强制格式（头部 `/* */` 清单与配套 DDL 逐字一致）**：

```sql
/*
1. (个人)基本信息[RESIDENT_ARCHIVE]新增字段：老年人健康管理等级代码[ELDER_HEALTH_LEVEL_CODE,O,S3,N1]
*/

insert into edsm_revise_record(revise_id,standard_id,version,require_no,summary,is_standard,published_at,is_upgraded,is_del,created_at)
values('{UUID}','winning-plat-02','{版本号}','{需求号}','1. (个人)基本信息[RESIDENT_ARCHIVE]新增字段：老年人健康管理等级代码[ELDER_HEALTH_LEVEL_CODE,O,S3,N1]',1,'{时间戳}',0,0,'{时间戳}');

/* (个人)基本信息[RESIDENT_ARCHIVE]新增字段：老年人健康管理等级代码[ELDER_HEALTH_LEVEL_CODE,O,S3,N1] · 元数据 */
insert into edsm_revise_detail(...)values(...);

/* (个人)基本信息[RESIDENT_ARCHIVE]新增字段：老年人健康管理等级代码[ELDER_HEALTH_LEVEL_CODE,O,S3,N1] · 数据集元素 */
insert into edsm_revise_detail(...)values(...);
```

**要点**：
- 头部只保留 `/* */` 编号清单，**不写** `-- 集合:` / `-- 需求:` / `-- 字段:` / `-- 说明:` 等辅助注释行；需求号仅体现于文件名与 `require_no` 列。
- INSERT 语句必须单行、紧凑，revise_after 用单行 JSON（字段名驼峰、日期 ISO 带 T）。
- `summary` 必须等于头部 `/* */` 清单（多条用 `\n` 连接），禁止与清单措辞或顺序不同。
- 同目录下 DDL（`edsm_sql/`、`system_sql/rhdp_dw/greenplum/`）和 CSV（`base_data/`）脚本也遵循同样原则：**先看同目录已有文件，复制其命名风格与 SQL 写法，但注释头统一按本规范**。

---

## 阶段5：修订记录Word文档维护

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
| 缺少元数据记录 | 只添加了datasetElement | 新字段需要同时添加metadata和datasetElement |
| 元数据共用/串号 | 不同表的同名字段引用了同一份元数据 | 元数据必须一对一：每个 datasetElement 用 element_id 生成专属 metadata，metadataCode=element_id，绝不按字段名共用 |
| 数据集缺少seqNo | 数据集记录没有序号 | 必须包含seqNo，且和文档顺序一致 |
| 修订摘要太模糊 | 只写"删除4个字段" | 必须具体列出字段名和中文名 |

### 前端代码错误

| 错误 | 原因 | 修复 |
|------|------|------|
| 文件名和后端不一致 | 后端调整了命名但前端没改 | 检查后端表名/Entity名，保持前端一致 |
| 添加了不需要的模块 | 需求只需要映射，却加了目录维护 | 根据需求确定功能范围 |
| API路径不一致 | 前端路径和后端Controller不匹配 | 检查后端@RequestMapping路径 |


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

## externalId生成规则

数据元标识符 `external_id` 的**完整规则、序号来源（四表 CSV 列映射）、索引文件与示例**已整理为专章：**`references/external-id-spec.md`**，以该专章为准。核心公式：

```
HDS{standard_seq:02d}{category_seq:02d}.{dataset_seq:03d}.{element_seq:03d}
```

- 生成脚本时由 `revise_record_generator.py` 的 `compute_external_id()` **自动计算填充**，**禁止留空 `""` 或手写随意值**。
- 序号数据源为 Skill 内的 `scripts/external_id_index.json`（由 base_data 的 4 个 CSV 全量构建，覆盖全部 standard、含 winning-plat-01；bms 项目自带的 `base_data/edsm_index.json` 仅含 winning-plat-02、不完整，不可作为其唯一来源）。

---

## Doris DDL生成规则

> **唯一来源**：Doris DDL 统一委托 **`reg-ddl-generator` Skill**（v4.6.0，`SKILL.md`《Doris 脚本生成规范》 + `references/ddl-templates.md`《Doris 模板》）生成，**本 Skill 不另立写法**。以下仅摘要核心要点，细节以 reg-ddl-generator 为准。

**生成路径**：先按 PostgreSQL 方言生成 probe（`--db postgresql --case lower --no-tran-log --no-public-fields`），再用 `scripts/convert_doris.py` 自动转换。

### 字符串长度 ×4 规则（用户 2026-08-28 确定）

Doris 存储 UTF-8 中文，**1 个汉字 3 字节、1 个特殊字符 4 字节**；标准文档长度按【字符数】控制，脚本长度必须按【字节数】定义 → `varchar(n)`/`char(n)` 统一 **×4**（如文档 `AN..100` → `varchar(100)` → Doris `varchar(400)`）。

- 由 `convert_doris.py` **转换时自动执行**，probe 阶段保持文档原始长度，**禁止提前手动 ×4**（否则变 ×16）。
- 最大原始 4000 → 16000，未超 Doris 上限 65533（溢出场景另议）。
- 自检：输出中所有 varchar/char 长度必须能被 4 整除（`verify_sql.py --db doris` 强制检查）。

### 语法差异（GP → Doris，由转换器处理）

> 完整的 Greenplum → Doris 语法差异对照表、同表合并规则、转换后 SQL 示例见 [references/doris_ddl.md](references/doris_ddl.md)。
> 转换由 `scripts/convert_doris.py` 自动完成，该表供人工核查与排错参考。

**校验**：`verify_sql.py <输出.sql> --db doris`（查 numeric/timestamp 残留 + 字符串长度非 4 倍数）。

---

## 目录结构

```
data-model-revision/
├── SKILL.md ← 本文件
├── bypass.md ← 非交互/流水线模式说明（阶段1-5 全链路全自动）
├── skill-contract.md ← Skill 输入输出契约
├── references/
│   ├── 6.0-spec.md ← 6.0版本详细规范（business_id格式、基础数据检查逻辑）
│   ├── bms-script-spec.md ← BMS脚本规范（Flyway增量铁律、DDL/修订记录/CSV目录约定）
│   ├── bms-revise-record-spec.md ← 修订记录脚本规范（metadata/datasetElement一对一模板）
│   ├── external-id-spec.md ← 数据元标识符(external_id)生成规则专章（HDS编号公式、四表序号来源、索引文件）
│   ├── revise-record-value-set-spec.md ← 值域修订记录规范
│   ├── revise-record-schema.md ← 修订表(edsm_revise_record/detail)结构说明
│   ├── common-errors.md ← 常见错误清单
│   ├── semantic-match-engine.py ← 标准比对语义匹配引擎（可执行，V8）
│   ├── semantic_matching_engine.md ← 语义匹配引擎技术方案（知识库定义 + 匹配函数详解）
│   ├── pdf_extraction.md ← 阶段1 PDF提取详细经验（字段名截断对照表、合并行修复）
│   └── doris_ddl.md ← Doris DDL 语法差异对照（GP → Doris，转换器处理）
├── scripts/
│   ├── revise_record_generator.py ← 修订记录生成脚本（核心，被本Skill调用）
│   ├── check_comment_consistency.py ← 注释一致性检查（DDL↔修订记录，生成后必跑）
│   ├── （已移除 ddl_generator.py ← 历史遗留，2026-08 归档，DDL统一委托 reg-ddl-generator）
│   ├── submit_scripts.py ← 脚本提交辅助
│   └── verify_word_pdf.py ← Word/PDF核对辅助
└── templates/
    └── model-revision.yaml ← 流水线配置模板
```

> ⚠️ **DDL 生成入口**：本 Skill 的 DDL 脚本统一**委托 `reg-ddl-generator` Skill** 生成（见核心工作流 [委托] DDL脚本生成 环节）。
> 本目录下的 `scripts/ddl_generator.py` 为历史遗留（功能与 reg-ddl-generator 重复），已于 2026-08 归档移出，不再使用。
> 新增/修改 DDL 时，直接调用 reg-ddl-generator，不要在此手写 DDL 生成逻辑。