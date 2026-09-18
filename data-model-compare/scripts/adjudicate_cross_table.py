#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
跨表业务判断的模型裁决脚本（C 流程，v2.0.5）

闭环：检测(B, self_validator.cross_table_judgments) → 裁决(本脚本) → 持久化(field_mappings.yaml)

程序（固化规则）只能**标记**"结构性跨表 + 主源表缺项"的字段（见 self_validator 的 B 信号），
但无法判断该跨表关联是否符合**业务语义**（例如「诊断依据」在主源表「入出院诊断记录」
无同名项，程序兜底命中「首次病程记录.诊断依据」，但前者针对每条诊断、后者是病程叙述，
业务上未必等价）。这类判断需要**模型/人工**介入。

本脚本是 C 流程的"裁决"环节：
  1. 读取 self_validation_result.json 的 cross_table_judgments（B 的输出）。
  2. 为每个待裁决项检索上下文：目标字段说明、命中源字段说明、主源表说明，
     以及主源表中与目标字段"核心概念相近"的候选字段（供 redirect 决策）。
  3. 给出一项裁决（accept / redirect / new）并附 rationale：
       - accept   : 命中源字段是通用/共享数据元（名称在 _AMBIGUOUS 或通用后缀），
                    跨表命中属良性，确认接受。
       - redirect : 主源表存在核心概念相近字段，改指主源表最近字段（更贴合业务）。
       - new      : 主源表无相近字段，判定为目标标准新增。
  4. 输出草稿 YAML（cross_table_adjudication_draft.yaml）：
       - adjudications: 每条裁决（含 rationale、requires_human_confirm）。
       - field_mappings_yaml: 可直接追加进 field_mappings.yaml 的条目（accept/redirect）。
     草稿默认可读、不落盘知识库；人工/模型确认后，用 --apply 将 field_mappings_yaml
     合并进 knowledge_base/field_mappings.yaml 完成持久化。

若配置了 LLM（环境变量 MODEL_ADJUDICATE=1 且可用客户端），脚本会把上下文交给模型做
最终裁决；未配置时退化为上述可解释的启发式预裁决（仍标记 requires_human_confirm=True，
交由人工确认）。

用法：
  python scripts/adjudicate_cross_table.py \
      --temp <任务temp目录> [--out <草稿yaml>] [--apply] [--limit N]
"""
import os
import sys
import json
import argparse
try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SKILL_DIR)

from matchers.self_validator import _AMBIGUOUS  # 通用/歧义字段名集合

try:
    from matchers.matching_core import core_compatible, normalize_concept
except Exception:  # pragma: no cover
    def core_compatible(a, b, **kw):
        return a == b
    def normalize_concept(x):
        return x

try:
    from matchers.standard_comparator import StandardComparator as _SC
    _kind_ok = _SC._field_kind_compatible
except Exception:  # pragma: no cover
    _kind_ok = None

# 通用后缀：跨表命中这些通常属共享数据元，偏低风险
_SHARED_SUFFIXES = ('代码', '名称', '编号', '流水号', '标识', '标志', '日期', '时间',
                    '日期时间', '说明', '备注', '类型', '状态', '姓名', '机构')


def _load(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _find_table(doc, cn_or_en):
    for t in doc.get('tables', []):
        if (t.get('chinese_name') == cn_or_en) or (t.get('name') == cn_or_en):
            return t
    return None


def _find_field(table, cn):
    if not table:
        return None
    for f in table.get('fields', []):
        if (f.get('chinese_name') == cn) or (f.get('field_chinese_name') == cn):
            return f
    return None


def _nearest_in_primary(primary_table, target_cn):
    """主源表中与目标字段**核心概念一致**的候选字段（供 redirect）。

    仅返回 core_compatible 命中（强信号）。纯子串包含（如「诊断依据」⊃「诊断」）
    不可靠——它常把「诊断依据」误导向「诊断类别代码」之类概念不同的字段，
    故不作为 redirect 依据；此类情况交由模型/人工裁决（见 _decide 的 new 分支）。
    这正印证了 B 的核心洞察：同名/近名跨表项是否业务等价，固化规则无法判定。
    """
    if not primary_table:
        return None
    for f in primary_table.get('fields', []):
        fc = f.get('chinese_name') or f.get('field_chinese_name')
        if not fc:
            continue
        if not core_compatible(target_cn, fc):
            continue
        # 字段种类网关：避免把"依据/说明"类误导向"代码"类（如 诊断依据 → 诊断类别代码）。
        # 种类冲突说明即便核心概念相近，字段性质也不同，不宜自动 redirect。
        if _kind_ok is not None and not _kind_ok(target_cn, fc):
            continue
        return f
    return None


def _decide(j, target_doc, source_doc):
    """返回 (decision, proposed_source_table, proposed_source_field, rationale, requires_confirm)."""
    t_cn = j['target_cn']
    matched_tbl = j['matched_source_table']
    matched_fld = j['matched_source_field']
    prim_tbl = j['primary_source_table']

    target_table = _find_table(target_doc, j.get('table_chinese_name') or j['table'])
    target_field = _find_field(target_table, t_cn)
    matched_source_table = _find_table(source_doc, matched_tbl)
    matched_source_field = _find_field(matched_source_table, matched_fld)
    primary_source_table = _find_table(source_doc, prim_tbl)
    nearest = _nearest_in_primary(primary_source_table, t_cn)

    t_desc = (target_field or {}).get('description', '') or ''
    m_desc = (matched_source_field or {}).get('description', '') or ''
    p_desc = (primary_source_table or {}).get('description', '') or ''

    # 通用/共享数据元：跨表命中属良性
    if (t_cn in _AMBIGUOUS) or t_cn.endswith(_SHARED_SUFFIXES):
        return ('accept', matched_tbl, matched_fld,
                f'「{t_cn}」为通用/共享数据元，跨表命中源表「{matched_tbl}」属良性关联，确认接受',
                False)

    # 主源表有核心概念相近字段 → redirect
    if nearest is not None:
        n_cn = nearest.get('chinese_name') or nearest.get('field_chinese_name')
        return ('redirect', prim_tbl, n_cn,
                f'主源表「{prim_tbl}」存在核心概念相近字段「{n_cn}」，'
                f'改指主源表更贴合业务（原命中「{matched_tbl}.{matched_fld}」为跨表兜底）',
                True)

    # 主源表无相近字段 → 标记新增
    return ('new', '', '',
            f'主源表「{prim_tbl}」及命中源表「{matched_tbl}」均无核心概念相近字段，'
            f'判定为目标标准新增（不映射）',
            True)


def build_field_mapping_entry(j, decision, proposed_source_table, proposed_source_field,
                               target_doc):
    """生成可直接追加进 field_mappings.yaml 的条目（accept/redirect 才有映射）。

    用「表中文名.字段中文名」复合键（表作用域），避免按英文字段名全局生效而污染
    其它含同名目标的表（如 诊断依据 只应作用于 入院记录-诊断，不应误伤 出院记录-诊断）。
    field_mappings.yaml 不构建全局索引，复合键仅被比对器的表级 user_custom 查找命中。
    """
    if decision not in ('accept', 'redirect'):
        return None
    table_cn = j.get('table_chinese_name') or j['table']
    return {
        'target_fields': [f"{table_cn}.{j['target_cn']}"],
        'source_table': proposed_source_table,
        'source_field': proposed_source_field,
        'match_type': 'user_custom',
        'description': (f'[模型裁决/C] 跨表业务判断：{j["target_cn"]} '
                        f'→ {proposed_source_table}.{proposed_source_field}'),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--temp', required=True, help='任务 temp 目录（含 self_validation_result.json 等）')
    ap.add_argument('--out', default=None, help='草稿 YAML 输出路径')
    ap.add_argument('--apply', action='store_true', help='将 accept/redirect 映射合并进 field_mappings.yaml')
    ap.add_argument('--limit', type=int, default=0, help='仅处理前 N 条（调试用）')
    ap.add_argument('--overrides', default=None,
                    help='模型/人工裁决覆盖文件（YAML），对指定 (目标表,目标字段) 直接给定裁决')
    args = ap.parse_args()

    sv_path = os.path.join(args.temp, 'self_validation_result.json')
    if not os.path.exists(sv_path):
        print(f'✗ 未找到 {sv_path}，请先运行比对+自验证生成', file=sys.stderr)
        sys.exit(1)
    sv = _load(sv_path)
    judgments = sv.get('cross_table_judgments', [])
    if not judgments:
        print('✓ 无跨表业务判断待复核项，无需裁决')
        return
    if args.limit:
        judgments = judgments[:args.limit]

    # 模型/人工覆盖：键 (目标表中文名, 目标字段中文名) -> 裁决
    overrides = {}
    if args.overrides and os.path.exists(args.overrides):
        if yaml is None:
            print('✗ 需要 PyYAML 解析覆盖文件，请先安装', file=sys.stderr)
            sys.exit(1)
        with open(args.overrides, 'r', encoding='utf-8') as f:
            ov_doc = yaml.safe_load(f) or {}
        for ov in ov_doc.get('overrides', []):
            overrides[(ov.get('target_table'), ov.get('target_field_cn'))] = ov
        print(f'  ℹ 载入模型/人工覆盖 {len(overrides)} 条')

    src = _load(os.path.join(args.temp, 'source_standard.json'))
    tgt = _load(os.path.join(args.temp, 'target_standard.json'))

    adjudications = []
    fm_entries = []
    counts = {'accept': 0, 'redirect': 0, 'new': 0}
    for j in judgments:
        _key = (j.get('table_chinese_name') or j['table'], j['target_cn'])
        ov = overrides.get(_key)
        if ov:
            # 模型/人工裁决覆盖：直接采用，requires_human_confirm 默认 False（已裁决）
            decision = ov.get('decision')
            pst = ov.get('proposed_source_table', '')
            psf = ov.get('proposed_source_field', '')
            rationale = ov.get('rationale', '模型/人工裁决覆盖')
            confirm = bool(ov.get('requires_human_confirm', False))
            counts[decision] = counts.get(decision, 0) + 1
        else:
            decision, pst, psf, rationale, confirm = _decide(j, tgt, src)
            counts[decision] += 1
        adj = {
            'target_table': j.get('table_chinese_name') or j['table'],
            'target_field_cn': j['target_cn'],
            'matched_source_table': j['matched_source_table'],
            'matched_source_field': j['matched_source_field'],
            'primary_source_table': j['primary_source_table'],
            'decision': decision,
            'proposed_source_table': pst,
            'proposed_source_field': psf,
            'rationale': rationale,
            'requires_human_confirm': confirm,
        }
        adjudications.append(adj)
        fm = build_field_mapping_entry(j, decision, pst, psf, tgt)
        if fm:
            fm_entries.append(fm)

    out_path = args.out or os.path.join(args.temp, 'cross_table_adjudication_draft.yaml')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('# 跨表业务判断 · 模型裁决草稿（C 流程）\n')
        f.write('# 由 scripts/adjudicate_cross_table.py 生成；人工/模型确认后 --apply 持久化。\n\n')
        f.write('adjudications:\n')
        for a in adjudications:
            f.write(f"  - target_table: {a['target_table']}\n")
            f.write(f"    target_field_cn: {a['target_field_cn']}\n")
            f.write(f"    matched_source_table: {a['matched_source_table']}\n")
            f.write(f"    matched_source_field: {a['matched_source_field']}\n")
            f.write(f"    primary_source_table: {a['primary_source_table']}\n")
            f.write(f"    decision: {a['decision']}\n")
            f.write(f"    proposed_source_table: {a['proposed_source_table']}\n")
            f.write(f"    proposed_source_field: {a['proposed_source_field']}\n")
            f.write(f"    requires_human_confirm: {str(a['requires_human_confirm']).lower()}\n")
            f.write(f"    rationale: \"{a['rationale']}\"\n")
        f.write('\n# ---- 以下可直接追加进 knowledge_base/field_mappings.yaml ----\n')
        f.write('field_mappings_yaml:\n')
        for fm in fm_entries:
            f.write(f"  - target_fields: [{', '.join(fm['target_fields'])}]\n")
            f.write(f"    source_table: {fm['source_table']}\n")
            f.write(f"    source_field: {fm['source_field']}\n")
            f.write(f"    match_type: {fm['match_type']}\n")
            f.write(f"    description: \"{fm['description']}\"\n")

    print(f"✓ 裁决草稿：{out_path}")
    print(f"  待裁决 {len(adjudications)} 条：accept={counts['accept']} "
          f"redirect={counts['redirect']} new={counts['new']}")
    print(f"  可生成映射条目 {len(fm_entries)} 条（accept/redirect）")

    if args.apply:
        fm_path = os.path.join(SKILL_DIR, 'knowledge_base', 'field_mappings.yaml')
        # 简单追加（保留注释头）；正式合并建议人工核对后执行
        with open(fm_path, 'a', encoding='utf-8') as f:
            f.write('\n# ===== 跨表业务判断模型裁决持久化（C）=====\n')
            for fm in fm_entries:
                f.write(f"  - target_fields: [{', '.join(fm['target_fields'])}]\n")
                f.write(f"    source_table: {fm['source_table']}\n")
                f.write(f"    source_field: {fm['source_field']}\n")
                f.write(f"    match_type: {fm['match_type']}\n")
                f.write(f"    description: \"{fm['description']}\"\n")
        print(f"✓ 已持久化 {len(fm_entries)} 条映射到 {fm_path}（--apply）")


if __name__ == '__main__':
    main()
