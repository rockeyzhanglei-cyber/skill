---
name: "AKSO Framework Usage Guide"
scope: project
priority: 1
---

# AKSO-Framework-Usage-Manual（工程约定）

> 适用版本：本手册以 `winning-base-project:5.5.0-SNAPSHOT` 为基线；Swagger/OpenAPI 文档能力以 **springdoc(OpenAPI 3)** 为准（不再以 springfox 为准）。

> 目的：这不是 AKSO 官方文档，也不是逐类源码说明；而是 **AKSO 在业务工程中的落地使用手册**，用于约束后续（含 AI）新增代码的写法与边界。
>
> 核心原则：**代码里出现 ≠ 合理 ≠ 推荐**。本手册会明确区分：
> - ✅ **推荐 / 标准用法**：项目已形成共识，默认遵循
> - ⚠️ **项目中存在但不推荐**：历史/特例，可继续维护但不应扩散
> - ❌ **反例（禁止 AI 学习/生成）**：会引入多租户/并发/性能/一致性风险

---

## 1. AKSO 框架识别范围（强制）

扫描源码时，凡属于以下包命名空间及其所有子包的类，统一视为 AKSO 框架组件：

- `com.winning.base.akso.**`
- `com.winning.akso.**`
- `com.winning.pts.**`

> 说明：`com.winning.pts.**`（如 `com.winning.pts.utils.*`、`com.winning.pts.exception.*`）属于 AKSO 工具链/基础设施的一部分，通常与 `com.winning.base.akso.*` 配套使用，因此同样纳入“框架组件”识别范围。
>
> AKSO 在业务工程中主要承担：**Web/RPC 上下文（BizContext/Session）、多租户上下文（TenancyContext）、异步执行与线程池（CompletableFutureBuilder/ExecutorServiceContext）、日志与链路（WinLogger/WinTracker）、通用工具（BeanMapper/RedisAbility/JPA 工具等）**。

### 1.1 手册定位（必须理解）

- 本手册是**工程约定**：强调“怎么用才安全、可维护、可审计”，不是 AKSO 官方文档。
- 本手册是**AI 生成约束**：任何“在某个项目里出现过”的写法，都必须经过本手册分级（✅/⚠️/❌）后才能作为 AI 默认输出。

---

---

## 2. 项目内 AKSO 组件使用场景概览（结论）

### 2.1 已形成的项目级统一用法（结论）

- **上下文获取**：在同步业务链路中，常用 `BizContext` / `SessionRequestContextHolder` 获取当前医院 `hospitalSOID`、登录人等信息，并封装为各模块 `SessionUtil`。
- **多租户绑定**：在 **跨线程/异步/缓存刷新** 等场景，普遍使用 `TenancyContext.getWithSoid(...)` / `TenancyContext.doWithSoid(...)` 显式绑定租户。
- **异步并发执行**：普遍用 `CompletableFutureBuilder` 作为标准异步工具，并结合 `Domain + hospitalSOID` 选择线程池与上下文传递。
- **线程池来源**：缓存/后台执行普遍从 `ExecutorServiceContext.getExecutorService(Domain.xxx.getAppName())` 获取线程池，而非直接 `Executors.*`。
- **对象转换**：绝大多数 DTO/BO/PO 转换使用 `BeanMapper`（尤其 `map` / `mapList`），在不同模块形成一致习惯。
- **JPA 查询**：`@Query(HQL/JPQL)` 与派生查询（`findBy...`）均存在；但结合工程规模，项目更偏向 **显式 HQL/JPQL**。

### 2.2 明显不合理或历史遗留用法（结论）

- **异步未显式传入 soid 的 CompletableFutureBuilder 调用**：少量代码使用 `CompletableFutureBuilder.getRpcSupplyAsync(..., Domain.XXX)` 这类 **未显式携带 soid** 的重载，存在租户上下文不确定风险（尤其在非 Web 主线程、批量/并发场景）。
- **缓存自动刷新 reload 体未强制包 TenancyContext**：存在 `submit(() -> reloadFunc.apply(key))` 这种形式，如果 `reloadFunc` 内部忘记使用 `TenancyContext.*WithSoid`，将产生隐蔽的租户串用风险。
- **过度读取 BizContext.getCurrentHospitalSOID()**：存在注释明确指出该调用可能触发 Redis，导致性能检测报大量调用；默认应避免在热点路径反复取上下文。
- **对象拷贝工具不统一**：少量模块存在 `org.springframework.beans.BeanUtils`、自建 `BeanUtils`（包装 BeanCopier/BeanUtils）、以及 MapStruct Converter；应视为 **特例/历史**，不要扩散为默认方案。

### 2.3 常见 AKSO 组件能力面（跨项目复用版）

> 说明：不同项目启用的 AKSO Starter 可能不同。本节仅给出“常见组件能力面”与使用约束；在具体工程中，应以依赖与代码扫描结果为准。

- ✅ **通用基础设施（多数项目都会用，AI 默认可生成）**
  - **Web/RPC 上下文**：`BizContext`、`SessionRequestContextHolder` 等
  - **多租户**：`TenancyContext`
  - **RPC 接口**：`WinRpcRequest` / `WinRpcQueryRequest` / `WinRpcResponse<T>`
  - **WebMVC 接口**：`WinMvcRequest` / `WinMvcQueryRequest` / `WinMvcResponse<T>`
  - **异步/线程池**：`CompletableFutureBuilder`、`ExecutorServiceContext`
  - **日志/链路**：`WinLogger`、`WinTracker`、`WinTransaction`
  - **Redis**：`RedisAbility`、`RedisBatchObject`、`RedisLocker`
  - **对象映射**：`BeanMapper`
  - **时间**：`WinningTimer`
  - **PTS 工具链**：`com.winning.pts.utils.*`、`com.winning.pts.exception.*`
- ⚠️ **子域能力（不是每个项目都需要；AI 生成需明确业务需求）**
  - **Elasticsearch**：`WinningElasticsearchTemplate`（检索/同步为主）
  - **Xxl-Job**：`@JobHandler` + AKSO 扩展 `@JobTriggerInfo`
  - **File**：`WinFileTemplate`

---


### 2.4 AKSO 组件清单与依赖引入（BOM + 坐标）（跨项目复用）

> 目的：给“新项目/新模块”一个**可复制**的依赖引入规范，而不是让每个团队成员凭记忆拼依赖。

#### 2.4.1 版本管理（强制）

- **规则 CL-1（强制）**：业务工程应在“版本 BOM/Version 模块”的 `dependencyManagement` 中 **import** `winning-akso-version`，由其统一管理 AKSO 各组件版本；业务模块只声明需要的 starter/组件，不在各模块里手写版本号。

```xml
<!-- 版本 BOM：统一 AKSO 版本 -->
<dependencyManagement>
  <dependencies>
    <dependency>
      <groupId>com.winning.base</groupId>
      <artifactId>winning-akso-version</artifactId>
      <version>${winning-akso.version}</version>
      <type>pom</type>
      <scope>import</scope>
    </dependency>
  </dependencies>
</dependencyManagement>
```

#### 2.4.2 组件按需引入（推荐）

- **规则 CL-2（推荐）**：业务模块按实际需要引入组件（starter/模块），避免“全家桶式”引入导致启动成本、自动配置冲突与治理成本上升。
- **规则 CL-3（强制）**：同一能力面（RPC、Redis、ES、File、任务等）在全工程必须保持**单一入口**：一旦选择 AKSO starter，就不得同时并行引入第三方同类 starter（除非团队明确治理方案）。

> 说明：`winning-akso-utils` 在研发口径上通常作为“工具聚合依赖”使用，其核心能力落在 `winning-akso-utils-core`；引入策略以团队统一为准，但仍建议“优先使用 AKSO/PTS 工具包，缺失才使用间接引入的第三方工具”。

#### 2.4.3 组件依赖声明明细（Maven 坐标）

> 说明：本仓库实践中，除 `akso-pbc-builder` 外，AKSO 组件通常统一为 `groupId=com.winning.base`；如果你们私服/平台对少数组件使用了不同 `groupId`，以 `winning-akso-version`（BOM）与私服坐标为准。

##### 总原则

- **规则 CL-4（强制）**：下列组件声明时 **不写 `<version>`**（交给 `winning-akso-version` 统一管理）。
- **规则 CL-5（强制）**：除 `akso-pbc-builder` 外，AKSO 组件在工程实践中通常统一为：
  - `groupId = com.winning.base`
  - `artifactId = winning-akso-...`

依赖声明模板（不写版本）：

```xml
<dependency>
  <groupId>com.winning.base</groupId>
  <artifactId><!-- 替换为下表中的 artifactId --></artifactId>
</dependency>
```

构建插件（打包）声明模板（注意：是 Maven Plugin，不走 BOM）：

```xml
<plugin>
  <groupId>com.winning.maven</groupId>
  <artifactId>akso-pbc-builder</artifactId>
  <!-- 插件版本不受 winning-akso-version 管控：以你们基础平台/私服为准 -->
</plugin>
```

##### 组件清单（逐项可复制）

- **数据源管理**：`com.winning.base:winning-akso-datasource-starter`
- **分布式唯一标识生成**：`com.winning.base:winning-akso-duid-starter`
- **JPA 持久层简化**：`com.winning.base:winning-akso-jpa-starter`
- **日志处理与管理**：`com.winning.base:winning-akso-logging-starter`
- **AKSO 服务入口**：`com.winning.base:winning-akso-server`
- **测试支持**：`com.winning.base:winning-akso-test-starter`
- **时间组件**：`com.winning.base:winning-akso-timer-starter`
- **工具类集合（含 utils-core）**：`com.winning.base:winning-akso-utils`
- **PDF 处理**：`com.winning.base:winning-akso-pdf-starter`
- **RPC 与 REST**：`com.winning.base:winning-akso-rpc-rest-starter`
- **OpenAPI/Swagger 文档生成（springdoc）**：`com.winning.base:winning-akso-swagger-starter`
- **DICOM 处理**：`com.winning.base:winning-akso-dcm-starter`
- **微服务客户端**：`com.winning.base:winning-akso-cloud-client-starter`
- **Redis 缓存**：`com.winning.base:winning-akso-redis-starter`
- **Elasticsearch 检索**：`com.winning.base:winning-akso-elasticsearch-starter`
- **缓存数据库**：`com.winning.base:winning-akso-cachedb-starter`
- **文件处理**：`com.winning.base:winning-akso-file-starter`
- **日志记录**：`com.winning.base:winning-akso-logging-record-starter`
- **微服务相关**：`com.winning.base:winning-akso-cloud-starter`
- **Freemarker 模板**：`com.winning.base:winning-akso-freemarker-starter`
- **Neo4j 图数据库**：`com.winning.base:winning-akso-neo4j-starter`
- **高可用搜索**：`com.winning.base:winning-akso-ha-search-starter`
- **Drools 规则引擎**：`com.winning.base:winning-akso-drools-starter`
- **分布式任务调度**：`com.winning.base:winning-akso-xxljob-starter`
- **应用性能管理**：`com.winning.base:winning-akso-apm-starter`
- **基于 MyBatis 的数据库操作**：`com.winning.base:winning-akso-mybatis-pbc-starter`
- **WDS 组件**：`com.winning.base:winning-akso-wds-starter`
- **FHIR 组件**：`com.winning.base:winning-akso-fhir-starter`
- **WXP 多租户 SDK**：`com.winning.base:winning-akso-wxp-tenancy-sdk`
- **MyBatis 数据库操作**：`com.winning.base:winning-akso-mybatis-starter`
- **多租户数据源 API**：`com.winning.base:winning-akso-tenancy-datasource-api`
- **AKSO PBC 打包插件（Maven Plugin）**：`com.winning.maven:akso-pbc-builder`
- **国际化**：`com.winning.base:winning-akso-i18n-starter`
- **事件处理**：`com.winning.base:winning-akso-event-starter`
- **AKSO 修复组件**：`com.winning.base:winning-akso-fix`
- **轻量级 AMQP 终端**：`com.winning.base:winning-akso-amqp-starter`
- **拼音工具**：`com.winning.base:winning-akso-pinyin`
- **五笔工具**：`com.winning.base:winning-akso-wubi`
- **worm 持久化**：`com.winning.base:winning-akso-worm-starter`
- **WebMVC 上下文（BizContext）**：`com.winning.base:winning-security-biz-webmvc` ⚠️ **重要**：Controller 中使用 `BizContext` 时必须引入此依赖

##### 常见场景依赖清单（按需引入）

> 目的：避免 AI 生成代码时遗漏必要的依赖，特别是跨模块边界的能力依赖。

- **规则 CL-6（强制）**：`*-app` 模块如果包含 Controller（使用 `@RestController`），且 Controller 中使用了 `BizContext`，**必须**引入 `winning-security-biz-webmvc` 依赖。
  - 依赖坐标：`com.winning.base:winning-security-biz-webmvc`
  - 说明：`BizContext` 类位于 `com.winning.akso.biz.webmvc.context` 包，由 `winning-security-biz-webmvc` 提供
  - 示例：
    ```xml
    <!-- 有前端web接口就需要引入winning-security-biz-webmvc -->
    <dependency>
        <groupId>com.winning.base</groupId>
        <artifactId>winning-security-biz-webmvc</artifactId>
    </dependency>
    ```
- **规则 CL-7（推荐）**：`*-app` 模块的标准依赖清单（按需引入）：
  - **基础依赖**（通常都需要）：
    - `winning-akso-server`：AKSO 服务入口
    - `winning-security-biz-webmvc`：Controller 使用 `BizContext` 时必需
  - **功能依赖**（按需引入）：
    - `winning-akso-duid-starter`：使用 DUID 生成唯一 ID
    - `winning-akso-redis-starter`：使用 Redis 缓存
    - `winning-akso-elasticsearch-starter`：使用 ES 检索
    - `winning-akso-xxljob-starter`：使用定时任务
    - `winning-akso-file-starter`：使用文件处理

---

## 3. 核心工程规则（必须写进 AI 约束）

### 3.1 多租户（TenancyContext）使用规范（项目级强制）

#### 背景

本项目为多租户架构，医院维度 `hospitalSOID` 既是业务参数也是 **租户路由关键上下文**。任何跨线程/异步执行若丢失租户上下文，会导致：

- 读写落到错误租户（数据串用）
- 缓存按错误租户构建（长期污染）
- RPC/DAO 层依赖上下文的组件行为异常（隐蔽且难排查）

#### ✅ 推荐 / 标准用法（默认遵循）

- **规则 T1（强制）**：凡是 **新线程**、**异步回调**、**缓存异步刷新**、**线程池 submit/execute**、**批量并行** 的执行体，必须在最外层显式绑定租户：
  - 有返回值用 `TenancyContext.getWithSoid(() -> {...}, hospitalSOID)`
  - 无返回值用 `TenancyContext.doWithSoid(() -> {...}, hospitalSOID)`
- **规则 T2（强制）**：业务方法链路应 **显式传递 `hospitalSOID`**（或 `Long[] soids`），并把它作为：
  - RPC 调用参数
  - DB 查询/缓存 key 的组成
  - TenancyContext 绑定的唯一来源
- **规则 T3（强制）**：当方法可能被异步/批量并发调用时，**禁止依赖“隐式上下文”**（例如只依赖 `BizContext` 的线程本地值）。

#### 事务边界与租户切换（必须理解）

- **规则 TX-1（强制）**：必须在进入事务（例如 `@Transactional`）之前完成 soid 绑定（`TenancyContext.*WithSoid` 或通过 `CompletableFutureBuilder` 带 soid 的任务入口）。
- **规则 TX-2（强制）**：当事务已经开启时，**禁止再通过 `TenancyContext` 切换/覆盖 soid**（这会导致同一事务内的数据源/租户语义不一致，风险极高）。
- **规则 TX-3（推荐）**：若业务确实需要“多租户批处理”，应采用“按 soid 分批 + 每个 soid 独立事务边界”的结构（例如外层循环逐租户调用，或在租户粒度使用 `REQUIRES_NEW` 的独立事务），而不是在同一个事务内切换 soid。

#### ⚠️ 项目中存在但不推荐（存在租户上下文风险的用法）

- **缓存刷新**：存在使用框架线程池 `submit(() -> reloadFunc.apply(key))` 的实现；虽然有注释提示“reload 必须使用 TenancyContext.getWithSoid”，但该约束依赖调用方自觉，属于高风险点。
- **入口未显式 TenancyContext**：Controller 层基本不直接出现 `TenancyContext`（更依赖 AKSO WebMVC/BizContext 统一绑定）。这是可以接受的，但 **一旦出现非标准入口**（例如绕过 AKSO 的自定义入口/工具类 main/批处理），必须显式绑定租户。

#### ❌ 反例（禁止 AI 学习或生成）

- 在 `ExecutorService.submit(...)` / `CompletableFuture.*Async(...)` / 新线程中直接访问 DB/RPC/缓存，但 **未使用 `TenancyContext.*WithSoid`**。
- 在异步线程里用 `BizContext.getCurrentHospitalSOID()` 作为租户来源（线程切换后不可靠，且可能触发额外 IO）。

#### AI 生成检查清单（必须逐条满足）

- 是否显式拿到了 `hospitalSOID`（来自入参/SessionUtil/上层传递）？
- 是否任何“线程边界”都使用了 `TenancyContext.getWithSoid/doWithSoid`？
- 是否避免在热点循环里反复读取 `BizContext.getCurrentHospitalSOID()`？

---

### 3.2 异步执行与线程池规范（项目级强制）

#### 背景

本项目大量业务调用涉及 RPC + 数据聚合，存在并发需求。与此同时多租户上下文需要在线程切换时继承/传递，因此项目形成了以 AKSO 工具为核心的统一方案。

#### ✅ 推荐 / 标准用法（默认遵循）

- **规则 A1（强制）**：异步/并发执行优先使用：
  - `com.winning.base.akso.cloud.client.util.CompletableFutureBuilder`
- **规则 A2（强制）**：`CompletableFutureBuilder` 调用必须 **显式携带 `hospitalSOID`**（优先选择带 `soid` 的重载），并明确 `Domain`：
  - `getRpcRunAsync(..., Domain.X, hospitalSOID)`
  - `getRpcSupplyAsync(..., Domain.X, hospitalSOID)`
- **规则 A3（强制）**：如果使用 `CompletableFutureBuilder` 的 **带 soid** 重载创建异步任务，框架会在任务执行时绑定 `TenancyContext`，异步体内通常**无需再重复包一层** `TenancyContext.*WithSoid`。
  - 仍需显式包租户上下文的情况包括但不限于：异步体内再次创建新线程/提交到其它线程池、使用了不带 soid 的重载、或使用了原生 `CompletableFuture/Executors` 等绕过框架的方式。
- **规则 A4（推荐）**：线程池统一从 `ExecutorServiceContext.getExecutorService(Domain.xxx.getAppName())` 获取，确保与框架初始化/监控/上下文传递机制一致。

#### 为什么要这么做（工程原因）

- 新线程需要继承租户上下文：内部依赖 `TenancyContext` 进行上下文传递与路由。
- 统一线程池与 Domain：便于隔离资源、定位问题、统一治理（超时/熔断/监控）。

#### ⚠️ 项目中存在但不推荐（建议逐步收敛）

- **未传 soid 的 CompletableFutureBuilder 重载**：项目中存在 `getRpcSupplyAsync(..., Domain.XXX)` 这类用法，不应继续增加；应改为显式传 `hospitalSOID`。
- **在工具类里兜底读取 BizContext**：例如为了减少上层改造，有的工具方法会在入参为空时读取 `BizContext.getCurrentHospitalSOID()`；这只能作为过渡兜底，不应成为默认写法（性能与线程语义都不稳定）。

#### ❌ 反例（禁止 AI 学习或生成）

- 直接使用：
  - `CompletableFuture.runAsync(...)` / `CompletableFuture.supplyAsync(...)`
  - `Executors.newFixedThreadPool(...)` 等自建线程池
  - 任何未处理租户上下文的自定义线程池/异步框架
- 在并发执行体内缺少 `TenancyContext.*WithSoid`，靠“主线程上下文”侥幸工作。

---

### 3.3 JPA 使用规范（项目经验约束）

#### 背景

项目体量很大，Repository 数量与查询方法众多。Spring Data JPA 的 **派生查询方法（findByXxxAndYyy）** 虽然开发快，但在大型工程里会带来：

- 首次调用需要代理解析与方法解析开销
- 方法数量增长会放大启动/预热成本

项目目前可能通过启动预热缓解，但这不是最佳实践。

#### ✅ 推荐 / 标准用法（默认遵循）

- **规则 J1（推荐）**：优先使用 `@Query`（HQL/JPQL）编写显式查询，尤其是：
  - 多条件组合
  - 涉及排序/聚合/分页/动态过滤
  - 性能敏感路径
- **规则 J2（推荐）**：需要动态条件时，优先使用 `JpaSpecificationExecutor` / Specification（项目中已存在该模式）。
- **规则 J3（强制）**：查询必须显式包含租户过滤条件（例如 `hospitalSOID` / soid 集合），并由上层传入，避免隐式上下文导致串租户。
- **规则 J4（强制）**：HQL/JPQL 语句中引用 Entity 时必须使用 **全包名**（Fully Qualified Class Name）。
  - 正例：`select t from com.winning.ipt.ward.item.itf.model.entity.ItemEntity t where ...`
  - 反例：`from ItemEntity t`
  - 原因：微服务工程中常存在不同模块定义了同名 Entity（如 `ConfigEntity`），只写类名会导致 Hibernate 解析歧义或报错。
- **规则 J5（强制）**：避免“循环数据库调用”（N 次往返）：当你需要查询一批 id/业务键时，必须优先使用 **批量查询**（例如 `in (:ids)`）或一次性查询后在内存组装；禁止在 `for/stream` 中逐条调用 Repository/DAO。
- **规则 J5.1（强制）**：使用 `in (:ids)` 这类批量查询时，必须限制 `ids` 长度并做分批（避免 SQL/参数数量过大）。默认单批不超过 `1000`（Oracle 存在硬限制），并将批大小抽为可配置参数。
- **规则 J6（推荐）**：当业务需要同时获取主表 + 关联表字段时，优先使用 **连表查询**（JPQL `join` / `left join`，必要时 `join fetch` 或投影 DTO）以减少往返与 N+1；但必须注意分页与重复行风险（必要时分两段查询或做去重）。

#### ⚠️ 项目中存在但不推荐（建议控制规模）

- 派生查询方法大量存在（`findBy...And...And...`），但 **AI 在生成代码时应避免“批量新增”此类方法**。
- 若确实需要派生查询：仅允许用于极少数、非常简单、稳定的查询（例如 1~2 个条件、且不会爆炸式增长）。

#### ❌ 反例（禁止 AI 学习或生成）

- 为每个组合条件新增一个 `findByAAndBAndCAndD...`，导致方法数量指数增长。
- 派生查询中隐含复杂排序/分页/动态条件，导致可读性与性能不可控。

---

### 3.4 Bean 拷贝与对象转换规范（项目级推荐）

#### 背景

项目跨模块 DTO/BO/PO 转换非常频繁，工具不统一会导致：

- 可读性下降（每个模块一个工具/一套习惯）
- 行为差异（null 处理、集合映射、覆盖策略）
- 性能与排障成本上升

#### ✅ 推荐 / 标准用法（默认遵循）

- **规则 M1（推荐）**：默认使用 `com.winning.base.akso.utils.spring.BeanMapper` 完成对象转换：
  - 单对象：`BeanMapper.map(...)`
  - 列表：`BeanMapper.mapList(...)`
- **规则 M2（推荐）**：当映射不是简单同名字段拷贝（需要聚合/拆分/格式化/枚举转换）时，使用 **显式手写映射**（清晰可控），而不是堆叠多个工具链。

#### ⚠️ 项目中存在但不推荐（历史/特例）

- `org.springframework.beans.BeanUtils.copyProperties(...)`：在部分模块/转换器中存在，视为历史或局部场景，不应默认继续使用。
- 自建 `BeanUtils`（封装 BeanCopier/BeanUtils）：在打印等模块存在，用于局部性能/兼容目的；新模块不要照搬。
- MapStruct `@Mapper`：项目中存在少量 MapStruct Converter。除非该模块已形成 MapStruct 体系并有明确收益，否则默认不引入。

#### ❌ 反例（禁止 AI 学习或生成）

- 新增一个“模块私有拷贝工具类”，并在全模块扩散使用。
- 同一业务链路里混用 BeanMapper + BeanUtils + MapStruct，导致行为不可预测。

---

### 3.4.1 分布式唯一标识（DUID）使用规范（项目级强制）

#### 背景

工程内存在“跨库/跨服务/跨实例”创建业务对象的场景，需要稳定、可治理的分布式唯一标识生成能力。若各模块自行引入 Snowflake/UUID/自研号段，会导致：

- 唯一性策略不一致（冲突风险）
- 可观测性与治理困难（号段来源、异常追踪）
- 与 AKSO 体系能力割裂（Starter、监控、兼容策略无法统一）

#### ✅ 推荐 / 标准用法（默认遵循）

- **规则 ID-1（强制）**：凡是需要“分布式唯一 ID（UID）”的新增代码，统一使用 AKSO DUID 组件（`com.winning.base:winning-akso-duid-starter`）。
- **规则 ID-2（强制）**：业务侧通过框架能力 `com.winning.base.akso.duid.DuidAbility` 获取 UID，并使用**业务维度 key**区分号段（例如 `BizKeys.ITEM`/`BizKeys.EMPLOYEE` 这类常量）。
- **规则 ID-3（推荐）**：业务常量 key 应沉淀为可复用的常量（优先放在提供方 `*-itf` 的 `model.constant` 包），避免各模块散落硬编码字符串。

#### ⚠️ 允许的例外（必须写清“为什么”）

- **例外 E1**：仅用于“短期临时、无跨系统关联”的前端展示性标识（例如页面组件临时 key），可使用 UUID；但**不得**落库作为业务主键/唯一约束字段。
- **例外 E2**：数据库自增主键（sequence/identity）属于 DB 内部策略：允许存量继续使用；但新建“跨系统业务主键/外部可见唯一标识”仍应使用 DUID。

#### ❌ 反例（禁止 AI 学习或生成）

- 在业务模块中新增或扩散以下实现来生成“分布式唯一 ID”：
  - 自研 Snowflake / IdWorker / 号段服务
  - `UUID.randomUUID()` 用作业务主键/分布式 ID
- 在多个模块内出现多套 ID 策略并存，且没有明确边界与治理说明。

---

### 3.5 Redis 使用规范（RedisAbility / RedisLocker）（项目级强制 + 推荐）

#### 背景

本项目大量缓存、暂存、同步状态、分布式锁都依赖 AKSO Redis 组件。AKSO 的 `RedisAbility` 在接口层已明确强调：

- **同一业务 key 下的值类型必须保持一致**（否则序列化/反序列化会出现不可预期结果）。

此外，多租户场景下 Redis 的“隔离”通常靠 **Key 设计** 而不是 TenancyContext，因此 Key 规范属于工程强约束。

#### ✅ 推荐 / 标准用法（默认遵循）

- **规则 R1（强制）**：任何“租户相关数据”的 Redis Key 必须包含 `hospitalSOID`（或按业务拆分在 field/value 中体现租户），避免跨租户缓存污染。
  - 推荐 Key 结构：`{appId}:{module}:{biz}:{hospitalSOID}:{id...}`（项目中已大量使用 `APP_ID:...` 前缀风格）。
- **规则 R2（强制）**：写入 Redis 时必须明确 TTL（过期时间，TTL默认单位为毫秒），除非是“明确的永久配置缓存”（且需有治理手段）。
  - 批量写入建议使用 `RedisBatchObject` + `redisAbility.multiSet(...)`（项目里用于批量同步定义态数据）。
  - **规则 R2.1（强制）**：`RedisAbility.set(K key, T value, long timeout)` 方法的 `timeout` 参数单位为**毫秒**（milliseconds），不是秒，也不接受 `TimeUnit` 参数。
    - 正确用法：`redisAbility.set(key, value, TimeUnit.HOURS.toMillis(1))` 或 `redisAbility.set(key, value, 3600000L)`（1小时=3600000毫秒）
    - 错误用法：`redisAbility.set(key, value, 1, TimeUnit.HOURS)` ❌（参数数量错误，set 方法只有3个参数）
    - 错误用法：`redisAbility.set(key, value, TimeUnit.HOURS.toSeconds(1))` ❌（单位错误，应使用 toMillis 转换为毫秒）
    - 错误用法：`redisAbility.set(key, value, TimeUnit.HOURS.toHours(1))` ❌（单位错误，应使用 toMillis 转换为毫秒）
- **规则 R3（推荐）**：优先使用 `redisAbility.get(key, Class/Type)`，避免直接处理原始字符串并散落 JSON 解析逻辑；如确需 JSON（历史存量），必须统一序列化策略并封装在 Repository/Cache 层。
- **规则 R4（推荐）**：Hash 场景优先使用 `hSet/hMSet/entries/hGet`，并确保：
  - field 命名稳定可回溯（通常是业务 id）
  - value 类型稳定（与 R1 一致）
- **规则 R5（推荐）**：批量读取优先 `multiGet`，避免循环 `get` 造成 Redis QPS 放大。

#### ✅ 分布式锁（RedisLocker）推荐用法

- **规则 RL1（强制）**：分布式锁必须使用 AKSO `RedisLocker`，禁止自研 RedLock/自写 setnx+expire。
- **规则 RL2（强制）**：必须设置合理的 `expireMs`（锁超时），并在 `finally` 解锁；锁粒度必须可审计（明确 biz + id/key）。
- **规则 RL3（推荐）**：根据业务语义选择锁模式：
  - **只允许同线程持有**：`lockByOneOnly(...)`
  - **允许同线程重入**：`lockByThread(...)`
  - **按节点**：`lockByNode(...)`

#### ⚠️ 项目中存在但不推荐（建议控制扩散）

- 在业务代码中直接 `JSONObject.parseObject`/手工 JSON（可继续维护存量，但默认优先走统一序列化/Repository 封装）。
- Key 未包含 `hospitalSOID` 但 value 是租户数据：属于隐性串租户风险点（需要治理/补偿）。

#### ❌ 反例（禁止 AI 学习或生成）

- 同一 key 下写入不同类型对象（R1 违背）。
- 写缓存不设 TTL（除非明确永久策略并有治理设计）。
- 直接用 `RedisTemplate`/`Jedis`/`Lettuce` 代替 `RedisAbility`（会绕过 AKSO 统一序列化与治理能力）。
- 自行实现分布式锁。

---

### 3.6 Elasticsearch 使用规范（WinningElasticsearchTemplate）（项目级推荐 + 约束）

#### 背景

业务工程可能存在 ES 同步与检索能力。AKSO ES 组件通过 `WinningElasticsearchTemplate` 统一封装索引/查询/更新/滚动等操作。

同时，从 AKSO 源码注释可见：

- **禁止直接使用 IndexCoordinates**（否则自定义前缀可能失效）。

#### ✅ 推荐 / 标准用法（默认遵循）

- **规则 ES1（强制）**：ES 操作统一使用 `WinningElasticsearchTemplate`，禁止直接引入原生 ES Client 做 CRUD。
- **规则 ES2（强制）**：优先使用基于实体 Class 的 API（例如 `indexOps(YourDocClass)`、`bulkIndex(queries, YourDocClass)`），避免手工拼 IndexCoordinates。
- **规则 ES3（强制）**：多租户隔离必须显式体现：
  - **索引命名隔离**（如果团队约定按租户分索引），或
  - **文档字段隔离**：Doc 必须包含 `hospitalSOID` 字段，查询/删除/更新必须带租户过滤条件。
- **规则 ES4（推荐）**：批量同步/更新使用 bulk（`bulkIndex/bulkUpdate`），大数据量读取使用 scroll（项目已有抽象封装）。

#### ⚠️ 项目中存在但不推荐（风险提示）

- “测试/运维辅助接口”包含删除索引、全量重建等高危操作：**不得对业务侧开放**，更不得让 AI 默认生成此类接口。

#### ❌ 反例（禁止 AI 学习或生成）

- 直接对外提供“任意删除索引/全量重建”的接口。
- 不带租户过滤的 ES 查询/删除（串租户风险）。
- 直接使用 `IndexCoordinates` 绕过 AKSO 的索引前缀/治理逻辑。

---

### 3.7 分布式任务（Xxl-Job + AKSO 扩展）使用规范（项目级强制）

#### 背景

业务工程可能存在定时同步任务（如同步数据到 ES、同步统计等）。在多租户架构下，定时任务本质是**独立入口**，必须显式处理租户上下文与隔离。

#### ✅ 推荐 / 标准用法（默认遵循）

- **规则 JH1（强制）**：任务入口（`@JobHandler`）必须以 **hospitalSOID 列表** 或可枚举租户作为驱动，并对每个租户：
  - `TenancyContext.doWithSoid(() -> sync(hospitalSOID), hospitalSOID)`
- **规则 JH2（强制）**：任务逻辑必须可幂等、可重试；失败必须记录可定位的租户维度日志（soid + 业务标识）。
- **规则 JH3（推荐）**：在任务上使用 AKSO 扩展注解（如 `@JobTriggerInfo`）以便运维平台采集任务元信息（本项目已有使用）。
- **规则 JH4（推荐）**：需要互斥/防重入时，使用 `RedisLocker` 做租户粒度或业务粒度锁，并保证超时与释放。

#### ❌ 反例（禁止 AI 学习或生成）

- 任务里直接依赖 `BizContext.getCurrentHospitalSOID()` 获取租户（任务线程无 Web 上下文，不可靠）。
- 一个任务在同一租户上下文里串行/并行处理多个 soid（极易串租户）。

---

### 3.8 File 组件（WinFileTemplate）（仅给出“引入门槛”：跨项目通用）

#### 结论

File 组件不是所有项目的默认依赖；必须在确认业务需求后再引入。

#### 约束（AI 生成规则）

- **规则 F1（强制）**：除非明确业务需求（文件上传/归档/打包下载等），AI 不得引入 File 组件及其依赖。
- **规则 F2（强制）**：一旦引入，必须在对象路径/桶/前缀中体现租户隔离（通常包含 `hospitalSOID`），避免跨租户文件混放。
- **规则 F3（推荐）**：优先使用 AKSO 的 `WinFileTemplate`（按 AKSO File Starter 的配置规范），不要直接引入 Minio/OSS SDK 自行封装。

---

### 3.9 接口入口规范（Controller / RPC-Feign）（项目级强制）

#### 背景

在 AKSO 体系中，**接口入口**（Controller / RPC Endpoint / Feign Provider）是最容易“漏租户上下文”的边界点。
即使项目里存在 AOP/过滤器做上下文注入，也应尽量“显式、可读、可审计”，避免把租户上下文绑定隐藏在框架黑盒里。

#### 统一约定（路径风格 + 注解）（项目级强制）

- **规则 URL-1（强制）**：接口 URL 必须使用“分段 + 小写 snake_case”风格：只允许 `a-z` / `0-9` / `_` / `/`；每个分段表达清晰语义，并且“动作/操作”放在最后一个分段（如 `query/by_example`、`set/quote_diagnosis_record/save`、`item_and_employee/save`）；禁止使用 `-`、驼峰、中文路径。

- **规则 URL-2（强制）**：接口 URL 必须由“统一常量”拼装产出，禁止在注解中手写散落字符串，避免口径漂移：
  - URL 的“项目段”必须来自**项目名**（如 `winning-demo-test-item-*` 中的 `demo-test`），并按 URL-1 风格转换为 `snake_case`（即 `demo_test`），避免硬编码。
  - WebMVC（前端调用 Controller）：统一在 `*-itf` 的 `model.constant.WebPathConstant` 定义（重点字段：`V1_BASE_CONTEXT`、`*_MODULE_PATH_PREFIX`），并且 `V1_BASE_CONTEXT` 必须包含 `/web/<project_snake>` 这一层（示例：`/api/v1/web/demo_test`）。
  - RPC/Feign（服务间接口契约）：统一在 `*-api` 的 `constant.ApiPathConstant` 定义（重点字段：`V1_BASE_CONTEXT`、`*_MODULE_PATH_PREFIX`），并且 `V1_BASE_CONTEXT` 必须使用 `/<project_snake>`（不带 `/web`，示例：`/api/v1/demo_test`）。
  - `*_MODULE_PATH_PREFIX` 必须由 `V1_BASE_CONTEXT + "/<module>"` 生成；其中 `<module>` 是模块名（如 `item`）；具体动作路径（如 `/get`、`/save`、`/item_and_employee/save`）必须拼接在该前缀下。

#### 3.9.1 RPC / Feign（`com.winning.base.akso.rpc.*`）规范

✅ 推荐 / 标准用法（AI 默认遵循）：

- **规则 IO-1（强制）**：RPC/Feign 入口的请求/响应对象命名必须统一为：
  - 请求：`*InputDTO`
  - 响应：`*OutputDTO`
  - 返回包装：`WinRpcResponse<*OutputDTO>`
  - 说明：这里的 DTO 指 **跨服务传输对象**，必须稳定、可序列化、可兼容演进。
- **规则 RPC-1（强制）**：Feign/RPC 接口方法的入参 DTO（请求类）应继承：
  - 查询类：`WinRpcQueryRequest`
  - 非查询/命令类：`WinRpcRequest`
- **规则 RPC-2（强制）**：Feign/RPC 接口方法返回值必须为 `WinRpcResponse<T>`（泛型 `T` 填具体 DTO/VO/BO）。
- **规则 RPC-2.1（强制）**：Feign/RPC 接口方法的映射注解必须使用 `@WinPostMapping`；禁止使用 Spring MVC 的 `@RequestMapping/@PostMapping/@GetMapping` 等注解，避免在 AKSO RPC 语义下产生不一致的路由与文档行为。
- **规则 RPC-3（强制）**：RPC Provider（实现类）在方法入口处必须使用 `TenancyContext.getWithSoid/doWithSoid`，并且 **soid 来源必须来自请求 DTO**：
  - `TenancyContext.getWithSoid(() -> { ... }, inputDTO.getHospitalSOID())`
- **规则 RPC-4（强制）**：RPC Consumer（调用方）在发起 Feign 调用前，必须 **显式把 hospitalSOID 写入请求 DTO**（不要依赖“下游自己猜 soid”）。
- **规则 RPC-5（推荐）**：避免“循环 RPC 调用”（N 次网络往返）：当业务需要批量聚合多条数据时，优先设计/使用 **批量 RPC**（入参携带 `List/Set`），或通过一次分页/条件查询 RPC 获取；禁止在 `for/stream` 中逐条调用远程 RPC。
- **规则 RPC-6（推荐）**：当确实需要并发扇出调用时，必须评估下游承载与超时策略，并使用 `CompletableFutureBuilder`（带 soid 的重载）进行并发聚合，同时提供超时/降级/失败分支与租户维度日志（含 soid），避免“无界并发”压垮下游。

⚠️ 项目中存在但不推荐：

- Provider 端不显式包 `TenancyContext`，仅依赖 AOP/Filter 隐式注入租户上下文：可继续维护存量，但新接口不应新增这种写法（排查困难，易串租户）。

❌ 反例（禁止 AI 学习或生成）：

- 请求 DTO 不带 `hospitalSOID`，Provider 端用 `BizContext.getCurrentHospitalSOID()` 兜底（RPC 线程语义不可靠）。
- 返回值用普通 POJO 或 `ResponseEntity` 代替 `WinRpcResponse<T>`（破坏 AKSO 统一响应语义）。

#### 3.9.2 Controller / WebMVC（`com.winning.base.akso.mvc.*`）规范

✅ 推荐 / 标准用法（AI 默认遵循）：

- **规则 MVC-0（强制）**：`*-app` 模块如果包含 Controller，且 Controller 中使用了 `BizContext`（例如 `BizContext.getCurrentHospitalSOID()`），**必须**在 `pom.xml` 中引入 `winning-security-biz-webmvc` 依赖。
  - 依赖坐标：`com.winning.base:winning-security-biz-webmvc`
  - 说明：`BizContext` 类位于 `com.winning.akso.biz.webmvc.context` 包，由 `winning-security-biz-webmvc` 提供，不是 `winning-akso-server` 提供
  - 示例 pom.xml：
    ```xml
    <!-- 有前端web接口就需要引入winning-security-biz-webmvc -->
    <dependency>
        <groupId>com.winning.base</groupId>
        <artifactId>winning-security-biz-webmvc</artifactId>
    </dependency>
    ```
- **规则 IO-2（强制）**：对前端/调用方暴露的 WebMVC Controller 请求/响应对象命名必须统一为：
  - 请求：`*InputVO`
  - 响应：`*OutputVO`
  - 返回包装：`WinMvcResponse<*OutputVO>`
  - 说明：这里的 VO 指 **对外展示/交互对象**，允许包含展示字段与聚合结构，但不应直接暴露内部 Entity。
- **规则 MVC-1（强制）**：Controller 入参 DTO（请求类）应继承：
  - 查询类：`WinMvcQueryRequest`
  - 非查询/命令类：`WinMvcRequest`
- **规则 MVC-2（强制）**：Controller 返回值必须为 `WinMvcResponse<T>`（泛型 `T` 填具体 DTO/VO/BO）。
- **规则 MVC-3（强制）**：Controller 方法入口必须显式绑定租户上下文：
  - 若该接口对外传入 soid：`TenancyContext.getWithSoid(() -> { ... }, inputDTO.getHospitalSOID())`
  - 若租户由会话/网关决定（顶层不传 soid）：`TenancyContext.getWithSoid(() -> { ... }, BizContext.getCurrentHospitalSOID())`
  - **注意**：使用 `BizContext` 时，必须确保已引入 `winning-security-biz-webmvc` 依赖（见规则 MVC-0）
- **规则 MVC-4（强制）**：Controller 的接口映射注解优先使用 `@WinPostMapping`，不要混用 Spring MVC 的 `@RequestMapping/@PostMapping/@GetMapping` 等注解，保持接口定义、网关路由与 AKSO 文档口径一致。

⚠️ 项目中存在但不推荐：

- Controller 不显式包 `TenancyContext`，依赖 AOP 初始化 Session/上下文：存量可维护，但不建议继续采用（跨项目复用时容易失效）。

❌ 反例（禁止 AI 学习或生成）：

- Controller 里在热点路径反复调用 `BizContext.getCurrentHospitalSOID()`；应先取一次存本地变量再传递。

#### 3.9.3 关于 “AOP 自动注入 soid / Session” 的约定（跨项目通用）

- **规则 AOP-1（强制）**：如果项目已存在 AOP/Filter 自动绑定 soid/Session，新增接口仍建议显式包 `TenancyContext`；但必须确认不会产生“重复绑定导致的上下文覆盖/嵌套错误”。
- **规则 AOP-2（推荐）**：团队应在项目级做出二选一的统一决策：
  - **显式绑定优先**：每个入口方法显式 `TenancyContext.*WithSoid`（可读、可审计，适合 AI 生成）
  - **AOP 绑定优先**：入口不写 `TenancyContext`，由统一 AOP 处理（需强约束与完善测试，AI 默认不推荐）

#### 3.9.4 命名与分层补充约束（强化规则，避免 DTO/VO 混用）

- **规则 IO-3（强制）**：DTO/VO 只用于接口边界（RPC/Controller）。业务内部流转对象建议用 `*BO`（或领域对象），持久化对象用 `*Entity`；禁止在 Controller/RPC 之间直接透传 Entity。
- **规则 IO-4（强制）**：同一业务能力的“入参对象”必须只有一个命名标准：RPC 统一 `InputDTO`，Web 统一 `InputVO`；禁止出现 `RequestDTO/ReqDTO/ParamDTO` 等多套命名并存。
- **规则 IO-5（强制）**：第三方/外部系统解耦接口与其配套类统一使用 `ExternalXxx...` 前缀命名（接口、DTO、必要的模型等）。
- **规则 IO-6（强制）**：内部跨模块解耦接口统一使用 `InternalXxx...` 前缀命名；接口如需使用模型类，直接复用 `*-itf` 的 `model` 包即可，不额外复制一套 `Internal*` 模型。
- **规则 IO-7（强制）**：跨层/跨模块复用的“业务常量”统一放到提供方 `*-itf` 的 `model.constant` 包（例如 `RedisKeys`、`BizKeys`、`DocConstant`、`WebPathConstant` 等），由 app/web/dao 直接复用；禁止在 `*-app`/`*-dao` 再复制一套同名常量导致口径漂移。
- **规则 IO-8（强制）**：对外 RPC/Feign 的路径常量（如 `ApiPathConstant`）必须只定义在 `*-api` 模块，作为接口契约的一部分；Provider/Consumer 一律引用该常量，禁止在 `*-app`/`*-itf` 自建重复路径常量。
- **规则 IO-8.1（强制）**：模块依赖边界：允许 `*-app` 跨模块复用别人的 `*-itf` 模型/常量（用于内部调用解耦）；`*-itf` 必须保持解耦，禁止依赖 `*-api`。
- **规则 IO-9（强制）**：接口模型（DTO/VO/Entity/Doc）字段尽量复用原有类，避免同字段多份重复定义。
  - **复用优先**：类字段相似且能满足当前接口诉求时，优先复用现有类，不再新建“同义 DTO/PO/VO”。
  - **映射取舍**：可使用 `BeanMapper` 做拷贝，但应优先减少热点链路上的反射式转换。
  - **收敛输出**：当 Entity/Doc 含敏感字段或冗余字段时，仍应新建/使用 DTO/VO 做对外收敛。

#### 3.9.5 soid/hospitalSOID 传递策略速查（仅“特殊场景”需要写明）

> 默认情况不需要额外写 `soidPolicy`：直接遵循本节的入口规则（MVC-3 / RPC-3 / RPC-4）即可。
> 只有在以下场景建议写一段“soid 传递策略说明”（用于设计/PR/联调文档）：**非标准入口**、**跨系统共享/多语言接入**、**接口允许显式切租户**、**任务/批处理入口**。

- **模板 1：标准 WebMVC（不在 Body 传 soid）**
  - 入口：WebMVC Controller
  - soid 来源：`BizContext.getCurrentHospitalSOID()`
  - 向下传递：Service/Repository 入参显式携带 `hospitalSOID`；调用 RPC 时写入 `InputDTO.hospitalSOID`
  - 异步边界：使用 `CompletableFutureBuilder` **带 soid** 的重载；异步体内通常无需重复包 `TenancyContext`（除非再次产生线程边界）
- **模板 2：WebMVC（显式传 soid，例如管理端切租户）**
  - 入口：WebMVC Controller
  - soid 来源：`InputVO.getHospitalSOID()`
  - 向下传递：全链路显式传 `hospitalSOID`；下游 RPC 继续写入 `InputDTO.hospitalSOID`
- **模板 3：RPC/Feign（跨服务调用）**
  - 入口：RPC Provider
  - soid 来源：`InputDTO.getHospitalSOID()`
  - 向下传递：服务内方法入参显式传 `hospitalSOID`；下游 RPC 继续写入下游 `InputDTO.hospitalSOID`
- **模板 4：任务入口（Xxl-Job/批处理/调度）**
  - 入口：任务线程
  - soid 来源：可枚举租户列表（配置/DB/远程配置），for each soid
  - 执行：每个租户执行体在入口绑定 soid（并发时仍用 `CompletableFutureBuilder` 带 soid）

#### 3.9.6 DTO/VO 字段注解规范（项目级强制）

为了保证接口文档的完整性与入参校验的安全性，所有对外（Controller/RPC）的 DTO/VO 必须遵循以下注解规范。

- **规则 AN-1（OpenAPI 强制）**：所有 DTO/VO 的字段必须使用 `io.swagger.v3.oas.annotations.media.Schema`（`@Schema`）注解，明确说明字段含义。
  - 示例：`@Schema(description = "员工姓名")`
- **规则 AN-2（Validation 强制）**：所有 **必填** 或 **有格式要求** 的入参字段，必须使用 `jakarta.validation.constraints.*` 注解进行校验。
  - 必填：`@NotNull` (对象/数字), `@NotBlank` (字符串), `@NotEmpty` (集合)
  - 示例：`@NotBlank(message = "姓名不能为空")`
- **规则 AN-3（推荐）**：校验注解应包含明确的 `message` 提示，以便前端/调用方快速定位问题。

- **规则 AN-3.1（推荐）**：Controller/RPC 的方法级文档信息使用 OpenAPI 3 注解（例如 `io.swagger.v3.oas.annotations.Operation`），在类上使用 `io.swagger.v3.oas.annotations.tags.Tag` 做分组。

- **规则 AN-4（禁止）**：禁止新增 `springfox` 体系的注解/配置（例如 `@ApiModelProperty`、`@EnableSwagger2`、`Docket`），避免在同一工程内形成两套 Swagger 体系。

#### 3.9.6.1 DTO/VO 类方法规范（项目级强制）

为了保证日志调试、对象比较和集合操作的正确性，所有 DTO/VO 类必须遵循以下规范：

- **规则 DTO-1（强制）**：所有 DTO/VO 类必须手动实现 `toString()` 方法，便于日志调试和问题排查。
  - 正例：手动实现 toString 方法，返回关键字段信息
  - 反例：DTO 类没有任何 toString 实现，日志打印时只能看到对象地址
- **规则 DTO-2（强制）**：所有 DTO/VO 类必须手动实现 `equals()` 和 `hashCode()` 方法，确保在集合操作（如 Set、Map）中行为正确。
  - 正例：基于业务主键字段实现 equals 和 hashCode
  - 反例：将 DTO 放入 Set 或作为 Map 的 key 时，无法正确去重或查找
- **规则 DTO-3（推荐）**：`toString()` 方法应包含所有业务关键字段，格式建议：
  ```java
  @Override
  public String toString() {
      return "XxxInputDTO{" +
              "field1='" + field1 + '\'' +
              ", field2=" + field2 +
              '}';
  }
  ```
- **规则 DTO-4（推荐）**：当 DTO 包含敏感字段（如密码、token、身份证号）时，应在 `toString()` 中排除或脱敏该字段，避免敏感信息泄露到日志：
  ```java
  @Override
  public String toString() {
      return "UserInputDTO{" +
              "username='" + username + '\'' +
              ", password='******'" +  // 脱敏处理
              '}';
  }
  ```
- **规则 DTO-5（强制）**：**禁止使用 Lombok 注解**（如 `@ToString`、`@EqualsAndHashCode`、`@Data`、`@Getter`、`@Setter` 等），必须手动实现 getter/setter 和 toString/equals/hashCode 方法。
  - 原因：Lombok 注解会带来编译依赖、IDE 兼容性、代码可读性和调试等问题

**标准 DTO 模板**：
```java
@Schema(description = "用户查询输入DTO")
public class UserQueryInputDTO extends WinRpcRequest {

    @Schema(description = "用户ID")
    @NotBlank(message = "用户ID不能为空")
    private String userId;

    @Schema(description = "用户名")
    private String username;

    // Getter
    public String getUserId() {
        return userId;
    }

    // Setter
    public void setUserId(String userId) {
        this.userId = userId;
    }

    public String getUsername() {
        return username;
    }

    public void setUsername(String username) {
        this.username = username;
    }

    @Override
    public String toString() {
        return "UserQueryInputDTO{" +
                "userId='" + userId + '\'' +
                ", username='" + username + '\'' +
                '}';
    }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (o == null || getClass() != o.getClass()) return false;
        UserQueryInputDTO that = (UserQueryInputDTO) o;
        return Objects.equals(userId, that.userId) &&
                Objects.equals(username, that.username);
    }

    @Override
    public int hashCode() {
        return Objects.hash(userId, username);
    }
}
```

**检查清单（AI 生成 DTO/VO 时必须逐条满足）**：
- [ ] DTO/VO 类是否手动实现了 toString 方法
- [ ] DTO/VO 类是否手动实现了 equals 和 hashCode 方法
- [ ] 是否**没有使用** Lombok 注解（@Data、@Getter、@Setter、@ToString、@EqualsAndHashCode 等）
- [ ] 敏感字段是否在 toString 中排除或脱敏
- [ ] 新增/修改字段时，是否同步更新了 toString、equals 和 hashCode 方法

---

### 3.9.7 分页与基础响应结构规范（补充约定）

#### 1. 查询请求基类结构（WinBaseQueryRequest）

所有分页查询请求（RPC/WebMVC）均继承自 `WinBaseQueryRequest`，其核心字段约定如下：

- **继承关系**：
  - RPC：`*InputDTO` extends `WinRpcQueryRequest` extends `WinBaseQueryRequest`
  - WebMVC：`*InputVO` extends `WinMvcQueryRequest` extends `WinBaseQueryRequest`
- **核心字段**：
  - `pageNo`：当前页码，**从 0 开始**，默认值为 `0`。
  - `pageSize`：每页大小，默认值为 `100`。
  - `pageType` / `queryPageType`：控制是否分页。
    - `P` / `Pagination`：分页（默认）。
    - `A` / `All`：不分页（全量返回，慎用）。
  - `queryNullCols`：传入需要查询 null 值的属性数组。
- **规则 PAGE-0（强制）**：当 `pageNo` 和 `pageSize` 字段是从 `WinBaseQueryRequest`（或其子类 `WinMvcQueryRequest`/`WinRpcQueryRequest`）继承而来，且字段类型为基本类型 `int`（不是包装类型 `Integer`）时，**不能与 `null` 比较**。
  - **判断条件**：如果 VO/DTO 继承自 `WinMvcQueryRequest` 或 `WinRpcQueryRequest`，且这些基类中的 `pageNo`/`pageSize` 字段类型为 `int`（基本类型），则不能进行 null 比较。
  - **正确用法**：直接使用 `inputVO.getPageNo()` 和 `inputVO.getPageSize()`，框架会提供默认值（pageNo=0, pageSize=100）
  - **错误用法**：`inputVO.getPageNo() != null` ❌（当字段类型为基本类型 `int` 时，不能与 null 比较，会导致编译错误）
  - **例外情况**：如果业务自定义的 VO/DTO 中自行定义了 `pageNo`/`pageSize` 字段，且类型为 `Integer`（包装类型），则可以与 `null` 比较。
  - **自定义默认值**：如果需要自定义默认值，可以使用：`int pageNo = inputVO.getPageNo() == 0 && 需要判断时 ? 自定义值 : inputVO.getPageNo()`

#### 2. 响应总数（count）性能约定

`WinBaseResponse`（及其子类 `WinMvcResponse`/`WinRpcResponse`）中的 `count` 字段用于返回符合条件的总条数。为了性能考虑，遵循以下 **框架约定**：

- **规则 PAGE-1（强制）**：仅在 **第一页**（`pageNo=0`）时计算并返回准确的 `count`。
- **规则 PAGE-2（强制）**：非首页查询，业务层/框架层应避免执行 count 查询，并将响应中的 `count` 设为 **-1**（或不返回），以减少 DB 压力。

---

### 3.9.8 异常与告警响应（`WinningRuntimeException` / `WinRpcResponse.warn` / `WinMvcResponse.warn`）

#### 背景

AKSO 体系中对外的错误语义主要有两类：

- **异常（error）**：用 `WinningRuntimeException` 表达业务失败，携带错误码与可格式化的消息参数。
- **告警（warn）**：用 `WinMvcResponse.warn` / `WinRpcResponse.warn` 表达“有提示但不失败”的响应（是否阻断由 `warnBlock*` 系列控制）。

#### ✅ 推荐 / 标准用法（AI 默认遵循）

- **规则 ERR-1（强制）**：业务校验失败、业务规则不满足等“可预期失败”，必须抛 `WinningRuntimeException`；禁止抛裸 `RuntimeException` / `Exception`。
  - errCode 必须来自统一错误码常量（优先放在提供方 `*-itf` 的 `model.constant.ErrorCodeConstant`），禁止在代码里硬编码 `"ESxxxxxx"` 之类字符串。
- **规则 ERR-2（强制）**：`WinningRuntimeException(errCode, String... params)` 的 `params` 用作“错误码消息模板”的格式化入参；业务侧传入的第一个参数应是**对外可读、可国际化**的消息文本。
  - 消息构造优先使用 `WinI18nUtils.loadString(...)`（避免中英文/多语言口径漂移）。
- **规则 ERR-3（推荐）**：当你是在 catch 里包装底层异常（DB/HTTP/RPC 等），优先使用 `WinningRuntimeException(errCode, ex, params...)` 保留 cause，便于排障与链路追踪。
- **规则 ERR-4（推荐）**：需要携带下游错误信息时（例如 RPC 返回的 `errorDetail.message`），仅允许拼接**已脱敏**且**可对外暴露**的片段；禁止把堆栈、SQL、token、账号等敏感信息拼到 message 里。

#### ✅ 告警响应规范

- **规则 WARN-1（强制）**：需要返回“警告但不失败”的响应时：
  - WebMVC：使用 `WinMvcResponse.warn(warnCode, warnMsg)`
  - RPC：使用 `WinRpcResponse.warn(warnCode, warnMsg)`
- **规则 WARN-2（推荐）**：warnCode 建议同样收敛到常量（可复用 `*-itf` 的 `model.constant` 目录），warnMsg 优先使用 `WinI18nUtils.loadString(...)`。
- **规则 WARN-3（推荐）**：当业务需要“告警并阻断”时，优先使用框架提供的 `warnBlock` / `warnBlockLimitDetail5`；如果语义上是明确失败（而非告警），则直接抛 `WinningRuntimeException`，不要混用两套语义导致调用方误判。

#### ❌ 反例（禁止 AI 学习或生成）

- 在业务代码里硬编码错误码 / 告警码字符串（例如 `"ES9999..."`）。
- 用 `return WinMvcResponse.warn(...)` 代替“真正的失败”来绕过失败语义（除非明确是 warnBlock* 语义）。
- 把敏感信息（SQL/堆栈/认证信息/隐私字段）拼进异常或告警 message。

---

### 3.10 工具类选型规范（winning-akso-utils-core / winning-pts-utils）（项目级推荐）

#### 背景

AKSO 工具链里已经沉淀了大量通用工具（主要集中在 `winning-akso-utils-core` 与 `winning-pts-utils`）。工程内应**优先复用框架提供的工具**，避免在不同模块引入“同类但行为不同”的第三方工具，导致：

- 序列化/反序列化策略不一致（尤其 JSON）
- 日期/时区/格式化不一致
- 字符串/编码/加密实现不一致
- 代码风格碎片化、排障成本上升

#### 选型总原则（你提到的核心约束，写成明确规则）

- **规则 U0（强推荐）**：优先使用 **`com.winning.base.akso.utils.*`** 与 **`com.winning.pts.utils.*`** 下的工具类。
- **规则 U1（推荐）**：仅当 AKSO/PTS 工具链没有覆盖某能力，才允许使用 AKSO 间接引入的第三方依赖工具（仍需团队确认不会引入“第二套标准”）。
- **规则 U2（强制）**：一旦项目选择了某个“标准工具入口”（如 JSON、拼音、五笔），必须全工程统一；禁止在不同模块建立不同入口。
- **规则 U3（强制）**：非必要不得新增第三方开源依赖；优先使用 AKSO/PTS 工具链或当前工程已通过 `winning-**-version` 管理的依赖能力。如确需新增，必须给出明确业务理由与替代方案对比，并把版本纳入 `winning-**-version` 的 `dependencyManagement` 统一管理（业务模块依赖声明不手写版本号）。

#### ✅ 推荐 / 标准用法（AI 默认遵循）

- **AKSO 基础运行信息（推荐）**：优先使用 `com.winning.base.akso.utils.ServerInfoUtil`
  - **适用场景**：获取应用名、IP、端口、实例标识、TraceId（请求维度）、ContextPath 拼接等“运行环境信息”。
  - **注意**：该工具依赖内部 `IServerInfoHandler`，属于框架运行时语义；不要自行用 `InetAddress`/环境变量拼装替代（容易在容器/多实例场景出错）。
- **AKSO ClassLoader 管理（推荐）**：优先使用 `com.winning.base.akso.utils.WinningClassLoaderUtil`
  - **适用场景**：需要明确使用 AKSO 全局 ClassLoader / 容器 ClassLoader 的场景（插件化、容器加载、跨模块动态加载等）。
  - **注意**：默认 `getGlobalClassloader()` 会回退到 `Thread.currentThread().getContextClassLoader()`；需要稳定语义时应由框架初始化设置全局 ClassLoader。
- **AKSO 类加载/子类型扫描（推荐）**：优先使用 `com.winning.base.akso.utils.WinningClassUtil`
  - **适用场景**：按类名安全加载（走 AKSO GlobalClassloader），或在指定包下扫描某父类型的实现（`findSubTypes`）。
  - **注意**：避免直接 `Class.forName`（可能绕过 AKSO 的 ClassLoader 语义）；若工程需要满足 AOT 打包原则，业务代码不得依赖 `findSubTypes` 这类“运行时扫描”作为核心能力入口（必须改为显式注册/白名单映射）。

- **JSON（强推荐）**：统一使用 `com.winning.pts.utils.mapper.JsonMapper`
  - **原则**：以 `JsonMapper.INSTANCE` 作为唯一入口（`toJson`/`fromJson`）。
  - **原因**：框架内部已经广泛使用该工具（日志、消息、发布等场景），便于统一配置与排障。
- **集合/判空（推荐）**：优先使用 `com.winning.pts.utils.collection.*` 下的工具
  - 例如：`ListUtil` / `MapUtil` / `CollectionUtil`（避免自己手写判空与转换）。
- **数值/单位（推荐）**：优先使用 `com.winning.pts.utils.number.*`
  - 例如：`MathUtil` / `NumberUtil` / `UnitConverter`。
- **时间（推荐）**：优先使用 `com.winning.pts.utils.time.*` 做日期处理；在“需要框架时间语义/可测时间”的场景，优先使用 `WinningTimer`（若项目已使用）
  - 例如：`DateUtil` / `DateFormatUtil` / `ClockUtil`。
- **反射/注解（推荐）**：优先使用 `com.winning.pts.utils.reflect.*`
  - 例如：`ReflectionUtil` / `AnnotationUtil` / `ClassUtil`。
  - **约束**：若工程需要满足 AOT 打包原则，反射仅允许用于少量“稳定且可预期”的框架类/基础设施层能力；禁止用反射做业务逻辑分派（例如根据字符串类名/方法名决定调用路径）。
- **文本/编码/摘要（推荐）**：优先使用 `com.winning.pts.utils.text.*`
  - 例如：`EncodeUtil` / `EscapeUtil` / `HashUtil` / `MoreStringUtil`。
- **拼音（强推荐）**：统一使用 `winning-akso-pinyin`
  - **原则**：只依赖 AKSO 提供的拼音能力，不要直接引入/调用 `pinyin4j`。
  - **原因**：AKSO 已封装并统一了拼音底层依赖与资源加载方式。
- **五笔（强推荐）**：统一使用 `winning-akso-wubi`
  - **原则**：只依赖 AKSO 提供的五笔能力，不要直接引入/调用 `wubi-data`/底层字库实现。
  - **原因**：AKSO 通过配置项（例如 `winning.wubi.base` / `winning.wubi.ext`）与统一初始化流程管理五笔资源。

#### ⚠️ 项目中可能存在但不推荐（AI 不作为默认生成）

- 直接使用第三方 JSON 工具（如 Jackson/Gson/Fastjson）进行业务 JSON 序列化：除非项目明确规定并统一治理，否则应统一到 `JsonMapper`。
- 直接调用底层拼音/五笔第三方库（`pinyin4j` / `wubi-data` 等）：会绕过 AKSO 的统一封装与配置。
- 直接使用 `InetAddress` / `NetworkInterface` / `System.getProperty` 等零散方式拼装应用信息：优先使用 `ServerInfoUtil` 统一获取。
- 直接 `Class.forName` / 自己维护静态 ClassLoader：优先使用 `WinningClassLoaderUtil` / `WinningClassUtil`。

#### ❌ 反例（禁止 AI 学习或生成）

- 在同一工程中混用多个 JSON 体系（例如 A 模块用 Fastjson，B 模块用 Jackson），导致字段命名、日期格式、null 策略不一致。
- 引入“模块私有的 JSON/拼音/五笔工具类”并扩散使用（会与 AKSO 工具链冲突）。
- 在框架/插件环境中绕过 AKSO ClassLoader 语义，导致“本地可运行、线上容器不可运行”的问题。

---

### 3.11 模块结构与跨模块约定（项目级强制）

#### 背景

本手册面向“任意业务工程”，建议默认沿用以下模块边界，用于：

- 业务模块间解耦（避免直接互相依赖 app 实现）
- 第三方/外部 API 统一适配接入（避免业务模块直接引入外部依赖）
- 跨模块模型复用（entity/vo/bo 与跨模块接口统一沉淀到 itf）

#### ✅ 推荐 / 标准约定（默认遵循）

- **规则 MOD-1（强制）**：系统内部业务模块用 `winning-xxx-xxx-employee`、`winning-xxx-xxx-item` 这类业务域模块承载。
- **规则 MOD-2（强制）**：所有项目外部 API 引入必须通过 `winning-xxx-xxx-external` 模块适配接入。
- **规则 MOD-3（强制）**：模块间解耦通过 `winning-xxx-xxx-*-itf` 完成，只在 itf 中放：
  - 跨模块接口（例如 `InternalEmployeeService`）
  - 可跨模块复用的模型（例如 `*Entity/*BO/*VO`）
- **规则 MOD-4（强制）**：业务模块禁止直接依赖其它业务模块的 `*-app`；跨模块调用只能依赖对方 `*-itf`。
- **规则 MOD-5（强制）**：内部跨模块接口统一使用 `InternalXxx...` 命名（接口定义在 `*-itf`，实现放在提供方 `*-app`）。
  - 说明：`*-itf` 已包含 `model`（`*Entity/*BO/*VO` 等），内部跨模块接口可直接依赖并使用这些模型类。
- **规则 MOD-6（强制）**：第三方/外部系统解耦接口统一使用 `ExternalXxx...` 命名（接口与配套 DTO 等放在 `external-itf`，实现放在 `external-app`）。
  - 说明：第三方适配场景下，除接口外，如果新增了为第三方调用服务的入参/出参/领域对象等类，也统一加 `External` 前缀，避免与内部模型混淆。
  - 业务模块只依赖 `external-itf`（不直接依赖第三方 API 包）。

#### 目录形态（推荐）

- 业务域：`winning-xxx-xxx-<domain>/{<domain>-api,<domain>-itf,<domain>-dao,<domain>-app}`
- 外部适配：`winning-xxx-xxx-external/{external-itf,external-app}`

---

### 3.12 事务与 DAO 层更新建议（项目级强制 + 推荐）

#### 背景

业务 `*-app` 层经常同时包含 RPC/Redis/ES 等操作。如果把 `@Transactional` 放到 app 的 Service 层，容易出现：

- 事务持有时间长（RPC/Redis/ES 等慢 IO 把 DB 事务拖住）
- 锁等待与吞吐下降
- 事务与租户上下文切换风险（事务开启后禁止切换 soid）

#### ✅ 推荐 / 标准用法（默认遵循）

- **规则 DAO-TX-1（强制）**：所有 DB 更新（insert/update/delete/逻辑删除）应集中在 `winning-xxx-xxx-*-dao` 层。
- **规则 DAO-TX-2（强制）**：事务建议在 `*-dao` 层开启（`@Transactional` 标注在 repository 类/方法上），`*-app` Service 层不持有长事务。
- **规则 DAO-TX-3（推荐）**：`*-app` Service 层应先完成 RPC/Redis/ES 等外部操作，最后再调用 `*-dao` 的事务方法落库（把事务缩到最小）。
- **规则 DAO-TX-4（推荐）**：复合模块更新（跨业务域的多表/多实体更新）时，dao 可以依赖多模块的 `*-itf`，并在同一个 dao 事务内完成更新。
- **规则 DAO-TX-5（推荐）**：复合/跨实体持久化默认使用 `EntityManager` 作为单一落库入口，避免 app 层同时持有多个模块的 `JpaRepository` 造成边界混乱。
  - **默认策略**：当实体可能来自“外部传入/跨模块组装”（可能是 detached），且无法 100% 确认是 insert 还是 update 时，优先使用 `EntityManager.merge(...)`（语义更稳，能覆盖“新增或更新”两类场景）。
  - **插入与更新的差异**：
    - 明确是新增且由本事务创建的实体：可用 `EntityManager.persist(...)`（避免 `merge` 触发的额外 select/复制成本）。
    - 明确是更新且只改少数字段、且表很大/热点很高：优先用 `JPQL update`（或必要时 native SQL）做定点更新，避免把整行实体加载到持久化上下文。
  - **批量/JPQL 更新注意事项**：`JPQL update/delete` 会绕过一级缓存；执行后应按需 `flush/clear`（或明确不复用同一持久化上下文中的旧实体），并且 where 条件必须包含租户过滤（如 `hospitalSOID`）。
- **规则 DAO-TX-6（推荐）**：dao 层 repository 包名统一使用 `repository`（避免 `repositories` 这种复数包名扩散为默认风格）。
- **规则 DAO-TX-7（推荐）**：同一 dao 模块内区分两类持久化入口：
  - 单实体 CRUD：`XxxRepository extends JpaRepository<XxxEntity, Long>`
  - 复合/跨实体更新：`XxxCompositeRepository`（内部用 `EntityManager` 统一落库，事务在此层开启）
- **规则 DAO-TX-8（推荐）**：在 dao 层使用 `EntityManager` 时，统一显式标注 `@PersistenceContext(unitName = "primaryPersistenceUnit")`，避免多数据源场景下注入到非预期的 PersistenceUnit。

#### 调用链建议（推荐）

- `*-app`：先完成 RPC/Redis/ES，最后调用 `*-dao` 的 `XxxCompositeRepository`/`XxxRepository` 落库
- `*-dao`：`@Transactional` 只出现在 repository 层（单表或复合）

---

### 3.13 AOT 打包原则（项目级强制）

#### 背景

AKSO 的 `akso-pbc-builder` 属于“构建期打包/装配”能力。为保证打包产物可预测、可启动、可治理，业务代码必须遵循“可被构建期静态分析/装配”的原则，避免把关键能力放到运行时通过扫描/反射/动态代理来“猜”出来。

#### ✅ 推荐 / 标准用法（默认遵循）

- **规则 AOT-1（强制）**：业务扩展点/策略选择必须使用“显式注册”的方式落地（例如枚举/Map 映射到具体实现、Spring 注入 `List<T>`/`Map<String, T>` 后再做选择），禁止依赖运行时扫描 classpath 来发现实现类。
- **规则 AOT-2（强制）**：禁止在业务代码里新增任何“以字符串驱动”的反射分派（例如 `Class.forName(className)`、`Method.invoke`、`Field#setAccessible(true)`）；需要可插拔能力时，必须使用接口 + 显式实现 + 显式映射。
- **规则 AOT-3（强制）**：禁止在业务代码里引入/扩散动态字节码增强与动态代理体系（例如 CGLIB `Enhancer`、ByteBuddy、`Proxy.newProxyInstance`）作为核心业务能力的实现手段。
- **规则 AOT-4（强制）**：资源文件读取必须通过 classpath 的“固定绝对路径”（例如 `classpath:/xxx/yyy.json` 或 Spring `ResourceLoader`），禁止通过 `new File(...)`、遍历目录、或对 jar 文件系统进行扫描来发现资源。
- **规则 AOT-5（推荐）**：需要“可配置的业务分派”时，优先设计为枚举/编码值（来自配置/数据库/入参）到固定实现的映射，而不是让配置直接携带类名/方法名。

#### ⚠️ 项目中可能存在但不推荐（AI 不作为默认生成）

- 在运行时做包扫描/子类扫描（例如 `WinningClassUtil.findSubTypes`）来构建核心注册表。
- 通过反射访问 DTO/Entity 的字段来完成业务逻辑（例如按字段名读写）；建议改为显式 getter/setter 或显式映射逻辑。

#### ❌ 反例（禁止 AI 学习或生成）

- 用配置项/数据库字段保存“类名/方法名”，运行时 `Class.forName` + `invoke` 来执行业务逻辑。
- 在业务模块引入并使用 ByteBuddy/CGLIB 自行生成类或代理，以替代正常的接口实现与 Spring 注入。
- 通过遍历 `jar:file:` 或目录来“发现” SQL/规则/模板等资源文件。

#### AI 生成检查清单（必须逐条满足）

- 新增代码是否避免了 `Class.forName` / `invoke` / `setAccessible` / 动态代理？
- 是否避免了运行时包扫描/子类扫描来完成“核心注册/发现”？
- 资源加载是否使用 classpath 固定路径，而不是文件系统遍历/扫描？
- 策略分派是否落在“枚举/Map/显式注入列表”而不是“字符串类名”？

---

## 4. AI 编码强约束汇总（可直接当规则引擎用）

### 4.1 强制

- **强制-1**：任何异步/线程池执行体访问 DB/RPC/缓存前，必须用 `TenancyContext.getWithSoid/doWithSoid` 绑定 `hospitalSOID`。
- **强制-2**：使用 `CompletableFutureBuilder` 时必须优先选择 **带 `hospitalSOID`** 的重载，并指定 `Domain`。
- **强制-3**：JPA 查询必须显式包含租户过滤（`hospitalSOID` / soid 集合）并由入参传入。
- **强制-3.1**：需要分布式唯一标识（UID）的新增代码，统一使用 AKSO DUID（`DuidAbility`），禁止在业务模块内扩散 Snowflake/UUID/自研号段作为业务主键/唯一标识。
- **强制-4**：Redis/ES 等“中间件命名隔离”依赖 `TenancyContext`：任何会触达 Redis/ES/文件/注册中心命名的代码路径，**必须确保当前线程已正确设置 soid**（入口显式包 `TenancyContext.*WithSoid`，或使用 `CompletableFutureBuilder` 带 soid 的方法创建线程）。
- **强制-4.1**：默认情况下 **不要在 Redis Key / ES Index 名里手工拼接 soid 前缀**；AKSO 会通过 `TenancyContext` 自动重写（避免“双前缀/重复隔离”导致定位困难）。
- **强制-4.2**：Redis 写入必须设置 TTL（除非明确永久策略，TTL默认单位为毫秒）。
- **强制-5**：Xxl-Job/定时任务必须按租户循环，并用 `TenancyContext.doWithSoid` 包装每个租户执行体。
- **强制-6**：所有 Controller / RPC Provider 入口必须显式 `TenancyContext.*WithSoid`，soid 来源必须明确（Controller：BizContext 或 inputDTO；RPC：inputDTO.getHospitalSOID）。
- **强制-7**：HQL/JPQL 语句中必须使用 Entity 的 **全包名**（例如 `com.pkg.Entity`），禁止仅使用类名，以避免同名类解析冲突。
- **强制-8**：新增业务代码必须满足 AOT 打包原则：禁止运行时包扫描/子类扫描作为核心发现机制；禁止“字符串驱动反射/动态代理”作为业务分派手段；资源加载必须使用 classpath 固定路径。

### 4.2 推荐

- **推荐-1**：对象转换默认用 `BeanMapper`，列表用 `mapList`。
- **推荐-2**：JPA 优先 `@Query(HQL/JPQL)` 或 Specification，控制派生查询规模。
- **推荐-3**：在热点路径避免频繁调用 `BizContext.getCurrentHospitalSOID()`；优先从入参/SessionUtil 取得并向下传递。
- **推荐-4**：ES 操作统一用 `WinningElasticsearchTemplate`（Class-based API），并显式带租户过滤（字段或索引隔离）。
- **推荐-5**：分布式锁统一使用 `RedisLocker`，并设置 expireMs + finally 解锁。
- **推荐-6**：JSON 序列化/反序列化统一使用 `JsonMapper`；拼音/五笔分别统一使用 `winning-akso-pinyin` / `winning-akso-wubi`。
- **推荐-7**：可配置策略分派优先使用“编码值/枚举 + 显式映射 + Spring 注入列表”，避免把类名/方法名下沉为配置。

### 4.2.1 关于“框架自动追加 soid 前缀”的边界与风险（重要）

✅ 框架能力（可以依赖，但前提是上下文正确）：

- **Redis**：AKSO Redis 组件默认使用 `KeyStringRedisSerializer`，其 `serialize/deserialize` 会调用 `TenancyContext.instance().changeRedisKey(key)` / `TenancyContext.unchangeRedisKey(key)`，从而**自动为 key 增加租户前缀**。
- **Elasticsearch**：AKSO 的 `IndexCoordinatesUtil` 会调用 `TenancyContext.instance().changeEsIndex(indexName)`，`WinningElasticsearchTemplate` 内部也会对 `IndexCoordinates` 做统一 `of(...)` 重写，从而**自动为索引名增加租户前缀**。

⚠️ 风险点（只靠框架处理仍可能出问题的场景）：

- **RISK-1（最高频）上下文丢失**：线程没有正确设置 soid（入口没包 `TenancyContext`、异步没带 soid、使用原生线程池/CompletableFuture），自动前缀就不会生效或会按默认策略生效，导致**串租户/写到默认租户**。
- **RISK-2 使用了“global key / 不走 KeyStringRedisSerializer”**：部分模板/开关可能显式使用 `StringRedisSerializer`（global 模式），这类写法会绕过自动前缀，导致 key 不隔离。
- **RISK-3 双重前缀**：业务手工拼了 soid，同时框架又追加一次，导致 key/index 变成 `soid_TENANCY_:soid_TENANCY_:xxx` 一类，排查和迁移成本很高。
- **RISK-4 跨系统共享 key/index**：如果有“多服务/多语言/外部系统”直接读写同一 Redis/ES 资源，且对方不理解 AKSO 的租户前缀规则，则会出现**读不到/写错位置**的问题。

✅ 统一建议（跨项目通用）：

- **建议 S1（强推荐）**：对“仅在本服务内部使用”的 Redis/ES 命名空间，**默认完全依赖 AKSO 的 TenancyContext 前缀**，业务不要重复拼 soid。
- **建议 S2（强推荐）**：若必须跨系统共享（或需要直接在 Redis/ES 控制台定位），应在团队内明确一套“可见的命名空间策略”（例如业务前缀 `biz:`），但仍不建议把 soid 手工拼进 key（保持由框架追加）。
- **建议 S3（推荐）**：对关键写路径增加“上下文断言/日志”能力（例如在关键入口记录当前 soid），用于快速发现 RISK-1。

### 4.3 禁止

- **禁止-1**：直接使用原生 `CompletableFuture.runAsync/supplyAsync`、`Executors.*` 自建线程池来跑业务逻辑。
- **禁止-2**：在新线程/异步体内“隐式依赖 BizContext 线程本地”作为租户来源。
- **禁止-3**：大量新增 `findBy...And...` 派生查询方法。
- **禁止-4**：绕过 `RedisAbility`/`RedisLocker` 自行使用 RedisTemplate/Jedis/Lettuce 或自研分布式锁。
- **禁止-5**：ES 直接使用原生 Client 或 `IndexCoordinates` 绕过 AKSO 前缀治理；更不得暴露“删除索引/全量重建”的对外接口。
- **禁止-6**：Controller/RPC 返回值绕过 `WinMvcResponse<T>` / `WinRpcResponse<T>`。
- **禁止-7**：新增代码中使用 `Class.forName`/反射调用/运行时扫描/动态代理来完成核心业务逻辑分派或扩展点发现。
- **禁止-8**：非必要新增第三方开源依赖；优先使用 AKSO/PTS 工具链或当前工程已纳入 `winning-**-version` 管理的依赖能力。

---

## 5.（可选）后续治理建议（不影响 AI 生成约束）

- 对所有 `submit(() -> reloadFunc.apply(key))` 类缓存刷新点做一次统一治理：在框架层提供强制租户包装的 reload 模板，避免“靠注释约束”。
- 对 `CompletableFutureBuilder` 未显式传 soid 的调用点做收敛（至少在新增代码中禁用）。
- 对派生查询方法制定上限与审查（例如每个 Repo 不超过 N 个派生方法，超过必须用 `@Query`/Specification）。

---

## 6. AI 使用时的“合理判断”原则（手册不完备时必须遵守）

> 说明：AKSO 能力面很广，且不同项目启用的 starter 与配置不完全一致，因此手册不可能覆盖所有细节。
> 当手册没有明确写到某个细节时，AI 允许“合理理解框架”做决策，但必须遵守以下边界。

- **AI-1（强制）**：永远优先保证 **租户上下文正确**（入口显式 `TenancyContext.*WithSoid`、异步用 `CompletableFutureBuilder` 带 soid、避免原生线程池）。当不确定是否会跨线程/跨入口时，默认按“会跨线程”处理。
- **AI-2（强制）**：永远优先保证 **接口边界稳定**（RPC：`*InputDTO/*OutputDTO` + `WinRpcResponse<T>`；Web：`*InputVO/*OutputVO` + `WinMvcResponse<T>`）。
- **AI-3（强制）**：永远优先保证 **单一入口与一致性**（同一能力面不引入第二套工具/第二套中间件客户端；JSON 统一 `JsonMapper`；对象映射默认 `BeanMapper`）。
- **AI-4（推荐）**：手册缺失但确需使用某 AKSO 能力时，应先尝试通过以下顺序“自证正确性”：
  - **优先用最省 token 的方式确认**：先搜索工程现有用法与配置（限定目录/限定符号），再补充最少量上下文；不要一上来通读大文件。
  - 仅当手册不完备、且工程内用法也无法自证时，才读取 AKSO 源码/索引（例如 `.cursor/knowledge/AKSO-Framework-Source-Code.md`）确认默认行为（尤其租户前缀/序列化器/线程池）。
  - 在工程中搜索同能力的既有用法，优先复用“已形成共识的写法”。
  - 若仍无法确定：宁可收敛到更显式的写法（显式传 soid、显式 TenancyContext 包裹、显式 TTL），不要靠隐式 AOP/ThreadLocal 侥幸工作。
- **AI-5（强制）**：**禁止凭空引入新的 AKSO 组件/新 starter 或第三方开源依赖**。如确需新增依赖，必须在 PR/变更说明中写清：业务需求、替代方案对比、配置项、租户隔离策略、回滚方案，并把版本纳入 `winning-**-version` 的 `dependencyManagement` 统一管理（业务模块依赖声明不手写版本号）。
- **AI-6（强制）**：仅当你明确要求输出"设计/评审/方案/变更说明"类文档时才允许新增 `.md` 文件，并统一存放到 `docs/ai/<moduleKey>/<featureKey>/`；同一主题固定文件名为 `<topic>.md`（后续迭代直接更新该文件），如需保留历史版本则把旧文件移动到 `docs/ai/<moduleKey>/<featureKey>/history/yyyyMMdd-HHmm-<topic>.md`；禁止散落在仓库根目录或模块根目录。
- **AI-7（强制）**：**生成代码时必须检查依赖完整性**。在生成 `*-app` 模块的代码时，必须检查：
  - 如果代码中使用了 `BizContext`，必须确保 `pom.xml` 中包含 `winning-security-biz-webmvc` 依赖
  - 如果代码中使用了 `DuidAbility`，必须确保 `pom.xml` 中包含 `winning-akso-duid-starter` 依赖
  - 如果代码中使用了 `RedisAbility`，必须确保 `pom.xml` 中包含 `winning-akso-redis-starter` 依赖
  - 如果代码中使用了 `WinningElasticsearchTemplate`，必须确保 `pom.xml` 中包含 `winning-akso-elasticsearch-starter` 依赖
  - 如果代码中使用了 `@JobHandler`，必须确保 `pom.xml` 中包含 `winning-akso-xxljob-starter` 依赖
  - **检查方法**：生成代码后，搜索代码中使用的 AKSO 组件类名，对照依赖清单（规则 CL-6/CL-7）确认 `pom.xml` 中是否已包含对应依赖

---

## 7. 专项指南

### 7.1 Redis（`winning-akso-redis-starter`）专项

#### 7.1.1 引入依赖（不写版本）

```xml
<dependency>
  <groupId>com.winning.base</groupId>
  <artifactId>winning-akso-redis-starter</artifactId>
</dependency>
```

#### 7.1.2 常用配置（示例）

> 注意：示例中的 host/password 仅作占位；实际值以部署环境为准。
> `winning.redis.client` 支持 `lettuce`/`jedis`，二选一。

Lettuce：

```properties
winning.redis.client=lettuce
spring.data.redis.repositories.enabled=false
spring.redis.database=8
spring.redis.host=127.0.0.1
spring.redis.port=6379
spring.redis.password=***REDACTED***
spring.redis.lettuce.pool.max-active=400
spring.redis.lettuce.pool.max-idle=200
spring.redis.lettuce.pool.max-wait=-1
spring.redis.lettuce.pool.min-idle=100
```

Jedis：

```properties
winning.redis.client=jedis
spring.data.redis.repositories.enabled=false
spring.redis.database=8
spring.redis.host=127.0.0.1
spring.redis.port=6379
spring.redis.password=***REDACTED***
spring.redis.jedis.pool.max-active=400
spring.redis.jedis.pool.max-idle=200
spring.redis.jedis.pool.max-wait=-1
spring.redis.jedis.pool.min-idle=100
```

#### 7.1.3 API 速查（`RedisAbility`）

> 目的：让研发快速知道“用哪个能力”，不是逐方法手册。具体方法以接口定义为准。

- **键值**：`get/set/setIfAbsent/delete/hasKey`
- **列表**：`leftPush/rightPush/range/leftPop/rightPop/listSize`
- **哈希**：`hSet/hGet/hMSet/hMGet/entries/deleteHashKv`
- **集合**：`sAdd/members/unionSet/deleteSetKv`
- **计数**：`increment/decrement`
- **过期**：`expire/expireAt`
- **批量**：`multiSet/multiGet/hGetAll/hGetAllToString`

#### 7.1.4 完整接口签名（Appendix，用于查阅；以源码为准）

> 说明：这里给出 `RedisAbility<K,V>` 的接口签名级清单（来自 AKSO 源码索引）。
> 使用时仍要遵守本手册的约束：**确保 soid 上下文**、**避免双前缀 key**、**写入必须 TTL（除非明确永久策略）**，以及"同一 key 下值类型必须一致"。
>
> **重要提示**：`set(K key, T value, long timeout)` 和 `setIfAbsent(K key, T value, long timeout)` 方法的 `timeout` 参数单位为**毫秒**（milliseconds），不是秒，也不接受 `TimeUnit` 参数。
> - 正确用法：`redisAbility.set(key, value, TimeUnit.HOURS.toMillis(1))` 或 `redisAbility.set(key, value, 3600000L)`（1小时=3600000毫秒）
> - 错误用法：`redisAbility.set(key, value, 1, TimeUnit.HOURS)` ❌（参数数量错误，set 方法只有3个参数）
> - 错误用法：`redisAbility.set(key, value, TimeUnit.HOURS.toSeconds(1))` ❌（单位错误，应使用 toMillis 转换为毫秒）
> - 错误用法：`redisAbility.set(key, value, TimeUnit.HOURS.toHours(1))` ❌（单位错误，应使用 toMillis 转换为毫秒）

```java
public interface RedisAbility<K, V> {

    Boolean hasKey(K key);
    V getOriginal(K key);

    <T> T get(K key, Class<T> type);
    <T> T get(K key, Type javaType);

    // timeout 参数单位为毫秒（milliseconds），不是秒，也不接受 TimeUnit 参数
    <T> void set(K key, T value, long timeout);
    <T> Boolean setIfAbsent(K key, T value, long timeout);

    <T> void rightPush(K key, T value, long expireTime);
    <T> void rightPushAll(K key, Collection<T> values, long expireTime);
    <T> void leftPush(K key, T value, long expireTime);
    <T> void leftPushAll(K key, Collection<T> values, long expireTime);

    <T> List<T> range(K key, long start, long end, Class<T> type);
    <T> List<T> rightPop(K key, int count, Class<T> type);
    <T> List<T> leftPop(K key, int count, Class<T> type);
    long listSize(K key);

    void hSet(K key, String field, String value, long expireTime);
    <T> void hSet(String key, String field, T value, long expireTime);
    String hGet(K key, Object filed);
    <T> T hGet(String key, String field, Class<T> type);
    Map<String, String> entries(K key);
    <V> void hMSet(K key, Map<String, V> values, long expireTime);
    void deleteHashKv(K key, Object... hashKeys);

    Boolean delete(K key);
    Long delete(Collection<K> keys);

    <T> void multiSet(List<? extends RedisObject<K, T>> values);
    <T> void multiSet(Map<String, T> valueMap);
    <T> void multiSet(Map<String, T> valueMap, Long expireTime);
    <T> List<T> multiGet(List<K> keys, Class<T> clazz);

    <T> void sAdd(K key, List<T> values, long expireTime);
    <T> void sAdd(K key, T values, long expireTime);
    <T> void deleteSetKv(K key, T... deleteValue);
    Set unionSet(String... key);
    <T> Set<T> unionSetWithType(Class<T> type, String... key);
    <R extends Collection> R unionCollection(Class<R> setType, String... key);
    <T> List<T> members(K key, Class<T> tClass);

    Long increment(String key);
    Long increment(String key, Long amount);
    Long decrement(String key, Long amount);
    Long decrement(String key);

    Boolean expireAt(String key, Date date);
    Boolean expire(String key, long time, TimeUnit timeUnit);

    @Deprecated
    List<Map> hGetAll(Collection<String> keys, Function<Map<byte[], byte[]>, Map> convertMap);

    <T> List<Map<String, T>> hGet(Collection<String> keys, List<String> fields, Function<byte[], T> convert);

    @Deprecated
    List<Map<String, String>> hGetAllToString(Collection<String> keys);

    <T> Map<String, T> hMGet(String key, Class<T> type);

    <T> List<T> hMGet(String key, Collection hashKeys, Class<T> type);
}
```

### 7.2 Elasticsearch（`winning-akso-elasticsearch-starter`）专项

#### 7.2.1 引入依赖（不写版本）

```xml
<dependency>
  <groupId>com.winning.base</groupId>
  <artifactId>winning-akso-elasticsearch-starter</artifactId>
</dependency>
```

#### 7.2.2 常用配置（示例）

TCP 模式：

```properties
spring.data.elasticsearch.cluster-name=winning_elasticsearch
spring.data.elasticsearch.cluster-nodes=127.0.0.1:9300
spring.data.elasticsearch.repositories.enabled=true
winning.elasticsearch.client=tcp
```

REST/HTTP 模式（可配置账号密码）：

```properties
spring.data.elasticsearch.cluster-name=winning_elasticsearch
spring.data.elasticsearch.cluster-nodes=127.0.0.1:9200
winning.elasticsearch.username=***REDACTED***
winning.elasticsearch.password=***REDACTED***
winning.elasticsearch.client=rest
```

#### 7.2.3 使用边界（与本手册规则对齐）

- **必须**使用 `WinningElasticsearchTemplate`（避免绕过 AKSO 的 `IndexCoordinatesUtil` 与租户索引前缀治理）。
- **必须**保证线程 soid 上下文正确（见 强制-4 / 强制-4.1）。
- **严禁**默认生成“删索引/重建索引”的对外接口。

#### 7.2.4 API 速查（`WinningElasticsearchTemplate`，按 AKSO 源码接口）

> 说明：这里提供“方法级速查”（方便开发查能力边界），不是鼓励随意调用所有方法。
> 使用时仍要遵守本手册的租户/索引治理规则，尤其是**不要绕过框架对 Index 的重写**。

- **Scroll 滚动查询**
  - `startScroll(scrollTimeInMillis, NativeSearchQuery, Class<T>)`
  - `startScroll(scrollTimeInMillis, CriteriaQuery, Class<T>)`
  - `continueScroll(scrollId, scrollTimeInMillis, Class<T>)`
  - `searchScrollStart(scrollTimeInMillis, Query, Class<T>, IndexCoordinates)`
  - `searchScrollContinue(scrollId, scrollTimeInMillis, Class<T>, IndexCoordinates)`
  - `clearScroll(scrollId)`
- **查询**
  - `queryForObject(GetQuery/CriteriaQuery/StringQuery, Class<T>)`
  - `queryForList(CriteriaQuery/StringQuery/NativeSearchQuery, Class<T>)`
  - `queryForPage(NativeSearchQuery/CriteriaQuery/StringQuery, Class<T>)`
  - `queryForIds(NativeSearchQuery, Class<T>)`
  - `count(CriteriaQuery/NativeSearchQuery, Class<T>)`
  - `stream(CriteriaQuery/NativeSearchQuery, Class<T>)`
  - `multiGet(NativeSearchQuery, Class<T>)`
  - `moreLikeThis(MoreLikeThisQuery, Class<T>)`
- **索引/映射/别名/设置**
  - `createIndex(indexName, settings)`
  - `deleteIndex(indexName)`
  - `indexExists(indexName)` / `existIndex(indexName)` / `existIndex(Class)`
  - `putMapping(indexName, type, mapping)` / `getMapping(indexName, type)`
  - `getSetting(indexName)` / `refresh(indexName)`
  - `queryForAlias(indexName)`
- **写入/更新/删除**
  - `index(IndexQuery[, indexName|Class])`
  - `update(UpdateQuery[, indexName|Class])`
  - `bulkIndex(List<IndexQuery>, indexName|Class)`
  - `bulkUpdate(List<UpdateQuery>, indexName|Class)`
  - `delete(indexName, type, id)` / `delete(Class<T>, id)` / `delete(DeleteQuery, Class<T>)` / `delete(CriteriaQuery, Class<T>)`
- **辅助**
  - `suggest(SuggestBuilder, indices...)` / `suggest(SuggestBuilder, Class)`
  - `ping()`

#### 7.2.5 完整接口签名（Appendix，用于查阅；以源码为准）

> 说明：为避免“口头描述偏差”，这里直接给出 `WinningElasticsearchTemplate` 的接口签名级清单（来自 AKSO 源码索引）。
> 实际使用仍须遵守本手册的约束：**不要绕过框架索引重写**、**确保租户上下文**、**禁止对外暴露高危运维接口**。

```java
public interface WinningElasticsearchTemplate extends ElasticsearchOperations, SearchOperations {

    void setSearchTimeout(String searchTimeout);

    <T> AggregatedPage<T> startScroll(long scrollTimeInMillis, NativeSearchQuery searchQuery, Class<T> clazz);
    <T> AggregatedPage<T> startScroll(long scrollTimeInMillis, CriteriaQuery criteriaQuery, Class<T> clazz);
    <T> AggregatedPage<T> continueScroll(String scrollId, long scrollTimeInMillis, Class<T> clazz);

    <T> SearchScrollHits<T> searchScrollStart(long scrollTimeInMillis, Query query, Class<T> clazz, IndexCoordinates index);
    <T> SearchScrollHits<T> searchScrollContinue(@Nullable String scrollId, long scrollTimeInMillis, Class<T> clazz, IndexCoordinates index);

    void clearScroll(String scrollId);
    <T> Page<T> moreLikeThis(MoreLikeThisQuery query, Class<T> clazz);

    boolean createIndex(String indexName, Object settings);
    Map getSetting(String indexName);
    void refresh(String indexName);

    List<AliasMetaData> queryForAlias(String indexName);
    ElasticsearchPersistentEntity getPersistentEntityFor(Class clazz);
    void setApplicationContext(ApplicationContext context) throws BeansException;

    SearchResponse suggest(SuggestBuilder suggestion, String... indices);
    SearchResponse suggest(SuggestBuilder suggestion, Class clazz);

    String delete(String indexName, String type, String id);
    <T> String delete(Class<T> clazz, String id);
    <T> void delete(DeleteQuery deleteQuery, Class<T> clazz);
    <T> void delete(CriteriaQuery criteriaQuery, Class<T> clazz);

    boolean deleteIndex(String indexName);
    boolean indexExists(String indexName);
    boolean typeExists(String index, String type);

    void bulkIndex(List<IndexQuery> queries, String indexName);
    void bulkUpdate(List<UpdateQuery> queries, String indexName);
    <T> void bulkIndex(List<IndexQuery> queries, Class<T> type);
    <T> void bulkUpdate(List<UpdateQuery> queries, Class<T> type);

    String index(IndexQuery query, String indexName);
    UpdateResponse update(UpdateQuery query, String indexName);
    <T> String index(IndexQuery query, Class<T> type);
    String index(IndexQuery query);
    <T> UpdateResponse update(UpdateQuery query, Class<T> type);

    boolean putMapping(String indexName, String type, Object mapping);
    Map getMapping(String indexName, String type);

    ElasticsearchConverter getElasticsearchConverter();

    <T> T queryForObject(GetQuery query, Class<T> clazz);
    <T> T queryForObject(CriteriaQuery query, Class<T> clazz);
    <T> T queryForObject(StringQuery query, Class<T> clazz);

    <T> AggregatedPage<T> queryForPage(NativeSearchQuery query, Class<T> clazz);

    <T> T query(NativeSearchQuery query, ResultsExtractor<T> resultsExtractor, Class<T> clazz);
    <T> T query(NativeSearchQuery query, ResultsExtractor<T> resultsExtractor, String indexName);
    <T> List<T> queryForList(NativeSearchQuery query, ResultsExtractor<List<T>> resultsExtractor, Class<T> clazz);

    <T> List<T> queryForList(CriteriaQuery query, Class<T> clazz);
    <T> List<T> queryForList(StringQuery query, Class<T> clazz);
    <T> List<T> queryForList(NativeSearchQuery query, Class<T> clazz);

    <T> List<String> queryForIds(NativeSearchQuery query, Class<T> clazz);
    <T> Page<T> queryForPage(CriteriaQuery criteriaQuery, Class<T> clazz);
    <T> Page<T> queryForPage(StringQuery query, Class<T> clazz);

    <T> CloseableIterator<T> stream(CriteriaQuery query, Class<T> clazz);
    <T> CloseableIterator<T> stream(NativeSearchQuery query, Class<T> clazz);

    <T> long count(CriteriaQuery criteriaQuery, Class<T> clazz);
    <T> long count(NativeSearchQuery searchQuery, Class<T> clazz);
    <T> List<T> multiGet(NativeSearchQuery searchQuery, Class<T> clazz);

    boolean existIndex(String indexName);
    boolean existIndex(Class type);

    void setPersistentEntityId(Object entity, String id);
    ElasticsearchPersistentEntity<?> getRequiredPersistentEntity(Class<?> clazz);

    void print(String msg);
    void error(String code, String msg);

    <T> boolean isKeyWord(String field, Class<T> clazz);
    boolean isKeyWord(String field, String idx);
    <T> String changeKeyWord(String field, Class<T> clazz);
    String changeKeyWord(String field, String idx);

    ClusterHealthResponse getHealth();
}
```

### 7.3 File（`winning-akso-file-starter`）专项

#### 7.3.1 引入依赖（不写版本）

```xml
<dependency>
  <groupId>com.winning.base</groupId>
  <artifactId>winning-akso-file-starter</artifactId>
</dependency>
```

#### 7.3.2 常用配置（示例）

Minio（新配置模式）：

```properties
winning.file.client=Minio
winning.file.uri=http://127.0.0.1:9000
winning.file.accessKey=***REDACTED***
winning.file.secretKey=***REDACTED***
```

Minio（旧配置模式，存量兼容）：

```properties
winning.minio.enabled=true
winning.minio.uri=http://127.0.0.1:9000
winning.minio.accessKey=***REDACTED***
winning.minio.secretKey=***REDACTED***
```

Aliyun OSS：

```properties
winning.file.client=AliyunOSS
winning.file.uri=http://oss-cn-shanghai.aliyuncs.com/
winning.file.accessKey=***REDACTED***
winning.file.secretKey=***REDACTED***
winning.file.baseBucketName=your-bucket
```

#### 7.3.3 API 速查（`WinFileTemplate`）

- **桶**：`bucketExists`
- **保存**：`save(bucketName, objectName, stream[, isOverride])`
- **打包 Zip**：`zip(zipBucketName, relativePath, ossFileNames, reNames)`
- **删除**：`delete`
- **获取**：`get`

### 7.4 Xxl-Job（`winning-akso-xxljob-starter`）专项

#### 7.4.1 引入依赖（不写版本）

```xml
<dependency>
  <groupId>com.winning.base</groupId>
  <artifactId>winning-akso-xxljob-starter</artifactId>
</dependency>
```

#### 7.4.2 常用配置（示例）

```properties
winning.xxljob.enabled=true
xxl.job.admin.addresses=http://127.0.0.1:18080
xxl.job.executor.appname=your-app-name
xxl.job.executor.logpath=/var/log/xxl-job/jobhandler
xxl.job.executor.logretentiondays=-1
xxl.job.executor.port=9999
```

#### 7.4.3 关键约束（多租户 + 入口）

- 任务是独立入口，必须按租户循环，并对每个租户执行体 `TenancyContext.doWithSoid(...)`（见 强制-5 / 规则 JH1）。
- 如需要运维平台采集任务元信息，可使用 AKSO 扩展注解（如 `@JobTriggerInfo`），但不改变租户约束。

#### 7.4.4 AKSO 扩展：`@JobTriggerInfo` 字段说明（按 AKSO 源码）

> 用途：让运维平台/任务平台可以采集任务元信息（cron/描述/作者/路由策略等），便于自动化管理。

- **必填**
  - `cron`：任务执行 CRON
  - `desc`：任务描述
  - `auth`：作者
  - `param`：运行参数
- **可选（常用）**
  - `route_strategy`：执行器路由策略（默认 `ROUND`）
  - `block_strategy`：阻塞处理策略（默认 `COVER_EARLY`）
  - `timeout`：执行超时（秒，默认 0）
  - `fail_retry_count`：失败重试次数（默认 0）
  - `glueType`：运行模式（默认 `BEAN`）
- **可选（平台治理/分类）**
  - `jobTag`：任务标签（示例含“同步 ES/同步 Redis/异步业务”等）
  - `sysTag`：系统标签（示例含“门诊/住院/HIS/病案/MDM/护理”等）
  - `defaultStartTag`：最小启动标志（默认 -1 未配置）
  - `grayStartTag`：灰度标志（默认 -1 未配置）
  - `grayCron`：灰度任务 CRON（默认空）
  - `preJobName`：前置任务名称（默认空）
  - `scenesType`：场景类型（默认空）

