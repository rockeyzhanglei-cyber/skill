# 阶段1-子流程B：标准文档 vs 库表结构自检（核心流程）

> 本文件从 SKILL.md 外置。**触发条件**：用户在「选择自检类型」中选 **B**（`check_type = docx_compare`）。执行前必读本文件，按其步骤逐步执行。

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

