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

> **⚠️ 执行省平台/国家平台标准比对修订前必读**：[references/scenario-b-standard-compare.md](references/scenario-b-standard-compare.md)
> 含：核心修订原则、值域修订原则、比对流程、索引映射规则（指纹匹配）、匹配方法优先级、业务逻辑推导规则、关联路径、三条地址对应关系、名称字段规则、约束检查规则、修订单条件、修订汇总输出格式、交付物、通用语义匹配引擎、颜色规范。
>
> **场景A（常规数据模型修订）不走此流程**，直接按「核心工作流」阶段1-5 执行。

## 阶段1：PDF数据提取（重要经验）

**工具选择**：MinerU（mineru-open-api）⭐⭐⭐⭐⭐ 质量最佳，缺点是分页会拆分表格；pdftotext ⭐⭐⭐（字段名截断、合并行、噪声多）；OCR ⭐⭐⭐（中文识别一般、速度慢）。**推荐**：MinerU 提取主数据 + 人工核对补充。

**MinerU 分页问题（关键！）**：按页提取会把跨页表格拆成多个 HTML 片段，导致同一表数据分割、部分字段丢失（如 T_HD_PATIENT_QUIT 只剩 15 个字段）、继承表字段不完整。应对：① 提取所有 HTML 表格；② 继承表用基表数据补充；③ pdftotext 截断的字段名对照 PDF 原文修复。

> **⚠️ 用 pdftotext 提取表结构后必读**：[references/pdf_extraction.md](references/pdf_extraction.md)
> 若发现字段名疑似截断（如 `EQUIPMENT_BR`、`ADMISSION_TI`）或多列合并成一行，对照其中的**字段名截断对照表**（约 48 条）与**合并行修复清单**（4 条）修复。

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

> **⚠️ 生成修订记录 SQL（`edsm_revise_record` + `edsm_revise_detail`）前必读**：[references/stage4-revise-record-sql.md](references/stage4-revise-record-sql.md)
> 含：修订摘要格式（summary字段）、完整修订记录内容、数据集序号（seqNo）确定规则、元数据（metadata）添加规则、SQL脚本格式。
>
> **核心红线**：元数据必须**一对一** —— 每个 `datasetElement` 用 `element_id` 生成专属 metadata，`metadataCode=element_id`，**绝不按字段名共用**。

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

> **何时读**：执行标准比对（场景B）时，语义匹配出现**误匹配/可疑映射**，或需了解 V1-V8 迭代经验时读。
> **必读** [references/standard-compare-errors.md](references/standard-compare-errors.md)。
>
> 含：语义匹配误匹配案例表（V1-V8迭代）、语义匹配引擎最佳实践、多值SEM映射（**已弃用**）、可复用知识库体系、新增字段合理性判断、版本迭代记录。

## 常见错误清单

> **何时读**：生成脚本或修订记录**报错时**对照排查。
> **必读** [references/error-troubleshooting.md](references/error-troubleshooting.md) —— 按环节分类：数据错误 / 格式错误 / DDL类型映射（PostgreSQL）/ 修订记录SQL错误 / 前端代码错误。
>
> 注：`references/common-errors.md` 是 **CVA 值域编码专项**错误清单，与本表用途不同，两者需分别对照。

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

**生成路径**：先按 PostgreSQL 方言生成 probe（`--db postgresql --case lower --no-tran-log --no-public-fields`），再用 `reg-ddl-generator/scripts/convert_doris.py` 自动转换。

> ⚠️ **脚本归属**：`convert_doris.py` / `verify_sql.py` 属于 **`reg-ddl-generator`**（本 Skill 的 `scripts/` 下没有这两个文件）。
> 本节提到的这两个脚本路径，均指 `reg-ddl-generator/scripts/` 下。

### 字符串长度 ×4 规则（用户 2026-08-28 确定）

Doris 存储 UTF-8 中文，**1 个汉字 3 字节、1 个特殊字符 4 字节**；标准文档长度按【字符数】控制，脚本长度必须按【字节数】定义 → `varchar(n)`/`char(n)` 统一 **×4**（如文档 `AN..100` → `varchar(100)` → Doris `varchar(400)`）。

- 由 `convert_doris.py` **转换时自动执行**，probe 阶段保持文档原始长度，**禁止提前手动 ×4**（否则变 ×16）。
- 最大原始 4000 → 16000，未超 Doris 上限 65533（溢出场景另议）。
- 自检：输出中所有 varchar/char 长度必须能被 4 整除（`reg-ddl-generator/scripts/verify_sql.py --db doris` 强制检查）。

### 语法差异（GP → Doris，由转换器处理）

> **何时读**：Doris 转换结果报错、或需人工核对转换是否正确时读 [references/doris_ddl.md](references/doris_ddl.md)。
> 含 Greenplum → Doris 语法差异对照表、同表合并规则、转换后 SQL 示例。转换由 `reg-ddl-generator/scripts/convert_doris.py` 自动完成。

**校验**：`reg-ddl-generator/scripts/verify_sql.py <输出.sql> --db doris`（查 numeric/timestamp 残留 + 字符串长度非 4 倍数）。

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
│   ├── scenario-b-standard-compare.md ← 【场景B】省平台标准比对修订全流程（原则/索引映射/匹配方法，执行前必读）
│   ├── stage4-revise-record-sql.md ← 【阶段4】修订记录SQL生成（summary/seqNo/metadata一对一/SQL格式，生成前必读）
│   ├── standard-compare-errors.md ← 【场景B】语义匹配误匹配案例（V1-V8迭代）+ 版本迭代记录
│   ├── error-troubleshooting.md ← 报错排查表（数据/格式/DDL类型映射/修订记录SQL/前端，报错时对照）
│   ├── common-errors.md ← CVA 值域编码专项错误清单（与 error-troubleshooting.md 用途不同）
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