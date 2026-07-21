# 修订记录表结构说明

本文档描述 `edsm_revise_record` 和 `edsm_revise_detail` 表的结构和使用方法。

## edsm_revise_record（数据标准修订记录）

### 表结构

| 字段名 | 类型 | 约束 | 说明 |
|-------|------|-----|------|
| revise_id | VARCHAR(64) | PK | 修订记录标识 |
| standard_id | VARCHAR(64) | NOT NULL | 标准ID |
| version | VARCHAR(64) | NOT NULL | 版本号 |
| require_no | VARCHAR(64) | NULL | 需求号 |
| summary | TEXT | NULL | 修订摘要 |
| is_standard | INT2 | NULL | 是否公版（1=公版, 0=项目化） |
| project_code | VARCHAR(64) | NULL | 项目编码（is_standard=0时必填，格式：PRJ-{序号}-{简称}） |
| published_at | TIMESTAMP | NULL | 发布日期时间 |
| is_upgraded | INT2 | NOT NULL | 是否已升级（0=未升级, 1=已升级, 2=已忽略） |
| upgraded_at | TIMESTAMP | NULL | 升级日期时间 |
| is_del | INT2 | NOT NULL | 逻辑删除（0=正常, 1=删除） |
| created_at | TIMESTAMP | NOT NULL | 创建日期时间 |
| modified_at | TIMESTAMP | NULL | 修改日期时间 |

### 字段说明

#### revise_id
- 修订记录的唯一标识
- 使用UUID生成：`uuid.randomUUID().toString()`
- 格式示例：`550e8400-e29b-41d4-a716-446655440000`

#### standard_id
- 关联的数据标准ID
- 格式：`winning-plat-01`、`winning-plat-02` 等
- 对应 `edsm_data_standard.standard_id`

#### version
- 修订版本号
- 示例：`6.0`、`v3.0`、`2026Q1`

#### require_no
- 关联的需求号（TFS工作项ID）
- 可为空（如公版基础修订）

#### summary
- 修订摘要，描述本次修订的主要内容
- 自动生成，格式参考DDL修订注释：
  - 新增表：`新增表：表名中文[表名]`
  - 新增字段：`表名中文[表名]新增字段：字段名中文[字段名,类型,约束]`
  - 修改字段：`表名中文[表名]修改字段：字段名中文[字段名] - 修改属性：属性名`

#### is_standard
- 是否公版标准：
  - `1`：公版（文档路径为 `01 标准规范/` 下的标准文档）
  - `0`：项目化（文档路径为 `02 标准规范（项目化）/` 下的项目标准）

#### project_code
- 项目编码，**仅当 `is_standard=0` 时填写**
- 格式：`PRJ-{3位序号}-{大写简称}`
- 序号对应项目文件夹的3位数字编号
- 简称为项目名称拼音首字母（2~6个大写字母）

**项目编码示例**：
| 项目文件夹 | project_code |
|-----------|-------------|
| 001 深圳市罗湖区妇幼保健院 | PRJ-001-SZLH |
| 002 北京电子病历共享工程二期 | PRJ-002-BJDZ |
| 004 郑州市区域平台项目 | PRJ-004-ZZ |
| 010 浙江省电子健康档案项目 | PRJ-010-ZJ |
| 014 安徽区域标准规范 | PRJ-014-AH |

**作用**：
- 一眼看出修订记录属于哪个项目
- 项目端升级时按 project_code 筛选相关修订
- is_standard=1 时留空

#### is_upgraded
- 升级状态枚举：
  - `0`：待升级（未升级）
  - `1`：已升级
  - `2`：已忽略

---

## edsm_revise_detail（数据标准修订明细）

### 表结构

| 字段名 | 类型 | 约束 | 说明 |
|-------|------|-----|------|
| revise_detail_id | VARCHAR(64) | PK | 修订明细标识 |
| revise_id | VARCHAR(64) | NULL | 修订记录标识（关联edsm_revise_record） |
| business_code | VARCHAR(64) | NULL | 业务分类代码 |
| business_id | VARCHAR(64) | NULL | 业务标识 |
| revise_type_code | VARCHAR(64) | NULL | 修订类型 |
| revise_before | TEXT | NULL | 修订前内容（JSON格式） |
| revise_after | TEXT | NULL | 修订后内容（JSON格式） |
| is_del | INT2 | NOT NULL | 逻辑删除（0=正常, 1=删除） |
| created_at | TIMESTAMP | NOT NULL | 创建日期时间 |
| modified_at | TIMESTAMP | NULL | 修改日期时间 |

### 字段说明

#### business_code
业务分类代码，标识本次修订涉及的业务对象类型：

| 值 | 说明 | 对应实体 |
|---|------|---------|
| `datasetCategory` | 数据集分类 | DatasetCategory |
| `dataset` | 数据集（表） | Dataset |
| `datasetElement` | 数据集元素（字段） | DatasetElement |
| `codeSystem` | 代码系统 | CodeSystem |
| `valueSet` | 值域 | ValueSet |
| `metadata` | 元数据 | Metadata |

#### business_id
业务标识，对应业务对象的ID：
- `datasetCategory` → `category_id`
- `dataset` → `dataset_id`
- `datasetElement` → `element_id`

#### revise_type_code
修订类型：

| 值 | 说明 | 处理方式 |
|---|------|---------|
| `add` | 新增 | INSERT |
| `edit` | 修改 | UPDATE（或DELETE后INSERT） |
| `delete` | 删除 | UPDATE is_del=1 |

#### revise_before / revise_after
修订前后的完整内容，JSON格式存储实体对象：

```json
// dataset示例
{
  "dataset_id": "winning-plat-01-TELEMED_REF",
  "standard_id": "winning-plat-01",
  "category_id": "winning-plat-01-医疗服务",
  "dataset_no": "TELEMED_REF",
  "dataset_name": "双向转诊",
  "status": 1,
  "is_del": 0
}

// datasetElement示例
{
  "element_id": "winning-plat-01-TELEMED_REF-REF_APPLY_AT",
  "dataset_id": "winning-plat-01-TELEMED_REF",
  "element_code": "REF_APPLY_AT",
  "element_name": "转诊申请日期时间",
  "definition": "",
  "is_pk": 0,
  "notnull": 1,
  "data_type": "DT",
  "representation_format": "DT19",
  "code_system_id": "",
  "status": 1,
  "is_del": 0
}
```

---

## 升级流程

### 项目端升级逻辑

当项目端执行升级时，会读取修订记录并执行：

```java
// DataStandardReviseServiceImpl.upgradeRevise()
public ResponseEntity upgradeRevise(ReviseRecord reviseRecord) {
    // 1. 查询修订明细
    List<ReviseDetail> reviseDetailList = reviseDetailDao.getReviseDetailData(params);

    // 2. 按修订类型处理
    for (ReviseDetail reviseDetail : reviseDetailList) {
        switch (reviseDetail.getReviseTypeCode()) {
            case "add":
                handleAddOperation(reviseDetail);  // INSERT
                break;
            case "edit":
                handleEditOperation(reviseDetail); // UPDATE
                break;
            case "delete":
                handleDeleteOperation(reviseDetail); // UPDATE is_del
                break;
        }
    }

    // 3. 更新修订记录状态为已升级
    reviseRecord.setIsUpgraded(1);
    reviseRecord.setUpgradedAt(new Date());
    reviseRecordDao.updateById(reviseRecord);

    return ResponseEntity.ok("升级成功");
}
```

### 升级步骤

1. **公版发布修订记录**
   - BMS后台生成修订记录脚本
   - 执行脚本插入 `edsm_revise_record` 和 `edsm_revise_detail`

2. **项目端检测待升级**
   - 查询 `is_upgraded = 0` 的修订记录
   - 显示待升级列表

3. **项目端执行升级**
   - 读取修订明细
   - 按修订类型更新数据标准基础数据
   - 更新修订记录状态为已升级

---

## INSERT脚本示例

### 新增表场景（公版）

```sql
-- edsm_revise_record（公版：is_standard=1，不含project_code）
insert into edsm_revise_record(
    revise_id, standard_id, version, require_no, summary,
    is_standard, published_at, is_upgraded, is_del, created_at, modified_at
) values (
    '550e8400-e29b-41d4-a716-446655440000',
    'winning-plat-01',
    '6.0',
    '1506090',
    '新增表：双向转诊[TELEMED_REF]',
    1,
    '2026-06-25 14:20:53',
    0,
    0,
    '2026-06-25 14:20:53',
    null
);

-- edsm_revise_detail（新增表）
insert into edsm_revise_detail(
    revise_detail_id, revise_id, business_code, business_id,
    revise_type_code, revise_before, revise_after, is_del, created_at, modified_at
) values (
    '550e8400-e29b-41d4-a716-446655440001',
    '550e8400-e29b-41d4-a716-446655440000',
    'dataset',
    'winning-plat-01-TELEMED_REF',
    'add',
    null,
    '{"dataset_id":"winning-plat-01-TELEMED_REF","standard_id":"winning-plat-01","category_id":"winning-plat-01-医疗服务","dataset_no":"TELEMED_REF","dataset_name":"双向转诊","status":1,"is_del":0}',
    0,
    '2026-06-25 14:20:53',
    null
);

-- edsm_revise_detail（新增表的字段）
insert into edsm_revise_detail(
    revise_detail_id, revise_id, business_code, business_id,
    revise_type_code, revise_before, revise_after, is_del, created_at, modified_at
) values (
    '550e8400-e29b-41d4-a716-446655440002',
    '550e8400-e29b-41d4-a716-446655440000',
    'datasetElement',
    'winning-plat-01-TELEMED_REF-REF_APPLY_AT',
    'add',
    null,
    '{"element_id":"winning-plat-01-TELEMED_REF-REF_APPLY_AT","dataset_id":"winning-plat-01-TELEMED_REF","element_code":"REF_APPLY_AT","element_name":"转诊申请日期时间","definition":"","is_pk":0,"notnull":1,"data_type":"DT","representation_format":"DT19","code_system_id":"","status":1,"is_del":0}',
    0,
    '2026-06-25 14:20:53',
    null
);
```

### 新增表场景（项目化）

```sql
-- edsm_revise_record（项目化：is_standard=0，含project_code）
insert into edsm_revise_record(
    revise_id, standard_id, version, require_no, summary,
    is_standard, project_code, published_at, is_upgraded, is_del, created_at, modified_at
) values (
    '550e8400-e29b-41d4-a716-446655440010',
    'winning-plat-01',
    '6.0',
    '1506090',
    '新增表：双向转诊[TELEMED_REF]',
    0,
    'PRJ-001-SZLH',
    '2026-06-25 14:20:53',
    0,
    0,
    '2026-06-25 14:20:53',
    null
);
```

### 新增字段场景

```sql
-- edsm_revise_record
insert into edsm_revise_record(
    revise_id, standard_id, version, require_no, summary,
    is_standard, published_at, is_upgraded, is_del, created_at, modified_at
) values (
    '550e8400-e29b-41d4-a716-446655440003',
    'winning-plat-01',
    '6.0',
    '1506091',
    '双向转诊[TELEMED_REF]新增字段：转诊申请日期时间[REF_APPLY_AT,TIMESTAMP,必填]',
    1,
    '2026-06-25 15:30:00',
    0,
    0,
    '2026-06-25 15:30:00',
    null
);

-- edsm_revise_detail
insert into edsm_revise_detail(
    revise_detail_id, revise_id, business_code, business_id,
    revise_type_code, revise_before, revise_after, is_del, created_at, modified_at
) values (
    '550e8400-e29b-41d4-a716-446655440004',
    '550e8400-e29b-41d4-a716-446655440003',
    'datasetElement',
    'winning-plat-01-TELEMED_REF-REF_APPLY_AT',
    'add',
    null,
    '{"element_id":"winning-plat-01-TELEMED_REF-REF_APPLY_AT","dataset_id":"winning-plat-01-TELEMED_REF","element_code":"REF_APPLY_AT","element_name":"转诊申请日期时间","definition":"","is_pk":0,"notnull":1,"data_type":"DT","representation_format":"DT19","code_system_id":"","status":1,"is_del":0}',
    0,
    '2026-06-25 15:30:00',
    null
);
```