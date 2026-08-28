# 阶段1-子流程C：标准文档 vs 原表自检 + TRAN/LOG直接重建

> 本文件从 SKILL.md 外置。**触发条件**：用户在「选择自检类型」中选 **C**（`check_type = docx_compare_rebuild`）。执行前必读本文件，按其步骤逐步执行。

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

