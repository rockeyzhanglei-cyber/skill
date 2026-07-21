# Auto-Dev 权限配置完整指南

---

## 一、全局级权限（~/.claude/settings.json）

**适用场景**：auto-dev 在多个产品目录间切换执行，子 agent 可能从任意目录启动

**配置路径**：`~/.claude/settings.json`

**完整配置**：
```json
{
  "autoUpdatesChannel": "latest",
  "env": {
    "ANTHROPIC_AUTH_TOKEN": "<your-api-key>",
    "ANTHROPIC_BASE_URL": "<your-api-base-url>"
  },
  "providers": {
    "anthropic": {
      "apiKey": ""
    }
  },
  "permissions": {
    "allow": [
      "Bash(mkdir:*)",
      "Bash(rm:*)",
      "Bash(cp:*)",
      "Bash(mv:*)",
      "Bash(ls:*)",
      "Bash(cat:*)",
      "Bash(touch:*)",
      "Bash(chmod:*)",
      "Bash(git clone:*)",
      "Bash(git init:*)",
      "Bash(git fetch:*)",
      "Bash(git pull:*)",
      "Bash(git push:*)",
      "Bash(git checkout:*)",
      "Bash(git switch:*)",
      "Bash(git branch:*)",
      "Bash(git add:*)",
      "Bash(git commit:*)",
      "Bash(git merge:*)",
      "Bash(git rebase:*)",
      "Bash(git reset:*)",
      "Bash(git stash:*)",
      "Bash(git worktree:*)",
      "Bash(git status:*)",
      "Bash(git diff:*)",
      "Bash(git log:*)",
      "Bash(git show:*)",
      "Bash(git remote:*)",
      "Bash(git config:*)",
      "Bash(git rev-parse:*)",
      "Bash(git symbolic-ref:*)",
      "Bash(python:*)",
      "Bash(pip:*)",
      "Bash(node:*)",
      "Bash(npm:*)",
      "Bash(yarn:*)",
      "Write(/c/Users/{username}/auto-dev-docs/*)",
      "Write(/c/Users/{username}/.cache/WinCode/skill/auto-dev/*)",
      "mcp__tfs-mcp__*",
      "mcp__devops-mcp__*"
    ]
  }
}
```

> **注意**：`Write` 路径中的 `{username}` 需替换为实际的 Windows 用户名。

---

## 二、项目级权限（产品目录下）

**适用场景**：只在特定产品目录下执行，权限范围更小更安全

**配置路径**：`{产品代码目录}/.claude/settings.json`

也可以直接使用预置模板：
```bash
cp SKILL_DIR/templates/project-settings.json {产品代码目录}/.claude/settings.json
```

**完整配置**：
```json
{
  "permissions": {
    "allow": [
      "Bash(mkdir:*)",
      "Bash(rm:*)",
      "Bash(cp:*)",
      "Bash(mv:*)",
      "Bash(ls:*)",
      "Bash(cat:*)",
      "Bash(touch:*)",
      "Bash(chmod:*)",
      "Bash(git clone:*)",
      "Bash(git init:*)",
      "Bash(git fetch:*)",
      "Bash(git pull:*)",
      "Bash(git push:*)",
      "Bash(git checkout:*)",
      "Bash(git switch:*)",
      "Bash(git branch:*)",
      "Bash(git add:*)",
      "Bash(git commit:*)",
      "Bash(git merge:*)",
      "Bash(git rebase:*)",
      "Bash(git reset:*)",
      "Bash(git stash:*)",
      "Bash(git worktree:*)",
      "Bash(git status:*)",
      "Bash(git diff:*)",
      "Bash(git log:*)",
      "Bash(git show:*)",
      "Bash(git remote:*)",
      "Bash(git config:*)",
      "Bash(git rev-parse:*)",
      "Bash(git symbolic-ref:*)",
      "Bash(python:*)",
      "Bash(pip:*)",
      "Bash(node:*)",
      "Bash(npm:*)",
      "Bash(yarn:*)",
      "Write(*)",
      "mcp__tfs-mcp__*",
      "mcp__devops-mcp__*"
    ]
  }
}
```

---

## 三、权限说明对照表

| 权限类型 | 说明 | 必须 |
|----------|------|------|
| `Bash(mkdir:*)` | 创建目录 | ✅ |
| `Bash(rm:*)` | 删除文件/目录 | ✅ |
| `Bash(cp:*)` | 复制文件 | ✅ |
| `Bash(mv:*)` | 移动文件 | ✅ |
| `Bash(git clone:*)` | 克隆仓库 | ✅ |
| `Bash(git worktree:*)` | 创建 worktree | ✅ |
| `Bash(git checkout:*)` | 切换分支 | ✅ |
| `Bash(git push:*)` | 推送代码 | ✅ |
| `Bash(git commit:*)` | 提交代码 | ✅ |
| `Bash(git merge:*)` | 合并分支 | ✅ |
| `Write(*)` | 写文件（项目级） | ✅ |
| `Write(/c/Users/{username}/auto-dev-docs/*)` | 写文件（全局级，限定路径） | ✅ |
| `mcp__tfs-mcp__*` | TFS MCP 所有操作 | ✅ |
| `mcp__devops-mcp__*` | DevOps MCP（PR创建、构建、部署） | ✅ |

---

## 四、推荐方案

**auto-dev 建议用全局级权限**，原因：

1. 子 agent 从主 session 启动，继承全局权限
2. auto-dev 需在源仓库和 worktree 目录之间切换
3. products.yaml 可能配置多个产品，需要跨目录操作

**如果只用项目级**，需要额外配置：
- 每个 worktree 目录的 `.claude/settings.json`
- 每个源仓库的 `.claude/settings.json`

---

## 五、快速配置命令

**配置全局权限**：
```
给我配置 auto-dev 全局权限，包含 git、mkdir、Write、TFS MCP 等完整权限列表
```

**配置项目级权限**：
```
给 auto-dev 产品 集团MDM 配置项目级权限
```

**批量配置多个产品**：
```
给 auto-dev 产品 集团MDM、MDM6.0 配置项目级权限
```

---

## 六、常见问题

### Q1: 为什么 auto-dev 执行失败提示权限不足？

**原因**：全局 settings.json 未配置 `permissions.allow`，子 agent 执行 git clone、mkdir、Write 等操作被拦截。

**解决方案**：按本文档配置全局权限或项目级权限。

### Q2: 全局权限和项目级权限哪个优先？

**优先级**：项目级 > 全局。项目级权限会覆盖全局配置。

### Q3: Write 权限路径怎么写？

**Windows 路径格式**：使用 Git Bash 风格
```
Write(/c/Users/{username}/auto-dev-docs/*)    # 限定集中文档目录
Write(*)                            # 项目级：允许所有路径（仅在项目目录生效）
```

### Q4: git credentials 配置在哪里？

**路径**：`~/.git-credentials`

**格式**：
```
http://{用户名}:{密码}@{TFS服务器地址}
```

**配置命令**：
```bash
echo "http://{用户名}:{密码}@tfs2018-web.winning.com.cn:8080" >> ~/.git-credentials
git config --global credential.helper store
```

---

## 七、配置检查清单

| 配置项 | 路径 | 状态检查 |
|--------|------|----------|
| products.yaml | `SKILL_DIR/templates/products.yaml` | ✅ YAML 格式正确 |
| git-credentials | `~/.git-credentials` | ✅ 已配置 |
| 全局权限 | `~/.claude/settings.json` | ✅ permissions.allow 已配置 |
| TFS MCP 连接 | MCP 服务器 | ✅ 已连接 |
| 企微 Webhook | `config.env` | ✅ WECHAT_WEBHOOK_URL 已配置 |

---

## 八、文档版本

- **版本**：v1.1
- **更新日期**：2026-04-26
- **适用范围**：auto-dev 全链路自动化开发流水线
