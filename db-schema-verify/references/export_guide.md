# 表结构导出 - 傻瓜式操作指南

## 前提准备

在开始之前，确认你电脑上已经安装了数据库客户端工具：
- Oracle：PL/SQL Developer、DBeaver、Navicat 等
- SQL Server：SSMS、Azure Data Studio、DBeaver 等

---

## 使用图形工具导出CSV

### DBeaver（推荐，免费，两种数据库都支持）

1. 打开DBeaver，连接到基准库
2. 新建SQL编辑器（Ctrl+] 或 菜单 SQL Editor → New SQL Script）
3. 复制对应的导出SQL内容粘贴进去
4. 按 Ctrl+Enter 执行查询
5. 在查询结果区域，右键 → "Export Data"（导出数据）
6. 格式选择 **CSV**
7. 保存路径：桌面 `baseline_export.csv`
8. 下一步 → 勾选"包含列头"（Header） → 完成

### PL/SQL Developer（Oracle专用）

1. 打开PL/SQL Developer，连接到基准库
2. 新建SQL Window（文件 → 新建 → SQL窗口）
3. 复制Oracle导出SQL粘贴
4. 按F8执行
5. 在结果标签页，点击左上角的"导出"按钮（或右键 → Export）
6. 格式选CSV → 保存到桌面

### SSMS（SQL Server专用）

1. 打开SSMS，连接到基准库
2. 新建查询（Ctrl+N）
3. 复制SQL Server导出SQL粘贴
4. 执行查询（F5）
5. 在结果网格中全选（Ctrl+A）→ 复制（Ctrl+C）→ 粘贴到Excel → Excel另存为CSV

**注意**：SSMS"结果到文件"输出的格式不太标准，建议使用上述Excel中转方式。

---

## 导出文件说明

无论用哪种方式，导出的CSV必须包含以下16列（列名必须完全一致）：

| 列名 | 说明 | 示例 |
|------|------|------|
| OWNER | 用户/模式名 | PT_STORE |
| TABLE_NAME | 表名 | BA_SYJBK |
| COLUMN_NAME | 字段名 | SYXH |
| DATA_TYPE | 数据类型 | VARCHAR2, NUMBER, DATE |
| DATA_LENGTH | 字节长度 | 22 |
| DATA_PRECISION | 数值精度 | 10 |
| DATA_SCALE | 小数位数 | 2 |
| CHAR_LENGTH | 字符长度 | 50 |
| NULLABLE | 是否可空 | Y/N |
| DATA_DEFAULT | 默认值 | '0', SYSDATE |
| COLUMN_ID | 字段顺序号 | 1 |
| PK_FLAG | 主键标识 | Y/N |
| PK_CONSTRAINT_NAME | 主键约束名 | PK_BA_SYJBK_TT |
| PK_POSITION | 主键列位置 | 1 |
| TABLE_COMMENTS | 表注释 | 病案首页 |
| COLUMN_COMMENTS | 字段注释 | 序号 |

**⚠️ 编码要求**：CSV文件必须使用 UTF-8 编码导出。

**验证清单**：
- [ ] 所有16列都存在
- [ ] 列名拼写完全一致（区分大小写）
- [ ] PK_FLAG='Y'的列都有PK_CONSTRAINT_NAME
- [ ] PK_POSITION从1开始连续递增
- [ ] DATA_DEFAULT没有`<Long>`占位符
- [ ] 编码为UTF-8

---

## 常见问题

**Q: 导出的CSV有乱码？**
A: 检查导出时的编码设置，确保选择UTF-8编码。如果用Excel打开，可能需要指定UTF-8编码导入。

**Q: 导出的CSV里字段值包含逗号，导致列错位？**
A: 这是CSV的经典问题。用Excel打开检查一下，如果确实错位了，在DBeaver中重新导出（DBeaver会正确处理字段内逗号）。

**Q: 表太多了，导出很慢？**
A: 正常现象，表多的库可能要几分钟，耐心等。Skill生成的导出SQL已经根据表范围做了过滤，只会导出需要的表。

**Q: 为什么统一使用UTF-8编码？**
A: UTF-8是国际通用编码，兼容所有语言字符，避免跨平台乱码问题。早期版本使用GBK，但Navicat等工具导出时编码不统一，导致脚本读取失败。统一UTF-8后，所有工具都能正确处理。
