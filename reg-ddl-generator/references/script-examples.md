# DDL / DML 脚本示例集

> 本文件从 SKILL.md 外置，收录各数据库的**完整脚本示例**，供生成脚本时对照格式。
> 对应的**规则表格**仍保留在 SKILL.md 中，两者配合阅读。

## 一、DDL 注释风格示例（对应 SKILL.md《DDL注释风格规范》）

**示例（Oracle新增表）**：
```sql
-- 人员基本信息[HRP_HUMAN] - 新增表
declare
    v_count number;
begin
    select count(*) into v_count from user_tables where table_name = upper('hrp_human');
    if v_count = 0 then
        execute immediate 'create table hrp_human (
            human_id varchar2(64) not null,
            org_code varchar2(64) not null,
            org_name varchar2(70) not null,
            constraint pk_hrp_human primary key (human_id, org_code)
        )';
        execute immediate 'comment on table hrp_human is ''人员基本信息''';
        execute immediate 'comment on column hrp_human.human_id is ''人员标识''';
    end if;
end;
/
```

**示例（Oracle新增字段）**：
```sql
-- 资产基本信息[HRP_ASSET]新增字段：医疗设备功能用途代码[EQUIP_FUNC_CODE,VARCHAR(50),应填]
declare
    v_count number;
begin
    select count(*) into v_count from user_tab_columns where table_name = upper('hrp_asset') and column_name = upper('equip_func_code');
    if v_count = 0 then
        execute immediate 'alter table hrp_asset add equip_func_code varchar2(50) null';
        execute immediate 'comment on column hrp_asset.equip_func_code is ''医疗设备功能用途代码''';
    end if;
end;
/
```


---

## 二、SQL Server / Oracle 脚本示例（对应 SKILL.md《SQL Server 脚本生成规范》）

**SQL Server 新增字段示例（全大写）**：
```sql
/*
表名中文[表名]新增字段：字段名中文[字段代码,应填,VARCHAR(50)]、字段名中文[字段代码,应填,VARCHAR(100)]
*/

-- 表名中文[表名]新增字段：字段名中文[字段代码,应填,VARCHAR(50)]、字段名中文[字段代码,应填,VARCHAR(100)]
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

**SQL Server 新增字段示例（全小写）**：
```sql
/*
表名中文[表名]新增字段：字段名中文[字段代码,应填,varchar(50)]、字段名中文[字段代码,应填,varchar(100)]
*/

-- 表名中文[表名]新增字段：字段名中文[字段代码,应填,varchar(50)]、字段名中文[字段代码,应填,varchar(100)]
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

**示例格式（Oracle新增字段，全大写）**：
```sql
/*
资产基本信息[HRP_ASSET]新增字段：医疗设备功能用途代码[EQUIP_FUNC_CODE,VARCHAR2(50),应填]、医疗设备功能用途名称[EQUIP_FUNC_NAME,VARCHAR2(100),应填]
*/

-- 资产基本信息[HRP_ASSET]新增字段：医疗设备功能用途代码[EQUIP_FUNC_CODE,VARCHAR2(50),应填]、医疗设备功能用途名称[EQUIP_FUNC_NAME,VARCHAR2(100),应填]
DECLARE
    V_COUNT NUMBER;
BEGIN
    SELECT COUNT(*) INTO V_COUNT FROM USER_TABLES WHERE TABLE_NAME = UPPER('HRP_ASSET');
    IF V_COUNT > 0 THEN
        SELECT COUNT(*) INTO V_COUNT FROM USER_TAB_COLUMNS WHERE TABLE_NAME = UPPER('HRP_ASSET') AND COLUMN_NAME = UPPER('EQUIP_FUNC_CODE');
        IF V_COUNT = 0 THEN
            EXECUTE IMMEDIATE 'ALTER TABLE HRP_ASSET ADD EQUIP_FUNC_CODE VARCHAR2(50) NULL';
            EXECUTE IMMEDIATE 'COMMENT ON COLUMN HRP_ASSET.EQUIP_FUNC_CODE IS ''医疗设备功能用途代码''';
        END IF;
        SELECT COUNT(*) INTO V_COUNT FROM USER_TAB_COLUMNS WHERE TABLE_NAME = UPPER('HRP_ASSET') AND COLUMN_NAME = UPPER('EQUIP_FUNC_NAME');
        IF V_COUNT = 0 THEN
            EXECUTE IMMEDIATE 'ALTER TABLE HRP_ASSET ADD EQUIP_FUNC_NAME VARCHAR2(100) NULL';
            EXECUTE IMMEDIATE 'COMMENT ON COLUMN HRP_ASSET.EQUIP_FUNC_NAME IS ''医疗设备功能用途名称''';
        END IF;
    END IF;
    SELECT COUNT(*) INTO V_COUNT FROM USER_TABLES WHERE TABLE_NAME = UPPER('HRP_ASSET_TRAN');
    IF V_COUNT > 0 THEN
        SELECT COUNT(*) INTO V_COUNT FROM USER_TAB_COLUMNS WHERE TABLE_NAME = UPPER('HRP_ASSET_TRAN') AND COLUMN_NAME = UPPER('EQUIP_FUNC_CODE');
        IF V_COUNT = 0 THEN
            EXECUTE IMMEDIATE 'ALTER TABLE HRP_ASSET_TRAN ADD EQUIP_FUNC_CODE VARCHAR2(50) NULL';
        END IF;
        SELECT COUNT(*) INTO V_COUNT FROM USER_TAB_COLUMNS WHERE TABLE_NAME = UPPER('HRP_ASSET_TRAN') AND COLUMN_NAME = UPPER('EQUIP_FUNC_NAME');
        IF V_COUNT = 0 THEN
            EXECUTE IMMEDIATE 'ALTER TABLE HRP_ASSET_TRAN ADD EQUIP_FUNC_NAME VARCHAR2(100) NULL';
        END IF;
    END IF;
    SELECT COUNT(*) INTO V_COUNT FROM USER_TABLES WHERE TABLE_NAME = UPPER('HRP_ASSET_LOG');
    IF V_COUNT > 0 THEN
        SELECT COUNT(*) INTO V_COUNT FROM USER_TAB_COLUMNS WHERE TABLE_NAME = UPPER('HRP_ASSET_LOG') AND COLUMN_NAME = UPPER('EQUIP_FUNC_CODE');
        IF V_COUNT = 0 THEN
            EXECUTE IMMEDIATE 'ALTER TABLE HRP_ASSET_LOG ADD EQUIP_FUNC_CODE VARCHAR2(50) NULL';
        END IF;
        SELECT COUNT(*) INTO V_COUNT FROM USER_TAB_COLUMNS WHERE TABLE_NAME = UPPER('HRP_ASSET_LOG') AND COLUMN_NAME = UPPER('EQUIP_FUNC_NAME');
        IF V_COUNT = 0 THEN
            EXECUTE IMMEDIATE 'ALTER TABLE HRP_ASSET_LOG ADD EQUIP_FUNC_NAME VARCHAR2(100) NULL';
        END IF;
    END IF;
END;
/
```
