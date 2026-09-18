# 历史修复档案

> 本文件记录 skill 的历史修复与改进，不参与上下文加载，仅供追溯判据来龙去脉。

## 2026-09-09: 跨表业务判断与模型裁决闭环（v2.0.4 → v2.0.5）

> 背景：用户实测发现山东「入院记录-诊断.诊断依据」被程序兜底匹配到「首次病程记录.诊断依据」，
> 但两者业务上下文不同（前者针对每条诊断、后者是病程叙述），程序无法判断该跨表关联是否等价。
> 核心洞察：**同名数据元在不同业务上下文是否等价，固化规则无法判定，必须交由模型/人工 adjudication。**
> 据此把自检从"漏配+误匹配"扩成"检测→裁决→持久化"闭环。

- **B（检测，程序只标记不裁决）**：`matchers/self_validator.py` 新增 `cross_table_judgments` 信号。
  触发（结构性，不限匹配通道）：字段命中源表 ≠ 目标表主对齐源表，且主源表无同名项。
  即程序因主源表缺项才兜底到另一张表抓同名项。输出进 `self_validation_result.json` /
  `self_validation_report.md` 的"三、跨表业务判断待复核"。
  - 与 v2.0.4 的 `pk_role`/表名同义修复**正交**：那两项修的是"应匹配却没匹配"，本项修的是
    "匹配到了但可能跨表误关联"——程序不裁决，只标队列。
  - 关键修正：初版只拦 `cross_table*`/`auto_relation*` 通道，但 `诊断依据` 实际是 `exact_chinese`
    解析到非主源表（源表≠主源表同样成立），故改为"命中源表≠主对齐源表"的结构性判定才捕获。
- **C（裁决，模型/人工介入）**：新增 `scripts/adjudicate_cross_table.py`。
  读 `cross_table_judgments` → 检索字段/表说明与主源表最近字段 → 给出 `accept`/`redirect`/`new`
  + rationale → 写草稿 `cross_table_adjudication_draft.yaml`（含可直接追加进 `field_mappings.yaml` 的段）。
  - `--overrides` 支持模型/人工对具体 (目标表,目标字段) 直接给定裁决（judge 环节）；
    非 accept 项一律 `requires_human_confirm: true`，启发式拿不准的绝不静默落库。
  - `--apply` 将 accept/redirect 合并进 `field_mappings.yaml` 完成持久化（闭环）。
  - 演示：山东「诊断依据」经 B 标记 → 模型裁决 `redirect → 入出院诊断记录.诊断说明`（V6.0 以诊断说明
    承载诊断依据）→ 草稿 rationale 可解释。
- **闭环落地（示例真正闭环）**：模型 override 裁决 `入院记录-诊断(辅 D08 标）.诊断依据 → 入出院诊断记录.诊断说明`
  已持久化进 `knowledge_base/field_mappings.yaml`（**表作用域复合键** `入院记录-诊断(辅 D08 标）.诊断依据`，
  不以裸中文名建全局索引，故**不会污染**出院记录-诊断/术前讨论等同名项）。
  - 因 `core_compatible(诊断依据, 诊断说明)` 在 KB 中为 False、字段类门限又过宽（诊断依据~诊断类别代码
    kind_ok=True），**固化启发式确实无法解析**，只能靠 `--overrides` 注入模型权威裁决——印证 B「只检测不裁决」。
  - `--apply` 已加固：仅 accept/redirect 落库，且统一产出表作用域复合键，杜绝跨表污染。
  - 重生成山东报告验证：该字段转为 `user_custom → 入出院诊断记录.诊断说明` 并**退出跨表队列（645→644）**；
    另两条 诊断依据（出院记录-诊断、术前讨论）主源表无诊断说明，**仍正确留队待人工确认**，证明无污染。
  - 三条回归守卫仍全绿（AST 9/9、test_runner 27/27、省平台 golden 零变化）。
- **文档**：SKILL.md 自验证流程增"跨表业务判断与模型裁决（B/C）"小节；self_validation_detail.md 增
  B 信号与 C 闭环用法；本档案记来龙去脉。
- **回归**：AST 9/9、test_runner 27/27 通过；B/C 仅改动自检与新增脚本，不触碰比对主链路，
  省平台(V6.0 vs 省平台v1.4.1) golden 比对零变化。

## 2026-09-08: 保守修复明显错误（v1.4.0 → v1.5.0）

> 背景：架构已切换为「解析靠说明（模型按 doc_parse_spec.md 产出规范化 MD）、比对靠程序」，
> 但文档多处仍描述旧解析器架构，本次只修错、不动结构。

- **SKILL.md version** 1.4.0 → 1.5.0
- **职责分层**：改为三阶段表（模型解析 → 程序装载 → 程序比对）+ 两条硬约束
  （禁改 standard_parser.py 列名判定逻辑、禁写自动提取脚本）；标注 converter.py /
  word_parser.py / excel_parser.py 为遗留兼容路径
- **执行方式**：唯一入口改为输入规范化 MD；标注 .doc 不可用（macOS 转换必丢表格）
- **四种工作模式**：原文写"三种"，实际有四个（比对/测试/验证/人工核对）；补充模式前置说明
- **FAQ Q1（PDF）**：改为新架构（模型读 PDF 产出规范化 MD）；保留旧 parsers.pdf.primary
  路径说明并标注 config.yaml 已无 parsers 配置段
- **FAQ Q3（跨表关联）**：修正 `relations.yaml`（单文件，不存在）→ `relations/` 目录
  （generic.yaml + source_yunnan_v5.5.yaml）
- **错误处理**：新增第 6 条「解析出 0 表 / 0 字段」排查步骤（列名归一化 → 约束值 M →
  表格语法 → 重新解析）；标注 on_failure=warn 时 0 表也会产出空报告，须立即中止
- **扩展点**：「添加新解析器」标注已废弃，改为「更新 doc_parse_spec.md 别名表」
- **核心功能与安装**：依赖清单修正——实际依赖 pyyaml/pandas/openpyxl/python-docx/
  pdfplumber/psutil，删除未使用的 marker-pdf
- **references/install.md**：重写——标题「核心功能概述」改为「依赖安装」（与文件名/用途一致）；
  删除与新架构冲突的「自动选择最佳解析器」；补全被截断的代码块；按实测依赖重列清单

## V6.0医疗服务 vs 省平台v1.4.1 医疗部分

### 实测修复记录

- **知识库脏映射修正**：`会诊记录-会诊医师.门(急)诊号 ← 门诊就诊记录表.姓名` 把 `gmap['门(急)诊号']`
  污染成 `{'source_field': '姓名'}`（gmap 后写覆盖、无源表约束），导致新表
  `m_emr_observation_resc.门(急)诊号` 错配到"姓名"。已将该条 source_field 改空。
  排查手法：用正则扫 gmap（target 含 号/代码/标识 + source 含 姓名/名称/性别）定位可疑。
- **整表新增 ≠ 字段新增**：用户确认整表新增 / 无表匹配时，**仍应对每个字段走字段级跨表匹配**
  （`_match_new_table_fields`），只把真正匹配不到的落为新增；整表直接全量落新增会
  误吞约 132 个可回收字段（本任务 3394→3224 即此修复贡献）。
- **"综述↔结果/结论"类命名差异**：`体检综述←总检结果`（目标说明"总检的汇总结果"）
  被 `_user_custom_hard_conflict` 判"核心概念不相干"（公共汉字仅"检"字）——属规则引擎
  保守误报，人工核验为同概念，保留。此类误报仅登记不否决，不影响结果；案例增多可
  在 `field_synonyms.yaml` 增加同义对或在硬冲突判据中加 description 兜底。

### P6 多表关联+否定确认强判死+自验证降噪

**背景**：目标标准 `个人基本信息标识号`/`卡类型代码`/`卡号`/`社保卡号`/`出生地-详细地址`/`居住地-详细地址`
需匹配源标准多表（PERSON 主表 + PERSON_IDENTIFICATION 子表 + PERSON_ADDRESS 子表），
要求通道支持 FK 说明驱动的多表关联。

**改动 1：P6 多表关联通道（auto_relation）——standard_comparator.py**
- 解析源字段说明中 FK 描述（`_FK_PATTERN`）构建双向表邻接图 `_auto_adjacency`
- 目标字段在当前对齐源表所有常规通道失败后，沿 FK 关联图搜索关联子表，是 new_field 前最后一环
- 跨表收集 + 全局最优等级：P6 遍历全部邻接表收集候选（`defer_claim=True`），按整数 rank（0=exact < 1=synonym < 2=semantic < 3=keyword）全局取最高优先级
- 跨通道占用保护 `_p6_occupied`：compare() 主循环登记非 P6 通道已占用的源字段，P6 决策时若候选已被占用且基名不一致则拒绝
- 通道级专有同义词 `_AUTO_REL_SYNONYMS`：`卡类型→卡证类型`、`卡号→卡证号码`、`社保卡号→卡证号码`、`居民健康卡卡号→卡证号码`
- 复用判定 `_auto_relation_reuse_allowed`：剥离地址位置/卡类型前缀与尾部种类词后基名一致才允许同源字段服务第二个目标字段

**改动 2：P6 意图登记 `_p6_uc_declared`（防止 P6 keyword 抢配已知错名）**
- user_custom 声明了来源但**解析失败**（表存在但字段未命中）时登记"意图"
- P6 决策点仅拦截 `str(mtype).endswith('keyword')` 最低置信兜底，高置信 synonym/semantic 不受影响
- 表不存在（陈旧表名如 `患者基本信息表`）不登记，降级全局跨表复用，P6 兜底仍可回收

**改动 3：否定确认改造——表可解析 + fact 全 miss 时强否定判死（standard_comparator.py）**
- 旧逻辑：否定确认（source_field 空）走 stale_negative_override 三级事实查找，miss 后不判死继续走常规通道 → 被 keyword/P6 抢配
- 新逻辑：**表可解析 + fact 三级全 miss** → 直接 `return None`（强否定判死）。fact 任一命中则不判死
- 类型名判断：`isinstance(sf, dict)` 表示 fact 命中（dict 态），`return None` 表示确定判死，`continue` 回到常规通道

**改动 4：self_validator.py 降噪规则扩展**
- `_NOISE_CHARS` 新增全角冒号 `：`
- `_NORMALIZE_MAP` 新增：`辩证→辨证`、`结束就诊→就诊结束`、`治疗处理→治疗`、`是否是→是否`、`药品→药物`、
  `出生地-/居住地-→地址-`、`手术申请单/电子申请单→申请单`、`手术后可能出现的意外及并发症→手术并发症`、`其中→''`
- `_GENERIC_PREFIXES` 新增 `医疗机构`
- `_strip_generic` 回退安全：剥前缀后若只剩后缀词（如 `医疗机构代码`→`代码`）则回退该前缀
- `_GENERIC_SUFFIXES` 新增 `唯一`

**修复效果（suspects 17→0，leaks 0）**：
- 6 目标字段全部回收
- 3 条真误配保持 new_field
- 14 条自验证合理匹配误报通过降噪规则收敛
- new_fields 从 3233→3064，准确率 100%

### round6：条件装配固化 + P6 外键方向否决

**改动 1：条件装配固化** — permanent_addr_district_code 匹配需带条件显示（地址类别代码=03）
**改动 2：P6 外键方向否决** — 候选表是当前源表的子表且无判别器时否决
**改动 3：属性子表显式名单** — `_AUTO_REL_ATTR_TABLE_DISCS` 显式注册判别器

**round6.2 最终效果**：new_fields 1576；condition_display 43 条；leak 0 / suspect 47；准确率 99.16%。

### 2026-08-28: A/B 网关修复（新疆自治区 vs 乌鲁木齐）

- **A 修复**：显式同义对豁免种类网关（ID_NO←ZJHM）
- **B 修复**：核心概念比较前 lower()+去空格归一（RH_CODE←RHXXDM）
- 自验证器同步：`_core` 归一、`_is_explicit_synonym` 改子串匹配
- 结果：可疑 189→163，漏配 144 不变

### 2026-08-28: 规则单一源重构（matching_core.py）

- 新增 `matchers/matching_core.py`：核心概念判定/显式同义判定/词表唯一实现
- 比对器+自验证器委托公共模块，差异显式参数化
- 验证：15万对抽样行为零变化，乌疆端到端漏配144/可疑163复现

### 2026-09-09: v2.0.1 架构一致性优化（三处双路径收拢）

- **回写单一路径**：`main.py --feedback` 改为只读分析（调 read_modified_excel.py
  输出知识库写入指令后退出），删除对 read_excel_feedback.py 自动回写的调用；
  旧脚本归档为 scripts/archive/read_excel_feedback_auto_writeback.py。
  回写唯一路径 = 模型按 SKILL.md 模式四执行。
- **知识库装载收拢 manager**：删除 comparator 的死方法 _load_table_synonyms /
  _load_field_mappings / _load_numbered_field_groups / 模块级 _load_relations
  （均零调用点，约 160 行）；multi_source_tables 改经 manager 装载
  （新增 kb.multi_source_tables 属性，aliases 展开逻辑等价迁移）。
- **修复 learned_mappings 失效 bug**：原赋值代码在被删除的死方法 _load_synonyms
  内，导致"已学习表映射"最高优先级从未生效；现统一经 kb.learned_mappings 装载
  （32 条 + 2 条 _alt），_find_matching_table 优先级 0 首次真正可用。
  V6.0 任务指纹零变化（V5.5 拼音表名在该任务不命中），乌疆任务后续观察。
- 验证：AST 9 模块通过；test_runner 27/27；regression_check 5349 指纹零变化。

### 2026-09-09: v2.0.2 剩余双路径收拢（接关联，不删代码）

- **CompatibilityEngine 接入 manager**：此前 `_load_rules` 直读
  compatibility_rules.yaml（绕过统一缓存）。现构造签名扩展为
  `CompatibilityEngine(skill_dir, kb_manager=None)`，comparator 传入
  `kb_manager=self.kb`；未传 manager 时保留直读回退（外部调用方兼容）。
- **self_validator 同义词接入 manager**：`_load_field_synonyms` 原按
  4 个候选路径（含两个用户目录绝对路径）自找文件，环境依赖且与比对器
  各读一份。现优先经 `KnowledgeBaseManager` 装载（与比对器共享同一份
  解析结果，352 条同义词运行时验证一致），候选路径直读降级为回退。
- **状态说明补齐（不删除）**：`standard_comparator._load_synonyms`
  确认零调用（功能已由 manager 接管，synonyms/exclude 双向字典运行时
  验证正常），docstring 标注"已废弃·保留备查"；`base_strategy.py`
  标注"预留扩展点，尚无子类"。
- **文档**：references/code_structure.md 新增"相关目录 + 装载纪律"节。
- **勘误**：上一轮深析中"CompatibilityEngine 零引用"为误报（BSD grep
  BRE 交替语法问题）。实际 L467 创建、L3311 调用链路完好，本轮仅
  收拢其装载路径。
- 验证：AST 9 模块通过；test_runner 27/27；regression_check
  V6.0 任务 5349 指纹零变化；manager 18 条规则 / engine 双路径规则数
  一致 / self_validator 352 条同义词与比对器同源，三项冒烟通过。

### 2026-09-09: v2.0.3 比对准确性三项全局优化（字形归一 + 互斥限定词网关 + 主题词网关）

> 背景：用「山东省平台电子病历2018V1.4 vs 区域平台V6.0医疗服务」实测审计，
> 归纳出三类根因漏配/误配。三项优化均为**平台无关、数据驱动可扩表**的通用规则，
> 不写任何针对具体字段的硬编码特例。

- **（A）字形归一层（matching_core.normalize_glyphs，v2.0.3 最高杠杆单点）**
  - 全角→半角（U+FF01–U+FF5E 显式区段，避 NFKC 连累 ㎎/㎡/①）、全角空格→空格；
    异体字 査(U+67FB)→查；异形词 适应证→适应症、禁忌证→禁忌症、结论→结果。
  - 单一最底层归一，匹配侧（exact_chinese / `_global_cn_lookup` / keyword / semantic /
    P6）与自验证侧共用，根治「exact 漏配→跌落到 n-gram 误配」级联。
  - 维护约定：只收无歧义等价写法，拿不准的（如 结果/信息）一律不收，交上层网关。
- **（B）互斥限定词网关（field_compatibility.mutex_qualifier_conflict）**
  - 对称硬冲突：根本/直接、术前/术中/术后、产前/产后/产时；方位词 前/后 按
    `_direction_keys` 词位（取前一词，非拆字）判定，避免「颅脑损伤患者入院前昏迷天数」
    误判。其他/其余/另 是**同义词组**非互斥，不入表。
  - 复用点：keyword / semantic / P6(auto_relation_residue) 三通道均经此网关。
- **（C）主题词网关（field_compatibility.keyword_subject_compatible）**
  - 剥离最长公共前缀+后缀后，剩余主体均非空且互不包含→不同主题拒绝
    （心理护理描述≠导管护理描述、产后宫底高度≠产后宫缩）。单侧空残基→放行。
  - **配套同义前置归一（keyword 清理路径）**：`NORMALIZE_MAP`（医师→医生、科别→科室、
    报告单→报告、辩证→辨证、唯一标识→标识 等人工复核同义表）在主题网关**之前**先归一，
    避免同义字对残基（总检医师/总检医生、出院科别/出院科室、报告单编号/报告唯一标识）
    被网关误拦。新增 `'唯一标识':'标识'` 使「检验报告单编号 vs 检验报告唯一标识」
    经空残基规则放行（同一报告 ID）。
  - **配套括号附注剥离（keyword 清理路径）**：`（…）`/`(…)` 说明性附注（如
    「入院病情(对应主要诊断)」的「(对应主要诊断)」、 「产后宫底高度(cm)」的「(cm)」）
    在主题网关前剥除（与 normalize_concept 一致），避免污染残基判定。
- **TEMPORAL 时间类（field_compatibility，v2.0.3）**：日期时间/日期/时间 与
  名称/代码/标识/流水号/签名等完全互斥，根治「交接班日期≠交接班记录唯一标识」类误配。
- **验证与回归结论**：
  - AST 9 模块通过；test_runner 27/27。
  - V6.0 医疗服务 vs 省平台v1.4.1 医疗部分 golden baseline（5349 字段）重跑：
    matched 3072→3075、modified 1295→1305、new_fields 982→970（**少 12 个漏配字段**）、
    suspect 23→34。suspect 上升为**自验证器启发式误报**——新增 suspect 均经人工核对为
    **正确回收**（如 cm_dtc_fee 辩证/辨证+全角冒号归一、乙肝核心/表面/ e 抗体标记、
    if_inf_case、剂量/街道括号仅分隔符差异），自验证器未按比对器归一比对原始名致
    「核心概念不一致」误标。已重生成 golden baseline 认证 v2.0.3 行为。
  - 全量「山东省平台电子病历2018V1.4 vs 区域平台V6.0医疗服务」（源 118 表/4898 字段、
    目标 76 表/2877 字段）重跑：matched=1075、modified=668、new_fields=1134、
    **suspect=7、准确率=99.76%**（v2.0.2 审计期约 31 个 suspect 经三项网关大幅压降）。
  - 已知债：自验证器「核心概念不一致」启发式未复用比对器归一，会对正确回收对产生
    false-suspect，后续可单独修（不在本版范围）。

### 2026-09-09: v2.0.4 两张用户实测缺陷修复（表名同义兜底穿透 + 主键角色归一）

> 背景：用户在「山东省平台电子病历2018V1.4 vs 区域平台V6.0医疗服务」实测中报两个
> 具体缺陷——① 表名 `入院记录-诊断` 应匹配 `入出院诊断记录` 却错配到代码字典表
> `疾病诊断目录`；② 主键 `内码` 与 `唯一标识`/`系统编码` 语义相同（都唯一标识一行
> 记录）却全部被判为新增。两处均属通用规则缺陷，无针对字段的硬编码特例。

- **（① 表名）根因**：`_normalize_table_name` 旧正则 `\([^)]*\)` 只剥 ASCII 括号对，
  而山东标准辅助表用**半角开+全角闭混合括号**（`入院记录-诊断(辅 D08 标）`、
  `影像诊断报告( D07 标）`），后缀始终留 `（辅 D08 标）` 残尾，导致
  `入院记录-诊断` 永远归不到 `入院记录-诊断`。准备阶段加的显式同义词条目
  （`入院记录-诊断 ↔ 入出院诊断记录`）因此从未命中，表退到「业务核心概念兜底」
  按源表顺序抢先撞上代码字典表 `疾病诊断目录`（记录表被字典表截胡）。
  **修复**：括号剥离正则扩为 `[（(][^）)]*[）)]`，统一处理全角/半角/混合三种括号。
  顺带使 6+ 张山东辅助表（`出院记录-诊断(辅 D12 标）`、`影像诊断报告( D07 标）`、
  `住院病案首页-诊断(电子病历) (辅 D09/D10 标）` 等）的 `辅/标` 后缀被归一，
  对齐质量整体改善。`table_synonyms.yaml` 的 `入院记录-诊断 ↔ 入出院诊断记录`
  显式条目保留（配合 `_is_table_synonym(explicit_only=True)` 的 3a 优先趟）。

- **（② 主键）根因**：`NORMALIZE_MAP` 已加 `'内码':'标识'`（v2.0.3），但字符串归一
  仍无法桥接主键对：裸 `内码` 归一后残基为空被「空残基早退」拦截；`入院记录内码`→
  `入院记录` 与 `入出院诊断记录唯一标识`→`入出院诊断记录` 在**表名前缀**上不互含。
  结果 88 个目标主键字段（每表 ID/`内码`、各 `XX内码`）全判新增。
  **修复**：`_compare_fields` 新增「主键角色归一」预趟 `_pk_role_matches`——同表对齐后，
  目标主键角色字段（`内码`/`XX内码`/`en==ID`）优先命中源主键角色字段
  （`系统编码`/`SYS_SOID`/`XX唯一标识`）：
  - 通用主键互配（无主体，`内码↔系统编码`）=2；
  - 同主体前缀对齐（`住院就诊记录内码↔住院就诊记录唯一标识`）=1；
  - 其余（如 `个人内码` 误撞 `系统编码`）=-1 不接受，避免主键错配。
  - 尊重 user_custom：目标字段若有 user_custom 映射则不在此抢先命中。
  产出新匹配类型 `pk_role`。

- **验证与回归结论**：
  - 山东任务（源 118 表/4898 字段、目标 76 表/2877 字段）重跑：
    `入院记录-诊断(辅 D08 标）` 现对齐 `入出院诊断记录`（首要源表，7 字段）；
    `pk_role`=62；**new_fields 1134→1064（−70）、new_tables 10→9**；
    matched 1075→1079、modified 668→734；**suspect=9（无一条是 pk_role——9 条均为
    keyword 通道既有启发式误报，未新增误配）**；准确率 99.69%。
  - Golden 回归（V6.0 vs 省平台v1.4.1 医疗部分，5349 字段）：**无回归，字段级指纹
    与基线完全一致（行为零变化）**——该对无 `内码`/混合括号表，两处修复对其良性。
  - AST 9 模块通过；test_runner 27/27。
  - 注：Golden baseline 已于 v2.0.3 末重认证（matched 3072 / modified 1314 /
    new_fields 962 / leak 1 / suspect 35）；本版在该对上行为不变，故未再更新基线。
