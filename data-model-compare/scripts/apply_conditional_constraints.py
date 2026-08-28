#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
条件式值域约束装配脚本（round6 固化）。

背景：round2 曾一次性往 iter_compare_result.json 注入 46 条 condition_display
（地址族 03/06/01 + 电话族 01/02），但未固化到代码，round4/5 重跑比对后全部
丢失。本脚本将装配逻辑固化为通用工具，在比对结果写盘后自动调用。

规则来源：<temp_dir>/conditional_constraints.json（v2 结构）：
  conditions: {COND_EN: {table, chinese_name, values: {code: name}}}
  rules: [{tables: [...], field_prefix 或 field, cond, value}]

装配格式（与报告渲染一致）：
  地址类别代码[ADDRESS_TYPE_CODE]=03[家庭常住住址]
  联系方式类别代码[CONT_TYPE_CODE]=01[手机]

幂等：首次运行前备份为 <cmp>.bak_pre_cond；重复运行重新装配（覆盖同值）。
matched / modified 均装配；Excel（读 iter_compare_result.json）同步生效。

用法：
  python scripts/apply_conditional_constraints.py <temp_dir>
"""
import json
import os
import shutil
import sys


def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def apply_condition_display(temp_dir: str):
    """按 conditional_constraints.json 的 rules 给比对结果装配 condition_display。

    Returns:
        装配完成后的 iter_compare_result dict（含 condition_display）；
        无配置/无规则/出错返回 None（不修改文件）。
    """
    temp = os.path.expanduser(temp_dir)
    cmp_path = os.path.join(temp, 'iter_compare_result.json')
    cfg_path = os.path.join(temp, 'conditional_constraints.json')
    if not os.path.exists(cmp_path):
        print(f'[条件装配] [ERR] 缺少 {cmp_path}')
        return None
    if not os.path.exists(cfg_path):
        print('[条件装配] 无 conditional_constraints.json，跳过条件装配')
        return None

    cfg = load_json(cfg_path)
    conditions = cfg.get('conditions') or {}
    rules = cfg.get('rules') or []
    if not rules:
        print('[条件装配] 配置无 rules，跳过条件装配')
        return None

    # 幂等备份（仅首次）
    bak = cmp_path + '.bak_pre_cond'
    if not os.path.exists(bak):
        shutil.copy2(cmp_path, bak)
        print(f'[条件装配] 备份 -> {bak}')

    cr = load_json(cmp_path)
    n = 0
    for kind in ('matched', 'modified'):
        for item in cr.get(kind, []):
            tname = item.get('table_name', '') or ''
            tfield = (item.get('target_field')
                      or item.get('field_name') or '') or ''
            if not tfield:
                continue
            for r in rules:
                if tname not in (r.get('tables') or []):
                    continue
                fp = r.get('field_prefix') or ''
                fexact = r.get('field') or ''
                hit = bool(fexact and tfield == fexact) or bool(
                    fp and tfield.startswith(fp))
                if not hit:
                    continue
                cond_en = r.get('cond') or ''
                cond = conditions.get(cond_en)
                if not cond:
                    continue
                val = str(r.get('value', ''))
                vname = (cond.get('values') or {}).get(val, '')
                disp = f"{cond.get('chinese_name', '') or cond_en}[{cond_en}]={val}"
                if vname:
                    disp += f'[{vname}]'
                item['condition_display'] = disp
                n += 1
                break

    with open(cmp_path, 'w', encoding='utf-8') as f:
        json.dump(cr, f, ensure_ascii=False, indent=2)
    print(f'[条件装配] 注入 condition_display {n} 条 -> {cmp_path}')
    return cr


def main():
    if len(sys.argv) < 2:
        print('用法: python apply_conditional_constraints.py <temp_dir>')
        return 1
    return 0 if apply_condition_display(sys.argv[1]) is not None else 1


if __name__ == '__main__':
    sys.exit(main())
