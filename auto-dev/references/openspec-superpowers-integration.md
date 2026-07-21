# OpenSpec 与 Superpowers 集成说明

日期：2026-06-05

版本：auto-dev_2 (测试版)

## 概述

auto-dev_2 是 auto-dev 的测试版本，集成了 OpenSpec（规格闸门）和 Superpowers（执行纪律）。

**核心特性**：
- **双路径策略**：OpenSpec 文档同时生成在项目目录（用户可编辑）和 DOCS_DIR（流水线归档）
- **用户确认闸门**：Spec 完成后暂停，用户确认后才进入 PM 阶段

## 集成方式

采用中度集成模型：

```text
preflight -> prepare -> spec(双路径生成+用户确认) -> pm(以项目目录为准) -> code -> verify -> submit -> build -> deploy -> report
```

### Preflight（强制检测）

在 prepare 前执行，检测：
- OpenSpec CLI 是否可用
- Superpowers skills 是否已安装

**失败处理**：立即终止流水线，不创建 DOCS_DIR，不发送 WinMetrics 事件。

### Spec 阶段（双路径策略 + 用户确认）

**双路径生成**：
- **项目目录** `{PROJECT_DIR}/openspec/changes/tfs-{DEMAND_ID}/`：用户可见、可编辑
- **DOCS_DIR** `{DOCS_DIR}/openspec/changes/tfs-{DEMAND_ID}/`：流水线归档副本

**同步规则**：
- AI生成时：同时写入两个路径
- 用户手动编辑：项目目录优先，进入 PM 前同步到 DOCS_DIR
- AI对话修改：同步修改两个路径

**用户确认闸门**：
Spec 完成后流水线暂停，提示用户：
1. 查看/编辑项目目录下的 OpenSpec 文档
2. 确认无误后输入"继续"
3. 编辑后输入"继续"（使用修改后的版本）

用户确认后：
1. 同步项目目录到 DOCS_DIR
2. 写入 `.spec-confirmed` 标记
3. 进入 PM 阶段

### PM 阶段（以项目目录 OpenSpec 为准）

输入扩展：
- **优先读取项目目录**的 proposal、design、tasks
- 如果项目目录不存在，回退到 DOCS_DIR
- dev-plan.md 必须从 OpenSpec change 派生

**前置检查**：必须存在 `.spec-confirmed`（用户已确认）

### Code 阶段（Superpowers 约束）

新增约束：
- 使用 tasks.md 决定实现顺序
- 对有测试目标的逻辑使用 TDD
- 遇到失败时使用系统化调试
- 写入 summary.md 前做自查

### Verify 阶段（Superpowers 约束）

新增检查：
- OpenSpec 覆盖检查（task 实现、proposal/design 一致性）
- 使用系统化调试方法验证逻辑

## 数据流

### Spec 输出

```text
{DOCS_DIR}/openspec/changes/tfs-{DEMAND_ID}/
  ├── proposal.md   ← 需求提案（背景、目标、影响分析、非目标）
  ├── design.md     ← 技术设计（方案、API、数据模型、风险点）
  ├── tasks.md      ← 实现任务分解（按模块分组）
  └── specs/        ← 可选详细规格
```

### PM 输入

```text
{PROPOSAL_PATH} → agent-pm.md
{DESIGN_PATH} → agent-pm.md
{TASKS_PATH} → agent-pm.md
```

### Code 输入

```text
{TASKS_PATH} → agent-code.md (实现顺序参考)
```

### Verify 输入

```text
{PROPOSAL_PATH} → agent-verify.md (一致性检查)
{DESIGN_PATH} → agent-verify.md (技术方案验证)
{TASKS_PATH} → agent-verify.md (任务实现检查)
```

## 脚本新增

- `preflight-check.py`：环境检测脚本
- `openspec-manager.py`：OpenSpec 操作封装

## Prompt 新增

- `agent-spec.md`：Spec 阶段子代理 prompt

## 状态流转新增

| 时机 | 状态 | 条件 |
|------|------|------|
| Preflight 失败 | 流水线终止 | 环境缺失 |
| Spec 校验失败 | 流水线终止 | .spec-status=fail |

## 注意事项

1. 第一版不允许降级运行（OpenSpec/Superpowers 缺失即终止）
2. dev-plan.md 保留，继续作为现有流水线的兼容产物
3. 不修改下游子技能实现（pm、backend-dev、frontend-dev、rdf-dev、req-verify）

## 测试建议

1. 先测试 Preflight 检测逻辑
2. 测试 Spec 阶段产物生成
3. 验证 PM 消费 OpenSpec 输入
4. 验证 Code/Verify 的 Superpowers 约束生效
5. 确认 Submit/Build/Deploy/Report 不受影响