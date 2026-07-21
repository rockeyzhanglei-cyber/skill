---
name: auto-dev
description: |
  全自动开发流水线 - 从需求分析到代码提交一站式完成。
  输入 TFS 工作项 ID，自动调度 pipeline.yaml 中配置的技能链（默认 prepare→pm→code→verify→submit→build→deploy→report）。
  支持单工作项和批量处理。

  **必须触发（自动开发）**（包含以下任一即触发）：
  - "自动开发" + 数字：如"自动开发 1506090"、"全自动开发需求 1506090"
  - "auto-dev"、"自动流水线"、"全自动流水线"、"批量开发"
  - "接需求" + 自动/全自动：如"自动接需求"、"自动接单"
  - 用户明确要求全链路处理（PM分析+编码+提交+PR 一站式完成）

  **不要触发**（由 backend-dev/frontend-dev/rdf-dev 单技能处理）：
  - "开发需求 1506090"、"帮我开发 1506090"（无"自动"前缀 → 走单技能）
  - "实现接口"、"写个页面"等单一开发任务

  **WinMetrics 补发**（由 winmetrics-retry skill 处理）：
  - "WinMetrics 补发"、"补发事件"、"事件重试"等关键词
  - 请使用独立的 winmetrics-retry skill

  **依赖技能**：pm, backend-dev, frontend-dev, rdf-dev, req-verify, git-merge, devops-mcp, winmetrics-retry（以 pipeline.yaml 实际配置为准）
tags: [研发, DevOps, 工具]
keywords: 自动开发 全自动开发 自动流水线 全自动流水线 批量开发 auto-dev 全链路 需求开发 自动接单 TFS工作项 一站式开发 PM分析 自动评审 worktree
metadata:
  author: 晁兴鹏
  version: 2.2.0
---

# Auto-Dev 全链路自动化开发（混合编排模式 + OpenSpec/Superpowers 集成）

## 概述

主代理作为流水线编排器，通过脚本处理确定性操作，通过子代理处理推理任务。

集成 OpenSpec（规格闸门）和 Superpowers（执行纪律）：

```
主代理（读 SKILL.md → 编排）
  ├─ Preflight: 环境检测（强制检测 OpenSpec + Superpowers）
  ├─ Step 0: 准备（脚本 + MCP）
  ├─ Step 0.5: Spec 规格生成（子代理，生成 OpenSpec 资产）
  ├─ Step 1: PM 分析（子代理，消费 OpenSpec）
  ├─ Step 2: 代码开发（子代理，内部调用 Superpowers skill）
  ├─ Step 3: 需求校验（子代理，内部调用 Superpowers skill）
  ├─ Step 3.5: 单元测试（可选，脚本驱动）
  ├─ Step 3.6: 清理 dev-plan.md
  ├─ Step 4: 提交+PR（脚本 + MCP）
  ├─ Step 5: 构建（脚本 + MCP）
  ├─ Step 6: 部署（脚本 + MCP）
  └─ Step 7: 报告（脚本 + MCP）
```

**OpenSpec 作用**：规格闸门 + 可追溯需求资产（proposal/design/tasks）
**Superpowers 作用**：编码和校验阶段的执行纪律（TDD/系统化调试/自查）

## ⚠️ WinMetrics 事件上报（强制执行）

**所有 WinMetrics 事件上报必须按以下时机执行，不可跳过或延迟。**

### 事件类型与执行时机

| 时机 | 事件名称 | 命令 | 必须执行 |
|------|----------|------|----------|
| Preflight 前无事件（无 DOCS_DIR） | - | - | - |
| Step 0.13 | pipeline.queued | `winmetrics-report.py pipeline-event --name pipeline.queued` | ✅ |
| Step 0.13 | pipeline.started | `winmetrics-report.py pipeline-event --name pipeline.started` | ✅ |
| Step 0.5 开始 | stage.started (spec) | `winmetrics-report.py stage-start --stage spec` | ✅ |
| Step 0.5 结束 | stage.completed (spec) | `winmetrics-report.py stage-complete --stage spec` | ✅ |
| Step 1 开始 | stage.started (pm) | `winmetrics-report.py stage-start --stage pm` | ✅ |
| Step 1 结束 | stage.completed (pm) | `winmetrics-report.py stage-complete --stage pm` | ✅ |
| Step 2 开始 | stage.started (code) | `winmetrics-report.py stage-start --stage code` | ✅ |
| Step 2 结束 | stage.completed (code) | `winmetrics-report.py stage-complete --stage code` | ✅ |
| Step 3 开始 | stage.started (verify) | `winmetrics-report.py stage-start --stage verify` | ✅ |
| Step 3 结束 | stage.completed (verify) | `winmetrics-report.py stage-complete --stage verify` | ✅ |
| Step 4 开始 | stage.started (submit) | `winmetrics-report.py stage-start --stage submit` | ✅ |
| Step 4 结束 | stage.completed (submit) | `winmetrics-report.py stage-complete --stage submit` | ✅ |
| Step 5 开始 | stage.started (build) | `winmetrics-report.py stage-start --stage build` | ✅ |
| Step 5 结束 | stage.completed (build) | `winmetrics-report.py stage-complete --stage build` | ✅ |
| Step 6 开始 | stage.started (deploy) | `winmetrics-report.py stage-start --stage deploy` | ✅ |
| Step 6 结束 | stage.completed (deploy) | `winmetrics-report.py stage-complete --stage deploy` | ✅ |
| Step 7 开始 | stage.started (report) | `winmetrics-report.py stage-start --stage report` | ✅ |
| Step 7 结束 | stage.completed (report) | `winmetrics-report.py stage-complete --stage report` | ✅ |
| Step 7.6 | retry-fallback | `winmetrics-report.py retry-fallback` | ✅ |
| Step 7.7 | pipeline.completed | `winmetrics-report.py summary` | ✅ |

### 强制执行规则

1. **阶段开始时**：必须在启动子代理或执行操作前调用 `stage-start`
2. **阶段结束时**：必须在阶段完成后立即调用 `stage-complete`（包含 duration 参数）
3. **流水线终态**：必须在 Step 7.7 发送 `pipeline.completed` 或 `pipeline.fallback`
4. **失败处理**：任何阶段失败时调用 `stage-failed`
5. **fallback 重试**：Step 7.6 必须执行 `retry-fallback` 确保所有事件发送

### 发送失败处理

如果 WinMetrics API 发送失败，事件会自动保存到 `{DOCS_DIR}/.wm-events.json` fallback 文件。Step 7.6 的 `retry-fallback` 会重试发送所有失败事件。

### 人工处理补发流程

当流水线某个阶段失败后，用户人工处理完成（如处理前置需求、手动创建PR等），需要补发成功状态的 WinMetrics 事件。

**触发场景**：
- 用户说："已人工处理完成"
- 用户说："WinMetrics 补发成功状态"
- 用户说："更新状态为成功"

**执行脚本**：
```bash
python scripts/winmetrics-manual-complete.py \
  --demand-id {DEMAND_ID} \
  --stage {失败阶段} \
  --docs-dir {DOCS_DIR}
```

**支持阶段**：
- `submit`: 提交+PR阶段（失败标记：`.pr-create-failed`）
- `build`: 构建阶段（失败标记：`.build-failed`）
- `deploy`: 部署阶段（失败标记：`.deploy-failed`）
- `verify`: 验证阶段（失败标记：`.verify-failed`）

**脚本执行流程**：
1. 更新状态文件（`.pr-status`/`.build-status`等）为 `success`
2. 删除失败标记文件（`.pr-create-failed`等）
3. 追加日志：`人工处理完成，状态已更新为success`
4. 补发 WinMetrics 事件：
   - `stage.completed ({stage}, status=success)`
   - `pipeline.completed`

**示例**：
```bash
# 需求1651457的submit阶段人工处理完成
python scripts/winmetrics-manual-complete.py \
  --demand-id 1651457 \
  --stage submit \
  --docs-dir "C:/Users/lenovo/auto-dev-docs/统一登录/1651457"
```

**输出**：
```json
{
  "demand_id": 1651457,
  "stage": "submit",
  "docs_dir": "C:/Users/lenovo/auto-dev-docs/统一登录/1651457",
  "status": "success",
  "winmetrics_sent": true
}
```

## 标签体系

| 标签 | 含义 | 路由策略 |
|------|------|----------|
| `AI-AUTO-DEV` | **必须有** | - |
| `AI-BACKEND` | 后端任务 | 只处理 backend-dev 仓库 |
| `AI-FRONTEND` | 前端任务 | 只处理 frontend-dev 仓库 |
| `AI-RDF` | RDF快开任务 | 只处理 rdf-dev 仓库 |
| `AI-FULLSTACK` | 全栈 | 按技能串行：code→frontend→rdf（每组内独立执行） |

## Git 操作隔离

| 阶段 | git add | git commit | git push | git fetch |
|------|---------|-----------|----------|-----------|
| Preflight | ❌ | ❌ | ❌ | ❌ |
| 准备 | ❌ | ❌ | ❌ | ✅ |
| Spec 规格生成 | ❌ | ❌ | ❌ | ❌ |
| PM 分析 | ❌ | ❌ | ❌ | ❌ |
| 代码开发 | ❌ | ❌ | ❌ | ❌ |
| 需求校验 | ❌ | ❌ | ❌ | ❌ |
| 单元测试 | ❌ | ❌ | ❌ | ❌ |
| 提交+PR | ✅ | ✅ | ✅ | ✅ |
| 构建/部署/报告 | ❌ | ❌ | ❌ | ❌ |

## 日志约定

流水线运行时通过 `stage-helper.py log` 向 `{DOCS_DIR}/auto-dev.log` 追加操作日志。

**日志调用简写**：下文中的 `LOG {STAGE} {message}` 等价于：
```bash
$PYTHON SKILL_DIR/scripts/stage-helper.py log --log-file {DOCS_DIR}/auto-dev.log --stage "{STAGE}" --message "{message}"
```
- INFO 级别（默认，无需显式指定）：
  ```bash
  $PYTHON SKILL_DIR/scripts/stage-helper.py log --log-file {DOCS_DIR}/auto-dev.log --stage "{STAGE}" --message "{message}"
  ```
- WARN 级别（显式添加 `--level WARN`）：
  ```bash
  $PYTHON SKILL_DIR/scripts/stage-helper.py log --log-file {DOCS_DIR}/auto-dev.log --level WARN --stage "{STAGE}" --message "{message}"
  ```
- ERROR 级别（显式添加 `--level ERROR`）：
  ```bash
  $PYTHON SKILL_DIR/scripts/stage-helper.py log --log-file {DOCS_DIR}/auto-dev.log --level ERROR --stage "{STAGE}" --message "{message}"
  ```

**阶段级日志**（阶段开始/完成、WinMetrics 事件）由 `winmetrics-report.py` 自动追加，无需手动调用。

## 目录结构

**双路径策略**：OpenSpec 文档同时在项目目录（用户可编辑）和 DOCS_DIR（流水线归档）生成。

```
{PROJECT_DIR}/openspec/changes/tfs-{DEMAND_ID}/  ← 项目目录（用户可见、可编辑，优先）
  ├── proposal.md   ← 需求提案
  ├── design.md     ← 技术设计
  ├── tasks.md      ← 实现任务分解
  └── specs/        ← 可选详细规格

${HOME:-$USERPROFILE}/auto-dev-docs/{产品名}/{需求号}/  ← 集中文档目录（流水线归档）
  ├── 附件/                  ← TFS 工作项附件（PRD、原型图等）
  ├── openspec/              ← OpenSpec 规格资产（同步副本）
  │   ├── changes/
  │   │   └── tfs-{DEMAND_ID}/
  │   │       ├── proposal.md   ← 同步自项目目录
  │   │       ├── design.md     ← 同步自项目目录
  │   │       ├── tasks.md      ← 同步自项目目录
  │   │       └── specs/        ← 同步自项目目录
  ├── auto-dev.log           ← 操作日志
  ├── dev-plan.md            ← 开发计划(PM产出)
  ├── summary.md             ← 编码总结
  ├── verify-report.md       ← 校验报告
  ├── ai-report.md           ← AI报告
  ├── .spec-status           ← Spec 状态(pass/fail/confirmed)
  ├── .spec-confirmed        ← 用户确认标记（人工确认后写入）
  ├── .analysis-task-id      ← AI分析任务ID
  ├── .task-id               ← Task ID
  ├── .verify-status         ← 校验状态(pass/warn/fail)
  ├── .verify-task-id        ← 校验任务ID
  ├── .pr-status             ← PR流水线状态
  ├── .build-status          ← 构建状态
  ├── .deploy-status         ← 部署状态
  ├── .unit-test-result      ← 单元测试结果
  ├── .dev-assigned-to       ← 需求开发负责人（WinMetrics account字段）
  ├── AI-UNIT-TEST-*.md      ← 单元测试覆盖率报告
  ├── .total-diff            ← 提交差异统计
  ├── .repos                 ← 仓库列表
  ├── .repo-collection       ← 仓库TFS集合
  ├── .deploy-env-id         ← 部署环境ID
  ├── .deploy-step-id        ← 部署步骤ID
  ├── .lock                  ← 并发锁
  ├── .wm-events.json       ← WinMetrics回退事件
  ├── .task-degraded         ← 降级标记（Task 创建失败时写入）
  ├── .degradation-reason    ← 降级原因
  ├── .pr-create-failed      ← PR 创建失败记录
  ├── .pr-review.md          ← PR 评审结果
  ├── .test-task-id          ← 人工测试任务ID
  ├── success-ext.json       ← 成功通知扩展数据
  ├── fail-ext.json          ← 失败通知扩展数据
  ├── result-marker.txt      ← 最终结果
  └── {stage}-done.json      ← 子代理完成信号（JSON格式）

${HOME:-$USERPROFILE}/auto-dev-docs/.batch/  ← 批量模式临时目录
  ├── start.json             ← 批量启动通知数据
  └── summary.json           ← 批量汇总通知数据

两种文件系统：
1. 阶段完成信号：{stage}-done.json — 子代理完成标记（JSON）
2. 流水线状态文件：.verify-status, .pr-status 等 — 主代理在编排过程中写入（纯文本）

SKILL_DIR/
  ├── SKILL.md
  ├── config.env
  ├── prompts/agents/         ← 子代理 prompt
  ├── prompts/snippets/       ← 可复用片段
  ├── references/             ← 参考文档
  ├── templates/              ← 配置模板
  └── scripts/                ← 操作脚本
```

---

## MCP 编排协议

### MCP_CALL（单次调用）

1. 执行脚本，脚本输出到 stdout：`MCP_CALL: <tool_name> <json_params>`
2. 主代理解析 tool_name 和 params
3. 主代理执行对应的 MCP 工具调用
4. 主代理将返回结果通过 stdin 传给解析命令（优先）：
   ```bash
   $PYTHON SKILL_DIR/scripts/<script>.py parse-<command> --result-stdin <<'JSONEOF'
   {MCP 返回的 JSON 结果}
   JSONEOF
   ```
   **关键**：`<command>` 是脚本中**实际的命令名**（如 `get-workitem`），不是操作对象名。
   例如：执行 `tfs-ops.py get-workitem` → 解析命令是 `parse-get-workitem`（不是 `parse-workitem`）
   备选：`--result-file <path>`（需要写临时文件时使用）
5. **注意**：`--result-stdin` 内置 JSON 反斜杠修复，`--result-file` 同样支持

### MCP_CALL_POLL（轮询调用）

1. 执行脚本，脚本输出：`MCP_CALL_POLL: <tool_name> <json_params>` + 轮询参数行
2. 主代理按 interval 间隔循环执行 MCP 调用（如有 initial_wait 先等待）
3. 每次将结果通过 `--result-stdin` 传给 `parse-poll`（同上协议）判断是否到达终态
4. 终态或超时后继续下一步
5. **轮询期间如 MCP 调用返回错误或空数据，立即停止轮询并标记为失败（不重试）**

### 错误分级

| 代码 | 行为 | 退出码 |
|------|------|--------|
| E001 | 自动重试 3 次 | 1 |
| E002 | 暂停并通知用户 | 2 |
| E003 | 立即终止流水线 | 3 |

### 强制约束：工具选择

**TFS 工作项操作（创建/更新/标签/评论/附件/关联）**：必须通过 `tfs-ops.py` 脚本调用。禁止直接调用 `mcp__tfs-mcp__tfs_create_workitem`、`mcp__tfs-mcp__tfs_update_workitem`、`mcp__tfs-mcp__tfs_add_tags`、`mcp__tfs-mcp__tfs_add_comment` 等 MCP 工具。

**TFS 状态变更**：必须通过 `tfs-ops.py update-state` 脚本调用。禁止直接调用 `mcp__tfs-mcp__tfs_change_state`。

**PR 创建**：唯一允许 `mcp__devops-mcp__create_pr`。禁止使用 `mcp__tfs-mcp__tfs_create_pr`。devops-mcp 失败后禁止回退到 tfs-mcp。

**违反以上约束会导致参数格式错误、字段缺失、迭代路径丢失等问题。**

---

## 子代理启动协议

### Prompt 组装方式：纯模板展开（不做追加拼接）

1. 读取 `SKILL_DIR/prompts/agents/agent-{stage}.md` 主 prompt 文件
2. 读取需要注入的 snippet 文件内容
3. 在主 prompt 中搜索占位符，替换为对应 snippet 内容
4. 替换其他变量占位符
5. 将最终 prompt 传给子代理

**关键**：只做占位符替换，不追加 snippet 文件。

### 组装矩阵

| 子代理 | agent-*.md | constraints-git | constraints-code | output-format | OpenSpec 输入 |
|--------|-----------|----------------|-----------------|---------------|---------------|
| Spec | agent-spec.md | ✅ | ❌ | ✅ | ❌ |
| PM | agent-pm.md | ✅ | ❌ | ✅ | ✅ (proposal/design/tasks) |
| Code | agent-code.md | ✅ | ❌ | ✅ | ✅ (tasks.md) |
| Verify | agent-verify.md | ✅ | ❌ | ✅ | ✅ (proposal/design/tasks) |

**注意**：Code 和 Verify 子代理不注入 constraints-code，而是在 prompt 中指导子代理使用 Skill 工具调用 Superpowers skill（test-driven-development / verification-before-completion）。子代理内部执行 TDD/校验流程，约束由 skill 内部实现。

### 替换占位符

{DOCS_DIR}, {WORK_DIR}, {PROJECT_DIR}, {STAGE_ID}, {SKILL_DIR}, {constraints-git}, {constraints-code}, {output-format}, {BASE_BRANCH}, {DEMAND_ID}, {DEMAND_TITLE}, {DEMAND_COLLECTION}, {verify-rubric}, {REQUIREMENT_BODY}, {PM_SKILL}, {CODE_SKILL}, {FRONTEND_SKILL}, {RDF_SKILL}, {timestamp}, {ELAPSED}, {PROJECT}, {PROPOSAL_PATH}, {DESIGN_PATH}, {TASKS_PATH}

**技能占位符来源**（从 pipeline.yaml 的 skill 映射获取）：
- `{PM_SKILL}` → PM 阶段对应技能名（如 pm）
- `{CODE_SKILL}` → 代码阶段对应技能名（如 backend-dev）
- `{FRONTEND_SKILL}` → 前端技能名（如 frontend-dev）
- `{RDF_SKILL}` → RDF 技能名（如 rdf-dev）

**变量来源**：
- `{PROJECT_DIR}` → 当前工作目录（用户启动 AI 工具时的目录，通过 Python `os.getcwd()` 获取，跨平台兼容）
- `{DEMAND_TITLE}` → 工作项标题（Step 0.2 获取）
- `{REQUIREMENT_BODY}` → 工作项描述内容（Step 0.2 获取）
- `{DEMAND_COLLECTION}` → 工作项所属 TFS 集合名（Step 0.1 获取，用于自定义 PM 技能的 TFS MCP 调用）
- `{PROJECT}` → TFS 项目名（从 parse-products.py 的 tfs_project 字段提取，仅用于脚本调用参数，不注入 agent prompt）
- `{timestamp}` → 当前时间戳（ISO 格式，注入时由主代理生成）
- `{ELAPSED}` → 阶段耗时（秒），仅用于 winmetrics 脚本调用参数，不注入 agent prompt
- `{BASE_BRANCH}` → 基础分支名，仅用于脚本调用参数，不注入 agent prompt
- `{STAGE_ID}` → 当前阶段名（pm / code / verify）
- `{verify-rubric}` → 评分标准文件内容（如有）

**替换执行**：两轮替换——第一轮注入 snippet 内容（可能包含 `{SKILL_DIR}` 等嵌套占位符），第二轮替换所有变量占位符。

### 子代理约束（必须注入）

- 不使用 clarify 工具
- 不使用 todo 工具
- 不执行任何 git 命令
- 不调用任何 TFS MCP 工具
- prompt 自包含，不依赖会话上下文

### Bypass 策略注入

启动子代理前，读取 `SKILL_DIR/references/bypass-strategies.md`，提取对应技能的 bypass 条目，注入子代理 prompt 的"交互点 bypass"段落。脚本驱动阶段不需要 bypass 策略。

### 完成信号

子代理完成后写入 `{DOCS_DIR}/{stage}-done.json`。主代理检测此文件后继续。

---

## 执行流程

**全自动，无需用户确认。**

根据输入判断模式：
- **单个需求号** → 单需求模式
- **多个需求号** → 批量模式

### Preflight: 环境检测（强制，prepare 前执行）

**目的**：检测 OpenSpec CLI 和 Superpowers skills 是否可用。失败则立即终止流水线，不创建 DOCS_DIR。

执行脚本：
```bash
$PYTHON SKILL_DIR/scripts/preflight-check.py --skill-dir {SKILL_DIR}
```

脚本检测：
1. **OpenSpec CLI**：执行 `openspec --version` 或 `openspec --help`，验证命令可执行
2. **Superpowers skills**：查找 Superpowers 目录（优先环境变量 `SUPERPOWERS_SKILL_DIR`，否则查找默认路径），验证关键技能文件存在：
   - `test-driven-development/SKILL.md`
   - `systematic-debugging/SKILL.md`
   - `requesting-code-review/SKILL.md`
   - `verification-before-completion/SKILL.md`

**失败处理**：
- 任一检测失败 → 退出码非 0 → 流水线立即终止（E003 级别）
- 输出缺失项和安装建议
- **不创建 `{DOCS_DIR}`**
- **不发送 WinMetrics 事件**（无 DOCS_DIR）

**日志**（无 DOCS_DIR 时输出到终端）：
```
[Preflight] OpenSpec: {status}
[Preflight] Superpowers: {status}
[Preflight] ✅ 环境检测通过 或 ❌ 环境检测失败，流水线终止
```

**注意**：Preflight 不依赖 DOCS_DIR，直接在 prepare 前执行。

### 环境检测（Python）

```bash
if python3 -c "pass" 2>/dev/null; then PYTHON=python3
elif python -c "pass" 2>/dev/null; then PYTHON=python
else echo "ERROR: Python not found"; exit 1; fi
```

### Step -1: 版本检查（非阻塞）

```bash
$PYTHON SKILL_DIR/scripts/update-check.py
```

对比本地 HEAD 与远程 origin/master 的 commit hash（缓存 1 天）。不同时输出 `⚠️ auto-dev 有新提交可用`，不阻塞流水线。

### Step 0: 准备

**0.1 MCP 可用性预检**（直接调用 MCP）：
```
DEMAND_COLLECTION = mcp__tfs-mcp__tfs_get_current_collection()
mcp__devops-mcp__validate_tfs_key()
```
`LOG 准备 "[Step 0.1] MCP连接验证 → tfs-mcp: {status}, devops-mcp: {status}"`

**0.2 获取工作项**（通过脚本准备参数）：
```bash
$PYTHON SKILL_DIR/scripts/tfs-ops.py get-workitem --id {DEMAND_ID} --collection {DEMAND_COLLECTION}
```
→ 检测 MCP_CALL → 执行 `mcp__tfs-mcp__tfs_get_workitem` → 解析结果
`LOG 准备 "[Step 0.2] MCP tfs_get_workitem(id={DEMAND_ID}) → {status}, 标题={DEMAND_TITLE}"`

**0.3 产品匹配（6 级降级链）**：
1. 从工作项 `Winning.Module.name` 字段提取产品名 → `parse-products.py {产品名}` 精确匹配
2. 字段为空 → 从标题前缀推断（如 "产品名:" 开头）
3. 匹配失败 → `detect-local-repos.sh` 扫描本地 TFS 仓库 → 按 URL 匹配 products.yaml
4. products.yaml 为空 → `register-product.py` 自动注册
5. products.yaml 有条目但均不匹配 → 列出所有产品名供用户选择
6. 无法确定 → 跳过（添加 `AI-SKIPPED` 标签 + 评论）→ 返回 skipped
`LOG 准备 "[Step 0.3] 产品匹配: {产品名} (来源: {Winning.Module.name/标题/本地扫描})"`
`LOG_WARN 准备 "产品匹配失败, 已跳过: {reason}"`（仅匹配失败时）

**关键区分**：`{产品名}` 是 products.yaml 的顶级 key（如 `统一登录`），`{仓库名}` 是 repos 下的 name（如 `winning-winex-basic-frame`）。后续所有 `parse-products.py` 调用的第一个参数始终是 `{产品名}`，不要用仓库名替代。

**产品匹配失败处理**（6 级均失败后）：
```bash
$PYTHON SKILL_DIR/scripts/tfs-ops.py add-tags --id {DEMAND_ID} --tags "AI-SKIPPED"
$PYTHON SKILL_DIR/scripts/tfs-ops.py add-comment --id {DEMAND_ID} --comment "AI自动开发跳过: 需求模块'{module}'未匹配到已配置产品"
```
→ 返回 skipped

**0.3.5 工作目录定位**（产品匹配成功后）：

获取 `product_dir` 并切换工作目录，使 auto-dev 可从任意目录启动。
**使用 `product_field:<name>` 模式直接取单字段值**，避免 grep+sed 文本解析的脆弱性：
```bash
PRODUCT_DIR=$($PYTHON SKILL_DIR/scripts/parse-products.py {产品名} product_field:product_dir)
```

> 如需同时读取多个产品级字段，可使用 `product_info_json` 模式一次性输出 JSON：
> ```bash
> read TFS_PROJECT DEFAULT_SKILL PRODUCT_DIR < <($PYTHON -c "
> import json, subprocess, sys
> out = subprocess.run([sys.executable, 'SKILL_DIR/scripts/parse-products.py', '{产品名}', 'product_info_json'], capture_output=True, text=True).stdout
> d = json.loads(out)
> print(d['tfs_project'], d['default_skill'], d['product_dir'])
> ")
> ```

- `PRODUCT_DIR` 非空且目录存在 → `cd "$PRODUCT_DIR"`，更新 `CWD="$PRODUCT_DIR"`
- `PRODUCT_DIR` 为空或目录不存在 → 回退：使用当前 `CWD`（保持原有行为），记录警告

`LOG 准备 "[Step 0.3.5] 工作目录: {原CWD} → {PRODUCT_DIR}"`（切换成功时）
`LOG_WARN 准备 "[Step 0.3.5] product_dir 未配置或不存在, 使用当前目录: {CWD}"`（回退时）

**0.4 DOCS_DIR 激活**：
产品匹配成功后，计算并创建文档目录：
```
DOCS_DIR = "${HOME:-$USERPROFILE}/auto-dev-docs/{产品名}/{DEMAND_ID}"
```
DOCS_DIR 必须为绝对路径（不含 `~`）。验证/创建目录：
```bash
$PYTHON SKILL_DIR/scripts/stage-helper.py init-stage --demand {DEMAND_ID} --product {产品名} --stage 准备
```
`LOG 准备 "[Step 0.4] DOCS_DIR 已激活: {DOCS_DIR}"`

**0.5 并发检查**：
```bash
$PYTHON SKILL_DIR/scripts/stage-helper.py check-lock --docs-dir {DOCS_DIR}
```
如果锁定且进程活跃 → 中止。流水线退出时移除锁。
`LOG 准备 "[Step 0.5] 并发锁检查通过"`

**0.6 检查标签**：必须包含 AI-AUTO-DEV（缺失时仅警告不阻塞），提取技能标签（AI-BACKEND/AI-FRONTEND/AI-RDF/AI-FULLSTACK）。
`LOG 准备 "[Step 0.6] 标签检查: {tags}"`
`LOG_WARN 准备 "AI-AUTO-DEV 标签缺失, 继续执行"`（仅缺失时）

**0.7 需求状态激活**：
检查工作项当前状态（Step 0.2 已获取）：
- 如果状态为"已分析"或更靠后的状态（如"已解决"、"已关闭"）→ 跳过状态变更，记录日志并继续
- 否则 → 执行状态变更：
```bash
$PYTHON SKILL_DIR/scripts/tfs-ops.py update-state --id {DEMAND_ID} --state "活动" --reason "已受理"
```
→ MCP_CALL → 执行
**注意**：如果状态变更失败（如已是"活动"），记录警告并继续 — 非阻塞。
`LOG 准备 "[Step 0.7] 需求状态={current_state}, {action}"`（action 为"已更新为'活动'" 或 "已是'{current_state}'，跳过状态变更"）

**0.8 仓库检查**（产品匹配成功后）：
如果 parse-products.py 返回空仓库列表：
→ 添加 AI-SKIPPED 标签 + TFS 评论："AI自动开发跳过: 产品'{产品名}'未配置仓库"
→ 返回 skipped

**0.9 变量提取**（产品匹配成功后，始终用 `{产品名}` 而非仓库名）：
```bash
$PYTHON SKILL_DIR/scripts/parse-products.py {产品名} name,url,branch,skill,worktree
```
输出每行格式：{仓库名}|{url}|{branch}|{skill}|{worktree}

主代理解析并保存到 `{DOCS_DIR}/.repos`：
- REPO_NAME, REPO_URL, BASE_BRANCH, REPO_SKILL per repo
- 技能名称解析：skill 列值直接作为 Skill 工具的参数使用
`LOG 准备 "[Step 0.9] 仓库路由: {tags} → [{repos}]"`

多技能仓库（如 "backend-dev,frontend-dev"）：按逗号分割，每个技能独立调用。

FULLSTACK 执行策略：当标签为 AI-FULLSTACK 时，按以下顺序串行执行：
1. 所有 code 技能仓库（后端）
2. 所有 frontend 技能仓库（前端，依赖后端 API）
3. 所有 rdf 技能仓库（RDF，依赖前端框架）
每组内的多个仓库独立执行，组间串行。

**0.10 仓库集合与部署环境提取**：
```bash
REPO_TFS_PROJECT=$($PYTHON SKILL_DIR/scripts/parse-products.py {产品名} name,tfs_project | head -1 | cut -d'|' -f2)
REPO_COLLECTION=$(echo "$REPO_TFS_PROJECT" | cut -d'/' -f1)
DEPLOY_ENV_ID=$($PYTHON SKILL_DIR/scripts/parse-products.py {产品名} product_info | grep 'deploy_env_id:' | awk '{print $2}')
echo "$REPO_COLLECTION" > {DOCS_DIR}/.repo-collection
echo "$DEPLOY_ENV_ID" > {DOCS_DIR}/.deploy-env-id
```

**0.11 仓库目录定位**：
用 CWD（已在 Step 0.3.5 切换到 product_dir）+ 仓库名拼接：
```bash
# REPO_NAME 已在 0.9 提取，直接拼接
cd "${CWD}/{REPO_NAME}"
# 验证是 git 仓库
git rev-parse --git-dir
```
如果目录不存在或不是 git 仓库，执行 `detect-local-repos.sh` 扫描作为回退。
`LOG 准备 "[Step 0.11] 仓库目录: {CWD}/{REPO_NAME}"`

**0.11.5 Worktree 创建（条件执行）**：

如果 `WORKTREE_MODE=true`，为需求创建隔离工作目录。

**恢复检测**（先检查是否已有可用 worktree）：
```bash
WORKTREE_BASE="$(cd "{CWD}" && pwd | xargs dirname)/.worktrees/{DEMAND_ID}-$(basename "$(cd "{CWD}" && pwd)")"
bash SKILL_DIR/scripts/setup-worktree.sh check {产品名} {DEMAND_ID} "{CWD}"
WT_CHECK_EXIT=$?
```
- 退出码 0 → worktree 完整可用，直接使用
- 退出码 1 → 部分损坏，尝试恢复
- 退出码 2 → worktree 不存在，正常创建

**创建/恢复 worktree**：
```bash
if [ $WT_CHECK_EXIT -eq 0 ]; then
    # worktree 已完整，直接使用 WORKTREE_BASE
    LOG 准备 "[Step 0.11.5] Worktree 已存在: $WORKTREE_BASE"
elif [ $WT_CHECK_EXIT -eq 1 ]; then
    # 尝试恢复失败仓库
    WT_JSON=$(bash SKILL_DIR/scripts/setup-worktree.sh create {产品名} {DEMAND_ID} "{CWD}" --retry-failed --json)
else
    # 正常创建
    WT_JSON=$(bash SKILL_DIR/scripts/setup-worktree.sh create {产品名} {DEMAND_ID} "{CWD}" --json)
fi
```

**解析 JSON 输出**：
```bash
WORKTREE_BASE=$(echo "$WT_JSON" | $PYTHON -c "import sys,json; d=json.load(sys.stdin); print(d['worktree_base'])")
WT_STATUS=$(echo "$WT_JSON" | $PYTHON -c "import sys,json; d=json.load(sys.stdin); print(d['status'])")
WT_FAILED=$(echo "$WT_JSON" | $PYTHON -c "import sys,json; d=json.load(sys.stdin); print(d['summary']['failed'])")
```

**错误处理**：
- `WT_STATUS=failed`（全部失败）→ E003 终止流水线
- `WT_STATUS=partial`（部分失败）→ 自动重试 1 次：
  ```bash
  WT_JSON=$(bash SKILL_DIR/scripts/setup-worktree.sh create {产品名} {DEMAND_ID} "{CWD}" --retry-failed --json)
  ```
  重试后仍有失败 → E002 暂停，通知用户

**切换 WORK_DIR**：
```bash
WORK_DIR="$WORKTREE_BASE"
echo "$WORKTREE_BASE" > {DOCS_DIR}/.worktree-path
echo "true" > {DOCS_DIR}/.worktree-mode
```

`LOG 准备 "[Step 0.11.5] Worktree 创建: worktree=true, base={WORKTREE_BASE}"`
`LOG 准备 "[Step 0.11.5] WORK_DIR 已切换: {CWD} → {WORKTREE_BASE}"`

如果 `WORKTREE_MODE=false` 或为空：
```bash
echo "false" > {DOCS_DIR}/.worktree-mode
```
跳过 worktree 创建，WORK_DIR 保持为 `{CWD}`。

**0.12 分支创建（worktree 模式适配 + 三态逻辑）**：

如果 worktree 模式（`{DOCS_DIR}/.worktree-mode` 为 `true`），`setup-worktree.sh create` 已创建 feature 分支，简化为验证：
```bash
if [ "$(cat {DOCS_DIR}/.worktree-mode 2>/dev/null)" = "true" ]; then
    # Worktree 模式：验证分支
    WT_BASE=$(cat {DOCS_DIR}/.worktree-path)
    BRANCH_OK=true
    while IFS='|' read -r repo_name _rest; do
        cd "$WT_BASE/$repo_name"
        CURRENT_BRANCH=$(git branch --show-current)
        if [ "$CURRENT_BRANCH" != "feature/{DEMAND_ID}" ]; then
            BRANCH_OK=false
            break
        fi
    done < {DOCS_DIR}/.repos
    if [ "$BRANCH_OK" = true ]; then
        LOG 准备 "[Step 0.12] 分支验证通过: feature/{DEMAND_ID} (worktree模式)"
    else
        LOG_WARN 准备 "Worktree 分支验证失败，回退到标准分支创建"
        # 回退到下方标准三态逻辑
        # ... (existing three-state logic below)
    fi
fi
```

标准三态逻辑（worktree:false 或验证失败时回退）：
1. 本地 `feature/{DEMAND_ID}` 已存在 → 直接使用
2. 远程 `origin/feature/{DEMAND_ID}` 已存在 → 创建本地跟踪分支
3. 均不存在 → 从 base_branch 创建新分支 `--no-track`
**安全检查**：当前已在 `feature/*` 分支 → 立即中止
`LOG 准备 "[Step 0.12] 分支创建: feature/{DEMAND_ID} ({mode}, base={BASE_BRANCH})"`

**0.13 WinMetrics 初始化（必须执行）**：
```bash
echo "auto-$(date +%Y%m%d%H%M%S)-{DEMAND_ID}" > {DOCS_DIR}/.run-id
# 保存需求开发负责人，用于 WinMetrics account 字段（优先级高于配置账号）
echo "{demand.assignedTo}" > {DOCS_DIR}/.dev-assigned-to
$PYTHON SKILL_DIR/scripts/winmetrics-report.py pipeline-event --name pipeline.queued --demand_id {DEMAND_ID} --attrs "demand_title={DEMAND_TITLE}" "product={产品名}" --docs-dir {DOCS_DIR}
$PYTHON SKILL_DIR/scripts/winmetrics-report.py pipeline-event --name pipeline.started --demand_id {DEMAND_ID} --docs-dir {DOCS_DIR}
```

**0.14 启动通知**（产品匹配成功后）：
```bash
bash SKILL_DIR/scripts/wechat-notify.sh start {产品名} {DEMAND_ID} "{DEMAND_TITLE}"
```
`LOG 准备 "[Step 0.14] 企微启动通知已发送"`

### Step 0.5: Spec 规格生成（子代理 + 双路径策略 + 用户确认闸门）

**必须执行 WinMetrics 阶段开始事件**：
```bash
$PYTHON SKILL_DIR/scripts/winmetrics-report.py stage-start --stage spec --skill "" --docs-dir {DOCS_DIR}
```

**目的**：为需求生成 OpenSpec change 资产，作为 PM 分析的规格闸门。

**双路径策略说明**：
- **项目目录** `{PROJECT_DIR}/openspec/changes/tfs-{DEMAND_ID}/`：用户可见、可编辑，优先使用
- **DOCS_DIR** `{DOCS_DIR}/openspec/changes/tfs-{DEMAND_ID}/`：流水线归档，作为同步副本
- **同步规则**：
  - AI生成时：同时写入两个路径
  - 用户手动编辑：项目目录优先，进入 PM 前同步到 DOCS_DIR
  - AI对话修改：同步修改两个路径

**0.5.1 初始化 OpenSpec 目录（双路径）**：
```bash
# 项目目录（用户启动 AI 工具的当前工作目录，跨平台）
PROJECT_DIR=$($PYTHON -c "import os; print(os.getcwd())")
PROJECT_OPENSPEC_DIR="$PROJECT_DIR/openspec/changes/tfs-{DEMAND_ID}"
mkdir -p "$PROJECT_OPENSPEC_DIR/specs"

# DOCS_DIR（归档副本）
DOCS_OPENSPEC_DIR="{DOCS_DIR}/openspec/changes/tfs-{DEMAND_ID}"
$PYTHON SKILL_DIR/scripts/openspec-manager.py init-demand --docs-dir {DOCS_DIR} --project-dir "$PROJECT_DIR" --demand-id {DEMAND_ID} --demand-title "{DEMAND_TITLE}" --requirement-body "{REQUIREMENT_BODY}"
```
`LOG 规格 "[Step 0.5.1] OpenSpec 目录已创建: 项目={PROJECT_OPENSPEC_DIR}, 归档={DOCS_OPENSPEC_DIR}"`

**0.5.2 启动 Spec 子代理（双路径写入）**：
启动子代理，prompt = `prompts/agents/agent-spec.md` 模板展开，并注入双路径说明：
- `{PROJECT_OPENSPEC_DIR}`：项目目录路径（用户可编辑）
- `{DOCS_OPENSPEC_DIR}`：DOCS_DIR 归档路径

子代理输出时同时写入两个路径：
```bash
# 子代理完成后，检查项目目录产物
for file in proposal.md design.md tasks.md; do
  if [ -f "$PROJECT_OPENSPEC_DIR/$file" ]; then
    # 同步到 DOCS_DIR
    cp "$PROJECT_OPENSPEC_DIR/$file" "$DOCS_OPENSPEC_DIR/$file"
  fi
done
```

等待 `{PROJECT_OPENSPEC_DIR}/spec-done.json` 或 `{DOCS_OPENSPEC_DIR}/spec-done.json`。读取其中的 `status` 字段：
- `status=failed` → 添加 AI-SKIPPED 标签 + TFS 评论："AI自动开发跳过: 规格生成失败"，然后终止流水线

**0.5.3 校验 OpenSpec 产物（优先检查项目目录）**：
```bash
# 优先检查项目目录
if [ -d "$PROJECT_OPENSPEC_DIR" ]; then
  $PYTHON SKILL_DIR/scripts/openspec-manager.py validate-demand --openspec-dir "$PROJECT_OPENSPEC_DIR" --demand-id {DEMAND_ID}
else
  # 回退到 DOCS_DIR
  $PYTHON SKILL_DIR/scripts/openspec-manager.py validate-demand --docs-dir {DOCS_DIR} --demand-id {DEMAND_ID}
fi
```
校验必需文件：proposal.md、design.md、tasks.md（至少 100 字节）
- 失败 → 写入 `.spec-status=fail` → 终止流水线
- 成功 → 写入 `.spec-status=pass` → **进入用户确认阶段**
`LOG 规格 "[Step 0.5.3] OpenSpec 校验: {status}，产物位于项目目录"`

**0.5.4 用户确认闸门（流水线暂停，循环确认）**：
Spec 完成后，流水线暂停等待用户确认。**支持多轮对话修改 + 再次确认**：

**首次提示**：
```
========================================
Spec 规格生成完成，请确认文档正确性
========================================
OpenSpec 文档位置：
- 项目目录: {PROJECT_DIR}/openspec/changes/tfs-{DEMAND_ID}/
  - proposal.md（需求提案）
  - design.md（技术设计）
  - tasks.md（实现任务分解）

您可以：
1. 直接查看并编辑上述文件（项目目录）
2. 告诉我需要修改的内容，我来修改
3. 确认无误后输入"继续"进入 PM 分析阶段

输入"继续"后将：
- 同步项目目录文档到 DOCS_DIR 归档
- 进入 PM 分析阶段（以项目目录版本为准）
========================================
```

**循环确认逻辑**：
- 用户输入"继续" → 确认完成，进入下一步
- 用户提出修改意见 → AI 修改文档（同时更新项目目录和 DOCS_DIR）→ **再次展示修改后的文档摘要** → 等待用户再次确认
- 用户自己编辑文件后 → 告知 AI → AI 展示文件变更摘要 → 等待用户确认

**修改后再次提示**：
```
========================================
文档已修改，请再次确认
========================================
修改内容摘要：
- proposal.md: {修改摘要}
- design.md: {修改摘要}
- tasks.md: {修改摘要}

文档位置: {PROJECT_DIR}/openspec/changes/tfs-{DEMAND_ID}/

请确认：
- 输入"继续" → 进入 PM 分析阶段
- 还需修改 → 继续告诉我修改内容
========================================
```

用户确认后：
```bash
# 1. 同步项目目录到 DOCS_DIR
cp -r "$PROJECT_OPENSPEC_DIR"/* "$DOCS_OPENSPEC_DIR/"

# 2. 写入确认标记
echo "confirmed" > {DOCS_DIR}/.spec-confirmed
echo "$(date +%Y%m%d%H%M%S)" >> {DOCS_DIR}/.spec-confirmed

# 3. 更新状态
echo "confirmed" > {DOCS_DIR}/.spec-status
```
`LOG 规格 "[Step 0.5.4] 用户已确认，同步项目目录到 DOCS_DIR，进入 PM 阶段"`

**注意**：
- 每次修改后必须再次展示文档变更摘要，让用户确认
- 禁止修改后直接进入 PM 阶段，必须等待用户明确输入"继续"
- 用户可以在项目目录直接编辑文档
- AI 对话修改时，同时更新两个路径
- PM 阶段优先读取项目目录版本

**强制交互规则（绝对规则）**：
用户提出修改意见且 AI 完成修改后，**必须**使用 `AskUserQuestion` 工具询问用户确认，格式如下：
```
AskUserQuestion({
  questions: [{
    question: "文档已修改，请确认是否可以进入 PM 分析阶段？",
    header: "Spec确认",
    options: [
      { label: "确认，继续", description: "文档无误，进入 PM 分析阶段" },
      { label: "还需修改", description: "继续提出修改意见" }
    ],
    multiSelect: false
  }]
})
```
禁止在修改后跳过此交互直接进入 PM 阶段。

**必须执行 WinMetrics 阶段完成事件**：
```bash
$PYTHON SKILL_DIR/scripts/winmetrics-report.py stage-complete --stage spec --status success --duration {ELAPSED} --docs-dir {DOCS_DIR}
```

### Step 1: PM 分析（子代理，以项目目录 OpenSpec 为准）

**前置检查**：确认 `.spec-confirmed` 存在（用户已确认 Spec 文档）

**必须执行 WinMetrics 阶段开始事件**：
```bash
$PYTHON SKILL_DIR/scripts/winmetrics-report.py stage-start --stage pm --skill {PM_SKILL} --docs-dir {DOCS_DIR}
```

启动子代理，prompt = `prompts/agents/agent-pm.md` 模板展开（constraints-git + output-format + 需求详情注入 + **项目目录 OpenSpec 输入**）。

**OpenSpec 输入注入（优先项目目录）**：
```bash
# 优先项目目录
PROJECT_OPENSPEC_DIR="{PROJECT_DIR}/openspec/changes/tfs-{DEMAND_ID}"
DOCS_OPENSPEC_DIR="{DOCS_DIR}/openspec/changes/tfs-{DEMAND_ID}"

# 判断使用哪个路径
if [ -f "$PROJECT_OPENSPEC_DIR/proposal.md" ]; then
  PROPOSAL_PATH="$PROJECT_OPENSPEC_DIR/proposal.md"
  DESIGN_PATH="$PROJECT_OPENSPEC_DIR/design.md"
  TASKS_PATH="$PROJECT_OPENSPEC_DIR/tasks.md"
else
  # 回退到 DOCS_DIR
  PROPOSAL_PATH="$DOCS_OPENSPEC_DIR/proposal.md"
  DESIGN_PATH="$DOCS_OPENSPEC_DIR/design.md"
  TASKS_PATH="$DOCS_OPENSPEC_DIR/tasks.md"
fi
```

**关键**：PM 子代理以用户确认的 OpenSpec 文档为准（项目目录版本），dev-plan.md 必须从 OpenSpec change 派生。

**1.1 范围检查**：
PM 子代理完成后，检查 dev-plan.md 中涉及的仓库是否都在 products.yaml 配置中。
如果存在未配置仓库：
- 添加 `AI-SKIPPED` 标签 + 评论："AI自动开发跳过: 需求涉及未配置仓库 {repo_list}"
- 返回 skipped
`LOG 需求分析 "[Step 1.1] 范围检查: dev-plan.md涉及仓库[{repos}]均在products.yaml配置的repos列表内, 检查{result}"`

**1.2 创建 AI 分析任务**：
```bash
$PYTHON SKILL_DIR/scripts/tfs-ops.py create-task --parent {DEMAND_ID} --title "AI分析任务:{DEMAND_TITLE}" --type Task --project {PROJECT} --assigned-to {demand.assignedTo} --iteration-path {demand.iterationPath} --area-path {demand.areaPath} --fields-stdin <<'JSONEOF'
{"Microsoft.VSTS.Common.Discipline": "分析", "Microsoft.VSTS.Scheduling.OriginalEstimate": "0.5"}
JSONEOF
```
→ MCP_CALL → 执行 → 解析 → 保存 .analysis-task-id
尝试 3 次重试（间隔 5s/10s/20s）。如果 3 次均失败 → 进入降级模式：
- ANALYSIS_TASK_ID = DEMAND_ID
- 写入 `.analysis-task-degraded` = "true"
- 写入 `.degradation-reason` = "{具体失败原因}"
- 降级告警：TFS 需求评论 `⚠️ AI自动开发降级告警：分析任务创建失败({reason})，后续步骤将跳过任务操作`
`LOG 需求分析 "[Step 1.2] MCP tfs_create_workitem(title=AI分析任务:...) → {status}, task=#{ANALYSIS_TASK_ID}"`
`LOG_WARN 需求分析 "降级告警: 分析任务创建失败, 原因={reason}"`（仅降级时）

**1.2.1 添加 AI-ANALYSIS 标签**（非降级模式）：
```bash
$PYTHON SKILL_DIR/scripts/tfs-ops.py add-tags --id {ANALYSIS_TASK_ID} --tags "AI-ANALYSIS"
```
降级模式下跳过此步。
`LOG 需求分析 "[Step 1.2.1] MCP add-tags(AI-ANALYSIS) → {status}"`

**1.3 更新分析任务状态为 "活动"**（非降级模式）：
```bash
$PYTHON SKILL_DIR/scripts/tfs-ops.py update-state --id {ANALYSIS_TASK_ID} --state "活动" --reason "调查"
```
→ MCP_CALL → 执行
降级模式下跳过此步（禁止对需求工作项设置"活动"状态）。
`LOG 需求分析 "[Step 1.3] 分析任务状态已更新为'活动'"`

**1.4 上传 dev-plan.md**：
```bash
$PYTHON SKILL_DIR/scripts/tfs-ops.py upload-attachment --id {DEMAND_ID} --file {DOCS_DIR}/dev-plan.md
```
`LOG 需求分析 "[Step 1.4] MCP tfs_upload_attachment(dev-plan.md) → {status}"`

**1.5 分析任务描述更新**（非降级模式）：
读取模版 `SKILL_DIR/templates/task-desc-analysis.html`，将 dev-plan.md 内容和工作项字段填充到模版占位符中，生成最终 HTML。占位符填充规则：
- `{DEMAND_TITLE}`, `{DEMAND_ID}` → 工作项字段
- `{OVERVIEW}` → dev-plan.md 的 Requirement Overview
- `{FEATURE_LIST}` → dev-plan.md 的 Feature List，逐条转为 `<li>`
- `{TECH_SOLUTION}` → dev-plan.md 的 Technical Solution（支持 Markdown 转 HTML 段落）
- `{REPO_TABLE_ROWS}` → dev-plan.md 的 Repositories and Modules，每行生成 `<tr><td>...</td></tr>`
- `{WORK_ESTIMATE}` → PM 分析判断的工作量估算文本
将最终 HTML 写入 TFS 分析任务描述（长内容用 `--fields-stdin`）：
```bash
$PYTHON SKILL_DIR/scripts/tfs-ops.py update-workitem --id {ANALYSIS_TASK_ID} --fields-stdin <<'JSONEOF'
{"System.Description": "{html_content}"}
JSONEOF
```
降级模式下跳过此步（需求约束禁止对需求工作项调用 update-workitem）。
`LOG 需求分析 "[Step 1.5] MCP tfs_update_workitem({ANALYSIS_TASK_ID}) → {status}"`

**1.6 更新分析任务状态为 "已解决"**（非降级模式）：
```bash
$PYTHON SKILL_DIR/scripts/tfs-ops.py update-state --id {ANALYSIS_TASK_ID} --state "已解决" --reason "已完成并且需要评审/测试"
```
→ MCP_CALL → 执行
降级模式下跳过此步。
`LOG 需求分析 "[Step 1.6] 分析任务状态已更新为'已解决'"`

**1.7 更新需求状态为 "已分析"**：
```bash
$PYTHON SKILL_DIR/scripts/tfs-ops.py update-state --id {DEMAND_ID} --state "已分析" --reason "分析完成"
```
→ MCP_CALL → 执行
`LOG 需求分析 "[Step 1.7] 需求状态已更新为'已分析'"`
**约束（绝对规则，仅限 Step 1 需求状态变更）**：对需求工作项只通过 `tfs-ops.py update-state` 变更状态，禁止直接调用 MCP。禁止调用 tfs_update_workitem 修改需求字段。禁止修改 completion_date、dev_commit_date 等其他字段。其他步骤对子任务（校验任务等）使用 update-workitem 更新描述字段不受此限制。

**必须执行 WinMetrics 阶段完成事件**：
```bash
$PYTHON SKILL_DIR/scripts/stage-helper.py write-status --file {DOCS_DIR}/.pm-status --value "success"
$PYTHON SKILL_DIR/scripts/winmetrics-report.py stage-complete --stage pm --status success --duration {ELAPSED} --docs-dir {DOCS_DIR}
```

### Step 2: 代码开发（子代理，内部调用 Superpowers skill）

**必须执行 WinMetrics 阶段开始事件**：
```bash
$PYTHON SKILL_DIR/scripts/winmetrics-report.py stage-start --stage code --skill {CODE_SKILL} --docs-dir {DOCS_DIR}
```

启动子代理，prompt = `prompts/agents/agent-code.md` 模板展开（constraints-git + output-format + dev-plan.md 路径 + **项目目录 OpenSpec tasks.md** + **Superpowers skill 使用指导**）。

**OpenSpec 输入注入（优先项目目录）**：
```bash
PROJECT_OPENSPEC_DIR="{PROJECT_DIR}/openspec/changes/tfs-{DEMAND_ID}"
DOCS_OPENSPEC_DIR="{DOCS_DIR}/openspec/changes/tfs-{DEMAND_ID}"

if [ -f "$PROJECT_OPENSPEC_DIR/tasks.md" ]; then
  TASKS_PATH="$PROJECT_OPENSPEC_DIR/tasks.md"
else
  TASKS_PATH="$DOCS_OPENSPEC_DIR/tasks.md"
fi
```
在 agent-code.md prompt 中增加占位符 `{TASKS_PATH}`，Code 子代理读取 tasks.md 决定实现顺序。

**Superpowers skill 使用指导**（注入到 agent-code.md prompt）：
在子代理 prompt 中添加指导段落：
```
## 开发流程执行

使用 Skill 工具调用 Superpowers 的 `test-driven-development` skill：

Skill(
  skill="test-driven-development",
  args="实现 {TASKS_PATH} 中的任务。dev-plan.md={DOCS_DIR}/dev-plan.md, 输出={DOCS_DIR}/summary.md"
)

skill 会自动执行：
1. TDD 流程（先写测试再实现）
2. 系统化调试（遇到失败不盲目修改）
3. 自查验证（写入前验证关键逻辑）

你只需：
- 提供 tasks.md 路径和输出路径作为参数
- 等待 skill 执行完成
- 检查输出文件是否生成
```

**约束注入**：只注入 constraints-git（禁止 git 操作），不注入 constraints-code（由 skill 内部约束）。

等待 `{DOCS_DIR}/code-done.json`。读取其中的 `status` 字段：
- `status=failed` → 添加 AI-SKIPPED 标签 + TFS 评论："AI自动开发跳过: 代码开发失败"，然后终止流水线（按"中间阶段失败处理"流程）
`LOG 编码 "[Step 2] 子Agent({REPO_SKILL})内部调用Superpowers skill完成 @ {repo} → {files}个文件, +{ins}行/-{del}行"`

**2.1 变更量检查**：
```bash
$PYTHON SKILL_DIR/scripts/stage-helper.py check-limits --docs-dir {DOCS_DIR} --max-files {max_files} --max-insertions {max_insertions}
```
（max_files/max_insertions 从 products.yaml 提取，默认 20/500）
`LOG 编码 "[Step 2.1] 改动量检查: {files}个文件(阈值={max}), {lines}行insertions(阈值={max}) → {result}"`

**变更量超限处理**：
if check-limits 返回 exceeded:
1. 丢弃所有工作区变更：`git checkout . && git clean -fd`
2. 添加 AI-SKIPPED 标签 + TFS 评论
3. 返回 skipped
`LOG_WARN 编码 "改动量超限: {reason}, 丢弃变更并跳过"`（仅超限时）

**2.2 上传编码总结**：
```bash
$PYTHON SKILL_DIR/scripts/tfs-ops.py upload-attachment --id {DEMAND_ID} --file {DOCS_DIR}/summary.md
```
`LOG 编码 "[Step 2.2] 编码完成, MCP tfs_upload_attachment(summary.md) → {status}"`

**2.3 创建/关联 TFS Task**：
Task 匹配规则：查询子任务列表，仅匹配标题以 "AI开发" 开头的任务。无匹配 → 创建新任务。
```bash
$PYTHON SKILL_DIR/scripts/tfs-ops.py create-task --parent {DEMAND_ID} --title "AI开发任务:{DEMAND_TITLE}" --type Task --project {PROJECT} --assigned-to {demand.assignedTo} --iteration-path {demand.iterationPath} --area-path {demand.areaPath} --fields-stdin <<'JSONEOF'
{"Microsoft.VSTS.Scheduling.OriginalEstimate": "0.5"}
JSONEOF
```
→ MCP_CALL → 执行 → 解析 → 保存 .task-id
`LOG 编码 "[Step 2.3] MCP tfs_create_workitem(title=AI开发:...) → {status}, task=#{TASK_ID}"`

**降级处理**（Task 创建失败时）：
1. 尝试 3 次重试（间隔 5s/10s/20s）
2. 如果 3 次均失败 → 进入降级模式：
   - TASK_ID = DEMAND_ID
   - 写入 `.task-degraded` = "true"
   - 写入 `.degradation-reason` = "{具体失败原因}"
3. 降级告警（3 个必须触发的位置）：
   - TFS 需求评论：`⚠️ AI自动开发降级告警：子任务创建失败...`
   - 后续提交信息后缀：`warning [降级告警] 子任务创建失败...`
   - 最终报告顶部：醒目降级告警段落
   `LOG_WARN 编码 "降级告警: 子任务创建失败, 原因={reason}"`（仅降级时）

**2.3.0 更新开发任务状态为 "活动"**（创建成功后立即执行，非降级模式）：
```bash
$PYTHON SKILL_DIR/scripts/tfs-ops.py update-state --id {TASK_ID} --state "活动" --reason "调查"
```
→ MCP_CALL → 执行
降级模式下跳过此步。
`LOG 编码 "[Step 2.3.0] 开发任务状态已更新为'活动'"`

**2.3.1 开发任务描述更新**（非降级模式）：
读取模版 `SKILL_DIR/templates/task-desc-dev.html`，将 dev-plan.md 的 Development Instructions 部分填充到模版占位符中，生成最终 HTML。
占位符填充规则：
- `{DEMAND_TITLE}`, `{DEMAND_ID}` → 工作项字段
- `{REPO_INSTRUCTIONS}` → dev-plan.md 的 `## Development Instructions` 部分，按 `### Repository: xxx` 分组，每个步骤转为 `<h4>` 标题 + `<div style="background:#f5f5f5"><code>` 代码块结构化 HTML（禁止使用 `<h5>`、`<pre>`、HTML 注释，TFS 不支持）
将最终 HTML 写入 TFS 开发任务描述（长内容用 `--fields-stdin`）：
```bash
$PYTHON SKILL_DIR/scripts/tfs-ops.py update-workitem --id {TASK_ID} --fields-stdin <<'JSONEOF'
{"System.Description": "{html_content}"}
JSONEOF
```
降级模式下跳过此步（需求约束禁止对需求工作项调用 update-workitem）。
`LOG 编码 "[Step 2.3.1] MCP tfs_update_workitem({TASK_ID}) → {status}"`

**2.4 添加 AI-CODING 和 AI-AUTO-DEV 标签**（任务创建成功后）：
给需求项添加 AI-CODING，给开发 Task 添加 AI-CODING 和 AI-AUTO-DEV：
```bash
$PYTHON SKILL_DIR/scripts/tfs-ops.py add-tags --id {DEMAND_ID} --tags "AI-CODING"
$PYTHON SKILL_DIR/scripts/tfs-ops.py add-tags --id {TASK_ID} --tags "AI-CODING,AI-AUTO-DEV"
```
降级模式下不给 Task 添加标签（仅给需求项添加 AI-CODING）。
`LOG 编码 "[Step 2.4] MCP add-tags(AI-CODING) → {status}, add-tags(AI-AUTO-DEV) → {status}"`

**必须执行 WinMetrics 阶段完成事件**：
```bash
$PYTHON SKILL_DIR/scripts/stage-helper.py write-status --file {DOCS_DIR}/.code-status --value "success"
$PYTHON SKILL_DIR/scripts/winmetrics-report.py stage-complete --stage code --status success --duration {ELAPSED} --docs-dir {DOCS_DIR}
```

### Step 3: 需求校验（子代理，内部调用 Superpowers skill）

**必须执行 WinMetrics 阶段开始事件**：
```bash
$PYTHON SKILL_DIR/scripts/winmetrics-report.py stage-start --stage verify --skill req-verify --docs-dir {DOCS_DIR}
```

启动子代理，prompt = `prompts/agents/agent-verify.md` 模板展开（constraints-git + output-format + dev-plan.md + summary.md 路径 + **项目目录 OpenSpec 输入** + verify-rubric + **Superpowers skill 使用指导**）。

**OpenSpec 输入注入（优先项目目录）**：
```bash
PROJECT_OPENSPEC_DIR="{PROJECT_DIR}/openspec/changes/tfs-{DEMAND_ID}"
DOCS_OPENSPEC_DIR="{DOCS_DIR}/openspec/changes/tfs-{DEMAND_ID}"

if [ -f "$PROJECT_OPENSPEC_DIR/proposal.md" ]; then
  PROPOSAL_PATH="$PROJECT_OPENSPEC_DIR/proposal.md"
  DESIGN_PATH="$PROJECT_OPENSPEC_DIR/design.md"
  TASKS_PATH="$PROJECT_OPENSPEC_DIR/tasks.md"
else
  PROPOSAL_PATH="$DOCS_OPENSPEC_DIR/proposal.md"
  DESIGN_PATH="$DOCS_OPENSPEC_DIR/design.md"
  TASKS_PATH="$DOCS_OPENSPEC_DIR/tasks.md"
fi
```
在 agent-verify.md prompt 中增加占位符 `{PROPOSAL_PATH}`, `{DESIGN_PATH}`, `{TASKS_PATH}`。

**Superpowers skill 使用指导**（注入到 agent-verify.md prompt）：
在子代理 prompt 中添加指导段落：
```
## 校验流程执行

使用 Skill 工具调用 Superpowers 的 `verification-before-completion` skill：

Skill(
  skill="verification-before-completion",
  args="校验 {PROPOSAL_PATH}, {DESIGN_PATH}, {TASKS_PATH} 是否完整实现。dev-plan.md={DOCS_DIR}/dev-plan.md, summary.md={DOCS_DIR}/summary.md, 输出={DOCS_DIR}/verify-report.md"
)

skill 会自动执行：
1. 功能覆盖检查（基于 dev-plan.md）
2. 逻辑正确性检查（使用系统化调试）
3. 代码质量检查
4. OpenSpec 覆盖检查（proposal/design/tasks）
5. 自查验证（输出前验证覆盖点准确）

你只需：
- 提供 OpenSpec 文档路径、dev-plan.md、summary.md 和输出路径作为参数
- 等待 skill 执行完成
- 检查输出文件是否生成
- 确保 verify-done.json 包含 verdict 字段（pass/warn/fail）
```

**约束注入**：只注入 constraints-git（禁止 git 操作），不注入 constraints-code（由 skill 内部约束）。

等待 `{DOCS_DIR}/verify-done.json`。

**3.1 创建校验任务**：
```bash
$PYTHON SKILL_DIR/scripts/tfs-ops.py create-task --parent {DEMAND_ID} --title "AI校验任务:{DEMAND_TITLE}" --type Task --project {PROJECT} --assigned-to {demand.assignedTo} --iteration-path {demand.iterationPath} --area-path {demand.areaPath} --fields-stdin <<'JSONEOF'
{"Microsoft.VSTS.Common.Discipline": "环境搭建/现场支持", "Microsoft.VSTS.Scheduling.OriginalEstimate": "0.5"}
JSONEOF
```
→ 保存 .verify-task-id
尝试 3 次重试（间隔 5s/10s/20s）。如果 3 次均失败 → 进入降级模式：
- VERIFY_TASK_ID = DEMAND_ID
- 写入 `.verify-task-degraded` = "true"
- 写入 `.degradation-reason` = "{具体失败原因}"
- 降级告警：TFS 需求评论 `⚠️ AI自动开发降级告警：校验任务创建失败({reason})，后续步骤将跳过任务操作`
`LOG 需求校验 "[Step 3.1] MCP tfs_create_workitem(title=AI校验:...) → {status}, task=#{VERIFY_TASK_ID}"`
`LOG_WARN 需求校验 "降级告警: 校验任务创建失败, 原因={reason}"`（仅降级时）

创建成功后立即更新状态为"活动"（非降级模式）：
```bash
$PYTHON SKILL_DIR/scripts/tfs-ops.py update-state --id {VERIFY_TASK_ID} --state "活动" --reason "调查"
```
→ MCP_CALL → 执行
降级模式下跳过此步（禁止对需求工作项设置"活动"状态）。
`LOG 需求校验 "[Step 3.1] 校验任务状态已更新为'活动'"`

**3.2 写入校验状态文件**：
```bash
$PYTHON SKILL_DIR/scripts/stage-helper.py write-status --file {DOCS_DIR}/.verify-status --value "{pass|warn|fail}"
```
`LOG 需求校验 "[Step 3.2] 最终评定: {status}, {severe}严重({fixed}已修复), {minor}轻微"`

如果 verify-status=fail → 将校验任务状态设为"已解决"（reason: "校验未通过"）。TFS 评论："AI自动开发: 需求校验未通过，详情见校验报告"。需求仍保持在 "已分析" 状态。然后终止流水线。
`LOG_ERROR 需求校验 "校验失败: {reason}"`（仅失败时）

**3.3 校验任务描述更新**（非降级模式）：
1. 读取 `{DOCS_DIR}/verify-report.md`
2. 读取模版 `SKILL_DIR/templates/task-desc-verify.html`，将 verify-report.md 内容填充到模版占位符中，生成最终 HTML。
占位符填充规则：
- `{DEMAND_TITLE}` → 工作项标题
- `{VERDICT}` → verify-report.md 的 Final Assessment 结论（pass/warn/fail）
- `{VERDICT_COLOR}` → pass=`#107c10`, warn=`#ff8c00`, fail=`#d13438`
- `{SEVERE_COUNT}`, `{SEVERE_FIXED}`, `{MINOR_COUNT}` → 从 verify-report.md 统计
- `{ROUND1_TABLE_ROWS}` → Round 1 表格，每行生成 `<tr><td>需求点</td><td>代码位置</td><td>判定</td></tr>`
- `{ROUND1_FIX_ACTIONS}` → Round 1 修复动作
- `{ROUND2_SUMMARY}`, `{ROUND2_FIX_ACTIONS}` → Round 2 逻辑检查摘要和修复
- `{ROUND3_SUMMARY}`, `{ROUND3_FIX_ACTIONS}` → Round 3 质量检查摘要和修复
- `{FINAL_SUMMARY}` → verify-report.md 的 Final Assessment 摘要段落
3. 将最终 HTML 写入 TFS 校验任务描述（长内容用 `--fields-stdin`）：
```bash
$PYTHON SKILL_DIR/scripts/tfs-ops.py update-workitem --id {VERIFY_TASK_ID} --fields-stdin <<'JSONEOF'
{"System.Description": "{html_content}"}
JSONEOF
```
降级模式下跳过此步（需求约束禁止对需求工作项调用 update-workitem）。

**3.4 更新校验任务状态为 "已解决"**（非降级模式）。
降级模式下跳过此步。
`LOG 需求校验 "[Step 3.4] 校验任务状态已更新为'已解决'"`

**必须执行 WinMetrics 阶段完成事件**：
```bash
$PYTHON SKILL_DIR/scripts/winmetrics-report.py stage-complete --stage verify --status {STATUS} --duration {ELAPSED} --docs-dir {DOCS_DIR}
```

### Step 3.5: 单元测试（条件执行，脚本驱动）

仅当 pipeline.yaml 包含 unit-test 阶段时执行（通过 `parse-pipeline.py stages` 检测 stage id）。

**对每个仓库执行**：
1. 检测技术栈（Java→JUnit5/TestNG, 前端→Vitest/Jest）
2. 从 dev-plan.md + summary.md 提取变更文件列表
3. 自动生成测试代码
4. 执行测试
5. 失败自动修复（最多 3 轮）
6. 生成覆盖率报告 → `{DOCS_DIR}/AI-UNIT-TEST-{DEMAND_ID}-{YYYYMMDD}.md`
7. 上传到 TFS + 添加 `AI-UNIT-TEST` 标签
8. 写入 `{DOCS_DIR}/.unit-test-result`（SUCCESS/PARTIAL/FAILED/N/A）

**跳过条件**：pipeline.yaml 无 unit-test 阶段 或 无适合单测的文件 → 写入 `N/A`

**完成后清理**（提交阶段前）：
1. 删除所有生成的测试文件
2. 删除覆盖率产物（Java: `target/site/jacoco/`, Vue: `coverage/`）
3. 删除 `.unit-test-files` 文件本身

**3.6 清理 dev-plan.md**：
代码、校验、单元测试均已完成对 dev-plan.md 的读取，此时安全删除：
```bash
rm -f {DOCS_DIR}/dev-plan.md
```
`LOG 需求校验 "[Step 3.6] dev-plan.md 已清理"`

### Step 4: 提交+PR（脚本驱动，无子代理）

**前置检查**：读取 `.verify-status`，如果为 `fail` → 立即返回 failed。
`LOG 提交+PR "阶段开始, TASK_ID={TASK_ID}, TASK_LINK_DEGRADED={.task-degraded}"`

**必须执行 WinMetrics 阶段开始事件**：
```bash
$PYTHON SKILL_DIR/scripts/winmetrics-report.py stage-start --stage submit --skill git-merge --docs-dir {DOCS_DIR}
```

**4.1 Git 提交约束（绝对规则）**：
- 只允许一次 `git add -A && git commit`
- 禁止 `git commit --amend`、禁止多次提交
- 提交信息格式（条件叠加）：
  - 正常：`#{TASK_ID} {DEMAND_TITLE}`（TASK_ID 为 Step 2.3 创建的 AI 开发任务 ID）
  - 降级模式：`#{DEMAND_ID} {DEMAND_TITLE} warning [降级告警] 子任务创建失败，代码直接关联需求 #{DEMAND_ID}。原因：{DEGRADATION_REASON}`
  - 校验警告：追加 `[AI-VERIFY-WARN] 存在轻微问题，已带警告通过校验`
  - 单测警告：追加 `[AI-UNIT-TEST-WARN] 单元测试未全部通过({UNIT_TEST_RESULT})`
- 推送前验证：`git log --oneline origin/{base_branch}..HEAD | wc -l` 必须 == 1
- 禁止从分支名解析工作项 ID

**分支保护**：
- 保护分支 = products.yaml 中所有 `default_branch` 和 `repos[].branch` 值
- 唯一允许推送目标：`feature/{DEMAND_ID}`
- 推送前检查：当前分支必须匹配 `feature/*` 且包含 DEMAND_ID
- 已在 feature 分支时禁止再次创建 feature 分支

**4.1.1 差异统计**（所有仓库推送完成后）：
对每个仓库执行 `git diff --shortstat HEAD~1`，汇总写入 `{DOCS_DIR}/.total-diff`。
`LOG 提交+PR "[Step 4.1] 仓库 {repo} 提交: commit={hash}, {files}files +{ins}/-{del}"`
`LOG 提交+PR "[Step 4.1] 仓库 {repo} 提交推送完成: commit={hash}, {files}files +{ins}/-{del}"`

**4.1.2 创建人工测试任务**：
`{next_business_day_10UTC}` = 下一个工作日 10:00 UTC（跳过周末，主代理计算）。
```bash
$PYTHON SKILL_DIR/scripts/tfs-ops.py create-task \
  --parent {DEMAND_ID} --title "人工测试:{DEMAND_TITLE}" \
  --type Task --project {PROJECT} \
  --assigned-to {demand.assignedTo} \
  --iteration-path {demand.iterationPath} --area-path {demand.areaPath} \
  --fields-stdin <<'JSONEOF'
{"Microsoft.VSTS.Common.Discipline": "环境搭建/现场支持", "Microsoft.VSTS.Scheduling.OriginalEstimate": "0.5", "Microsoft.VSTS.Scheduling.FinishDate": "{next_business_day_10UTC}"}
JSONEOF
```
→ 3 次重试（5s/10s/20s），失败仅记录警告（非阻塞）→ 成功后：update-state → "活动" → 写入 `.test-task-id`
`LOG 提交+PR "[Step 4.1.3] MCP tfs_create_workitem(title=人工测试:...) → {status}, task=#{TEST_TASK_ID}"`
`LOG 提交+PR "[Step 4.1.3] 测试任务状态已更新为'活动'"`

**4.2 创建 PR**（对每个仓库）：

**PR 工具绝对禁令**：
- ✅ 唯一允许：`mcp__devops-mcp__create_pr`
- ❌ 禁止：`mcp__tfs-mcp__tfs_create_pr`、任何其他 MCP PR 工具
- ❌ 禁止：devops-mcp 失败后回退到 tfs-mcp

1. 准备参数：
```bash
$PYTHON SKILL_DIR/scripts/pr-manager.py create --repo {URL} --source feature/{DEMAND_ID} --target {BASE_BRANCH}
```
2. 执行 MCP 调用：`mcp__devops-mcp__create_pr`
3. 解析创建结果（初始 RETRY_COUNT=0）：
```bash
$PYTHON SKILL_DIR/scripts/pr-manager.py parse-create --result-stdin --retry-count {RETRY_COUNT} <<'JSONEOF'
{MCP 返回结果}
JSONEOF
```
4. **重试逻辑**：如果 parse-create 返回 `action=retry`：
   - 等待 `delay` 秒（默认 30s）
   - RETRY_COUNT 递增
   - 回到步骤 2（重新执行 MCP create_pr → parse-create --retry-count {新值}）
   - 最多重试 `max_retries` 次（默认 3 次）
   - 重试耗尽后 → 写入 `.pr-create-failed`，标记 pr_status=failed

**可重试错误**：`提交未关联工作项`（TFS 工作项关联有传播延迟，等待后重试通常可恢复）

失败处理（非重试错误或重试耗尽）：写入 `.pr-create-failed`（格式：`{repo}:devops-mcp-failed:{error}`），标记 pr_status=failed，继续处理其他仓库。
`LOG 提交+PR "[Step 4.2] MCP create_pr(repo={repo}) → {status}, PR=#{tfs_pr_id}"`
`LOG 提交+PR "[Step 4.2] MCP create_pr 重试 {n}/{max}: delay={d}s, error={error}"`（每次重试时）
`LOG_WARN 提交+PR "MCP create_pr失败: {error}"`（仅最终失败时）

**4.2.1 评审标记**：
写入 `{DOCS_DIR}/.pr-review.md` 内容为 "PR评审已跳过（bypass模式）"。

**4.3 PR 轮询**：
```bash
$PYTHON SKILL_DIR/scripts/pr-manager.py poll --pr-id {tfs_pr_id}
```
→ MCP_CALL_POLL → 循环轮询 → 每次调用 parse-poll
`LOG 提交+PR "[Step 4.3] 轮询 {n}/{max}: current_step={step}, status={status}"`（每次轮询）
`LOG 提交+PR "[Step 4.3] PR #{ID} 流水线终态: {status}, 轮询{n}次"`（终态时）

**4.3.1 PR 状态文件**：
所有仓库 PR 轮询完成后，写入 `.pr-status`：
格式：每行 `{仓库名}#{tfs_pr_id}={pr_status}`

**4.4 更新工作项状态**（PR 轮询完成后）：

**前置检查**：读取 `.pr-status` 和 `.pr-create-failed`
- 如果有**任一**仓库 PR 失败 → 跳过本步骤，不更新任务和需求状态
  `LOG_WARN 提交+PR "[Step 4.4] 存在失败的PR，跳过状态更新"`
- 如果**所有**仓库 PR 均成功 → 继续执行状态更新

状态更新：
```bash
# 非降级模式
$PYTHON SKILL_DIR/scripts/tfs-ops.py update-state --id {TASK_ID} --state "已解决" --reason "已完成并且需要评审/测试"
```
```bash
# 无论是否降级
$PYTHON SKILL_DIR/scripts/tfs-ops.py update-state --id {DEMAND_ID} --state "已解决" --reason "代码完成且通过系统测试"
```
`LOG 提交+PR "[Step 4.4] AI开发任务状态已更新为'已解决'"`
`LOG 提交+PR "[Step 4.4] 需求状态已更新为'已解决'"`

**4.4.1 添加 AI-AUTO-DONE 标签**（所有仓库 PR 成功时）：
如果所有仓库 PR 均成功：
```bash
$PYTHON SKILL_DIR/scripts/tfs-ops.py add-tags --id {DEMAND_ID} --tags "AI-AUTO-DONE"
$PYTHON SKILL_DIR/scripts/tfs-ops.py add-comment --id {DEMAND_ID} --comment "AI自动开发端到端完成: PR已合并"
```
如果有任一仓库 PR 失败 → 跳过此步骤（不添加 AI-AUTO-DONE）。
`LOG 提交+PR "[Step 4.4.1] MCP add-tags(AI-AUTO-DONE) → {status}"`

**4.5 Worktree 处理**：

读取 `{DOCS_DIR}/.worktree-mode`：
- `true` → 保留 worktree 目录，输出路径到日志
  ```bash
  WT_PATH=$(cat {DOCS_DIR}/.worktree-path 2>/dev/null)
  LOG 提交+PR "[Step 4.5] Worktree 保留: $WT_PATH"
  ```
- `false` → 保留 feature 分支，全流程结束后切回配置的 BASE_BRANCH（见 Step 7.10.5）

**必须执行 WinMetrics 阶段完成事件**：
```bash
$PYTHON SKILL_DIR/scripts/winmetrics-report.py stage-complete --stage submit --status success --duration {ELAPSED} --docs-dir {DOCS_DIR}
```

### Step 5: 构建（脚本驱动，无子代理）

**前置检查**：读取 `.pr-status`，判断 PR 状态：
- 如果**所有**仓库 pr_status=failed → 返回 failed，不触发构建
- 如果**部分**仓库 PR 失败 → 继续构建（需求维度触发）
- 无仓库 PR 失败 → 正常继续

**必须执行 WinMetrics 阶段开始事件**：
```bash
$PYTHON SKILL_DIR/scripts/winmetrics-report.py stage-start --stage build --skill devops-mcp --docs-dir {DOCS_DIR}
```

1. 准备参数：
```bash
REPO_COLLECTION=$(cat {DOCS_DIR}/.repo-collection)
$PYTHON SKILL_DIR/scripts/build-manager.py trigger --demand_id {DEMAND_ID} --collection {REPO_COLLECTION}
```
`LOG 构建 "[Step 5.1] MCP build_single_demand(demand_id={DEMAND_ID}, collection={REPO_COLLECTION}) → {status}"`
2. 解析触发结果：
```bash
$PYTHON SKILL_DIR/scripts/build-manager.py parse-trigger --result-file {PATH}
```
3. 轮询构建状态：
```bash
$PYTHON SKILL_DIR/scripts/build-manager.py poll --demand_id {DEMAND_ID} --collection {REPO_COLLECTION}
```
`LOG 构建 "[Step 5.3] 轮询 {n}/{max}: result={result}"`（每次轮询）
`LOG 构建 "[Step 5.3] 构建状态检查结果: {result}"`（终态时）
4. 写入状态文件：
```bash
$PYTHON SKILL_DIR/scripts/stage-helper.py write-status --file {DOCS_DIR}/.build-status --value "{success|failed|timeout}"
```

**必须执行 WinMetrics 阶段完成事件**：
```bash
$PYTHON SKILL_DIR/scripts/winmetrics-report.py stage-complete --stage build --status {STATUS} --duration {ELAPSED} --docs-dir {DOCS_DIR}
```

### Step 6: 部署（脚本驱动，无子代理）

检查 build-status，非 success 则跳过。

**必须执行 WinMetrics 阶段开始事件**：
```bash
$PYTHON SKILL_DIR/scripts/winmetrics-report.py stage-start --stage deploy --skill devops-mcp --docs-dir {DOCS_DIR}
```

1. 准备参数：
```bash
DEPLOY_ENV_ID=$(cat {DOCS_DIR}/.deploy-env-id)
$PYTHON SKILL_DIR/scripts/deploy-manager.py trigger --demand_id {DEMAND_ID} --env-id {DEPLOY_ENV_ID}
```
`LOG 部署 "[前置] 目标环境: {DEPLOY_ENV_ID} (来源: products.yaml)"`
`LOG 部署 "[Step 6.1] MCP trigger_deploy(demandId={DEMAND_ID}, envId={DEPLOY_ENV_ID}) → {status}, stepId={stepId}, 环境={name}"`
2. 解析触发结果：
```bash
$PYTHON SKILL_DIR/scripts/deploy-manager.py parse-trigger --result-file {PATH}
```
3. 轮询部署状态：
```bash
$PYTHON SKILL_DIR/scripts/deploy-manager.py poll --step-id {stepId}
```
`LOG 部署 "[Step 6.3] 轮询 {n}/{max}: status={status}"`（每次轮询）
`LOG 部署 "[Step 6.3] 部署终态: {status}"`（终态时）
4. 写入状态文件：
```bash
$PYTHON SKILL_DIR/scripts/stage-helper.py write-status --file {DOCS_DIR}/.deploy-status --value "{success|failed|timeout|skipped}"
```

**必须执行 WinMetrics 阶段完成事件**：
```bash
$PYTHON SKILL_DIR/scripts/winmetrics-report.py stage-complete --stage deploy --status {STATUS} --duration {ELAPSED} --docs-dir {DOCS_DIR}
```

### Step 7: 报告（脚本驱动，无子代理）

**必须执行 WinMetrics 阶段开始事件**：
```bash
$PYTHON SKILL_DIR/scripts/winmetrics-report.py stage-start --stage report --skill "" --docs-dir {DOCS_DIR}
```

**7.1 生成报告**：
```bash
$PYTHON SKILL_DIR/scripts/stage-helper.py generate-report --docs-dir {DOCS_DIR} --demand_id {DEMAND_ID} --product {产品名}（不传 --template，报告由脚本内置段落 + 状态文件自动组装）
```
`LOG 报告 "[Step 7.1] 报告生成完成: ai-report.md ({sections}段)"`

**7.1.1 Worktree 信息（条件输出）**：

如果 `.worktree-mode` 为 `true`，在报告末尾追加 worktree 信息段落：
```bash
WT_PATH=$(cat {DOCS_DIR}/.worktree-path 2>/dev/null)
if [ -n "$WT_PATH" ]; then
    cat >> {DOCS_DIR}/ai-report.md <<WTEOF

## Worktree 信息

- 模式: worktree 隔离
- 路径: \`$WT_PATH\`
- 仓库:
WTEOF
    for repo_dir in "$WT_PATH"/*/; do
        [ -d "$repo_dir" ] || continue
        repo_name=$(basename "$repo_dir")
        branch=$(cd "$repo_dir" && git branch --show-current 2>/dev/null || echo 'unknown')
        echo "  - $repo_name: \`$repo_dir\` (branch: $branch)" >> {DOCS_DIR}/ai-report.md
    done
    echo "" >> {DOCS_DIR}/ai-report.md
    echo "> 清理命令: \`bash $SKILL_DIR/scripts/setup-worktree.sh remove {产品名} {DEMAND_ID}\`" >> {DOCS_DIR}/ai-report.md
fi
```

报告模板必须包含：基本信息、PM分析摘要、开发指令摘要、代码变更详情、DDL变更、评审结果、PR创建结果、PR流水线结果、构建结果、部署结果、需求校验结果、单元测试结果、跳过/失败原因。

条件段落：
- 降级模式 → 报告顶部醒目降级告警
- PR 创建失败 → 报告顶部醒目 PR 失败告警

**7.2 附件上传（3 步协议）**：
1. 查询已有附件：
```bash
$PYTHON SKILL_DIR/scripts/tfs-ops.py list-attachments --id {DEMAND_ID} --collection {DEMAND_COLLECTION}
```
2. 对比已有附件名，仅上传缺失文件（ai-report.md 必传，dev-plan.md/summary.md 补传，跳过 AI-UNIT-TEST-* 前缀）
`LOG 报告 "[Step 7.2] MCP tfs_upload_attachment({name}) → {status}"`（每个上传文件）
3. 二次验证：再次查询附件列表，确认数量合理，如有缺失则补传
`LOG 报告 "[Step 7.2] 附件验证: 已有{n}个, 补传{m}个"`

**7.3 添加 AI-CODING 标签（验证后再添加）**：
1. 查询父子关系：
```bash
$PYTHON SKILL_DIR/scripts/tfs-ops.py get-relations --id {DEMAND_ID}
```
2. 检查 TASK_ID 是否在子项列表中：
   - 验证通过：add-tags DEMAND_ID "AI-CODING" + add-comment + add-tags TASK_ID "AI-CODING"
   - 验证失败（或降级模式）：add-tags DEMAND_ID "AI-CODING" + add-comment，不给 Task 添加标签
   `LOG 报告 "[Step 7.3] 标签添加完成: 验证结果={result}"`

**7.4 校验警告标签**（条件执行）：
if .verify-status == "warn":
```bash
$PYTHON SKILL_DIR/scripts/tfs-ops.py add-tags --id {DEMAND_ID} --tags "AI-VERIFY-WARN"
```

**7.5 构建通知 stages 数组**：

| 阶段 | 判定方式 |
|------|---------|
| Preflight | 已到达 Step 0 → "success"，否则流水线终止 |
| 环境准备 | 已到达 Step 7 → "success" |
| 规格生成 | .spec-status: confirmed→"success", pass→"success"（待确认）, fail→"failed", 不存在→"skipped" |
| 需求分析 | dev-plan.md 存在 → "success"（需 .spec-confirmed） |
| 编码开发 | summary.md 存在 → "success" |
| 需求校验 | .verify-status: pass/warn→"success", fail→"failed", 不存在→"skipped" |
| 单元测试 | .unit-test-result: SUCCESS/PARTIAL→"success", FAILED→"failed", N/A→"skipped" |
| 提交+PR | .pr-status: 全部 success/review-wait→"success", 部分失败→"warn", 全部失败→"failed", 不存在→"skipped" |
| 构建 | .build-status: success→"success", failed→"failed", 不存在→"skipped" |
| 部署 | .deploy-status: success→"success", failed→"failed", 不存在→"skipped" |
| 报告通知 | 已在执行→"success" |

**7.6 WinMetrics 补发（必须执行）**：
```bash
$PYTHON SKILL_DIR/scripts/winmetrics-report.py retry-fallback --docs-dir {DOCS_DIR}
```

**7.7 WinMetrics 流水线终态事件（必须执行）**：
```bash
$PYTHON SKILL_DIR/scripts/winmetrics-report.py summary --demand_id {DEMAND_ID} --stages '{stages_json}' --product {产品名} --docs-dir {DOCS_DIR}
```

**7.8 通知**：
```bash
$PYTHON SKILL_DIR/scripts/stage-helper.py gen-notify-ext --docs-dir {DOCS_DIR} --demand_id {DEMAND_ID} --type success
bash SKILL_DIR/scripts/wechat-notify.sh success {产品名} {DEMAND_ID} "{DEMAND_TITLE}" {DOCS_DIR}/success-ext.json
```
`LOG 报告 "[Step 7.8] 企微通知已发送({type}), {产品名} {DEMAND_ID}"`

**7.9 移除并发锁**：
```bash
rm {DOCS_DIR}/.lock
```

**7.10 写入 result-marker.txt**。
`LOG 报告 "[Step 7.10] result-marker.txt已写入, STATUS={status}"`

**7.10.5 分支回切（worktree=false 时）**：

如果 `.worktree-mode` 为 `false`（或不存在），全流程已完成，将每个仓库的本地分支切回 products.yaml 中配置的 BASE_BRANCH。

**⚠️ 安全保护**：回切前先检测未提交变更，若有则 stash 保留，避免静默丢弃用户数据：
```bash
if [ "$(cat {DOCS_DIR}/.worktree-mode 2>/dev/null)" != "true" ]; then
    while IFS='|' read -r repo_name repo_url base_branch _rest; do
        REPO_DIR="{WORK_DIR}/$repo_name"
        if [ -d "$REPO_DIR/.git" ] || git -C "$REPO_DIR" rev-parse --git-dir >/dev/null 2>&1; then
            cd "$REPO_DIR"
            # 安全保护：stash 未提交变更，避免 checkout 时静默丢弃
            if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
                STASH_MSG="auto-dev-backup-$repo_name-$(date +%Y%m%d-%H%M%S)"
                git stash push -u -m "$STASH_MSG" 2>/dev/null || true
                LOG_WARN 报告 "[Step 7.10.5] $repo_name 存在未提交变更，已 stash 保留: $STASH_MSG (恢复: git stash pop)"
            fi
            git checkout "$base_branch" 2>/dev/null
            if [ $? -eq 0 ]; then
                git pull origin "$base_branch" --ff-only 2>/dev/null || true
                LOG 报告 "[Step 7.10.5] 分支已切回: $repo_name → $base_branch"
            else
                LOG_WARN 报告 "[Step 7.10.5] 分支切回失败: $repo_name, 目标=$base_branch"
            fi
        fi
    done < {DOCS_DIR}/.repos
fi
```
`LOG 报告 "[Step 7.10.5] worktree=false, 本地分支已切回配置的 BASE_BRANCH"`（仅 worktree=false 时）

**7.11 WinMetrics 阶段完成（必须执行）**：
```bash
$PYTHON SKILL_DIR/scripts/winmetrics-report.py stage-complete --stage report --status {STATUS} --duration {ELAPSED} --docs-dir {DOCS_DIR}
```

---

## 中间阶段失败处理

当任意阶段失败时：
1. `stage-helper.py write-result --docs-dir {DOCS_DIR} --stage {NAME} --status failed`
2. `winmetrics-report.py stage-failed --stage {NAME} --error "{MSG}" --docs-dir {DOCS_DIR}`
`LOG_ERROR {NAME} "阶段失败: {MSG}"`
3. 构建失败 stages 数组（失败阶段之前按状态文件判定，失败阶段标 "failed"，之后标 "skipped" reason="前置阶段失败"）
4. `$PYTHON SKILL_DIR/scripts/stage-helper.py gen-notify-ext --docs-dir {DOCS_DIR} --demand_id {DEMAND_ID} --type fail --fail-step "{STAGE}" --fail-reason "{MSG}"`
5. `wechat-notify.sh fail {产品名} {DEMAND_ID} "{DEMAND_TITLE}" {DOCS_DIR}/fail-ext.json`
6. WinMetrics summary + retry-fallback
7. 移除锁
8. 输出失败汇总

---

## 批量模式

**触发**：多个需求号

**流程**：
1. **启动通知**：
```bash
mkdir -p "${HOME:-$USERPROFILE}/auto-dev-docs/.batch"
echo '{"demand_list": [{"task_id": "1506090", "title": "...", "product": "..."}]}' > "${HOME:-$USERPROFILE}/auto-dev-docs/.batch/start.json"
bash SKILL_DIR/scripts/wechat-notify.sh start {产品名} batch "批量启动" "${HOME:-$USERPROFILE}/auto-dev-docs/.batch/start.json"
```

2. **串行处理**：每个需求独立执行 Preflight → Step 0 → Step 0.5 → Step 1-7。一个需求失败不阻塞下一个。

3. **汇总**：收集每个需求的 result-marker.txt，生成汇总表。

4. **汇总通知**：
```bash
echo '{"total": 3, "success_list": [...], "skipped_list": [...], "failed_list": [...]}' > "${HOME:-$USERPROFILE}/auto-dev-docs/.batch/summary.json"
bash SKILL_DIR/scripts/wechat-notify.sh summary {产品名} summary "每日报告" "${HOME:-$USERPROFILE}/auto-dev-docs/.batch/summary.json"
```

---

## 需求/任务状态流转表

| 时机 | 对象 | 状态 | 原因 | 条件 |
|------|------|------|------|------|
| Preflight 检测失败 | 流水线 | 终止 | 环境缺失 | 无 DOCS_DIR，不创建 |
| Step 0 产品匹配 | 需求 | 活动 | 已受理 | - |
| Step 0.5.3 Spec 校验失败 | 流水线 | 终止 | 规格不完整 | .spec-status=fail |
| Step 0.5.4 用户未确认 | 流水线 | 暂停 | 等待用户确认 | .spec-status=pass，无 .spec-confirmed |
| Step 0.5.4 用户确认 | 流水线 | 继续 | 用户已确认 | 写入 .spec-confirmed |
| Step 1.2 创建分析任务 | AI分析任务 | 已创建 | - | 创建后，初始状态由 TFS 默认，需 .spec-confirmed |
| Step 1.3 分析任务激活 | AI分析任务 | 活动 | 调查 | 创建后 |
| Step 1.6 分析完成 | AI分析任务 | 已解决 | 已完成并且需要评审/测试 | 分析内容写入后 |
| Step 1.7 分析完成 | 需求 | 已分析 | 分析完成 | 只改 state 字段 |
| Step 2.3 代码完成 | AI开发任务 | 已创建 | - | 创建后，初始状态由 TFS 默认 |
| Step 2.3.1 开发任务描述 | AI开发任务 | - | - | 注入 dev-plan.md Development Instructions，降级模式跳过 |
| Step 3.1 创建校验任务 | 校验任务 | 已创建 | - | 创建后，初始状态由 TFS 默认 |
| Step 3.1 校验任务激活 | 校验任务 | 活动 | 调查 | 创建后 |
| Step 3.4 校验完成 | 校验任务 | 已解决 | 已完成并且需要评审/测试 | - |
| Step 4.1.2 提交推送后 | AI开发任务 | 活动 | 调查 | 非降级模式 |
| Step 4 提交后 | 人工测试任务 | 活动 | 调查 | 创建后 |
| Step 4 PR成功 | AI开发任务 | 已解决 | 已完成并且需要评审/测试 | 非降级模式，所有仓库PR成功 |
| Step 4 PR成功 | 需求 | 已解决 | 代码完成且通过系统测试 | 所有仓库PR成功 |
| Step 4 有PR失败 | AI开发任务 | 活动 | - | 保持现状，不更新状态 |
| Step 4 有PR失败 | 需求 | 已分析 | - | 保持现状，不更新状态 |

**状态变更容错规则（通用）**：所有 `tfs-ops.py update-state` 调用失败时，记录警告但继续执行。不因状态变更失败而中断流水线。

---

## 前置配置

| 配置项 | 位置 |
|--------|------|
| **OpenSpec CLI** | 全局安装 `openspec` 命令（Preflight 强制检测） |
| **Superpowers skills** | 环境变量 `SUPERPOWERS_SKILL_DIR` 或默认路径（Preflight 强制检测） |
| products.yaml | templates/products.yaml |
| TFS PAT | 环境变量或 git credentials |
| git credentials | ~/.git-credentials |
| 权限配置 | 项目 .claude/settings.json |

**Preflight 强制检测项**：
- OpenSpec CLI：必须可执行 `openspec --version` 或 `openspec --help`
- Superpowers 关键技能：必须存在以下文件
  - `test-driven-development/SKILL.md`
  - `systematic-debugging/SKILL.md`
  - `requesting-code-review/SKILL.md`
  - `verification-before-completion/SKILL.md`

详见 `references/products-config.md` 和 `references/permission-config-guide.md`。
