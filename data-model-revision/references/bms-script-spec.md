# BMS脚本规范说明

本文档描述BMS后端程序中DDL脚本和修订记录脚本的命名规范和内容格式。

## 目录结构

```
winning-dps-rda-bms-server/src/main/resources/
├── edsm_sql/                          ← DDL脚本目录（Flyway管理）
│   ├── greenplum/                     ← Greenplum/PostgreSQL脚本
│   │   ├── V20260106180223__create_init_tables.sql
│   │   ├── V20260528103922__alter_table_telemed_ref.sql
│   │   └── ...
│   ├── oracle/                        ← Oracle脚本
│   ├── sqlserver/                     ← SQL Server脚本
│   └── postgresql/                    ← PostgreSQL脚本（与greenplum兼容）
│
└── system_sql/                        ← 系统脚本目录
    ├── rhdp_app/                      ← 应用层脚本
    │   └── postgresql/
    │       ├── V20260206142053__create_table_edsm_revise.sql  ← 修订记录表创建
    │       └── V{timestamp}__insert_revise_record_{doc}.sql   ← 修订记录INSERT
    │
    └── rhdp_dw/                       ← 数据仓库脚本
        └── greenplum/
            └── {edsm同步脚本}
```

---

## DDL脚本命名规范（Flyway）

### 文件命名格式

```
V{YYYYMMDDHHMMSS}__{描述}.sql
```

| 组成部分 | 说明 | 示例 |
|---------|------|------|
| V | 固定前缀 | V |
| 时间戳 | 年月日时分秒，14位 | 20260625142053 |
| __ | 双下划线分隔符 | __ |
| 描述 | 操作描述 | alter_table_telemed_ref |
| .sql | 固定后缀 | .sql |

### 命名示例

| 场景 | 文件名 |
|-----|--------|
| 新增表 | `V20260625142053__create_table_telemed_ref.sql` |
| 新增字段 | `V20260625153000__alter_table_telemed_ref.sql` |
| 修改字段 | `V20260625163000__modify_table_telemed_ref.sql` |
| 创建索引 | `V20260625170000__create_index_telemed_ref.sql` |

### 时间戳规则

- 使用实际时分秒，不能全0（如 `V20260625000000` 会被Flyway拒绝）
- 建议使用脚本生成时的实际时间
- 多个脚本按时间戳顺序执行

---

## DDL脚本内容规范

### Greenplum/PostgreSQL格式

```sql
-- 修订注释（简要描述变更）
-- 双向转诊[TELEMED_REF] 新增字段：转诊申请日期时间[REF_APPLY_AT,TIMESTAMP,必填]

-- 使用do $$块执行DDL（Flyway推荐方式）
do $$
begin
    -- 检查字段是否存在
    if not exists (
        select 1 from information_schema.columns
        where table_name = 'telemed_ref' and column_name = 'ref_apply_at'
    ) then
        -- 新增字段
        alter table telemed_ref add column ref_apply_at timestamp null;

        -- 添加字段注释
        comment on column telemed_ref.ref_apply_at is '转诊申请日期时间';
    end if;
end $$;
```

### 新增表示例

```sql
-- 医护人员信息表[BASE_EMPLOYEE] - 新增表
create table if not exists BASE_EMPLOYEE (
    SYS_SOID VARCHAR(64) NOT NULL,
    EMPLOYEE_ID VARCHAR(64) NOT NULL,
    ORG_CODE VARCHAR(64) NOT NULL,
    -- ... 其他字段
    primary key (SYS_SOID, EMPLOYEE_ID)
);

-- 字段注释（使用do $$块）
do $$
begin
    comment on column BASE_EMPLOYEE.SYS_SOID is '系统编码, 复合主键';
    comment on column BASE_EMPLOYEE.EMPLOYEE_ID is '医护人员唯一标识, 复合主键';
    -- ... 其他注释
end $$;
```

### 关键规范

| 规范项 | 要求 |
|-------|------|
| 幂等性 | 使用 `if not exists` 检查，避免重复执行报错 |
| 字段约束 | 新增字段统一使用 `null`，避免已有数据插入失败 |
| 注释方式 | 使用 `comment on column` 语句 |
| 脚本块 | 使用 `do $$ ... end $$;` 包裹多条语句 |
| 分隔符 | 每个表的操作完成后不需要GO（PostgreSQL） |

---

## 修订记录脚本命名规范

### 文件命名格式

```
V{YYYYMMDDHHMMSS}__insert_revise_record_{文档名}.sql
```

| 组成部分 | 说明 | 示例 |
|---------|------|------|
| V | 固定前缀 | V |
| 时间戳 | 年月日时分秒，14位 | 20260625142053 |
| __ | 双下划线分隔符 | __ |
| insert_revise_record | 固定操作类型 | insert_revise_record |
| {文档名} | 来源文档名称（可选） | 第02部分医疗服务 |
| .sql | 固定后缀 | .sql |

### 命名示例

```
V20260625142053__insert_revise_record.sql
V20260625142053__insert_revise_record_第02部分医疗服务.sql
```

---

## 修订记录脚本内容规范

### 脚本结构

```sql
-- 数据标准修订记录脚本
-- 文档: 第02部分：医疗服务
-- 需求号: 1506090
-- 版本: 6.0
-- 标准ID: winning-plat-01
-- 生成时间: 2026-06-25 14:20:53

-- ========== 修订摘要 ==========
-- 新增表：双向转诊[TELEMED_REF]
-- 双向转诊[TELEMED_REF]新增字段：转诊申请日期时间[REF_APPLY_AT,TIMESTAMP,必填]

-- ========== edsm_revise_record ==========

-- 数据标准修订记录
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

-- ========== edsm_revise_detail ==========

-- 新增数据集
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
    '{"dataset_id":"winning-plat-01-TELEMED_REF",...}',
    0,
    '2026-06-25 14:20:53',
    null
);

-- 新增数据集元素（字段）
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
    '{"element_id":"winning-plat-01-TELEMED_REF-REF_APPLY_AT",...}',
    0,
    '2026-06-25 14:20:53',
    null
);
```

---

## 数据标准基础数据同步脚本规范

数据标准基础数据同步脚本用于将数据模型结构化数据存入数据库表（edsm_*系列表），便于数据标准版本管理和项目端同步。

### 脚本目录

```
system_sql/rhdp_dw/greenplum/
```

### 脚本内容

```sql
-- 标准库同步DML脚本
-- 文档: 第02部分：医疗服务
-- 标准ID: winning-plat-01
-- 生成时间: 2026-06-25 14:20:53

-- ========== edsm_dataset_category（新增分类）==========

insert into edsm_dataset_category(category_id, standard_id, parent_id, category_no, category_name, seq_no, is_del, created_at, modified_at)
select 'winning-plat-01-医疗服务', 'winning-plat-01', null, '医疗服务','医疗服务', (select count(1) from edsm_dataset_category)+1, 0, now(), null
where not exists (select 1 from edsm_dataset_category where category_id = 'winning-plat-01-医疗服务');

-- ========== edsm_dataset（新增数据集）==========

insert into edsm_dataset(dataset_id, standard_id, category_id, dataset_no, dataset_name, status, seq_no, is_del, created_at, modified_at)
select 'winning-plat-01-TELEMED_REF','winning-plat-01', 'winning-plat-01-医疗服务', 'TELEMED_REF', '双向转诊', 1, (select count(1) from edsm_dataset)+1, 0, now(), null
where not exists (select 1 from edsm_dataset where dataset_id = 'winning-plat-01-TELEMED_REF');

-- ========== edsm_dataset_element（新增数据集字段）==========

insert into edsm_dataset_element(element_id, dataset_id, metadata_id, internal_id, element_code, element_name, definition, is_pk, "notnull", data_type, representation_format, code_system_id, allow, status, seq_no, is_del, created_at, modified_at)
select 'winning-plat-01-TELEMED_REF-REF_APPLY_AT', 'winning-plat-01-TELEMED_REF', null, null, 'REF_APPLY_AT', '转诊申请日期时间', '', 0, 1, 'DT', 'DT19', '', null, 1, 1, 0, now(), null
where not exists (select 1 from edsm_dataset_element where element_id = 'winning-plat-01-TELEMED_REF-REF_APPLY_AT');
```

---

## 脚本提交流程

### 提交步骤

1. **生成脚本**
   - 使用 `reg-ddl-generator` 生成DDL脚本
   - 使用 `revise_record_generator.py` 生成修订记录脚本

2. **检查目录**
   - 确认目标目录存在
   - 确认文件命名符合Flyway规范

3. **复制脚本**
   - DDL脚本 → `edsm_sql/{数据库类型}/`
   - 修订记录脚本 → `system_sql/rhdp_app/postgresql/`

4. **Git提交**（可选）
   ```bash
   cd winning-dps-rda-bms
   git add winning-dps-rda-bms-server/src/main/resources/edsm_sql/greenplum/V*.sql
   git commit -m "新增数据模型修订：需求1506090"
   ```

### 提交清单

```
本次修订提交的脚本：
1. DDL脚本
   - edsm_sql/greenplum/V20260625142053__alter_table_telemed_ref.sql

2. 修订记录脚本
   - system_sql/rhdp_app/postgresql/V20260625142053__insert_revise_record.sql

3. 数据标准基础数据同步脚本（可选）
   - system_sql/rhdp_dw/greenplum/V20260625142053__sync_dataset.sql
```