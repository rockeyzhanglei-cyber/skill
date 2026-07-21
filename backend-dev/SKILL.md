---
name: backend-dev
description: |
  Java Spring Boot / AKSO 框架后端开发 Skill。

  **必须触发**：用户要进行 Java 后端开发、接口实现、功能开发。

  触发关键词（包含以下任一即触发）：
  - "开发需求" + 数字：如"开发需求 1506090"、"帮我开发需求 1506090"、"开发需求号"
  - "实现需求" + 数字：如"实现需求 1506090"、"帮我实现需求"
  - "开发工作项" / "实现工作项"：如"开发工作项 1506090"
  - "开发接口" / "实现接口" / "写接口" / "新增接口"
  - "后端开发" / "Java 后端" / "Spring Boot 开发" / "AKSO 开发"
  - 技术术语：Controller、Service、Repository、RPC、Feign、WinMvcResponse、WinRpcResponse

  **不触发**：前端 Vue/React、Python/Go/Node.js、纯 SQL 优化、Docker/K8s
metadata:
  author: 晁兴鹏
  version: 1.0.0
---

# Java 后端开发 Skill (backend-dev)

## 概述

此 Skill 为后端工程师提供标准化的 Java/Spring Boot/AKSO 开发流程，确保：
1. **上下文感知** - 自动读取项目规范和 AKSO 框架约定
2. **计划先行** - 编码前生成详细的实施计划
3. **验证闭环** - 代码生成后必须运行测试验证
4. **风格统一** - 遵循 AKSO 框架使用规范

## 执行模式说明

本 Skill 的执行分为两个阶段，**全程在主对话中完成**：

| 阶段 | 步骤 | 说明 |
|------|------|------|
| **计划阶段** | Step 0-3 | 获取需求、分析设计、生成计划文件、用户确认 |
| **执行阶段** | Step 4-8 | 创建分支、编码、测试、记录、上传 |

**关键设计**：
- **不使用 EnterPlanMode**：直接在主对话中生成计划文件
- **计划保存到文件**：`docs/plans/yyyy-mm-dd-需求号.md`
- **用户确认后直接继续**：无需退出 Plan 模式，主对话继承 skill 步骤定义
- **全程在同一上下文**：避免 Plan 模式丢失 skill 步骤的问题
- **优雅降级**：优先使用 superpowers skills，不可用时回退到内置方式

## 核心流程

```
┌─────────────────┐
│   需求获取       │ ← TFS工作项 / PRD文档 / 用户描述
│  (Step 0)       │   下载附件到 product-docs/
└────────┬────────┘
         ▼
┌─────────────────┐
│ 需求分析与方案设计 │ ← superpowers:brainstorming（优先）
│  (Step 1)       │   或内置方式（读取上下文 + 手动分析）
└────────┬────────┘
         ▼
┌─────────────────┐
│   生成实施计划    │ ← superpowers:writing-plans（优先）
│  (Step 2)       │   或内置方式，保存到 docs/plans/
└────────┬────────┘
         ▼
┌─────────────────┐
│   用户审核计划    │ ← 人工确认后直接继续
│  (Step 3)       │
└────────┬────────┘
         ▼
┌─────────────────┐
│  创建开发分支     │ ← 确定子模块 → feature/需求号
│  (Step 4)       │
└────────┬────────┘
         ▼
┌─────────────────┐
│    编码实现      │ ← superpowers:executing-plans（优先）
│  (Step 5)       │   或内置方式，分层实现
└────────┬────────┘
         ▼
┌─────────────────┐
│   运行测试验证    │ ← mvn test
│  (Step 6)       │
└────────┬────────┘
         ▼
┌─────────────────┐
│  保存修改记录     │ ← /docs/feature/yyyy-mm-dd-需求号.md
│  (Step 7)       │
└────────┬────────┘
         ▼
┌─────────────────┐
│ 导出对话并上传TFS │ ← 上传附件 + 打标签 AI-CODING
│  (Step 8)       │
└─────────────────┘
```

**全程在主对话中执行，无需切换模式。**

## 执行步骤

### Step 0: 需求获取

**目标**: 从TFS或其他来源获取需求，下载相关文档

**需求来源识别**:
1. **TFS 工作项 ID** - 用户输入如 "实现工作项 1445554" 或 "1445554"
2. **PRD 文档路径** - 用户指定文档位置
3. **用户直接描述** - 用户直接说明需求内容

**处理流程**:

#### 情况A: TFS 工作项（推荐）

当识别到 TFS 工作项 ID 时：

1. **获取工作项详情**：
```javascript
mcp__tfs-mcp__tfs_get_workitem({
  id: 1445554
})
```

2. **创建需求文档目录**：
```bash
mkdir -p product-docs/1445554
```

3. **下载工作项附件**：
```javascript
mcp__tfs-mcp__tfs_download_attachments({
  id: 1445554,
  targetDir: "product-docs/1445554"
})
```

4. **提取需求信息**：
- 标题 → 功能名称
- 描述 → 需求详情
- 附件 → PRD/设计文档

5. **记录需求号**：用于后续分支命名和修改记录

**输出示例**:
```
📋 已获取需求:
- 工作项ID: 1445554
- 标题: 用户查询功能
- 附件: 3个文件已下载到 product-docs/1445554/
  ├── 需求文档.docx
  ├── 接口设计.xlsx
  └── 数据模型.png
```

#### 情况B: PRD 文档

当用户提供文档路径时：
```bash
# 读取文档
读取用户指定的 PRD 文档

# 复制到标准位置
cp [用户指定路径] product-docs/[需求号]/
```

#### 情况C: 用户直接描述

当用户直接描述需求时：
1. 提取功能点
2. 使用日期作为临时需求号：`YYYYMMDD`
3. 记录需求描述到 `product-docs/[日期]/需求描述.md`

---

### Step 1: 需求分析与方案设计

**目标**: 深入理解需求，设计技术方案，明确实现路径

#### 前置步骤：读取项目上下文（必须执行）

无论是否使用 superpowers，都需要先读取项目规范：

1. **读取项目 CLAUDE.md**：
   - 读取项目根目录的 `CLAUDE.md`
   - 提取关键信息：
     - Spring Boot 版本
     - Java 版本
     - AKSO 组件版本
     - ORM 框架 (JPA / MyBatis)
     - 构建工具 (Maven / Gradle)
     - 分层架构约定
     - 多租户处理方式

2. **读取 AKSO 框架规范**（如有）：
   - 查找项目中的 AKSO 规范文件
   - 理解框架特定约束

**输出示例**:
```
📋 已读取后端项目上下文:
- 框架: Spring Boot + AKSO 5.5.0
- ORM: JPA + Spring Data
- 多租户: TenancyContext (hospitalSOID)
- 异步: CompletableFutureBuilder
- 缓存: RedisAbility
- 检索: WinningElasticsearchTemplate
- 构建: Maven
- 分层: Controller → Service → Repository → Entity
```

#### 分析阶段：选择分析方式

**检测 superpowers 可用性**：
```
在 available_skills 列表中查找 "superpowers:brainstorming"
```

##### 情况 A: superpowers 可用（推荐）

调用 brainstorming skill 进行结构化分析：

```
使用 Skill 工具调用 superpowers:brainstorming

任务描述应包含：
- 需求来源（TFS 工作项 / PRD 文档 / 用户描述）
- 需求核心内容（Step 0 获取的信息）
- 技术栈背景（刚读取的 CLAUDE.md 内容）
- 输出要求（技术方案 + 实现路径）
```

brainstorming 会帮助：
1. **探索用户意图** - 理解真正要解决的问题
2. **需求澄清** - 识别模糊点和边界条件
3. **方案设计** - 提出多个候选方案并比较
4. **实现路径** - 明确具体的开发步骤

##### 情况 B: superpowers 不可用（回退方式）

执行内置分析流程：

1. **分析需求**：
   - 提取功能点
   - 识别技术约束
   - 确定涉及的模块和层级

2. **设计技术方案**：
   - 确定需要新增/修改的文件
   - 设计接口格式（请求/响应）
   - 规划数据流和依赖关系

**输出示例**:
```
📋 需求分析完成:
- 功能名称: 用户查询功能
- 技术栈: Spring Boot + AKSO 5.5.0
- 涉及层级: Controller → Service → Repository
- 核心技术点:
  - 多租户: TenancyContext (hospitalSOID)
  - ORM: JPA + Spring Data
  - 缓存: RedisAbility

📋 方案设计:
- 新增接口: POST /api/v1/web/user/query_list
- 新增文件: UserController, UserService, UserRepository
- 修改文件: UserEntity (新增查询字段)
```

### Step 2: 生成实施计划

**目标**: 在编码前规划好要修改/新增的文件和步骤

**检测 superpowers 可用性**：

首先检查 `superpowers:writing-plans` skill 是否可用：
```
在 available_skills 列表中查找 "superpowers:writing-plans"
```

#### 情况 A: superpowers 可用（推荐）

调用 writing-plans skill 生成规范的实施计划：

```
使用 Skill 工具调用 superpowers:writing-plans

任务描述应包含：
- Step 1 分析得出的技术方案
- 需求号（用于计划文件命名）
- 输出路径: docs/plans/yyyy-mm-dd-需求号.md
```

writing-plans 会帮助：
1. **结构化任务分解** - 将大任务拆分为可执行的小步骤
2. **依赖关系梳理** - 明确任务之间的依赖顺序
3. **验收标准定义** - 每个任务有明确的完成标准
4. **风险点识别** - 提前识别可能的技术难点

#### 情况 B: superpowers 不可用（回退方式）

使用内置的计划生成流程：

1. **创建计划目录**：
```bash
mkdir -p docs/plans
```

2. **生成实施计划文件**：

**文件命名规则**: `docs/plans/yyyy-mm-dd-需求号.md`
**示例**: `docs/plans/2024-01-15-1445554.md`

3. **计划内容包含**：
   - 需要修改的文件列表
   - 需要新增的文件列表
   - 接口设计（请求/响应格式）
   - 数据库变更（如需要）
   - 实施步骤（按任务拆分）

**计划模板**:
```markdown
# 实施计划: [功能名称]

**需求号**: 1445554
**日期**: 2024-01-15
**目标**: [一句话描述]

---

## 需要修改的文件

| 文件路径 | 修改说明 |
|----------|----------|
| `src/.../controller/UserController.java` | 新增查询接口 |

## 需要新增的文件

| 文件路径 | 说明 |
|----------|------|
| `src/.../service/UserQueryService.java` | 用户查询服务接口 |
| `src/.../service/impl/UserQueryServiceImpl.java` | 用户查询服务实现 |

## 接口设计

### 请求格式
```json
{
  "hospitalSOID": 123456,
  "userId": "xxx"
}
```

### 响应格式
```json
{
  "code": 200,
  "data": { ... }
}
```

## 实施步骤

### Task 1: 创建 Service 接口和实现
- [ ] 创建 UserQueryService.java
- [ ] 创建 UserQueryServiceImpl.java

### Task 2: 创建 Controller 接口
- [ ] 在 UserController 中新增查询方法

### Task 3: 运行测试验证
- [ ] mvn test
```

4. **展示计划给用户确认**

### Step 3: 用户审核

**目标**: 确保计划符合预期

**操作**:
1. 展示计划给用户
2. 等待用户确认或修改
3. 用户确认后直接继续执行 Step 4

**提示语**:
```
📋 实施计划已生成: docs/plans/2024-01-15-1445554.md

请审核计划内容，确认后回复"确认"或"开始实施"继续。
```

### Step 4: 创建开发分支

**目标**: 从主分支（或当前分支）创建功能开发分支

**重要**: 项目通常是多模块结构，父级目录不是 git 项目，子模块才是 git 项目。需要先确定涉及的子模块。

**操作**:

1. **确定需要修改的子模块**：

根据实施计划分析涉及的代码模块，识别需要创建分支的子模块：

```bash
# 扫描当前目录下的 git 子模块
find . -maxdepth 3 -name ".git" -type d | while read dir; do
  module=$(dirname "$dir" | sed 's|^\./||')
  echo "子模块: $module"
done
```

或直接查看常见的模块目录：
```bash
# 常见的模块目录结构示例
ls -la | grep "^d"
```

2. **询问用户确认子模块、分支策略和分支名格式**：

使用 `AskUserQuestion` 让用户选择：

**问题1 - 子模块和源分支**：
- **涉及哪些子模块** - 根据计划分析，列出可能涉及的子模块供用户选择
- **源分支选择** - 当前分支 / 主分支 / 其他分支

示例：
```
📋 根据计划分析，可能涉及以下子模块：
- wn-his-service
- wn-his-rpc
- wn-his-common

请确认需要创建分支的子模块和源分支。
```

**问题2 - 分支名格式**：

使用 `AskUserQuestion` 提供以下选项：

```
AskUserQuestion:
  question: "请选择分支名格式："
  options:
    - label: "feature/[需求号]"
      description: "功能开发分支，例如 feature/1445554"
    - label: "bugfix/[需求号]"
      description: "缺陷修复分支，例如 bugfix/1445555"
    - label: "手动输入"
      description: "自定义分支名，选择后请输入完整的分支名"
```

用户选择"手动输入"时，继续使用 `AskUserQuestion` 让用户输入完整的分支名。

3. **在各子模块中创建功能分支**：

对每个确认的子模块执行：
```bash
cd [子模块路径]

# 获取当前分支信息
git branch --show-current
git status

# 从源分支创建功能分支（使用用户选择的分支名格式）
git checkout -b [用户选择的分支名]
```

**分支命名规范**:
| 格式 | 示例 | 说明 |
|------|------|------|
| `feature/[需求号]` | `feature/1445554` | 功能开发（默认） |
| `bugfix/[需求号]` | `bugfix/1445555` | 缺陷修复 |
| 手动输入 | 用户自定义 | 完整分支名 |

4. **从源分支拉取最新代码**：

对每个子模块执行：
```bash
# 切换到源分支
git checkout [源分支名]

# 拉取远端最新代码
git pull origin [源分支名]

# 切换回功能分支（使用用户选择的分支名）
git checkout [用户选择的分支名]

# 合并源分支最新代码到功能分支
git merge [源分支名]
```

**处理冲突**（自动解决）：
- 优先保留功能分支的变更（`git merge -X theirs [源分支名]`）
- 如自动解决失败，提示用户确认后继续

5. **推送到远端**：

对每个子模块执行：
```bash
# 首次推送新分支到远端（使用用户选择的分支名）
git push -u origin [用户选择的分支名]
```

6. **记录分支信息**：
```
📋 开发分支信息:
- 涉及子模块: wn-his-service, wn-his-rpc
- 源分支: master
- 新分支: [用户选择的分支名]
- 需求号: 1445554
- 远端状态: ✓ 已推送
```

---

### Step 5: 编码实现

**目标**: 按照实施计划逐步完成代码编写

**检测 superpowers 可用性**：

首先检查 `superpowers:executing-plans` skill 是否可用：
```
在 available_skills 列表中查找 "superpowers:executing-plans"
```

#### 情况 A: superpowers 可用（推荐）

调用 executing-plans skill 执行实施计划：

```
使用 Skill 工具调用 superpowers:executing-plans

任务描述应包含：
- 计划文件路径: docs/plans/yyyy-mm-dd-需求号.md
- 项目技术栈背景（Spring Boot + AKSO）
- AKSO 框架规范约束（多租户、异步、缓存等）
```

executing-plans 会帮助：
1. **有序执行** - 按计划步骤逐一完成
2. **检查点验证** - 每个任务完成后有验证
3. **进度跟踪** - 清晰的完成状态
4. **问题处理** - 遇到阻塞时的处理策略

**输入给 executing-plans 的约束**：
- 必须遵循 AKSO 框架规范（见本 skill 下方的规范章节）
- 必须遵循分层架构（Controller → Service → Repository）
- 必须处理多租户上下文

#### 情况 B: superpowers 不可用（回退方式）

使用内置的分层实现流程：

**原则**:
- **分层清晰**: Controller → Service → Repository → Entity
- **单一职责**: 每个类/方法只做一件事
- **多租户安全**: 所有入口显式绑定 hospitalSOID
- **注释适度**: 只在必要时添加注释

**实现顺序**（由内向外）：
1. **Entity 层** - 数据库实体修改/新增
2. **Repository 层** - 数据访问接口
3. **Service 层** - 业务逻辑实现
4. **Controller/RPC 层** - 接口暴露
5. **DTO/VO 层** - 请求响应对象

---

### Step 6: 验证闭环

**目标**: 确保生成的代码能正常运行

**操作**:
1. **必须**运行测试: `mvn test`
2. 如果测试失败，分析错误并修复
3. 重复直到测试通过

### Step 7: 保存修改记录

**目标**: 记录本次开发的完整信息，便于追溯和评审

**操作**:

1. **创建 feature 文档目录**：
```bash
mkdir -p docs/feature
```

2. **生成修改记录文件**：

**文件命名规则**: `yyyy-mm-dd-需求号.md`
**示例**: `2024-01-15-1445554.md`

**文件模板**：
```markdown
# 功能实现记录

## 基本信息

| 项目 | 内容 |
|------|------|
| **日期** | 2024-01-15 |
| **需求号** | 1445554 |
| **分支** | feature/1445554-user-query |
| **需求标题** | 用户查询功能 |

## 需求来源

- **TFS 工作项**: #1445554
- **需求文档**: product-docs/1445554/

## 实施计划

[从 Plan 模式复制]

## 修改文件清单

### 新增文件

| 文件路径 | 说明 |
|----------|------|
| `src/.../controller/UserQueryController.java` | 用户查询控制器 |
| `src/.../service/UserQueryService.java` | 用户查询服务接口 |
| `src/.../service/impl/UserQueryServiceImpl.java` | 用户查询服务实现 |

### 修改文件

| 文件路径 | 修改说明 |
|----------|----------|
| `src/.../entity/UserEntity.java` | 新增查询字段 |

## 技术要点

- **多租户**: 所有查询方法显式传递 hospitalSOID
- **缓存**: 使用 RedisAbility，Key 包含租户标识
- **异步**: 使用 CompletableFutureBuilder 并发聚合

## 测试验证

- [x] 单元测试通过

## 待处理事项

- [ ] 代码评审
- [ ] 合并到主分支
- [ ] 部署到测试环境
```

3. **输出确认**：
```
📝 修改记录已保存: docs/feature/2024-01-15-1445554.md
```

---

## Step 8: 导出开发对话并上传到 TFS

**目标**: 将本次开发的完整对话记录导出并上传到 TFS 工作项，打上 `AI-CODING` 标签

**前置条件**: 需求来源于 TFS 工作项（有工作项 ID）

**操作流程**:

1. **提示用户导出对话**：

**文件命名规则**: `AI-CODING-log-yyyy-mm-dd-需求号.txt`
**保存位置**: `docs/feature/AI-CODING-log-yyyy-mm-dd-需求号.txt`

向用户输出提示（使用 AskUserQuestion 工具，让用户可以直接选择）：

```
AskUserQuestion:
  question: "请执行以下命令导出对话记录，完成后选择继续："
  options:
    - label: "已导出，继续上传"
      description: "已执行 /export 命令，继续上传到 TFS"
    - label: "跳过上传"
      description: "不上传对话记录到 TFS"
```

同时输出命令供用户复制：
```
/export docs/feature/AI-CODING-log-2024-01-15-1445554.txt
```

2. **等待用户选择**

用户选择"已导出，继续上传"后，继续执行后续步骤。
用户选择"跳过上传"则结束 Step 8。

3. **上传对话文档到 TFS**：

```javascript
// 上传附件到 TFS 工作项
mcp__tfs-mcp__tfs_upload_attachment({
  id: 1445554,
  filePath: "docs/feature/AI-CODING-log-2024-01-15-1445554.txt",
  fileName: "AI-CODING-log-2024-01-15.txt",
  comment: "AI 开发对话记录 - 完整对话导出"
})
```

4. **添加 AI-CODING 标签**：

```javascript
// 为工作项添加 AI-CODING 标签
mcp__tfs-mcp__tfs_add_tags({
  id: 1445554,
  tags: "AI-CODING"
})
```

5. **删除临时文件**：

上传成功后，删除临时文件：
```bash
rm docs/feature/AI-CODING-log-2024-01-15-1445554.txt
```

6. **输出确认**：
```
📤 开发对话已上传到 TFS:
- 工作项: #1445554
- 附件: AI-CODING-log-2024-01-15.txt
- 标签: AI-CODING ✓
- 临时文件: 已删除 ✓
```

**注意事项**:
- 如果需求没有 TFS 工作项 ID，跳过此步骤
- /export 命令导出完整的原始对话记录
- 上传完成后务必删除临时文件，避免文件堆积

7. **完成提示**：

开发完成后，向用户输出以下提示：
```
✅ 开发任务已完成！

💡 后续建议:
- 如需提交代码，说"提交代码"、"提交并同步"、"提交并推送"、"提交本次修改"即可触发 git-merge 技能
- 如发现 Bug 需要修复，请新开对话进行处理
- 如有优化需求，请新开对话进行处理
- 避免在当前会话中进行调试，以保持对话记录的清晰性
```

---

## AKSO 框架核心规范

### 多租户上下文 (TenancyContext) - 强制规则

**规则 T1**: 凡是新线程、异步回调、缓存异步刷新、线程池执行，必须显式绑定租户：
```java
// 有返回值
TenancyContext.getWithSoid(() -> {...}, hospitalSOID)

// 无返回值
TenancyContext.doWithSoid(() -> {...}, hospitalSOID)
```

**规则 T2**: 业务方法链路应显式传递 `hospitalSOID`

**规则 TX-1**: 必须在进入事务之前完成 soid 绑定

**规则 TX-2**: 事务已开启时，禁止再切换 soid

### 异步执行 (CompletableFutureBuilder) - 强制规则

**规则 A1**: 异步/并发执行优先使用 `CompletableFutureBuilder`

**规则 A2**: 必须显式携带 `hospitalSOID` 和 `Domain`：
```java
CompletableFutureBuilder.getRpcSupplyAsync(
    () -> rpcCall(),
    Domain.ORDER,
    hospitalSOID
)
```

**禁止**: 直接使用 `CompletableFuture.runAsync()` 或 `Executors.newFixedThreadPool()`

### 对象转换 (BeanMapper) - 推荐规则

**规则 M1**: 默认使用 `BeanMapper` 完成对象转换：
```java
// 单对象
BeanMapper.map(source, TargetClass.class)

// 列表
BeanMapper.mapList(sourceList, TargetClass.class)
```

**禁止**: 新增模块私有拷贝工具类

### JPA 查询规范 - 强制规则

**规则 J1**: 优先使用 `@Query` (HQL/JPQL) 编写显式查询

**规则 J3**: 查询必须显式包含租户过滤条件

**规则 J4**: HQL/JPQL 必须使用全包名引用 Entity：
```java
@Query("SELECT t FROM com.example.module.entity.UserEntity t WHERE t.hospitalSOID = :soid")
```

**规则 J5**: 禁止循环数据库调用，优先使用批量查询 `in (:ids)`

### Redis 使用规范 (RedisAbility) - 强制规则

**规则 R1**: 租户相关数据的 Key 必须包含 `hospitalSOID`：
```
{appId}:{module}:{biz}:{hospitalSOID}:{id}
```

**规则 R2**: 写入必须设置 TTL（单位：毫秒）：
```java
// 正确：1小时 = 3600000 毫秒
redisAbility.set(key, value, 3600000L)
// 或
redisAbility.set(key, value, TimeUnit.HOURS.toMillis(1))
```

**规则 RL1**: 分布式锁必须使用 `RedisLocker`，禁止自研

### Elasticsearch 规范 (WinningElasticsearchTemplate)

**规则 ES1**: 统一使用 `WinningElasticsearchTemplate`

**规则 ES3**: 多租户隔离必须显式体现（索引命名或文档字段）

### 定时任务规范 (Xxl-Job)

**规则 JH1**: 任务入口必须以 hospitalSOID 列表驱动：
```java
@JobHandler(value = "syncDataJob")
public class SyncDataJob extends IJobHandler {
    @Override
    public void execute() {
        List<Long> soids = getAllHospitalSOIDs();
        for (Long soid : soids) {
            TenancyContext.doWithSoid(() -> sync(soid), soid);
        }
    }
}
```

---

## 分层架构规范

```
src/main/java/com/example/project/
├── controller/          # 控制器层 - 接收请求，参数校验
├── service/             # 服务层 - 业务逻辑
│   └── impl/
├── repository/          # 数据访问层
├── entity/              # 实体类 - 数据库映射
├── dto/                 # 数据传输对象 - RPC 请求/响应
│   ├── *InputDTO.java
│   └── *OutputDTO.java
├── vo/                  # 视图对象 - Web 请求/响应
│   ├── *InputVO.java
│   └── *OutputVO.java
├── config/              # 配置类
└── util/                # 工具类
```

### 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| RPC 入参 | `*InputDTO` | `GetUserInputDTO` |
| RPC 出参 | `*OutputDTO` | `GetUserOutputDTO` |
| Web 入参 | `*InputVO` | `QueryUserInputVO` |
| Web 出参 | `*OutputVO` | `UserDetailOutputVO` |
| 实体类 | `*Entity` | `UserEntity` |

---

## 接口开发模板

### WebMVC Controller 接口

```java
@RestController
@RequestMapping("/api/v1/web/demo/user")
@RequiredArgsConstructor
public class UserController {

    private final UserService userService;

    /**
     * 查询用户列表
     */
    @PostMapping("/query_list")
    public WinMvcResponse<QueryUserListOutputVO> queryList(
            @Valid @RequestBody QueryUserListInputVO inputVO) {
        // soid 来源：BizContext.getCurrentHospitalSOID()
        return WinMvcResponse.success(userService.queryList(inputVO));
    }
}
```

**检查清单**:
- [ ] 是否使用了 WinMvcResponse 包装返回值
- [ ] 是否引入了 winning-security-biz-webmvc 依赖
- [ ] 是否添加了必要的校验注解

### RPC Provider 接口

```java
@FeignClient(name = "user-service")
public interface UserRpcService {

    @WinPostMapping("/rpc/user/get")
    WinRpcResponse<GetUserOutputDTO> getUser(
            @RequestBody GetUserInputDTO inputDTO);
}

@Service
@RequiredArgsConstructor
public class UserRpcServiceImpl implements UserRpcService {

    private final UserService userService;

    @Override
    public WinRpcResponse<GetUserOutputDTO> getUser(GetUserInputDTO inputDTO) {
        // soid 必须来自 inputDTO.getHospitalSOID()
        return WinRpcResponse.success(userService.getById(inputDTO));
    }
}
```

**检查清单**:
- [ ] RPC 方法入口是否显式绑定租户上下文
- [ ] 是否使用了 @WinPostMapping 注解
- [ ] soid 是否来自 inputDTO.getHospitalSOID()

### RPC Consumer 调用

```java
@Service
@RequiredArgsConstructor
public class OrderServiceImpl implements OrderService {

    private final UserRpcService userRpcService;

    public OrderDetailVO getOrderDetail(Long orderId, Long hospitalSOID) {
        // 调用前必须显式把 hospitalSOID 写入 InputDTO
        GetUserInputDTO inputDTO = new GetUserInputDTO();
        inputDTO.setHospitalSOID(hospitalSOID);
        inputDTO.setUserId(userId);

        // 处理返回值
        WinRpcResponse<GetUserOutputDTO> response = userRpcService.getUser(inputDTO);
        if (!response.isSuccess()) {
            throw new BizException(response.getMsg());
        }
        // ...
    }
}
```

---

## 并发聚合模板

```java
@Service
@RequiredArgsConstructor
public class OrderDetailServiceImpl {

    public OrderDetailVO getOrderDetail(Long orderId, Long hospitalSOID) {
        // 并发聚合，必须带 soid
        CompletableFuture<UserVO> userFuture = CompletableFutureBuilder.getRpcSupplyAsync(
            () -> userRpcService.getUser(userId, hospitalSOID),
            Domain.ORDER,
            hospitalSOID
        );

        CompletableFuture<List<OrderItemVO>> itemsFuture = CompletableFutureBuilder.getRpcSupplyAsync(
            () -> orderItemService.getItems(orderId, hospitalSOID),
            Domain.ORDER,
            hospitalSOID
        );

        // 等待所有结果
        CompletableFuture.allOf(userFuture, itemsFuture).join();

        return buildDetail(userFuture.get(), itemsFuture.get());
    }
}
```

---

## 强制验证规则

### 必须执行的验证

1. **新增代码后** - 任何新增的类/方法
2. **修改核心逻辑后** - 业务逻辑、数据处理
3. **用户明确要求时**

### 验证命令

```bash
# 单元测试
mvn test
```

### 禁止跳过验证

**绝对禁止**:
- 用户没有明确说"跳过测试"时跳过验证
- 测试失败时直接提交代码
- 声称"测试应该能过"但不实际运行

---

## 常见问题处理

### 问题 1: 多租户上下文丢失

**症状**: 异步执行或新线程中数据串租户

**处理**:
```java
// ❌ 错误
executorService.submit(() -> doSomething());

// ✅ 正确
executorService.submit(
    TenancyContext.getWithSoid(() -> doSomething(), hospitalSOID)
);
```

### 问题 2: 事务内切换租户

**症状**: 同一事务内数据源不一致

**处理**:
```java
// ❌ 错误：事务内切换 soid
@Transactional
public void batchProcess(List<Long> soids) {
    for (Long soid : soids) {
        TenancyContext.doWithSoid(() -> process(soid), soid); // 危险！
    }
}

// ✅ 正确：每个租户独立事务
public void batchProcess(List<Long> soids) {
    for (Long soid : soids) {
        processWithNewTransaction(soid);
    }
}

@Transactional(propagation = Propagation.REQUIRES_NEW)
public void processWithNewTransaction(Long soid) {
    TenancyContext.doWithSoid(() -> process(soid), soid);
}
```

### 问题 3: Redis Key 未包含租户标识

**症状**: 不同租户缓存污染

**处理**:
```java
// ❌ 错误
String key = "user:info:" + userId;

// ✅ 正确
String key = "user:info:" + hospitalSOID + ":" + userId;
```

---

## 使用示例

### 示例 1: 从 TFS 工作项开始开发（推荐）

**用户输入**:
```
实现工作项 1445554
```

**执行过程**:

**【计划阶段】**
1. **Step 0**: 从 TFS 获取工作项 #1445554
   - 调用 tfs-mcp 获取工作项详情
   - 下载附件到 `product-docs/1445554/`
   - 提取需求信息
2. **Step 1**: 需求分析与方案设计
   - 优先调用 superpowers:brainstorming（如可用）
   - 或使用内置方式读取上下文并分析需求
3. **Step 2**: 生成实施计划
   - 优先调用 superpowers:writing-plans（如可用）
   - 或使用内置方式生成计划文件
   - 保存到 `docs/plans/2024-01-15-1445554.md`
4. **Step 3**: 用户确认计划

**【执行阶段】**
5. **Step 4**: 创建分支 `feature/1445554`
6. **Step 5**: 编码实现
   - 优先调用 superpowers:executing-plans（如可用）
   - 或使用内置分层实现流程
7. **Step 6**: 运行测试验证
8. **Step 7**: 保存修改记录到 `docs/feature/2024-01-15-1445554.md`
9. **Step 8**: 导出对话并上传 TFS
    - 生成 `docs/feature/AI-CODING-log-2024-01-15-1445554.md`
    - 上传附件到 TFS 工作项 #1445554
    - 添加 `AI-CODING` 标签

### 示例 2: 基于需求文档开发（有 TFS 工作项）

**用户输入**:
```
根据 product-docs/1445555/需求文档.md 实现用户管理接口
```

**执行过程**:

**【计划阶段】**
1. **Step 0**: 读取需求文档
2. **Step 1**: 需求分析与方案设计（superpowers:brainstorming 或内置）
3. **Step 2-3**: 生成计划 → 用户确认

**【执行阶段】**
4. **Step 4**: 创建分支 `feature/1445555`
5. **Step 5-6**: 编码（superpowers:executing-plans 或内置）、测试
6. **Step 7**: 保存修改记录
7. **Step 8**: 导出对话并上传 TFS（如有工作项 ID）

### 示例 3: 快速开发（无 TFS 工作项）

**用户输入**:
```
实现用户管理接口，包含增删改查功能
```

**执行过程**:

**【计划阶段】**
1. **Step 0**: 使用日期作为临时需求号 `20240115`
2. **Step 1**: 需求分析与方案设计（superpowers:brainstorming 或内置）
3. **Step 2-3**: 生成计划 → 用户确认

**【执行阶段】**
4. **Step 4-7**: 创建分支、编码（superpowers:executing-plans 或内置）、测试、保存记录
5. **Step 8**: 跳过（无 TFS 工作项 ID）

### 示例 4: 新增 RPC 接口

**用户输入**:
```
新增一个 RPC 接口 getUserById，根据用户ID查询用户信息
```

**检查清单**:
- [ ] InputDTO 是否继承 WinRpcRequest
- [ ] 是否包含 hospitalSOID 字段
- [ ] 返回值是否使用 WinRpcResponse 包装
- [ ] 实现类是否显式绑定 TenancyContext

**完成后 (Step 8)**:
- [ ] 如有 TFS 工作项，上传对话记录并打 AI-CODING 标签

---

## 参考文件

当需要详细信息时，请查阅以下参考文件：

| 文件 | 说明 |
|------|------|
| `references/akso-framework-guide.md` | AKSO 框架使用指南（多租户、异步、JPA、Redis、ES 等详细规范） |
| `references/code-generation-templates.md` | 代码生成模板库（Controller、RPC、缓存、定时任务等模板） |

**何时读取参考文件**：
- 需要了解 AKSO 组件具体用法时 → 读取 `akso-framework-guide.md`
- 需要代码生成模板时 → 读取 `code-generation-templates.md`

---

## 检查清单

### 计划阶段 (Step 0-3)
- [ ] 需求来源已确认（TFS/PRD/用户描述）
- [ ] TFS 工作项已获取（如适用）
- [ ] 附件已下载到 `product-docs/需求号/`
- [ ] 需求分析与方案设计完成（superpowers:brainstorming 或内置）
- [ ] 生成实施计划并保存到 `docs/plans/yyyy-mm-dd-需求号.md`（superpowers:writing-plans 或内置）
- [ ] 用户确认计划

### 执行阶段 (Step 4-8)

### 分支管理 (Step 4)
- [ ] 已识别需要修改的子模块
- [ ] 已让用户选择分支名格式（feature/需求号、bugfix/需求号、手动输入）
- [ ] 各子模块从正确分支创建功能分支
- [ ] 分支命名符合用户选择的格式

### 编码实现 (Step 5)
- [ ] 执行方式: superpowers:executing-plans（优先）或内置分层实现
- [ ] 多租户：是否显式传递 hospitalSOID
- [ ] 异步：是否使用 CompletableFutureBuilder + soid
- [ ] 对象转换：是否使用 BeanMapper
- [ ] JPA：是否使用全包名 Entity 引用
- [ ] Redis：Key 是否包含 hospitalSOID，是否设置 TTL
- [ ] DTO/VO：是否手动实现 toString/equals/hashCode，是否禁止使用 Lombok 注解

### 验证完成 (Step 6-7)
- [ ] 运行测试验证
- [ ] 修改记录已保存到 `docs/feature/yyyy-mm-dd-需求号.md`

### 导出对话到 TFS (Step 8)
- [ ] 使用 AskUserQuestion 提示用户执行 /export
- [ ] 用户选择"已导出，继续上传"
- [ ] 上传对话文档到 TFS 工作项（如有工作项ID）
- [ ] 添加 `AI-CODING` 标签到工作项
- [ ] 删除临时文件

---

## 🚀 后续操作：代码提交与同步

开发任务完成并验证通过后，如无 Bug 需要修复，可以使用 **git-merge** skill 进行代码提交和分支同步。

### 触发 git-merge 的常用提示词

| 场景 | 提示词示例 |
|------|----------|
| 提交并同步 | "提交并同步"、"提交一下"、"帮我提交一下" |
| 同步分支 | "同步主分支"、"同步一下分支"、"帮我同步分支" |
| 合并代码 | "merge 主分支"、"合并主分支"、"合并一下 master" |
| 拉取更新 | "拉取最新代码"、"拉代码"、"更新代码" |
| 更新分支 | "更新分支到最新"、"更新一下分支" |

### 工作流程

使用 git-merge skill 后，将自动执行：
1. **提交代码** - 自动生成规范的 commit message
2. **更新主分支** - 拉取远端最新代码
3. **合并到开发分支** - 将主分支合并到当前功能分支
4. **验证代码** - 运行测试确保合并后代码正常
5. **推送到远端** - 推送代码并准备创建 PR

```
✅ 开发完成 → 💬 告诉我"提交并同步" → 🚀 自动完成提交、合并、推送
```

---

## 📋 工作总结（必须执行）

**在完成所有开发任务后，必须输出以下工作总结：**

```markdown
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 本次工作总结
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## ✅ 已完成的工作

### 需求信息
- **需求号**: [需求号/工作项ID]
- **需求标题**: [需求标题]
- **需求来源**: [TFS/PRD文档/用户描述]

### 开发分支
- **分支名称**: feature/[需求号]
- **涉及子模块**: [子模块列表]

### 代码变更
| 类型 | 文件数 | 说明 |
|------|--------|------|
| 新增 | [数量] | [Controller/Service/Repository等] |
| 修改 | [数量] | [修改说明] |

### 功能实现
- [x] [接口1]: [接口路径]
- [x] [接口2]: [接口路径]
- [ ] [待完成项（如有）]

### 技术要点检查
- [x] 多租户: hospitalSOID 显式传递
- [x] 异步处理: 使用 CompletableFutureBuilder + soid
- [x] 对象转换: 使用 BeanMapper
- [x] JPA 查询: 使用全包名 Entity 引用
- [x] Redis 缓存: Key 包含 hospitalSOID，设置 TTL

### 验证结果
- [x] 单元测试通过

### 文档输出
- 实施计划: `docs/plans/yyyy-mm-dd-需求号.md`
- 修改记录: `docs/feature/yyyy-mm-dd-需求号.md`
- TFS 上传: [已上传/跳过]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 💡 后续建议

1. **代码提交**: 说"提交代码"、"提交并同步"、"提交并推送"、"提交本次修改"触发 git-merge 技能
2. **Bug 修复**: 如发现问题，请新开对话处理

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```
