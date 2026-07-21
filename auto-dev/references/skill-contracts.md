# 技能接口契约

本文档定义可替换技能的输入/输出接口约束。
替换技能必须满足契约才能正确接入流水线。

---

## pm 技能契约

**输入**：
- `{DOCS_DIR}/附件/` - TFS 工作项附件（PRD、原型图等）

**输出**：
- `{DOCS_DIR}/dev-plan.md` - 开发计划，包含：
  - 需求概述
  - 涉及仓库及改动点
  - 开发步骤
  - 风险点

**注意**：`.analysis-task-id` 由主代理在 Step 1.2 通过 `tfs-ops.py create-task` 创建并写入，非 PM 子技能输出。

**失败处理**：
- 输出 `dev-plan.md` 缺失 → 阻断流程

---

## code 技能契约（backend-dev/frontend-dev/rdf-dev 共用）

**输入**：
- `{DOCS_DIR}/dev-plan.md` - PM 阶段输出的开发计划
- `{WORK_DIR}/{仓库名}/` - git worktree 工作目录

**输出**：
- `{DOCS_DIR}/summary.md` - 编码总结

**注意**：`.task-id` 由主代理在 Step 2.3 通过 `tfs-ops.py create-task` 创建并写入，非编码子技能输出。

**失败处理**：
- `summary.md` 缺失 → 阻断流程

---

## frontend 技能契约

同 code 技能契约。

---

## rdf 技能契约

同 code 技能契约。

---

## test 技能契约

**输入**：
- `{WORK_DIR}/{仓库名}/` - 代码变更
- `{DOCS_DIR}/dev-plan.md` - 开发计划

**输出**：
- `{DOCS_DIR}/.unit-test-result` - 测试总体结果（SUCCESS/PARTIAL/FAILED/N/A）

**失败处理**：
- 输出缺失 → 警告但不阻断流程

---

## 不可替换技能说明

以下技能依赖企业基础设施或核心流程，不可替换：

| 技能 | 原因 |
|------|------|
| verify | 输出 `.verify-status` 是 submit 阶段强依赖 |
| submit | 提交规范是核心流程，必须关联 Task ID |
| pr | 依赖 MCP 服务 `create_pr/query_pr_status` |
| build | 依赖 MCP 服务 `build_single_demand` |
| deploy | 依赖 MCP 服务 `trigger_deploy/query_deploy_progress` |