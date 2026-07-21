# Auto-Dev 功能更新总结（2026-05-04 之后）

---

## 第一周（5月4日 - 5月10日）

### 功能更新

1. **需求分析任务创建机制**
   - PM 阶段自动创建 AI 分析任务，继承父需求的迭代路径和区域路径
   - 任务指派人支持优先级匹配，优先指派给当前用户
   - AI 分析任务添加 AI-ANALYSIS 标签，专业字段设为"分析"

2. **PR 创建工具切换**
   - PR 创建切换到 winning-pr 工具，评审走 bypass 模式
   - 移除自动构建任务注册及服务地址配置

3. **TFS 集合冲突修复**
   - 修复 TFS 集合 ID 冲突导致子 Agent 操作错误工作项的问题
   - 子任务创建参数修复，commit message 格式规范化

---

## 第二周（5月11日 - 5月17日）

### 功能更新

1. **可插拔流水线架构**
   - 实现 pipeline.yaml 配置驱动，支持动态技能映射
   - 添加 configure-pipeline.py 交互式配置向导
   - 流水线阶段数改为动态计算，移除硬编码 /8

2. **需求校验(req-verify)集成**
   - Stage 4 集成 req-verify 技能，实现需求→代码一致性校验
   - AI 分析任务增加需求总结部分，提升分析质量

3. **构建部署能力集成**
   - 集成 devops-workflow，Stage 6 实现自动构建触发与轮询
   - 工作项状态更新从 Stage 6 移到 Stage 5（PR 完成后）
   - 构建成功后自动更新 AI 开发任务和需求状态为已解决

---

## 第三周（5月18日 - 5月24日）

### 功能更新

1. **中间阶段提交禁止**
   - 编码/校验阶段禁止执行 git commit/push，只由 Stage 5 统一提交
   - 防止需求号混入 commit message，强制单次提交约束

2. **指数重试机制**
   - TFS 任务创建添加指数重试（5s/10s/20s），提升稳定性
   - MCP 预检查机制，AI-AUTO-DEV 标签阻塞检测

3. **单元测试阶段集成**
   - 集成 unit-test 阶段到可插拔流水线
   - 默认关闭 unit-test，统一为 6 阶段流水线

---

## 第四周（5月25日 - 5月31日）

### 功能更新

1. **v2.1 混合编排架构**
   - SKILL.md 重构为混合编排协议，支持主 Agent + 子 Agent 模式
   - stdin 传参替代环境变量，安全加固和权限细化
   - 新增 PM/Code/Verify 子 Agent 提示词模板

2. **MCP 协调脚本体系**
   - tfs-ops.py：TFS 工作项操作协调
   - pr-manager.py：PR 创建与轮询协调
   - build-manager.py：构建触发与轮询协调
   - deploy-manager.py：部署触发与轮询协调

3. **WinMetrics 事件埋点**
   - 集成 WinMetrics 事件上报，支持 pipeline/stage 级自动埋点
   - HMAC 签名机制，WM_SECRET 环境变量配置

---

## 第五周（6月1日 - 至今）

### 功能更新

1. **更新检查增强**
   - Step -1 添加 auto-dev 版本更新检查
   - 自动更新提示 + 三重警告机制
   - 流水线启动前强制版本一致性检查

---

## 5月15日之后汇总

### 核心功能更新

1. **流水线架构重构**
   - 可插拔流水线：pipeline.yaml 配置驱动，动态技能映射，6-8 阶段可配置
   - 混合编排模式：主 Agent 协调 + 子 Agent 执行，stdin 传参 + MCP 协调脚本
   - 禁止中间阶段提交，Stage 5 统一提交，指数重试 + MCP 预检查

2. **构建部署一体化**
   - devops-workflow 集成：构建触发/轮询 → 状态更新 → 部署触发
   - PR 创建切换 winning-pr 工具，bypass 模式评审
   - 工作项状态流转：需求 → AI开发任务 → 构建 → 部署 全链路自动化

3. **质量保障机制**
   - req-verify 集成：需求→代码一致性校验
   - WinMetrics 埋点：pipeline/stage 级事件上报 + HMAC 签名
   - 版本更新检查：流水线启动前强制一致性检查 + 三重警告

---

## 全部更新汇总

### 核心功能更新

1. **架构演进**
   - 单体流程 → 5阶段分步 → 可插拔流水线 → v2.1 混合编排
   - 配置驱动：pipeline.yaml + products.yaml + config.env 三层配置体系
   - MCP 协调脚本：tfs-ops/pr/build/deploy-manager.py 统一协调层

2. **自动化能力**
   - 任务创建：AI 分析任务 + AI 开发任务，迭代/区域路径继承，指数重试
   - PR 创建：winning-pr 工具 + bypass 评审 + 自动构建触发
   - 构建部署：devops-workflow 集成 + 状态轮询 + 工作项状态自动流转

3. **质量与安全**
   - req-verify 校验：需求→代码一致性验证
   - 中间阶段禁止提交：Stage 5 统一提交 + 单次提交约束
   - WinMetrics 埋点：事件上报 + HMAC 签名 + 流水线级追踪
   - 版本检查：启动前强制一致性检查 + 自动更新提示

---

## 附录：关键提交索引

| 日期 | 提交 | 功能 |
|------|------|------|
| 05-26 | c5cfe16 | v2.1 全面增强 — stdin 传参、安全加固、权限细化 |
| 05-25 | e491f97 | SKILL.md 重构为混合编排协议 |
| 05-14 | 87ebcd6 | pipeline.yaml 默认配置（8 阶段） |
| 05-12 | afadd25 | devops-workflow 集成构建部署能力 |
| 05-12 | 6be4442 | req-verify 集成到 auto-dev pipeline |
| 05-09 | 86c95f6 | PM 阶段创建 AI 分析任务 |
| 06-01 | 1155845 | update-check 增强 + 自动更新 + 三重警告 |