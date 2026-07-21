# Auto-Dev 全链路自动化开发

> 全自动开发流水线 — 输入 TFS 工作项 ID，从需求分析到代码提交 PR 一站式完成。
> **v2.1.0 混合编排模式**：脚本负责确定性操作，子代理专注于推理任务（PM/Code/Verify）。

## 功能特性

- **混合编排架构**：脚本处理 MCP 调用、轮询、状态管理；子代理仅做 PM 分析、代码开发、需求校验
- **全链路自动化**：PM 分析 → 编码 → 校验 → Git 提交 → TFS PR → 构建 → 部署 → 报告
- **多技能路由**：根据标签自动路由到 backend-dev、frontend-dev、rdf-dev
- **FULLSTACK 串行策略**：后端 → 前端 → RDF 按依赖顺序执行
- **批量处理**：支持单工作项或多需求号批量处理
- **降级容错**：Task 创建失败时自动降级，告警通知三处触发
- **并发保护**：锁文件机制防止同一需求被重复处理

## 快速开始

### 1. 触发方式

```
自动开发 1506090
全自动开发需求 1506090
批量开发 1506090 1506091 1506092
```

### 2. 前置配置

| 配置项 | 说明 | 必须 |
|--------|------|------|
| `templates/products.yaml` | 产品仓库配置表 | 是 |
| TFS PAT Token | 环境变量或 git credentials | 是 |
| git credentials | `~/.git-credentials`，用于 clone/push 免密 | 是 |
| `WECHAT_WEBHOOK_URL` | 企微通知 Webhook | 否 |

### 3. TFS 标签体系

| 标签 | 含义 | 路由策略 |
|------|------|----------|
| `AI-AUTO-DEV` | 必须有 | — |
| `AI-BACKEND` | 后端任务 | 只路由到 backend-dev 仓库 |
| `AI-FRONTEND` | 前端任务 | 只路由到 frontend-dev 仓库 |
| `AI-RDF` | RDF 快开任务 | 只路由到 rdf-dev 仓库 |
| `AI-FULLSTACK` | 全栈 | 串行：code→frontend→rdf |

## 架构（v2.1.0）

```
主代理（读 SKILL.md → 编排）
  ├─ Step 0: 准备（脚本 + MCP）
  ├─ Step 1: PM 分析（子代理）
  ├─ Step 2: 代码开发（子代理）
  ├─ Step 3: 需求校验（子代理）
  ├─ Step 3.5: 单元测试（条件执行，脚本驱动）
  ├─ Step 4: 提交+PR（脚本 + MCP）
  ├─ Step 5: 构建（脚本 + MCP）
  ├─ Step 6: 部署（脚本 + MCP）
  └─ Step 7: 报告（脚本 + MCP）
```

子代理仅用于推理密集型任务（PM 分析、代码生成、需求校验），通过模板展开注入 prompt。
提交/构建/部署/报告阶段完全由脚本驱动，无子代理。

## 目录结构

```
SKILL_DIR/
  ├── SKILL.md                     ← 编排协议（v2.1.0 核心）
  ├── README.md                    ← 本文件
  ├── config.env.example           ← 环境配置模板
  ├── prompts/
  │   ├── agents/                  ← 子代理 prompt
  │   │   ├── agent-pm.md          ← PM 需求分析
  │   │   ├── agent-code.md        ← 代码开发
  │   │   └── agent-verify.md      ← 需求校验
  │   └── snippets/                ← 可复用片段
  │       ├── constraints-code.md  ← 代码生成约束
  │       ├── constraints-git.md   ← Git 禁令
  │       └── output-format.md     ← 完成信号格式
  ├── references/
  │   ├── bypass-strategies.md     ← 各技能的 bypass 策略表
  │   ├── products-config.md       ← products.yaml 配置说明
  │   ├── permission-config-guide.md
  │   ├── skill-contracts.md       ← 可替换技能的输入/输出契约
  │   └── sql-syntax-guide.md      ← SQL 语法指南
  ├── templates/
  │   ├── products-template.yaml   ← 产品配置模板
  │   ├── pipeline-template.yaml   ← 流水线配置模板
  │   └── project-settings.json    ← 项目权限配置模板
  ├── release/                     ← 版本发布说明
  ├── examples/
  │   └── pm-teamB/                ← PM 技能替换示例
  └── scripts/
      ├── lib/mcp_protocol.py      ← MCP_CALL 协议工具库
      ├── lib/pipeline_utils.py    ← pipeline 配置校验工具库
      ├── lib/product_utils.py     ← products 配置生成工具库
      ├── stage-helper.py          ← 阶段生命周期（日志/结果/限制/锁）
      ├── winmetrics-report.py     ← WinMetrics 事件上报（自动 run_id 追踪）
      ├── tfs-ops.py               ← TFS 工作项操作
      ├── pr-manager.py            ← PR 创建与轮询
      ├── build-manager.py         ← 构建触发与轮询
      ├── deploy-manager.py        ← 部署触发与轮询
      ├── parse-products.py        ← products.yaml 解析
      ├── parse-pipeline.py        ← pipeline.yaml 解析
      ├── configure-pipeline.py    ← 交互式流水线配置向导
      ├── add-product.py           ← 交互式产品配置向导
      ├── register-product.py      ← 产品自动注册
      ├── detect-local-repos.sh    ← 本地 TFS 仓库扫描
      ├── setup-worktree.sh        ← worktree 管理
      ├── wechat-notify.sh         ← 企微通知（Shell 入口）
      └── wechat-notify.py         ← 企微通知（Python 实现）
```

## 脚本清单

| 脚本 | 职责 |
|------|------|
| `mcp_protocol.py` | MCP_CALL/MCP_CALL_POLL/DRY_RUN 输出格式化，结果文件读写 |
| `pipeline_utils.py` | pipeline.yaml 校验、技能前缀检查、配置加载 |
| `product_utils.py` | products.yaml 生成、字段校验 |
| `stage-helper.py` | init-stage, log, write-result, write-status, check-limits, check-lock, generate-report |
| `winmetrics-report.py` | HMAC 签名事件上报，run_id 自动追踪，重试+回退，批量重发 |
| `tfs-ops.py` | 工作项 CRUD（get/create/update-state/add-tags/add-comment/attachment），MCP 参数准备+结果解析 |
| `pr-manager.py` | PR 创建参数准备 + 轮询策略 + 结果解析 |
| `build-manager.py` | 构建触发参数准备 + 轮询策略 + 结果解析 |
| `deploy-manager.py` | 部署触发参数准备 + 轮询策略 + 结果解析 |
| `parse-products.py` | products.yaml 解析，支持多字段查询输出 |
| `parse-pipeline.py` | pipeline.yaml 解析，stages/skill-map/validate/defaults |
| `configure-pipeline.py` | 交互式流水线配置向导 |
| `add-product.py` | 交互式产品配置向导 |
| `register-product.py` | 自动检测本地仓库并注册产品 |
| `detect-local-repos.sh` | 扫描本地 TFS 仓库，输出仓库 URL 列表 |
| `setup-worktree.sh` | git worktree 创建与管理 |
| `wechat-notify.sh` | 企微通知 Shell 入口，调用 wechat-notify.py |
| `wechat-notify.py` | 企微通知 Python 实现，支持 start/success/fail/summary 类型 |

## 可配置流水线

```bash
# 交互式向导
python scripts/configure-pipeline.py

# 校验配置
python scripts/parse-pipeline.py validate
```

## 依赖技能

| 技能 | 用途 |
|------|------|
| `pm` | 需求分析，输出开发指令 |
| `backend-dev` | Java Spring Boot 后端开发 |
| `frontend-dev` | Vue 3 前端开发 |
| `rdf-dev` | RDF 快开框架开发 |
| `req-verify` | 需求-代码一致性校验 |
| `git-merge` | Git 提交推送与分支合并 |
| `devops-mcp` | PR 创建、构建触发、自动部署 |

## 注意事项

- **不要触发场景**：`开发需求 1506090`（无"自动"前缀）路由到单技能，不走全链路
- **产品匹配**：6 级降级链（Module.name → 标题前缀 → 本地扫描 → 自动注册 → 用户选择 → 跳过）
- **降级模式**：Task 创建失败时代码直接关联需求 ID，三处告警触发
- 详细配置说明见 `references/products-config.md`
