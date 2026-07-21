---
name: "AKSO Code Generation Templates"
description: "AKSO 代码生成模板库，包含常见研发任务的提示词模板"
scope: project
priority: 2
---

# AKSO 代码生成模板

> **目的**：把"常见研发任务"写成可复制的提示词模板，快速触发 AI 按 **AKSO 工程约定**生成代码。
>
> **使用方式**：复制某条模板 → 填写【方括号】变量 → 发送给 AI。
>
> **相关规则**：所有实现必须遵循 `.cursor/rules/01-backend/akso-framework-guide.mdc` 的强制/推荐/禁止规则。

---

## 快速索引

### 按场景分类

- **接口开发**
  - [新增 WebMVC Controller 接口](#1-新增-webmvc-controller-接口给前端)
  - [新增 RPC/Feign Provider 接口](#2-新增-rpcfeign-provider-接口服务提供方)
  - [新增 RPC/Feign Consumer 调用封装](#3-新增-rpcfeign-consumer-调用封装服务调用方)

- **数据访问**
  - [新增 JPA 查询](#9-新增-jpa-查询repositoryspecification)
  - [新增 Redis 缓存/暂存](#6-新增-redis-缓存暂存repositorycache-层)
  - [新增 ES 同步/检索](#8-新增-es-同步检索searchsync)

- **并发与异步**
  - [并发聚合 / 异步加速](#4-并发聚合--异步加速改造现有逻辑)

- **任务与锁**
  - [新增定时任务 / Xxl-Job](#5-新增定时任务--xxl-job)
  - [新增分布式锁](#7-新增分布式锁租户粒度--业务粒度)

- **代码规范**
  - [AKSO 规范合规检查](#0-akso-规范合规检查查证--修复)
  - [分层命名与对象转换](#10-分层命名与对象转换dtovoboentity)

- **完整功能**
  - [功能模块全流程](#11-功能模块全流程从需求到上线的一条龙模板)

---

## 通用输出要求（建议你固定加在每次提示词末尾）

- 输出方式：**直接修改仓库代码**（不要只给建议），并说明改动文件列表
- 输出内容：包含必要的 DTO/VO、Service、Repo/DAO、单元测试/示例（如适用）
- 日志与错误：关键路径日志必须带 `hospitalSOID/soid`（不要泄露敏感信息）
- 命名约束：RPC 用 `*InputDTO/*OutputDTO`；Controller 用 `*InputVO/*OutputVO`
- 文档产物：仅当你明确要求输出设计/评审/方案/变更说明类文档时才创建，并统一存放到 `docs/ai/<moduleKey>/<featureKey>/`；同一主题固定文件名为 `<topic>.md`（后续迭代直接更新该文件），如需保留历史版本则把旧文件移动到 `docs/ai/<moduleKey>/<featureKey>/history/yyyyMMdd-HHmm-<topic>.md`；禁止散落在仓库根目录或模块根目录

---

## 0) AKSO 规范合规检查（查证 + 修复）

请基于 `.cursor/rules/01-backend/akso-framework-guide.mdc` 对以下代码做一次合规检查并直接修复：

- 目标范围：【[scope: 模块名/包名/类名/文件路径/方法名]】
- 关注点：【[focus: TenancyContext/soid 传递、事务边界、BeanMapper、分页规范、RPC 命名、日志规范、分布式ID DUID使用等]】

输出要求：

- 先列出不符合 Guide 的点（按文件路径 + 行号/方法名定位）
- 再直接修改仓库代码修复，并说明每一处修复对应的 Guide 条款
- 如涉及行为变更：补齐/更新必要的单元测试或最小可复现用例
- 文档产物（仅当你明确要求时）：统一存放到 `docs/ai/[module]/compliance/[scope]/`；同一主题固定为 `<topic>.md`，历史版本放 `docs/ai/[module]/compliance/[scope]/history/yyyyMMdd-HHmm-<topic>.md`

**使用示例**：
```
请基于 .cursor/rules/01-backend/akso-framework-guide.mdc 对以下代码做一次合规检查并直接修复：
- 目标范围：com.winning.demo.user.app.controller.UserController
- 关注点：TenancyContext/soid 传递、分页规范、日志规范
```

---

## 1) 新增 WebMVC Controller 接口（给前端）

请在模块【[module]】新增一个 Controller 接口【[apiName]】：

- 入参：`[apiName]InputVO`（继承 `WinMvcRequest` 或 `WinMvcQueryRequest`）
- 出参：`WinMvcResponse<[apiName]OutputVO>`
- soid 来源：【[soidSource: inputVO.getHospitalSOID() 或 BizContext.getCurrentHospitalSOID()]】

同时补齐：
- Service 接口与实现（`[apiName]Service`）
- 必要的校验、错误码/异常处理
- 文档产物（仅当你明确要求时）：统一存放到 `docs/ai/[module]/[apiName]/`；同一主题固定为 `<topic>.md`，历史版本放 `docs/ai/[module]/[apiName]/history/yyyyMMdd-HHmm-<topic>.md`

并声明：所有实现必须遵循 `.cursor/rules/01-backend/akso-framework-guide.mdc` 的 强制/推荐/禁止 规则。

**使用示例**：
```
请在模块【user】新增一个 Controller 接口【queryUserList】：
- 入参：queryUserListInputVO（继承 WinMvcQueryRequest）
- 出参：WinMvcResponse<queryUserListOutputVO>
- soid 来源：BizContext.getCurrentHospitalSOID()
```

**检查清单**：
- [ ] Controller 方法入口是否显式绑定租户上下文（TenancyContext.*WithSoid）
- [ ] 是否使用了 WinMvcResponse 包装返回值
- [ ] 是否引入了 winning-security-biz-webmvc 依赖（如果使用了 BizContext）
- [ ] 是否添加了必要的校验注解（@NotNull、@NotBlank 等）
- [ ] 是否添加了 @Schema 注解用于 API 文档

---

## 2) 新增 RPC/Feign Provider 接口（服务提供方）

请新增 RPC Provider 方法【[rpcMethod]】（模块【[module]】）：

- 请求：`[rpcMethod]InputDTO`（继承 `WinRpcRequest` 或 `WinRpcQueryRequest`）
- 响应：`WinRpcResponse<[rpcMethod]OutputDTO>`
- soid 来源：必须来自 `inputDTO.getHospitalSOID()`
- 文档产物（仅当你明确要求时）：统一存放到 `docs/ai/[module]/[rpcMethod]/`；同一主题固定为 `<topic>.md`，历史版本放 `docs/ai/[module]/[rpcMethod]/history/yyyyMMdd-HHmm-<topic>.md`

并声明：所有实现必须遵循 `.cursor/rules/01-backend/akso-framework-guide.mdc` 的 强制/推荐/禁止 规则。

**使用示例**：
```
请新增 RPC Provider 方法【getUserById】（模块【user】）：
- 请求：getUserByIdInputDTO（继承 WinRpcRequest）
- 响应：WinRpcResponse<getUserByIdOutputDTO>
- soid 来源：必须来自 inputDTO.getHospitalSOID()
```

**检查清单**：
- [ ] RPC Provider 方法入口是否显式绑定租户上下文（TenancyContext.*WithSoid）
- [ ] 是否使用了 @WinPostMapping 注解
- [ ] 是否使用了 WinRpcResponse 包装返回值
- [ ] soid 是否来自 inputDTO.getHospitalSOID()

---

## 3) 新增 RPC/Feign Consumer 调用封装（服务调用方）

请在模块【[module]】封装一次对【[targetService]】的 RPC 调用：

- 调用前必须显式把 `hospitalSOID` 写入 `*InputDTO`
- 返回值必须处理 `WinRpcResponse<T>`（成功/失败分支清晰）
- 如需并发聚合：必须用 `CompletableFutureBuilder` 的 **带 soid** 重载
- 文档产物（仅当你明确要求时）：统一存放到 `docs/ai/[module]/[targetService]/`；同一主题固定为 `<topic>.md`，历史版本放 `docs/ai/[module]/[targetService]/history/yyyyMMdd-HHmm-<topic>.md`

并声明：所有实现必须遵循 `.cursor/rules/01-backend/akso-framework-guide.mdc` 的 强制/推荐/禁止 规则。

**使用示例**：
```
请在模块【order】封装一次对【user】的 RPC 调用：
- 调用方法：getUserById
- 调用前必须显式把 hospitalSOID 写入 getUserByIdInputDTO
- 返回值必须处理 WinRpcResponse<getUserByIdOutputDTO>
```

**检查清单**：
- [ ] 调用前是否显式把 hospitalSOID 写入 InputDTO
- [ ] 是否处理了 WinRpcResponse 的成功/失败分支
- [ ] 如需并发，是否使用了 CompletableFutureBuilder 带 soid 的重载

---

## 4) 并发聚合 / 异步加速（改造现有逻辑）

请在模块【[module]】把【[existingMethod]】从串行改为并发聚合：

- 并发域：`Domain=[domain]`
- soid：`[soid]`
- 需要给出：超时策略、异常降级策略、租户维度日志（含 soid）
- 文档产物（仅当你明确要求时）：统一存放到 `docs/ai/[module]/[existingMethod]/`；同一主题固定为 `<topic>.md`，历史版本放 `docs/ai/[module]/[existingMethod]/history/yyyyMMdd-HHmm-<topic>.md`

并声明：所有实现必须遵循 `.cursor/rules/01-backend/akso-framework-guide.mdc` 的 强制/推荐/禁止 规则。

**使用示例**：
```
请在模块【order】把【queryOrderDetail】从串行改为并发聚合：
- 并发域：Domain.ORDER
- soid：从入参获取
- 需要给出：超时策略（5秒）、异常降级策略（返回部分数据）、租户维度日志（含 soid）
```

**检查清单**：
- [ ] 是否使用了 CompletableFutureBuilder 带 soid 的重载
- [ ] 是否指定了 Domain
- [ ] 是否设置了超时策略
- [ ] 是否处理了异常降级
- [ ] 日志是否包含 soid

---

## 5) 新增定时任务 / Xxl-Job

请新增 Xxl-Job 任务【[jobName]】：

- 租户驱动：`hospitalSOID` 列表来源【[soidListSource]】
- 幂等策略：【[idempotency]】
- 可选：补全 `@JobTriggerInfo` 元信息
- 文档产物（仅当你明确要求时）：统一存放到 `docs/ai/[module]/[jobName]/`；同一主题固定为 `<topic>.md`，历史版本放 `docs/ai/[module]/[jobName]/history/yyyyMMdd-HHmm-<topic>.md`

并声明：所有实现必须遵循 `.cursor/rules/01-backend/akso-framework-guide.mdc` 的 强制/推荐/禁止 规则。

**使用示例**：
```
请新增 Xxl-Job 任务【syncUserData】：
- 租户驱动：hospitalSOID 列表来源（从数据库查询所有激活的医院）
- 幂等策略：基于任务执行时间和 hospitalSOID 做幂等判断
- 补全 @JobTriggerInfo 元信息：cron="0 0 2 * * ?", desc="同步用户数据", auth="system"
```

**检查清单**：
- [ ] 任务入口是否按租户循环
- [ ] 每个租户执行体是否使用 TenancyContext.doWithSoid 包装
- [ ] 是否实现了幂等策略
- [ ] 是否添加了 @JobTriggerInfo 注解
- [ ] 失败日志是否包含 soid 和业务标识

---

## 6) 新增 Redis 缓存/暂存（Repository/Cache 层）

请在模块【[module]】新增 Redis Repository【[repoName]】：

- 缓存目标与口径：【[cachePurpose]】
- TTL 策略：【[ttlPolicy]】
- key 命名空间建议：【[keyNamespace]】
- 文档产物（仅当你明确要求时）：统一存放到 `docs/ai/[module]/[repoName]/`；同一主题固定为 `<topic>.md`，历史版本放 `docs/ai/[module]/[repoName]/history/yyyyMMdd-HHmm-<topic>.md`

并声明：所有实现必须遵循 `.cursor/rules/01-backend/akso-framework-guide.mdc` 的 强制/推荐/禁止 规则。

**使用示例**：
```
请在模块【user】新增 Redis Repository【UserCacheRepository】：
- 缓存目标与口径：缓存用户基本信息，减少数据库查询
- TTL 策略：1小时（3600000毫秒）
- key 命名空间建议：USER:INFO:{hospitalSOID}:{userId}
```

**检查清单**：
- [ ] Redis Key 是否包含 hospitalSOID（租户隔离）
- [ ] 写入是否设置了 TTL（单位：毫秒）
- [ ] 是否使用了 RedisAbility（而不是直接使用 RedisTemplate）
- [ ] 同一 key 下的值类型是否保持一致

---

## 7) 新增分布式锁（租户粒度 + 业务粒度）

请在模块【[module]】为【[bizScenario]】实现分布式锁：

- 锁粒度（biz/id）：【[lockKey]】
- expireMs 策略：【[expireMs]】
- 文档产物（仅当你明确要求时）：统一存放到 `docs/ai/[module]/[bizScenario]/`；同一主题固定为 `<topic>.md`，历史版本放 `docs/ai/[module]/[bizScenario]/history/yyyyMMdd-HHmm-<topic>.md`

并声明：所有实现必须遵循 `.cursor/rules/01-backend/akso-framework-guide.mdc` 的 强制/推荐/禁止 规则。

**使用示例**：
```
请在模块【order】为【创建订单】实现分布式锁：
- 锁粒度（biz/id）：ORDER:CREATE:{hospitalSOID}:{userId}
- expireMs 策略：5000毫秒（5秒）
```

**检查清单**：
- [ ] 是否使用了 RedisLocker（而不是自研锁）
- [ ] 是否设置了合理的 expireMs
- [ ] 是否在 finally 中解锁
- [ ] 锁粒度是否可审计（明确 biz + id/key）

---

## 8) 新增 ES 同步/检索（Search/Sync）

请在模块【[module]】为【[indexScenario]】实现 ES 同步/检索：

- 同步源：【[source]】
- 索引/字段隔离策略：【[tenancyStrategy]】
- 同步方式：全量/增量/滚动/批量【[syncMode]】
- 文档产物（仅当你明确要求时）：统一存放到 `docs/ai/[module]/[indexScenario]/`；同一主题固定为 `<topic>.md`，历史版本放 `docs/ai/[module]/[indexScenario]/history/yyyyMMdd-HHmm-<topic>.md`

并声明：所有实现必须遵循 `.cursor/rules/01-backend/akso-framework-guide.mdc` 的 强制/推荐/禁止 规则。

**使用示例**：
```
请在模块【user】为【用户信息检索】实现 ES 同步/检索：
- 同步源：数据库用户表
- 索引/字段隔离策略：文档字段包含 hospitalSOID，查询时带租户过滤
- 同步方式：增量同步（定时任务）
```

**检查清单**：
- [ ] 是否使用了 WinningElasticsearchTemplate（而不是原生 ES Client）
- [ ] 是否使用了基于实体 Class 的 API（避免手工拼 IndexCoordinates）
- [ ] 多租户隔离是否显式体现（索引命名隔离或文档字段隔离）
- [ ] 查询/删除/更新是否带租户过滤条件

---

## 9) 新增 JPA 查询（Repository/Specification）

请在模块【[module]】为实体【[entity]】新增查询【[queryName]】：

- 查询条件与分页排序：【[criteria]】
- 性能要求与索引建议：【[perf]】
- 文档产物（仅当你明确要求时）：统一存放到 `docs/ai/[module]/[queryName]/`；同一主题固定为 `<topic>.md`，历史版本放 `docs/ai/[module]/[queryName]/history/yyyyMMdd-HHmm-<topic>.md`

并声明：所有实现必须遵循 `.cursor/rules/01-backend/akso-framework-guide.mdc` 的 强制/推荐/禁止 规则。

**使用示例**：
```
请在模块【user】为实体【UserEntity】新增查询【queryByDepartment】：
- 查询条件与分页排序：按部门ID查询，支持分页，按创建时间倒序
- 性能要求与索引建议：建议在 departmentId 和 hospitalSOID 上建立联合索引
```

**检查清单**：
- [ ] 是否优先使用 @Query（HQL/JPQL）编写显式查询
- [ ] HQL/JPQL 中是否使用了 Entity 的全包名
- [ ] 查询是否显式包含租户过滤条件（hospitalSOID）
- [ ] 是否避免了循环数据库调用（优先使用批量查询）
- [ ] 分页是否遵循规范（pageNo 从 0 开始，仅首页返回准确 count）

---

## 10) 分层命名与对象转换（DTO/VO/BO/Entity）

请在模块【[module]】对【[feature]】做分层整理：

- RPC 入参/出参统一 `*InputDTO/*OutputDTO`
- Web 入参/出参统一 `*InputVO/*OutputVO`
- 内部业务对象用 `*BO`；持久化用 `*Entity`
- 对象转换默认使用 `BeanMapper`
- 文档产物（仅当你明确要求时）：统一存放到 `docs/ai/[module]/[feature]/`；同一主题固定为 `<topic>.md`，历史版本放 `docs/ai/[module]/[feature]/history/yyyyMMdd-HHmm-<topic>.md`

并声明：所有实现必须遵循 `.cursor/rules/01-backend/akso-framework-guide.mdc` 的 强制/推荐/禁止 规则。

**使用示例**：
```
请在模块【user】对【用户管理】做分层整理：
- RPC 入参/出参统一 *InputDTO/*OutputDTO
- Web 入参/出参统一 *InputVO/*OutputVO
- 内部业务对象用 *BO；持久化用 *Entity
- 对象转换默认使用 BeanMapper
```

**检查清单**：
- [ ] RPC 接口是否使用 *InputDTO/*OutputDTO 命名
- [ ] Web 接口是否使用 *InputVO/*OutputVO 命名
- [ ] 对象转换是否使用 BeanMapper
- [ ] 是否避免了 DTO/VO/BO/Entity 混用

---

## 11) 功能模块全流程（从需求到上线的"一条龙"模板）

> 适用：希望一次提示就让 AI 输出**完整落地方案**（功能设计、表结构、接口、服务、任务、缓存/ES 可选、测试与变更说明）。

请为功能模块【[featureName]】生成全流程实现方案并直接落地到代码（模块【[module]】）：

### 前置判断（两种情况，必须先判定再执行）

- 情况 A（目录已存在）：仓库中已经存在新增模块目录（例如 `winning-xxx-[newModule]`），或用户已通过工程内工具 `com.winning.tools.BlankModuleGenerator` 生成过空白模块。
  - 你只需要在该新增模块内工作（`winning-xxx-[newModule]-api/-itf/-dao/-app`），并检查 `winning-xxx-web` / `winning-xxx-version` 是否已接入（缺失则补齐）。
- 情况 B（目录不存在）：仓库中不存在新增模块目录。
  - 你必须先生成"空白模块骨架 + pom 接入"（优先使用 `com.winning.tools.BlankModuleGenerator` 的生成规则来创建同等结构），再开始业务实现。

### A. 功能与范围

- 背景/目标：【[why]】
- 业务范围（包含/不包含）：【[scope]】
- 关键术语与口径（字段含义、枚举值）：【[glossary]】

### B. 接口设计（必须给出清单）

- 前端接口（WebMVC）：列出接口清单（路径、方法、入参 `*InputVO`、出参 `*OutputVO`、错误码）
- 内部 RPC（如需要）：列出 RPC 清单（方法、`*InputDTO/*OutputDTO`、调用链路）
- soid/hospitalSOID：默认按 `.cursor/rules/01-backend/akso-framework-guide.mdc` 的入口规范执行；仅当存在"非标准入口/跨系统共享/特殊传递"时补充一段说明即可

### C. 数据模型与表结构（允许补全）

> 若你未给出表结构，允许 AI 提出建议，但必须标注"假设/可调整点"。

- 新增/修改表清单：【[tables]】
- 每张表字段（类型、约束、索引、是否租户字段）：【[ddlRequirements]】
- 迁移策略：脚本/兼容存量数据：【[migrationPlan]】

### D. 分层与职责边界

- 按 `.cursor/rules/01-backend/akso-framework-guide.mdc` 的模块分层：`*-api`（RPC 接口与 DTO）、`*-itf`（共享模型与 `Internal*` 接口）、`*-dao`（持久化与事务）、`*-app`（业务编排与接口入口）
- 按职责边界：Controller（入口适配）/ Service（业务编排，避免长事务）/ Repository（DAO 落库，事务在此层收敛）
- DTO/VO/BO/Entity 分层与命名必须遵循 Guide

### E. 关键非功能需求（必须逐条回应）

- 性能：热点路径、缓存策略（RedisAbility）、批量/分页
- 并发：是否需要并发聚合（CompletableFutureBuilder 带 soid）、超时与降级
- 多租户：所有入口与线程边界处理必须符合 Guide（事务开启后禁止切换 soid）
- 可观测：日志（必须带 soid）、关键指标、告警点
- 安全：敏感字段脱敏、权限边界（如有）

### F. 可选能力（按需启用）

- Redis：缓存/暂存/锁，key 命名空间与 TTL
- ES：索引/检索/同步，隔离策略
- Xxl-Job：定时任务，租户循环与幂等

### G. 交付物（必须输出）

- 新增/修改文件列表（含路径）
- 关键实现（Controller/RPC/Service/Repo/Job/Cache）
- 测试建议与必要用例
- 变更说明：配置项新增、回滚方式、上线注意事项

### H. 强化项（必须逐条自检并在输出中明确回应）

- 分页规范：所有分页查询必须按 Guide `3.9.7` 执行（`pageNo` 从 0 开始；仅首页返回准确 `count`，非首页 `count` 由框架强制为 `-1`）
- 循环调用治理：避免循环 RPC 调用与循环数据库调用；优先批量 RPC、批量查询（`in (:ids)` 需要限制 ids 长度并分批，默认单批不超过 `1000` 且可配置）、必要时使用连表查询（JPQL `join`/投影 DTO）减少往返，并明确说明 N+1 风险与取舍
- 版本/BOM 管理：如新增模块或新增依赖，必须把版本管理接入 `winning-**-version`（`dependencyManagement` 统一 import/管理），业务模块依赖声明不手写版本号
- 模块接入（新增模块必做）：当新增业务模块 `winning-xxx-[newModule]` 时，必须把 `winning-xxx-[newModule]-app` 加入 `winning-xxx-web` 的依赖中；并把该模块的 `*-api/*-itf/*-dao/*-app` 加入 `winning-xxx-version` 的 `dependencyManagement`（版本统一使用项目既有的业务版本 property）
- 文档产物（仅当你明确要求时）：统一存放到 `docs/ai/[module]/[featureName]/`；同一主题固定为 `<topic>.md`，历史版本放 `docs/ai/[module]/[featureName]/history/yyyyMMdd-HHmm-<topic>.md`

并声明：所有实现必须遵循 `.cursor/rules/01-backend/akso-framework-guide.mdc` 的 强制/推荐/禁止 规则。

**使用示例**：
```
请为功能模块【用户管理】生成全流程实现方案并直接落地到代码（模块【user】）：

### A. 功能与范围
- 背景/目标：提供用户的基本信息管理功能，包括查询、新增、修改、删除
- 业务范围（包含/不包含）：包含用户基本信息管理，不包含用户权限管理
- 关键术语与口径：用户ID使用DUID生成，用户状态：0-禁用，1-启用

### B. 接口设计
- 前端接口（WebMVC）：
  1. 查询用户列表：/api/v1/web/demo_test/user/query_list
  2. 新增用户：/api/v1/web/demo_test/user/save
  3. 修改用户：/api/v1/web/demo_test/user/update
  4. 删除用户：/api/v1/web/demo_test/user/delete

### C. 数据模型与表结构
- 新增表：t_user
- 字段：id(BIGINT,主键), hospital_soid(BIGINT,租户字段), username(VARCHAR), email(VARCHAR), status(INT)
- 索引：PRIMARY KEY(id), INDEX idx_hospital_soid(hospital_soid)
```

**检查清单**：
- [ ] 是否检查了模块目录是否存在
- [ ] 是否给出了完整的接口清单
- [ ] 是否设计了数据模型和表结构
- [ ] 是否遵循了模块分层规范
- [ ] 是否回应了所有非功能需求
- [ ] 是否检查了分页规范、循环调用治理、版本管理

---

## 相关规则文件

- [AKSO 框架使用指南](./akso-framework-guide.mdc) - 详细的框架使用规范和约束
- [后端规则索引](./README.md) - 后端规则文件索引和使用说明

---

> **维护者**：VibeCoding Team  
> **版本**：v1.0.0  
> **更新日期**：2025-01-XX

