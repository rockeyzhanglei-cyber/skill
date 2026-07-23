# 基准库自检标准

## 自检维度（必须一次性完成，共8个维度）

自检脚本 `scripts/self_check.py` 一次性检查以下8个维度：

### 1. 字段缺失检查
- 原表有的字段，_TRAN/_LOG表必须都有
- 缺失字段需要生成 ADD COLUMN 语句

### 2. 数据类型检查
- VARCHAR2, NUMBER, DATE, CLOB 等类型必须一致
- 类型不一致需要生成注释掉的 MODIFY 语句供人工确认

### 3. 长度检查（字符类型）
- CHAR_LENGTH 必须一致
- _TRAN/_LOG 表长度 < 原表长度时，需要扩大
- _TRAN/_LOG 表长度 >= 原表长度时，不需要修改

### 4. 精度检查（NUMBER类型）
- DATA_PRECISION 必须一致
- 精度不足时需要扩大

### 5. 小数位检查（NUMBER类型）
- DATA_SCALE 必须一致
- 小数位不足时需要调整
- 示例：原表 NUMBER(10,2)，TRAN 表 NUMBER(10,0) → 需要修改为 NUMBER(10,2)

### 6. 可空性检查
- NULLABLE (Y/N) 必须一致
- 原表 NOT NULL → 衍生表也必须是 NOT NULL
- 原表 NULL → 衍生表 NULL 或 NOT NULL 均可（不强制修改）

### 7. 默认值检查
- DATA_DEFAULT 必须一致
- 原表有默认值 → 衍生表也必须有相同默认值
- 原表无默认值 → 衍生表有或无均可

### 8. 表存在性检查
- 原表存在但 _TRAN/_LOG 表不存在时，需要生成 CREATE TABLE 语句
- 新建表结构与原表完全一致（包括字段类型、长度、精度、小数位、可空性、默认值）
- **新建表不包含主键约束**（_TRAN/_LOG 表不需要主键）

## 自检逻辑（核心原则）

### ⚠️ 最重要：原表是标准，绝对不能修改原表！

**修复方向**：
- 只修改 _TRAN 和 _LOG 表
- 使它们与原表结构完全一致
- **绝对不能反向修改原表**

**长度比较规则**：
- 原表 VARCHAR2(22)，_TRAN VARCHAR2(64) → **不修改**（_TRAN已经更大）
- 原表 VARCHAR2(64)，_TRAN VARCHAR2(22) → **修改_TRAN到64**

**可空性修复规则**：
- 原表 NOT NULL，_TRAN NULL → **不修改**（不允许收紧约束）
- 原表 NULL，_TRAN NOT NULL → **修改_TRAN为NULL**（只能放松约束）

**默认值修复规则**：
- 原表有DEFAULT，_TRAN无DEFAULT → **添加DEFAULT**
- 原表无DEFAULT，_TRAN有DEFAULT → **不修改**（允许额外约束）

## 使用方式

```bash
python scripts/self_check.py --md <md路径> --csv <csv路径> --task-dir <任务目录> --db-type <oracle|sqlserver>
```

脚本会自动：
1. 读取表清单MD文件获取原表名列表
2. 解析CSV文件（UTF-8编码）
3. 对比原表与 _TRAN/_LOG 表的8个维度
4. 生成修复SQL脚本（保存到任务目录，带存在性判断）
5. 输出检查报告（通过/未通过 + 问题统计）

## 自检结果判断标准

### 通过条件
- 脚本输出的"自动修复"数量为0
- 所有字段类型、长度、精度、小数位、可空性、默认值完全一致

### 未通过条件
- 脚本输出的"自动修复"数量 > 0
- 存在字段缺失、类型不一致、长度不足、精度不足、小数位不足、可空性不一致、默认值不一致、表不存在等问题

### 修复脚本特性
- 每条ALTER语句带存在性判断，防止表或字段不存在时报错
- TRAN/LOG表不存在时生成CREATE TABLE（结构同原表，无主键）
- 修复脚本生成后任务结束，用户自行执行

## 修复脚本SQL语法规范

### SQL Server
- 新增字段：`IF OBJECT_ID('表名', 'U') IS NOT NULL AND COL_LENGTH('表名', '列名') IS NULL ALTER TABLE ...`
- 修改字段：`IF OBJECT_ID('表名', 'U') IS NOT NULL AND COL_LENGTH('表名', '列名') IS NOT NULL ALTER TABLE ...`
- 新建表：`IF OBJECT_ID('表名', 'U') IS NULL CREATE TABLE ...`

### Oracle
- 新增字段：`BEGIN IF EXISTS(SELECT 1 FROM user_tab_columns WHERE table_name='...' AND column_name='...') THEN NULL; ELSE EXECUTE IMMEDIATE '...'; END IF; END;`
- 修改字段：`BEGIN IF NOT EXISTS(...) THEN NULL; ELSE EXECUTE IMMEDIATE '...'; END IF; END;`
- 新建表：`BEGIN IF NOT EXISTS(SELECT 1 FROM user_tables WHERE table_name='...') THEN EXECUTE IMMEDIATE 'CREATE TABLE ...'; END IF; END;`

