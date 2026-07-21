# 示例：pm-teamB — 团队 B 定制需求分析技能

这是一个可替换标准 `pm` 技能的完整示例，展示业务团队如何接入自己的技能到 auto-dev 流水线。

## 文件结构

```
pm-teamB/
├── SKILL.md                          # 技能主文件（触发条件、工作流程、输出契约）
├── bypass.md                         # auto-dev 全自动模式的 bypass 策略
└── references/
    ├── evaluation-template.md        # 三维度快速评估模板
    └── dev-plan-template.md          # 精简开发计划模板（4 节结构）
```

## 与标准 pm 的差异

| 项目 | 标准 pm | pm-teamB |
|------|---------|----------|
| 评估体系 | 五维度 125 分制 | 三维度 100 分制（必要性/可行性/影响面） |
| 需求补充 | 最多 10 个追问 | 最多 3 个追问，聚焦技术可行性 |
| PRD 结构 | 7 节完整 PRD | 精简 4 节（概述/功能点/接口变更/验收标准） |
| 原型设计 | WinDesign Next / Pencil | **跳过** |
| 验收标准 | 无 | 自动生成验收标准清单 |

## 如何使用

### 1. 复制到技能目录

```bash
cp -r examples/pm-teamB/ ~/.claude/skills/pm-teamB/
```

### 2. 修改 pipeline.yaml

```yaml
skill_registry:
  pm:
    prefix: "pm"
    default: "pm-teamB"       # ← 改为 pm-teamB
    replaceable: true
    contract_ref: "skill-contracts.md#pm"
```

### 3. 校验

```bash
python scripts/parse-pipeline.py validate
# 期望输出: ✅ 配置校验通过
```

### 4. 按需定制

修改以下文件适配你的团队：
- `SKILL.md` — 调整工作流程、评估维度、输出结构
- `bypass.md` — 调整 bypass 策略（哪些步骤跳过、哪些保留交互）
- `references/` — 替换评估模板和开发计划模板

## 注意事项

1. **输出契约不可破坏**：`dev-plan.md` 必须包含功能点清单和涉及仓库信息，否则编码阶段无法路由到正确的仓库
2. **技能名前缀**：目录名必须是 `pm-` 开头（如 `pm-teamB`、`pm-custom`），否则校验不通过
3. **bypass.md 必须存在**：缺失时回退到 `references/bypass-strategies.md` 中的 `## pm bypass` 段
4. **Git 操作隔离**：PM 技能不涉及 git 操作，无需关注此项
