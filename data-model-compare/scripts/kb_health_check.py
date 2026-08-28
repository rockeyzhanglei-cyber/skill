#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""知识库体检：找出 user_custom_mappings.yaml 里的脏正向映射。

背景
----
知识库里的正向映射是**人工领域判断**，人是权威，比对期不能靠启发式静默否决
（实测：语义硬冲突网关只抓到 1/3 真错，却误杀约 40 条正确人工确认）。
正确做法是把可疑条目挑出来给人复核，把脏数据修在知识库里。

三类相互独立的证据（**按强度加权**，总分越高越可疑）
--------------------------------------------------
E1a 强语义冲突(2分): 字段种类冲突 / 核心概念缺失
                    —— 一侧是裸通用词（姓名、编号），另一侧带实质限定。
                    这是人工误点最典型的形态：主治医师姓名 ← 姓名
E1b 弱语义冲突(1分): 核心概念不相干（双方都有限定但不搭）
                    —— 也可能是合理的领域判断，单独出现时不足以定罪
E2  库内自相矛盾(1分): 同一目标字段在库里有多条非空映射，本条落在少数簇
                    （生产批号 → {批号, 生产批号, 批准文号}，批准文号离群）
                    **豁免**：若多数簇的源字段名在本条的源表里根本不存在，
                    说明人工是"没有同名字段才退而用别名"，属正常，不计分。
                    （就诊类型代码 ← 门诊/住院标志：源表没有"就诊类型代码"）
E3  同表同名重复(2分): 源字段 X 在本表已归属同名目标字段 X，却又被给了别的字段
                    （会诊记录-会诊医师：姓名 既给了 姓名 又给了 门(急)诊号）

用法
----
  python scripts/kb_health_check.py                 # 全库体检
  python scripts/kb_health_check.py --min-score 2   # 只看≥2分的（推荐）
  # 带上源标准可开启 E2 豁免，显著降低误报：
  python scripts/kb_health_check.py --min-score 2 \
      --source <temp>/source_standard.json
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_DIR))

from matchers.standard_comparator import StandardComparator as SC  # noqa: E402


def _grams(s):
    return {s[i:i + 2] for i in range(len(s) - 1)} or ({s} if s else set())


def _related(a, b):
    """两个源字段名是否属于同一概念簇。"""
    na, nb = SC._global_norm_base(a), SC._global_norm_base(b)
    if not na or not nb:
        return False
    if na in nb or nb in na:
        return True
    return bool(_grams(na) & _grams(nb))


def _clusters(values):
    """按概念相关性做并查集聚类，返回按总权重降序的簇列表。"""
    uniq = list(dict.fromkeys(values))
    parent = list(range(len(uniq)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i in range(len(uniq)):
        for j in range(i + 1, len(uniq)):
            if _related(uniq[i], uniq[j]):
                pi, pj = find(i), find(j)
                if pi != pj:
                    parent[pi] = pj
    buckets = defaultdict(list)
    for i, v in enumerate(uniq):
        buckets[find(i)].append(v)
    cls = list(buckets.values())
    cls.sort(key=lambda c: -sum(values.count(x) for x in c))
    return cls


def _e1a_exempt(comp, reason, tf, sf, tt, st):
    """E1a（裸通用词/种类冲突）的两类正常形态豁免。

    (a) 表主语补全：被剥空一侧的"实质限定词"本就存在于表名里，
        说明人工是用"表主语 + 通用词"补全的，属正常。
        医护人员信息表：人员姓名 <- 姓名；转科记录：记录类别 <- 转科记录类型
    (b) 签名↔姓名 子类：主体相同或包含，比对器已认可，不必再报。
        接诊医师姓名 <- 医师签名
    """
    if reason in ('字段种类冲突', '核心概念缺失'):
        nt, ns = SC._p5_norm(tf), SC._p5_norm(sf)
        ct, cs = comp._strip_generic(nt), comp._strip_generic(ns)
        # 谁有实质限定，就检查它是否落在某侧表名里
        for core, tbl in ((ct, tt), (cs, st)):
            if core and tbl and core in SC._p5_norm(tbl):
                return True
    return False


def _e3_exempt(comp, tf, sf):
    """E3 的两类正常形态豁免（一源多目标本身并不必然是脏数据）。

    (a) 派生字段：源字段名整体是目标字段名的子串（或反之）
        建议 -> 体检建议、Rh血型代码 -> 申请Rh血型代码、出院科室代码 -> 院内出院科室代码
    (b) 主子表流水号继承：同为流水号/标识类，且核心概念共享 ≥2 字前缀
        会诊记录流水号 -> 会诊医师流水号、治疗记录流水号 -> 治疗诊断记录流水号
    其余（不良事件类别代码 -> 不良事件报告医师姓名）一律照旧报出。
    """
    nt, ns = SC._p5_norm(tf), SC._p5_norm(sf)
    if ns and nt and (ns in nt or nt in ns):
        return True
    kt, ks = SC._field_kind_of(nt), SC._field_kind_of(ns)
    serialish = SC._FIELD_KIND_SERIAL | SC._FIELD_KIND_IDENT
    if kt and kt == ks and kt in serialish:
        ct, cs = comp._strip_generic(nt), comp._strip_generic(ns)
        n = 0
        for a, b in zip(ct, cs):
            if a != b:
                break
            n += 1
        if n >= 2:
            return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--kb', default=str(SKILL_DIR / 'knowledge_base' /
                                       'user_custom_mappings.yaml'))
    ap.add_argument('--min-score', type=int, default=1)
    ap.add_argument('--source', default='',
                    help='source_standard.json，用于开启 E2 豁免（降误报）')
    ap.add_argument('--out', default=str(SKILL_DIR / 'knowledge_base' /
                                        'kb_health_report.json'))
    args = ap.parse_args()

    # ---- 源标准字段索引（可选，用于 E2 豁免）----
    src_fields = {}     # 源表中文名 -> {字段中文名归一}
    if args.source and Path(args.source).exists():
        sd = json.loads(Path(args.source).read_text(encoding='utf-8'))
        for t in sd.get('tables', []):
            key = t.get('chinese_name') or t.get('name') or ''
            names = {SC._p5_norm(f.get('chinese_name') or '')
                     for f in t.get('fields', [])}
            src_fields.setdefault(key, set()).update(names - {''})
        print(f'已加载源标准 {len(src_fields)} 表，E2 豁免已启用')

    import yaml
    kb = yaml.safe_load(Path(args.kb).read_text(encoding='utf-8'))
    mappings = kb.get('mappings') or []
    print(f'知识库: {args.kb}')
    print(f'created_from: {kb.get("created_from")}')
    print(f'映射总数: {len(mappings)}  （其中非空正向映射 '
          f'{sum(1 for m in mappings if (m.get("source_field") or "").strip())} 条）\n')

    # ---- 分组索引 ----
    by_target = defaultdict(list)               # 目标字段中文名 -> [源字段…]
    by_table_src = defaultdict(set)             # (目标表, 源字段) -> {目标字段…}
    def _is_placeholder(v):
        # [主子表映射:diagnosis_numbered] 这类是机制占位符，不是真实源字段
        return v.startswith('[') or v.startswith('<')

    for m in mappings:
        sf = (m.get('source_field') or '').strip()
        if not sf or _is_placeholder(sf):
            continue
        by_target[m['target_field']].append(sf)
        by_table_src[(m['target_table'], sf)].add(m['target_field'])

    cluster_cache = {}
    comp = SC()   # 只借用判据方法，不做比对

    class _F:
        """给判据方法喂的最小字段对象。"""
        def __init__(self, cn):
            self.chinese_name = cn
            self.name = ''
            self.description = ''

    rows = []
    seen_keys = set()
    for m in mappings:
        # 按 (目标字段, 源字段) 去重：同一对映射可能因出现在多张表而有多行，
        # 去重后只报一次，用 ×N表 标注覆盖表数（避免重复计分/重复清单）
        key = (m.get('target_field'), (m.get('source_field') or '').strip())
        if key in seen_keys:
            continue
        seen_keys.add(key)
        sf = (m.get('source_field') or '').strip()
        tf = m.get('target_field') or ''
        if not sf or not tf or _is_placeholder(sf):
            continue

        evidence = []
        score = 0
        # E1 语义硬冲突（分强弱）
        e1 = comp._user_custom_hard_conflict(_F(tf), _F(sf))
        if e1:
            if _e1a_exempt(comp, e1, tf, sf,
                           m.get('target_table', ''), m.get('source_table', '')):
                e1 = ''   # 表主语补全等正常形态，不计分
            else:
                strong = e1 in ('字段种类冲突', '核心概念缺失')
                w = 2 if strong else 1
                score += w
                evidence.append(f'E1{"a" if strong else "b"}({w}分):{e1}')

        # E2 知识库自相矛盾
        vals = by_target[tf]
        if len(set(vals)) > 1:
            if tf not in cluster_cache:
                cluster_cache[tf] = _clusters(vals)
            cls = cluster_cache[tf]
            if len(cls) > 1 and sf not in cls[0]:
                # 豁免：多数簇的名字在本条源表里压根不存在 -> 人工用别名是合理的
                pool = src_fields.get(m.get('source_table') or '')
                exempt = bool(pool) and not any(SC._p5_norm(x) in pool
                                                for x in cls[0])
                if not exempt:
                    score += 1
                    evidence.append(f'E2(1分):与多数簇{cls[0]}矛盾')

        # E3 同表已存在"同名归属"：源字段 X 在本表已经映射给了目标字段 X，
        #    却又被映射给另一个目标字段 -> 后者很可能是误点。
        #    （不良事件类别名称 已给 不良事件类别名称，又给了 不良事件报告医师姓名）
        siblings = set(by_table_src[(m['target_table'], sf)]) - {tf}
        if siblings:
            nsf = SC._p5_norm(sf)
            namesake = [s for s in siblings if SC._p5_norm(s) == nsf]
            if namesake and SC._p5_norm(tf) != nsf and \
                    not _e3_exempt(comp, tf, sf):
                score += 2
                evidence.append(
                    f'E3(2分):同表该源字段已归属同名目标字段{sorted(namesake)}')

        if score >= args.min_score:
            # 置信分层：E1a（裸通用词/种类冲突）或总分≥3 -> 大概率真错；
            # 仅 E3 或 E1b+E2 -> "一源多目标"，属需人工快判的灰区。
            tier = 'A-高置信' if (score >= 3 or any('E1a' in e for e in evidence)) \
                else 'B-待确认'
            rows.append({
                'tier': tier,
                'score': score,
                'target_table': m['target_table'],
                'target_field': tf,
                'source_table': m.get('source_table', ''),
                'source_field': sf,
                'evidence': evidence,
            })

    rows.sort(key=lambda r: (r['tier'], -r['score'],
                             r['target_table'], r['target_field']))

    # 去重展示（同一 目标字段+源字段 只提示一次，附出现次数）
    seen = defaultdict(int)
    for r in rows:
        seen[(r['target_field'], r['source_field'])] += 1
    shown = set()
    n_a = len({(r['target_field'], r['source_field'])
               for r in rows if r['tier'].startswith('A')})
    print(f'=== 待复核条目 {len(rows)} 条（去重后 {len(seen)} 种）'
          f'：A-高置信 {n_a} 种 / B-待确认 {len(seen) - n_a} 种 ===')
    cur = ''
    for r in rows:
        k = (r['target_field'], r['source_field'])
        if k in shown:
            continue
        shown.add(k)
        if r['tier'] != cur:
            cur = r['tier']
            head = ('大概率是误点，建议直接改 yaml' if cur.startswith('A')
                    else '一源对多目标，多为合理派生，人工快判即可')
            print(f'\n---- {cur}（{head}）----')
        n = seen[k]
        print(f"[{r['score']}分] {r['target_field']} <= {r['source_field']}"
              f"  ×{n}表")
        for e in r['evidence']:
            print(f'          {e}')

    Path(args.out).write_text(json.dumps(rows, ensure_ascii=False, indent=2),
                              encoding='utf-8')
    print(f'\n明细已写入 {args.out}')


if __name__ == '__main__':
    main()
