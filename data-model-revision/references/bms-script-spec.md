# BMS脚本规范说明

本文档描述BMS后端程序中DDL脚本和修订记录脚本的命名规范和内容格式。

## Flyway 增量脚本铁律（禁止修改历史）

所有脚本均由 Flyway 按版本号顺序执行，历史版本一旦执行即记入 `flyway_schema_history`。**严禁修改已存在的 `V{时间戳}__*.sql` 历史脚本**，否则 Flyway 校验失败、整个升级流程无法执行。

- **只增不改**：每次标准修订都生成**新的**版本化文件（新的时间戳），不回改、不删减任何历史文件。
- **适用范围**：
  - DDL 脚本：`edsm_sql/{库类型}/`（greenplum / oracle / sqlserver / postgresql）
  - 修订记录脚本：`system_sql/rhdp_app/postgresql/`
  - 数据标准基础数据同步脚本：`system_sql/rhdp_dw/greenplum/`
  - 数据标准基础数据 CSV：`base_data/1__*~14__*.csv`
- **基础数据（CSV / DML）也是增量**：新增数据 → 追加新行或新建增量脚本；修改已有数据 → 用新的增量脚本表达（先删后插 / UPDATE），**不动原始脚本和 CSV**。
- **历史脚本有问题**：不要改历史文件，新增一个版本号更新的修复脚本（repair / fix）来纠正。
- **参考同目录既有脚本**：生成/增加新脚本（`V*.sql`、CSV、DML）前，先 `Read` 同目录下已有的同类脚本，复制其**命名风格、SQL 写法与内容约定**（如 `comment on column ... is '...'` 写法、`base_data/*.csv` 的列顺序与表头）；但**注释头格式统一用本规范第 19 行起的《注释规范》`/* */` 块**，**不套用旧脚本里的 `-- 集合:` / `-- 需求:` 头注释**，避免与历史脚本的格式混用。

## 注释规范（DDL 与修订记录统一约束）

> 所有脚本注释必须遵循本规范。DDL 脚本（`edsm_sql/{库}`）与配套的基础数据修订记录脚本（`system_sql/rhdp_app/postgresql`）描述**同一处变更**，两者的"变更描述"必须保持一致——共用同一套描述语言、同一句话。

### 1. 统一变更描述语言（四类操作 + 值域）

#### 1.1 字段项格式（必读）

字段写在 `[]` 内，项与项之间用**半角逗号**分隔，顺序固定为：

```
[字段代码, 填报要求, 数据类型, 表示格式, 表示格式, 定义, 值域, 约束, 默认值]
```

- 仅"字段代码"为必填，其余按数据模型实际有值才写；没有的项**省略，不写空位**。
- 示例（字段代码 + 填报要求 + 数据类型 + 表示格式）：`日间手术病例标志[DAY_OP_FLAG,O,S3,N1]`。
- 表英文名 `]` 后**不加空格**（接 `新增字段：` 等操作词直接相连）。

#### 1.2 四类操作模板

| 操作 | 模板 | 示例 |
|------|------|------|
| 加字段 | `{表中文}[{表英文}]新增字段：{字段中文}[{字段项}]` | `出院登记信息[INP_DISCHARGE]新增字段：日间手术病例标志[DAY_OP_FLAG,O,S3,N1]` |
| 加表 | `{表中文}[{表英文}] - 新增表` | `机构数据统计表[ORG_STATISTICAL] - 新增表` |
| 修改字段 | `{表中文}[{表英文}]修改字段：{字段中文}[{字段代码}]（{旧}→{新}）` | `辅助检查[PE_AUXILIARY]修改字段：白细胞计数值[WBC]（表示格式 N..3,1→N..4,2）` |
| 删除字段 | `{表中文}[{表英文}]删除字段：{字段中文}[{字段代码}]` | `远程会诊[TELEMED_CONSULT]删除字段：流程状态[PROCESS_STATUS_CODE]` |

#### 1.3 批量写法（关键排版规则）

| 场景 | 规则 | 写法 |
|------|------|------|
| 同表加多个字段 | **合并一行**，字段间用**顿号（、）**分隔 | `出院登记信息[INP_DISCHARGE]新增字段：字段一中文[CODE1,…]、字段二中文[CODE2,…]、字段三中文[CODE3,…]` |
| 同表删多个字段 | **合并一行**，字段间用**顿号（、）**分隔 | `远程检验[TELEMED_LAB]删除字段：字段一中文[CODE1]、字段二中文[CODE2]` |
| 同表改多个字段 | **不写在一起**，每个字段**独立一行** | 每字段一条 `修改字段：…（旧→新）` |

> 理由：加 / 删是同质的"增减"动作，合在一行读起来紧凑；修改涉及每个字段"旧值→新值"各不相同，挤在一行反而看不清，故逐字段分行。

#### 1.4 值域（codeSystem / valueSet）修订

值域是独立于表的修订轨道，描述格式与表字段不同：

| 操作 | 模板 | 示例 |
|------|------|------|
| 值集新增项 | `值域-{代码表中文}[{CVA}]新增值：{值}[{明细中文}]、{值}[{明细中文}]` | `值域-编制情况代码表[CVA-0165]新增值：6[核酸岗]、7[员额岗]` |
| 值集枚举修改 | `值域-{代码表中文}[{CVA}]值修改为：{值}[{新中文}]、…` | `值域-双向转诊流程状态代码[CVA-0282]值修改为：01[已提交]、02[转出审核通过]、…、07[已取消]` |
| 字段值域引用变更 | 走"修改字段"，在括号里写值域迁移 | `远程检验[TELEMED_LAB]修改字段：检验类别代码[LAB_CATEGORY_CODE]（值域 CVA-0199→CT04.50.001）` |

#### 1.5 真实示例全集（清单里就这样写）

```sql
/*
1. 出院登记信息[INP_DISCHARGE]新增字段：日间手术病例标志[DAY_OP_FLAG,O,S3,N1]
2. 远程会诊[TELEMED_CONSULT]删除字段：流程状态[PROCESS_STATUS_CODE]
3. 远程检验[TELEMED_LAB]修改字段：检验类别代码[LAB_CATEGORY_CODE]（值域 CVA-0199→CT04.50.001）
4. 远程检验[TELEMED_LAB]检验类别代码[LAB_CATEGORY_CODE]字段值域由"CVA-0199"变更为："CT04.50.001"   ← 老式逐字段长描述，1.4 新规统一改为第 3 条写法
5. 值域-编制情况代码表[CVA-0165]新增值：6[核酸岗]、7[员额岗]
6. 新增表：机构数据统计表[ORG_STATISTICAL]
7. 值域-双向转诊流程状态代码[CVA-0282]值修改为：01[已提交]、02[转出审核通过]、03[转出审核驳回]、04[转入审核通过]、05[转入审核驳回]、06[已接诊]、07[已取消]
*/
```

- 多表同脚本：DDL 顶部 `/* */` 变更清单逐条编号；修订记录头部用**同一份**编号清单（见第 3 节），条数、顺序、文字逐字一致。

**统一采用"详细式"字段项**（张磊定稿，唯一标准，不再提供简式/详式二选一）：字段项 `[]` 内按 `[字段代码, 填报要求, 数据类型, 表示格式, 定义, 值域, 约束, 默认值]` 顺序书写，仅"字段代码"必填，其余有值才写、不写空位。

```sql
-- 标准写法（详细式）：
出院登记信息[INP_DISCHARGE]新增字段：日间手术病例标志[DAY_OP_FLAG,O,S3,N1]
-- 当字段仅有代码、无其它属性时，仅写代码（这不算"另一套格式"，而是详细式的省略形态）：
科室信息[BASE_DEPARTMENT]新增字段：记录状态[STATUS]
```

> **铁律**：DDL 脚本与修订记录脚本是同一处修订的配套产物，两者变更清单的条数、顺序、描述文字（含字段项形态）必须逐字一致。

### 2. DDL 脚本注释结构

- **文件级变更清单**：脚本顶部用 `/* */` 注释块，逐条（编号）列出本次所有变更，每条用第 1 节模板。
  ```sql
  /*
  1. 科室信息[BASE_DEPARTMENT]新增字段：记录状态[STATUS]
  2. 医护人员信息表[BASE_EMPLOYEE]新增字段：记录状态[STATUS]
  */
  ```
- **语句级注释**：
  - Doris `ALTER`：用 `/* {描述} */` 放在 `alter table` 前。同表加/删多个字段时，若多条 `alter table` 合并为一个块，**只保留一条清单级注释**（`/* {表中文}[{表英文}]新增字段：…、… */`），不必每条字段重复注释。
  - Doris / Greenplum `CREATE TABLE`：用 `-- {表中文名}[{表英文名}] - 新增表` 放在 `create table` 前。
  - Greenplum `ALTER`（do $$ 块）：块前用 `-- {描述}` 注释。
  - **修改字段**：每字段独立一行注释 + 独立的 `alter table` 语句（不合并）。
  - 字段类型 / 约束 / 默认值按数据模型写入 SQL 本身（`comment on column` / `comment '...'`），注释里不再重复类型。

### 3. 修订记录脚本注释结构

统一用 `/* */` 编号清单（无论单条还是多条），**与配套 DDL 顶部清单逐条逐字一致（含编号顺序、字段项形态）**；**不写** `-- 集合:` / `-- 需求:` / `-- 字段:` / `-- 说明:` 等辅助注释行（需求号仅体现于文件名与 `require_no` 列）：

```sql
/*
1. 科室信息[BASE_DEPARTMENT]新增字段：记录状态[STATUS,O,S3,N1]
2. 医护人员信息表[BASE_EMPLOYEE]新增字段：记录状态[STATUS,O,S3,N1]
*/
```

- **`summary` 字段 = 头部清单**：`edsm_revise_record.summary` 必须与头部清单**逐字一致**，多条时用 `\n` 连接（`1. xxx\n2. xxx`），单条时即 `1. xxx`。禁止 summary 与头部清单不同措辞或不同顺序。
- **语句级注释**：每条 `insert into edsm_revise_detail` 前用 `/* {变更描述} · {对象类型} */`，主句照抄清单，后缀标注对象类型（`元数据` / `数据集元素` / `值域` / `值域明细` / `数据集`）。
  ```sql
  /* 科室信息[BASE_DEPARTMENT]新增字段：记录状态[STATUS,O,S3,N1] · 元数据 */
  /* 科室信息[BASE_DEPARTMENT]新增字段：记录状态[STATUS,O,S3,N1] · 数据集元素 */
  ```
- **明细顺序**：`edsm_revise_detail` 各条按头部清单编号顺序分组排列（同一条变更的 元数据 → 数据集元素 相邻），不得与清单顺序错位。
- 字段类型 / 约束等细节放 `revise_after` 的 JSON 内，不在头部重复；脚本头部**不写** `-- 集合:` / `-- 需求:` / `-- 字段:` / `-- 说明:` 等辅助注释行（与第 111 行要求一致）。

### 4. 一致性铁律（配套脚本）

> DDL 脚本与修订记录脚本是**同一处标准修订的配套产物**（动表结构走增量 DDL，动基础数据走修订记录）。两者头部 / 变更清单里的"变更描述"必须逐字一致——同一张表、同一个字段、同一种操作、同一编号顺序，用同一句话描述。禁止一套写"新增字段"另一套写"增加字段"之类的措辞漂移。

**自动校验（生成后必跑）**：

```bash
python3 scripts/check_comment_consistency.py \
    --ddl  edsm_sql/doris/V{ts}__xxx.sql edsm_sql/greenplum/V{ts}__xxx.sql \
    --revise system_sql/rhdp_app/postgresql/V{ts}__insert_revise_record_{需求号}.sql
```

退出码非 0 即视为生成失败，必须修到全部通过再交付。

**一致性检查清单**（脚本已覆盖，人工复核用）：

| # | 检查项 | 要求 |
|---|--------|------|
| 1 | 变更条数与顺序 | DDL 顶部清单 与 修订记录头部清单 条数相同、编号顺序相同 |
| 2 | 描述文字 | 每条主句逐字一致（表中文名/英文名/操作词/字段中文名/字段代码全同） |
| 3 | summary | `edsm_revise_record.summary` 与头部清单逐字一致（`\n` 连接） |
| 4 | 语句级注释 | DDL 每条 `alter/create` 前的注释 = 清单中对应那条 |
| 5 | 需求号 | 文件名中的 `{需求号}` / `require_no` 两处同一个真实需求号（`-- 需求:` 注释行不写） |

**唯一允许的差异**：当"标准动作"与"物理落地方式"本就不同（例：标准侧字段逻辑删除 `isDel=1`，DDL 侧只能把约束改为非必填而不真删列），**主句必须仍然一致**，仅在括号内注明各自的落地方式：

```
修订记录： 2. 签约记录[SIGN_RECORD]删除34字段（isDel=1）：...
DDL：      2. 签约记录[SIGN_RECORD]删除34字段（约束改为非必填）：...
```

除此之外不得有任何措辞差异。

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
-- 双向转诊[TELEMED_REF]新增字段：转诊申请日期时间[REF_APPLY_AT]

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
| 字段约束 | 新增字段的 NULL/NOT NULL 与默认值**以数据模型定义为准**：参考脚本多为可空 `null`；强制标志类字段（如状态 STATUS `not null default '0'`）按实体口径用 `not null default '0'`，目的均为避免对已有数据造成写入失败或语义错误 |
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
/*
1. 双向转诊[TELEMED_REF] - 新增表
*/

/* ## 修订主记录 */
insert into edsm_revise_record(revise_id,standard_id,version,require_no,summary,is_standard,published_at,is_upgraded,is_del,created_at)values('550e8400-e29b-41d4-a716-446655440000','winning-plat-01','6.0','1506090','1. 双向转诊[TELEMED_REF] - 新增表',1,'2026-06-25 14:20:53',0,0,'2026-06-25 14:20:53');

/* 双向转诊[TELEMED_REF] - 新增表 · 数据集 */
insert into edsm_revise_detail(revise_detail_id,revise_id,business_code,business_id,revise_type_code,revise_before,revise_after,is_del,created_at)values('550e8400-e29b-41d4-a716-446655440001','550e8400-e29b-41d4-a716-446655440000','dataset','winning-plat-01-TELEMED_REF','add',null,'{"datasetId":"winning-plat-01-TELEMED_REF",...}',0,'2026-06-25 14:20:53');

/* 双向转诊[TELEMED_REF] - 新增表 · 数据集元素 */
insert into edsm_revise_detail(revise_detail_id,revise_id,business_code,business_id,revise_type_code,revise_before,revise_after,is_del,created_at)values('550e8400-e29b-41d4-a716-446655440002','550e8400-e29b-41d4-a716-446655440000','datasetElement','winning-plat-01-TELEMED_REF-REF_APPLY_AT','add',null,'{"elementId":"winning-plat-01-TELEMED_REF-REF_APPLY_AT",...}',0,'2026-06-25 14:20:53');
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