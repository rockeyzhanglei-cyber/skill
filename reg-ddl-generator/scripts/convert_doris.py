# -*- coding: utf-8 -*-
"""GP postgresql 方言 probe → Doris DDL 转换脚本
规则（对齐 BMS edsm_sql/doris 既有脚本风格 + 用户 2026-08-27 确定的规范）：
- do $$ 块展开为裸 SQL；if exists/if not exists 判断丢弃
- alter table t add column c type null; + comment on column t.c is 'x'; → 合并为一条
  alter table t add column c type null comment 'x';
- 同一张表的多个 add column 必须合并为【单条】ALTER 语句（多子句逗号分隔）——
  参考 doris/V20260729153107__alter_table_sign_record_234455.sql 风格。
  Doris 不允许同一张表拆分多条 ALTER，否则部分字段报错。
- 建表 create table t ( → create table if not exists t( ... ) unique key(...) comment '...'
  distributed by hash(首主键列) buckets 8;
  ⚠️ 桶数量固定为 8；【不输出】properties ('replication_num' = '...') 副本数参数（用户明确去除）。
- 字符串长度 ×4（用户 2026-08-28 确定）：Doris 存储 UTF-8 中文，1 个汉字 3 字节、
  1 个特殊字符 4 字节；标准文档长度按【字符数】控制，故 varchar(n)/char(n) 的 n 统一 ×4
  （n 表示字节数），如 varchar(100) → varchar(400)。转换在此层自动完成，
  上游 PostgreSQL probe 保持文档原始长度，不得提前手动 ×4（否则会变成 ×16）。
  校验：所有 varchar/char 长度必须能被 4 整除；最大 4000 → 16000，未超 Doris 65533 上限。
"""
import re, sys, os

def to_doris_type(t: str) -> str:
    """PostgreSQL 类型 → Doris 类型映射。

    PostgreSQL/Greenplum 的定点小数类型是 numeric(p[,s])，但 Doris 只认 decimal(p[,s])，
    原样透传会在 Doris 解析时报 'mismatched input numeric'。此处统一转换。
    Doris 无 TIMESTAMP 类型（仅有 DATE / DATETIME / DATETIMEV2），PG 的 timestamp 转 datetime。
    其它类型（varchar / date / int / text / boolean / json 等）Doris 与 PG 一致，原样保留。
    """
    tl = t.lower()
    if tl.startswith("numeric"):
        return re.sub(r"(?i)numeric", "decimal", t)
    if tl == "timestamp":
        return "datetime"
    return t

def x4_str_len(s: str) -> str:
    """字符串类型长度 ×4：varchar(n) / char(n) → n*4。

    只处理类型定义本身（调用方保证传入的是可执行代码，非注释/字符串字面量内容）。
    """
    def rep(m):
        return "%s(%d)" % (m.group(1), int(m.group(2)) * 4)
    return re.sub(r"\b(varchar|char)\(\s*(\d+)\s*\)", rep, s, flags=re.I)

X4_COUNT = [0]  # 非局部计数器：记录转换了几处长度

def convert(src_path: str, out_path: str) -> str:
    with open(src_path, encoding="utf-8") as f:
        lines = f.read().split("\n")

    out = []
    i = 0
    n = len(lines)
    X4_COUNT[0] = 0

    def emit(s):
        out.append(s)

    create_re = re.compile(r"^\s*create table (\w+) \(")
    field_re = re.compile(r"^\s+(\w+) (varchar\(\d+\)|char\(\d+\)|numeric\([\d,]+\)|date|timestamp|int|text|boolean|json(b)?) (not null|null),?$")
    pk_re = re.compile(r"^\s*constraint \w+ primary key \((.+)\)\s*,?$")
    tbl_comment_re = re.compile(r"^\s*comment on table (\w+) is '(.+)';")
    col_comment_re = re.compile(r"^\s*comment on column (\w+)\.(\w+) is '(.+)';")
    alter_re = re.compile(r"^\s*alter table (\w+) add column (\w+) (\S+) null;$")

    while i < n:
        line = lines[i]
        s = line.strip()

        # 头部注释块（/* ... */）原样保留
        if s.startswith("/*") or (s.startswith("*") and i > 0) or (out and out[-1].startswith("/*")):
            emit(line)
            i += 1
            continue

        # -- 注释行、空行：原样保留
        if s.startswith("--"):
            emit(line)
            i += 1
            continue
        if not s:
            if out and out[-1] != "":
                emit("")
            i += 1
            continue

        # do $$ 块开始：解析到 end $$;
        if s == "do $$":
            j = i + 1
            block_end = None
            for k in range(j, n):
                if lines[k].strip() == "end $$;":
                    block_end = k
                    break
            if block_end is None:
                raise RuntimeError("do $$ 块未闭合 at line %d" % i)
            body = lines[j:block_end]

            create_idx = None
            for b_i, bl in enumerate(body):
                if create_re.match(bl):
                    create_idx = b_i
                    break

            if create_idx is not None:
                # ============ 建表块 ============
                tbl = create_re.match(body[create_idx]).group(1)
                fields = []       # (col, type, nullable)
                pk_cols = None
                tbl_comment = None
                cmap = {}         # col -> comment
                b = create_idx + 1
                while b < len(body):
                    bl = body[b]
                    mf = field_re.match(bl)
                    mp = pk_re.match(bl)
                    mt = tbl_comment_re.match(bl)
                    mc = col_comment_re.match(bl)
                    if mf:
                        raw_t = mf.group(2)
                        # 先 to_doris_type，再字符串长度 ×4
                        dt = to_doris_type(raw_t)
                        if re.match(r"(?i)(varchar|char)\(", dt):
                            dt = x4_str_len(dt)
                            X4_COUNT[0] += 1
                        fields.append((mf.group(1), dt, mf.group(3) != "null"))
                    elif mp:
                        pk_cols = [c.strip() for c in mp.group(1).split(",")]
                    elif mt:
                        tbl_comment = mt.group(2).rstrip("，").rstrip(",").strip()
                    elif mc:
                        cmap[mc.group(2)] = mc.group(3).rstrip("，").rstrip(",").strip()
                    b += 1
                emit(f"create table if not exists {tbl}(")
                fl = []
                for col, typ, nn in fields:
                    c = cmap.get(col, "")
                    nn_s = " not null" if nn else " null"
                    if c:
                        fl.append(f"    {col} {typ}{nn_s} comment '{c}',")
                    else:
                        fl.append(f"    {col} {typ}{nn_s},")
                if fl:
                    fl[-1] = fl[-1].rstrip(",")
                out.extend(fl)
                emit(")")
                if pk_cols:
                    emit(f"unique key({', '.join(pk_cols)})")
                if tbl_comment:
                    emit(f"comment '{tbl_comment}'")
                # distributed by hash(第一个主键列) buckets 8 —— 不加 replication_num
                dist_col = pk_cols[0] if pk_cols else (fields[0][0] if fields else "")
                if dist_col:
                    emit(f"distributed by hash({dist_col}) buckets 8")
                emit(";")
                emit("")
            else:
                # ============ ALTER 块 ============
                adds = []  # (table, col, type, comment)
                cur = None
                for bl in body:
                    bs = bl.strip()
                    ma = alter_re.match(bs)
                    mc = col_comment_re.match(bs)
                    if ma:
                        raw_t = ma.group(3)
                        dt = to_doris_type(raw_t)
                        if re.match(r"(?i)(varchar|char)\(", dt):
                            dt = x4_str_len(dt)
                            X4_COUNT[0] += 1
                        cur = [ma.group(1), ma.group(2), dt, None]
                        adds.append(cur)
                    elif mc and cur and mc.group(1) == cur[0] and mc.group(2) == cur[1]:
                        cur[3] = mc.group(3)
                        cur = None
                    # if exists / if not exists 等行忽略
                # 按表分组合并为单条 ALTER（保持表出现顺序）
                by_tbl = {}
                order = []
                for tbl, col, typ, cmt in adds:
                    if tbl not in by_tbl:
                        by_tbl[tbl] = []
                        order.append(tbl)
                    by_tbl[tbl].append((col, typ, cmt))
                for tbl in order:
                    emit(f"alter table {tbl}")
                    items = by_tbl[tbl]
                    for idx, (col, typ, cmt) in enumerate(items):
                        c_s = f" comment '{cmt}'" if cmt else ""
                        sep = ";" if idx == len(items) - 1 else ","
                        emit(f"    add column {col} {typ} null{c_s}{sep}")
                    emit("")
            i = block_end + 1
            continue

        # 其它未识别行：原样保留
        emit(line)
        i += 1

    result = "\n".join(out)
    result = re.sub(r"\n{3,}", "\n\n", result)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(result)

    alters = result.count("alter table ")
    creates = result.count("create table if not exists ")
    print("Doris 输出:", out_path)
    print("总行数:", len(result.split("\n")))
    print("alter table 条数:", alters)
    print("create table 条数:", creates)
    print("字符串长度 ×4 处数:", X4_COUNT[0])
    # 自检：可执行代码区残留的 varchar/char 长度必须全部能被 4 整除
    bad = []
    for ln, l in enumerate(result.split("\n"), 1):
        if l.strip().startswith("--") or l.strip().startswith("/*") or l.strip().startswith("*"):
            continue
        for m in re.finditer(r"\b(varchar|char)\((\d+)\)", l, re.I):
            if int(m.group(2)) % 4 != 0:
                bad.append((ln, l.strip()[:110]))
    if bad:
        print("⚠️ 警告：仍有 %d 处字符串长度非 4 倍数（应全部 ×4）：" % len(bad))
        for ln, l in bad[:20]:
            print("  第%d行: %s" % (ln, l))
    if "replication_num" in result:
        print("⚠️ 警告：输出仍包含 replication_num，请检查！")
    if "buckets 1" in result:
        print("⚠️ 警告：输出仍包含 buckets 1，请检查！")
    return result

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法: python3 convert_doris.py <GP_postgresql_probe.sql> <输出.sql>")
        sys.exit(1)
    convert(sys.argv[1], sys.argv[2])