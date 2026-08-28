---
name: tfs-pr-skill
description: |
  TFS/Azure DevOps Pull Request 自动化工具。支持：1) 自动创建 PR - 识别当前分支、选择目标分支、关联工作项；2) 代码评审 - 代码质量分析 + 需求合规性检查；3) 评审结果发布到 PR 评论。

  触发场景：用户说"创建PR"、"帮我提交PR"、"代码评审"、"review PR"、"检查PR是否符合需求"、"分析这个PR"等。

  必须触发：用户提到 PR、Pull Request、代码评审、合并请求、分支合并，以及任何与 TFS/Azure DevOps PR 相关的操作。
metadata:
  author: 晁兴鹏
  version: 1.0.0
  openclaw:
    emoji: "🔀"
    user-invocable: true
---

# TFS Pull Request 自动化

集成 TFS MCP 工具，提供 Pull Request 自动创建和智能代码评审功能。

## 依赖要求

使用此 skill 需要以下条件：

1. **TFS MCP Server** - 需要配置并连接 TFS/Azure DevOps MCP 服务器
   - 提供以下 MCP 工具：`mcp__tfs-mcp__tfs_list_branches`, `mcp__tfs-mcp__tfs_get_pr`, `mcp__tfs-mcp__tfs_get_pr_diffs`, `mcp__tfs-mcp__tfs_get_pr_commits`, `mcp__tfs-mcp__tfs_get_pr_workitems`, `mcp__tfs-mcp__tfs_create_pr`, `mcp__tfs-mcp__tfs_add_pr_comment`
   - 如果工具不可用，提示用户检查 MCP 配置

2. **Git 命令行** - 用于获取本地仓库信息

---

## 功能概述

1. **自动创建 PR** - 识别当前分支，选择目标分支，关联工作项
2. **代码质量评审** - 代码可读性、最佳实践、潜在问题分析
3. **需求合规性检查** - 对照工作项需求验证代码实现
4. **评审结果发布** - 将评审报告发布到 PR 评论

---

## 一、创建 Pull Request（含自动评审）

### 步骤 1: 识别代码仓库和分支信息

获取当前代码仓库的信息：

```bash
# 获取当前分支名称
git branch --show-current

# 获取远程仓库 URL（用于识别 TFS 项目）
git remote get-url origin

# 获取最近的提交信息（用于生成 PR 标题）
git log -1 --pretty=format:"%s"
```

从远程 URL 中解析出：
- TFS 服务器地址
- **集合名称**（URL 中 `/tfs/{collection}/` 部分，如 `WinCode`、`WINNING-6.0`）
- 项目名称
- 仓库名称

**关键**：所有后续 MCP 调用必须传入 `collection` 参数（从 URL 提取的集合名称），避免使用默认集合导致仓库找不到。

**如果无法识别仓库信息**，使用 AskUserQuestion 请求用户手动输入。

### 步骤 2: 获取可用分支列表

使用 MCP 工具获取分支列表：

```javascript
mcp__tfs-mcp__tfs_list_branches({
  repositoryId: "<仓库名或ID>",
  project: "<项目名>",
  collection: "<集合名称>"
})
```

### 步骤 3: 获取并选择任务号（必须关联任务号才能创建 PR）

> **强制规则：必须关联至少一个任务号才能创建 PR。无任务号时禁止创建。**

#### 3a. 尝试自动提取需求 ID

按以下优先级从当前分支信息中提取需求 ID（数字）：

```bash
# 从分支名提取（如 feature/1506090-xxx → 1506090）
git branch --show-current | grep -oE '[0-9]{5,}'

# 从最近 10 条提交信息中提取（如 "feat: #1506090 实现xxx" → 1506090）
git log -10 --pretty=format:"%s" | grep -oE '[0-9]{5,}'
```

#### 3b. 获取需求下的子任务列表

如果提取到需求 ID，调用 MCP 工具获取子任务：

```javascript
mcp__tfs-mcp__tfs_get_relations({ id: <需求ID>, relationType: "children" })
```

对每个子任务，调用 `mcp__tfs-mcp__tfs_get_workitem({ id: <子任务ID> })` 获取任务标题和状态。

如果未提取到需求 ID，直接进入 3c 让用户手动输入。

#### 3c. 选择任务号（使用 AskUserQuestion）

根据是否有子任务列表，采用不同策略：

**有子任务列表时**，展示任务供用户多选：

```
AskUserQuestion:
  question: "请选择要关联的任务号（可多选）："
  options:
    - label: "#{taskId1} - {taskTitle1}"
      description: "状态: {state}"
    - label: "#{taskId2} - {taskTitle2}"
      description: "状态: {state}"
    - label: "手动输入任务号"
      description: "在 Other 中输入任务号，多个用逗号分隔"
  multiSelect: true
```

**无子任务列表时**，提示手动输入：

```
AskUserQuestion:
  question: "未检测到关联需求，请输入要关联的任务号："
  options:
    - label: "手动输入任务号"
      description: "在 Other 中输入任务号，多个用逗号分隔（如 1506090,1506091）"
    - label: "输入需求号查询子任务"
      description: "在 Other 中输入需求 ID，自动查询其下的子任务"
```

#### 3d. 校验任务号

- 如果用户通过"手动输入"提供了任务号，解析逗号分隔的数字列表
- 对每个任务号调用 `mcp__tfs-mcp__tfs_get_workitem({ id: <taskId> })` 验证有效性
- 无效的任务号提示用户确认

#### 3e. 强制校验

**如果最终任务号列表为空**：
```
❌ 必须关联至少一个任务号才能创建 PR。
- 请确认分支名或提交信息中包含需求/任务编号
- 或手动输入任务号
- 流程已终止，请重新发起创建 PR 并关联任务号
```

**流程终止，不继续执行后续步骤。**

### 步骤 4: 确认 PR 信息（使用 AskUserQuestion）

使用 AskUserQuestion 工具向用户确认 PR 信息。提供以下选项：

- **源分支**: 当前分支（自动检测，不可修改）
- **目标分支**: 从分支列表中选择，或提供常用分支（master/main/develop）
- **PR 标题**: 基于最近提交生成，用户可修改
- **PR 描述**: 可选，用户可添加
- **关联任务号**: 步骤 3 中选定的任务号列表（展示确认）

示例：
```
AskUserQuestion:
  question: "请确认 PR 信息："
  options:
    - label: "确认创建"
      description: "使用上述信息创建 PR（已关联 N 个任务号）"
    - label: "修改标题/描述"
      description: "在 Other 中输入新的标题或描述"
    - label: "取消"
      description: "取消创建 PR"
```

### 步骤 5: 创建 PR

使用 MCP 工具创建 PR，**必须传入步骤 3 中选定的任务号列表**：

```javascript
mcp__tfs-mcp__tfs_create_pr({
  repositoryId: "<仓库名或ID>",
  project: "<项目名>",
  collection: "<集合名称>",
  sourceRefName: "refs/heads/{源分支}",
  targetRefName: "refs/heads/{目标分支}",
  title: "<PR标题>",
  description: "<PR描述>",
  workItems: [/* 步骤 3 中用户选定的任务号 ID 列表 */]
})
```

创建成功后，**修正 webUrl 中的集合名称**（TFS 返回的 webUrl 默认使用用户默认集合，需替换为实际的 collection 参数）：

```python
# 将 webUrl 中的默认集合替换为实际集合
# 例如: .../tfs/WINNING-6.0/Skill/_git/... → .../tfs/WinCode/Skill/_git/...
corrected_webUrl = webUrl.replace(f"/tfs/{default_collection}/", f"/tfs/{collection}/")
```

返回 PR 链接供用户访问：

```
✅ PR 创建成功！
- PR 编号: #{pullRequestId}
- PR 标题: {title}
- 关联任务: #{taskId1}, #{taskId2}, ...
- 链接: {corrected_webUrl}
```

### 步骤 6: 自动进入代码评审

**创建 PR 成功后，自动进入代码评审流程，不需要询问用户。**

使用已获取的信息直接进入评审：
- repositoryId（已获取）
- project（已获取）
- pullRequestId（刚创建的 PR ID）

**直接跳转到「二、代码评审」的「步骤 2: 获取 PR 信息」继续执行。**

---

## 二、代码评审

代码评审包含两个部分：**代码质量分析** 和 **需求合规性检查**。

### 场景判断

在开始代码评审前，判断当前场景：

| 场景 | 触发条件 | 处理方式 |
|------|----------|----------|
| **场景 A：刚创建 PR** | 从「创建 PR」流程自动进入 | 直接使用已有信息，跳到步骤 2 |
| **场景 B：用户提供 PR 地址** | 用户输入包含 PR URL | 从 URL 解析信息后，跳到步骤 2 |
| **场景 C：用户指定 PR ID** | 用户说"评审 PR 123" | 从步骤 1 开始 |
| **场景 D：无明确信息** | 用户只说"评审 PR" | 从步骤 1 开始，询问用户 |

**URL 解析规则**：
```
页面地址格式：{server}/{collection}/{project}/_git/{repo}/pullrequest/{prId}?_a=overview
API 地址格式：{server}/{collection}/_apis/git/repositories/{repoId}/pullRequests/{prId}
```
从 URL 中提取：collection、project、repositoryId/repositoryName、pullRequestId

### 步骤 1: 确定 PR ID（仅场景 C/D）

**如果是从场景 A 或 B 进入，跳过此步骤。**

按以下优先级获取 pullRequestId 和仓库信息：

1. **用户明确指定 PR ID** - 从用户输入中提取（如 "评审 PR #123" 或 "评审 PR 123"）
2. **当前分支关联** - 查询当前分支是否有关联的 PR
3. **询问用户** - 如果以上都无法获取，使用 AskUserQuestion 询问

如果无法自动获取仓库信息（repositoryId, project），需要通过 git 命令解析或询问用户。

### 步骤 2: 获取 PR 信息

```javascript
mcp__tfs-mcp__tfs_get_pr({
  repositoryId: "<仓库名或ID>",
  project: "<项目名>",
  collection: "<集合名称>",
  pullRequestId: <PR编号>
})
```

### 步骤 3: 获取代码变更

```javascript
mcp__tfs-mcp__tfs_get_pr_diffs({
  repositoryId: "<仓库名或ID>",
  project: "<项目名>",
  collection: "<集合名称>",
  pullRequestId: <PR编号>
})

mcp__tfs-mcp__tfs_get_pr_commits({
  repositoryId: "<仓库名或ID>",
  project: "<项目名>",
  collection: "<集合名称>",
  pullRequestId: <PR编号>
})
```

### 步骤 4: 获取关联工作项

```javascript
mcp__tfs-mcp__tfs_get_pr_workitems({
  repositoryId: "<仓库名或ID>",
  project: "<项目名>",
  collection: "<集合名称>",
  pullRequestId: <PR编号>
})
```

如果有关联的工作项，获取其需求描述和验收标准。

**如果 PR 没有关联工作项**：
- 使用 AskUserQuestion 询问用户是否要提供需求描述进行合规性检查
- 如果用户不提供，仅进行代码质量评审

---

## 三、代码质量分析

对代码变更进行以下维度的分析：

### 分析维度

#### 1. 代码质量
- **可读性**: 命名规范、代码结构、注释完整性
- **复杂度**: 圈复杂度、方法长度、嵌套深度
- **重复代码**: 是否存在可提取的公共逻辑

#### 2. 最佳实践
- **SOLID 原则**: 单一职责、开闭原则等
- **设计模式**: 是否合理使用设计模式
- **错误处理**: 异常处理是否完善
- **资源管理**: 资源是否正确释放

#### 3. 潜在问题
- **Bug 风险**: 边界条件、空指针、类型错误
- **安全漏洞**: SQL 注入、XSS、敏感信息泄露
- **性能问题**: 循环效率、内存泄漏、数据库查询优化

#### 4. 改进建议
- 具体的改进建议
- 可选的替代方案
- 重构机会

### 评分标准

| 分数 | 等级 | 描述 |
|------|------|------|
| 9-10 | 优秀 | 代码质量高，无需改进，可直接合并 |
| 7-8 | 良好 | 整体质量不错，有小的改进空间 |
| 5-6 | 一般 | 代码可用，但存在明显问题需要改进 |
| 3-4 | 较差 | 存在较多问题，需要重大修改 |
| 1-2 | 不可接受 | 代码质量严重不达标，建议重写 |

评分依据：
- 无明显问题 + 有亮点 → 8-10 分
- 存在 1-2 个小问题 → 6-7 分
- 存在明显问题但不影响功能 → 4-5 分
- 存在严重问题（安全/性能/bug）→ 1-3 分

---

## 四、需求合规性检查

对照工作项需求，验证代码实现是否满足需求。

### 检查维度

1. **功能完整性**: 需求描述的功能是否都已实现
2. **验收标准**: 验收标准是否都已满足
3. **实现符合度**: 实现方式是否符合需求描述

### 合规性状态

| 状态 | 图标 | 判定逻辑 |
|------|------|----------|
| 完全符合 | ✅ | 所有需求都已实现，无明显偏差 |
| 部分符合 | ⚠️ | 部分需求已实现，有未完成项 |
| 不符合 | ❌ | 代码实现与需求不符或缺失关键功能 |
| 待验证 | 🔍 | 需要人工验证的内容（如 UI 交互、业务流程） |

---

## 五、评审报告格式

评审完成后，生成以下格式的报告：

```markdown
# 代码评审报告

## PR 信息
- **PR 标题**: {title}
- **PR 编号**: #{pullRequestId}
- **源分支**: {sourceRefName}
- **目标分支**: {targetRefName}
- **提交数量**: {commitCount}
- **变更文件**: {fileCount} 个文件

---

## 代码质量评审

### 整体评分: {score}/10 ({等级})

### 优点
- {具体优点，附代码位置引用}

### 需改进项
- {改进建议，附代码位置引用}

### 潜在问题
- {问题描述，严重程度，建议修复方式}

### 改进建议
- {具体可操作的建议}

---

## 需求合规性检查

### 关联工作项

| 任务号 | 标题 | 状态 |
|--------|------|------|
| #{workItemId1} | {workItemTitle1} | ✅ |
| #{workItemId2} | {workItemTitle2} | ⚠️ |

（如有多个关联工作项，逐个列出）

#### 工作项 #{workItemId} - {workItemTitle}

| 需求点 | 状态 | 说明 |
|--------|------|------|
| {需求1} | ✅ | 已实现，位于 {文件:行号} |
| {需求2} | ⚠️ | 部分实现，缺少 {具体内容} |

### 合规性结论: {complianceStatus}

---

## 总结

{评审总结，包含：整体评价、是否建议合并、后续行动项}
```

---

## 六、发布评审结果

评审完成后，使用 MCP 工具将评审报告发布到 PR 评论：

```javascript
mcp__tfs-mcp__tfs_add_pr_comment({
  repositoryId: "<仓库名或ID>",
  project: "<项目名>",
  collection: "<集合名称>",
  pullRequestId: <PR编号>,
  content: "评审报告内容（Markdown格式）"
})
```

发布前使用 AskUserQuestion 确认：
```
AskUserQuestion:
  question: "评审完成，是否将结果发布到 PR 评论？"
  options:
    - label: "发布到 PR（推荐）"
      description: "将评审报告作为评论发布"
    - label: "仅在对话中显示"
      description: "不发布到 PR，只在当前对话中展示"
```

同时在对话中展示评审结果摘要。

---

## 注意事项

1. **评审范围**: 专注于有意义的代码变更，忽略格式化、注释等非功能性变更
2. **评审深度**: 对于大型 PR（>20个文件），重点关注核心业务逻辑，询问用户是否需要完整评审
3. **建设性反馈**: 提供具体、可操作的改进建议，指出代码位置
4. **需求对照**: 始终以工作项需求为基准进行合规性检查
5. **评论格式**: 使用 Markdown 格式，便于阅读

---

## 错误处理

| 场景 | 处理方式 |
|------|----------|
| 无法识别仓库信息 | 使用 AskUserQuestion 请求用户手动指定项目名和仓库名 |
| MCP 工具不可用 | 提示用户检查 TFS MCP Server 配置 |
| PR 不存在 | 告知用户 PR ID 无效，请求确认 |
| PR 没有关联工作项 | 询问用户是否提供需求描述，否则仅进行代码质量评审 |
| 未关联任务号（创建时） | **禁止创建 PR**，提示用户必须关联至少一个任务号，流程终止 |
| 发布评论失败 | 在对话中展示完整评审结果，提示用户手动添加到 PR |
| 代码变更过大 | 询问用户是否需要完整评审，或只关注核心文件 |

---

## 📋 工作总结（必须执行）

**在完成 PR 创建或代码评审后，必须输出以下工作总结：**

```markdown
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 TFS PR 操作总结
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## ✅ 已完成的工作

### PR 信息
- **PR 编号**: #[pullRequestId]
- **PR 标题**: [title]
- **源分支**: [sourceRefName]
- **目标分支**: [targetRefName]
- **关联工作项**: #[taskId1], #[taskId2], ...（多个用逗号分隔）

### 操作记录
| 步骤 | 状态 | 说明 |
|------|------|------|
| PR 创建 | ✅/跳过 | [创建成功/已存在] |
| 代码获取 | ✅ | [X个文件变更] |
| 工作项获取 | ✅/⚠️ | [已获取/无关联] |
| 代码评审 | ✅/跳过 | [完成/用户跳过] |
| 结果发布 | ✅/跳过 | [已发布到PR/仅在对话显示] |

### 代码评审结果（如执行）
- **质量评分**: [X]/10 ([等级])
- **合规性**: ✅完全符合 / ⚠️部分符合 / ❌不符合
- **主要问题**: [问题摘要，如无则填"无"]

### 关键发现
- **优点**: [列出代码优点]
- **需改进项**: [列出改进建议]
- **潜在问题**: [列出潜在风险]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 💡 后续建议

- **处理评审意见**: 根据评审结果修改代码
- **合并 PR**: 确认无误后合并到目标分支
- **持续跟进**: 关注 PR 的审核状态

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```
