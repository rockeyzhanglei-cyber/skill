# 字体格式与继承表字段陷阱

## 字体格式规范（Word文档新增内容）

修改Word文档新增内容时，字体必须与已有行一致。

### 字体属性标准

| 属性 | 值 | 说明 |
|------|------|------|
| `w:ascii` | `Times New Roman` | 英文字体 |
| `w:eastAsia` | `Times New Roman` | **中文字体（必须设置，否则回退宋体）** |
| `w:hAnsi` | `Times New Roman` | ANSI字体 |
| `w:sz` | `20` | 字号（20=10pt，非小四12pt） |
| `w:szCs` | `20` | 复杂文种字号 |

### 方法A：deepcopy复制行（推荐）

```python
from copy import deepcopy
WD = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
new_tr = deepcopy(existing_row._tr)
for t in new_tr.findall(f'.//{WD}t'):
    t.text = ''
t = new_tr.find(f'.//{WD}r/{WD}t')
t.text = '新内容'
t.set(f'{WD}space', 'preserve')
```

### 方法B：从已有rPr模板创建

```python
template_rPr = deepcopy(existing_run.find(f'{WD}rPr'))
new_run = etree.SubElement(new_p, f'{WD}r')
new_run.insert(0, deepcopy(template_rPr))
```

### 事后修复缺失rPr的行

```python
for t in doc.tables:
    for r in t.rows[1:]:
        for cell in r.cells:
            for p in cell._tc.findall(f'.//{WD}p'):
                for run in p.findall(f'{WD}r'):
                    if run.find(f'{WD}rPr') is None:
                        run.insert(0, deepcopy(template_rPr))
                    else:
                        rPr = run.find(f'{WD}rPr')
                        rf = rPr.find(f'{WD}rFonts')
                        if rf is None:
                            rf = etree.SubElement(rPr, f'{WD}rFonts')
                        rf.set(f'{WD}eastAsia', 'Times New Roman')
                        sz = rPr.find(f'{WD}sz')
                        if sz is None:
                            sz = etree.SubElement(rPr, f'{WD}sz')
                        sz.set(f'{WD}val', '20')
```

### 常见字体格式错误

| 现象 | 原因 | 修复 |
|------|------|------|
| 中文显示为宋体 | `eastAsia` 未设置 | 设置 `eastAsia=Times New Roman` |
| 字号为12pt（小四） | `sz=24` | 改为 `sz=20`（10pt） |
| 新行字体与已有行不一致 | 用etree新建run，无rPr | 用deepcopy复制行，替换文本节点 |
| 新内容不是红色 | 未设置`w:color` | 设置 `color val=FF0000` |
| 行距1.5倍 | 未设置`w:spacing` | 设置 `spacing line=240 lineRule=auto` |
| 说明列"复合主键"未加粗 | 缺少`<w:b>` | 添加 `<w:b w:val="1"/>` 到rPr |
| `A..100` 在文档中 | MinerU输出错误 | 改为 `AN..100` |

### 新增内容格式检查清单（逐项确认）

| 检查项 | 设置值 | 说明 |
|--------|--------|------|
| 字体 | `rFonts ascii=Times New Roman eastAsia=Times New Roman hAnsi=Times New Roman` | 中文英文字体统一 |
| 字号 | `sz=20 szCs=20` | 10pt，不是小四(12pt) |
| 颜色 | `color val=FF0000` | 所有新增内容红色 |
| 行距 | `spacing line=240 lineRule=auto` | 单倍行距，不是1.5倍 |
| 复合主键加粗 | `b val=1` | 说明列中"复合主键"四字加粗 |

**用户强偏好**：表格新增内容用 `deepcopy(已有行._tr)` 方式，只替换`<w:t>`文本节点，**不重新创建段落/run元素**，以确保所有格式（字体、字号、颜色、行距、对齐等）完全继承。新增内容完成后，必须再遍历一次所有run，检查rPr是否完整，缺失则补充格式模板。

## 继承表字段处理

从PDF提取时，继承表只包含特有字段，不含基表继承字段。Word可能错误复制了基表所有字段。

### 各表正确字段数

| 表名 | 正确字段数 | 说明 |
|------|-----------|------|
| T_HD_STAFF | 20 | 含PERMANENT_TYPE+IN_DATE+OUT_DATE |
| T_HD_STAFF_LOGIN | 11 | 仅STAFF_NO+LOGIN_TIME等 |
| T_HD_PATIENT_QUIT | 15 | 仅退出相关字段 |
| T_HD_PATIENT_LINE | 13 | 仅标签属性字段 |
| T_PD_STAFF | 19 | 含PERMANENT_TYPE+IN_DATE+OUT_DATE |
| T_PD_STAFF_LOGIN | 11 | 同HD |
| T_PD_PATIENT_LINE | 13 | 同HD |

### 核对原则

用户强调：关键字段数据不要用自动化程序核对，必须逐行逐字段人工比对PDF原文。

## 常见pdftotext截断字段名

```
EQUIPMENT_BR → EQUIPMENT_BRAND
EQUIPMENT_MO → EQUIPMENT_MODEL
ADMISSION_TI → ADMISSION_TIME
NEOPATHY_TIM → NEOPATHY_TIME
DIAGNOSIS_TI → DIAGNOSIS_TIME
CI_TYP → CI_TYPE
RRT_TY → RRT_TYPE
DIC_KE → DIC_KEY
DIC_UN → DIC_UNIT
EQUIP → EQUIP_ID
END_DA → END_DATE
SNSTAT_DDATEATE → SN
YEAR_C → YEAR_CNT
DAY_CN → DAY_CNT
MAX_DA → MAX_DATE
ZZJHLS → ZZJHLSH
ICUJRR → ICUJRRQ
```

## revise_record_generator.py已知bug

`~/.agents/skills/data-model-revision/scripts/revise_record_generator.py` 中以下函数参数顺序错误：`timestamp`（无默认值）放在有默认值参数后面。

修正方式：把 `timestamp` 移到有默认值的参数之前。

- `generate_code_system_insert(revise_id, code_system_id, code_system_name, timestamp, definition='')`
- `generate_value_set_insert(revise_id, code_system_id, code_system_name, value_no, value_desc, timestamp, description='')`
- `generate_metadata_insert(revise_id, standard_id, metadata_code, metadata_name, definition, data_type, representation_format, timestamp, code_system_id='', allow='', external_id='')`
- `generate_dataset_element_insert(revise_id, dataset_id, element_code, element_name, definition, is_pk, notnull, data_type, representation_format, timestamp, code_system_id='', allow='', seq_no='', metadata_id='', internal_id='')`