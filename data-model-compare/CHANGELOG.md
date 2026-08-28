# 变更记录

> 本文件记录 skill 的历史修复与改进，不参与上下文加载。

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
