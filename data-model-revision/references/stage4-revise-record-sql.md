> 本文件从 SKILL.md 外置。
> **触发条件**：**生成修订记录 SQL**（`edsm_revise_record` + `edsm_revise_detail`）前必读。

# 阶段4：修订记录SQL生成（重要经验）

### 修订摘要格式（summary字段）

> **注释规范以 `references/bms-script-spec.md`《注释规范（DDL 与修订记录统一约束）》为准**。核心规则：
> - 字段写在 `[]` 内，分量用半角逗号分隔，顺序为 `[字段代码, 填报要求, 数据类型, 表示格式, 定义, 值域, 约束, 默认值]`（仅字段代码必填，其余有值才写）；表英文名 `]` 后**不加空格**。
> - 四类操作 + 值域：`{表}[{EN}]新增字段：…` / ` - 新增表` / `修改字段：…（旧→新）` / `删除字段：…`；值域用 `值域-{代码表}[{CVA}]新增值：…` / `值修改为：…`。
> - **批量排版**：同表**加/删**多个字段用**顿号合一行**；**修改**字段**不得合在一行**，每个字段独立一行。
> - **DDL 脚本与修订记录脚本的变更描述必须逐字一致**（同一份 `/* */` 清单）。

**规则**：
1. `summary` **必须等于**修订记录脚本头部 `/* */` 编号清单，多条用 `\n` 连接，单条即那一行描述。
2. 条数与顺序、文字必须与配套 DDL 顶部清单一致。
3. 加/删字段顿号合并；修改字段逐行。

```sql
-- 正确示例（与 DDL 顶部 /* */ 清单逐字一致）：
'1. 出院登记信息[INP_DISCHARGE]新增字段：日间手术病例标志[DAY_OP_FLAG,O,S3,N1]\n2. 远程会诊[TELEMED_CONSULT]删除字段：流程状态[PROCESS_STATUS_CODE]\n3. 远程检验[TELEMED_LAB]修改字段：检验类别代码[LAB_CATEGORY_CODE]（值域 CVA-0199→CT04.50.001）\n4. 远程检验[TELEMED_LAB]修改字段：标本类型代码[SPECIMEN_TYPE_CODE]（值域 CVA-0200→CVA-0255）\n5. 值域-编制情况代码表[CVA-0165]新增值：6[核酸岗]、7[员额岗]\n6. 新增表：机构数据统计表[ORG_STATISTICAL]\n7. 值域-双向转诊流程状态代码[CVA-0282]值修改为：01[已提交]、02[转出审核通过]、03[转出审核驳回]、04[转入审核通过]、05[转入审核驳回]、06[已接诊]、07[已取消]'

-- 错误示例：
'1. 增加字段 STATUS'                              -- 缺表中文名/英文名、措辞与 DDL 漂移
'远程检验[TELEMED_LAB]修改字段：A[..]（…）、B[..]（…）'  -- 修改字段不得用顿号合并，应每行一个
```

**正确优先（一次写对，不靠校验兜底）**：生成 DDL / 修订记录脚本时，**直接按 `references/bms-script-spec.md`《注释规范》把注释写对**——四类操作模板、字段项详细式 `[代码,填报要求,数据类型,表示格式]`、批量排版（加/删顿号合一行、修改逐行）、DDL↔修订记录逐字一致，全部在落盘前就满足。把校验脚本当成"最后一道门禁"，而不是"写错了再改"的循环。**任何情况下都不要把不合规的注释先写进去再等校验报错**。

**生成后必跑校验**（门禁，不通过不得交付）：

```bash
python3 scripts/check_comment_consistency.py \
    --ddl  edsm_sql/doris/V{ts}__xxx.sql edsm_sql/greenplum/V{ts}__xxx.sql \
    --revise system_sql/rhdp_app/postgresql/V{ts}__insert_revise_record_{需求号}.sql
```

### 完整的修订记录内容

一条完整的修订记录SQL应包含：
1. `edsm_revise_record` × 1条
2. `edsm_revise_detail`（business_code='codeSystem'） × 值域代码系统（新增值域时）
3. `edsm_revise_detail`（business_code='valueSet'） × 值域条目（新增值域时）
4. `edsm_revise_detail`（business_code='datasetCategory'） × 分类数（新增分类时）
5. `edsm_revise_detail`（business_code='dataset'） × 新增表数（**必须包含seqNo字段**）
6. `edsm_revise_detail`（business_code='metadata'） × 元数据（新字段需要添加元数据）
7. `edsm_revise_detail`（business_code='datasetElement'） × 所有字段数

### 数据集序号（seqNo）确定规则

- 数据集记录必须包含seqNo字段
- 序号要和文档中的顺序一致
- 查看Word文档中新表的位置，确定前一个表的序号
- 新表序号 = 前一个表序号 + 1

### 元数据（metadata）添加规则（一对一，废除共用）

**核心原则（绝对规则）**：每个数据集元素（datasetElement）对应**唯一一个**元数据（metadata），二者**一一对应**。

- **废除"元数据共用 / 去重"逻辑**：不再有任何"公共字段共用同一份元数据"的例外。
- **元数据的代码（metadataCode）与数据集元素的唯一标识（element_id）保持一致**：
  - `element_id` = `{standard_id}-{数据集代码}-{字段代码}`（如 `winning-plat-02-BASE_EMPLOYEE-STATUS`）
  - `metadata_id` = `element_id`（元数据主键 = 元素唯一标识）
  - `metadata_code` = `element_id`（与数据集元素唯一标识一致，便于追踪）
  - `datasetElement.metadata_id` = 自己的 `element_id`（指向专属元数据）
- **同一字段名出现在不同表/数据集中，各自生成独立的元数据**。例如 `winning-plat-02-BASE_DEPARTMENT-STATUS` 与 `winning-plat-02-BASE_EMPLOYEE-STATUS` 是两条**不同**的元数据，互不共享。
- **管理优势**：元数据 ID 直接由元素唯一标识推导得出，**不再需要去历史元数据里查 ID**。

**历史已存在的元数据**：不做任何改动，保持原样。本规则仅对**本次及以后**的新增 / 修订生效。

**元数据字段结构**：
```json
{
  "metadataId": "winning-plat-02-{数据集代码}-{字段名}",
  "namespaceId": "1",
  "externalId": "<由 generator 按 external-id-spec.md 规则自动生成，禁止留空>",
  "metadataCode": "winning-plat-02-{数据集代码}-{字段名}",
  "metadataName": "{中文名}",
  "definition": "{定义说明}",
  "dataType": "{数据类型}",
  "representationFormat": "{表示格式}",
  "codeSystemId": "{值域代码系统ID}",
  "allow": "",
  "status": 1,
  "isDel": 0,
  "createdAt": "{时间戳}",
  "modifiedAt": ""
}
```

**datasetElement引用元数据**：
```json
{
  "elementId": "winning-plat-02-{数据集代码}-{字段名}",
  "datasetId": "winning-plat-02-{数据集代码}",
  "metadataId": "winning-plat-02-{数据集代码}-{字段名}",  // 引用自己的专属元数据（= element_id）
  "elementCode": "{字段名}",  // 与文档字段英文名大小写一致，不转换
  "elementName": "{中文名}",
  "definition": "{定义说明}",
  "isPk": 0,
  "notnull": 0,
  "dataType": "{数据类型}",
  "representationFormat": "{表示格式}",
  "codeSystemId": "{值域代码系统ID}",
  "allow": "",
  "status": 1,
  "seqNo": {序号},
  "isDel": 0,
  "createdAt": "{时间戳}",
  "modifiedAt": ""
}
```

### SQL脚本格式

**注释头统一遵循 `references/bms-script-spec.md`《注释规范（DDL 与修订记录统一约束）》**：生成前先 `Read` 一条最近的同类脚本，参考其**命名风格、SQL 写法、JSON 结构**，但**注释头必须用统一的 `/* */` 编号清单**（不套用旧脚本里的 `-- 集合:` / `-- 需求:` 头注释）：

**强制格式（头部 `/* */` 清单与配套 DDL 逐字一致）**：

```sql
/*
1. (个人)基本信息[RESIDENT_ARCHIVE]新增字段：老年人健康管理等级代码[ELDER_HEALTH_LEVEL_CODE,O,S3,N1]
*/

insert into edsm_revise_record(revise_id,standard_id,version,require_no,summary,is_standard,published_at,is_upgraded,is_del,created_at)
values('{UUID}','winning-plat-02','{版本号}','{需求号}','1. (个人)基本信息[RESIDENT_ARCHIVE]新增字段：老年人健康管理等级代码[ELDER_HEALTH_LEVEL_CODE,O,S3,N1]',1,'{时间戳}',0,0,'{时间戳}');

/* (个人)基本信息[RESIDENT_ARCHIVE]新增字段：老年人健康管理等级代码[ELDER_HEALTH_LEVEL_CODE,O,S3,N1] · 元数据 */
insert into edsm_revise_detail(...)values(...);

/* (个人)基本信息[RESIDENT_ARCHIVE]新增字段：老年人健康管理等级代码[ELDER_HEALTH_LEVEL_CODE,O,S3,N1] · 数据集元素 */
insert into edsm_revise_detail(...)values(...);
```

**要点**：
- 头部只保留 `/* */` 编号清单，**不写** `-- 集合:` / `-- 需求:` / `-- 字段:` / `-- 说明:` 等辅助注释行；需求号仅体现于文件名与 `require_no` 列。
- INSERT 语句必须单行、紧凑，revise_after 用单行 JSON（字段名驼峰、日期 ISO 带 T）。
- `summary` 必须等于头部 `/* */` 清单（多条用 `\n` 连接），禁止与清单措辞或顺序不同。
- 同目录下 DDL（`edsm_sql/`、`system_sql/rhdp_dw/greenplum/`）和 CSV（`base_data/`）脚本也遵循同样原则：**先看同目录已有文件，复制其命名风格与 SQL 写法，但注释头统一按本规范**。

---

