#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
字段匹配测试运行器
用于验证字段匹配逻辑的正确性，防止回归
"""

import os
import sys
import yaml
from typing import Dict, List, Tuple

# 添加Skill路径
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SKILL_DIR)

from parsers.standard_parser import StandardField
from matchers.standard_comparator import StandardComparator


class FieldMatchingTestRunner:
    """字段匹配测试运行器"""

    def __init__(self):
        self.comparator = StandardComparator({})
        self.test_cases = self._load_test_cases()
        self.results = {
            'passed': 0,
            'failed': 0,
            'details': []
        }

    def _load_test_cases(self) -> List[Dict]:
        """加载测试用例"""
        test_cases_path = os.path.join(
            SKILL_DIR, 'tests', 'test_cases.yaml'
        )

        if not os.path.exists(test_cases_path):
            print(f"警告: 测试用例文件不存在: {test_cases_path}")
            return []

        with open(test_cases_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            return data.get('test_cases', [])

    def _create_field(self, field_data: Dict) -> StandardField:
        """创建标准字段对象"""
        return StandardField(
            name=field_data.get('name', ''),
            chinese_name=field_data.get('chinese_name', ''),
            data_type=field_data.get('data_type', 'S1'),
            length=field_data.get('length', 64),
            constraint=field_data.get('constraint', 'M'),
            description=field_data.get('description', ''),
            value_domains=[]
        )

    def _run_test_case(self, test_case: Dict) -> Tuple[bool, str]:
        """运行单个测试用例"""
        test_id = test_case.get('id', 'unknown')
        description = test_case.get('description', '')
        expected = test_case.get('expected', '')

        target_data = test_case.get('target_field', {})
        source_data = test_case.get('source_field', {})

        target_field = self._create_field(target_data)
        source_field = self._create_field(source_data)

        # 根据测试ID前缀选择不同的测试方法
        if test_id.startswith('keyword_'):
            # 测试 keyword 匹配的完整逻辑（包括角色、代码/名称、描述兼容性）
            is_keyword_match = self.comparator._is_keyword_match(
                target_field.chinese_name, source_field.chinese_name
            )
            # 如果基础匹配通过，还需要检查代码/名称兼容性和描述兼容性
            if is_keyword_match:
                is_code_name_ok = self.comparator._is_code_name_compatible(
                    target_field.chinese_name, source_field.chinese_name
                )
                is_desc_ok = self.comparator._is_description_compatible(
                    target_field, source_field
                )
                is_keyword_match = is_keyword_match and is_code_name_ok and is_desc_ok

            if expected == 'match':
                if is_keyword_match:
                    return True, f"✓ 正确匹配"
                else:
                    return False, f"✗ 应该匹配但被拒绝"
            elif expected == 'no_match':
                if not is_keyword_match:
                    return True, f"✓ 正确拒绝"
                else:
                    return False, f"✗ 应该拒绝但被匹配"

        elif test_id.startswith('synonym_'):
            # 测试 synonym 匹配的完整逻辑（包括角色、概念、描述兼容性）
            is_synonym_match = self.comparator._is_synonym_match(
                target_field.chinese_name, source_field.chinese_name
            )
            # 如果基础匹配通过，还需要检查描述兼容性
            if is_synonym_match:
                is_desc_ok = self.comparator._is_description_compatible(
                    target_field, source_field
                )
                is_synonym_match = is_synonym_match and is_desc_ok

            if expected == 'match':
                if is_synonym_match:
                    return True, f"✓ 正确匹配"
                else:
                    return False, f"✗ 应该匹配但被拒绝"
            elif expected == 'no_match':
                if not is_synonym_match:
                    return True, f"✓ 正确拒绝"
                else:
                    return False, f"✗ 应该拒绝但被匹配"

        elif test_id.startswith('std_ref_'):
            # 测试 standard_reference 映射的兼容性检查
            field_mapping = {
                'target_fields': [target_field.name],
                'source_field': source_field.name,
                'match_type': 'standard_reference'
            }
            is_compatible = self.comparator._is_field_mapping_compatible(
                target_field, source_field, field_mapping
            )
            if expected == 'match':
                if is_compatible:
                    return True, f"✓ 正确匹配"
                else:
                    return False, f"✗ 应该匹配但被拒绝"
            elif expected == 'no_match':
                if not is_compatible:
                    return True, f"✓ 正确拒绝"
                else:
                    return False, f"✗ 应该拒绝但被匹配"

        else:
            # 默认测试描述兼容性
            is_compatible = self.comparator._is_description_compatible(
                target_field, source_field
            )

            if expected == 'match':
                if is_compatible:
                    return True, f"✓ 正确匹配"
                else:
                    return False, f"✗ 应该匹配但被拒绝"
            elif expected == 'no_match':
                if not is_compatible:
                    return True, f"✓ 正确拒绝"
                else:
                    return False, f"✗ 应该拒绝但被匹配"
            elif expected == 'no_dictionary':
                # 测试字典检测
                context_fields = test_case.get('context_fields', [])
                all_fields = [target_field] + [
                    self._create_field(f) for f in context_fields
                ]
                related_code = self.comparator._find_related_code_field(
                    target_field, all_fields, {}
                )
                if related_code is None:
                    return True, f"✓ 正确识别为非字典项"
                else:
                    return False, f"✗ 错误识别为字典项 (关联字段: {related_code.name})"

        return False, f"? 未知的预期结果: {expected}"

    def run_all_tests(self) -> Dict:
        """运行所有测试"""
        print("=" * 80)
        print("字段匹配测试运行器")
        print("=" * 80)
        print()

        if not self.test_cases:
            print("没有测试用例可运行")
            return self.results

        print(f"共 {len(self.test_cases)} 个测试用例")
        print()

        for test_case in self.test_cases:
            test_id = test_case.get('id', 'unknown')
            description = test_case.get('description', '')

            passed, message = self._run_test_case(test_case)

            if passed:
                self.results['passed'] += 1
                status = "✓ PASS"
            else:
                self.results['failed'] += 1
                status = "✗ FAIL"

            print(f"[{status}] {test_id}: {description}")
            print(f"       {message}")

            self.results['details'].append({
                'id': test_id,
                'description': description,
                'passed': passed,
                'message': message,
                'rule': test_case.get('rule', '')
            })

        print()
        print("=" * 80)
        print(f"测试结果: {self.results['passed']} 通过, {self.results['failed']} 失败")
        print("=" * 80)

        return self.results

    def save_baseline(self, output_path: str = None):
        """保存测试基线"""
        if not output_path:
            output_path = os.path.join(
                SKILL_DIR, 'tests', 'test_baseline.yaml'
            )

        baseline = {
            'passed': self.results['passed'],
            'failed': self.results['failed'],
            'details': self.results['details']
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            yaml.dump(baseline, f, allow_unicode=True, default_flow_style=False)

        print(f"基线已保存到: {output_path}")

    def check_regression(self, baseline_path: str = None) -> bool:
        """检查回归"""
        if not baseline_path:
            baseline_path = os.path.join(
                SKILL_DIR, 'tests', 'test_baseline.yaml'
            )

        if not os.path.exists(baseline_path):
            print("没有找到基线文件，跳过回归检查")
            return False

        with open(baseline_path, 'r', encoding='utf-8') as f:
            baseline = yaml.safe_load(f)

        baseline_passed = baseline.get('passed', 0)
        current_passed = self.results['passed']

        print()
        print("=" * 80)
        print("回归检查")
        print("=" * 80)
        print(f"基线通过数: {baseline_passed}")
        print(f"当前通过数: {current_passed}")

        if current_passed < baseline_passed:
            print(f"⚠ 检测到回归！通过数减少了 {baseline_passed - current_passed}")

            # 找出哪些测试从通过变成了失败
            baseline_details = {d['id']: d for d in baseline.get('details', [])}
            for detail in self.results['details']:
                if not detail['passed']:
                    baseline_detail = baseline_details.get(detail['id'], {})
                    if baseline_detail.get('passed', False):
                        print(f"  回归: {detail['id']} - {detail['description']}")
                        print(f"    之前: {baseline_detail.get('message', '')}")
                        print(f"    现在: {detail['message']}")

            return True
        elif current_passed > baseline_passed:
            print(f"✓ 通过数增加了 {current_passed - baseline_passed}")
            return False
        else:
            print("✓ 没有回归")
            return False


def main():
    """主函数"""
    runner = FieldMatchingTestRunner()
    runner.run_all_tests()

    if len(sys.argv) > 1 and sys.argv[1] == '--save-baseline':
        runner.save_baseline()

    if len(sys.argv) > 1 and sys.argv[1] == '--check-regression':
        runner.check_regression()


if __name__ == '__main__':
    main()
