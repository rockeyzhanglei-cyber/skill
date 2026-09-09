---
name: data-model-compare
description: 数据模型比对，确保原标准数据无损传输到目标标准，自动生成修订建议。触发：数据模型比对、标准比对、数据标准比对、模型比对、比对这个文档、对比两个标准、对照两份标准、标准差异分析、diff两个标准、无损传输、数据上传、标准覆盖、值域比对、值域修订、代码表比对、标准迁移、标准升级、版本差异、两份标准、比对报告、自验证、核验比对结果、验证一下结果、自动验证、自动修复、生成Excel、人工核对、逐表核对。不触发：纯数据模型修订用 data-model-revision，生成DDL用 reg-ddl-generator。
version: 2.0.0
agent_created: true
author: WinAi
tags: [数据标准, 模型比对, 数据迁移, 值域修订]
keywords: 数据模型比对 标准比对 数据标准比对 模型比对 对比两个标准 对照两份标准 比对这个文档 值域比对 代码表比对 无损传输 标准迁移 标准升级 版本差异 两份标准 比对报告 diff两个标准 标准差异分析 标准覆盖 值域修订 自验证 核验比对结果 人工核对 生成Excel
---

# 数据模型比对

## 职责分层（先读）

**解析阶段没有程序；比对阶段才用程序。**

| 阶段 | 谁做 | 说明 |
|---|---|---|
| 读原始标准（docx/doc/xlsx/pdf）→ 规范化 MD/JSON | **模型** | 按 [references/doc_parse_spec.md](references/doc_parse_spec.md) 执行：该文件是**输出契约**，规定了规范化 MD 的语法、唯一可用的列名集合、每列取值规范、交付前 9 项自检 |
| 规范化 MD/JSON → 内部结构 | 程序 | 按契约**确定性装载**，不做任何文档格式猜测 |
| 字段匹配 / 约束与长度保护 / 值域覆盖 / 报告 | 程序 | 本 SKILL 的主体能力 |

> **两条硬约束**
> 1. **禁止**为适配某份文档的表头去改 `parsers/standard_parser.py` 的列名判定逻辑；
>    遇到新表头 → 改 `doc_parse_spec.md` 的别名表，由模型在解析时归一化。
> 2. **禁止**写"自动提取标准文档"的脚本——解析是模型的活。
>    `parsers/converter.py` 属于**遗留兼容路径**（docx/xlsx/pdf → MD 的机械转换），
>    主流程不再依赖它理解文档格式。

**标准执行顺序**

1. 模型读原始标准 → 产出 `temp/normalized/source_*.md` 与 `target_*.md`；
2. 模型按规范第 6 节做 9 项自检，并把结论写进对话；
3. 自检通过后再跑下面的命令（输入是**规范化 MD**，不是原始 docx）；
4. 程序解析出 0 表 / 字段数异常 → 回到第 1 步修规范化文件，不许带病比对。

## 执行方式（唯一入口）

**直接运行脚本，不要自己写代码。** 输入是**模型按解析说明产出的规范化 MD**：

```bash
python3 <skill_root>/main.py \
  --source <temp/normalized/source_xxx.md> \
  --target <temp/normalized/target_xxx.md> \
  --title <报告标题>
```

**多文件比对：**
```bash
python3 <skill_root>/main.py \
  --source <source_1.md> <source_2.md> \
  --target <target_xxx.md>
```

**参数说明：**
| 参数 | 说明 | 必填 |
|------|------|------|
| `-s, --source` | 原标准文件路径（支持多个） | 是 |
| `-t, --target` | 目标标准文件路径 | 是 |
| `--title` | 报告标题 | 否 |
| `-c, --config` | 配置文件路径 | 否 |
| `-f, --feedback` | 用户编辑后的 Excel：**只读分析并输出知识库写入指令**，不自动回写（回写由模型按模式四执行；给出此参数时分析完即退出，不继续比对） | 否 |

**推荐输入：** `.md`（规范化 MD，主路径，程序只做契约装载）
**遗留兼容：** `.docx` `.xlsx` `.pdf`（由 `parsers/converter.py` 转 MD，仅在确无必要人工规范化时使用；
`.doc` 不可用——macOS 下转换必丢表格，须先请人另存为 `.docx`）

脚本会自动执行：
1. ~~格式转换~~（输入为规范化 MD 时此步仅复制文件；输入为 docx/xlsx/pdf 时才走遗留转换）
2. 标准化装载（规范化 MD → 表结构/字段/值域 JSON）
3. 比对（字段匹配 + 约束检查 + 值域覆盖）
4. 两个独立维度的补充比对：
   - 值域字典（代码表）比对：解析双方向域字典，按标准号/规范化名称配对，计算代码覆盖率（完全覆盖/部分覆盖/仅目标有/仅源有），输出 `value_domain_report.md`
   - 自验证（漏配/误匹配体检）：无需人工触发，自动检测"本应匹配却判为新增"的漏配候选（同名源字段，建议补映射）与"模糊命中但核心概念不一致"的误匹配候选（建议人工复核），输出 `self_validation_report.md`，驱动知识库"越积越准"
5. 生成报告（MD + HTML）
6. 生成可编辑的Excel文件（用于人工核对；确认后回写知识库，P0 已实现跨表全局复用）

**输出目录：** `<输出根目录>/<任务名>/reports/`
（输出根目录取值优先级：环境变量 `DATA_STD_OUTPUT` > `config.yaml` 的 `workspace.root` > 默认 `~/data-model-compare-docs`）

**输出报告内容：**
- **HTML报告**：汇总统计 + 目录导航 + 逐表详情 + 颜色标识（🟢满足 🟠需修改 🔴需新增）
- **MD报告**：汇总统计 + 目录（带锚点）+ 逐表详情

**端到端示例：**

```bash
python3 <skill_root>/main.py \
  --source "<任务目录>/temp/normalized/source_区域平台V6.0医疗服务.md" \
  --target "<任务目录>/temp/normalized/target_山东电子病历2018V1.4.md" \
  --title "区域平台V6.0医疗服务_vs_山东电子病历2018V1.4"
```

输出到 `<输出根目录>/<任务名>/reports/`，含 `compare_report.html` 和 `compare_report.md`，
报告中显示满足/需修改/需新增的字段数与需新增的表数。

## 环境检查（首次使用先跑）

```bash
python3 <skill_root>/scripts/check_environment.py
```

输出 `ready / partial / needs_setup`：ready 直接开始；partial 标注受影响功能继续；
needs_setup 按 [references/setup-guide.md](references/setup-guide.md) 只补缺失项。
依赖清单见 [skill-dependencies.json](skill-dependencies.json)，
依赖与降级细节见 [references/install.md](references/install.md)。

## 核心原则（6条红线）

脚本已内置以下原则，这些规则在代码中强制执行：

1. **覆盖原则**：原标准必须覆盖目标标准的所有字段
2. **约束保护**：目标必填(M) → 原标准必须必填(M)；目标可选(O) → 原标准M/C/O均可
3. **长度保护**：原标准字段长度 ≥ 目标标准字段长度
4. **值域覆盖**：原标准值域必须覆盖目标标准，只能扩充，不能修改已有值
5. **只增不减**：不删除、不重命名原标准已有字段
6. **人工确认不被静默否决**：知识库里的正向映射是人工领域判断，人是权威。
   匹配期只能"检测并登记可疑"，不能用启发式规则悄悄推翻它
   （理论依据与知识库体检入口见 [references/kb_health.md](references/kb_health.md)）。

## 四种工作模式

> **模式前置**：进入任一模式前，先由模型按
> [references/doc_parse_spec.md](references/doc_parse_spec.md) 把原始标准解析为规范化 MD，
> 并通过该规范第 6 节的 9 项自检；自检未通过不要进入下面的流程。

根据用户的意图自动选择工作模式：

### 模式一：比对模式（默认）

**触发方式**：用户提供两套标准文档要求比对

**流程**：运行比对脚本 → 自动生成报告 → **自动进入自验证流程（3轮）** → 输出汇总报告 → 等用户确认 → 执行修复

这是最常用的模式。比对完成后不等用户指示，自动开始3轮自验证。3轮全部跑完后，输出一份汇总问题报告和解决方案，等用户确认后再执行修改。

### 模式二：测试模式

**触发方式**：用户说"测试这个skill"、"用这套标准测试"、"测试比对"等

**流程**：运行比对脚本 → **自验证流程（3轮）** → 输出测试总结报告 → 等用户确认 → 执行修复

与模式一的区别：用户的目的不是要比对结果，而是验证 skill 本身的质量。自验证结束后，输出测试总结，包括每种匹配类型的通过率、发现的问题数、解决方案。

### 模式三：验证模式

**触发方式**：比对任务完成后，用户说"验证一下结果"、"核验比对结果"、"自验证"等

**流程**：读取已有的比对结果 → **自验证流程（1轮，除非发现问题）** → 有问题则输出报告等确认

用于对已有结果进行抽查核验。默认只做1轮；如果发现错误，输出问题报告等用户确认。

### 模式四：人工核对模式

**触发方式**：用户说"人工核对"、"逐表核对"、"我来核对"、"生成Excel"等

**流程**：
1. 运行比对脚本，自动生成HTML报告、MD报告和可编辑的Excel文件
2. 用户打开Excel文件进行编辑：
   - 源表列（H列）：从下拉框选择原标准中的表
   - 源字段列（I列）：从下拉框选择对应表的字段（级联下拉）
   - 条件格式自动显示颜色：绿色=已匹配，红色=需新增
   - 全表新增的表所有行显示红色背景
3. 用户编辑完成后，将Excel文件保存到原位置（或告诉skill文件路径）
4. **模型读取修改后的 Excel**（`scripts/read_modified_excel.py` 负责读出修改行清单），
   逐条与原始比对结果对比找出差异
5. **模型把差异写入知识库**（这是模型的活，不走脚本自动回写）：
   - 用户修改了源表/源字段映射 → 更新 `knowledge_base/field_mappings.yaml`
   - 用户清空了源字段（表示不应匹配）→ 在 `knowledge_base/field_synonyms.yaml` 对应条目加 `exclude`
   - 用户新增了映射关系 → 添加到 `knowledge_base/field_mappings.yaml`
6. 重新运行比对脚本，确保下次生成结果与用户修改一致

**Excel格式说明**：
- 列：序号、目标表名、目标字段、类型/长度/约束、说明、值域、比对结果、对应源表★、对应源字段★
- 源表和源字段列有下拉框，可从原标准中选择（级联下拉）
- 条件格式：绿色=已匹配（源表和源字段都有值），红色=需新增（源表有值但源字段为空）
- 全表新增的表所有行显示红色背景
- 字体：Times New Roman，12号；行高：最小25，根据说明列内容自动撑开

**重要**：用户修改后的映射必须写入知识库永久保存，下次重新生成时保持一致。

---

## 运行模式：确认模式 vs 自动模式

所有工作模式都支持两种运行模式，通过开关控制：

### 确认模式（默认）

**特征**：每轮验证只收集问题，不修复。3轮全部跑完后，输出一份**汇总问题报告和解决方案**，等用户确认后再统一修复。

**流程**：
```
第1轮验证（只记录问题）→ 第2轮验证（只记录问题）→ 第3轮验证（只记录问题）
→ 输出汇总报告（所有问题 + 每个问题的解决方案）
→ 等用户确认
→ 用户说"可以"后，统一执行修复
→ 修复后重新运行比对 → 再跑3轮验证确认修复有效
```

**为什么这样设计**：3轮验证过程中如果边验边改，后面的轮次可能因为前面的修改而产生不同的结果，导致问题相互交织、难以追踪。先全部跑完、统一汇总、确认后再改，能保持验证过程的纯净性，用户也能一次性看到全貌。

### 自动模式

**触发方式**：用户说"自动验证"、"自动修复"、"不用确认"、"全自动"等

**特征**：跳过人工确认步骤。验证发现问题 → 直接修复 → 重新验证 → 再修复，全自动循环直到没有新问题。

**流程**：
```
第1轮验证 → 发现问题 → 直接修复 → 重新运行比对
→ 第2轮验证 → 发现问题 → 直接修复 → 重新运行比对
→ 第3轮验证 → 没有新问题 → 完成
（如果第3轮还有问题，继续循环直到干净）
```

**适用场景**：批量测试 skill（跑几百上千次）、迭代优化阶段、用户不在电脑前时让 skill 自己改进自己。

**注意**：自动模式下 skill 会自行修改知识库和配置，但**不会修改代码**（修改代码仍需遵循"程序修改规范"，需要用户确认）。

---

## 自验证流程

三种模式的核心都是自验证流程。区别仅在于：模式一和模式二固定跑3轮，模式三默认1轮（发现问题才循环）。运行模式（确认/自动）决定发现问题后的处理方式。

**修复入口（统一）：** 自验证发现的所有问题，修复时一律通过 `/skill-creator` 执行。不直接编辑 skill 文件——skill-creator 会走完整的分析→方案→实施→验证流程，确保修复安全可追溯。

**自验证每轮做两步：**

1. **分层抽样**：读取 `compare_result.json`，按匹配类型分组抽样，确保每种匹配策略有代表性样本。模糊匹配类型多抽，精确匹配少抽。
2. **逐条深度核验**：对每个抽样条目溯源到原始文档，收集源标准原文、目标标准原文、结构化解析结果、比对决策记录、知识库等完整上下文，判断匹配是否正确（matched/modified/new_fields/new_tables 四类核验标准）。

**确认模式**（默认）：3轮全部跑完后汇总所有问题输出报告，等用户确认后通过 `/skill-creator` 统一修复，再重跑比对+3轮验证确认修复有效。
**自动模式**：跳过人工确认，验证→`/skill-creator`修复→验证全自动循环，最多5轮。只改知识库和配置，不改代码。

> **⚠️ 执行自验证流程前必读**：[references/self_validation_detail.md](references/self_validation_detail.md)
> 含分层抽样表（各 match_type 的抽样数与核验重点）、核验判断标准、3轮具体安排、汇总报告格式、核验记录格式。

## 程序修改规范（强制）

**核心原则：不得擅自修改已验证通过的程序**

在执行任务过程中发现程序有问题时，必须遵循以下流程：

1. **停止修改**：发现程序问题时，立即停止直接修改代码
2. **分析问题**：详细分析问题原因和影响范围
3. **提出方案**：梳理修改方案（问题描述、具体改哪些代码、为什么、预期效果、潜在风险）
4. **用户确认**：等待用户确认方案可行后，再执行修改
5. **验证回归**：修改完成后，按 [references/testing_and_regression.md](references/testing_and_regression.md) 跑三套守卫，验证原有功能未被破坏

**禁止行为：**
- ❌ 发现问题直接修改程序（可能导致好的功能被改坏）
- ❌ 未经验证就提交修改
- ❌ 只修改不说明原因

## 配置文件

配置文件位于：`<skill_root>/config.yaml`

可配置项：
- 输出根目录（workspace.root；**环境变量 `DATA_STD_OUTPUT` 优先于本配置**，换机器无需改文件）
- 标准版本检测路径（standard_versions；同样支持环境变量 `DATA_STD_V5_PATHS` / `DATA_STD_V6_PATHS` 覆盖）
- 字段匹配优先级（field_matching.match_priority）
- 约束保护规则（constraint_protection.rules）
- 值域匹配策略（value_domain_matching.strategy）
- 质量验证参数（quality_validation）

## 常见问题

### Q1: PDF 标准怎么解析？

**当前做法（新架构）**：PDF 由**模型直接阅读**，并按
[doc_parse_spec.md](references/doc_parse_spec.md) 产出规范化 MD；扫描版需先 OCR，
人工复核后再进入比对。

> **遗留说明（旧路径，已不推荐，保留备查）**：
> 曾可「切换解析器：在 config.yaml 中修改 `parsers.pdf.primary`（marker / pymupdf4llm / pdfplumber）」。
> ⚠️ 当前 `config.yaml` 中**已无 `parsers` 配置段**，该配置不再生效。
> 另：确保 PDF 是文字版而非扫描版；产出 MD 后需人工核对表格是否串行/串列。

### Q2: 如何添加新的同义词到词库？
编辑 `knowledge_base/field_synonyms.yaml`，添加映射：
```yaml
field_synonyms:
  档案号:
    synonyms: [病案号, 住院号, local_id]
```

### Q3: 跨表关联匹配不到怎么办？

表关联关系按**标准来源分文件**存放，目录是 `knowledge_base/relations/`：

```
knowledge_base/relations/
├── generic.yaml              # 通用表关联
└── source_yunnan_v5.5.yaml   # 按源标准单独维护的关联
```

在对应文件里添加关联关系：

```yaml
relations:
  患者基本信息:
    related_tables:
      - table: 门诊挂号
        key: local_id
        type: "1:N"
```

## 错误处理指南

**1. 文件不存在**
```
✗ 错误: 文件不存在 - /path/to/file.docx
```
解决：检查文件路径是否正确，确保文件存在。

**2. 格式转换失败**
```
✗ 原标准转换失败: cannot import name 'Document' from 'docx'
```
解决：安装缺失的依赖 `pip install python-docx pandas openpyxl`（完整依赖见
[references/install.md](references/install.md)，或跑 `scripts/check_environment.py` 自检）。

**3. 解析失败**
```
✗ 原标准解析失败: Invalid markdown table format
```
解决：检查生成的 MD 文件是否包含有效的表格格式。

**4. 比对失败**
```
✗ 比对失败: source_doc is None
```
解决：检查解析步骤是否成功生成了 JSON 文件。

**5. 报告生成失败**
```
✗ HTML报告生成失败: Template not found
```
解决：检查 `reporters/templates/default_template.yaml` 是否存在。

**6. 解析出 0 表 / 0 字段（新路径最常见）**
```
✓ 原标准：0 张表，0 个字段
✗ 问题: 原标准 未解析出任何表
→ 策略: 继续执行（on_failure=warn）
```
原因：规范化 MD 的**列名不在规范列名集合内**（如 `数据元标识`、`标识符`、`填报要求`），
程序整表丢弃。

解决（按顺序排查）：
1. 对照 [doc_parse_spec.md §3.3](references/doc_parse_spec.md) 的规范列名集合，把列名归一化
   （`数据元标识`/`标识符`→`数据元标识符`、`名称`→`数据元名称`、`数据长度`→`表示格式`、
   `填报要求`→`约束`）；
2. 约束列取值"是"必须写成 `M`；
3. 每张表是否有 `#` 标题、表头行后是否紧跟 `| --- |` 分隔行；
4. 修完**重新解析确认表数/字段数正常**再跑比对——不要带病继续。

> ⚠️ 注意：当前质量验证策略是 `warn`，0 表也会继续跑完并产出"看起来完整"的空报告。
> 看到「0 张表」请立即中止，不要采信后续报告。

## 扩展点

如需扩展 Skill 功能：
- ~~**添加新解析器**：在 `parsers/` 下继承 `BaseParser`，实现 `can_parse()` 和 `parse()` 方法~~
  → **已废弃**：解析阶段不再有程序。遇到新文档格式请更新
  [references/doc_parse_spec.md](references/doc_parse_spec.md) 的列名别名表与处理建议，
  由模型按说明解析；`parsers/` 下的 `converter.py / word_parser.py / excel_parser.py`
  属遗留兼容路径，不再扩展。
- **添加新匹配策略**：在 `matchers/` 下添加匹配器，注册到 `standard_comparator.py`
- **添加新报告格式**：在 `reporters/` 下创建报告生成器，实现 `generate()` 方法
- **添加新的列名别名**：编辑 `references/doc_parse_spec.md` §3.3（**不要**改
  `parsers/standard_parser.py` 的列名判定逻辑）

## 深入阅读（按需加载）

| 文件 | 内容 | 何时读 |
|---|---|---|
| [references/doc_parse_spec.md](references/doc_parse_spec.md) | 解析输出契约：MD 语法、列名集合、9 项自检 | 每次解析原始标准前 |
| [references/kb_health.md](references/kb_health.md) | 知识库结论复用边界、体检工具（E1a/E1b/E2/E3） | 换标准对、修脏映射时 |
| [references/testing_and_regression.md](references/testing_and_regression.md) | 调优工具链、三套回归守卫、修改规则标准流程 | 改匹配逻辑前后 |
| [references/code_structure.md](references/code_structure.md) | matchers/ 模块表与无状态约定 | 重构 matchers 前 |
| [references/self_validation_detail.md](references/self_validation_detail.md) | 自验证抽样表、核验标准、报告格式 | 跑自验证前 |
| [references/install.md](references/install.md) | 依赖安装与说明 | 首次部署、排查依赖 |
| [references/setup-guide.md](references/setup-guide.md) | 环境配置逐步指南 | check_environment 报 needs_setup 时 |
| [references/history.md](references/history.md) | 历史修复记录 | 追溯判据来龙去脉 |

## 相关Skill

- `data-model-revision`：数据模型修订（无目标标准比对，纯修订场景）
- `reg-ddl-generator`：DDL生成（根据数据标准生成数据库表结构）
