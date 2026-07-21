---
name: frontend-dev
description: "Vue 3 + Spark 框架前端开发 Skill。触发场景：用户说'实现前端功能'、'开发页面'、'写组件'、Vue/前端/页面/组件相关需求、Vue2 迁移 Vue3、前端代码重构。强制在所有 Vue 3 前端开发任务中使用此 Skill。"
globs: []
metadata:
  author: 晁兴鹏
  version: 1.0.0
---

# Vue 3 + Spark 前端开发 Skill

此 Skill 为前端工程师提供标准化的 Vue 3 + Spark 框架开发流程，确保：
1. **上下文感知** - 自动读取项目规范和组件库约定
2. **权限约束** - 严格遵守 AI 修改权限边界
3. **计划先行** - 编码前生成详细的实施计划
4. **验证闭环** - 代码生成后必须运行测试验证
5. **风格统一** - 遵循 Spark 框架和 win-design 组件库规范

## 执行模式说明

本 Skill 的执行分为两个阶段，**全程在主对话中完成**：

| 阶段 | 步骤 | 说明 |
|------|------|------|
| **计划阶段** | Step 0-4 | 获取需求、分析设计、权限检查、生成计划文件、用户确认 |
| **执行阶段** | Step 5-9 | 创建分支、编码、测试、记录、上传 |

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
│  权限约束检查    │ ← 确认可修改范围
│  (Step 2)       │
└────────┬────────┘
         ▼
┌─────────────────┐
│   生成实施计划    │ ← superpowers:writing-plans（优先）
│  (Step 3)       │   或内置方式，保存到 docs/plans/
└────────┬────────┘
         ▼
┌─────────────────┐
│   用户审核计划    │ ← 人工确认后直接继续
│  (Step 4)       │
└────────┬────────┘
         ▼
┌─────────────────┐
│  创建开发分支     │ ← 确定子模块 → feature/需求号
│  (Step 5)       │
└────────┬────────┘
         ▼
┌─────────────────┐
│    编码实现      │ ← superpowers:executing-plans（优先）
│  (Step 6)       │   或内置方式，Vue组件 + TypeScript
└────────┬────────┘
         ▼
┌─────────────────┐
│   运行测试验证    │ ← type-check + lint
│  (Step 7)       │
└────────┬────────┘
         ▼
┌─────────────────┐
│  保存修改记录     │ ← /docs/feature/yyyy-mm-dd-需求号.md
│  (Step 8)       │
└────────┬────────┘
         ▼
┌─────────────────┐
│ 导出对话并上传TFS │ ← 上传附件 + 打标签 AI-FRCODING
│  (Step 9)       │
└─────────────────┘
```

**全程在主对话中执行，无需切换模式。**

---

## Step 0: 需求获取

**目标**: 从TFS或其他来源获取需求，下载相关文档

**需求来源识别**:
1. **TFS 工作项 ID** - 用户输入如 "实现工作项 1445554" 或 "1445554"
2. **PRD 文档路径** - 用户指定文档位置
3. **用户直接描述** - 用户直接说明需求内容

**处理流程**:

### 情况A: TFS 工作项（推荐）

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
- 附件 → 原型图/设计稿

5. **记录需求号**：用于后续分支命名和修改记录

**输出示例**:
```
📋 已获取需求:
- 工作项ID: 1445554
- 标题: 用户查询页面
- 附件: 2个文件已下载到 product-docs/1445554/
  ├── 原型设计.png
  └── 接口文档.xlsx
```

### 情况B: PRD 文档

当用户提供文档路径时：
```bash
# 读取文档
读取用户指定的 PRD 文档

# 复制到标准位置
cp [用户指定路径] product-docs/[需求号]/
```

### 情况C: 用户直接描述

当用户直接描述需求时：
1. 提取功能点
2. 使用日期作为临时需求号：`YYYYMMDD`
3. 记录需求描述到 `product-docs/[日期]/需求描述.md`

---

## Step 1: 需求分析与方案设计

**目标**: 深入理解需求，设计技术方案，明确实现路径

### 前置步骤：读取项目上下文（必须执行）

无论是否使用 superpowers，都需要先读取项目规范：

1. 读取项目根目录的 `CLAUDE.md`（如果存在）
2. 读取前端规范文件（如 `.cursor/rules`、`docs/frontend-guide.md` 等）
3. 提取关键信息：
   - 框架版本（Vue 3 + Spark）
   - UI 组件库（win-design-next）
   - 状态管理（Pinia）
   - 代码规范（ESLint + Prettier）
   - 测试框架（Vitest）

**输出示例**:
```
📋 已读取前端项目上下文:
- 框架: Vue 3 + Spark Framework
- UI 库: win-design-next (组件标签: <w-*>)
- 状态管理: Pinia (从 spark 导入)
- 测试: Vitest
- 代码规范: ESLint + Prettier
- API: request (从 spark 导入)
- 组件目录: src/views/[模块名]/components/
- 页面目录: src/views/[模块名]/index.vue
```

### 分析阶段：选择分析方式

**检测 superpowers 可用性**：
```
在 available_skills 列表中查找 "superpowers:brainstorming"
```

#### 情况 A: superpowers 可用（推荐）

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

#### 情况 B: superpowers 不可用（回退方式）

执行内置分析流程：

1. **分析需求**：
   - 提取功能点
   - 识别技术约束
   - 确定涉及的模块和层级

2. **设计技术方案**：
   - 确定需要新增/修改的文件
   - 设计组件结构（props、emits、slots）
   - 规划 API 接口

**输出示例**:
```
📋 需求分析完成:
- 功能名称: 用户查询页面
- 技术栈: Vue 3 + Spark Framework
- 涉及模块: src/views/UserQuery/

📋 方案设计:
- 新增页面: src/views/UserQuery/index.vue
- 新增组件: QueryForm.vue, ResultTable.vue
- 新增 API: apis/user.ts
```

---

## Step 2: 权限约束检查（最高优先级）

### 允许修改的路径

```
✅ src/views/**/*          - 所有视图模块
✅ src/components/**/*     - 全局组件（如果存在）
✅ src/composables/**/*    - 全局组合式函数
✅ src/stores/**/*         - 全局状态管理
✅ src/utils/**/*          - 工具函数
✅ mock/**/*               - Mock 数据
```

### 严格禁止修改的文件

```
❌ .sparkrc.ts             - Spark 框架配置
❌ src/app.ts              - 应用入口
❌ src/global.ts           - 全局配置
❌ src/global.scss         - 全局样式
❌ tsconfig.json           - TypeScript 配置
❌ package.json            - 依赖配置
❌ typings.d.ts            - 类型声明
```

### 权限违规处理

当检测到需要修改禁止区域时：

```
⚠️ 权限限制：检测到需要修改 `[文件路径]`
根据规则，AI 无权修改此文件。

替代方案：
1. [具体替代方案]
2. [另一个替代方案]

是否采用替代方案继续？
```

---

## Step 3: 生成实施计划

**目标**: 在编码前规划好要修改/新增的文件和步骤

**检测 superpowers 可用性**：

首先检查 `superpowers:writing-plans` skill 是否可用：
```
在 available_skills 列表中查找 "superpowers:writing-plans"
```

### 情况 A: superpowers 可用（推荐）

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

### 情况 B: superpowers 不可用（回退方式）

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
   - 组件设计（props、emits、slots）
   - API 接口设计
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
| `src/views/[模块]/index.vue` | 新增查询入口 |

## 需要新增的文件

| 文件路径 | 说明 |
|----------|------|
| `src/views/[模块]/components/[组件名].vue` | 组件说明 |
| `src/views/[模块]/apis/[接口名].ts` | 接口说明 |
| `src/views/[模块]/types/[类型名].ts` | 类型说明 |

## 组件设计

### [组件名].vue
- **Props**: [props 列表]
- **Emits**: [emits 列表]
- **State**: [响应式状态]
- **Methods**: [方法列表]

## 实施步骤

### Task 1: 创建类型定义
- [ ] 创建 types/user.ts

### Task 2: 添加 API 方法
- [ ] 创建 apis/user.ts

### Task 3: 创建组件
- [ ] 创建 components/QueryForm.vue
- [ ] 创建 components/ResultTable.vue

### Task 4: 集成到页面
- [ ] 修改 index.vue

### Task 5: 运行验证
- [ ] npm run type-check
- [ ] npm run lint
```

4. **展示计划给用户确认**

---

## Step 4: 用户审核

**目标**: 确保计划符合预期

**操作**:
1. 展示计划给用户
2. 等待用户确认或修改
3. 用户确认后直接继续执行 Step 5

**提示语**:
```
📋 实施计划已生成: docs/plans/2024-01-15-1445554.md

请审核计划内容，确认后回复"确认"或"开始实施"继续。
```

---

## Step 5: 创建开发分支

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

2. **确认分支命名**：

**默认分支命名规则**:
| 格式 | 示例 | 说明 |
|------|------|------|
| `feature/[需求号]` | `feature/1445554` | 新功能开发 |
| `bugfix/[需求号]` | `bugfix/1445555` | Bug 修复 |

使用 `AskUserQuestion` 让用户确认分支名：

```
📋 请选择分支类型：

- feature/[需求号] - 新功能开发（默认）
- bugfix/[需求号] - Bug 修复
- 手动输入 - 自定义分支名
```

选项：
- **feature/[需求号]** - 新功能开发（默认）
- **bugfix/[需求号]** - Bug 修复
- **手动输入** - 用户自定义分支名

3. **在各子模块中创建功能分支**：

对每个确认的子模块执行：
```bash
cd [子模块路径]

# 获取当前分支信息
git branch --show-current
git status

# 从源分支创建功能分支
git checkout -b [分支名]
```

4. **从源分支拉取最新代码**：

对每个子模块执行：
```bash
# 切换到源分支
git checkout [源分支名]

# 拉取远端最新代码
git pull origin [源分支名]

# 切换回功能分支
git checkout [分支名]

# 合并源分支最新代码到功能分支
git merge [源分支名]
```

**处理冲突**（自动解决）：
- 优先保留功能分支的变更（`git merge -X theirs [源分支名]`）
- 如自动解决失败，提示用户确认后继续

5. **推送到远端**：

对每个子模块执行：
```bash
# 首次推送新分支到远端
git push -u origin [分支名]
```

6. **记录分支信息**：
```
📋 开发分支信息:
- 涉及子模块: wn-his-web, wn-his-component
- 源分支: master
- 新分支: feature/1445554
- 需求号: 1445554
- 远端状态: ✓ 已推送
```

---

## Step 6: 编码实现

**目标**: 按照实施计划逐步完成代码编写

**检测 superpowers 可用性**：

首先检查 `superpowers:executing-plans` skill 是否可用：
```
在 available_skills 列表中查找 "superpowers:executing-plans"
```

### 情况 A: superpowers 可用（推荐）

调用 executing-plans skill 执行实施计划：

```
使用 Skill 工具调用 superpowers:executing-plans

任务描述应包含：
- 计划文件路径: docs/plans/yyyy-mm-dd-需求号.md
- 项目技术栈背景（Vue 3 + Spark）
- Spark 框架规范约束（从 spark 导入、win-design 组件等）
```

executing-plans 会帮助：
1. **有序执行** - 按计划步骤逐一完成
2. **检查点验证** - 每个任务完成后有验证
3. **进度跟踪** - 清晰的完成状态
4. **问题处理** - 遇到阻塞时的处理策略

**输入给 executing-plans 的约束**：
- 必须遵循 Spark 框架规范（从 spark 导入）
- 必须使用 win-design 组件（`<w-*>`）
- 必须使用 TypeScript 和 i18n

### 情况 B: superpowers 不可用（回退方式）

使用内置的分层实现流程：

**实现顺序**（由内向外）：
1. **types/** - 类型定义
2. **apis/** - API 接口
3. **composables/** - 组合式函数
4. **components/** - 组件实现
5. **stores/** - 状态管理
6. **index.vue** - 页面集成

### Vue 组件强制模板

```vue
<template>
  <div class="component-name">
    <!-- 使用 win-design 组件 -->
    <w-button type="primary">{{ $t('common.save') }}</w-button>
  </div>
</template>

<script setup lang="ts">
// 1. 从 spark 导入（禁止从 vue/vue-router 等原始库导入）
import { ref, computed, onMounted } from 'spark';

// 2. Props 定义（使用 TypeScript 接口）
interface Props {
  title: string;
  count?: number;
}
const props = withDefaults(defineProps<Props>(), {
  count: 0
});

// 3. Emits 定义
const emits = defineEmits<{
  change: [value: number];
}>();

// 4. 响应式状态
const loading = ref(false);
const dataList = ref<DataType[]>([]);

// 5. 计算属性
const filteredList = computed(() => {
  return dataList.value.filter(item => item.active);
});

// 6. 方法
const handleSubmit = () => {
  emits('change', props.count + 1);
};

// 7. 生命周期
onMounted(() => {
  fetchData();
});
</script>

<style scoped>
.component-name {
  padding: 16px;
}
</style>
```

### 强制规则

| 规则 | 说明 |
|------|------|
| ✅ 必须使用 `<script setup lang="ts">` | 禁止 Options API |
| ✅ 必须从 `spark` 导入 | 禁止从 `vue`/`vue-router` 导入 |
| ✅ 必须使用 TypeScript | 禁止 `any` 类型 |
| ✅ 必须使用 win-design | 组件标签: `<w-*>` |
| ✅ 必须使用 i18n | 禁止硬编码文案 |
| ✅ 模块内引用用相对路径 | 禁止 `@/views/` 跨模块 |

### 从 spark 导入的 API

```typescript
// 响应式
import { ref, reactive, computed, watch, watchEffect } from 'spark';

// 路由（无路由模式下谨慎使用）
import { useRouter, useRoute } from 'spark';

// 状态管理
import { defineStore, storeToRefs } from 'spark';

// HTTP 请求
import { request } from 'spark';

// 工具函数
import { utils } from 'spark';
// utils.object.cloneDeep()
// utils.array.chunk()
// utils.date.dayjs()
// utils.cookie.get/set()
// utils.base64.encode/decode()

// 国际化
import { t, useI18n } from 'spark';

// 微前端/事件
import { micro, useEventBus } from 'spark';
```

### win-design 组件使用

```vue
<template>
  <!-- ✅ 正确：使用 win-design 组件 -->
  <w-button type="primary">提交</w-button>
  <w-input v-model="value" placeholder="请输入" />
  <w-table :data="tableData" />
  <w-form :model="formData" />

  <!-- ❌ 错误：使用其他 UI 库 -->
  <el-button>提交</el-button>
  <a-input v-model:value="value" />

  <!-- ❌ 错误：大写标签 -->
  <W-Button>提交</W-Button>
</template>

<script setup lang="ts">
// ✅ 无需导入，开箱即用
// ❌ 禁止手动导入 win-design 组件
</script>
```

### 多语言处理

```vue
<template>
  <!-- ✅ 模板中使用 $t -->
  <div>{{ $t('common.save') }}</div>
  <w-button>{{ $t('user.create') }}</w-button>

  <!-- ❌ 硬编码 -->
  <div>保存</div>
</template>

<script setup lang="ts">
import { t } from 'spark';

// ✅ Script 中使用 t
const message = t('common.success');
const title = t('user.listTitle');

// ❌ 硬编码
const message = '操作成功';
</script>
```

---

## Step 7: 验证闭环

**目标**: 确保生成的代码能正常运行

**操作**:
1. 运行类型检查: `npm run type-check`
2. 运行 lint: `npm run lint`
3. 运行测试（如果有）: `npm run test`
4. 如果失败，分析错误并修复

**验证命令**:
```bash
# 类型检查
npm run type-check

# Lint 检查
npm run lint

# 测试
npm run test
```

**失败处理示例**:
```
❌ 类型检查失败: UserManage.vue

错误信息: Property 'fetchUsers' does not exist on type...

分析原因: 方法未正确声明

修复方案: 在 <script setup> 中定义 fetchUsers 函数

正在重新运行类型检查...
✅ 类型检查通过
```

---

## Step 8: 保存修改记录

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
| **需求标题** | 用户查询页面 |

## 需求来源

- **TFS 工作项**: #1445554
- **需求文档**: product-docs/1445554/

## 实施计划

[从 Plan 模式复制]

## 修改文件清单

### 新增文件

| 文件路径 | 说明 |
|----------|------|
| `src/views/UserQuery/index.vue` | 用户查询页面入口 |
| `src/views/UserQuery/components/QueryForm.vue` | 查询表单组件 |
| `src/views/UserQuery/components/ResultTable.vue` | 结果表格组件 |
| `src/views/UserQuery/apis/user.ts` | 用户查询接口 |
| `src/views/UserQuery/types/user.ts` | 类型定义 |

### 修改文件

| 文件路径 | 修改说明 |
|----------|----------|
| `src/locales/zh-CN/user.ts` | 新增用户查询相关文案 |

## 技术要点

- 组件库: win-design-next (`<w-*>`)
- 状态管理: Pinia (从 spark 导入)
- API 请求: request (从 spark 导入)
- 国际化: $t() / t()

## 测试验证

- [x] 类型检查通过
- [x] Lint 检查通过

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

## Step 9: 导出开发对话并上传到 TFS

**目标**: 将本次开发对话导出为文档，上传到 TFS 工作项并打上 `AI-FRCODING` 标签

**前置条件**: 需求来源于 TFS 工作项（有工作项 ID）

**操作流程**:

1. **生成开发对话文档**：

**文件命名规则**: `AI-FRCODING-log-yyyy-mm-dd-需求号.md`
**保存位置**: `docs/feature/AI-FRCODING-log-yyyy-mm-dd-需求号.md`

**文档模板**：
```markdown
# AI 开发对话记录

## 基本信息

| 项目 | 内容 |
|------|------|
| **日期** | 2024-01-15 |
| **需求号** | 1445554 |
| **分支** | feature/1445554-user-query |
| **需求标题** | 用户查询页面 |
| **AI 标签** | AI-FRCODING |

## 开发概述

[本次开发的主要目标和实现内容摘要]

## 实施计划

[从 Plan 模式复制完整的实施计划]

## 修改文件清单

### 新增文件

[列出所有新增的文件及说明]

### 修改文件

[列出所有修改的文件及修改说明]

## 关键代码片段

[记录关键的代码实现片段，便于评审]

## 技术要点

- [技术要点1]
- [技术要点2]

## 测试验证

- [ ] 类型检查通过
- [ ] Lint 检查通过
- [ ] 功能测试通过

## 开发对话完整记录

[完整的用户与 AI 的对话记录]
```

2. **上传对话文档到 TFS**：

```javascript
// 上传附件到 TFS 工作项
mcp__tfs-mcp__tfs_upload_attachment({
  id: 1445554,
  filePath: "docs/feature/AI-FRCODING-log-2024-01-15-1445554.md",
  fileName: "AI-FRCODING-log-2024-01-15.md",
  comment: "AI 开发对话记录 - 自动上传"
})
```

3. **添加 AI-CODING 标签**：

```javascript
// 为工作项添加 AI-FRCODING 标签
mcp__tfs-mcp__tfs_add_tags({
  id: 1445554,
  tags: "AI-FRCODING"
})
```

4. **输出确认**：
```
📤 开发对话已上传到 TFS:
- 工作项: #1445554
- 附件: AI-FRCODING-log-2024-01-15.md
- 标签: AI-FRCODING ✓
```

**注意事项**:
- 如果需求没有 TFS 工作项 ID，跳过此步骤
- 上传前检查文件是否已存在同名附件，会自动覆盖
- 标签添加采用增量方式，不会覆盖现有标签

5. **完成提示**：

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

## Vue2 到 Vue3 迁移规则

当用户要求迁移 Vue2 组件时，遵循以下规则：

### 核心原则

1. **行为等价原则**: 重构前后代码的运行时行为必须完全一致
2. **最小改动原则**: 只修改与迁移目标直接相关的代码
3. **全量迁移原则**: 允许修改组件内所有部分以达到纯 Vue3 Composition API

### 迁移映射

| Vue2 Options API | Vue3 Composition API |
|------------------|---------------------|
| `data()` | `ref()` / `reactive()` |
| `props` | `defineProps<T>()` |
| `emits` | `defineEmits<{}>()` |
| `computed` | `computed()` |
| `watch` | `watch()` / `watchEffect()` |
| `methods` | 普通顶层函数 |
| `mounted` | `onMounted()` |
| `beforeUnmount` | `onBeforeUnmount()` |
| `unmounted` | `onUnmounted()` |

### 迁移后必须输出审计报告

```markdown
## 🔍 Refactor Audit Block

### 基本信息
- 迁移文件路径: src/views/User/List.vue
- 迁移阶段: Vue2 to Vue3 Composition API Migration

### 行为等价性验证
- 行为是否等价: ✅ Yes
- 等价性说明: [具体说明]

### 副作用管理
- 副作用变更: [说明]
- 副作用详细列表: [列表]

### 代码质量检查
- Lint 检查: ✅ 通过
- TypeScript 类型: ✅ 完整

### 回滚能力
- 是否可回滚: ✅ Yes
- 回滚方式: `git revert <commit-hash>`
```

---

## AI 重构行为约束

### 四大核心原则（强制）

1. **禁止自由发挥**: AI 只能在明确授权范围内修改代码
2. **行为等价**: 重构前后运行时行为必须完全一致
3. **最小 Diff**: 只修改与目标直接相关的代码
4. **可回滚**: 所有修改必须支持 `git revert`

### 禁止的操作

```
❌ "顺手"优化代码结构
❌ 自动调整代码格式
❌ 修改变量/函数命名（除非是目标）
❌ 添加"可能有用"的功能
❌ 删除"看起来没用"的代码
❌ 修改代码风格
❌ 新增/删除依赖
❌ 修改框架配置文件
```

### 强制中止条件

检测到以下情况必须立即停止：
- 行为等价性无法保证
- 涉及模板或样式修改（除非是迁移要求）
- Props/Emits 类型变化
- 跨模块结构变更
- 超出授权范围

---

## 目录结构规范

```
src/views/
├── [ViewName]/              # 业务模块目录（PascalCase）
│   ├── apis/               # 接口定义
│   │   └── user.ts
│   ├── components/         # 模块组件
│   │   └── UserForm.vue
│   ├── composables/        # 组合式函数
│   │   └── useUserList.ts
│   ├── stores/             # 状态管理
│   │   └── user.ts
│   ├── types/              # 类型定义
│   │   └── user.ts
│   └── index.vue           # 模块入口（必需）
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
   - 读取项目上下文
   - 优先调用 superpowers:brainstorming（如可用）
   - 或使用内置方式分析需求
3. **Step 2**: 权限约束检查
4. **Step 3**: 生成实施计划
   - 优先调用 superpowers:writing-plans（如可用）
   - 或使用内置方式生成计划
   - 保存到 `docs/plans/2024-01-15-1445554.md`
5. **Step 4**: 用户确认计划

**【执行阶段】**
6. **Step 5**: 创建分支 `feature/1445554`
7. **Step 6**: 编码实现
   - 优先调用 superpowers:executing-plans（如可用）
   - 或使用内置分层实现流程
8. **Step 7**: 运行测试验证
9. **Step 8**: 保存修改记录到 `docs/feature/2024-01-15-1445554.md`
10. **Step 9**: 导出对话并上传 TFS

### 示例 2: 基于需求文档开发

**用户输入**:
```
根据 product-docs/1445555/需求文档.md 实现用户管理页面
```

**执行过程**:

**【计划阶段】**
1. **Step 0**: 读取需求文档
2. **Step 1-2**: 需求分析（superpowers:brainstorming 或内置）、权限检查
3. **Step 3-4**: 生成计划（superpowers:writing-plans 或内置）→ 用户确认

**【执行阶段】**
4. **Step 5**: 创建分支 `feature/1445555`
5. **Step 6-9**: 编码（superpowers:executing-plans 或内置）、测试、记录、上传

### 示例 3: 快速开发（无需求号）

**用户输入**:
```
实现一个用户查询页面
```

**执行过程**:

**【计划阶段】**
1. **Step 0**: 使用日期作为临时需求号 `20240115`
2. **Step 1-2**: 需求分析（superpowers:brainstorming 或内置）、权限检查
3. **Step 3-4**: 生成计划（superpowers:writing-plans 或内置）→ 用户确认

**【执行阶段】**
4. **Step 5-8**: 创建分支、编码（superpowers:executing-plans 或内置）、测试、保存记录
5. **Step 9**: 跳过（无 TFS 工作项 ID）

---

## 常见问题处理

### Q1: 组件库类型缺失

```bash
# 检查是否安装了类型包
npm install -D @types/xxx
```

### Q2: API 接口未定义

使用 Mock 数据开发：
```typescript
// TODO: 后端接口就绪后替换为真实 API
const mockUsers: User[] = [
  { id: 1, name: '张三' }
];

export const getUserList = async () => {
  // return userApi.getList()
  return { data: mockUsers };
};
```

### Q3: 样式深度选择器

```vue
<style scoped>
/* Vue 3 使用 :deep() */
:deep(.w-table .cell) {
  padding: 0;
}

/* 或使用 :global() */
:global(.custom-class) {
  color: red;
}
</style>
```

### Q4: 命名冲突避免

```typescript
// ❌ 错误：解构赋值时产生冲突
const hintStatus = ref('');
const { hintStatus } = res.data;  // 冲突！

// ✅ 正确：重命名避免冲突
const hintStatus = ref('');
const { hintStatus: hintStatusData } = res.data;
hintStatus.value = hintStatusData;
```

---

## 参考文件

当需要详细信息时，请查阅以下参考文件：

| 文件 | 说明 |
|------|------|
| `references/spark-api.md` | Spark 框架 API 详细文档（响应式、状态管理、HTTP、工具函数等） |
| `references/win-design.md` | win-design 组件库使用规范（表单、表格、弹窗等组件） |
| `references/vue3-migration.md` | Vue2 到 Vue3 迁移详细规则（迁移映射、场景示例、审计模板） |

**何时读取参考文件**：
- 需要了解 Spark 框架具体 API 用法时 → 读取 `spark-api.md`
- 需要使用 win-design 组件时 → 读取 `win-design.md`
- 执行 Vue2→Vue3 迁移任务时 → 读取 `vue3-migration.md`

---

## 检查清单

### 计划阶段 (Step 0-4)
- [ ] 需求来源已确认（TFS/PRD/用户描述）
- [ ] TFS 工作项已获取（如适用）
- [ ] 附件已下载到 `product-docs/需求号/`
- [ ] 读取项目上下文
- [ ] 需求分析与方案设计完成（superpowers:brainstorming 或内置）
- [ ] 确认修改权限范围
- [ ] 生成实施计划并保存到 `docs/plans/yyyy-mm-dd-需求号.md`（superpowers:writing-plans 或内置）
- [ ] 用户确认计划

### 执行阶段 (Step 5-10)

### 分支管理 (Step 5)
- [ ] 已识别需要修改的子模块
- [ ] 各子模块从正确分支创建功能分支
- [ ] 分支命名符合规范: `feature/需求号`

### 编码实现 (Step 6)
- [ ] 执行方式: superpowers:executing-plans（优先）或内置分层实现
- [ ] 使用 `<script setup lang="ts">`
- [ ] 从 `spark` 导入 API
- [ ] 使用 win-design 组件
- [ ] TypeScript 类型完整
- [ ] 使用 i18n 多语言

### 验证完成 (Step 7-8)
- [ ] 运行类型检查
- [ ] 运行 lint 检查
- [ ] 运行测试验证
- [ ] 修改记录已保存到 `docs/feature/yyyy-mm-dd-需求号.md`
- [ ] 输出审计报告（重构时）

### 导出对话到 TFS (Step 9)
- [ ] 生成开发对话文档 `AI-FRCODING-log-*.md`
- [ ] 上传对话文档到 TFS 工作项（如有工作项ID）
- [ ] 添加 `AI-FRCODING` 标签到工作项

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
| 新增 | [数量] | [简要说明] |
| 修改 | [数量] | [简要说明] |

### 功能实现
- [x] [功能点1]
- [x] [功能点2]
- [ ] [待完成项（如有）]

### 验证结果
- [x] 类型检查通过
- [x] Lint 检查通过

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
