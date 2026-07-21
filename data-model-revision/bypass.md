---
name: data-model-revision-bypass
description: |
  data-model-revision skill的auto-dev流水线bypass策略。
  定义在auto-dev模式下各Stage的交互点跳过策略。
version: 1.0.0
metadata:
  author: 张磊
  created: 2026-07-08
---

# data-model-revision Bypass策略

## 概述

本文件定义data-model-revision skill在auto-dev流水线模式下的行为。
auto-dev要求所有技能遵守：git隔离 + 无人工交互 + summary.md输出。

## Stage Bypass矩阵

| Stage | 正常模式 | auto-dev模式 | 说明 |
|-------|---------|-------------|------|
| Stage 1: 需求分析 | 无交互 | 无交互 | 从dev-plan.md读取需求，全自动 |
| Stage 2: PDF提取 | 无交互 | 无交互 | MinerU/pdftotext提取，全自动 |
| Stage 3: Word修订 | 无交互 | 无交互 | python-docx自动填充，全自动 |
| Stage 4: 逐行核对 | **人工核对** | **自动核对** | 使用scripts/verify_word_pdf.py脚本自动核对 |
| Stage 5: DDL生成 | 无交互 | 无交互 | 调用reg-ddl-generator，全自动 |
| Stage 6: 修订记录SQL | 无交互 | 无交互 | 生成edsm_revise_record/detail，全自动 |
| Stage 7: 修订记录Word | 无交互 | 无交互 | python-docx自动追加行，全自动 |
| Stage 8: 输出summary.md | 无交互 | 无交互 | 生成修订总结报告，**不执行git操作** |

## 关键差异说明

### Stage 4: 核对模式

**正常模式**：
- 人工逐行比对PDF与Word
- 手动标记不一致项
- 手动修正错误

**auto-dev模式**：
- 使用`scripts/verify_word_pdf.py`自动核对
- 脚本输出核对报告到`{DOCS_DIR}/verify-report.md`
- 如果发现严重错误，终止流程并在summary.md中列出错误
- 不暂停等待人工确认

### Stage 8: 输出模式

**正常模式**：
- 可选：git add + commit（如果用户要求）
- 输出修订总结

**auto-dev模式**：
- **禁止执行任何git操作**
- 只输出`{DOCS_DIR}/summary.md`
- git操作由auto-dev Step 4统一处理

## 调用约束

### 禁止行为
- ❌ 禁止执行 `git add`
- ❌ 禁止执行 `git commit`
- ❌ 禁止执行 `git push`
- ❌ 禁止执行 `git pull`
- ❌ 禁止执行任何git命令
- ❌ 禁止暂停等待人工确认
- ❌ 禁止调用clarify工具

### 必须行为
- ✅ 必须从`{DOCS_DIR}/dev-plan.md`读取需求
- ✅ 必须输出`{DOCS_DIR}/summary.md`
- ✅ Stage 4必须使用脚本自动核对
- ✅ 所有文件修改保留在工作区
- ✅ 所有产出文件写入指定路径

## 错误处理

| 错误类型 | 处理方式 |
|---------|---------|
| PDF提取失败 | 输出错误到summary.md，终止流程 |
| Word修订失败 | 输出错误到summary.md，终止流程 |
| 核对发现严重错误 | 输出错误到summary.md，终止流程 |
| DDL生成失败 | 输出错误到summary.md，终止流程 |

**关键原则**：即使失败，也必须输出summary.md（包含错误信息），否则auto-dev会判定Step 2失败。

## 与Superpowers的关系

data-model-revision **不使用**Superpowers skill：
- ❌ 不调用test-driven-development
- ❌ 不调用systematic-debugging
- ❌ 不调用requesting-code-review
- ❌ 不调用verification-before-completion

原因：数据模型修订是文档+DDL工作，不是代码TDD开发。
本skill有自己的核对机制（Stage 4）和质量控制。

## 调用示例

```python
Skill(
  skill="data-model-revision",
  args="dev-plan={DOCS_DIR}/dev-plan.md, output={DOCS_DIR}/summary.md"
)
```

## 产物清单

执行完成后，以下文件必须存在：

| 文件 | 路径 | 说明 |
|------|------|------|
| summary.md | `{DOCS_DIR}/summary.md` | **必须**，修订总结报告 |
| verify-report.md | `{DOCS_DIR}/verify-report.md` | 核对报告（Stage 4产出） |
| Word文档 | 原路径 | 修订后的文档 |
| DDL脚本 | `{WORK_DIR}/edsm_sql/greenplum/` | Flyway迁移脚本 |
| 修订记录SQL | `{WORK_DIR}/system_sql/rhdp_dw/greenplum/` | edsm修订记录 |
