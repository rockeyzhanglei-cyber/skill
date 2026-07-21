---
name: rdf-dev
description: |
  快开框架（RDF）开发 Skill，用于生成符合框架规范的 XML 配置文件和 TypeScript 控制类代码。

  **必须触发**：用户要进行快开框架页面开发、组件实现、功能开发。

  触发关键词（包含以下任一即触发）：
  - "快开框架" + 开发/实现：如"用快开框架开发页面"、"RDF开发"
  - "pageCode" + 数字/名称：如"pageCode userManage"、"页面编码"
  - "初始化页面" / "新建页面" / "创建页面"
  - "生成页面" + 设计图/图片：如"根据设计图生成页面"
  - ".page.meta.xml" / ".view.xml" / ".layout.xml" 文件相关
  - "RDF" / "rdf" / "pango-framework" + 开发需求
  - 快开框架 Bug：组件不显示、事件不响应、表格无数据等

  **不触发**：纯后端开发、Vue/React 非 RDF 框架、纯样式修改
metadata:
  author: 晁兴鹏
  version: 1.0.0
---

# 快开框架（RDF）开发 Skill

## 概述

此 Skill 为前端工程师提供标准化的快开框架（RDF）开发流程，确保：
1. **上下文感知** - 自动读取项目规范和框架约定
2. **计划先行** - 编码前生成详细的实施计划
3. **验证闭环** - 代码生成后必须运行项目验证
4. **风格统一** - 遵循 RDF 框架使用规范

## 执行模式说明

本 Skill 的执行分为两个阶段，**全程在主对话中完成**：

| 阶段 | 步骤 | 说明 |
|------|------|------|
| **计划阶段** | Step 0-3 | 获取需求、分析设计、生成计划文件、用户确认 |
| **执行阶段** | Step 4-8 | 创建分支、编码、验证、记录、上传 |

**关键设计**：
- **不使用 EnterPlanMode**：直接在主对话中生成计划文件
- **计划保存到文件**：`docs/plans/yyyy-mm-dd-需求号.md`
- **用户确认后直接继续**：无需退出 Plan 模式，主对话继承 skill 步骤定义
- **全程在同一上下文**：避免 Plan 模式丢失 skill 步骤的问题
- **优雅降级**：优先使用 superpowers skills，不可用时回退到内置方式

## 核心流程

```
┌─────────────────┐
│   需求获取       │ ← TFS工作项 / 设计图 / 用户描述
│  (Step 0)       │   下载附件到 product-docs/
└────────┬────────┘
         ▼
┌─────────────────┐
│ 需求分析与方案设计 │ ← superpowers:brainstorming（优先）
│  (Step 1)       │   或内置方式（扫描项目 + 手动分析）
│                 │   ★ 用户确认目标项目
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
│  创建开发分支     │ ← 确定项目 → feature/需求号
│  (Step 4)       │
└────────┬────────┘
         ▼
┌─────────────────┐
│    编码实现      │ ← superpowers:executing-plans（优先）
│  (Step 5)       │   或内置方式（场景A/B/C/D子流程）
└────────┬────────┘
         ▼
┌─────────────────┐
│   运行项目验证    │ ← npm run dev / pnpm dev
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

---

## 执行步骤

### Step 0: 需求获取

**目标**: 从TFS或其他来源获取需求，下载相关文档

**需求来源识别**:
1. **TFS 工作项 ID** - 用户输入如 "开发需求 1445554" 或 "1445554"
2. **设计图/截图路径** - 用户指定设计图位置
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
   - 附件 → 设计图/PRD文档

5. **识别开发场景**：
   - 提到"新建页面"/"初始化" → 场景A: 初始化空白页面
   - 包含设计图/截图 → 场景B: 图片生成页面
   - 提到"修改"/"新增"组件 → 场景C: 迭代需求
   - 提到"不显示"/"不响应"/"报错" → 场景D: Bug修复

**输出示例**:
```
📋 已获取需求:
- 工作项ID: 1445554
- 标题: 用户管理页面开发
- 附件: 2个文件已下载到 product-docs/1445554/
  ├── 设计图.png
  └── 需求说明.docx
- 识别场景: 场景B - 图片生成页面
```

#### 情况B: 设计图/截图

当用户提供设计图路径时：
```bash
# 读取设计图
使用 Read 工具读取图片文件

# 分析设计图内容
识别布局结构、组件类型、数据模型需求

# 复制到标准位置
cp [用户指定路径] product-docs/[需求号]/
```

#### 情况C: 用户直接描述

当用户直接描述需求时：
1. 提取功能点和 pageCode/viewCode
2. 使用日期作为临时需求号：`YYYYMMDD`
3. 记录需求描述到 `product-docs/[日期]/需求描述.md`

---

### Step 1: 需求分析与方案设计

**目标**: 深入理解需求，设计技术方案，**并在多模块项目中确认要修改的目标页面**

**重要**: 由于项目可能是多模块结构（父目录下有多个快开框架子项目），必须在此步骤确认要修改的项目和页面是否正确。

#### 前置步骤：读取项目上下文（必须执行）

无论是否使用 superpowers，都需要先扫描项目结构：

**1.1 扫描多模块项目结构**

```bash
# 扫描当前目录下所有包含快开框架特征的子项目
find . -maxdepth 4 -path "*/src/mainEntry/xml/pages" -type d 2>/dev/null | head -20
```

**识别快开框架项目特征**:
- 存在 `src/mainEntry/xml/pages/` 目录
- 存在 `src/mainEntry/ctrl/` 目录
- 存在 `.sparkrc.ts` 配置文件

**输出示例**:
```
📋 扫描到以下快开框架项目:
┌────┬─────────────────┬────────────────────────────────┐
│ #  │ 项目名称         │ 路径                           │
├────┼─────────────────┼────────────────────────────────┤
│ 1  │ wn-his-web      │ ./wn-his-web/                  │
│ 2  │ wn-emr-web      │ ./wn-emr-web/                  │
│ 3  │ wn-lis-web      │ ./wn-lis-web/                  │
└────┴─────────────────┴────────────────────────────────┘
```

#### 1.2 搜索指定 pageCode（如用户提供）

如果用户在 Step 0 中指定了 pageCode，搜索该 pageCode 在哪些项目中存在：

```bash
# 搜索指定 pageCode 的 .page.meta.xml 文件
find . -name "{pageCode}.page.meta.xml" 2>/dev/null

# 或搜索类似的页面名称（模糊匹配）
find . -name "*.page.meta.xml" | grep -i "{pageCode}" 2>/dev/null
```

**输出示例**:
```
📋 搜索 pageCode "userManage" 结果:
┌────┬─────────────────┬──────────────────────────────────────────────┐
│ #  │ 项目名称         │ 页面路径                                      │
├────┼─────────────────┼──────────────────────────────────────────────┤
│ 1  │ wn-his-web      │ wn-his-web/src/mainEntry/xml/pages/userManage/│
│ 2  │ wn-emr-web      │ wn-emr-web/src/mainEntry/xml/pages/userManage/│
└────┴─────────────────┴──────────────────────────────────────────────┘
```

#### 1.3 用户确认目标项目

**情况A: 只找到一个项目**
```
📋 已定位到唯一项目: wn-his-web
   页面路径: wn-his-web/src/mainEntry/xml/pages/userManage/

✅ 确认继续？(y/n)
```

**情况B: 找到多个项目（必须确认）**

使用 `AskUserQuestion` 让用户确认：

```
⚠️ 在多个项目中找到匹配的页面，请确认要修改的目标项目：

┌────┬─────────────────┬──────────────────────────────────────────────┐
│ #  │ 项目名称         │ 页面路径                                      │
├────┼─────────────────┼──────────────────────────────────────────────┤
│ 1  │ wn-his-web      │ wn-his-web/src/mainEntry/xml/pages/userManage/│
│ 2  │ wn-emr-web      │ wn-emr-web/src/mainEntry/xml/pages/userManage/│
└────┴─────────────────┴──────────────────────────────────────────────┘

AskUserQuestion:
  question: "请选择要修改的目标项目："
  options:
    - label: "wn-his-web"
      description: "HIS 系统的用户管理页面"
    - label: "wn-emr-web"
      description: "EMR 系统的用户管理页面"
    - label: "都不是，重新指定"
      description: "指定其他项目或页面编码"
```

**情况C: 未找到 pageCode（新建页面）**

如果 pageCode 不存在于任何项目中，说明是新建页面：

```
📋 pageCode "newFeature" 在所有项目中均未找到
   这将是一个新建页面操作。

AskUserQuestion:
  question: "请选择要创建页面的目标项目："
  options:
    - label: "wn-his-web"
      description: "在 HIS 系统中创建新页面"
    - label: "wn-emr-web"
      description: "在 EMR 系统中创建新页面"
```

**情况D: 用户未指定 pageCode**

如果用户没有指定 pageCode，列出各项目下的现有页面供参考：

```bash
# 列出各项目下的现有页面
for dir in $(find . -maxdepth 4 -path "*/src/mainEntry/xml/pages" -type d 2>/dev/null); do
  echo "项目: $(dirname $dir | xargs dirname | xargs basename)"
  ls -1 "$dir" | head -10
  echo "---"
done
```

#### 1.4 读取确认项目的上下文

确认目标项目后，读取该项目的详细上下文：

1. 读取项目根目录的 `CLAUDE.md`
2. 读取 RDF 框架规范文件（如有）
3. 读取现有页面的 XML 结构（用于参考）
4. 提取关键信息：
   - 框架版本（pango-framework-vue）
   - 项目结构（src/mainEntry/xml, src/mainEntry/ctrl）
   - 组件库版本（win-design-next）
   - 构建工具（Vite/Webpack）
   - 现有页面结构参考

#### 1.5 记录确认信息

**必须输出以下确认信息**:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ 目标确认
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- **目标项目**: wn-his-web
- **项目路径**: ./wn-his-web/
- **pageCode**: userManage
- **viewCode**: main
- **页面类型**: [新建/已存在]
- **操作场景**: [场景A/B/C/D]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**输出示例**:
```
📋 已读取 RDF 项目上下文:
- 框架: pango-framework-vue
- 组件库: win-design-next
- XML路径: wn-his-web/src/mainEntry/xml/pages/{pageCode}/
- 控制类路径: wn-his-web/src/mainEntry/ctrl/{PageCode}/
- 构建: Vite
- 命名规范: pageCode 小写开头，Ctrl 类大写开头
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
- 需求来源（TFS 工作项 / 设计图 / 用户描述）
- 需求核心内容（Step 0 获取的信息）
- 技术栈背景（RDF 框架 + pango-framework-vue）
- 输出要求（技术方案 + XML结构设计 + 实现路径）
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
   - 识别开发场景（初始化/图片生成/迭代/Bug修复）
   - 确定涉及的模块和层级

2. **设计技术方案**：
   - 确定需要新增/修改的 XML 文件
   - 设计数据模型（Dataset/DataList）
   - 规划组件清单和布局结构
   - 设计控制类方法

---

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
- 目标项目路径
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
   - XML 结构设计（组件+数据模型+布局）
   - 控制类方法设计
   - 实施步骤（按任务拆分）

**计划模板**:
```markdown
# 实施计划: [功能名称]

**需求号**: 1445554
**日期**: 2024-01-15
**目标**: [一句话描述]
**场景**: [场景A/B/C/D]

---

## 需要修改的文件

| 文件路径 | 修改说明 |
|----------|----------|
| `src/mainEntry/xml/pages/user/user.view.xml` | 新增组件定义 |

## 需要新增的文件

| 文件路径 | 说明 |
|----------|------|
| `src/mainEntry/xml/pages/user/user.page.meta.xml` | 页面配置 |
| `src/mainEntry/xml/pages/user/user.page.layout.xml` | 页面布局 |
| `src/mainEntry/xml/pages/user/user.main.view.xml` | 视图定义 |
| `src/mainEntry/xml/pages/user/user.main.layout.xml` | 视图布局 |
| `src/mainEntry/ctrl/User/UserMainCtrl.ts` | 控制类 |

## XML 结构设计

### 数据模型
- Dataset: userDataset (用户数据)
- DataList: statusList (状态选项)

### 组件清单
| 组件ID | 组件类型 | 绑定数据 | 事件 |
|--------|---------|---------|------|
| queryButton | Button | - | onClick |
| userGrid | Grid | userDataset | - |
| statusSelect | Select | statusList | onChange |

### 布局结构
```
FlowVLayout
├── FlowHPanel (查询区)
│   └── FlowHLayout
│       ├── FlowHPanel → statusSelect
│       └── FlowHPanel → queryButton
└── FlowVPanel (表格区)
    └── userGrid
```

## 实施步骤

### Task 1: 创建页面基础文件
- [ ] 创建 .page.meta.xml
- [ ] 创建 .page.layout.xml
- [ ] 创建 .main.view.xml
- [ ] 创建 .main.layout.xml

### Task 2: 实现组件和数据模型
- [ ] 定义 Dataset 和 DataList
- [ ] 实现查询区组件
- [ ] 实现表格组件

### Task 3: 实现控制类
- [ ] 创建 UserMainCtrl.ts
- [ ] 实现 queryButtonOnClick 方法
- [ ] 注册到 index.ts
```

4. **展示计划给用户确认**

---

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

---

### Step 4: 创建开发分支

**目标**: 从主分支创建功能开发分支

**操作**:

1. **检查当前 Git 状态**：
```bash
git status
git branch --show-current
```

2. **询问用户分支策略**：

使用 `AskUserQuestion` 让用户选择：

**问题 1 - 源分支选择**：
- 当前分支 / 主分支 / 其他分支

**问题 2 - 分支命名**（提供选项供用户选择）：

| 选项 | 格式 | 说明 |
|------|------|------|
| `feature/[需求号]` | 如 `feature/1445554` | 功能开发分支（默认推荐） |
| `bugfix/[需求号]` | 如 `bugfix/1445554` | 缺陷修复分支 |
| 手动输入 | 用户自定义 | 自定义分支名 |

示例 `AskUserQuestion` 调用：
```
AskUserQuestion({
  questions: [{
    question: "请选择分支命名方式：",
    header: "分支命名",
    options: [
      { label: "feature/[需求号]", description: "功能开发分支（推荐）" },
      { label: "bugfix/[需求号]", description: "缺陷修复分支" },
      { label: "手动输入", description: "自定义分支名称" }
    ],
    multiSelect: false
  }]
})
```

- 若用户选择"手动输入"，继续追问具体的分支名称
- 前端项目通常单仓库，一般需要创建新分支

3. **创建功能分支**（如需要）：
```bash
# 从源分支创建功能分支（根据用户选择的命名方式）
git checkout -b [用户选择的分支名]

# 推送到远端
git push -u origin [用户选择的分支名]
```

4. **记录分支信息**：
```
📋 开发分支信息:
- 源分支: master
- 新分支: feature/1445554
- 需求号: 1445554
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
- 目标项目路径
- RDF 框架规范约束（命名规范、文件权限等）
```

executing-plans 会帮助：
1. **有序执行** - 按计划步骤逐一完成
2. **检查点验证** - 每个任务完成后有验证
3. **进度跟踪** - 清晰的完成状态
4. **问题处理** - 遇到阻塞时的处理策略

**输入给 executing-plans 的约束**：
- 必须遵循 RDF 框架规范（见下方约束）
- 必须遵循命名规范
- 禁止修改框架配置文件

#### 情况 B: superpowers 不可用（回退方式）

根据 Step 0 识别的场景，选择对应的子流程：

**全局约束（必须遵守）**:

#### 文件修改权限

**最高优先级约束：AI 只能修改以下目录下的文件**

```
✅ 允许修改：
src/mainEntry/xml/**/*           # XML 配置文件
src/mainEntry/ctrl/**/*          # 控制类文件

❌ 严格禁止修改：
.sparkrc.ts                       # 框架配置文件
tsconfig.json                     # TypeScript 配置
package.json                      # 依赖配置文件
src/main.ts                      # 项目入口文件
src/CtrlContext.ts               # 控制器上下文（除非明确授权）
```

**违反此规则 = 立即停止操作并提示用户**

#### 命名规范（强制）

| 类型 | 规则 | 示例 |
|-----|------|------|
| 文件名 | 必须与输入 pageCode/viewCode 大小写一致 | `login.page.meta.xml` |
| 组件ID | 驼峰命名法，首字母小写 | `submitButton`、`userInput` |
| 控制类 | 驼峰命名法，首字母大写 | `LoginMainCtrl` |
| 类名 | 与文件名一致（不含扩展名） | `LoginMainCtrl.ts` → `LoginMainCtrl` |

#### 禁止行为清单

- 禁止在 `.view.xml` 中定义布局信息
- 禁止在 `.layout.xml` 中定义组件详细属性（除位置、尺寸外）
- 禁止组件不绑定必需的数据模型
- 禁止不注册控制类
- 禁止事件方法命名不符合规范
- 禁止使用其他 UI 组件库（自定义渲染时只能用 win-design-next）
- 禁止在渲染方法中使用 React hooks
- 禁止修改框架配置文件

---

**根据 Step 0 识别的场景，选择对应的子流程**:

#### 场景A: 初始化空白页面

**输入信息**:
- 项目根目录路径
- pageCode（页面编码）
- viewCode（视图编码，默认 `main`）

**文件生成位置**:
```
src/mainEntry/
├── xml/pages/{pageCode}/
│   ├── {pageCode}.page.meta.xml
│   ├── {pageCode}.page.layout.xml
│   ├── {pageCode}.{viewCode}.view.xml
│   └── {pageCode}.{viewCode}.layout.xml
└── ctrl/{PageCode}/
    ├── {PageCode}{ViewCode}Ctrl.ts
    └── index.ts (注册)
```

**生成步骤**:

1. **生成 `.page.meta.xml`**:
```xml
<Page xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
      id="{pageCode}"
      controller="designerctrl/{pageCode}/{PageCode}MainCtrl"
      isChanged="false">
    <ViewRefs>
        <ViewRef id="main" refId="main" canFreeDesign="true"/>
    </ViewRefs>
    <UIStates>
        <UIState id="editState" name="编辑态"/>
        <UIState id="viewState" name="浏览态"/>
    </UIStates>
</Page>
```

2. **生成 `.page.layout.xml`**:
```xml
<Page xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
      id="{pageCode}"
      layoutBgColor="#eef2fd"
      panelBgColor="#fff"
      compDefaultColor="#000">
    <ViewRef id="main" visible="true" showScrollBar="false"/>
</Page>
```

3. **生成 `.view.xml`**:
```xml
<View id="{viewCode}"
      isDialog="false"
      isCustom="true"
      controller="{pageCode}/{PageCode}{ViewCode}Ctrl"
      xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
    <DataModels>
    </DataModels>
    <Controls>
    </Controls>
</View>
```

4. **生成 `.layout.xml`**:
```xml
<View id="{viewCode}"
      xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
</View>
```

5. **生成控制类 `{PageCode}{ViewCode}Ctrl.ts`**:
```typescript
import {MouseEvent} from "pango-framework-vue";

export default class {PageCode}{ViewCode}Ctrl {

}
```

6. **注册控制类到 `index.ts`**:
```typescript
import {PageCode}{ViewCode}Ctrl from "./{PageCode}/{PageCode}{ViewCode}Ctrl";

export default {
    {PageCode}{ViewCode}Ctrl,
};
```

---

#### 场景B: 图片/设计稿生成页面

**工作流程**:

```
步骤1: 分析图片结构
  ↓
步骤2: 识别布局层级 → 选择合适的布局组件
  ↓
步骤3: 识别组件类型和属性
  ↓
步骤4: 识别数据模型需求（Dataset/DataList）
  ↓
步骤5: 生成 .view.xml（组件+数据模型）
  ↓
步骤6: 生成 .layout.xml（布局结构）
  ↓
步骤7: 生成控制类（事件方法）
  ↓
步骤8: 验证规则
```

**布局识别规则**:

| 图片特征 | 推荐布局 | 说明 |
|---------|---------|------|
| 上下排列 | FlowVLayout | 每个 Panel 放一个组件 |
| 左右排列 | FlowHLayout | 每个 Panel 放一个组件 |
| 自由定位 | AbsoluteLayout | 可直接放多个组件 |
| 自动换行 | FlowLayout | 可直接放多个组件 |
| 多页签 | TabLayout | 使用 TabPanel |
| 可折叠 | AccordionLayout | 使用 AccordionPanel |

**布局规则**：
- FlowVLayout/FlowHLayout 下必须有 Panel，每个 Panel 只能放一个组件或布局
- AbsoluteLayout/FlowLayout 下可以放多个组件，不能放布局
- 首次生成空白页面时，视图下可以不放布局，直接创建空的 `<View>` 根节点

**组件映射规则**:

| 图片元素 | RDF组件 | 必需绑定 |
|---------|---------|---------|
| 表格 | Grid | Dataset |
| 表单 | Form | Dataset |
| 动态表单 | DynamicForm | Dataset |
| 下拉框 | Select | DataList |
| 单选按钮组 | RadioGroup | DataList |
| 复选框组 | CheckboxGroup | DataList |
| 输入框 | Input | 无 |
| 按钮 | Button | 无 |

**合并规则**：如果在一个区域有多个输入框类型组件，可以尝试合并为 Form 组件。

**坐标映射规则**:
- 采用相对坐标系统：基于页面宽度和高度
- 坐标值范围：0-1
- 保留整数即可

---

#### 场景C: 迭代需求（修改现有页面）

**工作流程**:

```
步骤1: 分析需求变更内容
  ↓
步骤2: 定位需要修改的文件
  ↓
步骤3: 评估修改影响范围
  ↓
步骤4: 修改 XML/控制类
  ↓
步骤5: 验证兼容性
```

**修改原则**:

1. **最小化 diff**：优先选择最小改动方案
2. **保持兼容**：不破坏现有功能
3. **ID一致性**：`.view.xml` 和 `.layout.xml` 中对应的组件 ID 必须保持一致
4. **向后兼容**：新增组件/字段时，保留原有结构

**常见修改场景**:

| 场景 | 修改文件 | 注意事项 |
|-----|---------|---------|
| 新增组件 | .view.xml + .layout.xml | 添加数据模型（如需要） |
| 修改组件属性 | .view.xml | 保持 ID 不变 |
| 调整布局 | .layout.xml | 保持组件 ID 一致 |
| 新增事件 | .view.xml + 控制类 | 方法命名规范 |
| 修改数据模型 | .view.xml | 确保绑定的组件一致 |

---

#### 场景D: Bug 修复

**常见问题排查**:

| 现象 | 可能原因 | 排查步骤 |
|-----|---------|---------|
| 组件不显示 | 1. 布局缺少 Panel<br>2. 组件未绑定数据模型<br>3. visible=false | 检查 .layout.xml 布局结构、数据模型绑定 |
| 事件不响应 | 1. 控制类未注册<br>2. 方法命名错误<br>3. 事件参数类型错误 | 检查 index.ts、方法名、事件类型 |
| 表格无数据 | Dataset 未绑定或无 Fields | 检查 Dataset 配置和 Grid 绑定 |
| 表单无法输入 | Dataset isEdit=false | 检查 Dataset 的 isEdit 属性 |
| 下拉框无选项 | DataList 未绑定或无 DataItem | 检查 DataList 配置和 Select 绑定 |
| 自定义渲染报错 | 1. 使用了 React hooks<br>2. 组件未导入<br>3. 标签命名错误 | 检查渲染控制类代码 |

**修复原则**:

1. **定位根因**：先分析问题原因，再修复
2. **最小改动**：只修改必要的代码
3. **验证修复**：修复后确认问题已解决
4. **记录原因**：向用户解释问题原因和修复方案

---

### Step 6: 验证闭环

**目标**: 确保生成的代码能正常运行

**操作**:
1. **必须**运行项目: `npm run dev` 或 `pnpm dev`
2. 检查页面是否正常加载
3. 检查组件是否正常渲染
4. 检查事件是否正常响应
5. 如果有问题，分析错误并修复
6. 重复直到验证通过

**验证清单**:
```
□ 页面正常加载，无控制台报错
□ 所有组件正常渲染
□ 数据模型绑定正确
□ 事件方法正常响应
□ 布局结构符合预期
```

---

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
| **分支** | feature/1445554 |
| **需求标题** | 用户管理页面开发 |
| **开发场景** | 场景B - 图片生成页面 |

## 需求来源

- **TFS 工作项**: #1445554
- **需求文档**: product-docs/1445554/

## 实施计划

[从计划文件复制核心内容]

## 修改文件清单

### 新增文件

| 文件路径 | 说明 |
|----------|------|
| `src/mainEntry/xml/pages/user/user.page.meta.xml` | 页面配置 |
| `src/mainEntry/xml/pages/user/user.main.view.xml` | 视图定义 |
| `src/mainEntry/ctrl/User/UserMainCtrl.ts` | 控制类 |

### 修改文件

| 文件路径 | 修改说明 |
|----------|----------|
| `src/mainEntry/ctrl/index.ts` | 注册新控制类 |

## XML 结构

### 数据模型
- Dataset: userDataset
- DataList: statusList

### 组件清单
| 组件ID | 组件类型 | 绑定数据 |
|--------|---------|---------|
| queryButton | Button | - |
| userGrid | Grid | userDataset |

### 布局结构
FlowVLayout → 查询区 + 表格区

## 控制类方法

| 方法名 | 事件类型 | 说明 |
|--------|---------|------|
| queryButtonOnClick | MouseEvent<YButton> | 查询按钮点击 |

## 验证结果

- [x] 页面正常加载
- [x] 组件正常渲染
- [x] 事件正常响应

## 待处理事项

- [ ] 代码评审
- [ ] 合并到主分支
```

3. **输出确认**：
```
📝 修改记录已保存: docs/feature/2024-01-15-1445554.md
```

---

### Step 8: 导出开发对话并上传到 TFS

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

## 控制类生成规则

### 一般控制类

**文件路径**：`src/mainEntry/ctrl/{PageCode}/{PageCode}{ViewCode}Ctrl.ts`

**初始模板**：
```typescript
import {MouseEvent} from "pango-framework-vue";

export default class {PageCode}{ViewCode}Ctrl {

}
```

### 事件方法生成规则

1. **方法命名**：组件ID + 事件名称（首字母大写）
   - 示例：`queryButton` + `onClick` = `queryButtonOnClick`

2. **事件参数类型**（需要泛型）：

| 事件类型 | 泛型组件 | 示例 |
|---------|---------|------|
| MouseEvent | YButton, YGrid, YLabel... | `MouseEvent<YButton>` |
| TextEvent | YInput, YSelect, YCheckbox... | `TextEvent<YInput>` |
| KeyEvent | YInput, YTextArea... | `KeyEvent<YInput>` |
| FocusEvent | YInput, YSelect... | `FocusEvent<YInput>` |

3. **完整示例**：
```typescript
public submitButtonOnClick(e: MouseEvent<YButton>): void {
    // 处理点击事件
}
```

**详细事件映射**：参考 `references/event-map.md`

### 渲染控制类（可选）

**文件路径**：`src/mainEntry/ctrl/{PageCode}/{PageCode}Render.tsx`

**触发条件**：
1. 表格操作列自定义渲染（GridColumn 的 `renderType="CustomRender"`）
2. 布局 Panel 自定义渲染（Panel 的 `render` 属性）

**参数说明**：

| 场景 | 参数 |
|-----|------|
| 表格列渲染 | text, record, index, field, column, row |
| 布局 Panel 渲染 | yPanel, yView |

**win-design-next 使用规则**：
- 组件标签必须以 `<W` 开头（大写）
- 需要手动导入：`import { WButton } from 'win-design-next';`
- 禁止使用 React hooks

**详细规则**：参考 `references/render-core.md`

---

## 检查清单

### 计划阶段 (Step 0-3)
- [ ] 需求来源已确认（TFS/设计图/用户描述）
- [ ] TFS 工作项已获取（如适用）
- [ ] 附件已下载到 `product-docs/需求号/`
- [ ] **已扫描多模块项目结构**
- [ ] **已确认目标项目和 pageCode**
- [ ] **用户确认目标页面（多项目时必须）**
- [ ] 需求分析与方案设计完成（superpowers:brainstorming 或内置）
- [ ] 生成实施计划并保存到 `docs/plans/yyyy-mm-dd-需求号.md`（superpowers:writing-plans 或内置）
- [ ] 用户确认计划

### 执行阶段 (Step 4-8)

### 分支管理 (Step 4)
- [ ] 已检查 Git 状态
- [ ] 分支命名符合规范: `feature/需求号`

### 编码实现 (Step 5)
- [ ] 执行方式: superpowers:executing-plans（优先）或内置场景流程
- [ ] 文件路径正确：xml/pages/{pageCode}/ 和 ctrl/{PageCode}/
- [ ] pageCode/viewCode 大小写与输入保持一致
- [ ] Grid/Form/DynamicForm 已绑定 Dataset
- [ ] Select/RadioGroup/CheckboxGroup 已绑定 DataList
- [ ] 所有组件 ID 在 .view.xml 和 .layout.xml 中保持一致
- [ ] 布局下有 Panel（除了 AbsoluteLayout、FlowLayout）
- [ ] 控制类已注册到 index.ts
- [ ] 事件方法命名正确（组件ID + 事件名称）
- [ ] 事件参数类型正确

### 验证完成 (Step 6-8)
- [ ] 运行项目验证
- [ ] 修改记录已保存到 `docs/feature/yyyy-mm-dd-需求号.md`
- [ ] 导出对话并上传 TFS（如适用）

---

## 参考文档

当需要详细的组件、布局、API 信息时，参考以下文档：

| 文档 | 用途 | 路径 |
|-----|------|------|
| XML核心规范 | XML生成的核心规则和流程 | `references/xml-core.md` |
| 组件参考 | 各组件的属性说明和使用示例 | `references/components.md` |
| 布局参考 | 各布局的属性说明和使用示例 | `references/layout.md` |
| 数据模型 | 数据模型结构和属性 | `references/datamodel.md` |
| 事件映射表 | 组件支持的事件类型和事件名称 | `references/event-map.md` |
| 控制类规则 | 控制类生成规则和方法签名 | `references/ctrl-core.md` |
| 控制类API | 控制类常用API | `references/api-reference.md` |
| 自定义渲染 | 自定义渲染实现方式和示例 | `references/render-core.md` |
| 项目结构 | 前端项目目录结构说明 | `references/project-structure.md` |

**何时读取参考文件**：
- 需要了解组件具体用法时 → 读取 `components.md`
- 需要了解布局具体用法时 → 读取 `layout.md`
- 需要了解事件类型映射时 → 读取 `event-map.md`
- 需要代码生成模板时 → 读取 `xml-core.md` 或 `ctrl-core.md`

---

## 使用示例

### 示例 1: 从 TFS 工作项开始开发（推荐）

**用户输入**:
```
开发需求 1445554
```

**执行过程**:

**【计划阶段】**
1. **Step 0**: 从 TFS 获取工作项 #1445554
   - 调用 tfs-mcp 获取工作项详情
   - 下载附件到 `product-docs/1445554/`
   - 识别场景为"场景B - 图片生成页面"
   - 从需求中提取 pageCode: userManage
2. **Step 1**: 需求分析与方案设计
   - 扫描多模块项目：发现 wn-his-web、wn-emr-web、wn-lis-web
   - 搜索 pageCode "userManage"：在 wn-his-web 和 wn-emr-web 中均存在
   - **用户确认目标项目**: wn-his-web
   - 优先调用 superpowers:brainstorming（如可用）分析需求
   - 或使用内置方式读取上下文并分析
3. **Step 2**: 生成实施计划
   - 优先调用 superpowers:writing-plans（如可用）
   - 或使用内置方式生成计划
   - 保存到 `docs/plans/2024-01-15-1445554.md`
4. **Step 3**: 用户确认计划

**【执行阶段】**
5. **Step 4**: 在 wn-his-web 中创建分支 `feature/1445554`
6. **Step 5**: 编码实现
   - 优先调用 superpowers:executing-plans（如可用）
   - 或使用场景B流程：分析设计图 → 生成 XML → 生成控制类
7. **Step 6**: 运行项目验证
8. **Step 7**: 保存修改记录到 `docs/feature/2024-01-15-1445554.md`
9. **Step 8**: 导出对话并上传 TFS
   - 上传附件到 TFS 工作项 #1445554
   - 添加 `AI-CODING` 标签

### 示例 2: 根据设计图生成页面

**用户输入**:
```
根据 design.png 设计图生成用户管理页面，pageCode 是 userManage
```

**执行过程**:

**【计划阶段】**
1. **Step 0**: 读取设计图，识别场景为"场景B"
   - 提取 pageCode: userManage
2. **Step 1**: 需求分析与方案设计
   - 扫描多模块项目
   - 搜索 pageCode "userManage"
   - **用户确认目标项目和页面**
   - 优先调用 superpowers:brainstorming（如可用）
3. **Step 2-3**: 生成计划（superpowers:writing-plans 或内置）→ 用户确认

**【执行阶段】**
4. **Step 4**: 在确认的项目中创建分支 `feature/userManage`
5. **Step 5**: 编码实现（superpowers:executing-plans 或场景B流程）
6. **Step 6-8**: 验证、保存记录、上传 TFS（如有工作项）

### 示例 3: 快速开发（无 TFS 工作项）

**用户输入**:
```
初始化一个新页面，pageCode 是 dashboard，viewCode 是 main
```

**执行过程**:

**【计划阶段】**
1. **Step 0**: 使用日期作为临时需求号 `20240115`，识别场景为"场景A"
   - 提取 pageCode: dashboard（新建页面）
2. **Step 1**: 需求分析与方案设计
   - 扫描多模块项目
   - pageCode "dashboard" 不存在于任何项目
   - **用户确认在哪个项目中创建**: wn-his-web
   - 优先调用 superpowers:brainstorming（如可用）
3. **Step 2-3**: 生成计划（superpowers:writing-plans 或内置）→ 用户确认

**【执行阶段】**
4. **Step 4-7**: 创建分支、编码（superpowers:executing-plans 或场景A流程）、验证、保存记录
5. **Step 8**: 跳过（无 TFS 工作项 ID）

---

## 失败处理策略

### 规则冲突

当遇到规则冲突时，**立即停止操作**并向用户说明：

```
⚠️ 规则冲突检测

情况：组件必须绑定数据模型，但图片中无法识别数据模型需求

处理建议：
1. 使用默认数据模型结构
2. 或请求用户确认数据模型设计

操作：已停止，等待用户决策
```

### 不确定场景

遇到以下情况时，**请求用户介入**：

- 需要修改禁止区域的文件
- 规则描述不清晰或矛盾
- 业务逻辑理解不明确
- 潜在破坏性修改

---

## 🚀 后续操作：代码提交与同步

开发任务完成并验证通过后，如无 Bug 需要修复，可以使用 **git-merge** skill 进行代码提交和分支同步。

### 触发 git-merge 的常用提示词

| 场景 | 提示词示例 |
|------|----------|
| 提交并同步 | "提交并同步"、"提交一下"、"帮我提交一下" |
| 同步分支 | "同步主分支"、"同步一下分支"、"帮我同步分支" |
| 合并代码 | "merge 主分支"、"合并主分支"、"合并一下 master" |

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
- **需求来源**: [TFS/设计图/用户描述]
- **开发场景**: [场景A/B/C/D]

### 开发分支
- **分支名称**: feature/[需求号]

### 代码变更
| 类型 | 文件数 | 说明 |
|------|--------|------|
| 新增 | [数量] | [XML文件/控制类等] |
| 修改 | [数量] | [修改说明] |

### XML 结构
- **数据模型**: [Dataset/DataList 名称列表]
- **组件清单**: [主要组件列表]
- **布局结构**: [布局类型描述]

### 控制类方法
- [x] [方法1]: [事件类型] - [功能说明]
- [x] [方法2]: [事件类型] - [功能说明]

### 验证结果
- [x] 页面正常加载
- [x] 组件正常渲染
- [x] 事件正常响应
- [x] 无控制台报错

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

---

## AI 助手承诺

✅ 严格遵守所有规则文件的约束
✅ 永不修改禁止区域的文件
✅ 主动停止不确定或有风险的操作
✅ 清晰沟通操作意图和潜在影响
✅ 产出高质量可维护的生产级代码

❌ 绝不跳过规则检查
❌ 绝不假设不明确的需求
❌ 绝不隐藏潜在的风险
