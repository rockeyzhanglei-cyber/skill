---
title: Word文档解析指南
skill: db-schema-verify
version: 3.0
---

# Word文档解析指南

## 解析原则

**本指南供AI自动解析参考，不是用户操作手册。**
AI应使用python-docx自动解析Word文档，生成MD文件。用户无需手动操作。

## 文档结构特征（已验证的格式）

### 安徽区域标准规范V5.5格式（2026-07-20验证）
- **表名标题**：Heading 3样式，内容为"中文名 + 空格 + 英文表名"
  - 示例：`医护人员信息表 JBYHRYXXB`
  - 示例：`床位信息 BASE_BED`
  - 示例：`收费项目目录 JB_XMML`
- **字段定义表**：紧跟在表名标题后面，表头包含固定6列：
  - `数据元标识 | 数据元名称 | 约束 | 数据类型 | 表示格式 | 说明`
- **总目录表**：文档第一个表格（跳过），表头为：
  - `类目 | 数据集名称 | 数据库表名 | 是否必须 | 时效性规则 | 时效性字段`
- **TRAN/LOG表**：与原表共享同一个字段定义表，结构应一致
- **分隔符变体**：中英文表名可能有空格、无空格、或用括号括起来

## 自动解析流程

### 解析模式选择

根据任务类型选择不同的解析深度：

| 任务 | 解析模式 | 输出文件 | 说明 |
|------|---------|----------|------|
| 子流程A：原表 vs TRAN/LOG自检 | **轻量模式** | `tables_list.md` | 仅提取表清单，不解析字段定义 |
| 子流程B：标准文档 vs 库表自检 | **完整模式** | `table_structure.md` | 提取表清单 + 所有字段定义 |

**判断依据**：
- 如果只需要知道"核对哪些表" → 轻量模式
- 如果需要知道"每张表的字段定义" → 完整模式

### 步骤1：安装依赖
```bash
pip3 install python-docx lxml
```

### 步骤2：遍历文档元素建立映射
```python
from docx import Document
from docx.oxml.ns import qn
import re

doc = Document(doc_path)

current_table_name = None
current_cn_name = None
table_data = {}
table_index = 0

for element in doc.element.body:
    tag = element.tag.split('}')[-1]  # 获取标签名，去掉命名空间
    
    if tag == 'p':  # 段落
        # 检查段落样式 - 直接读取XML属性，不要用python-docx的style.name
        pPr = element.find(qn('w:pPr'))
        if pPr is not None:
            pStyle = pPr.find(qn('w:pStyle'))
            if pStyle is not None:
                style_val = pStyle.get(qn('w:val'))
                if style_val == '3':  # Heading 3（XML值是"3"不是"Heading 3"）
                    # 提取文本 - 必须用iter递归查找所有w:t元素
                    text = ''
                    for t_elem in element.iter(qn('w:t')):
                        if t_elem.text:
                            text += t_elem.text  # 必须取.text属性
                    
                    # 匹配表名：中文名 + 空格 + 英文表名
                    match = re.match(r'^(.+?)\s+([A-Z][A-Z0-9_]{2,})$', text.strip())
                    if match:
                        current_cn_name = match.group(1).strip()
                        current_table_name = match.group(2).strip()
    
    elif tag == 'tbl':  # 表格
        table_index += 1
        if table_index == 1:  # 跳过第1个总目录表
            continue
        if not current_table_name:
            continue
        
        # 提取表格行
        rows = element.findall(qn('w:tr'))
        if len(rows) < 2:
            continue
        
        # 检查表头是否包含"数据元标识"
        first_row_text = ''
        for t_elem in rows[0].iter(qn('w:t')):
            if t_elem.text:
                first_row_text += t_elem.text
        
        if '数据元标识' not in first_row_text:
            continue
        
        # 每个表只取第一个匹配表格
        if current_table_name in table_data:
            continue
        
        # 提取字段行
        fields = []
        for i, row in enumerate(rows[1:], start=1):
            cells = row.findall(qn('w:tc'))
            cell_texts = []
            for cell in cells:
                text = ''
                for t_elem in cell.iter(qn('w:t')):
                    if t_elem.text:
                        text += t_elem.text  # 必须取.text属性
                cell_texts.append(text.strip())
            
            if len(cell_texts) >= 6 and cell_texts[0]:
                fields.append({
                    'seq': i,
                    'data_element_id': cell_texts[0],
                    'data_element_name': cell_texts[1],
                    'constraint': cell_texts[2],
                    'data_type': cell_texts[3],
                    'format': cell_texts[4],
                    'description': cell_texts[5]
                })
        
        if fields:
            table_data[current_table_name] = {
                'cn_name': current_cn_name,
                'fields': fields
            }
```

**关键注意事项**：
- **XML样式值**：`pStyle/@w:val` 的值是 `"3"`，不是 `"Heading 3"`
- **文本提取**：必须用 `element.iter(qn('w:t'))` 递归查找，提取时用 `t_elem.text`（不是直接拼接元素对象）
- **表清单章节**：生成的 `table_structure.md` 必须包含"## 表清单"章节，否则后续步骤无法提取完整表清单

### 步骤3：生成输出文件

#### 轻量模式（子流程A：只需要表清单）

**输出文件**：`<任务目录>/tables_list.md`
**输出格式**：只包含 `## 表清单` 章节

```markdown
# 数据表结构

## 表清单

| 序号 | 中文名 | 英文表名 | 是否有TRAN | 是否有LOG |
|------|--------|----------|------------|----------|
| 1 | 医护人员信息表 | JBYHRYXXB | 否 | 否 |
| 2 | 床位信息 | BASE_BED | 是 | 是 |
```

**实现要点**：
- 只需遍历文档元素找到 Heading 3 段落（表名）
- 不需要解析字段定义表
- TRAN/LOG标记：检查表名+`_TRAN`/`_LOG`后缀的Heading 3是否存在，存在则标记"是"

#### 完整模式（子流程B：需要表清单 + 字段定义）

**输出文件**：`<任务目录>/table_structure.md`
**输出格式**：`## 表清单` + 每张表的 `### 表N：中文名[英文表名]` 字段定义

```markdown
# 数据表结构

## 表清单

| 序号 | 中文名 | 英文表名 | 是否有TRAN | 是否有LOG |
|------|--------|----------|------------|----------|
| 1 | 医护人员信息表 | JBYHRYXXB | 否 | 否 |

### 表1：医护人员信息表[JBYHRYXXB]

| 序号 | 数据元标识 | 数据元名称 | 约束 | 数据类型 | 表示格式 | 说明 |
|------|-----------|-----------|------|---------|---------|------|
| 1 | XMBH | 项目编码 | M | S1 | AN..50 | 主键 |
```

**实现要点**：
- 遍历文档元素，找到 Heading 3（表名）和紧随的字段定义表
- 必须提取完整字段信息（数据元标识、名称、约束、类型、格式、说明）
- 必须包含 `## 表清单` 章节（否则后续脚本无法提取表名）

## 数据类型映射

详见 `references/type_mapping.md`，包含完整的DataType到数据库类型的映射规则。

**表示格式解析**（按优先级顺序匹配）：
1. `AN..n` → 最大长度n的字母数字混合 → VARCHAR(n)
2. `N..n` → 数字序列 → VARCHAR(n)
3. `N{p}` 或 `N{p,s}` → 当DataType=N时为NUMBER/DECIMAL(p,s)，当DataType=S时为VARCHAR(n)
4. `A{n}` → 固定长度n → VARCHAR(n)
5. `[NDT]+{n}` → 数字字符串（如N1、N2、D10、DT19）→ VARCHAR(n)
6. `AN..*` → 不限制长度（通配符）→ 跳过长度比较
7. **注意**：长度/精度字段可能为`*`或空字符串，代码中int()转换必须try/except保护

**S2类型特殊处理**：
- 表示格式可能是`N1`、`N2`（表示1位/2位数字）
- 需匹配正则 `r'[NDT]+(\d+)'` 提取数字部分作为长度
- 示例：`N1` → 长度1，`N2` → 长度2，`D10` → 长度10

## 常见问题

### Q1：python-docx导入报lxml错误
**A**：`pip3 install --force-reinstall lxml python-docx`

### Q2：同一表名出现多次（西医/中医同名表）
**A**：每个表只取第一个匹配表格。如果需要区分同名表，按文档中的章节层级处理。

### Q3：文档中的可空性标记不统一
**A**：统一转换：M=必填, O=可选, C=条件必填

### Q4：新格式文档无法识别
**A**：先分析文档结构特征（段落样式、表格表头），更新本指南中的"已验证格式"部分，再编写解析逻辑。

### Q5：body元素遍历时找不到Heading段落（致命）
**A**：如果用`doc.element.body`遍历XML元素检查样式，`pStyle/@w:val`的值是数字`"3"`而非`"Heading3"`。
- **推荐**：直接读取XML属性 `pStyle/@w:val == "3"`（更可靠）
- 不要用 `para.style.name`（在某些文档中可能不准确）

### Q6：文本提取不完整或报错TypeError（致命）
**A**：用`element.findall(qn('w:r'))`嵌套`findall(qn('w:t'))`在某些文档结构中会漏提取文本。
- **必须用** `element.iter(qn('w:t'))` 递归查找所有文本节点
- **注意**：`iter()`返回的是XML元素对象，取文本必须用 `t_elem.text`，不能直接 `text += t_elem`
- 正确写法：
  ```python
  text = ''
  for t_elem in element.iter(qn('w:t')):
      if t_elem.text:
          text += t_elem.text  # 必须取.text属性
  ```

### Q7：生成的table_structure.md后续步骤提取不到表名
**A**：检查MD文件是否包含"## 表清单"章节。如果直接从"## 表1：XXX"开始，后续正则匹配会失败。
- **必须格式**：
  ```markdown
  ## 表清单
  
  | 序号 | 中文名 | 英文表名 | 是否有TRAN | 是否有LOG |
  |------|--------|----------|------------|----------|
  | 1 | 医护人员信息表 | JBYHRYXXB | 否 | 否 |
  | 2 | 科室信息 | JBKSXXB | 否 | 否 |
  ```
- **提取正则**：`r'\|\s*\d+\s*\|\s*[^|]+\s*\|\s*([A-Z_][A-Z0-9_]+)\s*\|'`

## 解析质量检查清单

- [ ] 表数量与文档目录一致
- [ ] 所有表都有中文名称和英文名称
- [ ] 字段数量与原表结构一致
- [ ] 数据类型映射正确（S1/S2/S3→VARCHAR2, N→NUMBER）
- [ ] 表示格式中的长度/精度正确提取（包括S2类型的N1/N2格式）
- [ ] **生成的MD包含"## 表清单"章节**（必须项）
- [ ] 表清单中的表数量与后续字段定义章节数量一致
