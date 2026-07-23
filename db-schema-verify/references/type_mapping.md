# 数据类型映射规则

本文档包含所有数据类型映射规则，分为三部分：
1. Word文档DataType → 数据库类型（子流程B使用）
2. 数据库间类型转换（多库比对使用）
3. 默认值转换

---

## 1. Word文档DataType → 数据库类型

### DataType映射表

| DataType | 含义 | → Oracle | → SQL Server |
|----------|------|----------|--------------|
| S1 | 字母型 | VARCHAR2 | VARCHAR |
| S2 | 数字字符型 | VARCHAR2 | VARCHAR |
| S3 | 汉字型 | VARCHAR2 | VARCHAR |
| S | 字符型 | VARCHAR2 | VARCHAR |
| N | 数值型 | NUMBER | NUMERIC |
| D | 日期型 | DATE | DATETIME |
| DT | 日期时间型 | DATE | DATETIME |

### 表示格式解析（长度/精度）

按优先级顺序匹配：

1. `AN..n` → 最大长度n的字母数字混合 → VARCHAR(n) / VARCHAR2(n)
2. `N..n` → 数字序列 → VARCHAR(n) / VARCHAR2(n)
3. `N{p,s}` → 当DataType=N时为NUMBER(p,s) / NUMERIC(p,s)
4. `N{n}` → 当DataType=S时为VARCHAR(n) / VARCHAR2(n)
5. `A{n}` → 固定长度n → VARCHAR(n) / VARCHAR2(n)
6. `[NDT]+{n}` → 数字字符串（如N1、N2、D10、DT19）→ VARCHAR(n) / VARCHAR2(n)
7. `AN..*` → 不限制长度（通配符）→ 跳过长度比较

**注意**：长度/精度字段可能为`*`或空字符串，代码中int()转换必须try/except保护

### S2类型特殊处理

S2类型（数字字符型）的表示格式可能是`N1`、`N2`（表示1位/2位数字）：
- 需匹配正则 `r'[NDT]+(\d+)'` 提取数字部分作为长度
- 示例：`N1` → 长度1，`N2` → 长度2，`D10` → 长度10

---

## 2. 数据库间类型转换

当基准库与目标库是不同类型数据库时（如Oracle→SQL Server或SQL Server→Oracle），需要做数据类型映射转换。

### Oracle → SQL Server

| Oracle类型 | SQL Server类型 | 说明 |
|-----------|---------------|------|
| VARCHAR2(n) | VARCHAR(n) | n为字符数，直接对应 |
| NVARCHAR2(n) | NVARCHAR(n) | 直接对应 |
| CHAR(n) | CHAR(n) | 直接对应 |
| NCHAR(n) | NCHAR(n) | 直接对应 |
| NUMBER(p,s) | NUMERIC(p,s) | 精度和小数位直接对应 |
| NUMBER (无精度) | NUMERIC(38,0) 或 FLOAT | 看实际用途 |
| INTEGER | INT | 直接对应 |
| DATE | DATETIME | Oracle DATE含时间，对应DATETIME |
| TIMESTAMP | DATETIME2 | 直接对应 |
| CLOB | NVARCHAR(MAX) | 大文本 |
| BLOB | VARBINARY(MAX) | 二进制大对象 |
| LONG | NVARCHAR(MAX) | 旧版大文本 |
| RAW(n) | VARBINARY(n) | 二进制 |

#### 长度转换注意

- Oracle VARCHAR2(n) → SQL Server VARCHAR(n)：字符数直接对应
- Oracle VARCHAR2(n BYTE) 需要转字符数时：字符数 = 字节数 ÷ 3（UTF-8中文3字节）
- 建议向上取整，宁大勿小

### SQL Server → Oracle

| SQL Server类型 | Oracle类型 | 说明 |
|---------------|-----------|------|
| NVARCHAR(n) | NVARCHAR2(n) | 直接对应 |
| VARCHAR(n) | VARCHAR2(n) | 直接对应字符数 |
| NCHAR(n) | NCHAR(n) | 直接对应 |
| CHAR(n) | CHAR(n) | 直接对应 |
| DECIMAL(p,s) | NUMBER(p,s) | 精度直接对应 |
| INT | NUMBER(10) | Oracle没有原生INT |
| BIGINT | NUMBER(19) | |
| SMALLINT | NUMBER(5) | |
| DATETIME | DATE | Oracle 12c+ DATE含时间 |
| DATETIME2 | TIMESTAMP | |
| NVARCHAR(MAX) | CLOB | |
| VARBINARY(MAX) | BLOB | |
| BIT | NUMBER(1) | 0/1 |

### 同类型跨版本

同类型不同版本（如Oracle 12c→19c），类型通常直接对应，无需转换。
但注意：
- Oracle 12c的VARCHAR2最大4000 BYTE，19c可能配置为32767 BYTE（需确认MAX_STRING_SIZE参数）
- SQL Server不同版本类型基本一致

---

## 3. 默认值转换

| Oracle默认值 | SQL Server默认值 | 说明 |
|-------------|-----------------|------|
| SYSDATE | GETDATE() | 当前时间 |
| SYSTIMESTAMP | SYSDATETIME() | 当前时间戳 |
| USER | SUSER_NAME() | 当前用户 |
| NULL | NULL | 直接对应 |
| '字符串' | N'字符串' | SQL Server加N前缀支持Unicode |
| 0 | 0 | 直接对应 |
| 1 | 1 | 直接对应 |

---

## 4. 类型不一致时的处理

当基准库和目标库字段类型不一致时：
1. **安全转换**（自动处理）：同族类型扩大，如 VARCHAR2(50) → VARCHAR2(100)
2. **跨族转换**（标记人工确认）：如 VARCHAR2 → NUMBER，DATE → VARCHAR2
3. **长度单位差异**（自动计算）：注意BYTE/CHAR差异，向上取整
