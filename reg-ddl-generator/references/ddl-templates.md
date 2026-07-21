# 数据库DDL模板

## 类型映射表

| 原始类型 | MySQL | Oracle | SQL Server | PostgreSQL |
|---------|--------|--------|------------|------------|
| VARCHAR | VARCHAR | VARCHAR2 | VARCHAR | VARCHAR |
| NUMBER | DECIMAL | NUMBER | DECIMAL | NUMERIC |
| NUMERIC | DECIMAL | NUMBER | DECIMAL | NUMERIC |
| INT | INT | NUMBER | INT | INTEGER |
| INTEGER | INT | NUMBER | INT | INTEGER |
| DATE | DATE | DATE | DATE | DATE |
| DATETIME | DATETIME | DATE | DATETIME | TIMESTAMP |
| TEXT | TEXT | CLOB | NVARCHAR(MAX) | TEXT |
| CLOB | TEXT | CLOB | NVARCHAR(MAX) | TEXT |
| BLOB | BLOB | BLOB | VARBINARY(MAX) | BYTEA |

---

## MySQL 示例

### 新增字段（幂等检查）

```sql
set @dbname = database();
set @tablename = '表名';
set @columnname = '字段名';
set @preparedStatement = (select if(
  (select count(*) from information_schema.columns
   where table_schema = @dbname and table_name = @tablename and column_name = @columnname) > 0,
  'select 1',
  concat('alter table ', @tablename, ' add column 字段名 类型 约束 comment ''注释''')
));
prepare alterIfNotExists from @preparedStatement;
execute alterIfNotExists;
deallocate prepare alterIfNotExists;
```

### 新增表（幂等检查）

```sql
set @tablename = '表名';
set @createTable = (select if(
  (select count(*) from information_schema.tables where table_schema = database() and table_name = @tablename) > 0,
  'select 1',
  concat('create table ', @tablename, ' (
    字段1 类型 约束 comment ''字段1中文'',
    字段2 类型 约束 comment ''字段2中文'',
    sczt varchar(1) default ''0'' not null comment ''创建状态'',
    primary key (主键字段1, 主键字段2)
  ) comment=''表名中文''')
));
prepare createIfNotExists from @createTable;
execute createIfNotExists;
deallocate prepare createIfNotExists;
```

---

## Oracle 示例

### 新增字段（多字段合并，含TRAN/LOG关联表同步）

**v3.4.0 规范**：
- 脚本块注释要写清楚加了哪些字段（与修订记录内容一致）
- 大小写格式应用到所有字符（SQL关键字、数据类型、表名、字段名）
- TRAN/LOG同步不加注释，只加字段
- 内容区域不加内部注释

```sql
/*
表名中文[表名]新增字段：字段名中文[字段名,VARCHAR2(50),应填]、字段名中文[字段名,VARCHAR2(100),应填]
*/

-- 表名中文[表名]新增字段：字段名中文[字段名,VARCHAR2(50),应填]、字段名中文[字段名,VARCHAR2(100),应填]
DECLARE
    V_COUNT NUMBER;
BEGIN
    SELECT COUNT(*) INTO V_COUNT FROM USER_TABLES WHERE TABLE_NAME = UPPER('表名');
    IF V_COUNT > 0 THEN
        SELECT COUNT(*) INTO V_COUNT FROM USER_TAB_COLUMNS WHERE TABLE_NAME = UPPER('表名') AND COLUMN_NAME = UPPER('字段1');
        IF V_COUNT = 0 THEN
            EXECUTE IMMEDIATE 'ALTER TABLE 表名 ADD 字段1 VARCHAR2(50) NULL';
            EXECUTE IMMEDIATE 'COMMENT ON COLUMN 表名.字段1 IS ''字段1中文''';
        END IF;
        SELECT COUNT(*) INTO V_COUNT FROM USER_TAB_COLUMNS WHERE TABLE_NAME = UPPER('表名') AND COLUMN_NAME = UPPER('字段2');
        IF V_COUNT = 0 THEN
            EXECUTE IMMEDIATE 'ALTER TABLE 表名 ADD 字段2 VARCHAR2(100) NULL';
            EXECUTE IMMEDIATE 'COMMENT ON COLUMN 表名.字段2 IS ''字段2中文''';
        END IF;
    END IF;
    SELECT COUNT(*) INTO V_COUNT FROM USER_TABLES WHERE TABLE_NAME = UPPER('表名_TRAN');
    IF V_COUNT > 0 THEN
        SELECT COUNT(*) INTO V_COUNT FROM USER_TAB_COLUMNS WHERE TABLE_NAME = UPPER('表名_TRAN') AND COLUMN_NAME = UPPER('字段1');
        IF V_COUNT = 0 THEN
            EXECUTE IMMEDIATE 'ALTER TABLE 表名_TRAN ADD 字段1 VARCHAR2(50) NULL';
        END IF;
        SELECT COUNT(*) INTO V_COUNT FROM USER_TAB_COLUMNS WHERE TABLE_NAME = UPPER('表名_TRAN') AND COLUMN_NAME = UPPER('字段2');
        IF V_COUNT = 0 THEN
            EXECUTE IMMEDIATE 'ALTER TABLE 表名_TRAN ADD 字段2 VARCHAR2(100) NULL';
        END IF;
    END IF;
    SELECT COUNT(*) INTO V_COUNT FROM USER_TABLES WHERE TABLE_NAME = UPPER('表名_LOG');
    IF V_COUNT > 0 THEN
        SELECT COUNT(*) INTO V_COUNT FROM USER_TAB_COLUMNS WHERE TABLE_NAME = UPPER('表名_LOG') AND COLUMN_NAME = UPPER('字段1');
        IF V_COUNT = 0 THEN
            EXECUTE IMMEDIATE 'ALTER TABLE 表名_LOG ADD 字段1 VARCHAR2(50) NULL';
        END IF;
        SELECT COUNT(*) INTO V_COUNT FROM USER_TAB_COLUMNS WHERE TABLE_NAME = UPPER('表名_LOG') AND COLUMN_NAME = UPPER('字段2');
        IF V_COUNT = 0 THEN
            EXECUTE IMMEDIATE 'ALTER TABLE 表名_LOG ADD 字段2 VARCHAR2(100) NULL';
        END IF;
    END IF;
END;
/
```

### 新增表（含TRAN/LOG关联表）

```sql
-- 表名中文[表名]新增表
declare
    v_count number;
begin
    select count(*) into v_count from user_tables where table_name = upper('表名');
    if v_count = 0 then
        execute immediate 'create table 表名 (
            字段1 类型 约束,
            字段2 类型 约束,
            sczt varchar2(1) default ''0'' not null,
            constraint pk_表名 primary key (主键字段1, 主键字段2)
        )';
        execute immediate 'comment on table 表名 is ''表名中文''';
        execute immediate 'comment on column 表名.字段1 is ''字段1中文''';
        execute immediate 'comment on column 表名.字段2 is ''字段2中文''';
    end if;
    select count(*) into v_count from user_tables where table_name = upper('表名_TRAN');
    if v_count = 0 then
        execute immediate 'create table 表名_TRAN (
            字段1 类型 null,
            字段2 类型 null,
            sczt varchar2(1) default ''0'' not null
        )';
    end if;
    select count(*) into v_count from user_tables where table_name = upper('表名_LOG');
    if v_count = 0 then
        execute immediate 'create table 表名_LOG (
            字段1 类型 null,
            字段2 类型 null,
            sczt varchar2(1) default ''0'' not null
        )';
    end if;
end;
/
```

### 修改字段属性

```sql
-- 表名中文[表名]字段名中文[字段名]字段约束修改为"O"，表示格式修改为"AN..100"
declare
    v_count number;
begin
    select count(*) into v_count from user_tab_columns where table_name = upper('表名') and column_name = upper('字段名');
    if v_count > 0 then
        execute immediate 'alter table 表名 modify 字段名 新类型 null';
    end if;
end;
/
```

---

## SQL Server 示例

### 新增字段（幂等检查，两层判断，含TRAN/LOG关联表同步）

**v4.2.0 规范**：
- 两层判断：先判断表是否存在，再判断字段是否存在
- 大小写格式应用到所有字符（SQL关键字、数据类型、表名、字段名）
- 同一行同一个语句不换行，保持紧凑
- 每个表（原表、TRAN、LOG）更新完后加GO分隔符
- TRAN/LOG同步不加注释，只加字段

**全大写格式示例**：
```sql
/*
表名中文[表名]新增字段：字段名中文[字段1,VARCHAR(50),应填]、字段名中文[字段2,VARCHAR(100),应填]
*/

-- 表名中文[表名]新增字段：字段名中文[字段1,VARCHAR(50),应填]、字段名中文[字段2,VARCHAR(100),应填]
IF EXISTS (SELECT * FROM SYS.TABLES WHERE NAME = '表名')
BEGIN
    IF NOT EXISTS (SELECT * FROM SYS.COLUMNS WHERE OBJECT_ID = OBJECT_ID('表名') AND NAME = '字段1')
        ALTER TABLE 表名 ADD 字段1 VARCHAR(50) NULL;
    IF NOT EXISTS (SELECT * FROM SYS.COLUMNS WHERE OBJECT_ID = OBJECT_ID('表名') AND NAME = '字段2')
        ALTER TABLE 表名 ADD 字段2 VARCHAR(100) NULL;
END
GO

IF EXISTS (SELECT * FROM SYS.TABLES WHERE NAME = '表名_TRAN')
BEGIN
    IF NOT EXISTS (SELECT * FROM SYS.COLUMNS WHERE OBJECT_ID = OBJECT_ID('表名_TRAN') AND NAME = '字段1')
        ALTER TABLE 表名_TRAN ADD 字段1 VARCHAR(50) NULL;
    IF NOT EXISTS (SELECT * FROM SYS.COLUMNS WHERE OBJECT_ID = OBJECT_ID('表名_TRAN') AND NAME = '字段2')
        ALTER TABLE 表名_TRAN ADD 字段2 VARCHAR(100) NULL;
END
GO

IF EXISTS (SELECT * FROM SYS.TABLES WHERE NAME = '表名_LOG')
BEGIN
    IF NOT EXISTS (SELECT * FROM SYS.COLUMNS WHERE OBJECT_ID = OBJECT_ID('表名_LOG') AND NAME = '字段1')
        ALTER TABLE 表名_LOG ADD 字段1 VARCHAR(50) NULL;
    IF NOT EXISTS (SELECT * FROM SYS.COLUMNS WHERE OBJECT_ID = OBJECT_ID('表名_LOG') AND NAME = '字段2')
        ALTER TABLE 表名_LOG ADD 字段2 VARCHAR(100) NULL;
END
GO
```

**全小写格式示例**：
```sql
/*
表名中文[表名]新增字段：字段名中文[字段1,varchar(50),应填]、字段名中文[字段2,varchar(100),应填]
*/

-- 表名中文[表名]新增字段：字段名中文[字段1,varchar(50),应填]、字段名中文[字段2,varchar(100),应填]
if exists (select * from sys.tables where name = '表名')
begin
    if not exists (select * from sys.columns where object_id = object_id('表名') and name = '字段1')
        alter table 表名 add 字段1 varchar(50) null;
    if not exists (select * from sys.columns where object_id = object_id('表名') and name = '字段2')
        alter table 表名 add 字段2 varchar(100) null;
end
go

if exists (select * from sys.tables where name = '表名_tran')
begin
    if not exists (select * from sys.columns where object_id = object_id('表名_tran') and name = '字段1')
        alter table 表名_tran add 字段1 varchar(50) null;
    if not exists (select * from sys.columns where object_id = object_id('表名_tran') and name = '字段2')
        alter table 表名_tran add 字段2 varchar(100) null;
end
go

if exists (select * from sys.tables where name = '表名_log')
begin
    if not exists (select * from sys.columns where object_id = object_id('表名_log') and name = '字段1')
        alter table 表名_log add 字段1 varchar(50) null;
    if not exists (select * from sys.columns where object_id = object_id('表名_log') and name = '字段2')
        alter table 表名_log add 字段2 varchar(100) null;
end
go
```

### 新增表（幂等检查）

```sql
IF NOT EXISTS (SELECT * FROM SYS.TABLES WHERE NAME = '表名')
CREATE TABLE 表名 (
    字段1 VARCHAR(50) NOT NULL,
    字段2 VARCHAR(100) NULL,
    SCZT VARCHAR(1) DEFAULT '0' NOT NULL,
    CONSTRAINT PK_表名 PRIMARY KEY (字段1)
);
GO

IF NOT EXISTS (SELECT * FROM SYS.TABLES WHERE NAME = '表名_TRAN')
CREATE TABLE 表名_TRAN (
    字段1 VARCHAR(50) NULL,
    字段2 VARCHAR(100) NULL,
    SCZT VARCHAR(1) DEFAULT '0' NOT NULL
);
GO

IF NOT EXISTS (SELECT * FROM SYS.TABLES WHERE NAME = '表名_LOG')
CREATE TABLE 表名_LOG (
    字段1 VARCHAR(50) NULL,
    字段2 VARCHAR(100) NULL,
    SCZT VARCHAR(1) DEFAULT '0' NOT NULL
);
GO
```

### 修改字段属性

```sql
IF EXISTS (SELECT * FROM SYS.TABLES WHERE NAME = '表名')
BEGIN
    IF EXISTS (SELECT * FROM SYS.COLUMNS WHERE OBJECT_ID = OBJECT_ID('表名') AND NAME = '字段名')
        ALTER TABLE 表名 ALTER COLUMN 字段名 VARCHAR(100) NULL;
END
GO
```

---

## PostgreSQL 示例

### 新增字段

```sql
do $$
begin
    if not exists (select 1 from information_schema.columns
                   where table_name = '表名' and column_name = '字段名') then
        alter table 表名 add column 字段名 类型 约束;
        comment on column 表名.字段名 is '注释';
    end if;
end $$;
```

### 新增表

```sql
do $$
begin
    if not exists (select 1 from information_schema.tables where table_name = '表名') then
        create table 表名 (
            字段1 类型 约束,
            字段2 类型 约束,
            sczt varchar(1) default '0' not null,
            constraint pk_表名 primary key (主键字段1, 主键字段2)
        );
        comment on table 表名 is '表名中文';
        comment on column 表名.字段1 is '字段1中文';
    end if;
end $$;
```