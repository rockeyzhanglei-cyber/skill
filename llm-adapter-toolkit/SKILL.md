---
title: "llm-adapter-toolkit"
summary: "在确定性/规则引擎流水线中接入可选大模型 Agent 的适配层模式，以及 GitHub 推送 workflow 文件的作用域坑"
description: >
  当用户的任务里有一部分无法固化为规则（如多样式文档解析、差异语义兜底），需要把大模型 Agent
  作为「可选增强」接入已有确定性管线时使用本模式。核心：平台无关核心 + 可切换外壳
  (disabled/http/cli/mock)，默认 disabled 以兑现「零 API Key」承诺。
  同时记录 GitHub 推送含 .github/workflows 的提交需要 workflow scope 令牌的硬性限制。
read_when:
  - 给纯规则/零 LLM 的工具加可选的 AI 增强
  - 需要支持 OpenAI 兼容 / 本地 CLI(codex, claude) / Mock 多种后端
  - 推送包含 GitHub Actions workflow 的提交被拒（missing workflow scope）
---

# 可选 LLM 适配层模式（一核多壳）

## 何时用
- 现有引擎是纯确定性脚本（subprocess 调用），但某些环节（文档解析、语义判读）格式太杂、无法规则化。
- 用户只提供「解析说明 / 领域说明」，具体解析交给大模型 Agent。
- 产品对外承诺「零 API Key、免联网」——所以 LLM 必须是**可选**，默认关闭。

## 架构（平台无关核心 + 可替换外壳）
1. **配置对象**：`LLMConfig(enabled, backend, base_url, api_key, model, cli_command, timeout)`。
   - `backend` 取值：`disabled`(默认) / `http`(OpenAI 兼容) / `cli`(本地命令行 Agent) / `mock`(自测占位)。
   - 读取自 `llm_config.json`，**必须写进 .gitignore**（含 api_key）。
2. **核心协议（与具体后端无关）**：
   - `parse_docx(doc_input, spec)` / `semantic_fallback(diff_input, spec)` —— `doc_input` 可为 **docx 文件路径**或已提取文本；`diff_input` 可为**产物目录路径**或差异文本。
   - **cli 模式传路径、http 模式才塞文本**：当 `backend=="cli"` 且输入是真实文件/目录时，只把**路径**注入 prompt（由本机 Agent 用工具自读），**绝不提前 `extract_docx_text` 全文**；仅 http/mock 模式才提取文本塞入（且标注上下文上限）。这是破除大文档上下文限制的关键，务必守住。
   - 两者都注入**用户的解析说明 spec** + 固定输出模板，要求模型输出结构化结果（如 `table_structure.md`）；`semantic_fallback` 产出标注「需人工复核」的结果。
3. **后端分发**：`LLMAgent(config).available` 决定是否能调；`call(prompt)` 按 backend 路由：
   - `disabled` → 抛/记「未启用」。
   - `http` → `requests.post(base_url, headers={Authorization: Bearer api_key}, json={model, messages})`。
   - `cli` → 本地 codex/claude/codebuddy，不经网络。`cli_command` 是模板，支持 `{file}`（文档/目录路径）与 `{prompt}`（说明）占位符，如 `codex -q "读取文件 {file}，按以下说明解析：{prompt}"` / `claude -p "读取文件 {file}，按以下说明解析：{prompt}"` / `codebuddy -p -y --model {model} "读取文件 {file}，按以下说明解析：{prompt}"`（{model} 默认 auto，可指定 hy3/glm-5.2/deepseek-v4-pro 等具体 ID）。本机 Agent 自行分块读、跑脚本、多步推理。
  - **命令行切分必须按平台区分（关键坑）**：`sys.platform == "win32"` 时用 `subprocess.run(cmd_str, shell=True)`，其余用 `subprocess.run(shlex.split(cmd_str))`。原因：① shlex 把反斜杠当转义符，Windows 路径 `C:\...\codebuddy.cmd` 会被拆坏；② codebuddy 在 Windows 多为 `.cmd`，无 shell 时 CreateProcess 无法直接运行 `.cmd/.bat`，必须经 `cmd.exe`（shell=True）。`shell=True` 时命令是整条字符串交给 cmd.exe 解析（路径含空格已由双引号保护）。`_cli_version` 对 `.cmd/.bat` 同样需 `shell=True`。
   - `mock` → 返回固定占位文本，供端到端自测（无需真 Key）。
4. **引擎接入点**：确定性脚本先跑；仅在「失败（如解析出 0 表）/ 用户强制勾选」时委托 Agent。Agent 产物与确定性产物并列归集，UI 明确标注「模型辅助」。

## 关键约定（避免返工）
- 默认 `disabled` → 不碰任何外部网络、不读 Key，兑现零 Key 承诺。
- `api_key` 在 GET 设置接口里**脱敏**（如 `***`），PUT/POST-test 时若传入为 `""` 或 `***`（脱敏占位=前端未改），**后端保留已保存真实 key**（`cfg = LLMConfig.load(); if api_key in ('','***'): api_key = cfg.api_key`）——否则「自动保存」会把 key 覆盖成字面量 `***`。前端也要在 api_key 未编辑时把字段置空（不发送 `***`）。
- Mock 后端让「接线是否正确」可在无 Key 环境完整验证（`py_compile` + `TestClient` 命中路由 + 调 mock）。
- 输出模板与下游比对引擎严格对齐（如 `table_structure_template.md`），模型只是填模板。

## cli 后端必须传文件路径，而非全文（关键坑）
- **现象**：若把整个 docx 提取成纯文本（几万字符）塞进 `codex -q "{prompt}"`，本地 Agent 也撞上下文窗；且纯文本问答浪费了 Agent 的工具/代码能力。
- **正确姿势**：`cli_command` 模板用 `{file}` 占位符，`parse_docx` 在 cli 模式只传**文件路径**（不把正文塞进 prompt）。细节：docx 先 `extract_docx_text` 抽成**临时 .md** 再把该 .md 路径交给 Agent（仍是传路径、不内联正文）——这样 codex/codebuddy 读到的是纯文本、规避其对 docx 解析不稳的问题，同时上下文限制仍在工具台侧被破除。本机 Agent 用文件读取工具自行打开、分块、多步推理。
- **验证方法**（无 Key）：`LLMConfig(backend="cli", cli_command='echo "FILE={file}||PROMPT={prompt}"')` 调 `parse_docx(path, spec)`，确认 stdout 含 `FILE=<路径>` 且**不含 docx 任何实际正文**（用 docx 独有段落断言 `not in prompt`）。
- **http 后端局限**：纯模型 API 无工具读文件，只能塞文本，存在上下文上限；明确留给「小文档/纯模型」场景，大文档一律用 cli。

## 智能体自动检测（面向非开发人员的极简配置）
- **CLI 智能体才可直接调用**：`codex` / `claude`(Claude Code) / `gemini` / `codebuddy`(WorkBuddy 内置) 有命令行，后端可在后台 `subprocess` 调起并拿回结果——是真正可用的「壳」。检测用 `shutil.which(bin)` + `bin --version` 取版本。
- **WorkBuddy 其实可无头调用（重要修正）**：WorkBuddy 桌面端 app 内部自带命令行 `codebuddy`（前身 CodeBuddy），支持 `-p/--print` 非交互输出、**复用桌面端登录态（无需额外 Key）**。macOS 路径 `/Applications/WorkBuddy.app/Contents/Resources/app.asar.unpacked/cli/bin/codebuddy`，**默认不在 PATH 中**。关键坑：
  - 检测时用绝对路径，并把 `cli_command` 模板里的裸 `codebuddy` **替换为该绝对路径**，否则 `subprocess.run` 报 `FileNotFoundError`（裸命令不在 PATH）。
  - 调用模板：`codebuddy -p -y --model auto "读取文件 {file}，按以下说明解析：{prompt}"`。其中 **`-y`（= `--permission-mode bypassPermissions`）非交互读文件必填**——否则无头模式弹不出权限确认，`Read`/`Bash` 工具被拒（提示改用 `-y`）。
  - 已实测：无头返回、复用登录态、直接读磁盘文件（破除上下文限制）、解析 docx 走「抽 md→传路径」正常。
- **GUI 客户端仍不可直接调用**：Claude App / Codex App / Cursor 是纯图形界面，没有 headless 调用入口，后端无法"喂文件→拿结果"。检测用平台路径仅做"已安装"提示，标 `callable=False` + "需 MCP 接入（规划中）"。**不要把这类 GUI 当可勾选的执行后端**。WorkBuddy 已从该列表移除（改用 codebuddy CLI）。
- **落地形态（CC Switch 卡片式）**：设置页进入即 `GET /api/settings/detect` 自动探测 → 每个智能体一张卡片，**开关 + 模型下拉框 + 测试按钮 + 高级自定义命令聚合在同一块**，打开卡片开关即启用并自动保存（**不要底部独立「保存」按钮**，改动即时落盘）。GUI 灰显不可选；无 CLI 时给「API 接口模式（需 Key）」卡片。模型选择用**下拉框**而非文本框——见下方「模型自动识别」。
- **模型自动识别（下拉框，不要让人手填模型名）**：`detect_agents()` 给每个 CLI 智能体返回 `models` 列表，前端 `models` 非空渲染 `<select>`、为空退化为文本框。
  - **codebuddy：从本机真实二进制解析**，最准——拉起 `codebuddy --help`，正则提取 `--model` 帮助行里的 `Currently supported: (auto, hy3, glm-5.2, ...)`。`_codebuddy_models(binary)` 用模块级 `_MODEL_CACHE` 缓存（同一二进制只解析一次）。解析失败回退到静态通用列表。
  - codex/claude/gemini：给静态 `default_models`（常用模型家族），用户也能在高级自定义命令里改。
  - 这样「大部分人不知道模型叫什么」的问题靠下拉框解决；`{model}` 占位符注入 `--model`，留空回落 `auto`。
- **检测范围提醒**：检测发生在"运行后端的机器"。本地 `./start.sh` 检测用户本机；Docker 容器内则检测容器内，需在镜像装 CLI 才能识别。app 内部 CLI（如 codebuddy）按平台回退检测（`app_cli_paths` + Windows 动态枚举）。
- **跨平台检测（按 sys.platform 自动识别）**：
  - macOS：PATH 或 `/Applications/WorkBuddy.app/.../cli/bin/codebuddy` 回退；codex/claude/gemini 走 PATH。
  - **Windows**：PATH（`where`/`shutil.which` 对 `.cmd/.exe` 生效）**或**动态枚举 WorkBuddy 内置 `codebuddy`——`LOCALAPPDATA`/`ProgramFiles` 等基目录 + `Programs` 子目录 + 应用名(`WorkBuddy`/`CodeBuddy`/...) + `resources/app.asar.unpacked/cli/bin/codebuddy(.cmd/.exe)`。`app_cli_paths["win32"]` 留空，由 `_win32_codebuddy_candidates()` 按环境变量枚举（安装目录不固定，不要硬编码单一路径）。
  - Linux：PATH 或 `/opt/WorkBuddy/...` / `~/WorkBuddy/...` 回退。
  - **绝对路径判断必须用 `os.path.isabs(path)`**，**不能**用 `"/" in path`：Windows 路径是反斜杠，会被漏判，导致 app 内部 CLI 的绝对路径没被注入 `cli_command`（裸命令在 PATH 找不到 → `FileNotFoundError`）。
  - 解析到绝对路径时，把模板里的裸命令名替换为绝对路径；**路径含空格时加双引号**（POSIX 由 shlex 识别、Windows 由 cmd.exe 识别），否则带空格路径会被拆成多段。

## GitHub 推送 workflow 文件的硬限制（坑）
- 规则：推送**任何包含 `.github/workflows/*` 的提交**时，所用令牌必须具备 workflow 写权限。
  - **只能用工 classic PAT 勾选 `workflow` scope**（或 `repo` 全量包含 workflow）。这是唯一可行路径。
  - ⚠️ **fine-grained PAT 不行**：即使给它 Workflows: Read and write，GitHub 也不允许用 fine-grained 令牌创建/更新 workflow 文件（官方限制，错误同为 `refusing to allow ... without workflow scope`）。别在 fine-grained 上浪费时间，直接用 classic PAT。
  - 否则整笔 push 被拒：`refusing to allow a Personal Access Token to create or update workflow '.github/workflows/...' without 'workflow' scope`。
- 现象：本地 commit 成功，但 `git push` 报上述错 → 不是网络问题，是 scope 不够。
- 处理套路（不阻塞功能交付）：
  1. 把 workflow 文件摘到**独立本地分支**（如 `ci/ghcr`），`git rm` 后 `git commit --amend` 让 main 不含 workflow。
  2. 用现有（缺 scope）令牌推 `main`（功能代码，成功）。
  3. 告知用户：生成带 `workflow` scope 的令牌后，`git push origin ci/ghcr` 并合并到 main 即触发 CI。
- 提醒：macOS 钥匙串 PAT 在非交互 shell 下偶尔锁（`errSecNotAvailable 100001`），需用户批准弹窗；且沙箱到 github.com 网络可能间歇性不通（LibreSSL SSL_connect 失败），推送失败先重试 2-3 次再判定为 scope 问题。

## 自测清单
- [ ] `py_compile` 全过
- [ ] 默认 `disabled` 下不发起任何网络请求
- [ ] `TestClient` 命中设置/工具路由，确认新选项与阶段已注册
- [ ] mock 后端能跑通解析/语义兜底接线（无需真 Key）
- [ ] 推送前确认 main 不含 `.github/workflows`（除非令牌有 workflow scope）
