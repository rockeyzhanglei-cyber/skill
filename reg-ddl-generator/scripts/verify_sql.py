#!/usr/bin/env python3
"""
SQL脚本验证器
v1.0.0
检查生成后的SQL脚本是否存在常见语法错误：
- VARCHAR/VARCHAR2/NVARCHAR 无长度（明显语法错误）
- NUMBER/NUMERIC/DECIMAL 无精度
- 括号不配对
- 其他可疑的语法问题
- Doris 专属：输出中不得残留 NUMERIC / TIMESTAMP 类型（Doris 仅支持 DECIMAL / DATETIME）
- Doris 专属：varchar/char 长度必须为 4 的倍数（Doris 存储 UTF-8，字符串长度按字节×4）

用法:
    python3 verify_sql.py <sql文件路径> [--db oracle|sqlserver|mysql|postgresql|doris]
"""

import sys
import os
import re
import argparse


def check_varchar_without_length(lines, db_type):
    """检查 VARCHAR/VARCHAR2/NVARCHAR 等类型是否有长度"""
    issues = []
    # 匹配模式：类型关键字后面紧跟空格或逗号或括号时
    # 需要排除 nvarchar(max) / nvarchar(max) 等合法无长度
    patterns = {
        'oracle': [
            (r'\bvarchar2\b(?!\s*\()', 'varchar2'),
            (r'\bvarchar\b(?!\s*\()', 'varchar'),
        ],
        'sqlserver': [
            (r'\bnvarchar\b(?!\s*\(|\s+max\b)', 'nvarchar'),
            (r'\bvarchar\b(?!\s*\()', 'varchar'),
        ],
        'mysql': [
            (r'\bvarchar\b(?!\s*\()', 'varchar'),
        ],
        'postgresql': [
            (r'\bvarchar\b(?!\s*\()', 'varchar'),
        ]
    }

    # 排除注释行
    pats = patterns.get(db_type, patterns['oracle'])
    for line_no, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith('--') or stripped.startswith('/*') or stripped.startswith('*'):
            continue
        # 检查动态SQL字符串中的类型（execute immediate '...' 内部）
        # 也需要检查
        for pat, type_name in pats:
            for m in re.finditer(pat, line, re.IGNORECASE):
                # 确认这不是 nvarchar(max) 也不是已经带括号的
                after = line[m.end():].lstrip()
                if after.startswith('(') or after.upper().startswith('MAX'):
                    continue
                # 确认不是注释中的内容
                col = m.start()
                before = line[:col].strip()
                if before.endswith('--') or '--' in before:
                    continue
                issues.append({
                    'line': line_no,
                    'content': line.strip()[:120],
                    'type': f'{type_name} 无长度'
                })
    return issues


def check_number_without_precision(lines, db_type):
    """检查 NUMBER/NUMERIC/DECIMAL 是否有精度"""
    issues = []
    # 只检查列定义中的 number（排除 v_count 等变量声明）

    for line_no, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith('--') or stripped.startswith('/*') or stripped.startswith('*'):
            continue

        # 在列定义行（create table 或 alter 语句中）检查
        for m in re.finditer(r'\b(number|numeric|decimal)\b(?!\s*\()', line, re.IGNORECASE):
            after = line[m.end():].lstrip()
            if after.startswith('('):
                continue
            # 确认不是 v_count number 这种变量声明
            before = line[:m.start()].strip()
            if re.match(r'(v_|declare\s+|v_count\s+)', before, re.IGNORECASE):
                continue
            issues.append({
                'line': line_no,
                'content': line.strip()[:120],
                'type': f'{m.group(1)} 无精度'
            })
    return issues


def check_unbalanced_parentheses(lines):
    """检查括号是否配对"""
    issues = []
    for line_no, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith('--') or stripped.startswith('/*') or stripped.startswith('*'):
            # 也检查多行注释中的括号，但跳过
            continue
        # 检查单行内的括号（多行括号由后续逻辑检查）
        opens = stripped.count('(')
        closes = stripped.count(')')
        if opens != closes:
            # 可能跨多行，只记录明显单行不配对
            if abs(opens - closes) >= 3 and 'execute immediate' not in stripped:
                issues.append({
                    'line': line_no,
                    'content': stripped[:120],
                    'type': f'括号不配对（左{opens}右{closes}）'
                })
    return issues


def check_suspicious_patterns(lines, db_type):
    """其他可疑模式"""
    issues = []
    suspicious = [
        (r'\bnull\b\s*\bnull\b', '重复NULL关键字'),
        (r'\bnot\b\s+not\b', '重复NOT'),
        (r'\bcreate\b\s+\btable\b\s+\btable\b', '重复TABLE关键字'),
    ]

    for line_no, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith('--') or stripped.startswith('/*'):
            continue
        for pat, desc in suspicious:
            if re.search(pat, stripped, re.IGNORECASE):
                issues.append({
                    'line': line_no,
                    'content': stripped[:120],
                    'type': desc
                })
    return issues


def _mask_comments(text):
    """将 /* */ 块注释与 -- 行注释替换为等长的空格，保留行号与换行，便于准确定位。"""
    def blk(m):
        return ' ' * len(m.group(0))
    text = re.sub(r'/\*.*?\*/', blk, text, flags=re.DOTALL)
    text = re.sub(r'--[^\n]*', blk, text)
    return text


def check_doris_type_compatibility(lines):
    """Doris 不支持 NUMERIC / TIMESTAMP 类型，必须转换为 DECIMAL / DATETIME。

    当 convert_doris.py 的 to_doris_type 漏转（或手工改脚本遗漏）时，
    Doris 解析会报 'mismatched input numeric'。此处扫描可执行代码区，
    若残留 numeric / timestamp 直接报警。/* */ 变更说明与 -- 注释先剥离，避免误报。
    """
    issues = []
    masked = _mask_comments("\n".join(lines)).split("\n")
    for line_no, line in enumerate(masked, 1):
        for m in re.finditer(r'\b(numeric|timestamp)\b', line, re.IGNORECASE):
            word = m.group(1).lower()
            target = 'DECIMAL' if word == 'numeric' else 'DATETIME'
            issues.append({
                'line': line_no,
                'content': line.strip()[:120],
                'type': f"Doris 不支持 {word.upper()} 类型（应转换为 {target}）"
            })
    return issues


def check_doris_str_len_x4(lines):
    """Doris 字符串字段长度必须 ×4（用户 2026-08-28 确定）。

    Doris 存储 UTF-8 中文 1 汉字 3 字节 / 1 特殊字符 4 字节，标准文档长度按【字符数】控制，
    生成脚本时 varchar(n)/char(n) 的 n 统一 ×4（n 为字节数）。此处扫描可执行代码区，
    若存在长度非 4 倍数的 varchar/char 直接报警（提示 ×4）。注释先剥离，避免误报。
    """
    issues = []
    masked = _mask_comments("\n".join(lines)).split("\n")
    for line_no, line in enumerate(masked, 1):
        for m in re.finditer(r'\b(varchar|char)\((\d+)\)', line, re.IGNORECASE):
            v = int(m.group(2))
            if v % 4 != 0:
                issues.append({
                    'line': line_no,
                    'content': line.strip()[:120],
                    'type': f"Doris 字符串长度 {m.group(1)}({v}) 非 4 倍数（应统一 ×4，如 {v * 4}）"
                })
    return issues


def verify_sql(sql_path, db_type='oracle'):
    """验证SQL脚本，返回问题列表"""
    if not os.path.exists(sql_path):
        print(f"文件不存在: {sql_path}")
        return False

    with open(sql_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    all_issues = []
    all_issues.extend(check_varchar_without_length(lines, db_type))
    all_issues.extend(check_number_without_precision(lines, db_type))
    all_issues.extend(check_unbalanced_parentheses(lines))
    all_issues.extend(check_suspicious_patterns(lines, db_type))
    if db_type == 'doris':
        all_issues.extend(check_doris_type_compatibility(lines))
        all_issues.extend(check_doris_str_len_x4(lines))

    # 按行号排序
    all_issues.sort(key=lambda x: x['line'])

    return all_issues


def print_report(all_issues, sql_path, db_type):
    if not all_issues:
        print(f"✓ 验证通过: {os.path.basename(sql_path)}（无语法问题）")
        return True

    print(f"✗ 发现 {len(all_issues)} 个语法问题: {os.path.basename(sql_path)}")
    print()
    for iss in all_issues:
        print(f"  [{iss['type']}] 第{iss['line']}行: {iss['content']}")
    print()
    print("建议: 检查脚本生成逻辑，修复对应问题后重新生成")
    return False


def main():
    parser = argparse.ArgumentParser(description='校验SQL脚本语法')
    parser.add_argument('sql_path', help='SQL文件路径')
    parser.add_argument('--db', default='oracle',
                        choices=['oracle', 'sqlserver', 'mysql', 'postgresql', 'doris'],
                        help='数据库类型')
    args = parser.parse_args()

    issues = verify_sql(args.sql_path, args.db)
    has_error = print_report(issues, args.sql_path, args.db)

    return 1 if not has_error or issues else 0


if __name__ == '__main__':
    sys.exit(main())