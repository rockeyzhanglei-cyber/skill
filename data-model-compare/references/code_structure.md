# 代码结构（matchers/）

> **何时读**：修改匹配逻辑、排查某个判据的归属、或重构 matchers 模块前。

P1-2 把 5019 行的单文件类拆成"主控 + 若干无状态辅助模块"：

| 模块 | 职责 | 状态依赖 |
|------|------|---------|
| `standard_comparator.py` | 主控：匹配调度、通道编排、结果组装 | **有**（配置与运行时状态） |
| `matching_core.py` | 核心概念判定、显式同义判定、词表（唯一事实来源） | 无 |
| `field_compatibility.py` | 字段兼容性判定（语义 / 种类 / 角色 / 类型） | 无 |
| `auto_relation.py` | P6 自动关联（沿 FK 关联图搜子表）判定 + 通道级常量 | 无 |
| `text_utils.py` | 文本工具（LCS、子序列、角色尾词剥离） | 无 |
| `global_lookup.py` | 全局查找的基名 / 语义基名归一化 | 无 |
| `value_domain_comparator.py` | 值域比对 | — |
| `self_validator.py` | 自验证（漏配 / 疑误配体检） | — |

**约定**：标"无"的模块必须保持无状态——需要配置时**通过参数传入**，
不要反向 import `standard_comparator`（会形成循环依赖，且判定结果难以复现）。
主控里保留的是**同名薄委托**，调用这些无状态方法时写法不变。

## 相关目录

| 目录/文件 | 职责 | 知识库装载方式 |
|------|------|---------|
| `rules/compatibility_engine.py` | 字段兼容性规则引擎（18 条规则，供 `_is_description_compatible` 前置过滤） | **经 `KnowledgeBaseManager`**（comparator 传入 `kb_manager=kb`；未传时回退直读 YAML） |
| `knowledge_base/manager.py` | 全部知识库统一装载 + MD5 缓存（field_synonyms / table_synonyms / field_mappings / numbered_field_groups / learned_mappings / **compatibility_rules** / relations / user_custom_mappings） | — |
| `matchers/base_strategy.py` | 预留扩展点：`MatchStrategy` 基类，尚无子类（六通道为主控内联实现） | — |

**装载纪律（v2.0.2 起）**：所有知识库 YAML 一律经 `KnowledgeBaseManager` 装载，
禁止模块内自建 `open()+yaml.safe_load` 直读（自验证器的同义词已同样接入 manager，
与比对器共享同一份解析结果；直读仅允许作为 manager 不可用时的回退保留）。
`standard_comparator._load_synonyms` 为已废弃方法（功能被 manager 接管），保留备查，勿再调用。
