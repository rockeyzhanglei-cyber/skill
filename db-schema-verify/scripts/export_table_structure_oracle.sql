-- ============================================
-- 导出表结构 - Oracle (11g/12c/19c)
-- 用途：导出基准库表结构为CSV
-- 适用版本：Oracle 11g/12c/19c
-- 注意：11g/12c的DATA_DEFAULT是LONG类型，必须用PL/SQL函数处理
-- ============================================

-- 步骤1：创建提取默认值的函数（处理LONG类型）
CREATE OR REPLACE FUNCTION extract_default_value(
    p_owner VARCHAR2,
    p_table_name VARCHAR2,
    p_column_name VARCHAR2
) RETURN VARCHAR2
IS
    v_default LONG;
    v_cursor INTEGER;
    v_sql VARCHAR2(1000);
    v_result VARCHAR2(4000);
    v_len INTEGER;
    v_ret INTEGER;
BEGIN
    v_cursor := DBMS_SQL.OPEN_CURSOR;
    v_sql := 'SELECT data_default FROM all_tab_columns WHERE owner = :1 AND table_name = :2 AND column_name = :3';
    DBMS_SQL.PARSE(v_cursor, v_sql, DBMS_SQL.NATIVE);
    DBMS_SQL.BIND_VARIABLE(v_cursor, ':1', p_owner);
    DBMS_SQL.BIND_VARIABLE(v_cursor, ':2', p_table_name);
    DBMS_SQL.BIND_VARIABLE(v_cursor, ':3', p_column_name);
    DBMS_SQL.DEFINE_COLUMN_LONG(v_cursor, 1);
    
    v_ret := DBMS_SQL.EXECUTE_AND_FETCH(v_cursor);
    
    IF v_ret > 0 THEN
        DBMS_SQL.COLUMN_VALUE_LONG(v_cursor, 1, 4000, 0, v_default, v_len);
        v_result := SUBSTR(v_default, 1, 4000);
    ELSE
        v_result := NULL;
    END IF;
    
    DBMS_SQL.CLOSE_CURSOR(v_cursor);
    RETURN v_result;
EXCEPTION
    WHEN OTHERS THEN
        IF DBMS_SQL.IS_OPEN(v_cursor) THEN
            DBMS_SQL.CLOSE_CURSOR(v_cursor);
        END IF;
        RETURN NULL;
END;
/

-- 步骤2：导出表结构（需要替换表名列表）
SELECT
    atc.owner                                          AS "OWNER",
    atc.table_name                                     AS "TABLE_NAME",
    atc.column_name                                    AS "COLUMN_NAME",
    atc.data_type                                      AS "DATA_TYPE",
    atc.data_length                                    AS "DATA_LENGTH",
    atc.data_precision                                 AS "DATA_PRECISION",
    atc.data_scale                                     AS "DATA_SCALE",
    atc.char_length                                    AS "CHAR_LENGTH",
    atc.nullable                                       AS "NULLABLE",
    extract_default_value(atc.owner, atc.table_name, atc.column_name) AS "DATA_DEFAULT",
    atc.column_id                                      AS "COLUMN_ID",
    CASE WHEN pk.constraint_name IS NOT NULL THEN 'Y' ELSE 'N' END AS "PK_FLAG",
    pk.constraint_name                                 AS "PK_CONSTRAINT_NAME",
    pk.position                                        AS "PK_POSITION",
    tc.comments                                        AS "TABLE_COMMENTS",
    cc.comments                                        AS "COLUMN_COMMENTS"
FROM all_tab_columns atc
LEFT JOIN all_cons_columns pk
    ON pk.owner = atc.owner
    AND pk.table_name = atc.table_name
    AND pk.column_name = atc.column_name
    AND pk.constraint_name IN (
        SELECT ac.constraint_name
        FROM all_constraints ac
        WHERE ac.owner = pk.owner
        AND ac.table_name = pk.table_name
        AND ac.constraint_type = 'P'
    )
LEFT JOIN all_tab_comments tc
    ON tc.owner = atc.owner
    AND tc.table_name = atc.table_name
LEFT JOIN all_col_comments cc
    ON cc.owner = atc.owner
    AND cc.table_name = atc.table_name
    AND cc.column_name = atc.column_name
WHERE atc.owner = USER
    AND atc.table_name IN (
        {TABLE_LIST}
    )
ORDER BY atc.owner, atc.table_name, atc.column_id;
