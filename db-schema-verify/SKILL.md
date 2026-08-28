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

### 子流程分发（按用户选择的 check_type 执行对应子流程）

| check_type | 触发条件 | 执行前必须读取 |
|-----------|---------|--------------|
| `tran_log` | 用户在「选择自检类型」中选 **A**（原表 vs TRAN/LOG表自检） | [references/stage1-a-tranlog-check.md](references/stage1-a-tranlog-check.md) |
| `docx_compare` | 用户选 **B**（标准文档 vs 库表结构自检，**核心流程**） | [references/stage1-b-docx-compare.md](references/stage1-b-docx-compare.md) |
| `docx_compare_rebuild` | 用户选 **C**（标准文档 vs 原表自检 + TRAN/LOG直接重建） | [references/stage1-c-rebuild.md](references/stage1-c-rebuild.md) |

> **执行前必读**：进入任一子流程前，先完整读取上表对应的参考文档，再按其步骤逐步执行。
> 三个子流程共用 `references/word_parsing_guide.md` 解析指南（A 只解析表清单，B/C 需解析完整字段定义）。

## 阶段2：多库比对（task_type 包含 multi_compare 时执行）

> **触发条件**：仅当 `task_type` 包含 `multi_compare`（用户在阶段0选了「先自检，再多库比对」的 full_flow）时执行。
> **执行前必须读取** [references/stage2-multi-compare.md](references/stage2-multi-compare.md)，按其步骤执行。
>
> ⚠️ 本阶段从头开始，**不复用前面自检阶段的 CSV**。

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
