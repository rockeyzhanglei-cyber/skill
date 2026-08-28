---
name: dmc-optimize-loop
description: >-
  数据标准比对 skill（data-model-compare）的循环优化方法论。当你要"拿一个真实比对任务
  去测试/打磨 data-model-compare 的匹配或知识库质量、把准确率拉到 ≥90%、定位知识库脏映射、
  或审计比对结果是否准确"时使用本 skill。覆盖快速迭代工具链、准确率自验证、人工确认权威
  红线、知识库体检与脏数据修复的正确姿势。即使用户只说"跑一下看看准不准""帮我优化这个 Skill"
  "知识库里好像有错的映射"，也应触发。
---

# data-model-compare 循环优化方法论

本 skill 不重复比对器实现，只讲**怎么把比对器/知识库打磨准**的可复用工作流。
底层匹配器在 `data-model-compare` 的 `matchers/standard_comparator.py`，配套脚本在
`scripts/` 下。以下路径以该 skill 根目录为基准。

## 核心红线（最重要的一条）

**人工确认（知识库 `user_custom_mappings.yaml`）是领域权威，比对期只能检测、不能静默否决。**

一次真实翻车：原计划给 `user_custom` 加"语义硬冲突网关"并直接否决陈旧映射，结果只抓到
3 个真错里的 **1** 个，却误杀约 **40** 条正确人工确认，覆盖率反而下降。根因是：这些"错映射"
不是标准版本漂移，而是**当年人工反馈时的误点 = 知识库脏数据**。正确做法是把脏数据挑出来交
人工改 yaml，绝不靠启发式在匹配期猜。

推论：
- 知识库的正向映射（`target_field ← source_field`）是"相对某次源标准"的结论。换源标准后
  同名条目可能指向完全不同的数据元，不能直接照搬。
- 负向结论（"确认无对应源字段"）更不能跨源标准复用为"永久钉死为新增"——源标准里有同义字段
  时要撤销（弱否决 / 事实优先）。
- 任何"新增匹配类型"必须同步加进 `self_validator.py` 的覆盖集合，否则准确率虚高。

## 快速迭代工具链（改完逻辑不要重跑整个解析）

按此顺序，秒级反馈：

| 脚本 | 作用 | 典型用法 |
|---|---|---|
| `scripts/fast_iterate.py` | **秒级判分**：复用已解析的 `*_standard.json` 重跑比对+自验证，打印匹配类型分布、漏配、疑误配、准确率 | `fast_iterate.py <temp_dir> --dump-suspects 40` |
| `scripts/audit_new_fields.py` | 新增字段深度审计：A=确定漏配 / B=疑似 / C=主子表展开 | `audit_new_fields.py <temp_dir>` |
| `scripts/audit_matches.py` | 全量匹配**分层置信**审计：L1 中文名同 / L2 基名+种类同 / LE 英文名同源 / LD 字典派生 / L3 需复核 / L4 最可疑 | `audit_matches.py <temp_dir> --sample 12` |
| `scripts/trace_field.py` | 单字段全链路追踪，定位为什么没匹配上 | `trace_field.py <temp_dir> <表> <字段>` |
| `scripts/kb_health_check.py` | 知识库脏映射体检（见下） | `kb_health_check.py --min-score 2 --source <temp>/source_standard.json` |
| `scripts/audit_kb_veto.py` | 审计"知识库映射被否决"的下游后果，防止网关误杀 | `audit_kb_veto.py <temp_dir>` |

**迭代纪律**：每次只改**一个**判据 → 立刻 `fast_iterate.py` → 确认漏配/疑误配不劣化。
**只看准确率会被自验证盲区骗到**：自验证只覆盖它认识的匹配类型；分层审计（`audit_matches.py`）
是它的交叉校验，两者都要看。

## 知识库体检（修脏数据的正确入口）

```bash
python scripts/kb_health_check.py --min-score 2 \
    --source <temp_dir>/source_standard.json
```

四类**按强度加权**的证据交叉定位（总分 ≥2 才报）：

- **E1a 强冲突（2 分）**：字段种类冲突 / 核心概念缺失（一侧是裸通用词`姓名`，另一侧带实质限定
  —— 人工误点最典型形态：`主治医师姓名 ← 姓名`、`责任护士代码 ← 责任护士执业证书编码`）。
- **E1b 弱冲突（1 分）**：核心概念不相干（双方都有限定但不搭）。
- **E2 库内自相矛盾（1 分）**：同一目标字段多条非空映射，本条落在少数簇；**豁免**——多数簇的
  源字段名在本条源表里根本不存在时，说明没有同名字段才退而用别名，属合理。
- **E3 同表同名归属（2 分）**：源字段 X 已归属同名目标字段 X，又给了别的目标字段；派生字段
  （子串关系）与主子表流水号继承两类正常形态予以豁免。

输出 `knowledge_base/kb_health_report.json`，按置信分层：
**A-高置信**（大概率误点，建议直接改 yaml）/ **B-待确认**（一源对多目标，多为合理派生，人工快判）。

> 启发式调优到**边际收益拐点即停**。继续硬猜别的误报规则，只会重犯"静默否决"的错。
> 不确定项如实交人工（B 层），不要假装精确。

## 复现命令（以区域平台60 vs 云南v1.4.1 为例）

```bash
cd ~/.cache/WinCode/skill/data-model-compare   # 或你的 skill 实际路径
PY=/Users/zhanglei/.workbuddy/binaries/python/envs/default/bin/python
T=/Users/zhanglei/data-model-compare-docs/区域平台60_vs_云南v1.4.1/temp

$PY scripts/fast_iterate.py $T --dump-suspects 40
$PY scripts/audit_matches.py $T --sample 12
$PY scripts/audit_new_fields.py $T
$PY scripts/kb_health_check.py --min-score 2 --source $T/source_standard.json
```

## 何时判定"够了"

- 主链路：0 漏配、≤2 疑误配、准确率 ≥99% 即达标（用户目标 90% 很容易超）。
- 剩余疑误配若是"可接受的近义/命名习惯差异"（如 `报告发布科室代码→报告科室编码`），不必强求清零。
- 知识库脏映射交人工改 yaml 后，重跑 `fast_iterate.py` 看覆盖率是否回升、漏配是否仍 0。
