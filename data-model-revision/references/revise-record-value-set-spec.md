# 值域修订脚本规范

## 文件命名规范

```
V{YYYYMMDDHHMMSS}__insert_revise_record_{需求号}.sql
```

示例：`V20260707181716__insert_revise_record_234159.sql`

## 表结构

### edsm_revise_record（修订记录主表）

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| revise_id | UUID | 修订记录唯一标识 | `a8e3c7d5-f1b2-4e6d-9a0c-8b7d6e5f4a3b` |
| standard_id | string | 标准集ID | `winning-plat-01` 或 `winning-plat-02` |
| version | string | 版本号 | `V6.0.{YYYYMMDDHHMMSS}` |
| require_no | string | 需求号 | `234159` |
| summary | string | 修订摘要 | 详细的修订内容描述 |
| is_standard | int | 是否标准修订 | `1` |
| published_at | datetime | 发布时间 | `2026-07-07T18:17:16` (ISO 8601) |
| is_upgraded | int | 是否升级 | `0` |
| is_del | int | 是否删除 | `0` |
| created_at | datetime | 创建时间 | `2026-07-07T18:17:16` (ISO 8601) |

### edsm_revise_detail（修订记录明细表）

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| revise_detail_id | UUID | 明细记录唯一标识 | `f1a2b3c4-d5e6-4789-abcd-ef0123456789` |
| revise_id | UUID | 关联主表ID | 同 edsm_revise_record.revise_id |
| business_code | string | 业务类型 | `codeSystem` / `valueSet` / `datasetCategory` / `dataset` / `metadata` / `datasetElement` |
| business_id | string | 业务ID | 根据 business_code 不同而变化 |
| revise_type_code | string | 修订类型 | `add` / `edit` / `delete` |
| revise_before | JSON/NULL | 修订前内容 | 新增时为 `null`，修改时为修订前JSON |
| revise_after | JSON/NULL | 修订后内容 | 删除时为 `null`，其他情况为修订后JSON |
| is_del | int | 是否删除 | `0` |
| created_at | datetime | 创建时间 | `2026-07-07T18:17:16` (ISO 8601) |

## business_code 类型说明

| business_code | 说明 | business_id 格式 | 使用场景 |
|---------------|------|------------------|----------|
| `codeSystem` | 值域代码系统 | `{CVA代码}` (如 `CVA-0294`) | 新增值域代码系统 |
| `valueSet` | 值域条目 | `{CVA代码}-{valueNo}` (如 `CVA-0294-01`) | 新增值域条目 |
| `datasetCategory` | 分类 | `{standard_id}-{分类名}` | 新增数据集分类 |
| `dataset` | 数据集 | `{standard_id}-{表名}` | 新增数据集（表） |
| `metadata` | 元数据 | `{standard_id}-{表名}-{字段名}`（= element_id，与数据集元素唯一标识一致，一对一） | 新增/修改元数据 |
| `datasetElement` | 数据集元素 | `{standard_id}-{表名}-{字段名}` | 新增/修改数据集字段 |

> **元数据一对一规则**：`metadata` 的 business_id 与 `datasetElement` 的 business_id 取值规则现已统一为 `{standard_id}-{表名}-{字段名}`（即 element_id）。每个数据集元素对应唯一一个元数据（`metadata_id` = `metadata_code` = `element_id`），**禁止按字段名共用元数据**；历史已存在的元数据保持不变。

## 值域修订脚本模板

### 场景1：已有值域新增条目（只需 valueSet）

```sql
/*
值域-{值域名称}[{CVA代码}]新增值：{值号}[{值描述}]、...
*/

/* ## 修订主记录 */
insert into edsm_revise_record(revise_id,standard_id,version,require_no,summary,is_standard,published_at,is_upgraded,is_del,created_at)values('{UUID}','{standard_id}','V6.0.{timestamp}','{require_no}','{summary}',1,'{timestamp}',0,0,'{timestamp}');

/* 值域-{值域名称}[{CVA代码}]新增值：{值号}[{值描述}] · 值域明细 */
insert into edsm_revise_detail(revise_detail_id,revise_id,business_code,business_id,revise_type_code,revise_before,revise_after,is_del,created_at)values('{UUID}','{revise_id}','valueSet','{CVA代码}-{valueNo}','add',null,'{"valueId":"{CVA代码}-{valueNo}","codeSystemId":"{CVA代码}","codeSystemNo":"{CVA代码}","codeSystemName":"{值域名称}","valueNo":"{valueNo}","valueDesc":"{valueDesc}","description":"","isInternal":1,"status":1,"isDel":0,"createdAt":"{timestamp}","modifiedAt":""}',0,'{timestamp}');
```

### 场景2：新增值域代码系统（需要 codeSystem + valueSet）

```sql
-- 新增值域：{值域名称}[{CVA代码}]，值：{值列表}
-- 需求: {需求号}

/* ## 修订主记录 */
insert into edsm_revise_record(revise_id,standard_id,version,require_no,summary,is_standard,published_at,is_upgraded,is_del,created_at)values('{UUID}','{standard_id}','V6.0.{timestamp}','{require_no}','{summary}',1,'{timestamp}',0,0,'{timestamp}');

-- edsm_revise_detail - codeSystem × 1
insert into edsm_revise_detail(revise_detail_id,revise_id,business_code,business_id,revise_type_code,revise_before,revise_after,is_del,created_at)
values('{UUID}','{revise_id}','codeSystem','{CVA代码}','add',null,'{"codeSystemId":"{CVA代码}","namespaceId":"1","codeSystemNo":"{CVA代码}","codeSystemName":"{值域名称}","definition":"{定义}","category":"CUSTOM","status":1,"isInternal":1,"isDel":0,"createdAt":"{timestamp}","modifiedAt":""}',0,'{timestamp}');

/* 值域-{值域名称}[{CVA代码}]新增值：{值号}[{值描述}] · 值域明细 */
insert into edsm_revise_detail(revise_detail_id,revise_id,business_code,business_id,revise_type_code,revise_before,revise_after,is_del,created_at)values('{UUID}','{revise_id}','valueSet','{CVA代码}-{valueNo}','add',null,'{"valueId":"{CVA代码}-{valueNo}","codeSystemId":"{CVA代码}","codeSystemNo":"{CVA代码}","codeSystemName":"{值域名称}","valueNo":"{valueNo}","valueDesc":"{valueDesc}","description":"","isInternal":1,"status":1,"isDel":0,"createdAt":"{timestamp}","modifiedAt":""}',0,'{timestamp}');
```

### 场景3：修改已有值域条目（需要 edit）

```sql
-- {CVA代码}[{值域名称}]修改{N}个明细项：{修改说明}
-- 需求: {需求号}

/* ## 修订主记录 */
insert into edsm_revise_record(revise_id,standard_id,version,require_no,summary,is_standard,published_at,is_upgraded,is_del,created_at)values('{UUID}','{standard_id}','V6.0.{timestamp}','{require_no}','{summary}',1,'{timestamp}',0,0,'{timestamp}');

-- edsm_revise_detail - valueSet × {N} (edit)
insert into edsm_revise_detail(revise_detail_id,revise_id,business_code,business_id,revise_type_code,revise_before,revise_after,is_del,created_at)
values('{UUID}','{revise_id}','valueSet','{CVA代码}-{valueNo}','edit','{修订前JSON}','{修订后JSON}',0,'{timestamp}');
```

## 值域编码格式规范

### valueNo 格式

| 值范围 | 格式 | 示例 |
|--------|------|------|
| 1-9 | 两位数字（带前导零） | `01`, `02`, ..., `09` |
| 10-98 | 两位数字（无前导零） | `10`, `11`, ..., `98` |
| 99 | 特殊值（其他） | `99` |

### 常见错误

❌ 错误：`1`, `2`, `3` (缺少前导零)
✅ 正确：`01`, `02`, `03`

❌ 错误：`100` (超过两位数)
✅ 正确：使用其他编码方案或扩展编码

## JSON 格式规范

### valueSet 条目 JSON

```json
{
  "valueId": "CVA-0294-01",
  "codeSystemId": "CVA-0294",
  "codeSystemNo": "CVA-0294",
  "codeSystemName": "值域名称",
  "valueNo": "01",
  "valueDesc": "值描述",
  "description": "",
  "isInternal": 1,
  "status": 1,
  "isDel": 0,
  "createdAt": "2026-07-07T18:17:16",
  "modifiedAt": ""
}
```

### codeSystem JSON

```json
{
  "codeSystemId": "CVA-0294",
  "namespaceId": "1",
  "codeSystemNo": "CVA-0294",
  "codeSystemName": "值域名称",
  "definition": "值域定义",
  "category": "CUSTOM",
  "status": 1,
  "isInternal": 1,
  "isDel": 0,
  "createdAt": "2026-07-07T18:17:16",
  "modifiedAt": ""
}
```

## 生成脚本检查清单

- [ ] 文件命名符合规范：`V{YYYYMMDDHHMMSS}__insert_revise_record_{需求号}.sql`
- [ ] edsm_revise_record 包含完整字段
- [ ] UUID 唯一且格式正确
- [ ] 时间戳使用 ISO 8601 格式：`YYYY-MM-DDTHH:mm:ss`
- [ ] valueNo 格式正确（个位数带前导零）
- [ ] JSON 格式正确，无语法错误
- [ ] 对于已有值域，只需 valueSet 记录
- [ ] 对于新增值域，需要 codeSystem + valueSet 记录
- [ ] 修订摘要清晰描述了变更内容

## 历史脚本参考

| 需求号 | 脚本文件 | 说明 |
|--------|----------|------|
| 228606 | V20260626133554__insert_revise_record_228606.sql | 值域修订 |
| cva0294 | V20260707181716__insert_revise_record_cva0294.sql | 已有值域新增条目 |
| 233977 | V20260723111128__insert_revise_record_233977.sql | 新增值域（codeSystem + valueSet） |
| 231626 | V20260707152022__insert_revise_record_231626.sql | 新增数据集和字段 |
| 228853 | V20260630104108__insert_revise_record_228853.sql | 值域修订 |
