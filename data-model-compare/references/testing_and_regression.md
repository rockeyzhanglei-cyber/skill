# 测试与回归防止

> **何时读**：改动匹配逻辑前后、重构 matchers 模块、或验证修复无回归时。

## 快速迭代与审计工具链（优化 skill 时用这套）

改完匹配逻辑不要重跑整个解析流程（慢且噪声大），按下面顺序走：

| 脚本 | 作用 | 典型用法 |
|---|---|---|
| `scripts/fast_iterate.py` | **秒级判分**。复用已解析的 `*_standard.json` 重跑比对+自验证，打印匹配类型分布、漏配数、疑误配数、准确率 | `fast_iterate.py <temp_dir> --dump-suspects 40` |
| `scripts/audit_new_fields.py` | 新增字段深度审计。A档=确定漏配 / B档=疑似 / C档=主子表展开 | `audit_new_fields.py <temp_dir>` |
| `scripts/audit_matches.py` | 全量匹配**分层置信**审计。L1 中文名同 / L2 基名+种类同 / LE 英文名同源 / LD 字典派生 / L3 需复核 / L4 最可疑 | `audit_matches.py <temp_dir> --sample 12` |
| `scripts/trace_field.py` | 单字段全链路追踪，定位某个字段为什么没匹配上 | `trace_field.py <temp_dir> <表名> <字段名>` |
| `scripts/kb_health_check.py` | 知识库脏映射体检（E1a/E1b/E2/E3 加权分层，A=高置信误点 / B=待确认派生） | `kb_health_check.py --min-score 2 --source <temp>/source_standard.json` |
| `scripts/audit_kb_veto.py` | 审计"知识库映射被否决"后的下游后果，防止网关误杀 | `audit_kb_veto.py <temp_dir>` |
| `audit_user_custom_review.py`（项目 temp 下，可复用模板） | **新表路径 user_custom 回收硬冲突复核**：遍历 new_tables 中 match_type=='user_custom' 的条目，对每对 (目标,源) 调 `_user_custom_hard_conflict` 输出全部条目+可疑清单到文件 | `python <temp>/audit_user_custom_review.py <temp_dir>`（需按 SKILL_DIR 修改脚本头） |
| `regenerate_reports.py`（项目 temp 下，可复用模板） | **跳过完整流程重新生成报告**：直接用 `iter_compare_result.json` 重出 HTML/MD/XLSX 三件套（含键名转换 modified→modified_fields），覆盖 reports/ | `python <temp>/regenerate_reports.py`（脚本内改 TEMP/OUT/TITLE） |
| `scripts/check_undefined_names.py` | **依赖漏带守卫**（P1-2）。AST 静态扫描未定义名字，专治「方法迁到新模块后漏带 import」这类潜伏问题——端到端回归覆盖不到的代码路径靠它兜底 | `python scripts/check_undefined_names.py` |
| `scripts/regression_check.py` | **端到端回归守卫**（P1-1）。对真实全量数据重跑「比对+自验证+条件装配」，与 golden baseline 逐项对比（含**字段级指纹**），确认行为零变化；有差异退出码 1，可接 CI。详见下方「回归防止机制」 | `regression_check.py --task-dir <任务目录>` |

**迭代纪律**：每次只改一个判据 → 立刻 `fast_iterate.py` → 看漏配/疑误配是否同时不劣化。
**只看准确率会被自验证的覆盖盲区骗到**：自验证只覆盖它认识的匹配类型，
新增匹配类型（如 `cross_table_fuzzy`）必须同步加进 `self_validator.py` 的 `fuzzy_types`，
否则准确率虚高。分层审计（`audit_matches.py`）是自验证的交叉校验，两者都要看。

## 测试用例库

测试用例位于：`tests/test_cases.yaml`

每个测试用例包含：
- **正确匹配案例**：应该被匹配的字段对
- **错误匹配案例**：不应该被匹配的字段对
- **边界案例**：需要特别注意的特殊情况

## 运行测试

**运行所有测试：**
```bash
python3 <skill_root>/scripts/test_runner.py
```

**保存测试基线：**
```bash
python3 <skill_root>/scripts/test_runner.py --save-baseline
```

**检查回归：**
```bash
python3 <skill_root>/scripts/test_runner.py --check-regression
```

## 修改规则的标准流程

**当发现新的匹配问题时，遵循以下流程：**

1. **添加测试用例**
   - 在 `knowledge_base/test_cases.yaml` 中添加新的测试用例
   - 描述问题场景和预期结果
   - 运行测试确认新用例失败（证明问题存在）

2. **修改规则**
   - 在 `matchers/standard_comparator.py` 中修改匹配逻辑
   - 优先修改通用规则，避免添加过于特殊的规则

3. **运行测试验证**
   - 运行所有测试：`python3 scripts/test_runner.py`
   - 确认新测试用例通过
   - 确认所有旧测试用例仍然通过（无回归）

4. **更新基线**
   - 如果所有测试通过，更新基线：`python3 scripts/test_runner.py --save-baseline`

## 回归防止机制

本 Skill 有**两套互补**的回归守卫，改动匹配逻辑时**两个都要跑**：

| 守卫 | 覆盖面 | 速度 | 命令 |
|------|--------|------|------|
| **单元级** `test_runner.py` | `tests/test_cases.yaml` 的 27 条手工用例，覆盖规则点 | 秒级 | `python scripts/test_runner.py --check-regression` |
| **端到端** `regression_check.py` | 真实全量数据（V6.0 任务 5349 个字段判定），覆盖整体行为 | 约 1-2 分钟 | `python scripts/regression_check.py --task-dir <任务目录>` |
| **静态** `check_undefined_names.py` | 全部模块的未定义名字（漏带 import） | 秒级 | `python scripts/check_undefined_names.py` |

**为什么必须有端到端基线**：单元测试只有 27 条用例，真实任务却有 5000+ 字段判定。
拆分 `standard_comparator.py`、重构 matcher 这类大改动，**单元测试全绿不等于行为没变**——
只有字段级指纹比对能证明"行为零变化"。

**为什么还要静态检查**：端到端基线只保证**被数据触发到的路径**行为不变，保证不了代码
100% 覆盖。P1-2 拆分时就出现过：方法迁到新模块后漏带 `import re`，但该分支在 V6.0 数据集
上从未被触发，端到端回归照样全绿，直到后续调用才 NameError。**三套守卫必须都跑**。

**端到端基线的关键能力**：不只比总数，还比对**每个字段的判定**（匹配类型 + 源字段 + 条件显示），
因此能捕获「matched 总数不变，但某字段从 `synonym` 漂移成 `keyword`」这类静默变化——
纯计数检测不出来。

**维护方式**：
- 基线文件：`tests/golden/<任务名>.json`（当前仅 V6.0医疗服务_vs_省平台v1.4.1医疗部分）
- 人工确认本次结果正确后更新基线：`regression_check.py --task-dir <任务目录> --update-baseline`
- 回归检查是**只读**的：结果只在内存判分，不覆盖 temp 下任何产物
- 退出码：`0`=无回归 / `1`=检出回归 / `2`=参数或文件错误

**其余机制**：
- **测试覆盖**：每次修复都添加对应测试用例，确保问题不会再次出现
- **持续积累**：测试用例库随使用不断完善，Skill 越来越智能
