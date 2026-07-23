# 历史踩坑记录

本文档记录了开发和使用本Skill过程中遇到的典型问题和解决方案。遇到类似问题时先查阅此文档。

## 文档结构类问题

### 错误1：假设所有目标库都是SQL Server格式
- **现象**：目标库实际是Oracle格式（VARCHAR2/NUMBER），但脚本只识别VARCHAR/DECIMAL，导致大量差异漏检
- **修复**：读取目标库时通过DATA_TYPE值自动判断格式

### 错误9：导出SQL中OWNER占位符替换错误
- **现象**：`WHERE atc.owner = 'USER'`（加了单引号，变成了字符串'USER'而非Oracle函数）
- **修复**：`{OWNER}`占位符替换时，Oracle直接用`USER`（无引号），SQL Server用`SCHEMA_NAME()`（无引号）
- **规则**：不要问用户Schema名，直接用当前登录用户函数

### 错误10：导出SQL中表清单缺少逗号分隔
- **现象**：生成`IN ('TABLE_A' 'TABLE_B')`，缺少逗号导致SQL语法错误
- **修复**：生成表清单时必须用`', '`分隔每个表名：`IN ('TABLE_A', 'TABLE_B', ...)`

### 错误12：过程文件随意放置
- **现象**：将导出SQL生成到`~/winning/日常工作/...`等非任务目录
- **修复**：所有过程文件必须生成到任务工作目录下。任务开始时先确认工作目录

### 错误13：基准库CSV编码问题（已修复）
- **现象**：早期版本PL/SQL Developer导出的CSV是GBK编码，用UTF-8读取报错
- **修复**：全Skill已统一为UTF-8编码。所有脚本的 `read_csv()` 默认 `encoding='utf-8'`，所有导出指导都要求用户导出UTF-8 CSV
- **注意**：如果用户从旧系统导出GBK CSV，需要手动指定 `--encoding gbk` 参数

### 错误18：文档目录用绝对路径而非相对项目路径
- **现象**：`db-schema-verify-docs`的路径写死为绝对路径
- **修复**：文档目录基于当前Agent的项目路径动态创建，格式为`{当前项目路径}/db-schema-verify-docs`

## Word文档解析类问题

### 错误7：Word文档表格解析失败
- **现象**：自动化解析Word表格时漏字段或解析错误
- **修复**：改为人工解析Word文档，按固定格式生成MD文件，再用程序对比

### 错误11：Word文档表名提取包含版本号后缀
- **现象**：从Word文档提取的表名带有版本号数字后缀（如`BA_SYJBK59`而非`BA_SYJBK`），导致匹配失败
- **修复**：提取表名后需检查是否包含数字后缀，与标准表名（不带版本号）进行匹配。版本号后缀通常是文档章节号，不是表名的一部分

### 错误14：让手动解析Word文档
- **现象**：解析指南写了"为什么需要人工解析"，让用户手动操作
- **修复**：解析指南是给AI参考的，AI应使用python-docx自动解析。指南内容已全面重写

### 错误15：TRAN/LOG表未纳入核对
- **现象**：只对比了原表，忽略了TRAN/LOG表
- **修复**：TRAN/LOG表也纳入核对，但注意：是各自独立与文档标准比对，不是与原表比对（详见错误20）

### 错误22：Word文档body遍历时Heading3样式值不匹配（致命错误）
- **现象**：使用`doc.element.body`遍历XML元素时，检查`pStyle.get(qn('w:val')) == 'Heading3'`，导致0个Heading被识别，所有字段表都匹配不上表名
- **根因**：python-docx的`para.style.name`返回`"Heading 3"`（含空格），但底层XML的`w:pStyle/@w:val`属性值只是数字`"3"`（或`"1"`、`"2"`）
- **修复**：body遍历时检查`style_val == '3'`匹配Heading 3，不要检查`'Heading3' in style_val`
- **验证方式**：调试时先打印所有段落`pStyle/@w:val`的实际值，确认真实格式

### 错误23：文档表示格式含非数字（如AN..*通配符）
- **现象**：`ValueError: invalid literal for int() with base 10: '*'`，文档中表示格式为`AN..*`（不限制长度）
- **修复**：对type_param和CSV长度/精度值做`try/except (ValueError, TypeError)`包裹，非数字视为0（跳过该维度的长度比较）
- **规则**：所有int()转换必须安全处理，文档中可能出现`*`、空字符串等非数字值

### 错误25：子流程B步骤顺序错误（Word解析在导出SQL之后）
- **现象**：先根据Word文档提取表清单生成导出SQL（步骤B1.3），再解析Word为MD（步骤B2），导致导出SQL的表清单来源不可控
- **根因**：Skill流程中B2（解析MD）放在B1.3（生成导出SQL）之后，顺序颠倒
- **修复**：调整流程为 B1→B2（解析Word为MD）→B3（从MD提取表清单生成导出SQL）→B4→B5→B6（MD+CSV对比）
- **关键**：table_structure.md是所有后续步骤的唯一输入源，必须先生成

### 错误26：一次性脚本固化到Skill的scripts目录
- **现象**：为特定文档编写的解析脚本放在了`scripts/`目录下，与固定的Skill脚本（如`compare_with_docx.py`）混在一起
- **修复**：一次性解析脚本只写在**任务目录**下（如`task-20260720-xxx/parse_docx_temp.py`），不要固化到Skill
- **规则**：`scripts/`目录只放通用的、可复用的固定脚本。特定文档的解析逻辑每次在任务目录临时编写

### 错误27：Skill参考文档未被流程引用
- **现象**：`references/word_parsing_guide.md`、`references/compare_rules.md`、`references/type_mapping.md`等参考文件存在，但流程中没有明确指引AI去加载和使用它们
- **修复**：在对应步骤中明确标注"加载参考文档：`references/xxx.md`（**必读**）"
- **规则**：每个步骤如果依赖参考文档，必须在流程描述中显式引用

### 错误28：Word文本提取时直接拼接元素对象导致TypeError
- **现象**：`TypeError: can only concatenate str (not "CT_Text") to str`，代码写的是 `text += t_elem` 而非 `text += t_elem.text`
- **根因**：`element.iter(qn('w:t'))` 返回的是XML元素对象（CT_Text类型），不是字符串
- **修复**：必须使用 `t_elem.text` 属性获取文本内容
- **正确写法**：
  ```python
  text = ''
  for t_elem in element.iter(qn('w:t')):
      if t_elem.text:
          text += t_elem.text  # 必须取.text属性
  ```

### 错误29：生成的table_structure.md缺少"表清单"章节
- **现象**：步骤B3从table_structure.md提取表清单时，只匹配到0-1个表，导致导出SQL只包含极少数表
- **根因**：解析脚本生成的MD文件直接从"表1：XXX"开始，缺少第一章的表清单表格
- **修复**：解析脚本必须在生成字段定义之前，先生成表清单章节
- **表清单格式**：
  ```markdown
  ## 表清单
  
  | 序号 | 中文名 | 英文表名 | 是否有TRAN | 是否有LOG |
  |------|--------|----------|------------|----------|
  | 1 | 医护人员信息表 | JBYHRYXXB | 否 | 否 |
  | 2 | 科室信息 | JBKSXXB | 否 | 否 |
  ```
- **提取正则**：`r'\|\s*\d+\s*\|\s*[^|]+\s*\|\s*([A-Z_][A-Z0-9_]+)\s*\|'`
- **验证**：生成MD后立即检查表清单章节是否存在，表数量是否正确

### 错误30：S2类型字段的表示格式"N1"/"N2"未被识别为长度
- **现象**：S2类型（数字字符型）字段的表示格式为"N1"、"N2"（表示1位/2位数字），但解析脚本只匹配了"AN..n"格式，导致这些字段的长度全部为空
- **根因**：表示格式解析逻辑不完整，缺少对"N{数字}"格式的匹配
- **修复**：增加正则匹配 `r'[NDT]+(\d+)'` 提取数字部分作为长度
- **示例**：
  - "N1" → 长度1
  - "N2" → 长度2
  - "D10" → 长度10
  - "DT19" → 长度19
- **完整匹配顺序**：
  1. `AN..n` → VARCHAR(n)
  2. `N..n` → VARCHAR(n)
  3. `N{n}` → 根据数据类型决定（N类型→NUMBER(n), S类型→VARCHAR(n)）
  4. `A{n}` → VARCHAR(n)
  5. `[NDT]+{n}` → VARCHAR(n)（新增）

## 数据库操作类问题

### 错误2：SQL Server脚本中使用Oracle函数SYSDATE
- **现象**：生成的SQL Server脚本包含`DEFAULT SYSDATE`，SQL Server不认识该函数
- **修复**：增加`convert_default_to_sqlserver()`函数

### 错误3：基准库CSV列数与目标库不同
- **现象**：基准库有17列（首列为行号），目标库有16列，导致列索引错位
- **修复**：基准库从第2列(index=1)开始取数据，目标库从第1列(index=0)开始

### 错误4：新增字段丢失DEFAULT值
- **现象**：基准库字段有DEFAULT '0'，生成的ADD语句没有带DEFAULT
- **修复**：生成ADD语句时检查并附加DEFAULT子句（经过方言转换）

### 错误5：SYSTIMESTAMP未转换
- **现象**：SQL Server脚本中出现`DEFAULT SYSTIMESTAMP`
- **修复**：在转换映射中补充SYSTIMESTAMP→SYSDATETIME()

### 错误6：精度判断只比较精度不比较标度
- **现象**：基准库NUMBER(8,2)，目标库DECIMAL(18,4)，脚本认为需要扩大精度
- **修复**：当目标库precision >= 基准库precision 且 target_scale >= base_scale 时，不生成修复语句

### 错误8：基准库自检后未重新导出CSV
- **现象**：自检通过后，目标库对比仍然失败
- **修复**：流程中明确要求：修复基准库后，询问是否重新导出CSV并重新验证

### 错误19：不安全修改SQL使用省略号占位（致命错误）
- **现象**：生成`ALTER TABLE X MODIFY Y ...;`这种无法执行的SQL
- **后果**：用户审核确认后放开注释仍然无法执行，必须手动补全SQL
- **修复**：所有注释掉的不安全SQL必须是**完整可执行的语句**，只是前面加`--`注释。用户放开注释即可直接执行。禁止使用`...`省略号或任何占位符

### 错误20：TRAN/LOG表比对方向错误
- **现象**：将TRAN/LOG表与原表做结构一致性比对（检查TRAN/LOG是否和原表一样）
- **修复**：TRAN/LOG表应各自独立与文档标准比对（TRAN vs 文档、LOG vs 文档），不是与原表比对。三表统一使用相同的比对规则和修复规则

### 错误21：生成多个独立修复脚本
- **现象**：为原表、TRAN表、LOG表各生成一个独立修复脚本
- **修复**：所有比对结果合并到一个统一修复脚本中（`fix_{db_type}.sql`），按安全/不安全分类，不按表类型分文件

### 错误24：新增字段添加为NOT NULL导致入库失败
- **现象**：修复脚本中新增字段带`NOT NULL`约束，第三方不传此字段时INSERT报错
- **修复**：所有新增字段必须为`NULL`（可空），不允许`NOT NULL`。即使文档中标注约束为M，新增时也只能加NULL。
- **规则**：新增字段的ALTER语句中不加NOT NULL，不加DEFAULT（第三方不传就不入库，由业务逻辑保证）

### 错误31：把对比和生成修复脚本拆成两个独立步骤
- **现象**：流程中先写"步骤B6：对比MD+CSV"，再写"步骤B7：生成修复脚本"，让AI以为这是两个独立操作
- **根因**：`scripts/compare_with_docx.py` 的 main() 内部已经先调用 `compare_structures()` 做对比，再调用 `generate_fix_script()` 生成修复脚本，是**一步完成**的
- **修复**：步骤B6就是"调用 compare_with_docx.py，完成对比+生成修复脚本"，不需要单独的B7步骤
- **规则**：在流程中引用脚本前，先读脚本的 main() 函数，确认它的完整能力边界，不要凭文件名猜测功能

### 错误32：Skill文件过度膨胀导致AI无法遵循
- **现象**：SKILL.md 膨胀到 791 行（34KB），踩坑记录占一半，AI读不完就丢关键步骤
- **根因**：所有历史经验（30+条踩坑）都堆在SKILL.md里，没有分层
- **修复**：SKILL.md只保留流程+规则（<600行），踩坑记录移到 `references/pitfalls.md` 独立文件。AI按需查阅，不需要每次全读
- **原则**：SKILL.md < 600行是硬上限。超过就拆分到 references/ 下。

### 错误33：跨文件编码不一致导致数据解析失败
- **现象**：CSV导出指导说UTF-8，但固化脚本默认GBK，参考文档又说是GBK，用户导出后脚本读取出错或乱码
- **根因**：SKILL.md、scripts/*.py、references/*.md 三处对CSV编码的描述不一致（UTF-8/GBK混用）
- **修复**：全Skill统一为UTF-8编码
  - `csv-format.md`：注意事项中明确"CSV文件必须使用UTF-8编码"
  - `export_guide.md`：所有导出步骤标注UTF-8
  - `SKILL.md`：A4/B5/M4步骤添加"⚠️ CSV编码必须为UTF-8"
  - 所有脚本：`read_csv()` 默认 `encoding='utf-8'`，argparse默认值改为utf-8
- **规则**：修改配置项（编码/参数/格式）时，必须grep全Skill检查所有相关文件，确保SKILL.md、scripts、references三处一致

### 错误34：SKILL.md步骤描述与脚本实际参数不匹配
- **现象**：SKILL.md写"调用 `scripts/generate_export_sql.py --tables <表清单>`"，但脚本实际只支持 `--md` 参数，导致脚本执行失败
- **根因**：SKILL.md的步骤描述凭记忆编写，没有对照脚本的argparse定义
- **修复**：统一使用 `--md` 参数（脚本只支持这个）
- **规则**：更新SKILL.md中的脚本调用指令前，必须先读取脚本的argparse部分，确认实际支持的参数名和必填/可选性。不要凭文件名或注释猜测参数

### 错误35：脚本依赖的文件未在流程中显式生成
- **现象**：`self_check.py` 需要读取 `table_scope.json`，但流程步骤中没有任何地方说明要创建这个文件，导致脚本运行时报FileNotFoundError
- **根因**：脚本开发时假设表范围信息已存在，但流程设计时没有显式添加生成步骤
- **修复**：在SKILL.md子流程A3中添加明确步骤："生成table_scope.json文件，包含base_tables数组"
- **规则**：如果固化脚本需要读取某个输入文件，流程中必须有显式的"生成该文件"步骤。检查方法：grep脚本中的open()和load操作，确认每个依赖文件都有对应的生成步骤

### 错误36：类型映射与实际用户偏好不符
- **现象**：`type_mapping.md` 中 Oracle VARCHAR2 映射到 SQL Server NVARCHAR，但用户明确偏好VARCHAR（因为Collation已支持中文）
- **根因**：type_mapping.md是从通用知识编写的，没有反映用户的特定偏好
- **修复**：
  - VARCHAR2(n) → VARCHAR(n)（不是NVARCHAR）
  - CHAR(n) → CHAR(n)（不是NCHAR）
  - 长度说明改为"字符数直接对应"（不是"字节÷3"）
- **规则**：类型映射必须与用户的数据库配置偏好一致。用户偏好VARCHAR不用NVARCHAR（因为SQL Server的Collation支持中文）。修改映射前先检查memory中的用户偏好

### 错误37：参考文档内容重复导致混淆
- **现象**：SKILL.md末尾的"通用比对与修复规则"与独立的 `compare_rules.md`、`type_mapping.md` 内容重复，模型可能参考了不同版本导致不一致
- **根因**：新增独立参考文件时，没有删除SKILL.md中的原始内容
- **修复**：SKILL.md改为摘要式引用，删除详细规则内容（约80行）
- **规则**：创建独立参考文件后，必须检查SKILL.md中是否有重复内容。如果有，改为摘要引用（"详见 references/xxx.md"），删除详细规则。SKILL.md只保留高层流程+摘要规则+强制标记

### 错误38：导出SQL的列定义不完整
- **现象**：`export_guide.md` 只列出了12个必需列，但CSV格式规范要求16列（缺少PK_POSITION、CHAR_LENGTH等），导致导出的CSV缺少关键字段
- **根因**：export_guide.md编写时没有对照csv-format.md的完整列定义
- **修复**：export_guide.md中列出完整的16列定义，包括每列的说明和示例值
- **规则**：如果多个参考文件描述同一数据结构（如CSV列定义），必须完全一致。修改一处后必须grep其他文件检查是否需要同步更新

## 参考文件维护类问题

### 错误39：S3类型映射在多个参考文件中不一致（已修复）
- **现象**：`word_parsing_guide.md` 中S3映射为 "VARCHAR2/NVARCHAR2"（二选一），但 `type_mapping.md` 中S3映射为 "NVARCHAR2"（明确唯一）。两处矛盾会导致解析时行为不确定。
- **根因**：两个文件各自维护了独立的DataType映射表，修改一处没有同步另一处
- **修复**：
  1. 确定S3的正确映射：S3(汉字型) → Oracle用VARCHAR2，SQL Server用VARCHAR（用户明确要求，不用NVARCHAR）
  2. 删除 `word_parsing_guide.md` 中"数据类型含义"章节，改为引用 `type_mapping.md`
  3. 表示格式解析规则保留在 `word_parsing_guide.md` 中（因为解析相关，不是映射相关）
  4. `compare_with_docx.py` 中 `doc_type_to_db()` 函数确认S1/S2/S3/S → VARCHAR2(Oracle)/VARCHAR(SQL Server)
- **规则**：同一数据结构（如DataType映射表）只允许在**一个文件**中定义完整版本（`type_mapping.md`），其他文件必须引用而非复制。修改映射后必须grep所有references检查引用一致性。

### 错误40：文档解析参考文件中存在重复内容（已修复）
- **现象**：`word_parsing_guide.md`（271行）和 `type_mapping.md`（71行）都包含完整的DataType→数据库类型映射表，内容高度重叠
- **根因**：type_mapping.md是后来独立出来的，但word_parsing_guide.md中的原始表格没有删除
- **修复**：
  1. 删除 `word_parsing_guide.md` 中"数据类型含义"章节（第193-217行）
  2. 替换为引用："完整的DataType映射和表示格式解析规则见 `references/type_mapping.md`"
  3. 保留word_parsing_guide.md中**解析相关**的内容（如何提取字段值、处理S2类型特殊格式等）
- **规则**：当从一个大文件中拆分出独立参考文件时，原文件中的对应内容必须删除或替换为引用，不能两边都保留完整版本

### 错误41：审计参考文件一致性时，必须用grep交叉验证
- **现象**：编码从GBK统一为UTF-8后，`generate_oracle_ddl.py`和`generate_sqlserver_ddl.py`的argparse默认值和帮助文本仍残留"gbk"
- **根因**：修改`read_csv`函数默认值时，没有grep文件头部的docstring和argparse help字符串
- **修复**：全Skill统一编码后，用 `grep -rn "gbk\|GBK" --include="*.md" --include="*.py"` 扫全部文件确认无残留
- **规则**：修改任何配置项（编码/参数/格式）时，必须：(1) grep全Skill检查所有相关文件 (2) 包括脚本头部的docstring、argparse help文本 (3) 不能只改函数默认值就认为完成

### 错误42：文件删除后引用未清理导致broken reference
- **现象**：删除 `csv-format.md`、`example_tables_list.md`、`example_table_structure.md` 后，SKILL.md中仍有10+处引用这些已删除文件
- **根因**：删除文件时没有先grep所有引用位置
- **修复**：删除文件前必须执行 `grep -rn "被删文件名" . --include="*.md" --include="*.py"` 并更新所有引用
- **规则**：删除或重命名参考文件的操作顺序：(1) grep所有引用 (2) 更新SKILL.md和其他文件中的引用 (3) 确认无残留引用后再删除原文件

### 错误43：文件合并时丢失代码逻辑导致脚本损坏
- **现象**：patch脚本的 `read_csv` 函数时，新代码和旧代码重叠产生不可达代码（`return`后面还有`for`循环）
- **根因**：用 `return list(reader)` 替换原有的 for 循环逻辑，但没有删除循环中的 `rows.append(clean_row)` 行
- **修复**：手动检查并删除死代码
- **规则**：修改脚本函数时，patch后必须执行 `python -m py_compile scripts/xxx.py` 验证语法正确。特别是替换函数体时，确保旧逻辑的残留行被完全清除

### 错误44：patch工具碰撞导致SKILL.md"关键规则"章节结构损坏
- **现象**：经过多轮patch后，SKILL.md的"关键规则"章节编号从 ### 2 直接跳到 ### 6，缺失 ### 3/4/5。"参考文档"列表也被截断，丢失了compare_rules.md等5个文件的引用。
- **根因**：多个patch操作修改了相邻区域，新内容与旧内容的边界不清晰，导致patch工具匹配到错误位置或重复删除
- **修复**：重新读取完整文件，人工对照检查章节编号连续性，补回丢失的3-8条规则和完整的参考文档列表
- **规则**：对SKILL.md进行大范围patch（涉及"关键规则"等核心章节）时，patch后必须验证：
  1. 章节编号连续性（0-8全部存在）
  2. 参考文档列表完整性（grep "强制加载" 确认所有references/*.md都被引用）
  3. 无重复内容（同一规则不出现两次）
  4. `wc -l SKILL.md` 确认行数在合理范围（应<750行）

### 错误45：compare_with_docx.py的read_csv有GBK回退链，违反UTF-8统一标准
- **现象**：`compare_with_docx.py` 的 `read_csv()` 函数默认 `encoding='utf-8-sig'`，且有 `gb18030/gbk` 回退链，与其他脚本（统一 `encoding='utf-8'`）不一致
- **根因**：该脚本是最早编写的，当时还在用GBK编码，后来统一UTF-8时漏改了这个函数
- **修复**：将 `read_csv()` 改为 `encoding='utf-8'`，删除GBK回退链。argparse `--encoding` 默认值也改为 `utf-8`
- **规则**：grep所有脚本的 `read_csv` 函数签名和argparse默认值，确认编码参数完全一致。不能只看函数体内部，还要看argparse的 `default=` 值
