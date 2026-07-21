---
name: win-skill-installer
description: |
  从 WinCode 共享空间（GitLab）搜索并安装 WinAi 技能和 MCP 服务器。

  触发场景：用户说"安装技能"、"搜索技能"、"更新技能"、"下载技能"、
  "有什么技能"、"查看可用技能"、"安装MCP"、"搜索MCP"、"卸载MCP"等。

  核心功能：
  1. 技能 - 搜索、安装（符号链接）
  2. MCP - 搜索、安装（自动配置)、卸载
tags: [skills, installer, tfs, mcp, devops]
allowed-tools: Bash, AskUserQuestion
metadata:
  author: 晁兴鹏
  version: 1.0.0
---

# WinAi Skill & MCP Installer

精简的技能和 MCP 管理工具。

## 工作原理

### 技能
```
TFS 仓库 ──git clone──→ ~/.cache/WinCode/skills/ (缓存)
                                          │
                                          │ 符号链接
                                          ↓
                                    ~/.claude/skills/ (全局目录)
```

### MCP
```
TFS 仓库 ──git clone──→ ~/.cache/WinCode/mcp/ (缓存)
                                          │
                                          │ npm install + build (直接在缓存目录)
                                          ↓
                                    更新 mcpServers 配置 (指向缓存路径)
                                          ↓
                                    ~/.claude.json (Claude 配置)
```

## 使用时机

用户需要：
- 搜索/浏览可用技能
- 安装技能到本地
- 更新技能到最新版本
- 搜索/浏览可用 MCP
- 安装 MCP 到本地（自动配置)
- 卸载已安装的 MCP

## 执行流程

### 通用步骤（必须执行）

**每次被触发时，必须先更新本地缓存，再进行查找操作：**

```bash
python ~/.claude/skills/win-skill-installer/scripts/main.py --update
```

> `--update` 会自动检测已安装的 MCP 并重新编译（`npm install` + `npm run build`），无需手动操作。
> **2026-06-17 增强**：安装/升级 WinCode skill 时，`main.py` 会自动把 skill 复制到 `~/.agents/skills/`（统一真源），并重新挂载 `~/.workbuddy/skills/`、`~/.codex/skills/user/` 三个 agent 入口。无需手动分发。
> **2026-06-17 二次增强**：增加升级前 diff 保护。同步到 `~/.agents/skills/` 之前，会先比对本地真源和 WinCode 仓库新版本，发现本地有未提交的修改会停下问用户：
> - `k` keep — 保留本地修改，跳过本次同步（默认）
> - `o` overwrite — 强制覆盖（会丢本地改动）
> - `b` backup — 把本地修改备份到 `~/Desktop/<name>-patch-<时间戳>/` 后再覆盖
> - `d` diff — 先看差异再决定

**如果 `--update` 输出包含 `[NEED_CREDENTIALS]` 标记，必须执行凭据收集流程：**

1. 使用 `AskUserQuestion` 向用户询问（一次询问，两个问题）：
   - 问题 1：`"请提供您的 TFS 域用户名（如 domain\\username）："`（文本输入，选择 "Other"）
   - 问题 2：`"请提供您的 TFS 域密码："`（文本输入，选择 "Other"）
2. 收集到凭据后，重新运行命令并传入凭据：

```bash
python ~/.claude/skills/win-skill-installer/scripts/main.py --update --cred-user "域用户名" --cred-pass "域密码"
```

> 也可以通过环境变量传入：设置 `TFS_CRED_USER` 和 `TFS_CRED_PASS` 后直接运行 `--update`。

### 技能操作

1. 搜索技能 → 搜索命令
2. 使用 `AskUserQuestion` 确认安装
3. 执行安装命令

### MCP 操作（严格遵守）

1. 搜索/列出 MCP
2. 使用 `AskUserQuestion` 确认安装
3. **判断 MCP 类型，执行对应安装流程：**
   - **tfs-mcp** → 必须执行「tfs-mcp 安装流程」
   - **wiki-mcp** → 必须执行「wiki-mcp 安装流程」
   - **devops-mcp** → 必须执行「devops-mcp 安装流程」
   - **其他 MCP** → 执行通用安装命令

> **禁止在未收集凭据的情况下安装 tfs-mcp、wiki-mcp 或 devops-mcp。**

### tfs-mcp 安装流程（必须）

**第 1 步：执行安装命令**

```bash
python ~/.claude/skills/win-skill-installer/scripts/main.py --mcp tfs-mcp
```

**第 2 步：收集凭据（必须，不可跳过）**

使用 `AskUserQuestion` 向用户询问（一次询问，两个问题）：
- 问题 1：`"请提供您的 TFS 个人访问令牌 (PAT)："`（文本输入，选择 "Other"）
- 问题 2：`"请选择您的默认 TFS 集合："`（选项：`WINNING-6.0`（推荐）、`WN_TECH`、`wn_his`、`其他（手动输入）`）

> TFS_URL 默认为 `http://tfs2018-web.winning.com.cn:8080/tfs`

**第 3 步：更新配置**

读取 `~/.claude.json`，将 tfs-mcp 的配置更新为（保留已有的 command 和 args，添加 env）：

```json
"tfs-mcp": {
  "command": "node",
  "args": ["~/.cache/WinCode/mcp/tfs-mcp/dist/index.js"],
  "env": {
    "TFS_URL": "http://tfs2018-web.winning.com.cn:8080/tfs",
    "TFS_PAT": "<第2步用户输入的PAT>",
    "TFS_COLLECTION": "<第2步用户选择的集合，选'其他'则使用用户输入值>"
  }
}
```

**第 4 步：提示用户重启 Claude Code**

### wiki-mcp 安装流程（必须）

**第 1 步：执行安装命令**

```bash
python ~/.claude/skills/win-skill-installer/scripts/main.py --mcp wiki-mcp
```

**第 2 步：收集凭据（必须，不可跳过）**

使用 `AskUserQuestion` 向用户询问：
- 问题 1：`"请提供您的 Confluence 个人访问令牌 (Token)："`

> CONFLUENCE_URL 默认为 `https://winwiki.winning.com.cn`

**第 3 步：更新配置**

读取 `~/.claude.json`，将 wiki-mcp 的配置更新为（保留已有的 command 和 args，添加 env）：

```json
"wiki-mcp": {
  "command": "node",
  "args": ["~/.cache/WinCode/mcp/wiki-mcp/dist/index.js"],
  "env": {
    "CONFLUENCE_URL": "https://winwiki.winning.com.cn",
    "CONFLUENCE_TOKEN": "<第2步用户输入的Token>"
  }
}
```

**第 4 步：提示用户重启 Claude Code**

### devops-mcp 安装流程（必须）

**第 1 步：执行安装命令**

```bash
python ~/.claude/skills/win-skill-installer/scripts/main.py --mcp devops-mcp
```

**第 2 步：收集凭据（必须，不可跳过）**

使用 `AskUserQuestion` 向用户询问（一次询问，三个问题）：
- 问题 1：`"请确认 DevOps API 后端地址 (API_OPS_BASE_URL)："`（选项：`http://172.16.7.52:7099/`（推荐）、`其他（手动输入）`）
- 问题 2：`"请确认 COP 部署服务地址 (API_COP_BASE_URL)："`（选项：`http://172.16.9.87:8089/`（推荐）、`其他（手动输入）`）
- 问题 3：`"请提供您的 TFS 个人访问令牌 (TFS_KEY)："`（文本输入，选择 "Other"）

> 两个 URL 均有默认值，用户确认即可；选"其他"则手动输入。
> TFS_KEY 需要在运营平台生成：**运营平台 → 新制品管理 → 持续集成 → TFS工作项 → 设置个人令牌**。请确认用户已获取令牌后再收集。

**第 3 步：更新配置**

读取 `~/.claude.json`，将 devops-mcp 的配置更新为（保留已有的 command 和 args，添加 env）：

```json
"devops-mcp": {
  "command": "node",
  "args": ["~/.cache/WinCode/mcp/devops-mcp/dist/index.js"],
  "env": {
    "API_OPS_BASE_URL": "<第2步用户输入的后端地址，默认 http://172.16.7.52:7099/>",
    "API_COP_BASE_URL": "http://172.16.9.87:8089/",
    "TFS_KEY": "<第2步用户输入的TFS令牌>"
  }
}
```

**第 4 步：提示用户重启 Claude Code**

### 其他 MCP 安装

无特殊凭据要求，直接安装：

```bash
python ~/.claude/skills/win-skill-installer/scripts/main.py --mcp MCP_NAME
```

## 命令参考

### 技能操作
```bash
# 列出所有技能
python ~/.claude/skills/win-skill-installer/scripts/main.py --list

# 搜索技能
python ~/.claude/skills/win-skill-installer/scripts/main.py --search KEYWORD

# 安装技能
python ~/.claude/skills/win-skill-installer/scripts/main.py SKILL_NAME

# 更新缓存
python ~/.claude/skills/win-skill-installer/scripts/main.py --update
```

### MCP 操作
```bash
# 列出可用 MCP
python ~/.claude/skills/win-skill-installer/scripts/main.py --mcp-list

# 搜索 MCP
python ~/.claude/skills/win-skill-installer/scripts/main.py --mcp-search KEYWORD

# 安装 MCP
python ~/.claude/skills/win-skill-installer/scripts/main.py --mcp MCP_NAME

# 列出已安装的 MCP
python ~/.claude/skills/win-skill-installer/scripts/main.py --mcp-installed

# 卸载 MCP
python ~/.claude/skills/win-skill-installer/scripts/main.py --mcp-uninstall MCP_NAME
```

## 交互示例

**安装 MCP：**
```
用户: 安装 tfs-mcp

AI 执行:
$ cd ~/.cache/WinCode/mcp/tfs-mcp && npm install && npm run build
$ # 更新 ~/.claude.json，路径指向缓存目录

安装 MCP: tfs-mcp
  目录: ~/.cache/WinCode/mcp/tfs-mcp
  正在安装依赖...
  [OK] 依赖安装完成
  正在编译...
  [OK] 编译完成
  正在更新配置...
[OK] 已安装 tfs-mcp (使用缓存目录)
```
