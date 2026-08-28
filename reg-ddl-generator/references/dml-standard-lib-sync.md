> 本文件从 SKILL.md 外置。
> **触发条件**：需要生成 **DML 标准库同步脚本**时读。

# DML标准库同步规则

当用户选择生成DML脚本时，将变更同步到以下标准库表：

### 表映射关系

| Word文档元素 | 标准库表 | 操作规则 |
|-------------|---------|---------|
| 文档封面名称 | `edsm_data_standard` | 一般不新增/修改（固定7个标准） |
| 数据集区域二级目录 | `edsm_dataset_category` | 红色字体→INSERT新增分类 |
| 数据集表格 | `edsm_dataset` | 新增表→INSERT；修改表→DELETE+INSERT |
| 数据集字段 | `edsm_dataset_element` | 新增字段→INSERT；修改字段→DELETE+INSERT |
| 元数据汇总 | `edsm_metadata` | 与dataset_element**一一对应、各自独立**，每个元素生成一条专属metadata，绝不共用/去重 |

### ID命名规则

| 表 | ID格式 | 示例 |
|----|--------|------|
| edsm_data_standard | `{standard_prefix}` | `winning-plat-01` |
| edsm_dataset_category | `{standard_id}-{category_name}` | `winning-plat-01-患者基本信息` |
| edsm_dataset | `{standard_id}-{dataset_no}` | `winning-plat-01-PERSON` |
| edsm_dataset_element | `{standard_id}-{dataset_no}-{element_code}` | `winning-plat-01-PERSON-XM` |

### 分类目录提取规则

Word文档中的"数据集区域"二级标题（如"患者基本信息"、"门急诊信息"）对应分类：
- 检测标题是否红色字体
- 红色标题 → 新增分类 → 生成INSERT语句
- 非红色标题 → 不操作（分类已存在）

### dataset_element字段映射

| Word列头 | dataset_element字段 | 说明 |
|---------|---------------------|------|
| 数据元标识 | element_code | 字段英文名（大小写与标准文档一致，不转换：文档大写则大写、小写则小写） |
| 数据元名称 | element_name | 字段中文名 |
| 说明/定义 | definition | 字段定义说明 |
| 约束(M/O) | notnull | 1=M(必填), 0=O(可选) |
| 是否主键 | is_pk | 从definition中检测"复合主键"等字样 |
| 数据类型 | data_type | S1/S2/S3/D/DT等 |
| 表示格式 | representation_format | AN..64/N1/DT19等 |
| 值域代码 | code_system_id | 如 GB/T 2261.1-2003 |

### DML生成策略

**新增场景**：
```sql
-- 新增分类
insert into edsm_dataset_category(...) select ... where not exists (...);

-- 新增数据集
insert into edsm_dataset(...) select ... where not exists (...);

-- 新增字段
insert into edsm_dataset_element(...) select ... where not exists (...);
```

**修改场景**（先删后插）：
```sql
-- 修改数据集：删除旧数据
delete from edsm_dataset_element where dataset_id = 'xxx';
delete from edsm_dataset where dataset_id = 'xxx';
-- 再插入新数据
insert into edsm_dataset(...) select ...;
insert into edsm_dataset_element(...) select ...;
```

**元数据一对一（重要，废除共用/去重）**：
- edsm_metadata 与 edsm_dataset_element **一一对应**：每一条 dataset_element 都生成一条独立、专属的 metadata，绝不按字段名共用同一份元数据（否则同名不同表的字段会串号）
- `metadata_id` = `metadata_code` = `element_id`（即 `{standard_id}-{dataset_no}-{element_code}`）
- `dataset_element.metadata_id` 直接关联自己的 `element_id`，不再通过 `element_code` 字段名反查
- 脚本通过 `not exists (select 1 from edsm_metadata where metadata_id = a.element_id)` 保证幂等增量；历史已存在的元数据**不做任何改动**

---

