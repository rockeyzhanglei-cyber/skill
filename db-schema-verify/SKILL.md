---
name: db-schema-verify
description: |
  库表结构核查与比对工具。支持两类任务：
  1) 单库自检 —— 原表与TRAN/LOG表结构一致性检查，或标准文档与库表结构符合度核查
  2) 多库比对 —— 基准库与多个目标库的结构差异比对，生成Oracle/SQL Server修复脚本
  核查后生成修复脚本，每条语句有注释说明原因，类型不一致的项注释掉供人工确认。
tags: [schema, ddl, sql, compare, repair, oracle, sqlserver, alter, self-check, verify]
version: "2.4"
---

# 库表结构核查与比对

## 定位

本 Skill 是一个**库表结构核查工具**，核心任务是发现表结构差异并生成修复脚本。

支持两种核查场景：
- **单库自检**：验证单个数据库的内部一致性（TRAN/LOG表是否与原表一致、库表是否符合标准文档）
- **多库比对**：以基准库为标准，发现多个目标库的结构差异，生成针对性修复脚本

## 全局通用基础依赖（强制加载）

以下三个文件是**所有流程的基础依赖**，在每个流程第一步前**必须先加载**：
1. `references/word_parsing_guide.md` — Word文档解析指南（生成临时解析脚本时必须参考）
2. `references/table_structure_template.md` — 数据结构MD固定模板（所有中间产物必须符合此格式）
3. `references/export_guide.md` — CSV导出指南（定义固定列结构，固化脚本依赖此格式）

跳过加载会导致中间产物格式错误、固化脚本解析失败。

---

## 强制执行规则

**F0 逐步执行**：每个clarify只问一个问题，等用户回答后再问下一个。禁止合并提问、禁止推测答案、步骤间必须有停顿（明确说"现在进入步骤X"）。

**F1 必须使用固化脚本**：`generate_export_sql.py`、`compare_with_docx.py`、`self_check.py`、`compare_db_to_db.py` — 禁止自己写替代方案。

**F2 必须加载参考文档**：每个流程开始前必须先加载"全局通用基础依赖"中的三个文件。生成临时解析脚本时必须参考 `word_parsing_guide.md` 和 `table_structure_template.md`。

**F3 必须按流程步骤执行**：每个步骤的输入都依赖前一步骤的输出，跳步会导致缺少必要数据。

---

## 流程架构

```
阶段0：任务类型选择
├─ 单库自检
│  ├─ A) 原表 vs TRAN/LOG表自检
│  ├─ B) 标准文档 vs 库表结构自检（核心流程）
│  │  └─ B-选项：TRAN/LOG处理方式（逐字段核对 | 直接重建）
│  └─ C) 标准文档 vs 原表自检 + TRAN/LOG直接重建
└─ 多库比对（基准库 vs 多个目标库）
```

## 核心概念：模板与固化

**模板驱动 + 程序固化**：固定模板（`table_structure_template.md`、`export_guide.md`）→ 固化脚本（`generate_export_sql.py`、`compare_with_docx.py`等）→ 临时脚本（文档解析，必须参考 `word_parsing_guide.md`，输出必须符合模板）。

## 文件管理原则

- **合并优先于删除**：整理参考文件时，先确认内容已覆盖后再删除，优先合并到保留文件
- **单一数据源**：同一数据结构只在一个文件中定义完整版本，其他文件引用而非复制
- **变更程序**：修改配置项/删除文件时，先grep全Skill检查所有引用，更新所有相关文件后确认无残留

---

## 阶段0：任务类型选择

**步骤1：选择任务类型**
```
clarify 提问：
"请选择任务类型：
 1) 单库自检（验证单个数据库的内部一致性）
 2) 多库比对（以基准库为标准，对比多个目标库的差异）
 3) 先自检，再多库比对（完整流程）"
```

⏸️ **等待用户回答**

- 记录：`task_type = single_check | multi_compare | full_flow`
- ✅ 用户已选择，继续下一步

---

## 阶段1：单库自检

**步骤2：选择自检类型**
```
clarify 提问：
"请选择自检类型：
 A) 原表 vs TRAN/LOG表自检（保证TRAN/LOG表与原表结构一致）
 B) 标准文档 vs 库表结构自检（保证库表符合文档标准）
 C) 标准文档 vs 原表自检 + TRAN/LOG直接重建（只核对原表与文档差异，TRAN/LOG表直接按原表结构重建，无主键）"
```

⏸️ **等待用户回答**

- 记录：`check_type = tran_log | docx_compare | docx_compare_rebuild`
- ✅ 用户已选择，继续下一步
- 说明：选项C适合"文档只定义原表结构、TRAN/LOG为数据交换影子表"的标准场景，TRAN/LOG不做逐字段比对，直接以原表（文档）结构重建

---

### 子流程A：原表 vs TRAN/LOG表自检

**核对逻辑**：以原表结构为准，分析TRAN表和LOG表与原表的差异，生成修复脚本使TRAN/LOG表与原表一致。

**⚠️ 子流程A结束后流程结束**，不需要再进入子流程B。子流程B是独立的另一种自检类型。

如果用户在阶段0选了"先自检，再多库比对"（full_flow），子流程A结束后直接进入阶段2（多库比对）。

**Word文档解析共用**：子流程A、子流程B、子流程C共用同一个 `references/word_parsing_guide.md` 解析指南。区别在于：
- 子流程A只需解析"表清单"（哪些表要核对）
- 子流程B和子流程C需要解析完整结构（每张表的字段定义）

---

**步骤A1：确定表清单来源**
```
clarify 提问：
"表清单来源：
 1) 从标准文档解析（需要提供Word文档路径）
 2) 手动指定（输入表名，逗号分隔，如：TABLE_A,TABLE_B,TABLE_C）"
```

⏸️ **等待用户回答**

- 如果选择1：
  - 提问Word文档路径
  - 强制加载参考文档：`references/word_parsing_guide.md`（解析指南，必读）
  - 强制加载参考文档：`references/table_structure_template.md`（产物格式模板，必读）
  - 解析模式：轻量模式 — 只提取表清单章节（序号 | 中文名 | 英文表名 | 是否有TRAN | 是否有LOG），不解析每张表的字段定义
  - 在任务目录下编写一次性python脚本，按解析指南的"轻量模式"编写
  - 脚本输出：`<任务目录>/tables_list.md`
  - 记录：`table_scope_source = docx`

- 如果选择2：
  - 用户直接输入表名（逗号分隔）
  - 生成 `tables_list.md`（按固定模板格式）
  - 记录：`table_scope_source = manual`

✅ 表清单已确定，继续下一步

---

**步骤A2：确认基准库数据库类型**
```
clarify 提问：
"基准库是什么数据库类型？
 1) Oracle
 2) SQL Server"
```

⏸️ **等待用户回答**

- 记录：`base_db_type = oracle | sqlserver`
- ✅ 数据库类型已确认，继续下一步

---

**步骤A3：确认客户端工具**
```
clarify 提问：
"你用什么客户端连接数据库？
 1) Navicat
 2) DBeaver
 3) PL/SQL Developer（仅Oracle）
 4) SSMS（仅SQL Server）"
```

⏸️ **等待用户回答**

- 记录：`base_client = navicat | dbeaver | plsqldev | ssms`
- ✅ 客户端工具已确认，继续下一步

---

### 步骤A4：生成导出SQL → 指导导出CSV → 获取CSV路径

⚠️ **强制调用固化脚本**（禁止自己编写替代脚本）：
```bash
python scripts/generate_export_sql.py \
  --md <任务目录>/tables_list.md \
  --db-type <oracle|sqlserver> \
  --output <任务目录>/export_<db_type>.sql
```

**操作**：
1. 根据 `base_db_type` 调用固化脚本 `generate_export_sql.py`，从表清单生成导出SQL
2. 根据 `base_client` 指导用户执行导出SQL并导出CSV（⚠️ **CSV必须符合** `references/export_guide.md` 的固定格式模板，**编码必须为UTF-8**）
3. 提示用户：导出完成后，请提供CSV文件路径
4. 获取并验证CSV文件
- 记录：`base_csv_path`

---

### 步骤A5：执行TRAN/LOG自检 → 生成修复脚本

⚠️ **强制加载参考文档**（必须先读取，否则不能继续）：
- `references/self-check-standards.md` — 自检标准（8维度）

⚠️ **强制调用固化脚本**（禁止自己编写替代脚本）：
```bash
python scripts/self_check.py \
  --md <任务目录>/tables_list.md \
  --csv <CSV路径> \
  --task-dir <任务目录> \
  --db-type <oracle|sqlserver>
```

**操作**：
- 脚本读取表清单和CSV，以原表结构为基准
- 逐一检查对应的_TRAN表和_LOG表
- 对比维度：字段缺失、类型差异、长度差异、精度差异、小数位差异、可空性、默认值、表是否存在
- 生成修复脚本：`<任务目录>/selfcheck_<db_type>.sql`

**修复脚本特性**（详见 `references/self-check-standards.md`）：
- 每条语句带存在性判断（表存在且字段不存在/存在才执行）
- TRAN/LOG表不存在时生成CREATE TABLE（结构同原表，无主键）
- 需人工确认的语句已注释（类型不一致、DEFAULT值冲突）

**⚠️ 脚本生成后任务结束。** 用户自行在SSMS/PL/SQL Developer中执行修复脚本。

---

### 子流程B：标准文档 vs 库表结构自检（核心流程）

**核对逻辑**：标准文档只定义了原表结构，但库里有三张表（原表、TRAN表、LOG表）。需要将文档中的表结构分别与库里这三张表核对，生成统一修复脚本。

> **TRAN/LOG处理方式（在步骤B3后追加确认）**：
> ```
> clarify 提问：
> "TRAN/LOG表如何处理？
>  1) 逐字段核对（文档结构分别与原表/TRAN表/LOG表三表核对，各自独立比对）
>  2) 直接重建（只核对原表与文档差异，TRAN/LOG表直接按原表结构重建，无主键）"
> ```
> 记录：`tran_log_mode = field_compare | rebuild`
> - 选择1：与原有子流程B一致
> - 选择2：相当于选项C，即子流程C（见下），比对脚本传 `--tran-log-mode rebuild`

#### 步骤B1：提供Word标准文档路径
```
clarify 提问：
"请提供Word标准文档路径"
```
- 验证文档存在且可读取
- 记录：`docx_path`

#### 步骤B2：确认基准库数据库类型
（同步骤A2）记录：`base_db_type = oracle | sqlserver`

#### 步骤B3：确认客户端工具
（同步骤A3）记录：`base_client = navicat | dbeaver | plsqldev | ssms`

---

#### 步骤B4：解析Word文档 → 固定格式MD

> ⚠️ 此步骤输出必须符合 `references/table_structure_template.md` 的固定格式，因为后续所有脚本都依赖此格式。

**强制加载的参考文档**：
1. `references/word_parsing_guide.md` — 解析指南（必读，包含文档结构特征和代码示例）
2. `references/table_structure_template.md` — MD固定模板（必读，定义输出格式）

**操作方式**：
1. 加载上述两个参考文档
2. 在**任务目录下**编写一次性python脚本（如 `parse_docx_temp.py`），使用python-docx解析Word文档
3. **强制约束**：脚本输出必须符合 `table_structure_template.md` 定义的固定格式

**固定格式要求**：
- 第一章：`## 表清单` 章节（序号 | 中文名 | 英文表名 | 是否有TRAN | 是否有LOG）
- 后续章节：每张表的字段定义表格（7列固定格式）

**验证**：
- 检查表清单章节是否存在
- 检查表数量是否与文档目录一致
- 检查格式是否符合模板定义

✅ Word文档解析完成，继续下一步

---

#### 步骤B5：生成导出SQL → 指导导出CSV → 获取CSV路径

> ⚠️ 必须调用 `scripts/generate_export_sql.py` 固化脚本。

**5a. 调用固化脚本生成导出SQL**

```bash
python scripts/generate_export_sql.py \
  --md <任务目录>/table_structure.md \
  --db-type <oracle|sqlserver> \
  --output <任务目录>/export_<db_type>.sql
```

**脚本自动完成**：从MD提取表名 → 扩展_TRAN/_LOG → 读取SQL模板 → 生成导出SQL。验证表数量是否正确。⚠️ **CSV必须符合 `export_guide.md` 的固定列结构，编码必须为UTF-8。**

**5b. 指导用户导出CSV**（参考 `references/export_guide.md` 中的客户端操作指引）

**5c. 获取CSV路径**
```
clarify 提问：
"CSV已导出，请提供CSV文件路径"
```
- 验证文件存在且可读取
- 记录：`base_csv_path`

---

#### 步骤B6：生成修复脚本 → 指导执行 → 二次验证（循环）

⚠️ **强制加载参考文档**（必须先读取，否则不能继续）：
- `references/compare_rules.md` — 比对规则（决定哪些差异需要修复，哪些忽略）
- `references/type_mapping.md` — 数据类型映射

⚠️ **强制调用固化脚本**（禁止自己编写替代脚本）：
```bash
# 默认：TRAN/LOG逐字段核对（原表+TRAN+LOG三表独立比对）
python scripts/compare_with_docx.py \
  --md <任务目录>/table_structure.md \
  --csv <CSV路径> \
  --db-type <oracle|sqlserver> \
  --task-dir <任务目录>

# TRAN/LOG直接重建（只核对原表，TRAN/LOG按原表结构重建）
python scripts/compare_with_docx.py \
  --md <任务目录>/table_structure.md \
  --csv <CSV路径> \
  --db-type <oracle|sqlserver> \
  --task-dir <任务目录> \
  --tran-log-mode rebuild
```

**核对逻辑**：文档中定义的原表结构，需要分别与库里的原表、TRAN表、LOG表核对，生成统一修复脚本。

**脚本自动完成**：
1. 解析 `table_structure.md`（Word文档标准，定义原表结构）
2. 解析 CSV（基准库导出，含原表+TRAN表+LOG表）
3. **逐字段核对模式**（默认）：将文档原表结构分别与库里原表/TRAN表/LOG表三表核对（各自独立比对）
4. **直接重建模式**（`--tran-log-mode rebuild`）：只将文档结构与原表核对；TRAN/LOG表不做逐字段比对，直接生成"按原表结构重建"的语句（DROP + CREATE，无主键、不加公共字段）
5. 生成统一修复脚本：`<任务目录>/fix_<db_type>_<时间戳>.sql`（三表问题合并到一个文件；如需固定文件名可传 `--output <任务目录>/fix_<db_type>.sql`）

**修复脚本结构**：
- **【不安全修改】**（注释状态，需人工确认）：
  - 类型变更、多余必填字段
  - 每条必须是完整可执行的ALTER语句，只是前面加`--`注释
- **【安全修改】**（直接可执行）：
  - 新增字段（ADD COLUMN）—— **全部为NULL，不允许NOT NULL**
  - 扩大字段长度/精度（MODIFY扩大）
- 脚本末尾输出统计行：不安全=N, 安全=N（含行大小优化时附该项）

**修复脚本已生成，继续二次验证循环**

**二次验证循环**：
```
clarify 提问：
"修复脚本已生成，是否执行修复？
 1) 执行修复（用户手动执行后继续）
 2) 跳过修复（保留差异，结束任务）"
```

⏸️ **等待用户回答**

如果选择1：
  指导用户执行修复脚本，然后：
  ```
  clarify 提问：
  "修复已执行，是否重新导出CSV并验证修复结果？
   1) 是（使用之前的导出SQL重新导出CSV，提供新CSV路径）
   2) 否（跳过验证，结束任务）"
  ```

  ⏸️ **等待用户回答**

  如果选择1：
    - 指导用户用之前的导出SQL重新导出CSV
    - 提问新的CSV路径
    - 重新执行步骤B6（调用固化脚本重新比对）
    - **循环直到用户确认"没问题了/可以结束"**
    - ✅ 验证完成，进入完成确认阶段

---

### 子流程C：标准文档 vs 原表自检 + TRAN/LOG直接重建

**适用场景**：标准文档只定义原表结构，TRAN/LOG表是数据交换影子表，无需逐字段比对，直接按原表（文档）结构重建，**无主键**。

**与子流程B的关系**：C = B 的一个选项（TRAN/LOG处理方式选"直接重建"），流程步骤完全复用 B1~B5，仅在 B6 生成修复脚本时改变 TRAN/LOG 的处理逻辑。

**核对逻辑**：
- **原表**：与文档标准逐字段核对（缺失字段、多余字段、类型/长度/精度、主键）
- **TRAN/LOG表**：不做逐字段比对，直接生成重建语句（DROP + CREATE）
  - 表结构 = 文档定义的全部字段（无主键、无公共字段SCZT/SYZT等）
  - 重建方式 = 若表存在则 DROP，再 CREATE（结构严格按文档）
  - 表不存在时直接 CREATE

#### 步骤C1：提供Word标准文档路径
（同步骤B1）记录：`docx_path`

#### 步骤C2：确认基准库数据库类型
（同步骤A2）记录：`base_db_type = oracle | sqlserver`

#### 步骤C3：确认客户端工具
（同步骤A3）记录：`base_client = navicat | dbeaver | plsqldev | ssms`

#### 步骤C4：解析Word文档 → 固定格式MD
（同步骤B4，完整模式，强制加载 `word_parsing_guide.md` + `table_structure_template.md`）
- 输出：`<任务目录>/table_structure.md`

#### 步骤C5：生成导出SQL → 指导导出CSV → 获取CSV路径
（同步骤B5，强制调用 `generate_export_sql.py`）
```bash
python scripts/generate_export_sql.py \
  --md <任务目录>/table_structure.md \
  --db-type <oracle|sqlserver> \
  --output <任务目录>/export_<db_type>.sql
```
- 导出SQL含原表 + _TRAN + _LOG（生成器自动扩展），TRAN/LOG表在CSV中是否存在均不影响重建生成

#### 步骤C6：生成修复脚本（原表核对 + TRAN/LOG重建）

⚠️ **强制加载参考文档**（必须先读取，否则不能继续）：
- `references/compare_rules.md` — 比对规则
- `references/type_mapping.md` — 数据类型映射

⚠️ **强制调用固化脚本**（禁止自己编写替代脚本）：
```bash
python scripts/compare_with_docx.py \
  --md <任务目录>/table_structure.md \
  --csv <CSV路径> \
  --db-type <oracle|sqlserver> \
  --task-dir <任务目录> \
  --tran-log-mode rebuild
```

**脚本自动完成**：
1. 解析 `table_structure.md` + CSV
2. **原表**：逐字段核对文档标准（缺失字段ADD、多余字段、类型/长度/精度、主键一致性）
3. **TRAN/LOG表**：不比对字段，直接生成重建脚本：
   - 表存在 → `DROP TABLE`（带存在性判断）+ `CREATE TABLE`（文档字段，无主键、无公共字段）
   - 表不存在 → 仅 `CREATE TABLE`
4. 生成统一修复脚本：`<任务目录>/fix_<db_type>_<时间戳>.sql`
   - 结构：【安全修改】原表新增/扩大字段、【不安全修改】原表类型变更等需人工确认项、【TRAN/LOG重建】集中独立章节
   - 重建语句默认**注释状态**（脚本头部提示：TRAN/LOG重建会清空表数据，需人工确认后放开执行）

**修复脚本已生成，继续二次验证循环**（同B6，循环直到用户确认"没问题了/可以结束"）

---

## 阶段2：多库比对（task_type包含multi_compare时执行）

**⚠️ 本阶段从头开始，不复用前面自检阶段的CSV。**

### 步骤M1：确认基准库数据库类型
（同步骤A2）记录：`base_db_type = oracle | sqlserver`

### 步骤M2：确认客户端工具
（同步骤A3）记录：`base_client = navicat | dbeaver | plsqldev | ssms`

### 步骤M3：确定表范围
```
clarify 提问：
"需要对比哪些表？
 1) 从标准文档解析（提供Word文档路径）
 2) 手动输入表名（逗号分隔）
 3) 全部表（从基准库CSV中提取所有表名）"
```

⏸️ **等待用户回答**

- 如果选择1：
  - 提问Word文档路径
  - ⚠️ **强制加载参考文档**（必须先读取，否则不能继续）：
    - `references/word_parsing_guide.md` — Word文档解析指南
    - `references/table_structure_template.md` — 表结构MD固定模板
  - 在任务目录下编写临时python脚本，按解析指南的"轻量模式"只解析表清单部分
  - 输出：`<任务目录>/tables_list.md`（必须符合MD模板格式）
- 如果选择2：
  - 用户直接输入表名（逗号分隔）
  - 生成 `tables_list.md`（按固定模板格式）
- 如果选择3：
  - 跳过表清单MD，后续从基准库CSV提取所有表名
  - **注意**：M4 的 `generate_export_sql.py --md` 参数为必填，选择"全部表"时无 `tables_list.md` 可用。此时有两种处理方式：
    - ① 导出SQL不限表范围：直接用模板脚本 `scripts/export_table_structure_<db>.sql`（去掉 `{TABLE_LIST}` 的 `IN (...)` 过滤）指导用户导出全部表
    - ② 先让用户导出CSV，再从CSV提取全部表名生成 `tables_list.md`，供 M4/M5/M7 使用
  - 推荐方式①：全部表场景下导出SQL不需要表名过滤
- 记录：`table_scope = docx | manual | all`
- ✅ 表范围已确定，继续下一步

### 步骤M4：生成导出SQL → 指导导出CSV → 获取基准库CSV路径

⚠️ **强制调用固化脚本**（禁止自己编写替代脚本）：
```bash
python scripts/generate_export_sql.py \
  --md <任务目录>/tables_list.md \
  --db-type <oracle|sqlserver> \
  --output <任务目录>/export_<db_type>.sql
```

**操作**：
1. 根据 `base_db_type` 调用固化脚本生成导出SQL
2. 根据 `base_client` 指导用户执行导出SQL并导出CSV
   - ⚠️ **CSV必须符合** `references/export_guide.md` 的固定格式模板
   - ⚠️ **CSV编码必须为UTF-8**
3. 提示用户：导出完成后，请提供CSV文件路径

```
clarify 提问：
"CSV已导出，请提供CSV文件路径"
```

⏸️ **等待用户回答**

4. 获取并验证CSV文件
- 记录：`base_csv_path`
- ✅ 基准库CSV已获取，继续下一步

### 步骤M5：选择目标操作
```
clarify 提问：
"接下来做什么？
 1) 全量重建（从基准库CSV生成目标库的完整DDL重建脚本）
 2) 修复（对比基准库和目标库，生成修复脚本）"
```

⏸️ **等待用户回答**
- 如果选择1（全量重建）：
  ```
  clarify 提问：
  "目标库数据库类型？
   1) Oracle
   2) SQL Server"
  ```
  - 根据目标库类型调用对应的固化脚本（使用--md参数读取表清单）：
    ```bash
    # Oracle
    python scripts/generate_oracle_ddl.py --csv <基准库CSV> --md <任务目录>/tables_list.md --mode rebuild --output <任务目录>/rebuild_oracle.sql
    # SQL Server
    python scripts/generate_sqlserver_ddl.py --csv <基准库CSV> --md <任务目录>/tables_list.md --mode rebuild --output <任务目录>/rebuild_sqlserver.sql
    ```
  - **注意**：M3 选"全部表"（无 tables_list.md）时，省略 `--md` 参数即可，脚本会处理CSV中全部表
  - 生成完整DDL重建脚本
  - **流程结束**（跳到阶段3）

- 如果选择2（修复）→ 进入步骤M6

### 步骤M6：获取目标库信息并导出CSV

**M6a：选择目标库CSV来源**
```
clarify 提问：
"目标库CSV来源：
 1) 指定目录（对比目录下所有CSV文件）
 2) 手动指定CSV文件列表
 3) 手动导出目标库CSV（指导用户导出）"
```

⏸️ **等待用户回答**

- 如果选择1：
  - 提问目录路径
  - 自动扫描目录下所有CSV文件
  - 提问："是否排除基准库CSV？1) 是 2) 否"
  - 记录：`target_csv_dir`, `exclude_base`
- 如果选择2：
  - 提问CSV文件路径列表（逗号分隔）
  - 记录：`target_csv_paths`
- 如果选择3：
  - 确认目标库数据库类型（Oracle/SQL Server）
  - 确认客户端工具
  - 调用固化脚本生成导出SQL（复用 M4 的 `tables_list.md`）：
    ```bash
    python scripts/generate_export_sql.py --md <任务目录>/tables_list.md --db-type <目标库类型> --output <任务目录>/export_target_<db_type>.sql
    ```
  - 指导用户导出目标库CSV（CSV必须符合固定格式模板）
  - 获取CSV文件路径

**M6b：自动检测目标库类型**
- 对每个目标库CSV自动检测数据库类型（Oracle/SQL Server）
- 检测逻辑：通过DATA_TYPE特征判断（VARCHAR2/NUMBER为Oracle，VARCHAR/DECIMAL为SQL Server）

### 步骤M7：比对CSV → 生成修复脚本 → 指导执行 → 二次验证（循环）

⚠️ **强制加载参考文档**（必须先读取，否则不能继续）：
- `references/compare_rules_db_to_db.md` — 两个库之间的比对规则（决定哪些差异需要修复，哪些忽略）
- `references/type_mapping.md` — 数据类型映射

⚠️ **强制调用固化脚本**（禁止自己编写替代脚本）：
```bash
python scripts/compare_db_to_db.py \
  --base-csv <基准库CSV路径> \
  --target-csv <目标库CSV路径> \
  --target-name <目标库名称> \
  --target-db-type <oracle|sqlserver> \
  --task-dir <任务目录> \
  --tables-scope <表清单文件路径（可选）>
```

对每个目标库执行对比（仅对比表范围内定义的表，比对规则详见 `references/compare_rules_db_to_db.md`）：
- 对比维度：缺失表、缺失字段、类型不一致、长度/精度不一致
- 生成修复脚本：`fix_<db_type>_<target_name>.sql`
- 脚本格式：类型不一致的语句注释置前；新增字段（ADD，全部为NULL）；扩大长度/精度（ALTER）；每条带原因注释
- 统计行：新增表=X, 新增字段=X, 扩大长度=X, 扩大精度=X, 需人工确认=X

**修复脚本已生成。**（二次验证循环同步骤B6，重新执行步骤M7比对，循环直到用户确认"没问题了/可以结束"，然后进入汇总报告阶段）

### 步骤M8：输出汇总报告
- 生成 `compare_report.md`，包含：基准库信息、目标库列表（名称、类型、差异统计）、生成的修复脚本列表、验证结果、待处理问题（如有）

---

## 阶段3：完成确认

**步骤3-1：最终确认**
```
clarify 提问：
"任务已完成，是否需要：
 1) 查看某个修复脚本详情
 2) 重新执行某个步骤
 3) 结束任务"
```

⏸️ **等待用户回答**

- ✅ 根据用户选择执行相应操作

---

## 关键规则

### 0. 过程文件目录规则（必须严格遵守）
**所有过程文件必须生成到当前任务的工作目录下，不得随意放置！**

- 任务开始时，先确认工作目录（通常是用户提供的CSV所在目录，或用户指定的任务目录）
- 所有中间产物（导出SQL、MD文件、修复脚本、对比报告）统一放在该目录下
- **绝对禁止**将过程文件放到`~/winning/日常工作/`或其他任意路径
- 如果不确定目录在哪，用clarify提问确认

### 1. 必须使用clarify提问的场景
- 任务类型选择（步骤1）
- 自检类型选择（步骤2）
- 表范围来源选择（步骤A1/M3）
- 基准库数据库类型（步骤A2/B2/M1）
- 客户端工具选择（步骤A3/B3/M2）
- 是否执行修复（步骤A5/B6/M7，可选）
- 修复后是否重新导出验证（步骤A5/B6/M7，可选）
- 目标库来源选择（步骤M6）
- 目标操作选择（步骤M5：全量重建/修复）
- 完成确认（步骤3-1）

### 2. 模板与脚本依赖
详见"全局通用基础依赖"和"强制执行规则F1"。辅助工具：`generate_oracle_ddl.py`、`generate_sqlserver_ddl.py`（重建场景，可选）。

### 3. 脚本生成规范
- 每条ALTER语句必须有注释说明修改原因
- 需人工确认的语句必须注释掉，放在脚本最前面
- 统计行必须准确
- DEFAULT值转换详见 `references/type_mapping.md`

### 4. 精度判断规则
- 同时比较precision和scale
- 目标库precision >= 基准库precision 且 target_scale >= base_scale 时，不生成修复语句

### 5. TRAN/LOG表规则
- **各自独立比对**：原表、TRAN表（_TRAN后缀）、LOG表（_LOG后缀）各自独立与文档标准比对，不是互相比较
- **无主键**：TRAN表和LOG表不能有主键（PK_FLAG应为空/N）
- **统一修复脚本**：三表的问题合并到同一个修复脚本中（`fix_{db_type}_{时间戳}.sql`），不按表类型分文件
- **直接重建模式**（`--tran-log-mode rebuild`，子流程C）：TRAN/LOG表不做逐字段比对，直接生成 DROP + CREATE 重建语句，结构严格按文档字段（无主键、不加公共字段 SCZT/SYZT 等）；重建语句默认注释状态，需人工确认（会清空表数据）

### 6. 新增字段规则
- 新增字段时，**全部为NULL（可空），不允许NOT NULL，不加DEFAULT**
- 即使文档中标注约束为M，修复新增时也只能加NULL
- 理由：第三方不传就不入库，由业务逻辑保证

### 7. 不安全修改规则
- 每条不安全修改必须包含**完整可执行的ALTER语句**（只是前面加`--`注释）
- **禁止使用`...`省略号占位**
- 用户放开注释即可直接执行
- 每条注释需说明：修改理由、当前值、期望值

### 8. 数据类型映射
详见 `references/type_mapping.md`，包含完整的类型映射规则。

---

## 文档目录规范

在当前项目根目录下创建 `db-schema-verify-docs/task-{日期}-{任务类型}/`，所有过程文件（table_structure.md、tables_list.md、export_*.sql、fix_*.sql、compare_report.md、parse_docx_temp.py）统一放在该任务目录下（详见关键规则0）。禁止在其他位置生成文件。
