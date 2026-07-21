#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
集成测试套件
测试组件之间的协作和数据流转
"""

import os
import sys
import json
import tempfile
from typing import Dict, List

# 添加Skill路径
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SKILL_DIR)

from parsers.standard_parser import StandardParser, StandardDocument
from matchers.standard_comparator import StandardComparator, CompareResult


class TestParserComparatorIntegration:
    """测试解析器和比较器的集成"""

    def __init__(self):
        self.parser = StandardParser({})
        self.comparator = StandardComparator({})
        self.results = {
            'passed': 0,
            'failed': 0,
            'details': []
        }

    def test_small_document_comparison(self):
        """测试小文档比对"""
        # 创建测试数据
        source_tables = [
            {
                'name': '患者基本信息表 JBBRJBXXB',
                'chinese_name': '患者基本信息表 JBBRJBXXB',
                'fields': [
                    {'name': 'XM', 'chinese_name': '姓名', 'data_type': 'S1', 'length': 50, 'constraint': 'M'},
                    {'name': 'XB', 'chinese_name': '性别', 'data_type': 'S1', 'length': 1, 'constraint': 'M'},
                    {'name': 'CSRQ', 'chinese_name': '出生日期', 'data_type': 'D', 'length': 10, 'constraint': 'M'}
                ]
            }
        ]

        target_tables = [
            {
                'name': 'm_patient',
                'chinese_name': '患者基本信息',
                'fields': [
                    {'name': 'patient_name', 'chinese_name': '患者姓名', 'data_type': 'S1', 'length': 50, 'constraint': 'M'},
                    {'name': 'gender_code', 'chinese_name': '性别代码', 'data_type': 'S1', 'length': 1, 'constraint': 'M'},
                    {'name': 'birthday', 'chinese_name': '出生日期', 'data_type': 'D', 'length': 10, 'constraint': 'M'}
                ]
            }
        ]

        # 创建文档对象
        source_doc = self._create_document(source_tables)
        target_doc = self._create_document(target_tables)

        # 执行比对
        result = self.comparator.compare(source_doc, target_doc)

        # 验证结果
        passed = len(result.matched) > 0
        test_name = "小文档比对"

        if passed:
            self.results['passed'] += 1
            print(f"✓ PASS: {test_name}")
            print(f"  匹配字段数: {len(result.matched)}")
        else:
            self.results['failed'] += 1
            print(f"✗ FAIL: {test_name}")
            print(f"  预期有匹配字段，但实际为 0")

        self.results['details'].append({
            'test': test_name,
            'passed': passed,
            'matched': len(result.matched),
            'modified': len(result.modified),
            'new_fields': len(result.new_fields)
        })

    def test_field_mapping_integration(self):
        """测试字段映射集成"""
        # 测试 insurance_type_code -> BXLX 的映射
        source_tables = [
            {
                'name': '患者基本信息表 JBBRJBXXB',
                'chinese_name': '患者基本信息表 JBBRJBXXB',
                'fields': [
                    {'name': 'BXLX', 'chinese_name': '医疗费用支付方式', 'data_type': 'S1', 'length': 2, 'constraint': 'C'}
                ]
            }
        ]

        target_tables = [
            {
                'name': 'm_patient',
                'chinese_name': '患者基本信息',
                'fields': [
                    {'name': 'insurance_type_code', 'chinese_name': '医疗保险类别代码', 'data_type': 'S1', 'length': 2, 'constraint': 'M'}
                ]
            }
        ]

        source_doc = self._create_document(source_tables)
        target_doc = self._create_document(target_tables)

        result = self.comparator.compare(source_doc, target_doc)

        # 验证字段映射生效
        matched = False
        for m in result.matched:
            if m.get('target_field') == 'insurance_type_code':
                matched = True
                break

        test_name = "字段映射集成"
        if matched:
            self.results['passed'] += 1
            print(f"✓ PASS: {test_name}")
        else:
            self.results['failed'] += 1
            print(f"✗ FAIL: {test_name}")
            print(f"  insurance_type_code 未匹配到 BXLX")

    def test_error_handling(self):
        """测试错误处理"""
        # 测试空文档比对
        source_doc = StandardDocument(source_file='empty_source')
        target_doc = StandardDocument(source_file='empty_target')

        try:
            result = self.comparator.compare(source_doc, target_doc)
            test_name = "空文档比对错误处理"
            self.results['passed'] += 1
            print(f"✓ PASS: {test_name}")
            print(f"  空文档比对正常处理，无异常")
        except Exception as e:
            self.results['failed'] += 1
            print(f"✗ FAIL: 空文档比对错误处理")
            print(f"  异常: {e}")

    def _create_document(self, tables_data: List[Dict]) -> StandardDocument:
        """创建测试文档"""
        from parsers.standard_parser import StandardTable, StandardField

        doc = StandardDocument(source_file='test')
        for table_data in tables_data:
            table = StandardTable(
                name=table_data['name'],
                chinese_name=table_data['chinese_name']
            )
            for field_data in table_data['fields']:
                field = StandardField(
                    name=field_data['name'],
                    chinese_name=field_data['chinese_name'],
                    data_type=field_data.get('data_type', 'S1'),
                    length=field_data.get('length', 64),
                    constraint=field_data.get('constraint', 'M'),
                    description=field_data.get('description', ''),
                    value_domains=[]
                )
                table.fields.append(field)
            doc.tables.append(table)
        return doc

    def run_all_tests(self):
        """运行所有集成测试"""
        print("=" * 80)
        print("集成测试套件")
        print("=" * 80)
        print()

        self.test_small_document_comparison()
        print()
        self.test_field_mapping_integration()
        print()
        self.test_error_handling()

        print()
        print("=" * 80)
        print(f"测试结果: {self.results['passed']} 通过, {self.results['failed']} 失败")
        print("=" * 80)

        return self.results


def run_integration_tests():
    """运行集成测试"""
    tester = TestParserComparatorIntegration()
    return tester.run_all_tests()


if __name__ == '__main__':
    results = run_integration_tests()
    sys.exit(0 if results['failed'] == 0 else 1)
