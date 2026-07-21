# 常见问题与解决方法

本文档记录需求分析流程中遇到的常见问题及其解决方法。

---

## 目录

1. [阶段0：前置依赖问题](#阶段0前置依赖问题)
2. [阶段4：原型设计问题](#阶段4原型设计问题)
3. [阶段6：TFS上传问题](#阶段6tfs上传问题)
4. [其他问题](#其他问题)

---

## 阶段0：前置依赖问题

### 问题1：TFS 全局配置缺失

**现象**：
```
检测到首次使用 TFS 功能，需要配置认证信息
```

**原因**：
- 全局 TFS 配置文件不存在：`~/.claude/skills/tfs2018-integration/config/tfs-config.json`

**解决方法**：

1. 创建全局配置文件：
```bash
mkdir -p ~/.claude/skills/tfs2018-integration/config
```

2. 创建配置文件并填入 PAT 令牌：
```json
{
  "serverUrl": "http://tfs2018-web.winning.com.cn:8080/tfs/WINNING-6.0",
  "pat": "你的PAT令牌"
}
```

3. 获取 PAT 令牌：
   - 登录 TFS: http://tfs2018-web.winning.com.cn:8080/tfs/
   - 用户头像 → 安全 → +添加 → 个人访问令牌
   - 选择权限：工作项(读取、管理)、代码(读取)
   - 复制生成的令牌

**预防措施**：
- 首次使用 TFS 功能时，自动检测并引导用户配置

---

### 问题2：tfs2018-integration 依赖缺失

**现象**：
```
npm ERR! missing: azure-devops-node-api@*
```

**原因**：
- tfs2018-integration 技能的 node_modules 依赖未安装

**解决方法**：
```bash
cd ~/.claude/skills/tfs2018-integration
npm install
```

**预防措施**：
- 在阶段0前置检查中自动检测依赖
- 若缺失，询问用户是否自动安装

---

### 问题3：TFS 附件上传失败

**现象**：
```
上传附件时提示错误
```

**原因**：
- tfs2018-integration 技能配置缺失或令牌无效
- 文件路径不正确或文件不存在

**解决方法**：

**方法一：验证令牌（推荐）**
```bash
# 验证 TFS 令牌是否有效
node ~/.claude/skills/tfs2018-integration/tools/verify-token.mjs
```

**方法二：使用 tfs-mcp MCP 服务逐个上传附件**
```javascript
// 逐个上传附件（每个文件单独调用）
mcp__tfs-mcp__tfs_upload_attachment({
  id: <工作项ID>,
  filePath: "过程文件/[需求号]/[需求号]_需求设计_01_需求合理性评估报告.md",
  comment: "需求分析过程文档"
})

mcp__tfs-mcp__tfs_upload_attachment({
  id: <工作项ID>,
  filePath: "过程文件/[需求号]/[需求号]_需求设计_02_功能需求.md",
  comment: "需求分析过程文档"
})

mcp__tfs-mcp__tfs_upload_attachment({
  id: <工作项ID>,
  filePath: "过程文件/[需求号]/[需求号]_需求设计_03_原型说明.md",
  comment: "需求分析过程文档"
})

mcp__tfs-mcp__tfs_upload_attachment({
  id: <工作项ID>,
  filePath: "过程文件/[需求号]/[需求号]_需求设计_04_TFS需求分析.md",
  comment: "需求分析过程文档"
})
```

> **注意**：使用 tfs-mcp 的 `tfs_upload_attachment` 工具逐个上传附件，每个文件单独调用一次。

**预防措施**：
- 在阶段6开始前验证 TFS 令牌
- 确保文件路径正确（使用绝对路径）
- 确认文件存在且可读

---

## 阶段4：原型设计问题

### 问题1：Pencil MCP 工具检测失败

**现象**：
```
调用 mcp__pencil__get_editor_state 失败
```

**原因**：
- `mcp__pencil__get_editor_state` 需要先在 VSCode 中打开 .pen 文件才能工作
- 该工具不适合用于检测 Pencil MCP 服务器连接状态

**解决方法**：

使用正确的检测方法：

**方法一：使用脚本检测（推荐）**
```bash
node ~/.claude/skills/std-req-analysis/scripts/check-pencil-mcp.js
```

**检测结果**：
- 返回 0：Pencil 扩展已安装
- 返回 1：Pencil 扩展未安装
- 返回 2：检测失败

**方法二：调用其他 Pencil MCP 工具**
```javascript
try {
  await mcp__pencil__get_style_guide_tags();
  // Pencil MCP 可用
} catch (error) {
  // Pencil MCP 不可用
}
```

**最佳实践**：
- 优先使用 `mcp__pencil__get_style_guide_tags` 检测
- 不依赖打开文件的工具进行检测

---

### 问题2：Pencil .pen 文件保存失败

**现象**：
```
cp: cannot stat 'pencil-new.pen': No such file or directory
```

**原因**：
- Pencil 编辑器在内存中打开新文档，文件尚未保存到磁盘
- .pen 文件在编辑器中是内存状态，需要用户手动保存

**解决方法**：

**正确流程**：
1. 在 Pencil 编辑器中绘制原型
2. 生成原型说明文档和截图
3. 提示用户手动保存 .pen 文件：
```
请手动保存 .pen 文件：
1. 在 Pencil 编辑器中点击 "文件" → "另存为"
2. 保存到：过程文件/[需求号]/prototype/[原型名称].pen
```

**不要尝试**：
- ❌ 使用 `cp` 命令复制文件
- ❌ 使用 PowerShell `Copy-Item` 复制文件
- ❌ 尝试自动保存未保存的内存文件

**最佳实践**：
- 在原型说明文档中说明用户如何保存文件
- 提供明确的保存路径和文件名
- 截图可以自动下载到过程文件目录

---

### 问题3：字体家族无效警告

**现象**：
```
Font family 'Microsoft YaHei' is invalid.
```

**原因**：
- Pencil 工具对字体家族有限制
- 中文字体名称可能不被识别

**解决方法**：

使用通用字体家族：
```javascript
// ❌ 错误：中文字体名称
fontFamily: "Microsoft YaHei"

// ✅ 正确：通用字体家族
fontFamily: "sans-serif"  // 或 "Inter"
```

**可用字体家族**：
- `sans-serif` - 无衬线字体
- `serif` - 衬线字体
- `monospace` - 等宽字体
- `Inter` - 系统默认字体

**注意**：
- 中文内容仍然可以正常显示
- 只是字体名称设置被忽略
- 使用通用字体家族更安全

---

## 阶段6：TFS上传问题

### 问题1：TFS 需求分析字段格式错误

**现象**：
```
TFS 需求分析字段显示原始 Markdown 标记
```

**原因**：
- 使用了错误的工具：`update-demand-analysis.mjs`（直接上传 Markdown）
- TFS 的 `Winning.Demand.Analysis` 字段需要 HTML 格式才能正确渲染

**解决方法**：

使用正确的工具：
```bash
# ✅ 正确：使用 HTML 转换工具
node tools/update-demand-analysis-html.mjs <工作项ID> "<需求分析文档路径>"

# ❌ 错误：直接上传 Markdown
node tools/update-demand-analysis.mjs <工作项ID> "<需求分析文档路径>"
```

**区别**：
- `update-demand-analysis-html.mjs`：将 Markdown 转换为 HTML 后上传
- `update-demand-analysis.mjs`：直接上传 Markdown 原文

**示例**：
```bash
cd ~/.claude/skills/tfs2018-integration
node tools/update-demand-analysis-html.mjs 1445554 "d:\workspace\过程文件\1445554\1445554_需求设计_04_TFS需求分析.md"
```

**最佳实践**：
- 始终使用 `update-demand-analysis-html.mjs`
- 验证上传后的 TFS 字段渲染效果

---

### 问题2：附件批量上传失败

**现象**：
```
批量上传附件时部分文件上传失败
```

**原因**：
- 文件路径不正确或文件不存在
- TFS 令牌权限不足
- 网络连接问题

**解决方法**：

**使用 tfs-mcp MCP 服务逐个上传**
```javascript
// 逐个上传附件（每个文件单独调用）
mcp__tfs-mcp__tfs_upload_attachment({
  id: <工作项ID>,
  filePath: "过程文件/[需求号]/[需求号]_需求设计_01_需求合理性评估报告.md",
  comment: "需求分析过程文档"
})

mcp__tfs-mcp__tfs_upload_attachment({
  id: <工作项ID>,
  filePath: "过程文件/[需求号]/[需求号]_需求设计_02_功能需求.md",
  comment: "需求分析过程文档"
})

mcp__tfs-mcp__tfs_upload_attachment({
  id: <工作项ID>,
  filePath: "过程文件/[需求号]/[需求号]_需求设计_03_原型说明.md",
  comment: "需求分析过程文档"
})

mcp__tfs-mcp__tfs_upload_attachment({
  id: <工作项ID>,
  filePath: "过程文件/[需求号]/[需求号]_需求设计_04_TFS需求分析.md",
  comment: "需求分析过程文档"
})
```

**MCP 服务说明**：
- 使用 `tfs_upload_attachment` 逐个上传文件
- 如文件已存在同名附件，需先手动删除再上传
- 串行上传，避免 TFS 并发限制

**最佳实践**：
- 上传前验证 TFS 令牌
- 使用相对路径（相对于当前工作目录）
- 确认所有文件都已成功上传
- 检查返回的 `failCount` 和 `results` 字段

---

## 其他问题

### 问题1：目录命名规则混淆

**现象**：
```
文件名不包含需求号前缀，如 "需求设计_01_需求合理性评估报告.md"
```

**原因**：
- 未遵循新的文件命名规范
- 文件名应包含需求号前缀

**解决方法**：

**正确的目录和文件命名**：
```
过程文件/
└── 1445554/              ← 目录名使用需求号
    ├── 1445554_需求设计_01_需求合理性评估报告.md  ← 文件名包含需求号
    ├── 1445554_需求设计_02_功能需求.md
    ├── 1445554_需求设计_03_原型说明.md
    └── 1445554_需求设计_04_TFS需求分析.md
```

**命名规则**：
- 目录名：使用 TFS 工作项 ID（如 `1445554`）或年月日（如 `20260228`）
- 文件名：必须包含需求号前缀，如 `[需求号]_需求设计_01_需求合理性评估报告.md`

**最佳实践**：
- 创建目录时使用 `mkdir -p "过程文件/[需求号]"`
- 生成文件时使用带前缀的文件名，如 `1445554_需求设计_01_需求合理性评估报告.md` 或 `20260228_需求设计_01_...`

---

### 问题2：页面布局不是 ASCII 字符画

**现象**：
```
功能需求文档中的页面布局使用普通文字描述，而不是 ASCII 字符画方框图
```

**原因**：
- 未按照模板要求生成 ASCII 字符画

**解决方法**：

**正确的页面布局示例**：
```
┌─────────────────────────────────────────────────────────┐
│ 医疗组管理 - 成员变化                                  │
├─────────────────────────────────────────────────────────┤
│ 查询条件                                               │
│ ┌───────────────────────────────────────────────────┐ │
│ │ 医疗组：[普通外科一病区医疗组]                     │ │
│ │ 时间段：[2025-01-01] 至 [2025-01-31]              │ │
│ │ [查询]  [重置]                                    │ │
│ └───────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

**使用字符**：
- 框线：`┌ ┬ ┐ ├ ┼ ┤ └ ┴ ┘ ─ │`
- 文字：使用中文或英文

**最佳实践**：
- 参考 [workflow-guide.md](workflow-guide.md) 中的页面布局示例
- 使用代码块包裹 ASCII 字符画
- 确保对齐和可读性

---

### 问题3：优先级划分不正确

**现象**：
```
功能需求未按 MoSCoW 方法划分优先级，或优先级标识不正确
```

**原因**：
- 未按照 MoSCoW 方法划分优先级
- 优先级标识不统一

**解决方法**：

**正确的优先级划分（MoSCoW）**：
- **P0** Must have：必须有
- **P1** Should have：重要但不紧急
- **P2** Could have：锦上添花
- **P3** Won't have：本期不做

**示例**：
```markdown
### 功能需求

#### 4.1 P0 必须实现

**功能1**: 成员变化查询（P0）
- 优先级：P0
- 功能描述：...

#### 4.2 P1 重要但不紧急

**功能2**: 数据导出（P1）
- 优先级：P1
- 功能描述：...
```

**最佳实践**：
- 每个功能必须标注优先级（P0/P1/P2/P3）
- 按优先级分组展示（P0、P1、P2、P3）
- 使用统一的优先级标识

---

## 预防措施总结

### 阶段0前置检查清单

在开始需求分析前，执行以下检查：

```bash
# 1. 检查 TFS 全局配置
if [ ! -f ~/.claude/skills/tfs2018-integration/config/tfs-config.json ]; then
  echo "⚠️  TFS 配置缺失，需要配置"
  # 询问用户是否配置
fi

# 2. 检查 tfs2018-integration 依赖
cd ~/.claude/skills/tfs2018-integration
if ! npm list azure-devops-node-api > /dev/null 2>&1; then
  echo "⚠️  TFS 依赖缺失，需要安装"
  # 询问用户是否安装
fi

# 3. 验证 TFS 令牌
node tools/verify-token.mjs
case $? in
  0) echo "✓ TFS 令牌有效" ;;
  1) echo "⚠️  TFS 令牌无效" ;;
  2) echo "⚠️  TFS 配置缺失" ;;
esac

# 4. 检查 Pencil 扩展（通过 MCP 工具检测）
# 直接调用 mcp__pencil__get_style_guide_tags 进行检测
```

### 阶段4原型设计注意事项

1. **检测方法**：优先使用 `mcp__pencil__get_style_guide_tags` 检测
2. **文件保存**：提示用户手动保存 .pen 文件，不尝试自动保存
3. **字体选择**：使用通用字体家族（sans-serif、Inter）
4. **选项说明**：明确说明 A/B 选项的优缺点

### 阶段6 TFS 上传注意事项

1. **令牌验证**：上传前使用 `verify-token.mjs` 验证令牌
2. **格式转换**：使用 `update-demand-analysis-html.mjs` 转换为 HTML
3. **批量上传**：使用 **mcp-tfs-upload MCP 服务**的 `upload_attachments` 工具
4. **验证结果**：检查 MCP 服务返回的上传结果（successCount、failCount、results）
5. **禁止混用**：不要同时使用 MCP 服务和 tfs2018-integration 脚本上传

---

## 联系支持

如果遇到本文档未记录的问题，请：

1. 检查 [workflow-guide.md](workflow-guide.md) 详细流程说明
2. 查看 [technical-specs.md](technical-specs.md) 技术规范
3. 参考 [exception-handling.md](exception-handling.md) 异常处理指南
