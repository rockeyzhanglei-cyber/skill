# MinerU PDF 提取参考

## 概述
MinerU（`mineru-open-api`）是一款免费在线文档解析CLI工具，可将PDF表格精确解析为HTML `<table>` 格式。在pdftotext/PDFPlumber/PyMuPDF等本地工具均无法正确提取表格时，MinerU是可靠的外部替代方案。

## 安装
```bash
npm install -g mineru-open-api
```

## 使用方式
```bash
# 提取指定页（免费版单次≤200页）
mineru-open-api extract path/to.pdf --pages 266-332 -o output.md

# 分页提取后合并
cat part1.md part2.md > combined.md
```

## 输出格式
MinerU输出的表格是单行HTML，整个 `<table>` 在一行内。列顺序（9列）：
```
数据元标识符 | 现数据项 | 字段名 | 数据类型 | 长度 | 标准数据类型 | 标准表示格式 | 填报要求 | 说明
```

## 提取注意事项
1. **分页限制**：免费版单次≤200页，超限需分页提取
2. **表名转义**：MinerU输出中下划线被转义为 `\\_`，解析时需还原
3. **表格连续性**：同一张表跨页时会被分成多个 `<table>` 片段，需按表名聚合后取最大片段（或按字段名去重合并）
4. **网络依赖**：MinerU是云端API，需网络连接且可能超时（可缩小页码范围重试）

## 解析代码示例
```python
import re
from lxml import html

def parse_mineru_tables(filepath):
    with open(filepath, 'r') as f:
        content = f.read()
    
    tables = []
    for m in re.finditer(r'<table>.*?</table>', content, re.DOTALL):
        try:
            root = html.fromstring(m.group(0))
            rows = []
            for tr in root.findall('.//tr')[1:]:
                tds = tr.findall('td')
                if len(tds) >= 9:
                    rows.append({
                        'field_name': tds[2].text_content().strip() or '',
                        'data_name': tds[1].text_content().strip() or '',
                        'constraint': tds[7].text_content().strip() or '',
                        'std_type': tds[5].text_content().strip() or '',
                        'format': tds[6].text_content().strip() or '',
                        'desc': tds[8].text_content().strip() or '',
                    })
            if rows:
                tables.append(rows)
        except:
            pass
    return tables
```

## 常见PDF提取错误清单

### 一、字段名合并（最常见）

MinerU分页提取导致同一行被拆成两个HTML片段，pdftotext多空格列分割时相邻列合并。

| 合并字段 | 应拆分为 | 涉及表 |
|---------|---------|-------|
| `LOCAL_INSURANCEDIALYSDATEIS_START_TIM` | `LOCAL_INSURANCE` + `DIALYSIS_START_TIME` | T_HD_PATIENT_QUIT, T_HD_PATIENT_LINE |
| `BORN_DATEDIALYSDATEIS_START_TIM` | `BORN_DATE` + `DIALYSIS_START_TIME` | T_PD_PATIENT, T_PD_PATIENT_LINE |
| `PERMANENT_TYIN_DATDATEOUT_DADATE` | `PERMANENT_TYPE` + `IN_DATE` + `OUT_DATE` | T_HD_STAFF_LOGIN, T_PD_STAFF, T_PD_STAFF_LOGIN |
| `REMOVE_REASON_DESCSETUP_DATE` | `REMOVE_REASON_DESC` + `SETUP_DATE` | T_HD_ACCESS |
| `PATIENT_NKSEQUELDATEAE_DAT` | `PATIENT_NK` + `SEQUELAE_DATE` | T_PD_OUTCOME |
| `SNSTAT_DDATEATE` | `SN` + `STAT_DATE` | T_HD_VERIFY, T_PD_VERIFY |

### 二、字段名截断（pdftotext列宽限制）

| 截断字段名 | 正确字段名 | 涉及表 |
|-----------|-----------|-------|
| `EQUIPMENT_BR` | `EQUIPMENT_BRAND` | T_HD_WM |
| `EQUIPMENT_MO` | `EQUIPMENT_MODEL` | T_HD_WM |
| `EQUIPMENT_TY` | `EQUIPMENT_TYPE` | T_HD_WM |
| `EQUIP` | `EQUIP_ID` | T_HD_EQUIP_INSPECT, T_PD_EQUIP, T_PD_EQUIP_INSPECT |
| `DIAGNOSIS_TI` | `DIAGNOSIS_TIME` | T_HD_DIAGNOSIS |
| `DIAGNOSIS_TY` | `DIAGNOSIS_TYPE` | T_HD_DIAGNOSIS |
| `ACCESS_STATU` | `ACCESS_STATUS` | T_HD_ACCESS |
| `CATHETER_SIT` | `CATHETER_SITE` | T_HD_ACCESS |
| `REMOVE_REASO` | `REMOVE_REASON` | T_HD_ACCESS |
| `CI_TYP` | `CI_TYPE` | T_HD_CI |
| `BLOOD_CULTUR` | `BLOOD_CULTURE` | T_HD_CI |
| `ADMISSION_TI` | `ADMISSION_TIME` | T_HD_INHOSPITAL, T_PD_INHOSPITAL |
| `NEOPATHY_TIM` | `NEOPATHY_TIME` | T_HD_COMPLICATION |
| `NEOPATHY_TYP` | `NEOPATHY_TYPE` | T_HD_COMPLICATION |
| `NEOPATHY_DES` | `NEOPATHY_DESC` | T_HD_COMPLICATION |
| `FOR_EMERGENC` | `FOR_EMERGENCY` | T_HD_SICKBED |
| `EMG_START_TI` | `EMG_START_TIME` | T_HD_SICKBED |
| `END_TI` | `END_TIME` | T_HD_SICKBED, T_HD_DIALYSIS, T_HD_PARAM, T_PD_PARAM |
| `DIVISION_NAM` | `DIVISION_NAME` | T_HD_DIVISION |
| `DIVISION_TYP` | `DIVISION_TYPE` | T_HD_DIVISION |
| `RRT_TY` | `RRT_TYPE` | T_HD_DOCTORS_ADVICE |
| `RRT_TYPE_NAM` | `RRT_TYPE_NAME` | T_HD_DOCTORS_ADVICE |
| `BICARBONATE_RADICA` | `BICARBONATE_RADICAL` | T_HD_DOCTORS_ADVICE |
| `DIALYSIS_DAT` | `DIALYSIS_DATE` | T_HD_DIALYSIS |
| `DOWN_NURSE_I` | `DOWN_NURSE_ID` | T_HD_DIALYSIS |
| `CHECK_NURSE` | `CHECK_NURSE_ID` | T_HD_DIALYSIS |
| `MZ_FLA` | `MZ_FLAG` | T_HD_LIS_REPORT |
| `CARD_N` | `CARD_NO` | T_HD_LIS_REPORT, T_PD_PATIENT |
| `INSPECTED_TY` | `INSPECTED_TYPE` | T_HD_LIS_REPORT |
| `REPORT_CATEG` | `REPORT_CATEGORY` | T_HD_LIS_REPORT |
| `RECORD_CCOUN` | `RECORD_COUNT` | T_HD_LIS_REPORT |
| `DIAGNOSE_COD` | `DIAGNOSE_CODE` | T_HD_LIS_REPORT |
| `DIAGNOSE_NAM` | `DIAGNOSE_NAME` | T_HD_LIS_REPORT |
| `INSPECTED_RESULT_N` | `INSPECTED_RESULT_NO` | T_HD_LIS_INDICATORS |
| `INSPECTED_RE` | `INSPECTED_RESULT` | T_HD_LIS_INDICATORS |
| `UNIT_T` | `UNIT_TYPE` | T_HD_LIS_INDICATORS |
| `SORTIN` | `SORTING` | T_HD_LIS_INDICATORS, T_PD_LIS_INDICATORS |
| `DIC_KE` | `DIC_KEY` | T_HD_PARAM, T_PD_PARAM |
| `DIC_UN` | `DIC_UNIT` | T_HD_PARAM, T_PD_PARAM |
| `DIC_EX` | `DIC_EXT` | T_HD_PARAM, T_PD_PARAM |
| `HOSPITAL_NAM` | `HOSPITAL_NAME` | T_PD_HOSPITAL |
| `SEQUELAE_TYP` | `SEQUELAE_TYPE` | T_PD_OUTCOME |
| `SUB_TY` | `SEQUELAE_SUB_TYPE` | T_PD_OUTCOME |
| `END_DA` | `END_DATE` | T_PD_EQUIP, T_PD_EQUIP_INSPECT |
| `INSPECTED_ITEM_EN` | `INSPECTED_ITEM_EN_NAME` | T_PD_LIS_INDICATORS |
| `ZZJHLS` | `ZZJHLSH` | DP_ICU_HZJBXX |
| `ZZJHSD` | `ZZJHSDM` | DP_ICU_HZJBXX |
| `ZZJHSM` | `ZZJHSMC` | DP_ICU_HZJBXX |
| `ICUJRR` | `ICUJRRQ` | DP_ICU_HZJBXX |
| `ICUTCR` | `ICUTCRQ` | DP_ICU_HZJBXX |
| `POSITI` | `POSITION` | T_PD_STAFF |
| `STAFF` | `STAFF_ID` | T_PD_STAFF |
| `MEDICAL_NO` | `SN` | T_HD_INHOSPITAL |
| `ADMISSION_CAUSE` | `ADMISSION_CAUSE_CODE` | T_HD_INHOSPITAL |
| `ID_TYP` | `ID_TYPE` | T_HD_PATIENT |
| `NURSE` | `NURSE_ID` | T_HD_MIDDLE |

### 三、表示格式截断

| 错误格式 | 正确格式 | 字段 | 涉及表 |
|---------|---------|------|-------|
| `A..100` | `AN..100` | PATIENT_NAME | 所有含PATIENT_NAME的表 |
| `AN..12` | `AN..128` | YLYL1, YLYL2 | 所有含预留字段的表 |
| `AN..12` | `AN..128` | LAB_SN | T_HD_LIS_REPORT等 |
| `AN..12` | `AN..128` | DIC_EX | T_HD_PARAM, T_PD_PARAM |
| `AN..10` | `AN..100` | STAFF_NAME, CHECK_RESULT等 | 各表 |
| `AN..20` | `AN..2000` | DIAGNOSIS_SUMMARY, ICUYY | T_HD_PATIENT, DP_ICU_HZJBXX |
| `AN..51` | `AN..512` | CHECK_ITEM_NAME等 | T_HD_LIS_REPORT等 |
| `AN..60` | `AN..600` | INSPECTED_RESULT_DESC等 | T_HD_LIS_INDICATORS等 |
| `AN..30` | `AN..300` | APPLICATION_TYPE, REF_RANGE | 各表 |
| `AN..15` | `AN..150` | SAMPLE_NAME | T_HD_LIS_INDICATORS等 |
| `AN..10` | `AN..1000` | YCTSSM | T_HD_LIS_INDICATORS |
| `AN..25` | `AN..255` | CHECK_NAME | T_HD_LIS_REPORT |
| `AN..25` | `AN..256` | CHECK_ITEM_CODE | T_HD_LIS_REPORT |

### 四、约束映射规则

**注意顺序**：先检查有则必填/条件必填，再检查必填，否则包含关系会误判。

```python
# 正确顺序
con = 'C' if '有则必填' in cr or '条件必填' in cr else ('M' if '必填' in cr else 'O')
# 错误顺序（会导致所有有则必填被误判为M）
con = 'M' if '必填' in cr else ('C' if '有则必填' in cr or '条件必填' in cr else 'O')
```

### 五、继承表字段数问题

| 表名 | Word错误字段数 | PDF正确字段数 |
|-----|---------------|-------------|
| T_HD_STAFF_LOGIN | 17 | 11 |
| T_PD_STAFF_LOGIN | 16 | 11 |
| T_HD_PATIENT_QUIT | 22 | 15 |
| T_HD_PATIENT_LINE | 22 | 13 |
| T_PD_PATIENT_LINE | 20 | 13 |

### 六、人工核对步骤（必须执行）

1. 从MinerU输出解析PDF数据：用 `^## ` 分割段落（注意 `\\_` 转义），提取 `<table>` 数据
2. 约束映射用正确顺序（先C再M）
3. 遍历Word表格，逐行对比6列
4. 修复原则：修改 `<w:t>` 文本节点保留rPr，不重新创建段落/run
5. 修复后再次遍历验证，确保无遗漏

### 七、新增行字体格式规范（用户反复纠正）

**行插入方法**：`deepcopy(已有行._tr)` → 替换 `<w:t>` 文本节点 → 保留所有 rPr 格式。**不要用 etree 创建新 tr/tc/p/run**，会导致字体格式丢失。

**字体属性**（必须与已有行一致）：

| 属性 | 值 | 说明 |
|------|------|------|
| `w:ascii` | `Times New Roman` | 英文字体 |
| `w:eastAsia` | `Times New Roman` | 中文字体（必须设置，否则回退宋体） |
| `w:hAnsi` | `Times New Roman` | ANSI字体 |
| `w:sz` | `20` | 字号（20=10pt，非小四12pt） |
| `w:szCs` | `20` | 复杂文种字号 |
| `w:color` | `FF0000` | 红色（新增内容标记） |
| 行距 | `spacing line=240 lineRule=auto` | 单倍行距，非1.5倍 |

**说明列"复合主键"加粗**：在 rPr 中添加 `<w:b w:val="1"/>`。

**修复步骤**：
1. 遍历所有新增表格的数据行，检查每个 `<w:r>` 是否有 `<w:rPr>`
2. 缺失则插入格式模板（从已有行复制）
3. 检查 `eastAsia` 是否设置，未设置则补充
4. 检查 `sz` 是否为20，`color` 是否为FF0000
5. 检查 `spacing line=240` 行距设置