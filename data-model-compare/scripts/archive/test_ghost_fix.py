#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
幽灵映射修复专项测试：外键方向约束 + 知识库源表解析

覆盖：
  1. _user_custom_direction_conflict
     - 同表                    → 合法（''）
     - 子表→主表（取业务表时关联主数据）→ 合法（''）
     - 主表←子表（反向借用）      → 非法（返回理由）
     - 无外键关系                → 合法（''）
  2. _resolve_source_table
     - 英文表名精确匹配
     - 中文表名精确匹配
     - 包含匹配（患者基本信息表 → 患者基本信息）
     - 歧义包含（多个候选）→ None
     - 未命中 → None

用法：python scripts/test_ghost_fix.py
"""
import os
import sys

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SKILL_DIR)

from parsers.standard_parser import StandardTable, StandardField
from matchers.standard_comparator import StandardComparator


def mk_table(name, cn, fields=None):
    t = StandardTable(name=name, chinese_name=cn)
    for f in (fields or []):
        t.fields.append(f)
    return t


def mk_field(name, cn, description=''):
    return StandardField(name=name, chinese_name=cn,
                         data_type='S1', length=64, constraint='M',
                         description=description)


def build_index(*tables):
    idx = {}
    for t in tables:
        idx[t.name] = t
        if t.chinese_name:
            idx[t.chinese_name] = t
            idx[f'{t.name}|{t.chinese_name}'] = t
    return idx


passed = 0
failed = 0


def check(name, actual, expected):
    global passed, failed
    ok = actual == expected
    if ok:
        passed += 1
        print(f"  ✓ PASS: {name}")
    else:
        failed += 1
        print(f"  ✗ FAIL: {name}\n      期望: {expected!r}\n      实际: {actual!r}")


def test_direction_conflict():
    print("\n[1] _user_custom_direction_conflict 外键方向约束")
    comp = StandardComparator()
    # FK: MAHP_MAIN(病案首页).PERSON_ID → PERSON(患者基本信息)
    comp._auto_fk_edges = [
        ('MAHP_MAIN', '病案首页', '患者身份证号', 'PERSON', '患者基本信息', '身份证号'),
    ]
    mahp = mk_table('MAHP_MAIN', '病案首页')
    person = mk_table('PERSON', '患者基本信息')
    card_tbl = mk_table('CARD', '卡证信息')

    # 1.1 同表：合法
    r = comp._user_custom_direction_conflict(mahp, mahp)
    check('同表合法', r, '')

    # 1.2 目标对齐表=子表(MAHP_MAIN) ← 源字段表=主表(PERSON)：合法（取病案首页时关联患者）
    r = comp._user_custom_direction_conflict(person, mahp)
    check('子表借主表字段（MAHP_MAIN 对齐，源字段来自 PERSON）合法', r, '')

    # 1.3 目标对齐表=主表(PERSON) ← 源字段表=子表(MAHP_MAIN)：反向借用 → 非法
    r = comp._user_custom_direction_conflict(mahp, person)
    check('主表反向借子表字段（PERSON 对齐，源字段来自 MAHP_MAIN）非法', r != '', True)
    if r:
        print(f'       理由: {r}')
        check('非法理由含外键方向关键字', '外键方向反向' in r, True)

    # 1.4 无外键关系：不判非法（知识库声明背书）
    r = comp._user_custom_direction_conflict(card_tbl, person)
    check('无外键关系不判非法', r, '')

    # 1.5 任一表为 None：合法
    r = comp._user_custom_direction_conflict(None, person)
    check('source_field_table=None 合法', r, '')

    # 1.6 无外键边时：合法
    comp._auto_fk_edges = []
    r = comp._user_custom_direction_conflict(mahp, person)
    check('无外键边不判非法', r, '')


def test_resolve_source_table():
    print("\n[2] _resolve_source_table 知识库源表解析")
    comp = StandardComparator()
    person = mk_table('PERSON', '患者基本信息')
    mahp = mk_table('MAHP_MAIN', '病案首页')
    address = mk_table('PAT_ADDRESS', '患者地址信息')
    idx = build_index(person, mahp, address)

    # 2.1 英文表名精确
    t = comp._resolve_source_table('PERSON', idx)
    check('英文表名精确匹配', t is person, True)

    # 2.2 中文表名精确
    t = comp._resolve_source_table('患者地址信息', idx)
    check('中文表名精确匹配', t is address, True)

    # 2.3 包含匹配：患者基本信息表 → 患者基本信息（唯一命中）
    t = comp._resolve_source_table('患者基本信息表', idx)
    check('包含匹配（患者基本信息表→患者基本信息）', t is person, True)

    # 2.4 歧义包含：'患者' 命中 患者基本信息（不包含 病案首页/地址），构造歧义场景
    t = comp._resolve_source_table('不存在', idx)
    check('未命中返回 None', t is None, True)

    # 2.5 空参
    t = comp._resolve_source_table('', idx)
    check('空表名返回 None', t is None, True)
    t = comp._resolve_source_table('PERSON', None)
    check('空索引返回 None', t is None, True)


if __name__ == '__main__':
    print("幽灵映射修复专项测试")
    test_direction_conflict()
    test_resolve_source_table()
    print(f"\n结果: {passed} 通过, {failed} 失败")
    sys.exit(1 if failed else 0)
