# 修订记录生成器常见问题

## 问题1：Python参数顺序错误
**错误的脚本（`revise_record_generator.py` v1.3.0）** 中有3个函数的参数顺序违反Python规则：
```python
# 错误：默认参数定义在非默认参数之前
def generate_code_system_insert(revise_id, code_system_id, code_system_name, definition='', timestamp):
def generate_value_set_insert(revise_id, code_system_id, code_system_name, value_no, value_desc, description='', timestamp):
def generate_metadata_insert(revise_id, standard_id, metadata_code, metadata_name, definition,
                             data_type, representation_format, code_system_id='', allow='',
                             external_id='', timestamp):
```
**修复**：将 `timestamp` 移到默认参数前面。

## 问题2：修订记录SQL缺少edsm_revise_detail
生成脚本时需同时生成 `edsm_revise_record` 和 `edsm_revise_detail`：
- 新增分类 → `business_code='datasetCategory'`
- 新增数据集 → `business_code='dataset'`
- 新增字段 → `business_code='datasetElement'`

## 问题3：分类序号需查历史数据
新增分类的seqNo不能猜测，必须查 `4__edsm_dataset_category.csv`（在BMS base_data目录下）确认当前最大序号，再按文档顺序插入。