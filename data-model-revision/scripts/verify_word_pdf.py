#!/usr/bin/env python3
"""
自动核对Word文档与PDF提取数据的一致性
用于auto-dev模式下的Stage 4自动核对
"""

import sys
import json
from pathlib import Path
from docx import Document

def verify_word_pdf(word_path: str, pdf_data_path: str, output_path: str):
    """
    核对Word文档与PDF数据的一致性
    
    Args:
        word_path: Word文档路径
        pdf_data_path: PDF提取数据JSON路径（由Stage 2生成）
        output_path: 核对报告输出路径
    """
    try:
        # 读取Word文档
        doc = Document(word_path)
        word_tables = extract_tables_from_word(doc)
        
        # 读取PDF数据
        with open(pdf_data_path, 'r', encoding='utf-8') as f:
            pdf_data = json.load(f)
        
        # 执行核对
        results = []
        total_fields = 0
        matched_fields = 0
        errors = []
        
        for table_name, pdf_fields in pdf_data.items():
            if table_name not in word_tables:
                errors.append(f"表 {table_name} 在Word中不存在")
                continue
            
            word_fields = word_tables[table_name]
            
            for pdf_field in pdf_fields:
                total_fields += 1
                field_name = pdf_field.get('name')
                
                # 查找Word中对应字段
                word_field = find_field_in_word(word_fields, field_name)
                
                if not word_field:
                    errors.append(f"字段 {field_name} 在Word中不存在")
                    continue
                
                # 核对各属性
                checks = check_field_attributes(pdf_field, word_field)
                
                if all(checks.values()):
                    matched_fields += 1
                else:
                    for attr, passed in checks.items():
                        if not passed:
                            errors.append(f"表 {table_name} 字段 {field_name} 属性 {attr} 不匹配")
        
        # 生成报告
        pass_rate = (matched_fields / total_fields * 100) if total_fields > 0 else 0
        
        report = {
            'total_fields': total_fields,
            'matched_fields': matched_fields,
            'pass_rate': pass_rate,
            'errors': errors,
            'status': 'pass' if pass_rate >= 95 else 'fail'
        }
        
        # 输出报告
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        # 同时输出Markdown格式
        md_report = generate_markdown_report(report)
        md_path = Path(output_path).with_suffix('.md')
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(md_report)
        
        return report
        
    except Exception as e:
        error_report = {
            'status': 'error',
            'error': str(e)
        }
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(error_report, f, ensure_ascii=False, indent=2)
        return error_report

def extract_tables_from_word(doc):
    """从Word文档提取表格数据"""
    tables = {}
    for table in doc.tables:
        # 假设第一行是表名
        if len(table.rows) > 0:
            first_cell = table.rows[0].cells[0].text.strip()
            if first_cell.startswith('T_'):
                table_name = first_cell
                tables[table_name] = extract_fields_from_table(table)
    return tables

def extract_fields_from_table(table):
    """从Word表格提取字段列表"""
    fields = []
    # 跳过表名行和表头行
    for i, row in enumerate(table.rows[2:], start=2):
        if len(row.cells) >= 6:
            field = {
                'name': row.cells[0].text.strip(),
                'element_name': row.cells[1].text.strip(),
                'constraint': row.cells[2].text.strip(),
                'data_type': row.cells[3].text.strip(),
                'format': row.cells[4].text.strip(),
                'description': row.cells[5].text.strip()
            }
            if field['name']:  # 只添加有字段名的行
                fields.append(field)
    return fields

def find_field_in_word(word_fields, field_name):
    """在Word字段列表中查找指定字段"""
    for field in word_fields:
        if field['name'] == field_name:
            return field
    return None

def check_field_attributes(pdf_field, word_field):
    """核对字段属性"""
    checks = {
        'constraint': check_constraint(pdf_field.get('constraint'), word_field.get('constraint')),
        'data_type': pdf_field.get('data_type', '').strip() == word_field.get('data_type', '').strip(),
        'format': pdf_field.get('format', '').strip() == word_field.get('format', '').strip()
    }
    return checks

def check_constraint(pdf_constraint, word_constraint):
    """核对约束条件（特殊处理C/M/O映射）"""
    if not pdf_constraint or not word_constraint:
        return False
    
    pdf_c = pdf_constraint.strip()
    word_c = word_constraint.strip()
    
    # 约束映射规则
    if '有则必填' in pdf_c or '条件必填' in pdf_c:
        return word_c == 'C'
    elif '必填' in pdf_c:
        return word_c == 'M'
    elif '可选' in pdf_c:
        return word_c == 'O'
    
    return pdf_c == word_c

def generate_markdown_report(report):
    """生成Markdown格式的核对报告"""
    md = "# 数据模型核对报告\n\n"
    md += f"## 核对结果\n\n"
    md += f"- **状态**: {report['status'].upper()}\n"
    md += f"- **总字段数**: {report['total_fields']}\n"
    md += f"- **匹配字段数**: {report['matched_fields']}\n"
    md += f"- **通过率**: {report['pass_rate']:.1f}%\n\n"
    
    if report.get('errors'):
        md += "## 发现的问题\n\n"
        for i, error in enumerate(report['errors'], 1):
            md += f"{i}. {error}\n"
        md += "\n"
    
    if report['status'] == 'fail':
        md += "## 建议\n\n"
        md += "核对未通过，请检查上述问题并修正后重新运行。\n"
    
    return md

if __name__ == '__main__':
    if len(sys.argv) != 4:
        print("用法: verify_word_pdf.py <word_path> <pdf_data_path> <output_path>")
        sys.exit(1)
    
    word_path = sys.argv[1]
    pdf_data_path = sys.argv[2]
    output_path = sys.argv[3]
    
    result = verify_word_pdf(word_path, pdf_data_path, output_path)
    
    if result['status'] == 'error':
        print(f"错误: {result['error']}")
        sys.exit(1)
    elif result['status'] == 'fail':
        print(f"核对未通过，通过率: {result['pass_rate']:.1f}%")
        sys.exit(1)
    else:
        print(f"核对通过，通过率: {result['pass_rate']:.1f}%")
        sys.exit(0)
