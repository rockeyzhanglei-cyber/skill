# 数据模型修订常见错误清单

以下错误在实际操作中出现过，**必须避免再次发生**。

> **使用说明**：本文件是data-model-revision Skill的参考文档，修订过程中应对照检查。

---

## 1. CVA值域编码格式错误

**错误现象**：使用CVA-306（3位数字）
**正确做法**：CVA编码格式为`CVA-{4位序号}`，如CVA-0306

```
❌ 错误: CVA-306
✅ 正确: CVA-0306
```

---

## 2. CVA值域类别错误

**错误现象**：CVA类值域归类为"平台部分"
**正确做法**：CVA开头的值域都是"业务自定义部分"

```
❌ 错误: 平台部分
✅ 正确: 业务自定义部分
```

---

## 3. 值域字典读取不完整

**错误现象**：只读取前500行，遗漏后面的编码
**正确做法**：必须使用`sheet.max_row`读取所有行（可能超过16000行）

```python
❌ 错误: for row in sheet.iter_rows(max_row=500):
✅ 正确: for row in sheet.iter_rows(max_row=sheet.max_row):
```

---

## 4. revise_after字段名格式错误

**错误现象**：JSON使用下划线格式（code_system_id, is_internal等），标准升级时报错：
```
Unrecognized field "code_system_id" (class com.winning.dps.rda.common.entity.CodeSystem)
```

**正确做法**：JSON字段名必须使用驼峰格式（Java实体类属性名）

```json
❌ 错误:
{"code_system_id": "CVA-0306", "is_internal": 1, "created_at": "..."}

✅ 正确:
{"codeSystemId": "CVA-0306", "isInternal": 1, "createdAt": "..."}
```

参见`references/6.0-spec.md`中的"字段名对照表"，区分三种字段名：
- CSV列名：用于CSV文件
- 数据库表字段名：用于数据库INSERT/UPDATE
- JSON属性名（驼峰）：用于revise_after JSON

---

## 5. JSON日期格式错误

**错误现象**：JSON使用空格分隔的日期格式，标准升级时报错：
```
Cannot parse date "2026-06-26 13:35:54": while it seems to fit format 'yyyy-MM-dd'T'HH:mm:ss.SSSX'
```

**正确做法**：JSON日期必须使用ISO格式（带`T`分隔符）

```json
❌ 错误:
{"createdAt": "2026-06-26 13:35:54"}

✅ 正确:
{"createdAt": "2026-06-26T13:35:54"}
```

---

## 6. INSERT语句格式错误

**错误现象**：多行格式，字段列表和值分开写
**正确做法**：单行紧凑格式，一个语句一行

```sql
❌ 错误:
insert into edsm_revise_record(
    revise_id,standard_id,version,...
)values(
    'xxx','xxx','xxx',...
);

✅ 正确:
insert into edsm_revise_record(revise_id,standard_id,version,require_no,summary,is_standard,published_at,is_upgraded,is_del,created_at)values('xxx','xxx','xxx','xxx','xxx',1,'xxx',0,0,'xxx');
```

---

## 7. Word文档格式不一致

**错误现象**：新增行格式与相邻行不同（行高、对齐、字体等），或设置固定行高导致内容显示不全
**正确做法**：复制相邻行的格式属性，设置行高为0.6厘米实现自适应

```xml
必须设置:
- 水平居中: w:jc val="center"
- 单元格垂直居中: w:vAlign val="center"
- 红色字体: w:color val="FF0000"
- 行高自适应: w:trHeight val="340" w:hRule="atLeast" (0.6cm)
```

---

## 8. DDL缺少幂等判断

**错误现象**：直接ALTER TABLE，不做存在性判断
**正确做法**：使用reg-ddl-generator生成，保留幂等判断逻辑

```sql
❌ 错误:
alter table resident_archive add column elder_health_level_code varchar(1);

✅ 正确:
do $$
begin
    if exists (select 1 from information_schema.tables where table_name = 'resident_archive') then
        if not exists (select 1 from information_schema.columns where table_name = 'resident_archive' and column_name = 'elder_health_level_code') then
            alter table resident_archive add column elder_health_level_code varchar(1) null;
        end if;
    end if;
end $$;
```

---

## 9. 跳过用户审核直接执行

**错误现象**：需求分析后直接开始修订
**正确做法**：必须生成修订计划，用户确认后才执行

---

## 10. 修订记录Word文档格式问题

**错误现象**：新增行格式与参考行不一致（行高、行距、中文版式、序号设置等）
**正确做法**：复制上一行（使用`deepcopy(prev_row._element)`），自动继承所有格式，只需填充内容并修改numId重新编号

```
❌ 错误：手动设置各种格式属性，导致格式不一致
✅ 正确：复制上一行 → 填充内容 → 设置新numId重新编号
```

**具体格式要求**（由复制上一行自动继承）：
- 行高：340 twips (0.6cm)，hRule="atLeast"
- 行距：240 twips (单倍)，lineRule="auto"
- 中文版式：wordWrap、autoSpaceDE、autoSpaceDN
- 修订内容列：numPr（序号设置）、ind（悬挂缩进）
- 重新编号：设置新numId（上一行numId+1）