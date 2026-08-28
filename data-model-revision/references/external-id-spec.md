# 数据元标识符（external_id）生成规则

> 强制要求：修订记录脚本中每条 `metadata` 的 `external_id` **必须按本规则由 generator 自动生成填充，禁止留空 `""`、禁止手写随意值**。
> 参考来源：生产库 SQL（从 `edsm_dataset_element` / `edsm_dataset` / `edsm_dataset_category` / `edsm_data_standard` 四表按 `seq_no` 拼出）。

---

## 1. 规则公式

```
external_id = "HDS" + SS + CC + "." + DDD + "." + EEE
```

| 段 | 含义 | 来源表 | 位数 | 补零 |
|----|------|--------|------|------|
| `SS`  | 标准序号      | `edsm_data_standard.seq_no`      | 2 位 | 左补零 |
| `CC`  | 数据集分类序号 | `edsm_dataset_category.seq_no`   | 2 位 | 左补零 |
| `DDD` | 数据集序号    | `edsm_dataset.seq_no`            | 3 位 | 左补零 |
| `EEE` | 数据集元素序号 | `edsm_dataset_element.seq_no`    | 3 位 | 左补零 |

生产库原始 SQL（等价逻辑）：

```sql
insert into edsm_metadata(namespace_id, external_id, ...)
select (select namespace_id from edsm_namespace where namespace_code='winning-plat' limit 1),
       'HDS'||lpad(d.seq_no::text,2,'0')||lpad(c.seq_no::text,2,'0')||'.'||lpad(b.seq_no::text,3,'0')||'.'||lpad(a.seq_no::text,3,'0'),
       ...
from edsm_dataset_element a, edsm_dataset b, edsm_dataset_category c, edsm_data_standard d
where a.dataset_id = b.dataset_id
  and b.category_id = c.category_id
  and c.standard_id = d.standard_id;
```

---

## 2. 序号来源（base_data 初始化种子 CSV）

权威数据来自 BMS 项目 `winning-dps-rda-bms-server/src/main/resources/base_data/` 下的初始化种子 CSV：

| 序号 | 来源文件 | 关联键 | `seq_no` 所在列（0-based） |
|------|----------|--------|----------------------------|
| `SS` 标准   | `3__edsm_data_standard.csv` | `standard_id` | 第 3 列 |
| `CC` 分类   | `4__edsm_dataset_category.csv` | `category_id`（由数据集的 `category_id` 关联） | 第 6 列 |
| `DDD` 数据集 | `5__edsm_dataset.csv` | `dataset_id` | 第 7 列（注意比分类表多一列 `category_id`，`seq_no` 后移一位） |
| `EEE` 元素  | `6__edsm_dataset_element.csv` | `element_id` | 第 15 列 |

> ⚠️ 列偏移坑：`5__edsm_dataset.csv` 比 `4__edsm_dataset_category.csv` 多了一列 `category_id`（位于第 3 列），因此其 `seq_no` 在**第 7 列**而非第 6 列；`6__edsm_dataset_element.csv` 的 `seq_no` 在**第 15 列**。任何解析脚本都必须按上述列索引取值，否则数据集/元素段会算错。

---

## 3. generator 使用的数据源索引

`data-model-revision/scripts/external_id_index.json`：由上述 4 个 CSV **全量构建**，供 `revise_record_generator.py` 读取后自动计算 `external_id`。结构：

```json
{
  "rule": "HDS{lpad(standard_seq,2)}{lpad(category_seq,2)}.{lpad(dataset_seq,3)}.{lpad(element_seq,3)}",
  "standards":  { "winning-plat-01": 1, "winning-plat-02": 2, ... },
  "categories": { "winning-plat-01": { "winning-plat-01-基础目录": 1, ... }, ... },
  "datasets":   { "winning-plat-01": { "BASE_DEPARTMENT": {"seq_no": 3, "category_id": "winning-plat-01-基础目录", "max_element_seq": 17}, ... }, ... }
}
```

- **已有元素**：`EEE` 直接取其 `seq_no`。
- **新增字段**：`EEE = 该数据集的 max_element_seq + 1`（索引预存每个数据集现有最大元素序号，避免越界/重复）。
- 计算函数：`compute_external_id(standard_id, dataset_code, element_seq_no)`。

### 与 bms 项目 `base_data/edsm_index.json` 的关系

bms 项目自带 `base_data/edsm_index.json`（description 亦写"用于快速查询序号信息生成 external_id"），但经核查它**仅含 `winning-plat-02`（公共卫生）的 datasets，`winning-plat-01`（医疗服务）等缺失，不完整**。因此：

- **以本 Skill 的 `external_id_index.json` 为准**（覆盖全部 7 个 standard，含 winning-plat-01）。
- 若 bms 项目后续补全其 `edsm_index.json`，可仅作为交叉校验，不依赖它生成。

---

## 4. 生成约束（强）

- 修订记录脚本中每条 `metadata` 的 `external_id` **必须由 generator 按本规则自动计算填充，不得留空 `""`**（早期"外部标识符，无则 `""`"的写法已废止）。
- `revise_record_generator.py` 的 `generate_metadata_insert` 已默认自动计算；调用方（新增表字段、新增字段分支）**无需也不应**显式传 `external_id=''`。

---

## 5. 示例（已与 `7__edsm_metadata.csv` 权威值交叉验证）

| 元素 | 推导 | external_id |
|------|------|-------------|
| `winning-plat-02-CAD_ARCHIVE-CUR_CITY_CODE`（已有，基准） | `02` + `34`(冠心病) `.` `158` `.` `045` | `HDS0234.158.045` |
| `winning-plat-01-BASE_DEPARTMENT-STATUS`（新增） | `01` + `01`(基础目录) `.` `003` `.` `018`(17+1) | `HDS0101.003.018` |
| `winning-plat-01-BASE_EMPLOYEE-STATUS`（新增） | `01` + `01`(基础目录) `.` `001` `.` `048`(47+1) | `HDS0101.001.048` |

> 第 1 行取自 `7__edsm_metadata.csv` 真实值，证明公式与索引正确；第 2、3 行即本 Skill 修订记录脚本 `V20260813093759__insert_revise_record_234683.sql` 的 STATUS 字段应填的 `external_id`。

---

## 6. 重建索引

当 `base_data` 的 4 个 CSV 发生变更（新增标准 / 分类 / 数据集 / 元素）后，须重新构建 `external_id_index.json`，确保 `max_element_seq` 与最新序号一致。重建脚本读取上述 4 个 CSV，按第 2 节列索引取值并写出 JSON（见 `revise_record_generator.py` 同目录的索引构建逻辑 / 历史构建命令）。
