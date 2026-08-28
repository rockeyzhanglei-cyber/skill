---
name: reg-ddl-generator
description: |
  【必须触发】Word文档表格转数据库DDL/DML脚本工具。支持Oracle/MySQL/SQL Server/PostgreSQL四库，支持增量模式（识别红色字体标记）和全量模式（不识别红色字体，处理所有表格），生成幂等DDL脚本和标准库DML同步脚本。

  **核心概念**：
  - 增量模式：识别红色字体 → 只处理红色标记的变更（DDL和DML都遵循此规则）
  - 全量模式：不识别红色字体 → 将文档中所有涉及数据集的表格全部生成（DDL和DML都遵循此规则）

  **强制触发场景**（包含以下任一即触发）：
  - 口语化表达："改表"、"加字段"、"表结构改了"、"数据库要改"、"Word转SQL"、"把Word表格转成建表脚本"
  - 正式表述："表结构修订"、"生成DDL"、"建表脚本"、"数据库修订脚本"、"修订记录"、"标准同步"、"数据集同步"
  - 全量场景："生成全量DDL"、"生成完整建表脚本"、"所有表都要建"、"全量脚本"、"不识别红色"
  - 增量场景："识别红色字体"、"红色标记的变更"、"增量脚本"
  - 直接命令："/reg-ddl-generator"
  - 提供Word文档并提到"数据库"、"表"、"字段"、"SQL"等关键词

  **核心能力**：
  - 增量模式：识别红色字体标记的变更，生成CREATE TABLE/ALTER TABLE脚本
  - 全量模式：不识别红色字体，所有表格按新增表处理，生成完整CREATE TABLE脚本
  - DDL和DML可独立选择增量/全量
  - 可选生成edsm_*标准库同步DML
metadata:
  author: 张磊
  version: 4.6.0
  changes:
    - "v4.6.0: Doris 字符串长度 ×4 固化——Doris 存储 UTF-8 中文（1 汉字 3 字节 / 1 特殊字符 4 字节），标准文档长度按【字符数】控制，故转换层自动将 varchar(n)/char(n) 统一 ×4（如 varchar(100)→varchar(400)，最大 4000→16000 未超 Doris 65533 上限）。convert_doris.py 转换时自动执行（上游 PG probe 保持文档原始长度，禁止提前手动 ×4 否则变 ×16）；verify_sql.py --db doris 新增防线：残留长度非 4 倍数的 varchar/char 直接报警"
    - "v4.5.5: verify_sql.py 新增 Doris 防线——支持 --db doris，check_doris_type_compatibility 扫描可执行代码区，若残留 numeric/timestamp 直接报警（提示转 DECIMAL/DATETIME）；/* */ 与 -- 注释先剥离，不会误报变更说明文字"
    - "v4.5.4: Doris 转换修复——convert_doris.py 新增 to_doris_type 映射，PostgreSQL 定点数 numeric(p[,s])→decimal(p[,s])、timestamp→datetime，避免 Doris 报 'mismatched input numeric' 解析错误；Greenplum/PostgreSQL 目标库仍用 numeric（它们支持），仅 Doris 转换层改"
    - "v4.5.3: element_code 大小写规则——跟随标准文档字段英文名（文档大写则大写、小写则小写，不做任何转换）；与 data-model-revision v2.1.2 及 bms-revise-record-spec.md 口径一致"
    - "v4.5.2: 新增Doris脚本规范——建表 distribute by hash(x) buckets 8（不写副本数）、ALTER合并为单条多子句（参考doris/V20260729153107风格）；新增『不确定就问用户，不猜』铁律"
    - "v4.5.1: 注释规范彻底统一——删掉 Skill 内旧的『[字段名,类型(长度),约束]』『修改属性』『字段约束修改为\"M\"』等冲突写法，统一到 data-model-revision/references/bms-script-spec.md《注释规范》唯一来源；字段项改为[代码,填报要求,数据类型,表示格式]；脚本生成规范表改为引用规范、不再重复定义；强调『一次写对，不靠校验兜底』"
    - "v4.5.0: 注释规范补『字段项详细式语法』与『批量排版』（加/删多字段顿号合一行、修改字段逐行），DDL注释风格规范新增变更清单写法；对齐 data-model-revision 示例"
    - "v4.5.0: 注释规范统一到 data-model-revision/references/bms-script-spec.md《注释规范》——四类操作统一变更描述模板（表英文名]后无空格）、本Skill采用详式、DDL与配套修订记录清单必须逐字一致；修正『新增字段统一null』为『默认null，数据模型明确必填带默认值时按模型定义』"
    - "v4.4.5: 修正Flyway铁律——base_data/*__*.csv 是初始化种子、只读不可变，初始化后基础数据变更一律走修订记录（data-model-revision），绝不改动CSV；适用范围由四类收缩为三类（DDL/修订记录/同步脚本）"
    - "v4.4.4: 元数据废除共用/去重逻辑，改为与dataset_element一一对应（metadata_id=metadata_code=element_id）；新增Flyway增量脚本铁律章节（历史脚本不可回改，全部走增量）"
    - "v4.4.3: 修订记录新增版本号格式（公版V6.0.{ts}，项目化V6.0.{project_code}.{ts}）、datasetName用中文、日期格式使用ISO标准（带T分隔符）"
    - "v4.3.8: 步骤3修正为逐个clarify（clarify不支持分组问题）；添加无红色标记时建议切换全量模式的pitfall"
    - "v4.3.7: 修复S2+N..4全角圆点解析bug（全角句点U+FF0E→英文点U+002E）；SKILL.md中选项改为一次性多选模式"
    - "v4.3.5: 修复表名提取逻辑：只提取Heading样式段落的表名，排除Normal样式的说明文字（如'1、必须和...'）"
    - "v4.3.4: 约束显示规则优化：注释中条件必填显示'条件必填'、空白显示'应填'、M显示'必填'；脚本中统一使用NULL（非必填）避免已有数据插入失败"
    - "v4.3.3: 新增中文括号格式表名解析支持（如'献血者基本信息（XZ_XXZJBXX）'）；强化交互原则（用户重调用skill应从头开始）"
    - "v4.3.2: 补充S3代码表类型映射规则（N..3→VARCHAR而非NUMBER）；明确CREATE TABLE语句格式（字段列表多行、主键约束换行）"
    - "v4.3.1: 强化clarify工具限制说明（最多约4选项）；清理重复版本记录"
    - "v4.3.0: 修正DT数据类型映射（Oracle DATE而非TIMESTAMP）；简化DDL注释风格（单行注释、语句不换行、去除分隔线）"
    - "v4.2.0: 新增Greenplum/Flyway迁移脚本支持；添加Word文档修改风险警告和备份强制要求；修正脚本路径指向Hermes技能目录"
    - "v4.1.0: 文档选择改为逐层目录选择方式；所有选项改为Checkbox方式（multiSelect: true）；明确全量和增量模式的含义（增量=识别红色字体，全量=不识别红色字体）"
    - "v4.0.0: 新增全量模式支持，DDL和DML可独立选择增量/全量；交互流程改为Checkbox多选方式"
    - "v3.4.0: 完善脚本生成规范；优化交互流程一次性弹出所有选项"
    - "v3.3.0: 新增表格过滤功能，自动排除非数据库表结构表格（如汇总表、指标表等）"
    - "v3.2.0: 统一脚本生成规范，简化注释，合并多字段到单个begin-end块"
    - "v3.1.0: Oracle DDL模板重构：参考PostgreSQL格式风格"
---
...

---

## Flyway 增量脚本铁律（禁止修改历史）

> **绝对规则**：本工具生成的全部脚本都遵循 Flyway 版本化迁移原则——**历史脚本不可修改，所有修订必须是增量脚本**。

- **只增不改**：已执行过的 `V{时间戳}__*.sql` 历史脚本不允许回改。Flyway 会校验历史文件内容（checksum），改动后执行将失败。
- **适用范围**（以下三类目录的产物全部必须是增量，不回改原文件）：
  1. DDL 升级脚本：`edsm_sql/{库类型}/`（greenplum/oracle/sqlserver/postgresql）—— 表结构变更走这里
  2. 修订记录脚本：`system_sql/rhdp_app/postgresql/`
  3. 基础数据同步脚本：`system_sql/rhdp_dw/greenplum/`
- **基础数据 CSV（`base_data/*__*.csv`）＝初始化种子、只读不可变**：仅在系统初始化时灌入基础数据表，**之后基础数据变更（数据集元素/元数据/值域）一律走修订记录脚本（见上第2条 + data-model-revision Skill），绝不改动 CSV、也不新建增量 CSV**。本工具只生成 DDL/DML，不负责基础数据 CSV。
- **DML 也是增量**：同步脚本同样不可回改，新增逻辑用新文件表达，不修改已提交的旧文件。
- **历史有问题**：若历史脚本/CSV 存在错误，必须写**新的修复脚本/新文件**去修正，而非修改原文件。
- **幂等安全**：增量脚本通过 `not exists (...)` / `where ... is null` 等条件保证重复执行安全；历史已存在的数据**不做任何改动**。
- **参考同目录既有脚本**：生成/增加新脚本（`V*.sql`、CSV、DML）前，先 `Read` 同目录下已有的同类脚本，复制其**命名风格、SQL 写法与内容约定**（如 `comment on column ... is '...'` 写法、`base_data/*.csv` 的列顺序与表头）；但**注释头格式统一用 `data-model-revision/references/bms-script-spec.md`《注释规范》的 `/* */` 块**，不套用旧脚本里的 `-- 集合:` / `-- 需求:` 头注释。

---

## 增量模式与全量模式（v4.1.0）

本工具支持两种生成模式，DDL和DML可独立选择。

### 增量模式（识别红色字体）
- **核心规则**：识别红色字体标记的内容，只处理红色标记的变更
- **DDL生成**：
  - 整表红色 → CREATE TABLE（新增表）
  - 整行红色 → ALTER TABLE ADD COLUMN（新增字段）
  - 部分红色 → ALTER TABLE MODIFY（修改字段属性）
- **DML生成**：仅同步红色标记的表和字段到标准库

### 全量模式（不识别红色字体）
- **核心规则**：不识别红色字体标记，将文档中所有涉及数据集的表格全部处理
- **DDL生成**：所有表格生成CREATE TABLE脚本（完整建表）
- **DML生成**：同步所有表格和字段到标准库

**重要格式校验原则**（用户明确要求）：
- **不自行容错**：如果表示格式不符合规范规则，不自行推断默认长度或类型
- **列出问题字段**：解析完成后，扫描所有字段的表示格式，列出无法识别的给用户查看
- **用户修正文档**：由用户在Word文档中修正表示格式后重新运行，不要自作主张给VARCHAR(n)等假设值
- **AN..\* 不限长度**：映射为大字段类型（Oracle→CLOB, SQL Server→nvarchar(max), PostgreSQL→TEXT等）
- **容错只覆盖字面量变形**：全角点(U+FF0E→U+002E)、不可见字符清理，这些是文档编辑时引入的非语义差异，而非格式语义差异
- 增量模式 = 识别红色字体 → 只处理红色内容
- 全量模式 = 不识别红色字体 → 处理所有表格
- DDL语句和DML语句都遵循这个规则

### 组合选择
用户可以独立选择：
| DDL模式 | DML模式 | 说明 |
|--------|--------|------|
| 增量 | 不生成 | 仅生成红色变更的DDL（原有默认行为） |
| 增量 | 增量 | 生成红色变更的DDL + DML同步 |
| 全量 | 不生成 | 所有表生成完整DDL |
| 全量 | 全量 | 所有表生成完整DDL + DML同步 |
| 全量 | 增量 | 所有表生成完整DDL，但DML只同步红色变更 |
| 增量 | 全量 | 仅红色变更生成DDL，但DML同步所有表 |

---

## 预设文档目录（v4.0.0）

为了方便快速选择文档，预设了三个常用目录：

| 目录标识 | 目录路径 | 说明 |
|---------|---------|------|
| 5.x | `/Users/zhanglei/winning/tfs2018/RDA-01-标准规范/02 V5.5/01 产品文档/02 标准规范/库表接入规范` | 5.x版本标准规范 |
| 6.0 | `/Users/zhanglei/winning/tfs2018/RDA-01-标准规范/02 V5.5/01 产品文档/02 标准规范/60模型/v3.0` | 6.0版本模型标准 |
| 项目化 | `/Users/zhanglei/winning/tfs2018/RDA-01-标准规范/02 V5.5/01 产品文档/04 标准规范（项目化）` | 项目化标准规范 |

---

## 表格过滤规则（v3.3.0）

解析器会自动过滤非数据库表结构的表格，只处理符合以下条件的表格：

| 必须包含的列 | 说明 |
|-------------|------|
| 字段标识列 | `数据元标识`、`数据元标识符`、`字段名`、`英文名` 等 |
| 字段名称列 | `数据元名称`、`字段`、`数据项` 等 |
| 约束或数据类型列 | `约束`、`填报要求`、`表示格式`、`数据类型` 等 |

**被过滤的表格类型**：
- 数据集汇总表（如包含`类目`、`数据集名称`、`数据库表名`等列头）
- 指标定义表（如包含`指标代码`、`指标名称`等列头）
- 其他非字段定义表格（如修订记录表、说明表等）

---

## 数据类型映射规则（v4.3.9）

### 基础映射（按数据类型类别）

| 数据类型类别 | DDL类型 | 说明 |
|------------|---------|------|
| S1/S2/S3 | VARCHAR | 字符型（S3=代码表类型，仅存代码值） |
| N | NUMBER/DECIMAL | 数值型 |
| DT | DATE | 日期时间型（Oracle DATE精度到秒） |
| D | DATE | 日期型 |
| L | VARCHAR(1) | 布尔型（F/T） |
| T | VARCHAR(8) | 时间型（hh:mm:ss） |

### 表示格式解析规则（按格式前缀）

格式解析顺序：AN → A → N.. → N → DT → D → S → 通用fallback

| 表示格式 | 示例 | 解析结果 | 说明 |
|---------|------|---------|------|
| **AN系列** | | | 字母数字混合 |
| `AN..n` | `AN..64` | VARCHAR(64) | 可变长度最大n |
| `AN.n` | `AN.64` | VARCHAR(64) | 单点变体 |
| `ANn` | `AN4` | VARCHAR(4) | 固定长度 |
| `ANn..m` | `AN4..18` | VARCHAR(18) | 范围长度，取最大值 |
| `AN..nXm` | `AN..64X3` | VARCHAR(192) | 多行：每行n字符×m行 |
| `AN..` / `AN..*` | `AN..*` | CLOB/TEXT | **不限长度**，映射为大字段类型 |
| **A系列** | | | 纯字母字符（UTF-8） |
| `An` | `A1`, `A4` | VARCHAR(1), VARCHAR(4) | 固定长度 |
| `A..n` | `A..18` | VARCHAR(18) | 可变长度 |
| `An..m` | `A1..10` | VARCHAR(10) | 范围长度，取最大值 |
| `A..nXm` | `A..10X3` | VARCHAR(30) | 多行 |
| `A` | `A` | VARCHAR(1) | 纯标识符，默认1 |
| **N系列** | | | 根据data_type_cat判断 |
| `N..n` + 类别S | `N..4` + S2 | VARCHAR(4) | 数字字符型 |
| `N..n` + 类别N | `N..4` + N | NUMBER(4) | 数值型 |
| `N..n,m` + 类别N | `N..10,2` + N | NUMBER(10,2) | 数值型带小数 |
| `Nn` + 类别S | `N1` + S2 | VARCHAR(1) | 数字字符型 |
| `Nn` + 类别N | `N1` + N | INTEGER | 整数型 |
| `Nn,m` + 类别N | `N5,2` + N | NUMBER(5,2) | 数值型带小数 |
| **DT系列** | | | 日期时间 |
| `DTn` | `DT19` | DATE | 固定格式 |
| **D系列** | | | 日期 |
| `Dn` | `D10` | DATE | 固定格式（排除DT） |
| **T系列** | | | 时间 |
| `T8` | `T8` | VARCHAR(8) | hh:mm:ss |
| **S系列** | | | 字符串 |
| `Sn` | `S1` | VARCHAR | 无长度 |
### 常见PDF提取错误修复（必查字段清单）

以下字段在从PDF/MinerU提取后经常出现格式错误，**必须在生成DDL前修复Word文档**。

#### 表示格式截断（MinerU输出AN..10实为AN..100等）

| 错误 | 正确 | 出现表 | 字段 |
|------|------|--------|------|
| `A..100` | `AN..100` | 所有含PATIENT_NAME的表 | PATIENT_NAME |
| `AN..12` | `AN..128` | 所有含YLYL1/YLYL2的表 | YLYL1, YLYL2 |
| `AN..12` | `AN..128` | T_HD_LIS_REPORT, T_HD_LIS_INDICATORS | LAB_SN |
| `AN..12` | `AN..128` | T_HD_PARAM, T_PD_PARAM | DIC_EX |
| `AN..10` | `AN..100` | 各表 | STAFF_NAME, CHECK_RESULT等 |
| `AN..20` | `AN..2000` | T_HD_PATIENT等 | DIAGNOSIS_SUMMARY |
| `AN..51` | `AN..512` | 各表 | CHECK_ITEM_NAME, INSPECTED_INDICATE等 |
| `AN..60` | `AN..600` | 各表 | INSPECTED_RESULT_DESC等 |
| `AN..30` | `AN..300` | 各表 | APPLICATION_TYPE, REF_RANGE等 |
| `AN..15` | `AN..150` | 各表 | SAMPLE_NAME |
| `AN..10` | `AN..1000` | T_HD_LIS_INDICATORS | YCTSSM |
| `AN..25` | `AN..255` | T_HD_LIS_REPORT | CHECK_NAME |
| `AN..25` | `AN..256` | T_HD_LIS_REPORT | CHECK_ITEM_CODE |

#### 合并字段（MinerU分页导致两列合并为一行）

| 合并字段 | 应拆分为 | 表 |
|---------|---------|-----|
| `LOCAL_INSURANCEDIALYSDATEIS_START_TIM` | `LOCAL_INSURANCE` + `DIALYSIS_START_TIME` | T_HD_PATIENT_QUIT, T_HD_PATIENT_LINE |
| `BORN_DATEDIALYSDATEIS_START_TIM` | `BORN_DATE` + `DIALYSIS_START_TIME` | T_PD_PATIENT, T_PD_PATIENT_LINE |
| `PERMANENT_TYIN_DATDATEOUT_DADATE` | `PERMANENT_TYPE` + `IN_DATE` + `OUT_DATE` | T_HD_STAFF_LOGIN, T_PD_STAFF, T_PD_STAFF_LOGIN |

#### 约束错误（Word中C须改为M）

PDF标注`必填`的字段，Word中经常被错误标为`C`（有则必填）。**必须逐字段对比PDF确认**。

#### 数据元名称截断

| 错误 | 正确 | 说明 |
|------|------|------|
| `身高` | `身高(cm)` | 缺单位 |
| `分支机构` | `分支机构ID` | 缺ID后缀 |
| `透前收缩压` | `透前收缩压(mmHg)` | 缺单位 |
| `卡` | `卡类型` | 截断 |
| `门急诊号` | `门(急)诊号` | 括号格式 |

#### 检查步骤（DDL生成前必须执行）

**⚠️ 人工核对比自动校验更可靠。** 自动化程序无法发现字段名截断、合并行、数据元名称截断等问题。必须逐表逐行逐单元格人工比对PDF源数据。

1. 读取MinerU输出 → 解析为结构化数据（`##`分割，注意`\\_`转义，约束映射先C再M）
2. 遍历Word表格，逐字段六列对比：字段名、数据元名称、约束、数据类型、表示格式、说明
3. 修复时修改`<w:t>`节点文本，**不重新创建段落/run**（保留rPr字体属性）
4. 修复后再次遍历验证，循环直到无真实数据差异

常见错误模式详见 `references/mineru-extraction.md`

## 字体格式统一规范（新增内容必须遵循）

修改Word文档新增内容时，字体必须与已有行一致。

### 字体属性标准

| 属性 | 值 | 说明 |
|------|------|------|
| `w:ascii` | `Times New Roman` | 英文字体 |
| `w:eastAsia` | `Times New Roman` | 中文字体（必须设置，否则回退宋体） |
| `w:hAnsi` | `Times New Roman` | ANSI字体 |
| `w:sz` | `20` | 字号（20=10pt，非小四12pt） |
| `w:szCs` | `20` | 复杂文种字号 |

### 修复步骤

1. 复制已有行（`deepcopy`），替换`<w:t>`文本节点——保留格式
2. 遍历所有`<w:r>`，检查`<w:rPr>`，缺失则插入格式模板
3. 检查`eastAsia`是否设置，未设置则补充（否则中文显示为宋体）
4. 检查`sz`是否为20，不是则改为20

## 常见特殊变体（不自行容错 → 列出给用户修正）

以下格式**不该**出现在规范的文档中。如果遇到，**不自行推算默认长度**，而是列出给用户修改文档：

| 文档中见到的格式 | 问题说明 |
|-----------------|---------|
| `4000`, `64`, `18` 等纯数字 | 裸数字，缺少AN..前缀 |
| `M1`, `B2` 等非标准前缀 | 文档笔误，标准前缀只有 A/AN/N/DT/D/T/S |
| `AN..` (无数字) | 缺最大长度值 |
| `AN..AN..50` | 重复前缀，应改为 `AN..50` |
| `N..6，2` 含中文逗号 | 应为英文逗号 `N..6,2` |

另：`AN..*` 算规范的"不限长度"表示法，映射为 CLOB/TEXT/nvarchar(max)。

**判断依据**：data_type_category为S1/S2/S3时，即使表示格式是N开头，也转换为VARCHAR而非NUMBER。

---

## DDL注释风格规范（v4.3.2）

> **统一注释规范以 `data-model-revision/references/bms-script-spec.md`《注释规范（DDL 与修订记录统一约束）》为准。**
> 核心：四类操作（加字段/加表/修改/删除）+ 值域修订，用统一的变更描述模板 `{表中文名}[{表英文名}]{操作}：…`（**`]` 后无空格**）；字段项写在 `[]` 内、半角逗号分隔，顺序 `[字段代码, 填报要求, 数据类型, 表示格式, …]`（仅代码必填）。
> 本 Skill 采用其中的**详式**（字段项内附类型与约束，如 `[DAY_OP_FLAG,O,S3,N1]`）；
> **批量排版**：同表**加/删**多个字段用**顿号（、）合一行**；**修改**字段**不要合在一行**，每字段独立一行；
> **配套铁律**：DDL 脚本与其配套的数据标准修订记录脚本，变更清单的条数、顺序、描述文字必须逐字一致，且形式（简式/详式）全程统一。
> 生成后可跑 `data-model-revision/scripts/check_comment_consistency.py` 校验。

| 规范项 | 要求 |
|--------|------|
| 脚本块注释 | 单行注释，如：`-- 表名中文[表名] - 新增表` |
| 变更清单 | 顶部 `/* */` 编号列出所有变更；同表加/删多字段用顿号合一行，如 `出院登记信息[INP_DISCHARGE]新增字段：日间手术病例标志[DAY_OP_FLAG,O,S3,N1]、主管医生姓名[CHIEF_DOC_NAME,O,S3,XM]` |
| SELECT/COMMENT语句 | **一个语句一行，不换行**（SELECT、EXECUTE IMMEDIATE COMMENT等都在同一行） |
| CREATE TABLE语句 | **字段列表保持多行**，每个字段一行，主键约束单独一行，括号后换行 |
| 分隔线 | **不加**分隔线（如 `-- ============`） |
| 内容区域注释 | **不加**步骤注释（如 `-- 检查表是否存在`、`-- 添加字段注释`） |
| 字段注释 | 直接生成COMMENT语句，不加说明文字 |

> **⚠️ 生成 DDL 注释（变更清单、COMMENT 语句）前必读**：[references/script-examples.md](references/script-examples.md) 第一部分
> 含 Oracle 新增表 / 新增字段的注释风格完整示例。


---

## 脚本生成规范（v3.4.0）

**所有数据库类型通用规则**：

| 规范项 | 要求 |
|--------|------|
| 文件头信息 | **不要**文件名称、数据库类型、生成时间、来源文档等，直接生成修订记录注释 |
| 修订记录注释 / 变更清单 | 顶部用 `/* ... */` 编号列出所有变更（新增表、新增字段、修改字段、删除字段、值域修订）。**格式、字段项写法、批量排版一律以 `data-model-revision/references/bms-script-spec.md`《注释规范》为唯一准绳**，本表不重复定义 |
| 脚本块注释 | 与变更清单逐条一致；字段项用详细式 `表名中文[表名]新增字段：字段名中文[字段代码,填报要求,数据类型,表示格式]`，同表加/删多字段顿号合一行、修改字段逐行 |
| 新增字段检查 | 先判断表是否存在，再判断字段是否存在 |
| 大小写格式 | 选择全大写/全小写时，脚本**所有字符**都应用该格式（SQL关键字、数据类型、表名、字段名） |
| 内容区域注释 | 内容区域**不加注释**（如"检查字段是否存在"等）；只在脚本块前写简单描述 |
| 字段约束 | 默认 `null`（非必填），避免已有数据插入失败；**但数据模型/实体明确为必填且有默认值时按模型定义**（如标志类字段 `not null default '0'`），不得一刀切改成 null |
| 关联表同步 | TRAN/LOG表只同步字段，不加注释；修订记录注释中不含关联表 |

> **注释规范唯一来源**：本 Skill 不再另立一套注释格式。字段项语法、四类操作模板、批量排版（加/删顿号合一行、修改逐行）、DDL↔修订记录一致性，全部见 `data-model-revision/references/bms-script-spec.md`《注释规范（DDL 与修订记录统一约束）》。生成 DDL 时直接按该规范写注释，不要事后依赖校验脚本兜底。

**大小写格式详细规则**：

当用户选择"全大写"时：
- SQL关键字：`DECLARE`, `BEGIN`, `END`, `IF`, `THEN`, `SELECT`, `FROM`, `WHERE`, `AND`, `EXECUTE`, `IMMEDIATE`, `ALTER`, `TABLE`, `ADD`, `NULL`, `COMMENT`, `ON`, `COLUMN`, `IS`
- 数据类型：`VARCHAR2`, `NUMBER`, `DATE`, `TIMESTAMP`, `INTEGER`
- 表名/字段名：全部大写
- 系统表/列：`USER_TABLES`, `USER_TAB_COLUMNS`, `TABLE_NAME`, `COLUMN_NAME`, `COUNT`, `UPPER`

当用户选择"全小写"时：
- 所有上述内容全部小写

---

## SQL Server 脚本生成规范（v4.2.0）

**SQL Server 特有规则**：

| 规范项 | 要求 |
|--------|------|
| 两层判断 | 先判断表是否存在，再判断字段是否存在 |
| 大小写格式 | 脚本所有字符（关键字、数据类型、表名、字段名）都遵循用户选择 |
| 单行语句 | 同一行同一个语句不换行，保持紧凑 |
| GO分隔符 | 每个表的原表、TRAN表、LOG表更新完后，后面加一个GO，换行 |
| 系统表查询 | 使用 `sys.tables` 判断表存在，`sys.columns` 判断字段存在 |
| OBJECT_ID | 使用 `object_id('表名')` 获取表对象ID |

> **⚠️ 生成 SQL Server / Oracle 新增字段或建表脚本前必读**：[references/script-examples.md](references/script-examples.md) 第二部分
> 含 SQL Server 全大写 / 全小写、Oracle 新增字段的完整脚本示例（原表 + TRAN + LOG 三表）。


---

## 列头识别规则

根据列头自动判断使用哪套规范：

```
列头含"数据元标识/数据元名称/约束/表示格式" → 规则A（区域卫生信息平台）
列头含"字段/字段名/类型/长度/填报要求" → 规则B（数据采集接口标准）
两套特征都不明显 → 询问用户确认
```

**何时读取详细规范**：
- 检测到规则A特征 → Read `references/rule-a-standard.md` 获取字段映射、数据类型转换表
- 检测到规则B特征 → Read `references/rule-b-interface.md` 获取字段映射、数据类型转换表
- 生成DDL脚本前 → Read `references/ddl-templates.md` 获取各数据库DDL模板

---

## 红色标记含义

| 红色范围 | 含义 | 生成DDL |
|---------|-----|---------|
| 整表红色字体 | 新增表 | CREATE TABLE |
| 章节标题红色 | 所属表格为新增表 | CREATE TABLE |
| 整行红色字体 | 新增字段 | ALTER TABLE ADD COLUMN |
| 部分内容红色 | 修改字段属性 | 根据列类型决定 |

**注意**：空单元格忽略，仅判断非空单元格的红色标记。

---

## 修改字段详细规则

当表格中**部分内容**为红色字体时，按以下规则处理：

### 需要生成DDL的变更（约束和表示格式列）

| 列名 | 红色变更 | DDL操作 | 说明 |
|-----|---------|---------|------|
| 约束/填报要求 | M→O | ALTER TABLE MODIFY/ALTER COLUMN | 将 NOT NULL 改为 NULL（生成DDL） |
| 约束/填报要求 | O→M | **不生成DDL** | 只更新修订记录注释，| 表示格式 | 类型/长度变更 | ALTER TABLE MODIFY/ALTER COLUMN | 修改数据类型或长度 |

**约束列变更规则**：
- `M`（必填）→ `O`（可选）：生成DDL，将 `NOT NULL` 改为 `NULL`
- `O`（可选）→ `M`（必填）：**不生成DDL**，只在修订记录注释中体现

**表示格式列变更**：
- `AN..50` → `AN..100`：VARCHAR(50) → VARCHAR(100)
- `N5` → `N10`：VARCHAR(5) → VARCHAR(10)
- `DT15` → `DT19`：DATE 类型不变，无需修改

### 只生成注释的变更（其他列）

| 列名 | 红色变更 | 处理方式 |
|-----|---------|---------|
| 数据元名称/字段中文名 | 内容变更 | 仅修订记录注释，不生成DDL |
| 说明/备注 | 内容变更 | 仅修订记录注释，不生成DDL |
| 值域 | 内容变更 | 仅修订记录注释，不生成DDL |

**修订记录格式**（仅修订记录注释、不生成 DDL 的字段属性变更，同样用统一语法）：
```sql
表名中文[表名]修改字段：字段名中文[字段名]（{旧属性值}→{新属性值}）
```

示例：
```sql
/*
患者基本信息[JB_BRJBXX]修改字段：姓名[XM]（约束 → 必填）
门诊就诊记录[JB_MZJZJL]修改字段：诊断代码[ZDDM]（表示格式 → AN..20）
门诊就诊记录[JB_MZJZJL]修改字段：诊断名称[ZDMC]（说明 → ICD-10 诊断名称）
*/
```

**注意**：只修改"说明"等非 DDL 列时，只在修订记录注释中体现（用上面的统一修改语法），不生成 ALTER 脚本。格式仍须与 `data-model-revision`《注释规范》一致。

---

## 修订记录格式

统一格式（与 `data-model-revision`《注释规范》完全一致，**这是唯一格式**）：
```sql
/*
新增表：表名中文[表名]
表名中文[表名]新增字段：字段名中文[字段代码,填报要求,数据类型,表示格式]、字段名中文[字段代码,填报要求,数据类型,表示格式]
表名中文[表名]修改字段：字段名中文[字段代码]（{旧属性值}→{新属性值}）
*/
```

- 同表加/删多个字段用顿号（`、`）合一行；修改字段每个字段独立一行。
- 每个字段必须写全「字段中文名[字段代码,…]」，不可省略。
- **修订记录不含关联表（_TRAN、_LOG）**。
- 约束改为 M（O→M）、或仅改"说明/值域内容"等非结构属性：**不生成 DDL**，只在修订记录注释中用统一修改语法体现（`（旧→新）`）。
- **只有表示格式变更和约束改为O（M→O）才生成DDL脚本**

### 修订记录SQL生成要点

**版本号格式**（与历史已有记录一致）：
- 公版：`V6.0.{yymmddHHMMSS}`（如 `V6.0.260626133554`）
- 项目化：`V6.0.{project_code}.{yymmddHHMMSS}`（如 `V6.0.PRJ-001-SZLH.260707152022`）

**datasetName 用中文**：`dataset` 类型的 `datasetName` 必须是中文表名（如"血透机构信息表"），`datasetNo` 保留英文表名。

**日期格式ISO**：JSON中的 `createdAt`/`modifiedAt` 使用 `yyyy-MM-ddTHH:mm:ss`（带T，无空格时区），否则Jackson反序列化失败。

---

## 公共字段规范

新增表可选添加以下公共字段：

| 字段名 | 类型 | 约束 | 说明 |
|-------|------|------|------|
| SCZT | VARCHAR(1) | NOT NULL DEFAULT '0' | 创建状态 |
| SCZT_INDEX | VARCHAR(1) | NULL | 索引状态 |
| SCZT_GGWS | VARCHAR(1) | NULL | 公共卫生状态 |
| SCZT_YLFW | VARCHAR(1) | NULL | 医疗服务状态 |

---

## 关联表同步规则

- `_TRAN` - 交易/流水表（无主键）
- `_LOG` - 日志表（无主键）
- 主表新增字段时，自动同步到关联表
- 脚本会检查关联表是否存在后再添加
- **修订记录注释中不含关联表**

---

## 主键检测规则

从"说明"或"备注"列检测主键：
- 包含"复合主键"、"联合主键"、"主键"字样的字段组合为主键
- 主键约束命名：`pk_表名`
- 关联表（_TRAN、_LOG）不设置主键

---

## DML标准库同步规则

当用户选择生成DML脚本时，将变更同步到以下标准库表：

### 表映射关系

| Word文档元素 | 标准库表 | 操作规则 |
|-------------|---------|---------|
| 文档封面名称 | `edsm_data_standard` | 一般不新增/修改（固定7个标准） |
| 数据集区域二级目录 | `edsm_dataset_category` | 红色字体→INSERT新增分类 |
| 数据集表格 | `edsm_dataset` | 新增表→INSERT；修改表→DELETE+INSERT |
| 数据集字段 | `edsm_dataset_element` | 新增字段→INSERT；修改字段→DELETE+INSERT |
| 元数据汇总 | `edsm_metadata` | 与dataset_element**一一对应、各自独立**，每个元素生成一条专属metadata，绝不共用/去重 |

### ID命名规则

| 表 | ID格式 | 示例 |
|----|--------|------|
| edsm_data_standard | `{standard_prefix}` | `winning-plat-01` |
| edsm_dataset_category | `{standard_id}-{category_name}` | `winning-plat-01-患者基本信息` |
| edsm_dataset | `{standard_id}-{dataset_no}` | `winning-plat-01-PERSON` |
| edsm_dataset_element | `{standard_id}-{dataset_no}-{element_code}` | `winning-plat-01-PERSON-XM` |

### 分类目录提取规则

Word文档中的"数据集区域"二级标题（如"患者基本信息"、"门急诊信息"）对应分类：
- 检测标题是否红色字体
- 红色标题 → 新增分类 → 生成INSERT语句
- 非红色标题 → 不操作（分类已存在）

### dataset_element字段映射

| Word列头 | dataset_element字段 | 说明 |
|---------|---------------------|------|
| 数据元标识 | element_code | 字段英文名（大小写与标准文档一致，不转换：文档大写则大写、小写则小写） |
| 数据元名称 | element_name | 字段中文名 |
| 说明/定义 | definition | 字段定义说明 |
| 约束(M/O) | notnull | 1=M(必填), 0=O(可选) |
| 是否主键 | is_pk | 从definition中检测"复合主键"等字样 |
| 数据类型 | data_type | S1/S2/S3/D/DT等 |
| 表示格式 | representation_format | AN..64/N1/DT19等 |
| 值域代码 | code_system_id | 如 GB/T 2261.1-2003 |

### DML生成策略

**新增场景**：
```sql
-- 新增分类
insert into edsm_dataset_category(...) select ... where not exists (...);

-- 新增数据集
insert into edsm_dataset(...) select ... where not exists (...);

-- 新增字段
insert into edsm_dataset_element(...) select ... where not exists (...);
```

**修改场景**（先删后插）：
```sql
-- 修改数据集：删除旧数据
delete from edsm_dataset_element where dataset_id = 'xxx';
delete from edsm_dataset where dataset_id = 'xxx';
-- 再插入新数据
insert into edsm_dataset(...) select ...;
insert into edsm_dataset_element(...) select ...;
```

**元数据一对一（重要，废除共用/去重）**：
- edsm_metadata 与 edsm_dataset_element **一一对应**：每一条 dataset_element 都生成一条独立、专属的 metadata，绝不按字段名共用同一份元数据（否则同名不同表的字段会串号）
- `metadata_id` = `metadata_code` = `element_id`（即 `{standard_id}-{dataset_no}-{element_code}`）
- `dataset_element.metadata_id` 直接关联自己的 `element_id`，不再通过 `element_code` 字段名反查
- 脚本通过 `not exists (select 1 from edsm_metadata where metadata_id = a.element_id)` 保证幂等增量；历史已存在的元数据**不做任何改动**

---

## 约束显示与脚本处理规则（v4.3.4）

Word文档"填报要求"列可能包含多种约束类型，处理规则如下：

### 注释中的约束显示

| 填报要求原始值 | 注释显示 | 说明 |
|--------------|---------|------|
| 条件必填 | 条件必填 | 保持原样 |
| 空白/O/可选 | 应填 | 默认非必填 |
| M/必填 | 必填 | 明确标注必填 |

### 脚本中的约束处理

| 填报要求类型 | DDL脚本约束 | 说明 |
|-------------|------------|------|
| 条件必填 | NULL | 按非必填处理，避免已有数据插入失败 |
| 空白/O/可选 | NULL | 非必填 |
| M/必填 | NULL | **新增字段统一使用NULL** |

### 设计原因

新增字段统一使用 `NULL`（非必填），原因：
- 避免已有数据因新增必填字段导致插入失败
- 条件必填属于特殊业务约束，不适合用数据库NOT NULL实现

建表DDL仍按文档要求生成必填/非必填约束。

---

## 新增字段约束规则

无论文档标注必填还是非必填，新增字段DDL统一使用 `null`（非必填）。

**原因**：避免已有数据因新增必填字段导致插入失败。

建表DDL仍按文档要求生成必填/非必填约束。

---

## 执行步骤详解

### 步骤1：选择文档（v4.3.0 简化交互方式）

**采用简洁文字展示方式，避免技术格式干扰**：

#### 选择流程

1. **展示预设目录**（用简洁文字，不显示label等技术字段）：
   ```
   请选择文档目录（输入序号或名称）：
   1. 5.x - 库表接入规范
   2. 6.0 - 60模型v3.0  
   3. 项目化 - 标准规范(项目化)
   4. 其他目录（手动输入路径）
   
   用户输入：1 或 5.x 或 库表接入规范
   ```

2. **列出目录内容**（当文件较多时用序号列表）：
   ```
   目录下的文档文件（输入序号或文件名）：
   1. 第02部分：医疗服务.docx (645KB)
   2. 第03部分：公共卫生.docx (410KB)
   ...
   12. 第13部分：公共卫生（实时）.docx (107KB)
   
   用户输入：7 或 第08部分 或 人财物
   ```

3. **智能识别用户输入**：
   - 输入序号：直接匹配
   - 输入部分名称：模糊匹配
   - 输入关键字：如"人财物"匹配"人财物运营管理"

#### 交互原则（v4.3.0）

| 原则 | 说明 |
|------|------|
| 简洁展示 | 只显示名称和必要信息，不显示label/description等技术字段 |
| 序号优先 | 当选项超过4个时，使用序号列表让用户输入数字 |
| 智能匹配 | 支持序号、名称、关键字模糊匹配 |
| 避免checkbox | 不使用多选checkbox，改为输入序号或名称 |
| 重新开始 | 用户重新调用skill时，必须从头开始流程，不要记住之前的选择 |

---

## 表名格式识别规则（v4.3.3/v4.3.5）

### 段落样式过滤（v4.3.5 重要）

**只提取Heading样式段落的表名，排除Normal样式的说明文字！**

Word文档中表格前可能有两种段落：
- **Heading样式（标题）**：真正的表名定义，如"出院患者收费记录表 ZYSFJLB"
- **Normal样式（正文）**：表说明文字，如"1、必须和住院收费记录表(ZYSFJLB)关联..."

| 样式 | 示例 | 处理 |
|------|------|------|
| Heading 3 | "出院患者收费记录表 ZYSFJLB" | ✓ 提取表名 |
| Normal | "1、必须和住院收费记录表(ZYSFJLB)关联..." | ✗ 排除 |

**判断方法**：检查 `para.style.name`，只处理以"Heading"开头或包含"标题"的段落。

### 表名格式匹配

解析器支持两种表名格式：

| 格式 | 示例 | 说明 |
|------|------|------|
| 空格分隔 | `孕册信息 FB_YCF_YCXX` | 表名在段落末尾，空格分隔 |
| 中文括号 | `献血者基本信息（XZ_XXZJBXX）` | 表名在中文括号内 |

**代码实现**：word_parser.py的extract_table_names_ordered函数先检查段落样式是否为Heading，再匹配表名格式。

### 步骤2：解析文档表格

处理：
1. 使用 python-docx 读取文档
2. 提取所有表格
3. 自动过滤非数据库表结构表格（汇总表、指标表等）
4. 解析标题行获取表名（格式：`中文名 表名`）
5. 提取列头
6. 检测红色字体标记

输出：
```
文档共有 X 个表格（数据库表结构表格 Y 个）
检测到列头：[数据元标识, 数据元名称, 约束, 数据类型, 表示格式, 说明]
有红色标记的表格：X 个
新增表：X 个
新增字段：X 个
修改字段：X 个
```

### 步骤2.5：格式校验（v4.4.0 新增——必须执行）

解析后、生成前，**先执行格式校验**：

1. 遍历所有字段，对每个表示格式调用 `parse_format_string`
2. 返回 `('', '')` 的 → 列出完整信息（表名、字段名、数据类型、表示格式），**不自行容错**
3. 有不符合规范的字段 → **给用户列出来**，用户修改文档后再重新生成
4. 全部规范 → 进入下一步

**容错规则**（仅修正纯字面量变形，不影响语义）：
- 全角点 U+FF0E → U+002E（N．．4 → N..4）
- 不可见字符（零宽空格、软连字符等）清理

**不做容错**（格式语义未知，必须用户确认）：
- 裸数字 `4000`、`64`、`18`
- 非标准前缀 `M1`
- `AN..` 缺少最大长度数字
- `AN..AN..50` 重复前缀
- 中文逗号替换英文逗号

### 步骤3：逐个询问选项（单问单答）

每个选项用单独的 clarify 工具依次询问，每次**最多 4 个选项**：

1. **数据库类型**（可传数组，输入序号如 `1,3` 表示多选）：
   ```
   1. Oracle
   2. MySQL
   3. SQL Server
   4. PostgreSQL
   ```
2. **DDL模式**：
   ```
   1. 全量（所有表CREATE TABLE）
   2. 增量（仅红色标记变更）
   ```
3. **DML模式**：
   ```
   1. 不生成DML
   2. 全量DML
   3. 增量DML
   ```
4. **大小写格式**：
   ```
   1. 全小写
   2. 全大写
   ```
5. **关联表**（TRAN/LOG表同步）：
   ```
   1. 是
   2. 否
   ```
6. **公共字段**（SCZT等）：
   ```
   1. 是
   2. 否
   ```

**不要**使用预置组合方式（已被用户否决——选项过多组合爆炸，用户偏好一个个问）。

**关键规则**：
- **数据库类型可多选**，每选一种生成一套脚本。用户在 choices 中输入序号组合如 `1,3`
- 其他选项若用户输入多个，取第一个
- 用户重新调用skill时，必须从头开始流程

**多数据库处理**：每种类型分别调用 `run_generator.py`，最终告知所有文件路径。

### 步骤4：生成修订记录

遍历有变更的表格，按格式生成修订记录注释。

### 步骤5：生成DDL/DML脚本

- 根据用户选择的数据库类型生成对应DDL
- 应用大小写格式到所有字符
- 若用户选择生成DML，同时生成标准库同步脚本
- 输出文件：DDL文件（必选）和DML文件（可选）

### 步骤6：语法验证 + 自进化（v4.4.0 新增）

脚本生成后，**必须执行语法验证**，确保没有以下问题：
- VARCHAR/VARCHAR2/NVARCHAR 无长度（如 `varchar2` 不带括号）
- NUMBER/NUMERIC 无精度（如 `number` 不带括号）
- 括号不配对、重复关键字等

验证使用 `scripts/verify_sql.py`（已集成到 `run_generator.py` 中自动执行）。

**发现问题时的处理流程（自进化环路）**：\n```\n生成脚本 → 验证语法 → 有错误?\n  ├── 是 → 定位根因（parse_format_string/ddl_generator/type_map）\n  │        → 修复代码/bug\n  │        → 重新生成 → 重新验证（循环，直到无错误）\n  └── 否 → 交付用户\n```\n\n### 常见语法验证失败原因\n\n| 现象 | 根因 | 修复方式 |\n|------|------|---------|\n| `varchar` 无长度（如 `varchar not null`） | Word文档中该字段表示格式列为空，map_type未生成长度 | 设置默认长度：`varchar(255)`；或补全Word文档表示格式列 |\n| `numeric` 无精度（如 `numeric not null`） | Word文档中数值字段表示格式列为空 | 设置默认精度：`numeric(18,2)`；或补全Word文档 |\n| `varchar2` 无括号 | Oracle映射时长度缺失 | 检查 parse_format_string 是否识别了该格式 |
| `varchar` 无长度（如 `varchar not null`） | Word文档中该字段表示格式列为空，map_type未生成长度 | 设置默认长度：`varchar(255)`；或补全Word文档表示格式列 |
| `numeric` 无精度（如 `numeric not null`） | Word文档中数值字段表示格式列为空 | 设置默认精度：`numeric(18,2)`；或补全Word文档 |\n\n**修复后务必同步到公共目录**（`~/.agents/skills/reg-ddl-generator/`），让其他智能体也能用到修复后的代码。在 Hermes 内使用 `terminal` 执行 cp 命令同步。

---

## 固化脚本调用

### 一键执行（DDL + DML）

```bash
python3 ~/.hermes/skills/software-development/reg-ddl-generator/scripts/run_generator.py \
    '/path/to/document.docx' \
    --db oracle \
    --case lower \
    --ddl-mode incremental \
    --dml-mode none \
    [--no-tran-log] \
    [--no-public-fields]
```

参数说明（使用 `--help` 查看完整帮助）：
- 文档路径（必填）
- `--db`：数据库类型（oracle/mysql/sqlserver/postgresql）
- `--case`：大小写格式（upper/lower/original）
- `--ddl-mode`：DDL生成模式（incremental/full）
  - `incremental`：增量模式，仅生成红色标记的变更
  - `full`：全量模式，所有表格按新增表处理
- `--dml-mode`：DML生成模式（none/incremental/full）
  - `none`：不生成DML脚本（默认）
  - `incremental`：增量DML，仅同步红色标记的变更
  - `full`：全量DML，同步所有表格和字段
- `--no-tran-log`：不生成关联表
- `--no-public-fields`：不添加公共字段
- `--output`：输出目录（默认 ~/Downloads/）

---

---

## ⚠️ Word文档修改风险警告（v4.2.0）

**重要原则：修改Word文档前必须确保可回退！**

| 场景 | 要求 |
|------|------|
| Git仓库内的文档 | 先 `git stash` 或 `git commit`，确保可回退 |
| 非Git目录的文档 | 先 `cp file file.bak` 创建备份文件 |
| 无备份手段 | **拒绝修改**，告知用户无法回退 |

**Word文档修改常见坑点**：
- 表格位置定位错误：不能仅靠表格索引定位，必须通过段落内容判断（区分目录段落和详细定义段落）
- 表格插入顺序错误：需先删除旧表格再插入新表格，或直接在正确位置插入
- 段落级别不一致：新插入的标题段落需与现有文档结构级别一致
- 多次操作导致混乱：建议一次性完成所有修改，避免反复操作

**推荐策略**：优先生成SQL脚本，Word文档修改由用户手动完成或确认有备份后再操作。

---

## Greenplum/Flyway迁移脚本规范（v4.2.0）

当目标数据库为Greenplum且项目采用Flyway迁移管理时：

| 规范项 | 要求 |
|--------|------|
| 文件命名 | `V{YYYYMMDDHHMMSS}__create_table_{表名}.sql` |
| 时间戳 | 使用实际时分秒，不能全0（如 `V20260611184025`） |
| 描述格式 | 必须是 `create_table_{表名}` 格式 |
| DDL脚本目录 | `.../edsm_sql/greenplum/` |
| 对照表脚本目录 | `.../system_sql/rhdp_dw/greenplum/` |
| 主键命名 | 复合主键使用 `primary key (字段1, 字段2)` |
| 注释方式 | 使用 `do $$ begin ... end $$;` 块执行COMMENT语句 |

**示例文件名**：
- `V20260611184025__create_table_base_exam_item.sql` - 检查检验项目目录表
- `V20260611184025__create_table_exam_item_mapping.sql` - 对照表

---

## Doris 脚本生成规范（v4.6.0）

当目标数据库为 Doris（BMS 60 模型 edsm_sql/doris 目录）时：

| 规范项 | 要求 |
|--------|------|
| 生成路径 | 先按 postgresql 方言生成 probe（`--db postgresql --case lower --no-tran-log --no-public-fields`），再用 `scripts/convert_doris.py` 转换 |
| 文件命名 | `V{YYYYMMDDHHMMSS}__alter_table_medical_std_{yymmdd}.sql`（与 GP 同时间戳） |
| DDL脚本目录 | `.../edsm_sql/doris/` |
| 大小写 | 全小写（表名/字段名/类型/SQL关键字） |
| 建表语句 | `create table if not exists t( ... )` + `unique key(...)` + `comment '...'` + `distributed by hash(首主键列) buckets 8;` |
| 桶数量 | **固定 `buckets 8`**（用户 2026-08-27 确定） |
| 副本数 | **不输出 `properties ('replication_num' = '...')`**（用户明确去除） |
| 新增字段 | `alter table t add column c type null comment '...';` 单行 |
| **同表合并（重要）** | **同一张表的多个字段变更必须合并为【单条】ALTER 语句**，多子句逗号分隔、分号在末条，缩进 4 空格。Doris 不允许同一张表分多条 ALTER，否则执行报错。参考 `doris/V20260729153107__alter_table_sign_record_234455.sql` |
| 幂等 | 不写 if exists 判断（Doris 无该语法），直接裸 ALTER；建表用 `if not exists` |
| 类型映射 | PostgreSQL probe 的定点数 `numeric(p[,s])` 在转换时自动改为 Doris 的 `decimal(p[,s])`；`timestamp` → `datetime`。**Doris 无 NUMERIC / TIMESTAMP 类型**，原样透传会报 `mismatched input 'numeric'` 解析错误。其余类型（varchar / date / int / text / boolean / json 等）两库一致，原样保留（映射逻辑见 `convert_doris.py` 的 `to_doris_type`） |
| **字符串长度 ×4（重要）** | Doris 存储 UTF-8 中文，**1 个汉字 3 字节、1 个特殊字符 4 字节**；标准文档长度按【字符数】控制，脚本中字符串字段长度必须按字节数定义 → 转换层自动将 `varchar(n)`/`char(n)` 统一 **×4**（如 `varchar(100)` → `varchar(400)`）。**上游 PG probe 保持文档原始长度，禁止提前手动 ×4（否则转换后变 ×16）**；最大 4000 → 16000，未超 Doris 65533 上限。转换后自检：可执行代码区所有 varchar/char 长度必须能被 4 整除 |
| 校验 | 生成后用 `verify_sql.py <输出.sql> --db doris` 扫描可执行代码区，若残留 `numeric`/`timestamp`（提示转 DECIMAL/DATETIME）、或 varchar/char 长度非 4 倍数，直接报警；`/* */` 与 `--` 注释会被剥离，不会误报变更说明文字 |

**ALTER 合并示例**（同表多字段，长度已按 ×4 展示，如原文档 `varchar(2)` → `varchar(8)`）：
```sql
alter table emr_outp
    add column hosp_code varchar(8) null comment '院区代码',
    add column hosp_name varchar(280) null comment '院区名称',
    add column outp_no varchar(256) null comment '门（急）诊号',
    add column symptom_desc varchar(4096) null comment '症状描述';

alter table emr_emergency_obs
    add column hosp_code varchar(8) null comment '院区代码',
    add column hosp_name varchar(280) null comment '院区名称',
    add column outp_no varchar(256) null comment '门（急）诊号',
    add column disposal_plan varchar(8000) null comment '处置计划';
```

**建表示例**（新表）：
```sql
create table if not exists emr_health_info(
    sys_soid varchar(64) not null comment '系统编码',
    health_info_id varchar(64) not null comment '基本健康信息唯一标识',
    ...
)
unique key(sys_soid, health_info_id)
comment '基本健康信息'
distributed by hash(sys_soid) buckets 8;
```

> 转换脚本：`scripts/convert_doris.py`（已内置同表合并、buckets 8、去副本数、字符串长度 ×4 规则）。生成后自检：输出中不得出现 `replication_num`、`buckets 1`；所有 varchar/char 长度必须能被 4 整除（可跑 `verify_sql.py --db doris` 校验）。

---

## 异常处理

| 异常情况 | 处理方式 |
|---------|---------|
| 无备份无法回退 | **拒绝修改**，告知用户需先创建备份 |
| 文档无法解析 | 检查文件格式，提示提供正确的.docx文件 |
| 列头无法识别 | 列出检测到的列头，询问用户手动指定含义 |
| 无红色标记 | 提示文档可能无变更，询问是否继续 |
| 脚本执行失败 | 展示错误信息，提供手动排查建议 |

---

## DDL模板参考

详细DDL模板请参考：`references/ddl-templates.md`