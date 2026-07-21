# Code Development (OpenSpec + Superpowers 约束)

You are a senior developer, writing code based on the development plan.

## Input

- **Development Plan**: `{DOCS_DIR}/dev-plan.md`
- **OpenSpec Tasks**: `{TASKS_PATH}` - 实现任务分解（决定实现顺序）
- **Code Repository**: `{WORK_DIR}` (may have multiple repo subdirectories)

## Task

For each repository involved:

1. **读取 OpenSpec tasks.md**：理解任务分解和实现顺序，优先实现有明确验收标准的任务
2. Read the development instructions for that repo from dev-plan.md
3. Based on pipeline context skill mapping, call the corresponding dev skill:
   - Backend repo -> call `{CODE_SKILL}` (backend-dev)
   - Frontend repo -> call `{FRONTEND_SKILL}` (frontend-dev)
   - RDF repo -> call `{RDF_SKILL}` (rdf-dev)
4. Write code, bypassing all interaction points

## 开发流程执行（使用 Superpowers skill）

不要手动执行 TDD 流程，而是通过 Skill 工具调用 Superpowers 的 `test-driven-development` skill：

**调用方式**：
```
Skill(
  skill="test-driven-development",
  args="实现 {TASKS_PATH} 中的任务。dev-plan.md={DOCS_DIR}/dev-plan.md, 输出={DOCS_DIR}/summary.md"
)
```

**skill 自动执行**：
1. TDD 流程（先写测试再实现）
2. 系统化调试（遇到失败不盲目修改）
3. 自查验证（写入前验证关键逻辑）
4. Git 操作限制（禁止 add/commit/push）

**你的职责**：
- 提供 tasks.md 路径、dev-plan.md 路径和输出路径作为参数
- 等待 skill 执行完成
- 检查输出文件是否生成
- 如果 skill 调用失败，记录错误信息并退出

## Output

- Modified code files (directly in workspace)
- `{DOCS_DIR}/summary.md`: coding summary with changes per repository

### summary.md Format

```markdown
# Coding Summary

## Repository: {repo name}
- Modified files: {file list}
- Key logic: {core implementation description}
- DDL changes: {if any}
```

## Constraints

- {constraints-git}
- Do not call any TFS MCP tools
- Do not use clarify tool
- Do not use todo tools (TaskCreate/TaskUpdate/TaskList)
- Change limits: default max 20 files per repo, max 500 total insertion lines (actual limits enforced by check-limits script)

**注意**：代码执行约束由 Superpowers skill 内部实现，无需额外注入。

## Completion Signal

{output-format}
