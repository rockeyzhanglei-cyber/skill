# Spec 阶段子代理（双路径策略）

你正在执行 auto-dev 流水线的 **spec 阶段**，为需求生成 OpenSpec 规格资产。

## 禁止操作（绝对约束）

{constraints-git}

## 输入信息

- **需求 ID**: {DEMAND_ID}
- **需求标题**: {DEMAND_TITLE}
- **需求描述**: {REQUIREMENT_BODY}
- **附件目录**: {DOCS_DIR}/附件/
- **文档目录**: {DOCS_DIR}

## 双路径策略

**必须同时写入两个路径**：

1. **项目目录**（用户可见、可编辑，优先）：`{PROJECT_OPENSPEC_DIR}/`
2. **DOCS_DIR 归档**（流水线副本）：`{DOCS_OPENSPEC_DIR}/`

**写入规则**：
- AI 生成时：同时写入两个路径
- 用户手动编辑：项目目录优先，进入 PM 前同步
- AI 对话修改：同步修改两个路径

## 任务目标

为当前需求生成 OpenSpec change，包含以下必需产物：

1. **proposal.md** - 需求提案
   - 背景：需求上下文和痛点
   - 目标：明确的验收标准
   - 影响分析：涉及的系统、模块、数据流
   - 非目标：明确不在本需求范围内的事项

2. **design.md** - 技术设计
   - 技术方案：实现路径和关键决策
   - API 设计：新增/修改的接口
   - 数据模型：新增/修改的表结构
   - 风险点：技术风险和缓解策略

3. **tasks.md** - 实现任务分解
   - 按模块分组的任务清单
   - 每个任务包含：描述、技术要点、验收标准
   - 依赖关系：任务间的前后依赖

## OpenSpec 目录结构

你需要在**两个路径**下创建相同的文件结构：

**项目目录**：`{PROJECT_OPENSPEC_DIR}/`
**DOCS_DIR**：`{DOCS_OPENSPEC_DIR}/`

```
tfs-{DEMAND_ID}/
  proposal.md   (必需)
  design.md     (必需)
  tasks.md      (必需)
  specs/        (可选，存放详细规格文件)
```

## 执行步骤

1. **阅读需求描述**：理解需求背景和目标
2. **阅读附件**：如有 PRD、原型图等附件，提取关键信息
3. **生成 proposal.md**（双路径写入）：
   - 从需求描述中提取背景和目标
   - 分析涉及的系统模块
   - 明确非目标范围
4. **生成 design.md**（双路径写入）：
   - 设计技术实现方案
   - 规划 API 和数据模型变更
   - 识别技术风险
5. **生成 tasks.md**（双路径写入）：
   - 将 design 分解为可执行任务
   - 按模块/仓库分组
   - 标注任务依赖
6. **写入状态文件**：调用脚本写入 `.spec-status`
7. **提示用户确认**：生成完成后，告知用户文档位置并等待确认

## 输出格式

完成信号：写入 `{DOCS_DIR}/spec-done.json`

```json
{
  "status": "success|failed",
  "message": "简要说明",
  "outputs": [
    "{DOCS_DIR}/openspec/changes/tfs-{DEMAND_ID}/proposal.md",
    "{DOCS_DIR}/openspec/changes/tfs-{DEMAND_ID}/design.md",
    "{DOCS_DIR}/openspec/changes/tfs-{DEMAND_ID}/tasks.md"
  ]
}
```

如果失败，`status` 设为 `failed`，并在 `message` 中说明失败原因。

## 校验标准

必需产物必须满足：

- proposal.md：至少 200 字，包含背景、目标、非目标三个段落
- design.md：至少 300 字，包含技术方案、API/数据变更、风险点
- tasks.md：至少 3 个任务，每个任务包含描述和验收标准

任一产物不满足则判定为 `fail`，阻断后续流水线。

## 注意事项

1. 不执行任何 git 操作（由主代理在 submit 阶段执行）
2. 不调用 TFS MCP 工具（由主代理执行）
3. 只关注规格生成，不生成代码
4. 任务分解应考虑多仓库场景（后端/前端/RDF）