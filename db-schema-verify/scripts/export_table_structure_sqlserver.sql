-- ============================================
-- 导出表结构 - SQL Server
-- 用途：导出基准库表结构为CSV
-- 适用版本：SQL Server 2012及以上
-- 注意：所有版本语法一致
-- ============================================

SELECT
    s.name AS 'OWNER',
    t.name AS 'TABLE_NAME',
    c.name AS 'COLUMN_NAME',
    tp.name AS 'DATA_TYPE',
    c.max_length AS 'DATA_LENGTH',
    c.precision AS 'DATA_PRECISION',
    c.scale AS 'DATA_SCALE',
    CASE 
        WHEN tp.name IN ('varchar', 'char', 'nvarchar', 'nchar') THEN c.max_length / (CASE WHEN tp.name IN ('nvarchar', 'nchar') THEN 2 ELSE 1 END)
        ELSE 0
    END AS 'CHAR_LENGTH',
    CASE WHEN c.is_nullable = 1 THEN 'Y' ELSE 'N' END AS 'NULLABLE',
    dc.definition AS 'DATA_DEFAULT',
    c.column_id AS 'COLUMN_ID',
    CASE WHEN ic.index_column_id IS NOT NULL THEN 'Y' ELSE 'N' END AS 'PK_FLAG',
    i.name AS 'PK_CONSTRAINT_NAME',
    ic.key_ordinal AS 'PK_POSITION',
    ep.value AS 'TABLE_COMMENTS',
    ep_col.value AS 'COLUMN_COMMENTS'
FROM sys.tables t
INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
INNER JOIN sys.columns c ON t.object_id = c.object_id
INNER JOIN sys.types tp ON c.user_type_id = tp.user_type_id
LEFT JOIN sys.default_constraints dc ON c.default_object_id = dc.object_id
LEFT JOIN sys.index_columns ic ON c.object_id = ic.object_id AND c.column_id = ic.column_id AND ic.is_included_column = 0
LEFT JOIN sys.indexes i ON ic.object_id = i.object_id AND ic.index_id = i.index_id AND i.is_primary_key = 1
LEFT JOIN sys.extended_properties ep ON ep.major_id = t.object_id AND ep.minor_id = 0 AND ep.name = 'MS_Description'
LEFT JOIN sys.extended_properties ep_col ON ep_col.major_id = t.object_id AND ep_col.minor_id = c.column_id AND ep_col.name = 'MS_Description'
WHERE s.name = SCHEMA_NAME()
    AND t.name IN (
        {TABLE_LIST}
    )
ORDER BY s.name, t.name, c.column_id;
