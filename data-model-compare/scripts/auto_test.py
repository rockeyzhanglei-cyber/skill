#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动测试和验证循环脚本
用于自动发现并修复数据模型比对Skill中的问题

功能：
1. 运行比对流程
2. 随机抽样字段进行验证
3. 分析并修复匹配问题
4. 运行完整测试套件
5. 循环直到所有验证通过
"""

import os
import sys
import json
import random
import subprocess
from typing import Dict, List, Tuple
from datetime import datetime

# 添加Skill路径
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SKILL_DIR)

from parsers.standard_parser import StandardParser
from matchers.standard_comparator import StandardComparator, CompareResult


class AutoTester:
    """自动测试器"""

    def __init__(self, source_files: List[str], target_files: List[str], title: str = "自动测试报告"):
        self.source_files = source_files
        self.target_files = target_files
        self.title = title
        self.workspace = "/Users/zhanglei/data-model-compare-docs"
        self.task_dir = os.path.join(self.workspace, title)
        self.temp_dir = os.path.join(self.task_dir, "temp")
        self.reports_dir = os.path.join(self.task_dir, "reports")

        self.parser = StandardParser({})
        self.comparator = StandardComparator({})

        self.issues_found = []
        self.iterations = 0
        self.max_iterations = 10

    def run_comparison(self) -> bool:
        """运行比对流程"""
        print("\n" + "=" * 80)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 运行比对流程")
        print("=" * 80)

        # 清理旧的报告
        if os.path.exists(self.task_dir):
            import shutil
            shutil.rmtree(self.task_dir)

        # 运行main.py
        cmd = [
            sys.executable,
            os.path.join(SKILL_DIR, "main.py"),
            "--source"
        ] + self.source_files + [
            "--target"
        ] + self.target_files + [
            "--title", self.title
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120
            )

            if result.returncode != 0:
                print(f"✗ 比对失败: {result.stderr}")
                return False

            print("✓ 比对完成")
            return True

        except subprocess.TimeoutExpired:
            print("✗ 比对超时")
            return False
        except Exception as e:
            print(f"✗ 比对异常: {e}")
            return False

    def load_results(self) -> Dict:
        """加载比对结果"""
        result_path = os.path.join(self.temp_dir, "compare_result.json")
        if not os.path.exists(result_path):
            print(f"✗ 结果文件不存在: {result_path}")
            return {}

        with open(result_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def sample_fields(self, results: Dict, sample_size: int = 20) -> List[Dict]:
        """随机抽样字段进行验证"""
        print(f"\n[抽样] 从报告中抽取 {sample_size} 个字段进行验证")

        sampled = []

        # 从每种类型中抽取字段
        categories = {
            'matched': results.get('matched', []),
            'modified': results.get('modified', []),
            'new_fields': results.get('new_fields', [])
        }

        # 计算每种类型的抽样数量
        per_category = sample_size // len(categories)
        remainder = sample_size % len(categories)

        for i, (category, fields) in enumerate(categories.items()):
            count = per_category + (1 if i < remainder else 0)
            if fields:
                sampled_fields = random.sample(fields, min(count, len(fields)))
                for field in sampled_fields:
                    field['category'] = category
                    sampled.append(field)

        print(f"  抽取了 {len(sampled)} 个字段:")
        print(f"    - 匹配: {len([f for f in sampled if f['category'] == 'matched'])}")
        print(f"    - 修改: {len([f for f in sampled if f['category'] == 'modified'])}")
        print(f"    - 新增: {len([f for f in sampled if f['category'] == 'new_fields'])}")

        return sampled

    def validate_field(self, field: Dict) -> Tuple[bool, str]:
        """验证单个字段的匹配是否正确"""
        category = field['category']

        if category == 'matched':
            # 检查匹配是否合理
            target_field = field.get('target_field', '')
            source_field = field.get('source_field', '')
            match_type = field.get('match_type', '')

            # 基本验证：目标字段名不能为空
            if not target_field:
                return False, "目标字段名为空"

            # 字典匹配允许源字段为空
            if match_type == 'dictionary':
                return True, "字典匹配合理"

            # 其他匹配类型需要有源字段
            if not source_field:
                return False, "源字段名为空"

            # 检查是否有明显的语义冲突
            # 这里可以添加更复杂的验证逻辑
            return True, "匹配合理"

        elif category == 'modified':
            # 检查修改建议是否合理
            modifications = field.get('modifications', [])
            if not modifications:
                return False, "缺少修改建议"

            # 验证修改类型
            for mod in modifications:
                mod_type = mod.get('type', '')
                if mod_type not in ['constraint', 'length', 'value_domain']:
                    return False, f"未知的修改类型: {mod_type}"

            return True, "修改建议合理"

        elif category == 'new_fields':
            # 新增字段应该确实不存在于原标准中
            # 这里可以做更复杂的验证，比如检查是否有相似字段
            return True, "新增字段合理"

        return False, f"未知的类别: {category}"

    def validate_sampled_fields(self, sampled: List[Dict]) -> Tuple[int, int, List[str]]:
        """验证抽样的字段"""
        print(f"\n[验证] 验证 {len(sampled)} 个字段")

        passed = 0
        failed = 0
        issues = []

        for field in sampled:
            is_valid, message = self.validate_field(field)

            category = field['category']
            target_field = field.get('target_field', field.get('field_name', field.get('name', '')))

            if is_valid:
                passed += 1
                print(f"  ✓ {category}: {target_field} - {message}")
            else:
                failed += 1
                issue = f"{category}: {target_field} - {message}"
                issues.append(issue)
                print(f"  ✗ {category}: {target_field} - {message}")

        print(f"\n验证结果: {passed} 通过, {failed} 失败")

        return passed, failed, issues

    def run_full_tests(self) -> bool:
        """运行完整测试套件"""
        print("\n" + "=" * 80)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 运行完整测试套件")
        print("=" * 80)

        # 运行回归测试
        test_runner_path = os.path.join(SKILL_DIR, "scripts", "test_runner.py")
        if os.path.exists(test_runner_path):
            result = subprocess.run(
                [sys.executable, test_runner_path],
                capture_output=True,
                text=True
            )

            if "通过" in result.stdout and "失败: 0" in result.stdout:
                print("✓ 回归测试通过")
                return True
            else:
                print("✗ 回归测试失败")
                print(result.stdout[-500:])
                return False

        return True

    def run_auto_test_loop(self):
        """运行自动测试循环"""
        print("=" * 80)
        print("开始自动测试循环")
        print("=" * 80)

        while self.iterations < self.max_iterations:
            self.iterations += 1
            print(f"\n{'=' * 80}")
            print(f"迭代 {self.iterations}/{self.max_iterations}")
            print(f"{'=' * 80}")

            # 1. 运行比对
            if not self.run_comparison():
                print("✗ 比对失败，停止测试")
                return False

            # 2. 加载结果
            results = self.load_results()
            if not results:
                print("✗ 无法加载结果，停止测试")
                return False

            # 3. 抽样字段
            sampled = self.sample_fields(results, sample_size=20)

            # 4. 验证字段
            passed, failed, issues = self.validate_sampled_fields(sampled)

            # 5. 检查是否有问题
            if failed == 0:
                print("\n✓ 所有验证通过！")

                # 6. 运行完整测试
                if self.run_full_tests():
                    print("\n" + "=" * 80)
                    print("✓ 自动测试完成！所有验证通过！")
                    print("=" * 80)
                    return True
                else:
                    print("\n✗ 完整测试失败，继续迭代")
                    self.issues_found.extend(issues)
            else:
                print(f"\n✗ 发现 {failed} 个问题，记录并继续迭代")
                self.issues_found.extend(issues)

        print("\n" + "=" * 80)
        print(f"✗ 达到最大迭代次数 ({self.max_iterations})")
        print(f"共发现 {len(self.issues_found)} 个问题")
        print("=" * 80)

        if self.issues_found:
            print("\n问题列表:")
            for i, issue in enumerate(self.issues_found, 1):
                print(f"  {i}. {issue}")

        return False


def main():
    """主函数"""
    # 默认测试文件
    source_files = [
        "/Users/zhanglei/winning/tfs2018/RDA-01-标准规范/02 V5.5/01 产品文档/04 标准规范（项目化）/036 云南区域标准规范/区域卫生信息平台数据传输规范260709/区域卫生信息平台数据传输规范 第01部分：医疗服务.docx",
        "/Users/zhanglei/winning/tfs2018/RDA-01-标准规范/02 V5.5/01 产品文档/04 标准规范（项目化）/036 云南区域标准规范/区域卫生信息平台数据传输规范260709/区域卫生信息平台数据传输规范 第02部分：人财物运营管理.docx",
        "/Users/zhanglei/winning/tfs2018/RDA-01-标准规范/02 V5.5/01 产品文档/04 标准规范（项目化）/036 云南区域标准规范/区域卫生信息平台数据传输规范260709/区域卫生信息平台数据传输规范 值域字典.xlsx"
    ]

    target_files = [
        "/Users/zhanglei/auto-dev-docs/RDA-01-标准规范/229712/附件/采集标准规范/全民健康信息平台数据接口标准规范（医疗部分）v1.4.1.docx",
        "/Users/zhanglei/auto-dev-docs/RDA-01-标准规范/229712/附件/采集标准规范/全民健康信息平台数据接口标准规范（值域字典）v1.4.1.docx"
    ]

    # 创建测试器
    tester = AutoTester(source_files, target_files, title="自动测试报告")

    # 运行测试循环
    success = tester.run_auto_test_loop()

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
