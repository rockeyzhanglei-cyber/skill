#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主测试运行器
运行所有类型的测试并生成综合报告
"""

import os
import sys
import time
import json
from typing import Dict, List
from datetime import datetime

# 添加Skill路径
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SKILL_DIR)


class MasterTestRunner:
    """主测试运行器"""

    def __init__(self):
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'total_passed': 0,
            'total_failed': 0,
            'total_duration': 0,
            'test_suites': {}
        }

    def run_all_tests(self, skip_e2e: bool = False):
        """运行所有测试"""
        print("=" * 80)
        print("主测试运行器 - 完整测试套件")
        print("=" * 80)
        print()

        start_time = time.time()

        # 1. 回归测试
        print(">>> 运行回归测试...")
        print()
        regression_result = self._run_regression_tests()
        self.results['test_suites']['regression'] = regression_result
        print()

        # 2. 单元测试
        print(">>> 运行单元测试...")
        print()
        unit_result = self._run_unit_tests()
        self.results['test_suites']['unit'] = unit_result
        print()

        # 3. 集成测试
        print(">>> 运行集成测试...")
        print()
        integration_result = self._run_integration_tests()
        self.results['test_suites']['integration'] = integration_result
        print()

        # 4. 端到端测试（可选，因为耗时较长）
        if not skip_e2e:
            print(">>> 运行端到端测试...")
            print()
            e2e_result = self._run_e2e_tests()
            self.results['test_suites']['e2e'] = e2e_result
            print()
        else:
            print(">>> 跳过端到端测试（使用 --skip-e2e 参数）")
            print()

        # 汇总结果
        self.results['total_duration'] = time.time() - start_time
        self._summarize_results()

        return self.results

    def _run_regression_tests(self) -> Dict:
        """运行回归测试"""
        try:
            from scripts.test_runner import FieldMatchingTestRunner
            runner = FieldMatchingTestRunner()
            result = runner.run_all_tests()
            return {
                'passed': result['passed'],
                'failed': result['failed'],
                'details': result['details']
            }
        except Exception as e:
            print(f"回归测试运行失败: {e}")
            return {'passed': 0, 'failed': 1, 'error': str(e)}

    def _run_unit_tests(self) -> Dict:
        """运行单元测试"""
        try:
            from scripts.unit_tests import run_unit_tests
            success = run_unit_tests()
            return {
                'passed': 1 if success else 0,
                'failed': 0 if success else 1
            }
        except Exception as e:
            print(f"单元测试运行失败: {e}")
            return {'passed': 0, 'failed': 1, 'error': str(e)}

    def _run_integration_tests(self) -> Dict:
        """运行集成测试"""
        try:
            from scripts.integration_tests import run_integration_tests
            result = run_integration_tests()
            return result
        except Exception as e:
            print(f"集成测试运行失败: {e}")
            return {'passed': 0, 'failed': 1, 'error': str(e)}

    def _run_e2e_tests(self) -> Dict:
        """运行端到端测试"""
        try:
            from scripts.e2e_tests import run_e2e_tests
            result = run_e2e_tests()
            return result
        except Exception as e:
            print(f"端到端测试运行失败: {e}")
            return {'passed': 0, 'failed': 1, 'error': str(e)}

    def _summarize_results(self):
        """汇总测试结果"""
        for suite_name, suite_result in self.results['test_suites'].items():
            self.results['total_passed'] += suite_result.get('passed', 0)
            self.results['total_failed'] += suite_result.get('failed', 0)

        print("=" * 80)
        print("测试汇总")
        print("=" * 80)
        print()

        for suite_name, suite_result in self.results['test_suites'].items():
            passed = suite_result.get('passed', 0)
            failed = suite_result.get('failed', 0)
            total = passed + failed

            status = "✓ PASS" if failed == 0 else "✗ FAIL"
            print(f"{status} {suite_name.upper()}: {passed}/{total} 通过")

        print()
        print(f"总通过: {self.results['total_passed']}")
        print(f"总失败: {self.results['total_failed']}")
        print(f"总耗时: {self.results['total_duration']:.2f}秒")
        print("=" * 80)

    def save_report(self, output_path: str = None):
        """保存测试报告"""
        if not output_path:
            output_path = os.path.join(
                SKILL_DIR, 'knowledge_base', 'test_report.json'
            )

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)

        print(f"测试报告已保存到: {output_path}")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='主测试运行器')
    parser.add_argument('--skip-e2e', action='store_true',
                        help='跳过端到端测试（耗时较长）')
    parser.add_argument('--save-report', action='store_true',
                        help='保存测试报告到文件')

    args = parser.parse_args()

    runner = MasterTestRunner()
    results = runner.run_all_tests(skip_e2e=args.skip_e2e)

    if args.save_report:
        runner.save_report()

    # 返回退出码
    sys.exit(0 if results['total_failed'] == 0 else 1)


if __name__ == '__main__':
    main()
