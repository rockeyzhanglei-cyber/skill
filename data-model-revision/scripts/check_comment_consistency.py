#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BMS 配套脚本注释一致性检查（DDL ↔ 修订记录）

规范来源：references/bms-script-spec.md《注释规范（DDL 与修订记录统一约束）》

检查项：
  1. 各 DDL 脚本顶部 /* */ 变更清单 与 修订记录头部清单：条数、顺序、文字逐字一致
  2. edsm_revise_record.summary 与头部清单逐字一致（多条用 \\n 连接）
  3. DDL 每条 alter/create 前的语句级注释 = 清单中对应那条
  4. 修订记录每条 edsm_revise_detail 前的语句级注释主句（' · ' 之前）在清单内，且顺序与清单一致
  5. 需求号三处一致：文件名 / -- 需求: / require_no
  6. 变更描述符合模板：{表中文名}[{表英文名}]{操作}...（] 后无空格）
  7. 字段项语法（详细式 [代码,填报要求,...] 各分量位置正确、只在顶层逗号分隔）
  8. 批量排版规则：同表加/删多个字段用顿号合一行；修改字段不得合在一行（每个字段独立）

用法：
  python3 check_comment_consistency.py \
      --ddl  <doris.sql> [<greenplum.sql> ...] \
      --revise <insert_revise_record_xxx.sql>

退出码：0 全部通过；1 存在不一致
"""
import argparse
import re
import sys
from pathlib import Path

OK = "  [OK] "
NG = "  [NG] "
WARN = "  [!!] "

# 变更描述模板：表中文名[TABLE_EN]操作... ，] 后不得有空格
DESC_RE = re.compile(r'^[^\[\]]+\[[A-Z0-9_]+\](?! )')

# 字段项：[代码, 填报要求, 数据类型, 表示格式, ...]；仅代码必填，其余按数据模型有值才写
# 合法"填报要求"取值（部分），用于校验第2分量（写全式时）
REQ_SET = {"O", "M", "必填", "应填", "条件必填", "空白", ""}
# 合法数据类型前缀（SQL 类型 + 卫生信息 S/N/C 体系），用于校验第3分量
DT_RE = re.compile(r'^(VARCHAR2?|CHAR|NUMBER|INT|INTEGER|DECIMAL|BIGINT|TIMESTAMP|DATE|TEXT|C[0-9]|N[0-9]|S[0-9]|AN?\.'
                   r'|XM|J[0-9]|T[0-9]|BLOB)', re.IGNORECASE)
FIELD_DETAILED_HEAD = re.compile(r'^[^\[\]]+\[[A-Z0-9_]+\](?! )')


def split_fields(body):
    """把顿号分隔的字段清单拆成单个字段项文本（仅在顶层 [] 外按 、 切分）。"""
    out, depth, cur = [], 0, ""
    for ch in body:
        if ch == "[":
            depth += 1
            cur += ch
        elif ch == "]":
            depth -= 1
            cur += ch
        elif ch == "、" and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


def extract_field_items(desc):
    """从一条变更描述里抽出所有 [..] 字段项（字符串），供语法校验。"""
    return re.findall(r"\[([^\[\]]*)\]", desc)


def read(p):
    return Path(p).read_text(encoding="utf-8")


def top_list(sql):
    """取脚本顶部 /* */ 注释块内的编号清单"""
    m = re.match(r"\s*/\*\s*\n(.*?)\n\s*\*/", sql, re.S)
    if not m:
        return []
    items = []
    for line in m.group(1).strip().split("\n"):
        line = line.strip()
        if line:
            items.append(line)
    return items


def strip_no(item):
    """去掉 '1. ' 编号前缀"""
    return re.sub(r"^\d+\.\s*", "", item)


def ddl_stmt_comments(sql):
    """DDL 语句级注释：Doris 用 /* */，Greenplum 用 --（排除顶部清单块）"""
    body = re.sub(r"\A\s*/\*.*?\*/", "", sql, count=1, flags=re.S)
    out = []
    out += [c.strip() for c in re.findall(r"/\*\s*(.+?)\s*\*/", body)]
    out += [l[2:].strip() for l in body.split("\n") if l.strip().startswith("--")]
    return out


def revise_stmt_comments(sql):
    body = re.sub(r"\A\s*/\*.*?\*/", "", sql, count=1, flags=re.S)
    return [c.strip() for c in re.findall(r"/\*\s*(.+?)\s*\*/", body) if "##" not in c]


def check(ddl_paths, revise_path):
    errors = []
    rev = read(revise_path)
    rev_list = top_list(rev)
    if not rev_list:
        # 单条变更走三行式：第 1 行 -- {变更描述}
        first = rev.strip().split("\n")[0].strip()
        if first.startswith("--") and not first.startswith("-- 集合") and not first.startswith("-- 需求"):
            rev_list = [first[2:].strip()]
    if not rev_list:
        errors.append("修订记录脚本缺少头部变更清单（/* */ 编号清单 或 -- 单行描述）")
        rev_list = []

    print(f"修订记录清单（{len(rev_list)} 条）:")
    for i in rev_list:
        print("   ", i)

    # 1. DDL 清单一致
    for p in ddl_paths:
        d = top_list(read(p))
        name = Path(p).name
        if d == rev_list:
            print(OK + f"{name} 顶部清单与修订记录逐字一致")
        else:
            errors.append(f"{name} 顶部清单与修订记录不一致\n      DDL   : {d}\n      修订记录: {rev_list}")
            print(NG + f"{name} 顶部清单与修订记录不一致")

    # 2. summary
    m = re.search(r"insert into edsm_revise_record\(([^)]*)\)\s*values\((.*?)\);", rev, re.S)
    if m:
        cols = [c.strip() for c in m.group(1).split(",")]
        raw = m.group(2)
        try:
            idx = cols.index("summary")
        except ValueError:
            idx = -1
        # 简易按顶层逗号切分（值均为 '...' 或 数字/null）
        vals, buf, in_q = [], "", False
        i = 0
        while i < len(raw):
            ch = raw[i]
            if ch == "'":
                if in_q and i + 1 < len(raw) and raw[i + 1] == "'":
                    buf += "''"
                    i += 2
                    continue
                in_q = not in_q
                buf += ch
            elif ch == "," and not in_q:
                vals.append(buf.strip())
                buf = ""
            else:
                buf += ch
            i += 1
        vals.append(buf.strip())
        if 0 <= idx < len(vals):
            summary = vals[idx].strip("'")
            expect = "\\n".join(rev_list)
            if summary == expect:
                print(OK + "summary 与头部清单逐字一致")
            else:
                errors.append(f"summary 与头部清单不一致\n      summary : {summary}\n      期望    : {expect}")
                print(NG + "summary 与头部清单不一致")
    else:
        errors.append("未找到 edsm_revise_record 插入语句")

    # 3. DDL 语句级注释
    bare = [strip_no(x) for x in rev_list]
    for p in ddl_paths:
        cs = [c for c in ddl_stmt_comments(read(p)) if c]
        # 排除修订记录式头部行（集合/需求/字段/说明）
        cs = [c for c in cs if not (c.startswith("集合:") or c.startswith("需求:") or c.startswith("字段:") or c.startswith("说明:"))]
        name = Path(p).name
        bad = [c for c in cs if c not in bare]
        if bad:
            errors.append(f"{name} 语句级注释不在清单内: {bad}")
            print(NG + f"{name} 语句级注释不在清单内: {bad}")
        else:
            print(OK + f"{name} 语句级注释均取自清单（{len(cs)} 条）")

    # 4. 修订记录语句级注释顺序
    rcs = revise_stmt_comments(rev)
    mains = [c.split(" · ")[0].strip() for c in rcs]
    bad = [c for c in mains if c not in bare]
    if bad:
        errors.append(f"修订记录语句级注释主句不在清单内: {bad}")
        print(NG + f"修订记录语句级注释主句不在清单内: {bad}")
    else:
        seq, seen = [], set()
        for c in mains:
            if c not in seen:
                seen.add(c)
                seq.append(c)
        if seq == bare:
            print(OK + f"修订记录明细顺序与清单一致（{len(rcs)} 条明细注释）")
        else:
            errors.append(f"修订记录明细顺序与清单错位\n      明细顺序: {seq}\n      清单顺序: {bare}")
            print(NG + "修订记录明细顺序与清单错位")

    # 5. 需求号一致性（文件名 ↔ require_no 必须一致；-- 需求: 行可选，若存在须一致）
    fn = re.search(r"_(\d{5,})\.sql$", Path(revise_path).name)
    hd = re.search(r"--\s*需求[:：]\s*(\d+)", rev)
    rq = re.search(r"'(\d{5,})','(?:[^']|'')*',1,", rev)
    nums = {
        "文件名": fn.group(1) if fn else None,
        "头部注释(-- 需求:)": hd.group(1) if hd else None,
        "require_no": rq.group(1) if rq else None,
    }
    present = [v for v in nums.values() if v]
    if present and len(set(present)) == 1:
        extra = f" / 头部注释" if hd else ""
        print(OK + f"需求号一致(文件名 / require_no{extra}): {present[0]}")
    else:
        errors.append(f"需求号不一致或缺失: {nums}")
        print(NG + f"需求号不一致或缺失: {nums}")

    # 6. 描述模板 + 字段项语法 + 批量排版规则
    bad_fmt = []
    bad_field = []
    bad_batch = []
    for x in bare:
        # 跳过"值集修订"整行（值域-XXX新增值 / 值修改为）与 新增表；
        # 注意：字段修改里出现"（值域 …）"不算值集行，必须继续校验
        if "新增表" in x or re.match(r'^值域-', x) or "新增值：" in x or "值修改为：" in x:
            continue
        if not DESC_RE.match(x):
            bad_fmt.append(x)
            continue
        # 字段项语法：[] 内顶层逗号分隔、各分量非空、首尾为字段代码
        items = extract_field_items(x)
        if not items:
            bad_field.append(f"{x} 缺少 [字段项]")
            continue
        for it in items:
            parts = [p.strip() for p in it.split(",")]
            if not parts or not parts[0]:
                bad_field.append(f"{x} 字段项『[{it}]』首分量(字段代码)为空")
                continue
            if any(p == "" for p in parts[1:]):
                bad_field.append(f"{x} 字段项『[{it}]』含空分量（连续逗号或首尾逗号）")
                continue
            # 写全式（≥2 分量）时校验顺序：第2=填报要求、第3=数据类型、第4=表示格式
            if len(parts) >= 2 and parts[1] not in REQ_SET:
                bad_field.append(f"{x} 字段项『[{it}]』第2分量应为填报要求之一(O/M/必填/应填/条件必填/空白)，实际『{parts[1]}』")
            if len(parts) >= 3 and not DT_RE.match(parts[2]):
                bad_field.append(f"{x} 字段项『[{it}]』第3分量应为数据类型（如 VARCHAR(50)/S3/N..3,1），实际『{parts[2]}』")
        # 批量排版规则
        if "新增字段" in x or "删除字段" in x:
            if "、" in x and "新增字段：" in x:
                # 校验顿号确实在字段项之间（每个 、后应为 字段中文[）
                body = x.split("：", 1)[1] if "：" in x else x
                segs = split_fields(body)
                rest = segs[1:]
                for r in rest:
                    if not re.match(r'^[^\[\]]+\[', r):
                        bad_batch.append(f"{x} 顿号分隔处格式异常：『{r}』")
        elif "修改字段" in x:
            # 修改字段：每个字段独立一行，不得用顿号/、连接多个字段
            if "、" in x and re.search(r"修改字段[：:].*?[、].*?[\u4e00-\u9fff]+\[", x):
                bad_batch.append(f"{x} 修改字段不得用顿号合并多字段，应每行一个字段")
            elif "、" in x:
                bad_batch.append(f"{x} 修改字段不得用顿号合并多字段，应每行一个字段")
    if bad_fmt:
        errors.append(f"变更描述不符合模板 {{表中文名}}[{{TABLE_EN}}]{{操作}}（] 后禁空格）: {bad_fmt}")
        print(NG + f"变更描述不符合模板: {bad_fmt}")
    else:
        print(OK + "变更描述均符合模板（] 后无空格）")
    if bad_field:
        errors.append(f"字段项语法错误: {bad_field}")
        print(NG + f"字段项语法错误: {bad_field}")
    else:
        print(OK + "字段项语法正确（] 内顶层逗号分隔、各分量非空）")
    if bad_batch:
        errors.append(f"批量排版违规: {bad_batch}")
        print(NG + f"批量排版违规: {bad_batch}")
    else:
        print(OK + "批量排版合规（加/删可顿号合一行；修改字段逐行）")

    return errors


def main():
    ap = argparse.ArgumentParser(description="BMS 配套脚本注释一致性检查")
    ap.add_argument("--ddl", nargs="+", required=True, help="DDL 脚本路径（可多个库）")
    ap.add_argument("--revise", required=True, help="修订记录脚本路径")
    a = ap.parse_args()

    print("=" * 60)
    print("BMS 注释一致性检查（DDL ↔ 修订记录）")
    print("=" * 60)
    errs = check(a.ddl, a.revise)
    print("-" * 60)
    if errs:
        print(f"不通过：{len(errs)} 项问题")
        for e in errs:
            print("  * " + e)
        sys.exit(1)
    print("全部通过")
    sys.exit(0)


if __name__ == "__main__":
    main()
