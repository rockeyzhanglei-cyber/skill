# Auto-Dev Bypass 策略表

auto-dev 全自动执行时，需要跳过各技能中的用户交互点。以下列出每个技能的 bypass 策略。

**技能名动态化说明**：从可插拔流水线改造后，技能名可能被团队替换（如 pm → pm-teamA）。
Bypass 策略按 **prefix 段** 组织（即下方 `## <prefix> bypass` 章节标题）。
自定义技能的 bypass 策略优先从技能目录下查找（如 `pm-teamA/bypass.md`），
找不到则使用对应 prefix 段的策略（如 `pm-teamA` → `## pm bypass` 段）。

## pm bypass

> **auto-dev 模式说明**：在 auto-dev 流水线中，PM 子代理受 `agent-pm.md` 约束，**禁止直接调用 TFS MCP 工具**。阶段 5（TFS 分析）和阶段 6（上传 TFS）由主代理统一处理。下表中的"TFS 分析/上传"策略仅适用于独立运行 PM 技能（非 auto-dev 模式）的场景。

| PM阶段 | 正常交互 | auto-dev策略 |
|--------|----------|-------------|
| 阶段0 获取需求 | AskUserQuestion确认需求内容 | **跳过**，直接用TFS工作项内容 |
| 阶段0.5 Wiki获取 | 无交互 | 正常执行 |
| 阶段0.6 创建AI分析任务 | 无交互 | 正常执行 |
| 阶段1 需求评估 | 无交互（内部评分） | 正常执行 |
| 阶段2 需求补充 | AskUserQuestion提问(最多10个) | **跳过**，不补充提问 |
| 阶段3 PRD设计 | 生成PRD后要求用户审阅 | **跳过审阅**，直接采纳 |
| 阶段4 原型设计 | AskUserQuestion选原型工具 | **跳过整个阶段** |
| 阶段5 TFS分析 | 无交互 | 正常执行 |
| 阶段6 上传TFS | AskUserQuestion确认 | **正常执行：字段+标签+附件全部执行** |
| 阶段6.5 完成AI分析任务 | 无交互 | 正常执行 |
| 清理阶段 | AskUserQuestion删除/保留过程文件 | **跳过**，auto-dev统一管理docs目录 |

## backend-dev bypass

| 步骤 | 正常交互 | auto-dev策略 |
|------|----------|-------------|
| Step 0 需求获取 | 获取TFS工作项 | **跳过**，从 dev-plan.md 读取 |
| Step 1 需求分析 | 读取CLAUDE.md | 正常执行 |
| Step 2 生成计划 | superpowers:writing-plans | 正常执行，保存到 docs/plans/ |
| Step 3 用户确认 | AskUserQuestion | **跳过**，自动确认 |
| Step 4 创建分支 | AskUserQuestion选分支名 | **跳过**，Step 0 已创建 feature 分支（worktree 或 inline 模式） |
| Step 5 编码实现 | 无交互 | 正常执行，**但禁止 git add/commit/push**（只修改文件） |
| Step 6 测试验证 | 无交互 | 正常执行 |
| Step 7 保存记录 | 无交互 | **跳过**（含 git commit，由 Step 4 统一提交） |
| Step 8 上传TFS | AskUserQuestion确认导出 | **跳过**，auto-dev统一处理 |

**⚠️ Git 操作隔离**：backend-dev 在 auto-dev 模式下**绝对禁止**执行 `git add`、`git commit`、`git push`。所有文件修改保留在工作区，由 Step 4（提交+PR）统一 add + commit + push。

## frontend-dev bypass

| 步骤 | 正常交互 | auto-dev策略 |
|------|----------|-------------|
| Step 0 需求获取 | 获取TFS工作项 | **跳过**，从 dev-plan.md 读取 |
| Step 1 分析+读取上下文 | 读取CLAUDE.md | 正常执行 |
| Step 2 权限约束检查 | 无交互 | 正常执行 |
| Step 3 生成计划 | superpowers:writing-plans | 正常执行 |
| Step 4 用户确认 | AskUserQuestion | **跳过**，自动确认 |
| Step 5 创建分支 | AskUserQuestion选子模块+分支名 | **跳过**，Step 0 已创建 feature 分支（worktree 或 inline 模式） |
| Step 6 编码实现 | 无交互 | 正常执行，**但禁止 git add/commit/push**（只修改文件） |
| Step 7 验证 | 无交互 | 正常执行 |
| Step 8 保存记录 | 无交互 | **跳过**（含 git commit，由 Step 4 统一提交） |
| Step 9 上传TFS | AskUserQuestion确认导出 | **跳过**，auto-dev统一处理 |

**⚠️ Git 操作隔离**：frontend-dev 在 auto-dev 模式下**绝对禁止**执行 `git add`、`git commit`、`git push`。

## rdf-dev bypass

| 步骤 | 正常交互 | auto-dev策略 |
|------|----------|-------------|
| Step 0 需求获取 | 获取TFS工作项 | **跳过**，从 dev-plan.md 读取 |
| Step 1 分析+确认项目 | AskUserQuestion确认目标项目 | **跳过**，从products.yaml读取 |
| Step 2 生成计划 | superpowers:writing-plans | 正常执行 |
| Step 3 用户确认 | AskUserQuestion | **跳过**，自动确认 |
| Step 4 创建分支 | AskUserQuestion选分支名 | **跳过**，Step 0 已创建 feature 分支（worktree 或 inline 模式） |
| Step 5 编码实现 | 无交互 | 正常执行，**但禁止 git add/commit/push**（只修改文件） |
| Step 6 验证 | 无交互 | 正常执行 |
| Step 7 保存记录 | 无交互 | **跳过**（含 git commit，由 Step 4 统一提交） |
| Step 8 上传TFS | AskUserQuestion确认导出 | **跳过**，auto-dev统一处理 |

**⚠️ Git 操作隔离**：rdf-dev 在 auto-dev 模式下**绝对禁止**执行 `git add`、`git commit`、`git push`。

## git-merge bypass

| git-merge步骤 | 正常交互 | auto-dev策略 |
|---------------|----------|-------------|
| Step 0 检测项目结构 | AskUserQuestion选择操作仓库 | **自动选择**，对products.yaml中涉及仓库逐一执行 |
| Step 1 检查工作区 | AskUserQuestion(提交/暂存/取消) | **自动提交**，不提供暂存/取消选项 |
| Step 2 关联TFS任务 | AskUserQuestion选任务号 | **跳过分支名解析**，直接使用 TASK_ID。不从分支名（如 feature/1611089）提取工作项 ID |
| Step 2.3 确认commit message | AskUserQuestion | **自动确认**，格式固定为 `#{TASK_ID} {DEMAND_TITLE}`。**严禁在 message 中包含需求号** |
| Step 2.5 提交执行 | 自动执行 | **只允许一次 git commit，禁止 git commit --amend** |
| Step 3 选择主分支 | AskUserQuestion | **从products.yaml读取** |
| Step 7 冲突处理 | AskUserQuestion选策略 | **保留本地版本(-X ours)** |
| Step 8 验证失败 | AskUserQuestion是否继续 | **自动继续，但在 result-marker.txt 中记录警告** |
| **Step 10 前分支保护检查** | **脚本自动检查** | **强制执行，不可 bypass**。检查当前分支是否为保护分支（products.yaml 中的 default_branch / repos[].branch），是则拒绝推送并报错退出 |
| Step 10 推送 | AskUserQuestion确认 | **自动推送**（仅当分支保护检查通过后） |

## devops-mcp bypass

PR 创建已改为通过 `mcp__devops-mcp__create_pr` 直接调用，无需 bypass 交互。Step 4 中直接指定参数，无 AskUserQuestion 环节。

## req-verify bypass

| req-verify步骤 | 正常交互 | auto-dev策略 |
|---------------|----------|-------------|
| Step 0 收集输入 | AskUserQuestion确认输入 | **跳过**，从 {DOCS_DIR} 自动读取 |
| Step 1 创建校验任务 | 无交互 | 正常执行 |
| Step 2 质疑循环 | 无交互（AI自问自答） | 正常执行 |
| Step 2.5 修复严重问题 | AskUserQuestion确认修复 | **自动修复，但禁止 git add/commit/push**（只修改文件，由 Step 4 统一提交） |
| Step 3 最终评定 | 无交互 | 正常执行 |
| Step 4 输出结果 | 无交互 | 正常执行 |

**⚠️ Git 操作隔离**：req-verify 在 auto-dev 模式下**绝对禁止**执行 `git add`、`git commit`、`git push`。修复严重问题时只修改文件，保留在工作区。

## unit-test bypass

| 步骤 | 正常交互 | auto-dev策略 |
|------|----------|-------------|
| Step 0 确定变更文件范围 | 用户提供变更文件列表 | **跳过**，自动从 dev-plan.md + summary.md 提取 |
| Step 1 检测测试框架 | 无交互 | 正常执行 |
| Step 2 生成测试代码 | AskUserQuestion确认生成 | **跳过**，自动确认，无需人工审核 |
| Step 3 执行测试 | 无交互 | 正常执行 |
| Step 4 自动修复失败用例 | 无交互 | 正常执行，最多 3 轮 |
| Step 5 生成覆盖率报告 | 无交互 | 正常执行 |
| Step 6 TFS 上传+打标签 | AskUserQuestion确认上传 | **跳过**，自动上传覆盖率报告 |
| Step 6.5 清理测试产物 | AskUserQuestion确认清理 | **跳过**，自动删除生成的测试文件和覆盖率产物 |

**⚠️ Git 操作隔离**：unit-test 在 auto-dev 模式下**绝对禁止**执行 `git add`、`git commit`、`git push`。生成的测试文件保留在工作区，由提交阶段统一处理。
