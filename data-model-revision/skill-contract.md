---
name: data-model-revision-contract
description: |
  data-model-revision skill的接口契约，定义输入输出规范。
  用于auto-dev流水线集成时的契约校验。
version: 1.0.0
metadata:
  author: 张磊
  created: 2026-07-08
---

# data-model-revision 技能契约

## 输入

| 参数 | 来源 | 说明 |
|------|------|------|
| `{DOCS_DIR}/dev-plan.md` | PM阶段输出 | 开发计划，包含修订需求详情 |
| `{WORK_DIR}/{仓库名}/` | auto-dev准备阶段 | git worktree工作目录 |
| PDF标准文档路径 | dev-plan.md中指定 | 数据标准源文件 |
| Word文档路径 | dev-plan.md中指定 | 待修订的目标文档 |

## 输出

| 产物 | 路径 | 说明 |
|------|------|------|
| `{DOCS_DIR}/summary.md` | 必须输出 | 修订总结报告 |
| Word文档修订版 | 原路径覆盖 | 包含新增表/字段的文档 |
| DDL脚本 | `{WORK_DIR}/edsm_sql/greenplum/` | Flyway迁移脚本 |
| 修订记录SQL | `{WORK_DIR}/system_sql/rhdp_dw/greenplum/` | edsm_revise_record + edsm_revise_detail |
| 修订记录Word更新 | 原路径覆盖 | 新增修订记录行 |

## summary.md 格式规范

```markdown
# 数据模型修订总结

## 修订概述
- 需求ID: {DEMAND_ID}
- 修订类型: {公版/项目化}
- 版本号: {V6.0.xxx}

## 修订内容

### 新增表
| 表名 | 中文名 | 字段数 | 所属数据集 |
|------|--------|--------|-----------|
| T_HD_XXX | XXX表 | 15 | 血透相关 |

### 新增字段
| 表名 | 字段名 | 数据类型 | 约束 |
|------|--------|----------|------|
| T_HD_XXX | FIELD_NAME | S1(100) | M |

## 生成的脚本

### DDL脚本
- `V20260708152022__create_table_xxx.sql`

### 修订记录SQL
- `V20260708152022__revise_record.sql`

## Word文档变更
- `RDA-01-标准规范-数据模型-V6.0.docx` - 新增{N}个表定义

## 核对结果
- PDF提取字段数: {X}
- Word填充字段数: {Y}
- 核对通过率: {Z}%

## 已知问题
{如有问题在此列出，如无则写"无"}
```

## 失败处理

| 场景 | 处理方式 |
|------|---------|
| PDF提取失败 | 终止流程，输出错误到summary.md |
| Word修订失败 | 终止流程，输出错误到summary.md |
| DDL生成失败 | 终止流程，输出错误到summary.md |
| 核对发现严重错误 | 终止流程，列出错误到summary.md |

**关键约束**：
- 必须输出summary.md，即使流程失败也要输出错误信息
- summary.md是auto-dev Step 2.3检查产物完整性的依据
- 所有脚本路径必须使用实际生成的文件名，不能使用占位符

## auto-dev集成说明

### Git操作隔离
- **本Skill不执行任何git操作**
- git add/commit/push由auto-dev Step 4统一处理
- 所有文件修改保留在工作区，等待Step 4提交

### 交互点处理
- Stage 4核对：使用`scripts/verify_word_pdf.py`自动核对
- 其他阶段：无交互点，全自动执行

### 调用方式
```python
Skill(
  skill="data-model-revision",
  args="dev-plan={DOCS_DIR}/dev-plan.md, output={DOCS_DIR}/summary.md"
)
```
