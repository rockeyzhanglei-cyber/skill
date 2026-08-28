# Doris DDL 语法差异（GP → Doris）

> 本文件从 SKILL.md 外置。转换由 `scripts/convert_doris.py` 自动处理，此表供人工核查与排错参考。
> 关联文档：`## Doris DDL生成规则`（SKILL.md 内保留核心要点与 ×4 长度规则）。

### 语法差异（GP → Doris，由转换器处理）

| Greenplum | Doris |
|-----------|-------|
| `do $$ ... end $$;` | 展开为裸 SQL（不再用存储过程 / DELIMITER 写法） |
| `ALTER TABLE ADD COLUMN IF NOT EXISTS` | 不写 if exists，直接裸 `alter table t add column c type null comment '...';` |
| `COMMENT ON COLUMN ... IS ...` | 合并进 `alter table` / `create table` 的 `comment '...'` |
| `TIMESTAMP` | `DATETIME` |
| `INTEGER` | `INT` |
| `NUMERIC(p,s)` | `DECIMAL(p,s)`（Doris 无 NUMERIC，原样透传报解析错误） |
| 无DISTRIBUTED BY | `DISTRIBUTED BY HASH(首主键列) BUCKETS 8`（**固定 8**，用户 2026-08-27 确定） |
| 无PROPERTIES | **不输出** `PROPERTIES ("replication_num" / "replication_allocation" ...)`（用户明确去除） |

**同表合并（重要）**：同一张表的多个字段变更必须合并为**单条** ALTER 语句，多子句逗号分隔、分号在末条、缩进 4 空格；Doris 不允许同一张表分多条 ALTER。

**示例（转换后）**：

```sql
-- 表名中文[表名]新增字段：字段A中文[FIELD_A,O,S1,AN..50]、字段B中文[FIELD_B,O,N,N..10,2]
alter table 表名
    add column field_a varchar(200) null comment '字段A中文',   -- 文档 AN..50 → ×4
    add column field_b decimal(10,2) null comment '字段B中文';
```

```sql
create table if not exists 表名(
    soid varchar(256) not null comment '系统编码',   -- 文档 AN..64 → ×4
    name varchar(400) null comment '名称',            -- 文档 AN..100 → ×4
    amount decimal(18,2) null comment '金额',
    create_time datetime null comment '创建时间',      -- timestamp → datetime
    remark text null comment '备注'                    -- 不限长度：text，不乘
)
unique key(soid)
comment '表名中文'
distributed by hash(soid) buckets 8;
```

**校验**：`verify_sql.py <输出.sql> --db doris`（查 numeric/timestamp 残留 + 字符串长度非 4 倍数）。
