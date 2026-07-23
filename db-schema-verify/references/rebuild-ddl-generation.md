# 重建模式 DDL 生成指南

## 概述

重建模式（Rebuild Mode）是指完全删除目标库中的现有表结构，然后根据基准库的定义重新创建。这种方式适用于：

- 目标库结构严重不一致，修复成本过高
- 开发/测试环境需要完全重置
- 新项目初始化表结构

**⚠️ 警告**：重建模式会丢失目标库中所有现有数据！必须在执行前进行完整备份。

---

## 工作流程

### 1. 确认重建模式

在生成DDL之前，必须：
- 明确告知用户重建模式会删除所有数据
- 要求用户确认已备份或可以丢失数据
- 记录用户确认的时间戳

### 2. 读取基准库CSV

从任务目录读取基准库结构CSV文件：
```python
task_dir = Path("/path/to/task-NNN")
csv_path = task_dir / "base_schema.csv"
```

CSV文件应包含以下列：
- OWNER - Schema名称
- TABLE_NAME - 表名
- COLUMN_NAME - 列名
- DATA_TYPE - 数据类型
- DATA_LENGTH - 数据长度（字节）
- DATA_PRECISION - 数值精度
- DATA_SCALE - 小数位数
- CHAR_LENGTH - 字符长度
- NULLABLE - 是否可空（Y/N）
- DATA_DEFAULT - 默认值
- COLUMN_ID - 列顺序
- PK_FLAG - 是否主键（Y/N）
- PK_CONSTRAINT_NAME - 主键约束名
- TABLE_COMMENTS - 表注释
- COLUMN_COMMENTS - 列注释

### 3. 读取表范围

从 `table_scope.json` 读取需要重建的表列表：
```python
with open(task_dir / "table_scope.json", "r") as f:
    scope = json.load(f)
    
base_tables = scope["base_tables"]  # 原表列表
all_tables = scope["all_tables"]    # 包含_TRAN/_LOG的完整列表
```

### 4. 生成DDL脚本

按照以下顺序生成DDL：

#### 4.1 DROP语句

为每张表生成DROP语句（忽略表不存在的错误）：

```sql
-- 忽略错误地删除表
BEGIN
    EXECUTE IMMEDIATE 'DROP TABLE "OWNER"."TABLE_NAME" CASCADE CONSTRAINTS';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE != -942 THEN  -- ORA-00942: 表或视图不存在
            RAISE;
        END IF;
END;
/
```

**注意事项**：
- 使用 `CASCADE CONSTRAINTS` 删除所有相关约束
- 捕获 ORA-00942 错误，避免表不存在时脚本失败
- 其他错误应该继续抛出

#### 4.2 CREATE语句

根据CSV中的列信息生成CREATE TABLE语句：

```sql
CREATE TABLE "OWNER"."TABLE_NAME" (
    "COLUMN1" VARCHAR2(100) NOT NULL,
    "COLUMN2" NUMBER(10,2) DEFAULT 0,
    "COLUMN3" DATE,
    ...
);
```

**类型映射规则**：

| CSV DATA_TYPE | 生成语法 | 说明 |
|--------------|---------|------|
| VARCHAR2 | `VARCHAR2(char_length)` | 使用CHAR_LENGTH（字符数） |
| NVARCHAR2 | `NVARCHAR2(char_length)` | 使用CHAR_LENGTH |
| CHAR | `CHAR(char_length)` | 使用CHAR_LENGTH |
| NCHAR | `NCHAR(char_length)` | 使用CHAR_LENGTH |
| NUMBER (有精度) | `NUMBER(precision, scale)` | 使用DATA_PRECISION和DATA_SCALE |
| NUMBER (无精度) | `NUMBER` | 不指定精度 |
| DATE | `DATE` | 无参数 |
| TIMESTAMP | `TIMESTAMP` | 无参数 |
| CLOB | `CLOB` | 无参数 |
| BLOB | `BLOB` | 无参数 |
| LONG | `CLOB` | Oracle LONG已废弃，转换为CLOB |

**NULL约束**：
- `NULLABLE = 'N'` → 添加 `NOT NULL`
- `NULLABLE = 'Y'` → 不添加约束（默认可空）

**默认值**：
- `DATA_DEFAULT` 不为空 → 添加 `DEFAULT value`
- 注意转义单引号：`'value'` → `''value''`

#### 4.3 主键约束

**重要规则：只有原表有主键，衍生表（_TRAN/_LOG）不应该有主键**

如果原表有主键，在CREATE TABLE后添加：

```sql
ALTER TABLE "OWNER"."TABLE_NAME" 
ADD CONSTRAINT "CONSTRAINT_NAME" PRIMARY KEY ("COL1", "COL2", ...);
```

主键列从CSV中提取：
- 筛选 `PK_FLAG = 'Y'` 的列
- 按 `COLUMN_ID` 排序

**衍生表处理**：
- 表名以 `_TRAN` 或 `_LOG` 结尾的表是衍生表
- 即使CSV中衍生表的 `PK_FLAG = 'Y'`，也**不应该**生成主键约束
- 应该输出警告注释，提示用户CSV中存在异常的主键标记

**示例**：
```sql
-- 原表生成主键
ALTER TABLE BA_SYJBK ADD CONSTRAINT PK_BA_SYJBK PRIMARY KEY (YLJGDM, JZLSH, XGBZ);

-- 衍生表跳过主键并输出警告
-- ⚠️ 警告: 衍生表 BA_SYJBK_TRAN 在CSV中有主键标记，但衍生表不应该有主键约束，已跳过
```

#### 4.4 表注释

```sql
COMMENT ON TABLE "OWNER"."TABLE_NAME" IS '表注释内容';
```

注意：
- 注释内容中的单引号需要转义：`'` → `''`
- 如果 `TABLE_COMMENTS` 为空，跳过此语句

#### 4.5 列注释

```sql
COMMENT ON COLUMN "OWNER"."TABLE_NAME"."COLUMN_NAME" IS '列注释内容';
```

注意：
- 为每个有注释的列生成语句
- 注释内容中的单引号需要转义
- 如果 `COLUMN_COMMENTS` 为空，跳过此语句

---

## 完整DDL生成脚本模板

**注意**：此模板仅供参考。实际使用时应优先使用固化脚本：
- `scripts/generate_oracle_ddl.py` - Oracle DDL生成
- `scripts/generate_sqlserver_ddl.py` - SQL Server DDL生成

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
重建模式DDL生成脚本
用途：根据基准库CSV生成目标库的完整DDL（DROP + CREATE）
"""

import csv
import json
from pathlib import Path
from collections import defaultdict

def load_table_scope(task_dir):
    """加载表范围"""
    ```python
    import csv

    def read_csv(csv_path, encoding='utf-8'):
        """读取CSV文件"""
        with open(csv_path, 'r', encoding=encoding) as f:
            reader = csv.DictReader(f)
            return list(reader)

    # 读取基准库CSV
    rows = read_csv('baseline.csv')
```

def is_derived_table(table_name):
    """判断是否为衍生表（_TRAN/_LOG）"""
    return table_name.endswith('_TRAN') or table_name.endswith('_LOG')

def generate_drop_statement(owner, table_name):
    """生成DROP语句"""
    return f"""-- 删除表 {owner}.{table_name}（忽略不存在错误）
BEGIN
    EXECUTE IMMEDIATE 'DROP TABLE "{owner}"."{table_name}" CASCADE CONSTRAINTS';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE != -942 THEN
            RAISE;
        END IF;
END;
/
"""

def generate_create_statement(owner, table_name, columns):
    """生成CREATE语句"""
    lines = [f'CREATE TABLE "{owner}"."{table_name}" (']
    
    col_defs = []
    for col in columns:
        col_name = col["COLUMN_NAME"]
        data_type = col["DATA_TYPE"]
        nullable = col["NULLABLE"]
        data_default = col.get("DATA_DEFAULT", "")
        
        # 构建类型定义
        type_def = build_type_definition(col)
        
        # 构建列定义
        col_def = f'    "{col_name}" {type_def}'
        
        # 添加默认值（DEFAULT必须在NOT NULL之前）
        if data_default and data_default.strip():
            default_value = escape_string(data_default.strip())
            col_def += f" DEFAULT {default_value}"
        
        # 添加NOT NULL约束
        if nullable == "N":
            col_def += " NOT NULL"
        
        col_defs.append(col_def)
    
    lines.append(",\n".join(col_defs))
    lines.append(");")
    
    return "\n".join(lines)

def build_type_definition(col):
    """根据列信息构建类型定义"""
    data_type = col["DATA_TYPE"]
    char_length = col.get("CHAR_LENGTH", "")
    data_precision = col.get("DATA_PRECISION", "")
    data_scale = col.get("DATA_SCALE", "")
    
    if data_type in ("VARCHAR2", "NVARCHAR2", "CHAR", "NCHAR"):
        if char_length:
            return f"{data_type}({char_length})"
        else:
            return data_type
    elif data_type == "NUMBER":
        if data_precision and data_scale:
            return f"NUMBER({data_precision}, {data_scale})"
        elif data_precision:
            return f"NUMBER({data_precision})"
        else:
            return "NUMBER"
    elif data_type == "LONG":
        return "CLOB"  # LONG已废弃，转换为CLOB
    else:
        return data_type

def generate_primary_key(owner, table_name, pk_name, pk_columns):
    """生成主键约束"""
    if not pk_name or not pk_columns:
        return ""
    
    cols = ", ".join([f'"{col}"' for col in pk_columns])
    return f'ALTER TABLE "{owner}"."{table_name}" ADD CONSTRAINT "{pk_name}" PRIMARY KEY ({cols});'

def generate_table_comment(owner, table_name, comment):
    """生成表注释"""
    if not comment or not comment.strip():
        return ""
    
    escaped_comment = escape_string(comment)
    return f"COMMENT ON TABLE \"{owner}\".\"{table_name}\" IS '{escaped_comment}';"

def generate_column_comments(owner, table_name, columns):
    """生成列注释"""
    lines = []
    for col in columns:
        comment = col.get("COLUMN_COMMENTS", "")
        if comment and comment.strip():
            col_name = col["COLUMN_NAME"]
            escaped_comment = escape_string(comment)
            lines.append(f"COMMENT ON COLUMN \"{owner}\".\"{table_name}\".\"{col_name}\" IS '{escaped_comment}';")
    return "\n".join(lines)

def generate_rebuild_ddl(task_dir, output_file="rebuild_schema.sql"):
    """生成完整的重建DDL脚本"""
    
    # 加载配置
    scope = load_table_scope(task_dir)
    csv_path = task_dir / "base_schema.csv"
    
    # 读取CSV
    rows = read_csv(csv_path)
    
    # 按表组织数据
    tables = defaultdict(lambda: {"columns": [], "pk_columns": []})
    for row in rows:
        table_key = f"{row['OWNER']}.{row['TABLE_NAME']}"
        tables[table_key]["owner"] = row["OWNER"]
        tables[table_key]["table_name"] = row["TABLE_NAME"]
        tables[table_key]["columns"].append(row)
        
        # 收集主键列
        if row.get("PK_FLAG") == "Y":
            tables[table_key]["pk_columns"].append({
                "name": row["COLUMN_NAME"],
                "id": int(row["COLUMN_ID"])
            })
        
        # 保存表注释
        if row.get("TABLE_COMMENTS"):
            tables[table_key]["table_comment"] = row["TABLE_COMMENTS"]
    
    # 生成DDL
    ddl_lines = []
    ddl_lines.append("-- " + "=" * 60)
    ddl_lines.append("-- 重建模式DDL脚本")
    ddl_lines.append(f"-- 表数量: {len(tables)}")
    ddl_lines.append("-- ⚠️ 警告：此脚本会删除所有现有数据！")
    ddl_lines.append("-- " + "=" * 60)
    ddl_lines.append("")
    
    # 第一阶段：DROP所有表
    ddl_lines.append("-- ============================================")
    ddl_lines.append("-- 阶段1: 删除现有表")
    ddl_lines.append("-- ============================================")
    ddl_lines.append("")
    
    for table_key in sorted(tables.keys()):
        table_info = tables[table_key]
        owner = table_info["owner"]
        table_name = table_info["table_name"]
        ddl_lines.append(generate_drop_statement(owner, table_name))
    
    # 第二阶段：CREATE所有表
    ddl_lines.append("-- ============================================")
    ddl_lines.append("-- 阶段2: 创建新表")
    ddl_lines.append("-- ============================================")
    ddl_lines.append("")
    
    for table_key in sorted(tables.keys()):
        table_info = tables[table_key]
        owner = table_info["owner"]
        table_name = table_info["table_name"]
        columns = sorted(table_info["columns"], key=lambda x: int(x["COLUMN_ID"]))
        
        # CREATE TABLE
        ddl_lines.append(f"-- 创建表: {table_name}")
        ddl_lines.append(generate_create_statement(owner, table_name, columns))
        ddl_lines.append("")
        
        # 主键约束（只有原表有主键，衍生表跳过）
        is_derived = is_derived_table(table_name)
        if table_info["pk_columns"] and not is_derived:
            pk_cols = sorted(table_info["pk_columns"], key=lambda x: x["id"])
            pk_col_names = [col["name"] for col in pk_cols]
            pk_name = columns[0].get("PK_CONSTRAINT_NAME", f"PK_{table_name}")
            
            pk_stmt = generate_primary_key(owner, table_name, pk_name, pk_col_names)
            if pk_stmt:
                ddl_lines.append(pk_stmt)
                ddl_lines.append("")
        elif table_info["pk_columns"] and is_derived:
            # 衍生表有PK标记，输出警告
            ddl_lines.append(f"-- ⚠️ 警告: 衍生表 {table_name} 在CSV中有主键标记，但衍生表不应该有主键约束，已跳过")
            ddl_lines.append("")
        
        # 表注释
        table_comment = table_info.get("table_comment", "")
        comment_stmt = generate_table_comment(owner, table_name, table_comment)
        if comment_stmt:
            ddl_lines.append(comment_stmt)
            ddl_lines.append("")
        
        # 列注释
        col_comments = generate_column_comments(owner, table_name, columns)
        if col_comments:
            ddl_lines.append(col_comments)
            ddl_lines.append("")
    
    # 写入文件
    output_path = task_dir / output_file
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(ddl_lines))
    
    print(f"✅ 重建DDL脚本已生成: {output_path}")
    print(f"   表数量: {len(tables)}")
    print(f"   ⚠️  警告：执行此脚本会删除所有现有数据！")
    
    return output_path

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("用法: python rebuild_ddl_generator.py <task_dir>")
        sys.exit(1)
    
    task_dir = Path(sys.argv[1])
    generate_rebuild_ddl(task_dir)

```

---

## 关键检查点

### ✅ 必须检查的项目

1. **类型映射正确性**
   - VARCHAR2使用CHAR_LENGTH（字符数），不是DATA_LENGTH（字节数）
   - NUMBER的精度和小数位是否正确
   - LONG已转换为CLOB

2. **默认值处理**
   - 字符串默认值是否用单引号包裹
   - 单引号是否正确转义（`'` → `''`）
   - 数字默认值不需要引号
   - DEFAULT必须在NOT NULL之前

3. **NOT NULL约束**
   - NULLABLE = 'N' 的列是否正确添加了NOT NULL
   - 主键列是否自动包含NOT NULL

4. **主键约束**
   - 主键列是否按COLUMN_ID排序
   - 主键约束名称是否正确
   - **衍生表（_TRAN/_LOG）不应该有主键**

5. **衍生表主键处理**
   - 表名以 `_TRAN` 或 `_LOG` 结尾的是衍生表
   - 衍生表即使CSV中有 `PK_FLAG = 'Y'`，也不应该生成主键约束
   - 应该输出警告注释

6. **注释内容**
   - 表注释和列注释是否正确转义
   - 空注释是否被跳过

7. **表范围**
   - 是否只处理了table_scope.json中定义的表
   - _TRAN和_LOG表是否包含在内

---

## 常见陷阱

### ❌ 陷阱1：字节数 vs 字符数

**错误**：使用 `DATA_LENGTH`（字节数）定义VARCHAR2长度
```sql
-- 错误示例
CREATE TABLE t (col VARCHAR2(400));  -- 假设DATA_LENGTH=400
```

**正确**：使用 `CHAR_LENGTH`（字符数）
```sql
-- 正确示例
CREATE TABLE t (col VARCHAR2(100));  -- 假设CHAR_LENGTH=100
```

### ❌ 陷阱2：默认值未转义

**错误**：
```sql
-- 如果默认值是 'it's'
CREATE TABLE t (col VARCHAR2(100) DEFAULT 'it's');  -- 语法错误！
```

**正确**：
```sql
CREATE TABLE t (col VARCHAR2(100) DEFAULT 'it''s');  -- 正确转义
```

### ❌ 陷阱3：LONG类型未转换

**错误**：
```sql
CREATE TABLE t (col LONG);  -- LONG已废弃！
```

**正确**：
```sql
CREATE TABLE t (col CLOB);  -- 转换为CLOB
```

### ❌ 陷阱4：主键列未排序

**错误**：
```sql
-- 主键列顺序错误
ALTER TABLE t ADD CONSTRAINT pk_t PRIMARY KEY (col2, col1);
```

**正确**：
```sql
-- 按COLUMN_ID排序
ALTER TABLE t ADD CONSTRAINT pk_t PRIMARY KEY (col1, col2);
```

### ❌ 陷阱5：未处理表不存在错误

**错误**：
```sql
-- 如果表不存在，脚本会失败
DROP TABLE "OWNER"."TABLE_NAME" CASCADE CONSTRAINTS;
```

**正确**：
```sql
-- 捕获ORA-00942错误
BEGIN
    EXECUTE IMMEDIATE 'DROP TABLE "OWNER"."TABLE_NAME" CASCADE CONSTRAINTS';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE != -942 THEN
            RAISE;
        END IF;
END;
/
```

### ❌ 陷阱6：衍生表错误地添加了主键

**错误**：
```sql
-- 衍生表不应该有主键
ALTER TABLE BA_SYJBK_TRAN ADD CONSTRAINT PK_BA_SYJBK_TRAN PRIMARY KEY (YLJGDM, JZLSH);
```

**正确**：
```sql
-- 衍生表跳过主键
-- ⚠️ 警告: 衍生表 BA_SYJBK_TRAN 在CSV中有主键标记，但衍生表不应该有主键约束，已跳过
```

**原因**：
- _TRAN表是事务表，记录变更历史
- _LOG表是日志表，记录操作日志
- 这两类表的数据是追加的，不应该有唯一性约束

---

## 执行建议

### 执行前检查

1. **备份数据**
   ```bash
   # 使用expdp备份
   expdp system/password@db DIRECTORY=DATA_PUMP_DIR DUMPFILE=backup_%U.dmp \
       SCHEMAS=YOUR_SCHEMA CONTENT=ALL
   ```

2. **审查DDL脚本**
   - 检查DROP语句是否正确
   - 验证CREATE语句的语法
   - 确认主键约束和注释
   - 确认衍生表没有主键约束

3. **测试环境验证**
   - 先在测试环境执行
   - 验证表结构是否符合预期
   - 检查数据完整性约束

### 执行顺序

1. 执行DROP阶段（删除所有表）
2. 执行CREATE阶段（创建新表）
3. 验证表结构
4. 导入数据（如果需要）

### 执行后验证

```sql
-- 验证表数量
SELECT COUNT(*) FROM all_tables WHERE owner = 'YOUR_SCHEMA';

-- 验证表结构
SELECT table_name, column_name, data_type, data_length, nullable
FROM all_tab_columns
WHERE owner = 'YOUR_SCHEMA'
ORDER BY table_name, column_id;

-- 验证主键（确认衍生表没有主键）
SELECT constraint_name, table_name
FROM all_constraints
WHERE owner = 'YOUR_SCHEMA' AND constraint_type = 'P'
ORDER BY table_name;
```

---

## 参考资源

- [Oracle DDL语法文档](https://docs.oracle.com/en/database/oracle/oracle-database/19/sqlrf/CREATE-TABLE.html)
- [Oracle数据类型参考](https://docs.oracle.com/en/database/oracle/oracle-database/19/sqlrf/Data-Types.html)
- 自检脚本: `scripts/self_check.py`
- Oracle DDL生成脚本: `scripts/generate_oracle_ddl.py`
- SQL Server DDL生成脚本: `scripts/generate_sqlserver_ddl.py`
- 导出SQL模板: `scripts/export_table_structure_oracle.sql`
