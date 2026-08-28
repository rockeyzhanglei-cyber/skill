# BMS修订记录INSERT脚本生成规范

> **强制要求**：生成脚本前必须读取本文档，严格按照模板生成。
> **参考来源**：`V20260626133554__insert_revise_record_228606.sql`（已验证可升级成功）
> **Flyway 增量铁律**：所有脚本必须为**新增**的 `V{时间戳}__*.sql` 版本化文件，**禁止修改已存在的历史脚本**（含 DDL、修订记录、基础数据同步脚本）。`base_data/*__*.csv` 是**初始化种子、只读不可变**，初始化后基础数据变更一律走修订记录，绝不改动 CSV。**需求号必填**（见下方"需求号规则"）。详见 `bms-script-spec.md`。

---

## 0. 需求号规则（硬性，必填）

- `edsm_revise_record.require_no`（以及文件名中的 `{需求号}`）**必须**填写真实**需求号**（如 `234683`），不得留空、不得用描述性文字（如"数据标准修订-增加记录状态字段"）代替。脚本头部**不写** `-- 需求:` 注释行。
- 用户在对话中给出需求号直接用；**若生成修订记录时发现没有需求号，必须主动询问用户**，不要编造、不要跳过。缺需求号会导致修订记录无法与需求关联、无法追溯。
- 已记录需求号（非穷举）：`234683`（STATUS 记录状态字段修订，CVA-0166）。

---

## 1. 脚本命名

```
V{YYYYMMDDHHMMSS}__insert_revise_record_{需求号}.sql
```

放置目录：`winning-dps-rda-bms-server/src/main/resources/system_sql/rhdp_app/postgresql/`

---

## 1.1 头部注释格式（与 DDL 配套统一，唯一格式）

修订记录脚本头部的"变更描述"与配套 DDL 脚本（`edsm_sql/{库}`）**逐字一致**。四类操作（加字段 / 加表 / 修改 / 删除）及值域修订的模板、字段项写法、批量排版，**全部唯一来源为 `bms-script-spec.md`《注释规范（DDL 与修订记录统一约束）》**。本规范不另立格式。

**无论单条还是多条变更，统一用 `/* */` 编号清单**（与 DDL 顶部清单逐条逐字一致，含编号顺序、字段项形态）：

```sql
/*
1. 科室信息[BASE_DEPARTMENT]新增字段：记录状态[STATUS,O,S3,N1]
2. 医护人员信息表[BASE_EMPLOYEE]新增字段：记录状态[STATUS,O,S3,N1]
*/
```

- 单条变更也写成 `/* 1. … */` 形式（不另用三行 `--` 式），与多条保持同一套写法，避免双格式。
- **不写 `-- 集合:` / `-- 需求:` / `-- 字段:` / `-- 说明:` 等辅助注释行**：需求号仅体现于文件名与 `require_no` 列；字段类型/约束/值域等细节均放在 `revise_after` 的 JSON 内，不在头部以注释重复。
- `edsm_revise_record.summary` **必须等于头部清单**：多条用 `\n` 连接（`1. xxx\n2. xxx`），单条即 `1. xxx`。禁止 summary 与头部清单措辞不同或顺序不同。
- 字段类型 / 约束等细节放 `revise_after` 的 JSON 内，不在头部重复。
- **一致性铁律**：DDL 与修订记录是同一标准修订的配套产物，两者变更清单条数、顺序、描述文字必须逐字一致，禁止"新增字段 / 增加字段"之类措辞漂移。唯一例外：标准动作与物理落地方式本就不同时（如标准侧 `isDel=1` vs DDL 侧改为非必填），主句仍须一致，仅括号内注明落地方式。

## 2. SQL模板总览

### edsm_revise_record（10列）

```sql
insert into edsm_revise_record(revise_id,standard_id,version,require_no,summary,is_standard,published_at,is_upgraded,is_del,created_at)
values('{revise_id}','winning-plat-02','{version}','{require_no}','{summary}',1,'{timestamp}',0,0,'{timestamp}');
```

### edsm_revise_detail（9列）

```sql
insert into edsm_revise_detail(revise_detail_id,revise_id,business_code,business_id,revise_type_code,revise_before,revise_after,is_del,created_at)
values('{detail_id}','{revise_id}','{business_code}','{business_id}','{type}','{before}','{after}',0,'{timestamp}');
```

**关键规则**：
- `revise_id`：一个脚本共用一个UUID
- `revise_detail_id`：每条记录使用不同的UUID
- `business_id`：与 `revise_after` JSON中的主键字段值一致
- `revise_before`：`add` 操作填 `null`，`edit` 操作填修改前的JSON
- `revise_after`：`delete` 操作填 `null`，`add`/`edit` 操作填JSON

---

## 3. 时间戳规则

- SQL值：ISO 8601格式，带T分隔符，如 `'2026-07-23T14:25:00'`
- JSON内字段值：同格式，如 `"2026-07-23T14:25:00"`
- **禁止**使用空格分隔（`2026-07-23 14:25:00` 会导致反序列化失败）

---

## 4. JSON模板

### 4.1 codeSystem（11个字段）

```json
{
  "codeSystemId": "CVA-0308",
  "namespaceId": "1",
  "codeSystemNo": "CVA-0308",
  "codeSystemName": "健康教育活动形式代码",
  "definition": "",
  "category": "CUSTOM",
  "status": 1,
  "isInternal": 1,
  "isDel": 0,
  "createdAt": "2026-07-23T14:25:00",
  "modifiedAt": ""
}
```

**对应SQL**：
```sql
insert into edsm_revise_detail(revise_detail_id,revise_id,business_code,business_id,revise_type_code,revise_before,revise_after,is_del,created_at)
values('{uuid}','{revise_id}','codeSystem','CVA-0308','add',null,'{"codeSystemId": "CVA-0308", "namespaceId": "1", "codeSystemNo": "CVA-0308", "codeSystemName": "健康教育活动形式代码", "definition": "", "category": "CUSTOM", "status": 1, "isInternal": 1, "isDel": 0, "createdAt": "2026-07-23T14:25:00", "modifiedAt": ""}',0,'2026-07-23T14:25:00');
```

**字段说明**：

| 字段名 | 类型 | 固定值/说明 |
|--------|------|------------|
| codeSystemId | String | CVA编号，如 `"CVA-0308"` |
| namespaceId | String | 固定 `"1"` |
| codeSystemNo | String | 与codeSystemId相同 |
| codeSystemName | String | 值域名称 |
| definition | String | 值域定义，可为 `""` |
| category | String | 固定 `"CUSTOM"` |
| status | int | 固定 `1`（启用） |
| isInternal | int | 固定 `1` |
| isDel | int | 固定 `0` |
| createdAt | String | ISO时间戳 |
| modifiedAt | String | 固定 `""` |

---

### 4.2 valueSet（12个字段）

```json
{
  "valueId": "CVA-0308-01",
  "codeSystemId": "CVA-0308",
  "codeSystemNo": "CVA-0308",
  "codeSystemName": "健康教育活动形式代码",
  "valueNo": "01",
  "valueDesc": "提供健康教育资料",
  "description": "",
  "isInternal": 1,
  "status": 1,
  "isDel": 0,
  "createdAt": "2026-07-23T14:25:00",
  "modifiedAt": ""
}
```

**对应SQL**：
```sql
insert into edsm_revise_detail(revise_detail_id,revise_id,business_code,business_id,revise_type_code,revise_before,revise_after,is_del,created_at)
values('{uuid}','{revise_id}','valueSet','CVA-0308-01','add',null,'{"valueId": "CVA-0308-01", "codeSystemId": "CVA-0308", "codeSystemNo": "CVA-0308", "codeSystemName": "健康教育活动形式代码", "valueNo": "01", "valueDesc": "提供健康教育资料", "description": "", "isInternal": 1, "status": 1, "isDel": 0, "createdAt": "2026-07-23T14:25:00", "modifiedAt": ""}',0,'2026-07-23T14:25:00');
```

**字段说明**：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| valueId | String | `{CVA编号}-{值编码}`，如 `"CVA-0308-01"` |
| codeSystemId | String | 所属值域编号 |
| codeSystemNo | String | 与codeSystemId相同 |
| codeSystemName | String | 所属值域名称 |
| valueNo | String | 值编码，如 `"01"` |
| valueDesc | String | 值含义 |
| description | String | 值说明，可为 `""` |
| isInternal | int | 固定 `1` |
| status | int | 固定 `1` |
| isDel | int | 固定 `0` |
| createdAt | String | ISO时间戳 |
| modifiedAt | String | 固定 `""` |

**business_id** 与 `valueId` 保持一致。

---

### 4.3 metadata（13个字段）

> **external_id 生成规则见 external-id-spec.md**：必须由 generator 按规则自动填充，禁止留空 `""` 或手写随意值。

```json
{
  "metadataId": "winning-plat-02-DATASET_CODE-FIELD_CODE",
  "namespaceId": "1",
  "externalId": "",
  "metadataCode": "winning-plat-02-DATASET_CODE-FIELD_CODE",
  "metadataName": "字段中文名",
  "definition": "字段定义",
  "dataType": "S3",
  "representationFormat": "AN..100",
  "codeSystemId": "CVA-0308",
  "allow": "",
  "status": 1,
  "isDel": 0,
  "createdAt": "2026-07-23T14:25:00",
  "modifiedAt": ""
}
```

**对应SQL**：
```sql
insert into edsm_revise_detail(revise_detail_id,revise_id,business_code,business_id,revise_type_code,revise_before,revise_after,is_del,created_at)
values('{uuid}','{revise_id}','metadata','winning-plat-02-DATASET_CODE-FIELD_CODE','add',null,'{"metadataId": "winning-plat-02-DATASET_CODE-FIELD_CODE", "namespaceId": "1", "externalId": "", "metadataCode": "winning-plat-02-DATASET_CODE-FIELD_CODE", "metadataName": "字段中文名", "definition": "字段定义", "dataType": "S3", "representationFormat": "AN..100", "codeSystemId": "CVA-0308", "allow": "", "status": 1, "isDel": 0, "createdAt": "2026-07-23T14:25:00", "modifiedAt": ""}',0,'2026-07-23T14:25:00');
```

**字段说明**：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| metadataId | String | `winning-plat-02-{数据集代码}-{字段代码}`（= 元素唯一标识 element_id） |
| namespaceId | String | 固定 `"1"` |
| externalId | String | 数据元标识符，**按 external-id-spec.md 规则自动生成**（HDS{标准2}{分类2}.{数据集3}.{元素3}），由 generator 填充，**禁止留空/手写** |
| metadataCode | String | 数据集元素唯一标识（= `winning-plat-02-{数据集代码}-{字段代码}`，与 element_id 一致） |
| metadataName | String | 字段中文名 |
| definition | String | 字段定义说明 |
| dataType | String | S1/S2/S3/N/L/D/T/DT/BY |
| representationFormat | String | 表示格式，如 `AN..100`、`N..4` |
| codeSystemId | String | 关联值域编号，无关联则 `""` |
| allow | String | 允许值（S2枚举型时用），无则 `""` |
| status | int | 固定 `1` |
| isDel | int | 固定 `0` |
| createdAt | String | ISO时间戳 |
| modifiedAt | String | 固定 `""` |

**business_id** 与 `metadataId` 保持一致。

---

### 4.4 datasetElement（17个字段）

```json
{
  "elementId": "winning-plat-02-DATASET_CODE-element_code",
  "datasetId": "winning-plat-02-DATASET_CODE",
  "metadataId": "winning-plat-02-DATASET_CODE-element_code",
  "internalId": "",
  "elementCode": "element_code",
  "elementName": "元素中文名",
  "definition": "元素定义",
  "isPk": 0,
  "notnull": 0,
  "dataType": "S3",
  "representationFormat": "AN..100",
  "codeSystemId": "CVA-0308",
  "allow": "",
  "status": 1,
  "seqNo": 20,
  "isDel": 0,
  "createdAt": "2026-07-23T14:25:00",
  "modifiedAt": ""
}
```

**对应SQL**：
```sql
insert into edsm_revise_detail(revise_detail_id,revise_id,business_code,business_id,revise_type_code,revise_before,revise_after,is_del,created_at)
values('{uuid}','{revise_id}','datasetElement','winning-plat-02-DATASET_CODE-element_code','add',null,'{"elementId": "winning-plat-02-DATASET_CODE-element_code", "datasetId": "winning-plat-02-DATASET_CODE", "metadataId": "winning-plat-02-DATASET_CODE-element_code", "internalId": "", "elementCode": "element_code", "elementName": "元素中文名", "definition": "元素定义", "isPk": 0, "notnull": 0, "dataType": "S3", "representationFormat": "AN..100", "codeSystemId": "CVA-0308", "allow": "", "status": 1, "seqNo": 20, "isDel": 0, "createdAt": "2026-07-23T14:25:00", "modifiedAt": ""}',0,'2026-07-23T14:25:00');
```

**字段说明**：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| elementId | String | `winning-plat-02-{数据集代码}-{元素代码}` |
| datasetId | String | `winning-plat-02-{数据集代码}` |
| metadataId | String | `winning-plat-02-{数据集代码}-{字段代码}`（= element_id，专属元数据，不与其它元素共用） |
| internalId | String | 内部标识符，无则 `""` |
| elementCode | String | 元素代码（与标准文档字段英文名大小写保持一致：文档大写则大写，文档小写则小写，不做任何转换） |
| elementName | String | 元素中文名 |
| definition | String | 元素定义说明 |
| isPk | int | 0=否，1=是 |
| notnull | int | 0=否，1=是 |
| dataType | String | 与metadata一致 |
| representationFormat | String | 与metadata一致 |
| codeSystemId | String | 与metadata一致 |
| allow | String | 与metadata一致 |
| status | int | 固定 `1` |
| seqNo | int | 字段序号，从已有最大seqNo+1开始 |
| isDel | int | 固定 `0` |
| createdAt | String | ISO时间戳 |
| modifiedAt | String | 固定 `""` |

**business_id** 与 `elementId` 保持一致。

---

### 4.4.1 元数据一对一规则（重要）

**每个 datasetElement 必须对应唯一一个 metadata，二者一一对应，禁止共用。**

- `metadata_id` 与 `metadata_code` 均等于该元素的唯一标识 `element_id`（`winning-plat-02-{数据集代码}-{字段代码}`）。
- `datasetElement.metadata_id` 必须等于自己的 `element_id`，指向**专属**元数据，不能按字段名（element_code）去复用其它元素的元数据。
- 同一字段名出现在不同数据集时，各自生成独立的 metadata（如 `...-BASE_DEPARTMENT-STATUS` 与 `...-BASE_EMPLOYEE-STATUS` 是两条不同的元数据）。
- **历史已存在的元数据不做改动**，本规则仅对本次及以后的新增 / 修订生效。

---

### 4.5 metadata edit操作（revise_before + revise_after）

```sql
insert into edsm_revise_detail(revise_detail_id,revise_id,business_code,business_id,revise_type_code,revise_before,revise_after,is_del,created_at)
values('{uuid}','{revise_id}','metadata','winning-plat-02-FIELD_CODE','edit','{before_json}','{after_json}',0,'{timestamp}');
```

- `revise_before`：修改前的完整metadata JSON（13个字段）
- `revise_after`：修改后的完整metadata JSON（13个字段）
- 两者都**必须**包含全部字段，不能省略

---

## 5. 各类型字段对照总表

| 类型 | JSON字段数 | 关键唯一字段 | business_id对应 |
|------|-----------|-------------|----------------|
| codeSystem | 11 | codeSystemId | codeSystemId |
| valueSet | 12 | valueId | valueId |
| metadata | 13 | metadataId | metadataId |
| datasetElement | 17 | elementId | elementId |

---

## 6. 常见错误与解决方案

| # | 错误信息 | 根因 | 解决 |
|---|---------|------|------|
| 1 | `null value in column "namespace_id"` | JSON缺少 `namespaceId` 字段 | 添加 `"namespaceId": "1"` |
| 2 | `null value in column "category"` | codeSystem JSON缺少 `category` | 添加 `"category": "CUSTOM"` |
| 3 | `null value in column "code_system_no"` | valueSet JSON缺少 `codeSystemNo` | 添加 `"codeSystemNo": "CVA-XXXX"` |
| 4 | `null value in column "status"` | JSON缺少 `status` 字段 | 添加 `"status": 1` |
| 5 | `duplicate key value violates unique constraint` | ID与已有记录重复 | 使用新的UUID |
| 6 | `Cannot deserialize` / `Unrecognized field` | JSON字段名非驼峰 | 用驼峰命名（`codeSystemId` 不是 `code_system_id`） |
| 7 | `Cannot parse date` | 时间格式用了空格 | 用ISO格式 `2026-07-23T14:25:00`（带T） |

---

## 7. datasetElement的seqNo确定规则

**关键要求**：新增字段的seqNo必须从该表现有最大seqNo+1开始。

**查找方法**：
1. 从BMS后端初始化脚本中查找表定义：`winning-dps-rda-bms-server/src/main/resources/edsm_sql/greenplum/V20260106180223__create_init_tables.sql`
2. 统计`create table if not exists {表名}`后的字段数量
3. 新增字段的seqNo从 字段数+1 开始递增

**示例**：
- EDU_GROUP_ACTIVITY_RECORD表有39个字段（SYS_SOID到SYS_MODIFIED_AT）
- 新增字段seqNo从40开始

---

## 8. 执行顺序

一个完整脚本中，INSERT语句的**执行顺序**很重要：

1. `edsm_revise_record`（1条）
2. `edsm_revise_detail - codeSystem add`（如有新值域）
3. `edsm_revise_detail - valueSet add`（如有新值域项）
4. `edsm_revise_detail - metadata edit`（如有字段修改）
5. `edsm_revise_detail - metadata add`（如有新字段）
6. `edsm_revise_detail - datasetElement edit`（如有元素修改）
7. `edsm_revise_detail - datasetElement add`（如有新元素）

---

## 8. 历史成功脚本参考

```
winning-dps-rda-bms-server/src/main/resources/system_sql/rhdp_app/postgresql/
├── V20260626133554__insert_revise_record_228606.sql  ← 最佳参考（codeSystem+valueSet+metadata+datasetElement完整链路）
├── V20260707181716__insert_revise_record_cva0294.sql ← 已有值域新增明细项
├── V20260630104108__insert_revise_record_228853.sql  ← 修改值域引用
└── V20260716164142__insert_revise_record_216593.sql  ← 综合示例
```

**遇到格式不确定时，必须对照上述脚本确认**。
