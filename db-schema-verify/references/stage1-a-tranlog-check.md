# 阶段1-子流程A：原表 vs TRAN/LOG表自检

> 本文件从 SKILL.md 外置。**触发条件**：用户在「选择自检类型」中选 **A**（`check_type = tran_log`）。执行前必读本文件，按其步骤逐步执行。

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

