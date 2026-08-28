---
name: navicat-to-jetbrains-ds
description: >
  将 Navicat 导出的 .ncx 连接文件（含加密密码）转换为 JetBrains DataGrip /
  IDEA 的 dataSources.xml。核心能力：(1) 正确解密 Navicat 12+ 的 AES 密码；
  (2) 按数据库类型映射成正确的 driver id 与 JDBC URL；  (3) 用 DataGrip 2026
  真正能识别的双文件 XML 格式生成 dataSources.xml + dataSources.local.xml，
  凭据内联进 JDBC URL 的属性/查询参数（避免 @ 被 URL 编码成 %40）。
  当用户说"把 Navicat 连接导入 DataGrip / IDEA / JetBrains"或"Navicat 密码解不出来"
  时使用。
---

# Navicat .ncx → JetBrains DataGrip dataSources.xml

## 何时使用
- 用户想把 Navicat（Premium / CC / 16 / 17）的连接迁移到 DataGrip 等 JetBrains IDE
- 用户导出 .ncx 后找不到导入入口（DataGrip 确实没有 .ncx 导入器，必须改配置文件）
- 需要从 .ncx 里解出明文数据库密码

## 前置检查
1. 确认 DataGrip 已**关闭**（否则退出时它会用内存里的空状态覆盖 dataSources.xml）。
   用 `osascript -e 'tell application "DataGrip" to quit'` 优雅退出，等几秒确认 `pgrep -x datagrip` 为空。
2. 定位目标项目的 .idea 目录：
   - 默认项目：`~/DataGripProjects/default/.idea/dataSources.xml`
   - 其他项目看 `~/Library/Application Support/JetBrains/DataGrip<ver>/options/recentProjects.xml`
     里的 `$USER_HOME$/DataGripProjects/<proj>` 映射
3. 安装依赖：`pip install pycryptodome`

## 密码解密（最关键，坑很多）

### Navicat 12+（Navicat CC / Premium 16/17，.ncx 密文通常是 16 字节倍数）
- 算法：**AES-128-CBC**
- key = `b"libcckeylibcckey"` （16 字节 ASCII）
- iv  = `b"libcciv libcciv "` （16 字节 ASCII，**末尾有一个空格**，极易漏）
- 解密后 **整段就是密码**，**没有**长度前缀字节（这是最常见坑：
  若按 Navicat 11 逻辑去读 `dec[0]` 当长度，会把首字符吃掉，例如
  `winning@sql2k8` 变 `inning@sql2k8`）
- 用 `Crypto.Util.Padding.unpad(dec, 16)` 去 PKCS7 填充后直接 `decode`

### 通用解码模板
```python
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
KEY=b"libcckeylibcckey"; IV=b"libcciv libcciv "
def decrypt(hexc):
    if not hexc: return ""
    raw=bytes.fromhex(hexc)
    if len(raw)%16!=0: return ""   # 非 AES 块
    try:
        return unpad(AES.new(KEY,AES.MODE_CBC,IV).decrypt(raw),16).decode("utf-8","replace")
    except Exception:
        return ""
```
- 若解密结果全为 `0x10`（满块 PKCS7 填充），说明 Navicat 导出时该连接密码本就为空，
  需向用户确认真实密码再填。

## driver id 映射（必须与 DataGrip 安装包内置一致，否则"未知驱动"）
通过 `DataGrip.app/Contents/plugins/DatabaseTools/lib/modules/intellij.database.dialects.*.jar`
里的 `databaseDrivers/*.xml` 的 `<driver id="...">` 确认（本机 DataGrip 2026.2 实测）：
| Navicat ConnType | driver-ref | jdbc-driver | URL 前缀 |
|---|---|---|---|
| POSTGRESQL（含 Greenplum/Kingbase/人大金仓，best-effort） | `postgresql` | `org.postgresql.Driver` | `jdbc:postgresql://` |
| ORACLE | `oracle` | `oracle.jdbc.OracleDriver` | `jdbc:oracle:thin:` |
| SQLSERVER | `sqlserver.ms` | `com.microsoft.sqlserver.jdbc.SQLServerDriver` | `jdbc:sqlserver://` |
| MYSQL（含 Doris） | `mysql.8` | `com.mysql.cj.jdbc.Driver` | `jdbc:mysql://` |

⚠️ 易错点：PostgreSQL 在本版本 id 是 `postgresql`（**不是**老资料里的 `postgres`）；
SQL Server 是 `sqlserver.ms`（**不是** `sqlserver`）；MySQL 是 `mysql.8`。
不确定时直接解压安装包核对：`find DataGrip.app -name "*.jar" | while read j; do unzip -l "$j"|grep -q postgres-drivers.xml && unzip -p "$j" databaseDrivers/postgres-drivers.xml; done`

## 生成 DataGrip 配置 —— 正确格式（最关键！）

### ⚠️ 核心坑：DataGrip 密码存哪里？
- **macOS 默认密码存储 = 系统钥匙串（Native Keychain）**。在此模式下，导入时
  `dataSources.local.xml` 里的 `<password>` 元素**被忽略**（官方文档原话：
  "XML does not include password unless provided within a JDBC URL"）。
  所以想让导入的连接带上密码，**唯一可靠方式就是把凭据内联进 JDBC URL**。
- 把密码写成独立的 `<password>` 子元素 → DataGrip 界面密码字段显示为空、连不上。
  （这一条踩过，实测：local.xml 里 `<password>wn360@60</password>` 明文写上，
  DataGrip 加载后密码字段依然是空的。）

### 凭据内联进 JDBC URL（用"属性/查询参数"形式，避免 @ 被编码）
不能用 `jdbc:...://user:password@host`（userinfo 形式）——`@` 是 host 分隔符，
密码里的 `@` 必须编码成 `%40`，DataGrip 可能把 `%40` 当字面密码导致连不上。
改用**属性/查询参数**形式，`@` 不是分隔符、保持字面：
- PostgreSQL / MySQL: `jdbc:{type}://{host}:{port}/{db}?user={u}&password={p}`
- SQL Server: `jdbc:sqlserver://{host}:{port};databaseName={db};instanceName={inst};user={u};password={p};encrypt=false;trustServerCertificate=true`
  （Navicat Host `172.17.1.202\SQL_2016` → host=`172.17.1.202` + `instanceName=SQL_2016`）
  **必须追加 `encrypt=false;trustServerCertificate=true`**：微软 JDBC 驱动默认强制加密，遇到只支持 TLS 1.0 的老 SQL Server（SQL Server 2008/2016 常见）会报
  `The server selected protocol version TLS10 is not accepted by client preferences [TLS13, TLS12]`。
  加这两个参数让驱动跳过强制 SSL/TLS 握手。
- Oracle（SID 形式）: `jdbc:oracle:thin:{u}/{p}@{host}:{port}/{sid}`（本批 Oracle 密码无 `@`，安全；
  若密码含 `@` 仍需 `%40`，含 `%` 需 `%25`）

编码规则（只编码破坏 URL 解析的字符，保留 `@ ) *` 字面）：
- PG/MySQL 密码值：`% & = #` → `%XX`（`&` 是查询分隔符，`%` 是转义符）
- SQL Server 密码值：额外编码 `;`（属性分隔符）
- 整个 `jdbc-url` 文本写 XML 时用 `xml.sax.saxutils.escape` 转义（`&`→`&amp;`）
- 例：`wn360@60` → `password=wn360@60`（字面 @）；`K%mi2c%oe5l` → `password=K%25mi2c%25oe5l`

字段名坑（写错 DataGrip 只留名字）：
- URL 子元素叫 **`<jdbc-url>`**（**不是** `<url>`）
- 用户名子元素叫 **`<user-name>`**（**不是** `<user>`）
- 驱动引用叫 **`<driver-ref>`**（**不是** `<driver>`）
- 组件名 `<component name="DataSourceManagerImpl" format="xml" multifile-model="true">`

`dataSources.local.xml` 可一并生成（同 uuid + `<user-name>` + `<password>` 明文）作为备份，
但钥匙串模式下 DataGrip 会忽略其中 `<password>`，凭据以 URL 为准；
DataGrip 首次连接成功后会把密码从 URL 接管进系统钥匙串，并把 URL 改写成干净形式。

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project version="4">
  <component name="DataSourceManagerImpl" format="xml" multifile-model="true">
    <data-source source="LOCAL" name="连接名" uuid="<uuid4>">
      <driver-ref>postgresql</driver-ref>
      <synchronize>true</synchronize>
      <jdbc-driver>org.postgresql.Driver</jdbc-driver>
      <jdbc-url>jdbc:postgresql://host:port/db?user=winning&amp;password=wn360@60</jdbc-url>
      <user-name>winning</user-name>
    </data-source>
  </component>
</project>
```

## 部署流程（避免被 DataGrip 覆盖）
1. 关闭 DataGrip（见前置检查）
2. 备份并删除旧文件：`dataSources.xml`、`dataSources.local.xml`、`dataSources/` 目录
   （在 .idea 下，属项目配置，删前 cp 到 /tmp 备份）
3. 写入正确的 `dataSources.xml`（凭据在 URL 里，字面 @）
4. 重新打开 DataGrip 验证（Database 工具窗显示全部连接；密码随 URL 被读入，字段不再为空）

## SQL Server 老服务器 TLS 1.0 问题（必做额外步骤）
连 SQL Server 2008/2012（只支持 TLS 1.0/1.1）时，DataGrip 2026 默认驱动 **13.2.1**
会在握手后抛 `java.sql.SQLWarning: TLSv1 was negotiated...`，DataGrip 把它当"已失败"显示，
但连接其实建立成功了（Ping 通、DBMS 已识别）。

两套都做，缺一不可：
1. **URL 加参数**（`encrypt=false;trustServerCertificate=true`）——跳过强制加密握手
   （见上面的 SQL Server URL 构造）
2. **降级 JDBC 驱动到 7.4.1**——彻底消除 TLSv1 警告（8.4.1 仍会告警，13.2.1 更会）。

⚠️ 关键坑：`databaseDrivers.xml` 里改 `<driver><url>` 指向本地旧 jar **不生效**
（DataGrip 仍从原 `13.2.1` 路径加载）。真正有效的是 **直接替换 jar 内容**：

```bash
JAR=~/Library/Application\ Support/JetBrains/DataGrip2026.2/jdbc-drivers/SQL\ Server/13.2.1/com/microsoft/sqlserver/mssql-jdbc/13.2.1.jre11/mssql-jdbc-13.2.1.jre11.jar
# 下载 7.4.1
curl -L -o /tmp/mssql-7.4.1.jar https://repo1.maven.org/maven2/com/microsoft/sqlserver/mssql-jdbc/7.4.1.jre8/mssql-jdbc-7.4.1.jre8.jar
# 备份原 jar → 用 7.4.1 内容覆盖同名 jar（DataGrip 以为自己用的是 13.2.1）
cp "$JAR" "${JAR}.original"
cp /tmp/mssql-7.4.1.jar "$JAR"
```
重启 DataGrip 即生效。验证：日志里不再出现 `TLSv1 was negotiated`，连接测试为绿色成功。

⚠️ 副作用：
- 此 hack 在 DataGrip 升级/重装驱动时会丢失，需重新替换
- `databaseDrivers.xml` 里那个 `<artifact version="13.2.1">` 不用动，保持原值即可
- （可选）改内置 JDK `java.security` 删 `TLSv1, TLSv1.1` 能让握手不报 protocol 错误，
  但**不能消除 13.2.1 的 TLSv1 警告**，所以降级驱动才是根本解法

## 交付后
- 首次连接 DataGrip 把密码接管进 macOS Keychain，URL 改写为干净形式
- Kingbase/人大金仓 用 postgresql driver 兼容，可能连不上，需用户手动加 kingbase 驱动
- 若密码字段仍空：99% 是密码没进 URL（误写成独立 `<password>` 字段且钥匙串模式忽略它）
- 若连不上且密码含 `@`：检查是否误用了 userinfo 形式导致 `%40`（应改属性/查询参数形式）
- 若 SQL Server 报 TLS10/TLS11 不被接受 或 "TLSv1 was negotiated" 警告：按上一节降级驱动到 7.4.1

## 多库显示（Navicat 一个连接展开所有库的效果）
DataGrip 一个数据源默认只加载 URL 指定的那一个库。要像 Navicat 那样一个节点展开全部库：
1. 数据源属性（⌘↵）→ 左侧 **Schemas** 选项卡 → 勾 **All schemas**（或手动勾库）
2. PostgreSQL/Kingbase 想最像 Navicat（一个服务器节点挂全部库）：把连接 URL 的库名改成
   `postgres` 维护库（如 `jdbc:postgresql://host:5432/postgres?...`），Schemas 里即可列出该服务器所有库
3. MySQL/Doris：库即 schema，DataGrip 默认就显示全部，无需改
4. Oracle：Schemas 选项卡勾选其他 schema
⚠️ Schemas "显示全部"是 DataGrip 连接后内部状态，无法可靠写进 dataSources.xml，需用户在 UI 点一下

## 编辑 dataSources.xml 的安全注意事项
- **绝不要用多行正则（含 `\n`）去替换/重组该 XML**：raw string 里的 `\n` 在 re 中会被当作真换行，
  一旦分组错位就会把 uuid/driver/jdbc-url 串位导致文件损坏。改用**纯子串 `str.replace()`** 最稳。
- 若改坏了：直接重新跑转换脚本 `navicat_to_datagrip.py` 生成干净文件，再施加安全的子串替换即可，
  不用手动修补（脚本是权威来源）。
- 改之前先 `cp` 备份到 /tmp；改完用 ElementTree 回读校验（uuid/driver-ref/jdbc-driver/jdbc-url 字段齐全）。
- 每次改完必须**先关 DataGrip**再写文件，否则它退出时会用内存状态覆盖你的修改。

## 密码跨重启持久化（关键经验，同日踩出）
- **症状**：部分连接密码重启电脑后消失。
- **根因**：DataGrip 默认 `KEYCHAIN`（macOS 钥匙串）模式下，用户**连上某连接**后，DataGrip 会把 URL 里的密码"迁移"进钥匙串并**清空该连接的 URL 凭据**；若钥匙串没拿到（钥匙串模式失效/重置，本机实测即此），该连接重启后密码为空。未被连过、密码仍在 URL 里的连接不受影响（所以表现为"只有连过的丢了"）。
- **修复 = 两步**：
  1. 把缺失密码的连接 URL 用**纯子串 `str.replace()`** 补回凭据（格式见上文"凭据内联进 JDBC URL"）。
  2. 创建 `~/Library/Application Support/JetBrains/DataGrip<ver>/options/security.xml`，把密码存储设为 `IN_MEMORY`（"不保存"模式），DataGrip 不再把 URL 凭据迁移走，密码一直留在 URL 里、重启不丢、且不依赖钥匙串：
  ```xml
  <?xml version="1.0" encoding="UTF-8"?>
  <application>
    <component name="PasswordSafe">
      <option name="PROVIDER" value="IN_MEMORY" />
    </component>
  </application>
  ```
- provider 枚举值（从 `intellij.platform.credentialStore*.jar` 核实）：`IN_MEMORY`(不保存) / `KEEPASS`(磁盘 .kdbx + 主密码) / `KEYCHAIN`(macOS 钥匙串,默认)。若担心 IN_MEMORY 在"连上"瞬间仍剥离 URL，可改用 `KEEPASS`（磁盘文件、重启持久，但每次启动要输一次主密码）。
- ⚠️ 必须"**所有连接 URL 都带凭据 + IN_MEMORY**"组合才稳；否则某连接被连过后又会迁移清空。

## 文件夹/分组存储位置（绝不可动）
- 用户在 Database 工具窗里建的"分组文件夹"存在 `项目/.idea/db-forest-config.xml`
  （`<component name="db-forest-configuration">`），**不是** `dataSources.xml`。
- 格式：上半部 `<order>:<depth>:<uuid>:<index> 分组名` 定义文件夹（depth=0）；
  下半部 `<order>:<parentOrder>:<uuid>` 把各连接 uuid 挂到父文件夹（parentOrder=文件夹的 order）。
- **编辑 dataSources.xml 时：绝不要删/改 db-forest-config.xml，且不要改连接的 `uuid`**
  （分组靠 uuid 关联）。只动 `jdbc-url` 属性值（纯子串替换），分组映射自动保持。
- 改连接 URL 后 DataGrip 退出重写文件时，会原样保留 db-forest-config.xml 的分组（已实测）。
