# SQL 脚本生成规范

## 数据库类型

auto-dev 默认生成的 SQL 脚本使用 **SQL Server (T-SQL)** 语法。

---

## 字段定义

### 添加字段
```sql
ALTER TABLE {table_name}
ADD {column_name} {datatype};
```

示例：
```sql
ALTER TABLE gcp_new_drug_prescription
ADD mix_operator VARCHAR(255);
```

### 添加字段注释
```sql
EXEC sp_addextendedproperty
    @name = N'MS_Description', @value = N'{注释内容}',
    @level0type = N'SCHEMA', @level0name = 'dbo',
    @level1type = N'TABLE', @level1name = '{table_name}',
    @level2type = N'COLUMN', @level2name = '{column_name}';
```

示例：
```sql
EXEC sp_addextendedproperty
    @name = N'MS_Description', @value = N'调配操作人账号',
    @level0type = N'SCHEMA', @level0name = 'dbo',
    @level1type = N'TABLE', @level1name = 'gcp_new_drug_prescription',
    @level2type = N'COLUMN', @level2name = 'mix_operator';
```

---

## 常用数据类型

| 说明 | SQL Server 类型 |
|------|----------------|
| 字符串(短) | VARCHAR(64/255) |
| 字符串(长) | VARCHAR(MAX) 或 TEXT |
| 整数 | INT |
| 布尔 | BIT |
| 日期时间 | DATETIME |
| 时间戳 | DATETIME |
| 金额 | DECIMAL(18,2) |

---

## 权限资源脚本

### 添加按钮权限
```sql
DECLARE @ResourceId INT;
INSERT INTO {database}.dbo.ums_resource (appid, createdate, deptype, functional, isdelete, isdisabled, issys, mainfunction, module_code, module_name, openmode, ordernum, paramlist, parentid, resource_code, resource_level, resource_name, resource_type, resource_url, ruletype, shortcutkey, updatedate)
VALUES (3300, null, null, null, 0, 0, 1, null, N'{module_code}', N'{module_name}', 0, {ordernum}, null, 0, N'{resource_code}', 5, N'{resource_name}', 2, null, null, null, null);
SET @ResourceId = SCOPE_IDENTITY();
INSERT INTO {database}.dbo.ums_role_resource (resourceid, roleid) VALUES (@ResourceId, {roleid});
```

示例：
```sql
DECLARE @mixResourceId INT;
INSERT INTO gcp.dbo.ums_resource (appid, createdate, deptype, functional, isdelete, isdisabled, issys, mainfunction, module_code, module_name, openmode, ordernum, paramlist, parentid, resource_code, resource_level, resource_name, resource_type, resource_url, ruletype, shortcutkey, updatedate)
VALUES (3300, null, null, null, 0, 0, 1, null, N'pharmacy_send_prescription_mix', N'发药流程-调配按钮', 0, 14, null, 0, N'pharmacy_send_prescription_mix', 5, N'发药流程-调配按钮', 2, null, null, null, null);
SET @mixResourceId = SCOPE_IDENTITY();
INSERT INTO gcp.dbo.ums_role_resource (resourceid, roleid) VALUES (@mixResourceId, 230);
```

---

## 回滚脚本模板

### 删除字段注释
```sql
EXEC sp_dropextendedproperty
    @name = N'MS_Description',
    @level0type = N'SCHEMA', @level0name = 'dbo',
    @level1type = N'TABLE', @level1name = '{table_name}',
    @level2type = N'COLUMN', @level2name = '{column_name}';
```

### 删除字段
```sql
ALTER TABLE {table_name} DROP COLUMN {column_name};
```

### 删除权限资源
```sql
DELETE FROM ums_resource WHERE resource_code = '{resource_code}';
```

---

## 完整 SQL 脚本模板

```sql
-- ============================================
-- {需求号} {需求标题} - 字段变更
-- ============================================

-- 1. 添加字段
ALTER TABLE {table_name}
ADD {column1} {datatype};

ALTER TABLE {table_name}
ADD {column2} {datatype};

-- 添加列注释
EXEC sp_addextendedproperty
    @name = N'MS_Description', @value = N'{column1注释}',
    @level0type = N'SCHEMA', @level0name = 'dbo',
    @level1type = N'TABLE', @level1name = '{table_name}',
    @level2type = N'COLUMN', @level2name = '{column1}';

EXEC sp_addextendedproperty
    @name = N'MS_Description', @value = N'{column2注释}',
    @level0type = N'SCHEMA', @level0name = 'dbo',
    @level1type = N'TABLE', @level1name = '{table_name}',
    @level2type = N'COLUMN', @level2name = '{column2}';

-- 2. 添加按钮权限资源
DECLARE @resourceId INT;
INSERT INTO {database}.dbo.ums_resource (appid, createdate, deptype, functional, isdelete, isdisabled, issys, mainfunction, module_code, module_name, openmode, ordernum, paramlist, parentid, resource_code, resource_level, resource_name, resource_type, resource_url, ruletype, shortcutkey, updatedate)
VALUES (3300, null, null, null, 0, 0, 1, null, N'{module_code}', N'{module_name}', 0, {ordernum}, null, 0, N'{resource_code}', 5, N'{resource_name}', 2, null, null, null, null);
SET @resourceId = SCOPE_IDENTITY();
INSERT INTO {database}.dbo.ums_role_resource (resourceid, roleid) VALUES (@resourceId, {roleid});

-- ============================================
-- 回滚脚本 (如需回滚)
-- ============================================
-- EXEC sp_dropextendedproperty ...
-- ALTER TABLE {table_name} DROP COLUMN {column1};
-- ALTER TABLE {table_name} DROP COLUMN {column2};
-- DELETE FROM ums_resource WHERE resource_code = '{resource_code}';
```

---

## 注意事项

1. **不要使用 MySQL 语法**，如 `COMMENT` 或 backtick (`` ` ``)
2. **VARCHAR 长度**：一般使用 64 或 255，避免使用过大的长度
3. **注释使用 sp_addextendedproperty**，不是 `COMMENT ON COLUMN`
4. **权限脚本使用 DECLARE + SCOPE_IDENTITY()**，确保获取正确的 ID
5. **始终包含回滚脚本**，便于出现问题时恢复