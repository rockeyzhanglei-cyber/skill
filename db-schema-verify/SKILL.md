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

以下三个文件是**所有流程的基础依赖**，在任何流程开始前**必须先加载到上下文**：

1. **`references/word_parsing_guide.md`** — Word文档解析指南
   - 指导如何理解标准文档的结构和字段定义
   - 用于生成临时解析脚本时必须参考

2. **`references/table_structure_template.md`** — 数据结构MD固定模板
   - 约束如何存储从标准文档解析出的数据结构
   - 所有中间产物（table_structure.md）必须符合此格式
   - 固化脚本依赖此格式进行解析

3. **`references/export_guide.md`** — CSV导出指南
   - 定义了导出CSV的固定列结构和操作指南
   - 固化脚本依赖此格式进行解析

**强制执行方式**：
- 在每个流程的第一步（如A1、B1等），**必须立即调用 `skill_view(name="db-schema-verify", file_path=...)` 加载这三个文件**
- 加载完成后才能继续后续步骤
- 这些文件是固化脚本正确工作的前提，跳过它们会导致中间产物格式错误、固化脚本解析失败

---

## 强制执行规则（违反会导致流程失败）

### 规则F0：逐步执行，禁止跳步（最重要）

**每个步骤必须独立执行，等待用户回答后才能进入下一步。**

具体约束：
1. **每个clarify只问一个问题**，等用户回答后再问下一个
2. **禁止合并提问**：不能在一个clarify里问多个问题
3. **禁止推测答案**：即使你觉得知道答案，也必须等用户确认
4. **步骤间必须有停顿**：完成一个步骤后，必须明确说"现在进入步骤X"

**为什么不能跳步？**
- 用户可能在不同场景下有不同选择（如Oracle vs SQL Server需要不同的导出SQL）
- 跳过步骤会导致后续流程使用错误的配置
- 用户希望掌控流程，而不是被模型"代表"做决定

**违反后果**：流程混乱、生成错误的SQL、用户体验差

**检查清单**（每个步骤前自检）：
- [ ] 前一步骤用户是否已明确回答？
- [ ] 当前步骤的clarify是否只包含一个问题？
- [ ] 我是否在等待用户回答，而不是继续往下走？

---

### 规则F1：必须使用固化脚本，禁止自己编写替代方案
- `scripts/generate_export_sql.py` — 生成导出SQL（必须调用，禁止自己写SQL）
- `scripts/compare_with_docx.py` — 对比文档vs库表并生成修复脚本（必须调用，禁止自己写对比逻辑）
- `scripts/self_check.py` — 原表vs TRAN/LOG自检（必须调用，禁止自己写自检逻辑）
- `scripts/compare_db_to_db.py` — 库vs库结构比对（阶段3必须调用，禁止自己写对比逻辑）

**违反后果**：自己编写的脚本无法利用固定格式的优势，会重复造轮子，且可能引入错误。

### 规则F2：必须加载参考文档，禁止跳过
- 每个流程开始前，必须先加载"全局通用基础依赖"中的三个文件
- 生成临时解析脚本时，必须参考 `word_parsing_guide.md` 和 `table_structure_template.md`
- 这些文档不是建议，是必须执行的步骤

**违反后果**：不加载参考文档会导致生成的中间产物格式错误，后续固化脚本无法解析，整个流程失败。

### 规则F3：必须按流程步骤执行，禁止跳步
- 每个步骤的输入都依赖前一步骤的输出
- 跳步会导致缺少必要的数据，流程无法继续

**违反后果**：流程中断或产出错误的结果。

---

## 流程架构

```
阶段0：任务类型选择
├─ 单库自检
│  ├─ A) 原表 vs TRAN/LOG表自检
│  └─ B) 标准文档 vs 库表结构自检（核心流程）
└─ 多库比对（基准库 vs 多个目标库）
```

## 核心概念：模板与固化

本 Skill 的核心设计原则是**模板驱动 + 程序固化**：

1. **固定模板**：所有中间产物都有固定格式，下游脚本依赖这些格式
   - `table_structure_template.md` — 数据表结构MD文件的固定格式
   - `export_guide.md` — 导出CSV的固定列结构和操作指南

2. **固化脚本**：基于固定模板的转换逻辑被固化为可复用脚本
   - `scripts/generate_export_sql.py` — 从固定格式MD生成导出SQL
   - `scripts/compare_with_docx.py` — 对比MD+CSV，生成修复脚本（一步完成）

3. **临时脚本**：文档解析逻辑因文档格式差异大，每次临时生成
   - 但必须严格参考 `references/word_parsing_guide.md`（解析指南）
   - 必须严格输出符合 `references/table_structure_template.md`（固定模板）

## 文件管理原则

**合并优先于删除**：整理参考文件时，如果文件中有内容可能与其他文件重叠，必须先对比确认内容已覆盖后再删除。不能把有用的东西直接删掉。优先合并到保留文件中，而不是简单删除。

**单一数据源原则**：同一数据结构（如DataType映射表、CSV列定义）只允许在**一个文件**中定义完整版本，其他文件必须引用而非复制。修改映射后必须grep所有references检查引用一致性。

**文件删除/重命名程序**：
1. 删除前必须执行 `grep -rn "被删文件名" . --include="*.md" --include="*.py"` 查找所有引用
2. 更新SKILL.md和其他文件中的引用
3. 确认无残留引用后再删除原文件

**配置项变更程序**：修改任何配置项（编码/参数/格式）时：
1. grep全Skill检查所有相关文件（包括脚本头部的docstring、argparse help文本）
2. 更新SKILL.md、scripts/*.py、references/*.md中的对应内容
3. 不能只改函数默认值就认为完成——必须验证全Skill一致性

**文件拆分程序**：当从一个大文件中拆分出独立参考文件时：
1. 原文件中的对应内容必须删除或替换为引用
2. 不能两边都保留完整版本
3. 添加引用说明："详见 references/xxx.md"

---

## 提问风格原则

**逐个提问**：每个clarify只问一个问题，等用户回答后再问下一个。不要在一个clarify里塞多个问题。用户习惯一次处理一个决定。

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
 B) 标准文档 vs 库表结构自检（保证库表符合文档标准）"
```

⏸️ **等待用户回答**

- 记录：`check_type = tran_log | docx_compare`
- ✅ 用户已选择，继续下一步

---

### 子流程A：原表 vs TRAN/LOG表自检

**核对逻辑**：以原表结构为准，分析TRAN表和LOG表与原表的差异，生成修复脚本使TRAN/LOG表与原表一致。

**⚠️ 子流程A结束后流程结束**，不需要再进入子流程B。子流程B是独立的另一种自检类型。

如果用户在阶段0选了"先自检，再多库比对"（full_flow），子流程A结束后直接进入阶段3（多库比对）。

**Word文档解析共用**：子流程A和子流程B共用同一个 `references/word_parsing_guide.md` 解析指南。区别在于：
- 子流程A只需解析"表清单"（哪些表要核对）
- 子流程B需要解析完整结构（每张表的字段定义）

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
2. 根据 `base_client` 指导用户执行导出SQL并导出CSV
   - ⚠️ **CSV必须符合** `references/export_guide.md` 的固定格式模板
   - ⚠️ **CSV编码必须为UTF-8**（与固化脚本的默认编码一致）
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

**修复脚本特性**：
- 每条语句带存在性判断（表存在且字段不存在/存在才执行）
- TRAN/LOG表不存在时生成CREATE TABLE（结构同原表，无主键）
- 需人工确认的语句已注释（类型不一致、DEFAULT值冲突）

**⚠️ 脚本生成后任务结束。** 用户自行在SSMS/PL/SQL Developer中执行修复脚本。

---

### 子流程B：标准文档 vs 库表结构自检（核心流程）

**核对逻辑**：标准文档只定义了原表结构，但库里有三张表（原表、TRAN表、LOG表）。需要将文档中的表结构分别与库里这三张表核对，生成统一修复脚本。

#### 步骤B1：提供Word标准文档路径
```
clarify 提问：
"请提供Word标准文档路径"
```
- 验证文档存在且可读取
- 记录：`docx_path`

#### 步骤B2：确认基准库数据库类型
```
clarify 提问：
"基准库是什么数据库类型？
 1) Oracle
 2) SQL Server"
```
- 记录：`base_db_type = oracle | sqlserver`

#### 步骤B3：确认客户端工具
```
clarify 提问：
"你用什么客户端连接数据库？
 1) Navicat
 2) DBeaver
 3) PL/SQL Developer（仅Oracle）
 4) SSMS（仅SQL Server）"
```
- 记录：`base_client = navicat | dbeaver | plsqldev | ssms`

---

#### 步骤B4：解析Word文档 → 固定格式MD

> ⚠️ 此步骤输出必须符合 `references/table_structure_template.md` 的固定格式，因为后续所有脚本都依赖此格式。

**强制加载的参考文档**：
1. `references/word_parsing_guide.md` — 解析指南（必读，包含文档结构特征和代码示例）
2. `references/table_structure_template.md` — MD固定模板（必读，定义输出格式）

**操作方式**：
1. 加载上述两个参考文档
2. 在**任务目录下**编写一次性python脚本（如 `parse_docx_temp.py`）
3. 脚本使用python-docx解析Word文档
4. **强制约束**：脚本输出必须符合 `table_structure_template.md` 定义的固定格式

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

**脚本自动完成**：
1. 从 `table_structure.md` 的 `## 表清单` 章节提取所有英文表名
2. 扩展为 `_TRAN/_LOG` 后缀
3. 读取对应的SQL模板（`scripts/export_table_structure_oracle.sql` 或 `scripts/export_table_structure_sqlserver.sql`）
4. 替换模板中的 `{TABLE_LIST}` 占位符
5. 生成导出SQL文件

**验证**：检查生成的SQL文件中表数量是否正确。

**⚠️ CSV格式约束**：导出的SQL必须保证用户用它导出的CSV符合 `references/export_guide.md` 定义的固定列结构。否则后续固化脚本 `compare_with_docx.py` 无法正确解析。

**⚠️ CSV编码约束**：CSV文件必须使用 UTF-8 编码导出（与固化脚本的默认编码一致）。

**5b. 指导用户导出CSV**

根据`base_client`提供对应客户端操作指引：
- 读取 `references/export_guide.md`（导出操作指南）
- PL/SQL Developer：新建SQL窗口 → 粘贴SQL → F8执行 → 右键结果 → Export → CSV（UTF-8）
- Navicat：新建查询 → 粘贴SQL → 执行 → 导出结果 → CSV（编码UTF-8）
- DBeaver：新建SQL编辑器 → 粘贴SQL → Ctrl+Enter执行 → 右键结果 → Export Data → CSV（UTF-8）
- SSMS：新建查询 → 粘贴SQL → F5执行 → 全选结果 → 复制到Excel → 另存CSV（UTF-8）

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
python scripts/compare_with_docx.py \
  --md <任务目录>/table_structure.md \
  --csv <CSV路径> \
  --db-type <oracle|sqlserver> \
  --task-dir <任务目录>
```

**核对逻辑**：文档中定义的原表结构，需要分别与库里的原表、TRAN表、LOG表核对，生成统一修复脚本。

**脚本自动完成**：
1. 解析 `table_structure.md`（从Word文档标准，定义的是原表结构）
2. 解析 CSV（从基准库导出，包含原表+TRAN表+LOG表）
3. 将文档中的原表结构分别与库里三张表核对：
   - 文档原表 vs 库里原表 → 发现原表的问题
   - 文档原表 vs 库里TRAN表 → 发现TRAN表的问题
   - 文档原表 vs 库里LOG表 → 发现LOG表的问题
4. 对比维度：
   - 缺失字段
   - 多余字段（按通用规则过滤）
   - 类型不一致
   - 长度/精度/小数位不一致
5. 生成统一修复脚本：`<任务目录>/fix_<db_type>.sql`（三表问题合并到一个文件）

**修复脚本结构**：
- **【不安全修改】**（注释状态，需人工确认）：
  - 类型变更、多余必填字段
  - 每条必须是完整可执行的ALTER语句，只是前面加`--`注释
- **【安全修改】**（直接可执行）：
  - 新增字段（ADD COLUMN）—— **全部为NULL，不允许NOT NULL**
  - 扩大字段长度/精度（MODIFY扩大）
- 脚本末尾附统计行：不安全=N, 安全=N，原表=N, TRAN=N, LOG=N

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

## 阶段3：多库比对（task_type包含multi_compare时执行）

**⚠️ 本阶段从头开始，不复用前面自检阶段的CSV。**

### 步骤M1：确认基准库数据库类型
```
clarify 提问：
"基准库是什么数据库类型？
 1) Oracle
 2) SQL Server"
```

⏸️ **等待用户回答**

- 记录：`base_db_type = oracle | sqlserver`
- ✅ 数据库类型已确认，继续下一步

### 步骤M2：确认客户端工具
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
  - 跳过，后续从基准库CSV提取所有表名
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
  - 根据目标库类型调用对应的固化脚本：
    - Oracle → `scripts/generate_oracle_ddl.py`
    - SQL Server → `scripts/generate_sqlserver_ddl.py`
  - 生成完整DDL重建脚本
  - **流程结束**（跳到阶段4）

- 如果选择2（修复）→ 进入步骤M7

### 步骤M7：获取目标库信息并导出CSV

**M7a：选择目标库CSV来源**
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
  - 调用固化脚本生成导出SQL
  - 指导用户导出目标库CSV（CSV必须符合固定格式模板）
  - 获取CSV文件路径

**M7b：自动检测目标库类型**
- 对每个目标库CSV自动检测数据库类型（Oracle/SQL Server）
- 检测逻辑：通过DATA_TYPE特征判断（VARCHAR2/NUMBER为Oracle，VARCHAR/DECIMAL为SQL Server）

### 步骤M8：比对CSV → 生成修复脚本 → 指导执行 → 二次验证（循环）

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

对每个目标库执行对比（仅对比表范围内定义的表）：
- 对比维度：
  - 缺失表
  - 缺失字段
  - 类型不一致
  - 长度/精度不一致
- 生成修复脚本：`fix_<db_type>_<target_name>.sql`
- 脚本格式：
  - 类型不一致的语句（注释状态，需人工确认，放在脚本最前面）
  - 新增字段（ADD语句）—— **全部为NULL**
  - 扩大长度（ALTER语句）
  - 扩大精度（ALTER语句）
- 每条语句必须有注释说明修改原因
- 统计行：新增表=X, 新增字段=X, 扩大长度=X, 扩大精度=X, 需人工确认=X

**修复脚本已生成，继续二次验证循环**

**二次验证循环**：
```
所有修复脚本生成完成后：
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
      - 重新执行步骤M8比对
      - **循环直到用户确认"没问题了/可以结束"**
      - ✅ 验证完成，进入汇总报告阶段

### 步骤M9：输出汇总报告
- 生成 `compare_report.md`
- 包含：
  - 基准库信息
  - 目标库列表（名称、类型、差异统计）
  - 生成的修复脚本列表
  - 验证结果
  - 待处理问题（如有）

---

## 阶段4：完成确认

**步骤4-1：最终确认**
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
- 是否执行修复（步骤A5/B6/M8，可选）
- 修复后是否重新导出验证（步骤A5/B6/M8，可选）
- 目标库来源选择（步骤M7）
- 目标操作选择（步骤M5：全量重建/修复）
- 完成确认（步骤4-1）

### 2. 模板与脚本依赖

**固定模板**（所有中间产物必须符合）：
- `references/table_structure_template.md` — 数据表结构MD的固定格式
- `references/export_guide.md` — 导出CSV的固定列结构和操作指南

**固化脚本**（基于固定模板的转换逻辑）：
- `scripts/generate_export_sql.py` — 从固定格式MD生成导出SQL
- `scripts/compare_with_docx.py` — 对比MD+CSV，生成修复脚本（一步完成）
- `scripts/self_check.py` — 原表 vs TRAN/LOG自检
- `scripts/compare_db_to_db.py` — 库vs库结构比对（阶段3使用）

**辅助工具**（可选使用）：
- `scripts/extract_tables_from_docx.py` — 从Word文档提取表名（辅助）
- `scripts/generate_oracle_ddl.py` — 从CSV生成Oracle完整DDL（重建场景）
- `scripts/generate_sqlserver_ddl.py` — 从CSV生成SQL Server完整DDL（重建场景）

**参考文档**（按流程类型强制加载）：
- `references/word_parsing_guide.md` — Word文档解析指南（强制加载）
- `references/table_structure_template.md` — 数据结构MD固定模板（强制加载）
- `references/export_guide.md` — CSV导出指南（强制加载）
- `references/compare_rules.md` — 文档vs库表比对规则（子流程B强制加载）
- `references/compare_rules_db_to_db.md` — 库vs库比对规则（阶段3强制加载）
- `references/type_mapping.md` — 数据类型映射（比对时强制加载）
- `references/self-check-standards.md` — 自检标准7维度（子流程A强制加载）
- `references/pitfalls.md` — 历史踩坑记录（遇到类似问题时查阅）

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
- **统一修复脚本**：三表的问题合并到同一个修复脚本中（`fix_{db_type}.sql`），不按表类型分文件

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

**文档目录路径**：`{当前项目路径}/db-schema-verify-docs`

说明：
- 在当前Agent的项目根目录下创建 `db-schema-verify-docs` 文件夹
- 不要使用绝对路径，要基于当前工作目录动态创建

**目录结构**：
```
db-schema-verify-docs/
├── task-{日期}-{任务类型}/          # 每个任务独立目录
│   ├── table_structure.md          # 表结构MD（产物B）
│   ├── tables_list.md              # 表清单（产物A，多库比对场景）
│   ├── export_{db_type}.sql        # 导出SQL
│   ├── fix_{db_type}.sql           # 修复脚本
│   ├── compare_report.md           # 对比报告
│   └── parse_docx_temp.py          # 一次性解析脚本
```

**重要规则**：
- 所有过程文件必须生成到任务目录下
- 禁止在项目目录、临时目录或其他位置生成文件
