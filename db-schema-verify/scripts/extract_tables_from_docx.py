#!/usr/bin/env python3
"""
Word文档表名提取工具
用途：从Word文档（.docx）的目录/标题结构中提取数据库表名
策略：解析docx的TOC标题（通常三级标题包含数据表名），提取"中文名+英文表名"
依赖：Python标准库（zipfile + xml.etree.ElementTree），无第三方依赖

用法：
    python extract_tables_from_docx.py <Word文档路径>

输出：JSON格式的表名列表（包含原表和TRAN/LOG表）
"""
import sys
import re
import json
import zipfile
from xml.etree import ElementTree as ET
from pathlib import Path


# docx XML命名空间
NS = {
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'w14': 'http://schemas.microsoft.com/office/word/2010/wordml',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
}


def parse_headings(docx_path):
    """
    解析docx文件，提取所有带样式的段落（标题）。
    返回：[(style_val, text), ...]
    """
    headings = []
    with zipfile.ZipFile(docx_path, 'r') as z:
        with z.open('word/document.xml') as f:
            tree = ET.parse(f)
            root = tree.getroot()

    for p in root.findall('.//w:p', NS):
        pPr = p.find('w:pPr', NS)
        style = ''
        if pPr is not None:
            pStyle = pPr.find('w:pStyle', NS)
            if pStyle is not None:
                style = pStyle.get(f'{{{NS["w"]}}}val', '')

        # 提取段落文本
        texts = []
        for t in p.findall('.//w:t', NS):
            if t.text:
                texts.append(t.text)
        text = ''.join(texts).strip()

        if style and text:
            headings.append((style, text))

    return headings


def is_toc_heading(style):
    """判断是否为目录/标题样式"""
    # TOC样式：TOC1, TOC2, TOC3, TOC4
    # Heading样式：1, 2, 3, 4 或 Heading1, Heading2, Heading3, Heading4
    style_upper = style.upper()
    if style_upper.startswith('TOC'):
        return True
    if style_upper.startswith('HEADING'):
        return True
    if re.match(r'^[1-4]$', style):
        return True
    return False


def get_heading_level(style):
    """获取标题层级（1-4），无法识别返回0"""
    style_upper = style.upper()
    # TOC1/TOC2/TOC3/TOC4
    match = re.search(r'(\d+)', style_upper)
    if match:
        return int(match.group(1))
    return 0


def extract_table_name_from_heading(text):
    """
    从标题文本中提取中文名和英文表名。
    标题格式示例：
        "2.1.1 医护人员信息表 JBYHRYXXB"
        "2.1.2 科室信息(JBKSXXB)"
        "2.1.3 病区信息（JBBQXXB）"
        "2.3.3 门(急)诊病历"（无英文表名）
    
    返回：(中文名, 英文表名) 或 (中文名, None)
    """
    # 去掉序号前缀（如 2.1.1, 3.1.2.1）
    cleaned = re.sub(r'^[\d.]+\s*', '', text).strip()
    if not cleaned:
        return None, None

    # 去掉末尾的页码数字（独立数字）
    cleaned = re.sub(r'\s+\d+\s*$', '', cleaned).strip()

    # 策略1：中文后跟括号内的英文表名（中英文括号都兼容）
    match = re.search(
        r'([\u4e00-\u9fff（）()、/\s\w]+?)[（(]([A-Z][A-Z0-9_]+)[)）]',
        cleaned
    )
    if match:
        cn_name = match.group(1).strip()
        en_name = match.group(2).strip()
        return cn_name, en_name

    # 策略2：中文后跟空格+英文表名（从右往左匹配大写英文序列）
    match = re.search(
        r'([\u4e00-\u9fff（）()、/\s]+?)\s+([A-Z][A-Z0-9_]+)\s*$',
        cleaned
    )
    if match:
        cn_name = match.group(1).strip()
        en_name = match.group(2).strip()
        # 排除中文内部括号被误判的情况
        # 如"门(急)诊病历"不应提取"诊病历"为中文名
        if cn_name and len(cn_name) >= 2:
            return cn_name, en_name

    # 策略3：中文直接接英文表名（无分隔）
    match = re.search(
        r'([\u4e00-\u9fff（）()、/]+)([A-Z][A-Z0-9_]+)\s*$',
        cleaned
    )
    if match:
        cn_name = match.group(1).strip()
        en_name = match.group(2).strip()
        if cn_name and len(cn_name) >= 2:
            return cn_name, en_name

    # 策略4：只有中文名，没有英文表名
    # 去掉"表"字后缀看是否还有内容
    cn_only = re.sub(r'表\s*$', '', cleaned).strip()
    if cn_only and re.search(r'[\u4e00-\u9fff]', cn_only):
        return cn_only, None

    return None, None


def detect_toc_level(headings):
    """
    自动检测哪一级标题包含数据表名。
    通常是三级标题（TOC3），但需要验证。
    """
    level_counts = {}
    for style, text in headings:
        if not is_toc_heading(style):
            continue
        level = get_heading_level(style)
        if level not in level_counts:
            level_counts[level] = []
        # 尝试提取英文表名
        cn_name, en_name = extract_table_name_from_heading(text)
        if en_name:
            level_counts.setdefault(level, [])
            level_counts[level].append(en_name)

    # 找出英文表名最多的层级
    best_level = None
    best_count = 0
    for level, names in level_counts.items():
        if len(names) > best_count:
            best_count = len(names)
            best_level = level

    return best_level


def extract_tables(docx_path):
    """
    从Word文档中提取所有数据库表名。
    返回：[(中文名, 英文表名), ...] 去重后
    """
    headings = parse_headings(docx_path)

    # 自动检测表名所在的标题层级
    table_level = detect_toc_level(headings)

    if table_level is None:
        # 回退：扫描所有标题层级
        table_level = 0  # 0表示不限层级

    tables = []
    seen_en_names = set()

    for style, text in headings:
        if not is_toc_heading(style):
            continue

        level = get_heading_level(style)
        # 如果检测到了最佳层级，只提取该层级的表名
        if table_level > 0 and level != table_level:
            continue

        cn_name, en_name = extract_table_name_from_heading(text)

        if en_name:
            # 按英文表名去重
            if en_name not in seen_en_names:
                seen_en_names.add(en_name)
                tables.append((cn_name or en_name, en_name))
        elif cn_name:
            # 没有英文表名的表，标记出来让用户确认
            tables.append((cn_name, None))

    return tables


def expand_table_names(base_names, suffixes=None):
    """
    将基础表名扩展为包含TRAN和LOG后缀的完整列表。
    """
    if suffixes is None:
        suffixes = ['_TRAN', '_LOG']

    result = []
    for cn_name, en_name in base_names:
        if en_name is None:
            # 没有英文表名的跳过（无法生成_TRAN/_LOG）
            result.append({'table_name': cn_name, 'type': '原表（无英文名，需确认）'})
            continue

        result.append({'cn_name': cn_name, 'table_name': en_name, 'type': '原表'})
        for suffix in suffixes:
            result.append({
                'cn_name': cn_name,
                'table_name': en_name + suffix,
                'type': suffix.strip('_') + '表'
            })

    return result


def main():
    if len(sys.argv) < 2:
        print("用法: python extract_tables_from_docx.py <Word文档路径>")
        print("输出: JSON格式的表名列表（包含原表和TRAN/LOG表）")
        sys.exit(1)

    docx_path = sys.argv[1]

    if not Path(docx_path).exists():
        print(f"错误: 文件不存在 - {docx_path}", file=sys.stderr)
        sys.exit(1)

    print(f"正在解析Word文档: {docx_path}", file=sys.stderr)
    base_tables = extract_tables(docx_path)

    if not base_tables:
        print("警告: 未找到任何表名。请检查文档是否包含目录结构。", file=sys.stderr)
        sys.exit(1)

    # 分离有英文名和无英文名的表
    with_en = [(cn, en) for cn, en in base_tables if en is not None]
    without_en = [(cn, en) for cn, en in base_tables if en is None]

    # 扩展为完整列表（包含TRAN和LOG）
    expanded = expand_table_names(base_tables)

    # 输出结果
    output = {
        'source_file': docx_path,
        'base_table_count': len(with_en),
        'total_table_count': len(expanded),
        'base_tables': [en for _, en in with_en],
        'table_details': [
            {'cn_name': cn, 'en_name': en}
            for cn, en in with_en
        ],
        'tables_without_english': [
            {'cn_name': cn}
            for cn, _ in without_en
        ],
        'all_tables': expanded
    }

    print(json.dumps(output, ensure_ascii=False, indent=2))

    if without_en:
        print(f"\n⚠️  有 {len(without_en)} 个表没有英文表名，需要人工确认：", file=sys.stderr)
        for cn, _ in without_en:
            print(f"   - {cn}", file=sys.stderr)


if __name__ == '__main__':
    main()
