# 阶段2：多库比对

> 本文件从 SKILL.md 外置。**触发条件**：仅当 `task_type` 包含 `multi_compare`（阶段0选了「先自检，再多库比对」的 full_flow）时执行。执行前必读本文件。

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

