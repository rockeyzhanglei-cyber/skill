# products.yaml 配置说明

> **技能名联动说明**：以下示例中的技能名（如 `backend-dev`、`frontend-dev`）对应 `pipeline.yaml` 中 `skill_registry` 的 **prefix**。
> products.yaml 中的 `skill` 值不需要随 pipeline.yaml 的 `default` 变化而变化。
> 技能路由逻辑：products.yaml 的 `skill` 值 → 匹配 pipeline.yaml 的 registry prefix → 使用该 key 的 `default` 值调用实际技能。

## 配置文件

| 文件 | 用途 |
|------|------|
| `templates/products.yaml` | 实际使用的配置（包含真实产品数据） |
| `templates/products-template.yaml` | 纯模板（新增产品时复制参考） |

## 配置结构

```yaml
products:
  产品名称:
    product_dir: "F:\work-space\products\my-product"  # 可选: 产品仓库根目录，auto-dev 自动切换到此目录
    worktree: false              # false=直接在源仓库开发（默认）, true=worktree隔离模式
    tfs_project: "TFS项目路径"
    default_skill: "backend-dev"
    default_branch: "develop"
    deploy_env_id: ""            # 必填: 自动部署目标环境ID（每个产品独立配置）
    change_limits:                # 可选
      max_files: 20
      max_insertions: 500
    repos:
      - name: "仓库名"
        url: "git clone URL"
        branch: "分支名"
        skill: "backend-dev"
        tfs_project: "TFS项目路径"
        description: "仓库说明"
    skill_routing:
      "AI-BACKEND": "backend-dev"
      "AI-FRONTEND": "frontend-dev"
      "AI-RDF": "rdf-dev"
      "AI-FULLSTACK":
        - "backend-dev"
        - "frontend-dev"
```

## 新增产品

**方式一：使用脚本（推荐）**
```bash
python SKILL_DIR/scripts/add-product.py
```

**方式二：手动配置**
1. 参考 `templates/products-template.yaml` 的格式
2. 将新产品配置追加到 `templates/products.yaml`

## 常见问题

### Q: 产品名匹配不上怎么办？
A: auto-dev 会列出所有已配置的产品名让用户选择。

### Q: product_dir 是做什么的？
A: 配置产品仓库所在的本地目录路径。配置后 auto-dev 可从任意目录启动，匹配到产品后会自动 cd 到此目录，无需手动在特定目录下启动终端。未配置时回退到当前工作目录（原有行为）。

### Q: 需求涉及多个产品怎么办？
A: Phase1 暂不支持，需要拆成多个需求分别处理。

### Q: 开发过程中出错怎么办？
A: auto-dev 会保留 worktree，用户可以手动进入目录继续开发。

### Q: worktree: false 和 true 有什么区别？
A: `worktree: false`（默认）直接在源仓库目录中创建 feature 分支开发，开发完成后保留分支和代码，适合首次使用和需要手动调试的场景。`worktree: true` 使用 git worktree 为每个需求创建隔离工作目录，适合全自动托管场景。

### Q: worktree 目录在哪里？
A: 在所有产品目录的父目录下，使用 `.worktrees/{需求号}-{主目录名}/` 格式集中管理。例如：
```
F:\space\
├── my-productA\
│   ├── repo1\              ← 源仓库
│   └── repo2\              ← 源仓库
├── my-productB\
│   ├── repo3\
│   └── repo4\
└── .worktrees\                              ← 隐藏目录，统一管理
    ├── 1506090-my-productA\                 ← 需求号-主目录名
    │   ├── repo1\
    │   └── repo2\
    ├── 1506091-my-productA\
    │   ├── repo1\
    │   └── repo2\
    └── 1506092-my-productB\
        ├── repo3\
        └── repo4\
```

### Q: 如何手动管理 worktree？
```bash
# 查看 worktree 列表
bash SKILL_DIR/scripts/setup-worktree.sh list {产品名}

# 检查 worktree 完整性
bash SKILL_DIR/scripts/setup-worktree.sh check {产品名} {需求号}

# 清理 worktree
bash SKILL_DIR/scripts/setup-worktree.sh remove {产品名} {需求号}

# 创建 worktree（通常由流水线自动完成）
bash SKILL_DIR/scripts/setup-worktree.sh create {产品名} {需求号}
```

### Q: worktree 创建失败怎么办？
A: 流水线会自动重试 1 次（`--retry-failed`）。如果仍然失败，会暂停并通知用户。常见原因：
- 磁盘空间不足 → 清理磁盘后重新运行
- 分支冲突 → 手动删除 worktree 后重新运行
- 源仓库不存在 → 检查 products.yaml 配置

### Q: 企微通知没收到？
A: 检查 `WECHAT_WEBHOOK_URL` 环境变量是否配置。未配置时脚本会跳过通知，不影响主流程。

### Q: change_limits 改动量阈值怎么配？
A: 可选字段，控制单个需求的最大改动规模，防止 AI 过度修改。未配置时默认 `max_files: 20, max_insertions: 500`。任一指标超标（OR 关系）会跳过该需求并标记 `AI-SKIPPED`。
