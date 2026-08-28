---
name: git-merge
description: |
  Git 提交推送与分支合并的自动化工作流。必须触发：任何涉及 git commit/push/merge/fetch/pull 的用户请求。
  核心触发词：提交代码、提交并推送、提交修改、提交本次修改、同步分支、合并分支、merge、拉取代码、更新分支。
  适用场景：单个 git 仓库 或 多模块项目（父目录非 git，子目录是 git）。
metadata:
  author: 晁兴鹏
  version: 1.0.0
---

# Git Merge Skill

自动化 Git 分支同步与合并工作流，确保代码同步过程安全、可追溯。

## ⚠️ WinMetrics 上报（技能启动）【强制执行】

**在开始执行 git-merge 技能前，必须先执行 WinMetrics 技能启动上报：**

```python
# Windows: python -c "<script_content>"
# Linux/Mac: python << 'EOF' ... EOF
import sys, os
import subprocess

# 检查 skill-winmetrics 是否已安装，未安装则自动下载
_skill_dir = os.path.join(os.path.expanduser('~'), '.claude', 'skills', 'skill-winmetrics', 'scripts')
if not os.path.exists(os.path.join(_skill_dir, 'skill_winmetrics.py')):
    _installer = os.path.join(os.path.expanduser('~'), '.claude', 'skills', 'win-skill-installer', 'scripts', 'main.py')
    subprocess.run([sys.executable, _installer, 'skill-winmetrics'], check=True)

sys.path.insert(0, _skill_dir)
from skill_winmetrics import SkillWinMetrics

# 获取当前分支名和仓库名
branch_name = subprocess.run(['git', 'branch', '--show-current'], capture_output=True, text=True).stdout.strip()
repo_name = subprocess.run(['git', 'rev-parse', '--show-toplevel'], capture_output=True, text=True).stdout.strip()
repo_name = os.path.basename(repo_name)

# 从分支名提取demand_id（可选）
import re
demand_id = None
match = re.search(r'feature/(\d+)', branch_name)
if match:
    demand_id = match.group(1)

wm = SkillWinMetrics('git-merge', demand_id=demand_id)
wm.report_skill_started(repo_name=repo_name, branch_name=branch_name)
```

> **重要提醒**：
> - 仅独立调用时执行此上报（流水线内调用时跳过）
> - 此步骤不可跳过，必须在开始执行 git-merge 流程前执行
> - 如果无法从分支名提取 demand_id，使用仓库名作为标识

---

## ⚠️ WinMetrics 事件上报（强制执行）

**必须执行以下 WinMetrics 上报，不可跳过。**

### 事件上报时机

| 时机 | 事件名称 | 调用方法 | 必须执行 |
|------|----------|----------|----------|
| **技能启动时** | git-merge.started | `wm.report_skill_started()` | ✅ 独立调用时必须上报 |
| **技能完成时** | git-merge.completed | `wm.report_skill_completed()` | ✅ 独立调用时必须上报 |

### 强制执行规则

1. **独立调用时**（无 AUTO_DEV_PIPELINE 环境变量）：
   - ✅ 必须上报 `git-merge.started`（技能启动）
   - ✅ 必须上报 `git-merge.completed`（技能完成）

2. **流水线内调用时**（有 AUTO_DEV_PIPELINE=true）：
   - ⏭️ 跳过 `git-merge.started` 和 `git-merge.completed`（auto-dev 已上报 stage 级事件）

### WinMetrics 初始化与上报代码

```python
import sys, os
import subprocess

# 检查 skill-winmetrics 是否已安装，未安装则自动下载
_skill_dir = os.path.join(os.path.expanduser('~'), '.claude', 'skills', 'skill-winmetrics', 'scripts')
if not os.path.exists(os.path.join(_skill_dir, 'skill_winmetrics.py')):
    _installer = os.path.join(os.path.expanduser('~'), '.claude', 'skills', 'win-skill-installer', 'scripts', 'main.py')
    subprocess.run([sys.executable, _installer, 'skill-winmetrics'], check=True)

sys.path.insert(0, _skill_dir)
from skill_winmetrics import SkillWinMetrics

# 获取当前分支名和仓库名
branch_name = subprocess.run(['git', 'branch', '--show-current'], capture_output=True, text=True).stdout.strip()
repo_name = subprocess.run(['git', 'rev-parse', '--show-toplevel'], capture_output=True, text=True).stdout.strip()
repo_name = os.path.basename(repo_name)

# 从分支名提取demand_id（可选）
import re
demand_id = None
match = re.search(r'feature/(\d+)', branch_name)
if match:
    demand_id = match.group(1)

# 初始化WinMetrics上报器（技能开始时执行）
wm = SkillWinMetrics('git-merge', demand_id=demand_id)

# 技能启动上报（仅独立调用时执行）
wm.report_skill_started(repo_name=repo_name, branch_name=branch_name)

# ... 执行 Git 操作流程 ...

# 技能完成上报（仅独立调用时执行）
wm.report_skill_completed(
    repo_name=repo_name,
    status='success'
)
```

---

## ⚠️ 核心原则

**必须严格按照以下步骤顺序执行，不得跳过任何步骤：**

```
Step 0 → Step 1 → Step 2(可选) → Step 3 → Step 4 → Step 5 → Step 6 → Step 7 → Step 8 → Step 9 → Step 10
```

**确认点（使用 AskUserQuestion，单选）：**
- Step 1: 有修改时 → 是否提交
- Step 2: commit message 确认
- Step 3: 首次选择主分支
- Step 7: 有冲突时选择策略
- Step 8: 验证失败时是否继续
- Step 10: 是否推送

**禁止提前终止：** 必须执行到 Step 10 完成推送后才能结束。

**禁止推送保护分支（最高优先级规则）：**

保护分支 = Step 3 中选择的主分支（master/main/develop 等）。在执行 Step 10 推送前，必须检查当前分支是否为主分支本身。如果是，**拒绝推送并报错**。

git-merge 的职责是将主分支合并**到**开发分支，然后推送开发分支。**绝对禁止将开发分支合并到主分支并推送主分支。**

---

## Step 0: 检测项目结构

**命令**：
```bash
git rev-parse --is-inside-work-tree 2>/dev/null
```

**情况 A - 单仓库**：当前目录是 git → 直接进入 Step 1

**情况 B - 多模块**：扫描子目录

**【输出格式 - 多模块检测】**：
```
🔍 检测到多个 Git 仓库：

┌──────────────────────────┬─────────────────────────┬────────────┐
│          仓库            │          分支           │   状态     │
├──────────────────────────┼─────────────────────────┼────────────┤
│ winning-mdm              │ feature/1506090-xxx     │ 有修改     │
│ winning-dtc-Akso         │ master                  │ 干净       │
│ winning-dtc-MiddleWare   │ develop                 │ 干净       │
└──────────────────────────┴─────────────────────────┴────────────┘
```

**【用户选择】**（AskUserQuestion，单选）：
```
问题：请选择要操作的仓库
选项：
  • winning-mdm (有修改) [推荐]
  • 全部仓库
  • 取消
```

---

## Step 1: 检查工作区状态

**命令**：
```bash
git status --porcelain
```

**情况 A - 工作区干净**：
```
✅ 工作区干净，无需提交

→ 继续 Step 3
```

**情况 B - 有未提交修改**：

**【输出格式】**：
```
📝 检测到未提交的修改：

┌──────────────────────────────────────────────────────┬────────┐
│                       文件                           │  状态  │
├──────────────────────────────────────────────────────┼────────┤
│ src/main/java/.../ValueSetEntity.java               │  修改  │
│ src/main/java/.../ValueSetDAOImpl.java              │  修改  │
│ src/main/java/.../ValueSetDTO.java                  │  修改  │
└──────────────────────────────────────────────────────┴────────┘
```

**【用户选择】**（AskUserQuestion，单选）：
```
问题：检测到未提交的修改，如何处理？
选项：
  • 提交后继续 [推荐]
  • 暂存(stash)后继续
  • 取消操作
```

- 选择"提交" → **进入 Step 2**
- 选择"stash" → 执行 stash，**进入 Step 3**
- 选择"取消" → 结束流程

---

## Step 2: 提交代码

**【Step 2.1 - 显示变更】**：
```
📋 变更摘要：

┌──────────────────────────────────────────────────────┬────────┐
│                       文件                           │  变更  │
├──────────────────────────────────────────────────────┼────────┤
│ ValueSetEntity.java                                  │ -4 行  │
│ ValueSetDAOImpl.java                                 │ -1 行  │
│ ValueSetDTO.java                                     │ -4 行  │
├──────────────────────────────────────────────────────┼────────┤
│ 合计                                                 │ -9 行  │
└──────────────────────────────────────────────────────┴────────┘

变更说明：移除 ValueSet 的 valueId 字段
```

**【Step 2.2 - 查询 TFS 任务】**：

从分支名自动提取工作项ID（如 `feature/1506090-xxx` → `1506090`），然后通过 TFS MCP 查询关联任务：

**查询逻辑**：
1. 调用 `tfs_get_workitem(id)` 获取工作项详情
2. 判断工作项类型：
   - 若为**需求**（如 Product Backlog Item / User Story）：直接调用 `tfs_get_relations(id, "children")` 获取子任务
   - 若为**任务**（Task）：调用 `tfs_get_relations(id, "parent")` 找到父需求，再调用 `tfs_get_relations(parentId, "children")` 获取所有同级任务
3. 汇总所有任务列表

**【用户选择】**（AskUserQuestion，单选）：
```
问题：请选择本次提交关联的任务（将用于 commit message）
选项：
  • #1506101 - 实现值集管理接口
  • #1506102 - 值集实体类调整
  • #1506103 - 单元测试编写
  • #1506090（需求本身，不关联子任务）
  • 自定义输入
  • 跳过（不添加任务号）
```

> 如果 TFS 查询失败（网络问题、ID不存在等），回退到手动输入模式。

**【Step 2.3 - 生成 commit message】**（AskUserQuestion，单选）：

基于用户选择的任务和代码变更，生成 commit message。

自动分析 `git diff` 的变更内容，结合所选任务的标题，生成语义化的提交说明。

**生成策略**：
- **优先使用任务标题**：直接取 TFS 任务的标题作为提交说明（简洁可靠）
- **AI 增强**：分析代码 diff 内容，生成更精确的提交说明

最终格式：`#任务号 提交说明`

> **强制规则**：commit message 禁止只包含任务号（如 `#1506101`）。如果 Step 2.2 中未获取到任务标题，**必须调用 `tfs_get_workitem(id)` 查询该任务的标题**，拼接到任务号后面。只有在用户选择"跳过（不添加任务号）"时才可以不包含任务号。

```
问题：确认 commit message: "#1506101 实现值集管理接口"？
选项：
  • 确认提交
  • 修改消息（选择后弹出输入框）
  • 取消
```

**【Step 2.4 - 提交结果】**：
```
✅ 提交成功！

• Commit: ced2d5553
• 消息: #1506101 实现值集管理接口
• 关联任务: #1506101 - 实现值集管理接口
• 变更: 3 files changed, 9 deletions(-)

→ 继续 Step 3
```

---

## Step 3: 确定分支信息

**命令**：
```bash
git branch --show-current
git config --get Codex-merge.mainBranch
```

**情况 A - 已配置主分支**：
```
📌 分支信息：
  • 当前分支: feature/1506090-add-value-id
  • 主分支: master（使用上次配置）

→ 继续 Step 4
```

**情况 B - 首次配置**：

**【用户选择】**（AskUserQuestion，单选）：
```
问题：请选择主分支
选项：
  • master（自动检测）
  • main
  • develop
  • 自定义输入
```

配置后保存：`git config Codex-merge.mainBranch master`

---

## Step 4: 获取远端更新

**命令**：
```bash
git fetch origin
```

**【输出格式】**：
```
📥 获取远端更新...

✅ 已获取远端更新
  • 更新时间: 2024-03-18 14:30:00
  • 检测到 2 个新提交

→ 继续 Step 5
```

---

## Step 5: 更新主分支

**命令**：
```bash
git checkout master
git pull origin master
```

**【输出格式】**：
```
📦 更新主分支 master...

✅ 主分支已更新
  • 新增提交: 2 个
  • 最新提交: abc1234 - fix: 修复xxx问题

→ 继续 Step 6
```

---

## Step 6: 合并到开发分支

**命令**：
```bash
git checkout feature/1506090-add-value-id
git merge master
```

**【输出格式 - 无冲突】**：
```
🔄 合并 master → feature/1506090-add-value-id...

✅ 合并成功，无冲突

→ 继续 Step 7
```

**【输出格式 - 有冲突】**：
```
🔄 合并 master → feature/1506090-add-value-id...

⚠️ 检测到冲突：

┌──────────────────────────────────────────────────────┐
│ 冲突文件                                              │
├──────────────────────────────────────────────────────┤
│ src/main/java/.../ValueSetEntity.java                │
│ src/main/java/.../Config.java                        │
└──────────────────────────────────────────────────────┘

→ 继续 Step 7 处理冲突
```

---

## Step 7: 处理冲突

**情况 A - 无冲突**：直接进入 Step 8

**情况 B - 有冲突**：

**【用户选择】**（AskUserQuestion，单选，每个冲突文件）：
```
问题：如何处理冲突文件 ValueSetEntity.java？
选项：
  • 保留本地版本（使用当前分支的修改）
  • 保留远端版本（使用主分支的修改）
  • 手动解决（我会在编辑器中修改）
  • 取消合并
```

**【冲突解决后】**：
```
✅ 冲突已解决

• 解决方式: 保留本地版本
• 解决文件: 2 个

→ 继续 Step 8
```

---

## Step 8: 验证代码

**自动检测项目类型**：
```bash
[ -f "pom.xml" ] && echo "maven"
[ -f "package.json" ] && echo "npm"
```

**【输出格式 - 开始验证】**：
```
🔍 代码验证...

• 项目类型: Maven
• 验证命令: mvn test -q
```

**情况 A - 验证通过**：
```
✅ 验证通过

• 测试用例: 156 个通过
• 耗时: 12.3s

→ 继续 Step 9
```

**情况 B - 验证失败**：

**【用户选择】**（AskUserQuestion，单选）：
```
❌ 验证失败

• 失败用例: 2 个
• 错误信息: [简要错误]

问题：验证失败，是否继续？
选项：
  • 继续（跳过验证，继续推送）
  • 终止（不推送，手动修复）
```

---

## Step 9: 输出报告

**【输出格式】**：
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 Git Merge Report
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📌 分支信息
  • 当前分支: feature/1506090-add-value-id
  • 主分支: master
  • 操作时间: 2024-03-18 14:35:22

📝 提交信息
  • Commit: ced2d5553
  • 消息: #1506090 移除 ValueSet 的 valueId 字段
  • 变更: 3 files, 9 deletions

🔄 合并状态
  • 状态: ✅ 成功
  • 新增提交: 2 个

✅ 验证结果
  • 状态: ✅ 通过
  • 测试: 156 cases passed

→ 继续 Step 10
```

---

## Step 10: 推送到远程

**【用户选择】**（AskUserQuestion，单选）：
```
问题：是否推送到远程仓库？
选项：
  • 推送到远程 [推荐]
  • 暂不推送（本地已完成合并）
```

**⚠️ 分支保护检查（推送前必须执行）**：
```bash
CURRENT_BRANCH=$(git branch --show-current)
MAIN_BRANCH=$(git config --get Codex-merge.mainBranch)
# 检查1: 当前分支是否就是主分支（保护分支）
[[ "$CURRENT_BRANCH" == "$MAIN_BRANCH" ]] && { echo "❌ BLOCKED: 当前分支 '$CURRENT_BRANCH' 是主分支/保护分支，禁止推送。只允许推送 feature/* 开发的分支。"; exit 1; }
# 检查2: 当前分支不应以 develop/master/main/release 等保护名称开头
case "$CURRENT_BRANCH" in
  master|main|develop|release*|hotfix*) echo "❌ BLOCKED: 当前分支 '$CURRENT_BRANCH' 是保护分支，禁止推送"; exit 1 ;;
esac
```

如果检查失败：**拒绝推送，报错退出**。不允许绕过此检查。

**命令**：
```bash
git push -u origin feature/1506090-add-value-id
```

**【最终输出格式】**：
```
✅ 推送成功！

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 完整操作报告
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌────────────┬─────────────────────────────────────────────┐
│    项目    │                    内容                     │
├────────────┼─────────────────────────────────────────────┤
│ 仓库       │ winning-mdm                                 │
│ 分支       │ feature/1506090-add-value-id                │
│ Commit     │ ced2d5553                                   │
│ 消息       │ #1506090 移除 ValueSet 的 valueId 字段      │
│ 变更       │ 3 files, 9 deletions                        │
│ 合并       │ ✅ master → feature/1506090-add-value-id    │
│ 验证       │ ✅ 通过                                     │
│ 推送       │ ✅ origin/feature/1506090-add-value-id      │
└────────────┴─────────────────────────────────────────────┘

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 下一步
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 代码已推送到远程，可以创建 PR：

  ┌────────────────────────────────────────────────────┐
  │  触发词                  │  功能                   │
  ├────────────────────────────────────────────────────┤
  │  "创建PR" / "提交PR"     │  创建 PR + 关联工作项   │
  │  "代码评审"              │  代码质量分析           │
  └────────────────────────────────────────────────────┘

  • 查看变更: git log --oneline -5
```

---

## 多模块汇总报告

当操作多个仓库时，最后输出汇总：

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 多模块操作汇总
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌──────────────────────┬──────────┬──────────┬──────────┐
│        仓库          │  提交    │  合并    │  推送    │
├──────────────────────┼──────────┼──────────┼──────────┤
│ winning-mdm          │    ✅    │    ✅    │    ✅    │
│ winning-dtc-Akso     │    -     │    ✅    │    ✅    │
│ winning-dtc-MW       │    -     │    ⚠️    │    ❌    │
└──────────────────────┴──────────┴──────────┴──────────┘

📊 统计: ✅ 成功 2 | ⚠️ 冲突已解决 0 | ❌ 失败 1
```

---

## 错误处理

| 场景 | 输出示例 |
|------|----------|
| 网络错误 | `❌ 网络错误，无法连接远程仓库` + 重试选项 |
| 权限错误 | `❌ 权限不足，请检查认证配置` |
| 合并失败 | `❌ 合并失败: [错误详情]` + 回退选项 |
| 推送失败 | `❌ 推送失败: [错误详情]` + 重试选项 |

---

## ⚠️ WinMetrics 上报（技能完成）【强制执行】

**在输出工作总结前，必须先执行 WinMetrics 技能完成上报：**

```python
# Windows: python -c "<script_content>"
# Linux/Mac: python << 'EOF' ... EOF
import sys, os
import subprocess
sys.path.insert(0, os.path.join(os.path.expanduser('~'), '.claude', 'skills', 'skill-winmetrics', 'scripts'))
from skill_winmetrics import SkillWinMetrics

# 获取仓库名
repo_name = subprocess.run(['git', 'rev-parse', '--show-toplevel'], capture_output=True, text=True).stdout.strip()
repo_name = os.path.basename(repo_name)

# 从分支名提取demand_id（可选）
import re
branch_name = subprocess.run(['git', 'branch', '--show-current'], capture_output=True, text=True).stdout.strip()
demand_id = None
match = re.search(r'feature/(\d+)', branch_name)
if match:
    demand_id = match.group(1)

wm = SkillWinMetrics('git-merge', demand_id=demand_id)

commits_pushed = [推送的提交数]
conflicts_resolved = [是否有冲突解决]
status = 'success' if commits_pushed > 0 else 'failed'

wm.report_skill_completed(
    repo_name=repo_name,
    status=status,
    commits_pushed=commits_pushed,
    conflicts_resolved=conflicts_resolved
)
```

> **重要提醒**：
> - 仅独立调用时执行此上报（流水线内调用时跳过）
> - 此步骤不可跳过，必须在输出工作总结前执行

---

## 📋 工作总结（必须执行）

**在完成所有操作后，必须输出以下工作总结：**

```markdown
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 Git 操作总结
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## ✅ 已完成的操作

### 仓库信息
- **仓库名称**: [仓库名]
- **当前分支**: [分支名]
- **主分支**: [主分支名]

### 操作记录
| 步骤 | 状态 | 说明 |
|------|------|------|
| 工作区检查 | ✅/⚠️ | [干净/有修改已提交] |
| 代码提交 | ✅/跳过 | [commit hash 或 无修改] |
| 主分支更新 | ✅ | [新增N个提交] |
| 合并操作 | ✅/⚠️ | [成功/有冲突已解决] |
| 代码验证 | ✅/⚠️/跳过 | [通过/失败但继续/无测试] |
| 远程推送 | ✅/跳过 | [已推送/用户选择不推送] |

### 提交信息（如有提交）
- **Commit**: [commit hash]
- **消息**: [commit message]
- **变更**: [X files changed, Y insertions, Z deletions]

### 冲突处理（如有冲突）
- **冲突文件**: [文件列表]
- **解决方式**: [保留本地/保留远端/手动解决]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 💡 后续建议

- **创建 PR**: 使用 tfs-pr-skill 创建 Pull Request
- **代码评审**: 进行代码评审确保质量

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```
