#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
端到端测试套件
使用真实文档测试完整流程
"""

import os
import sys
import time
import subprocess
from typing import Dict, List

# 添加Skill路径
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SKILL_DIR)


class EndToEndTester:
    """端到端测试器"""

    def __init__(self):
        self.main_script = os.path.join(SKILL_DIR, 'main.py')
        self.results = {
            'passed': 0,
            'failed': 0,
            'details': []
        }

    def test_complete_workflow_with_real_docs(self):
        """使用真实文档测试完整工作流"""
        test_name = "完整工作流（真实文档）"

        # 测试文档路径
        source_files = [
            "/Users/zhanglei/winning/tfs2018/RDA-01-标准规范/02 V5.5/01 产品文档/04 标准规范（项目化）/036 云南区域标准规范/区域卫生信息平台数据传输规范260709/区域卫生信息平台数据传输规范 第01部分：医疗服务.docx"
        ]
        target_files = [
            "/Users/zhanglei/auto-dev-docs/RDA-01-标准规范/229712/附件/采集标准规范/全民健康信息平台数据接口标准规范（医疗部分）v1.4.1.docx"
        ]

        # 检查文件是否存在
        for f in source_files + target_files:
            if not os.path.exists(f):
                self.results['failed'] += 1
                print(f"✗ FAIL: {test_name}")
                print(f"  文件不存在: {f}")
                return

        # 构建命令
        cmd = [
            sys.executable, self.main_script,
            '--source'
        ] + source_files + [
            '--target'
        ] + target_files + [
            '--title', 'E2E测试报告'
        ]

        # 执行命令
        start_time = time.time()
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120  # 2分钟超时
            )
            duration = time.time() - start_time

            # 验证结果
            success = result.returncode == 0
            has_html = 'HTML报告' in result.stdout
            has_md = 'MD报告' in result.stdout

            if success and has_html and has_md:
                self.results['passed'] += 1
                print(f"✓ PASS: {test_name}")
                print(f"  执行时间: {duration:.2f}秒")
                print(f"  报告生成成功")
            else:
                self.results['failed'] += 1
                print(f"✗ FAIL: {test_name}")
                print(f"  返回码: {result.returncode}")
                if not success:
                    print(f"  错误: {result.stderr[:200]}")

        except subprocess.TimeoutExpired:
            self.results['failed'] += 1
            print(f"✗ FAIL: {test_name}")
            print(f"  执行超时（>120秒）")
        except Exception as e:
            self.results['failed'] += 1
            print(f"✗ FAIL: {test_name}")
            print(f"  异常: {e}")

    def test_error_handling_missing_file(self):
        """测试缺失文件的错误处理"""
        test_name = "错误处理（缺失文件）"

        cmd = [
            sys.executable, self.main_script,
            '--source', '/nonexistent/file.docx',
            '--target', '/nonexistent/file2.docx',
            '--title', '错误测试'
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            # 应该返回非0退出码
            if result.returncode != 0:
                self.results['passed'] += 1
                print(f"✓ PASS: {test_name}")
                print(f"  正确处理缺失文件错误")
            else:
                self.results['failed'] += 1
                print(f"✗ FAIL: {test_name}")
                print(f"  应该返回错误码，但返回了 0")

        except Exception as e:
            self.results['failed'] += 1
            print(f"✗ FAIL: {test_name}")
            print(f"  异常: {e}")

    def test_performance_large_comparison(self):
        """测试性能（大文档比对）"""
        test_name = "性能测试（多文件比对）"

        # 使用多个文件测试性能
        source_files = [
            "/Users/zhanglei/winning/tfs2018/RDA-01-标准规范/02 V5.5/01 产品文档/04 标准规范（项目化）/036 云南区域标准规范/区域卫生信息平台数据传输规范260709/区域卫生信息平台数据传输规范 第01部分：医疗服务.docx",
            "/Users/zhanglei/winning/tfs2018/RDA-01-标准规范/02 V5.5/01 产品文档/04 标准规范（项目化）/036 云南区域标准规范/区域卫生信息平台数据传输规范260709/区域卫生信息平台数据传输规范 第02部分：人财物运营管理.docx"
        ]
        target_files = [
            "/Users/zhanglei/auto-dev-docs/RDA-01-标准规范/229712/附件/采集标准规范/全民健康信息平台数据接口标准规范（医疗部分）v1.4.1.docx",
            "/Users/zhanglei/auto-dev-docs/RDA-01-标准规范/229712/附件/采集标准规范/全民健康信息平台数据接口标准规范（值域字典）v1.4.1.docx"
        ]

        # 检查文件是否存在
        for f in source_files + target_files:
            if not os.path.exists(f):
                self.results['failed'] += 1
                print(f"✗ FAIL: {test_name}")
                print(f"  文件不存在: {f}")
                return

        cmd = [
            sys.executable, self.main_script,
            '--source'
        ] + source_files + [
            '--target'
        ] + target_files + [
            '--title', '性能测试报告'
        ]

        start_time = time.time()
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=180  # 3分钟超时
            )
            duration = time.time() - start_time

            if result.returncode == 0:
                # 性能指标
                max_acceptable_time = 120  # 最多2分钟

                if duration < max_acceptable_time:
                    self.results['passed'] += 1
                    print(f"✓ PASS: {test_name}")
                    print(f"  执行时间: {duration:.2f}秒 (阈值: {max_acceptable_time}秒)")
                else:
                    self.results['failed'] += 1
                    print(f"⚠ WARN: {test_name}")
                    print(f"  执行时间: {duration:.2f}秒 (超过阈值 {max_acceptable_time}秒)")
            else:
                self.results['failed'] += 1
                print(f"✗ FAIL: {test_name}")
                print(f"  返回码: {result.returncode}")

        except subprocess.TimeoutExpired:
            self.results['failed'] += 1
            print(f"✗ FAIL: {test_name}")
            print(f"  执行超时（>180秒）")
        except Exception as e:
            self.results['failed'] += 1
            print(f"✗ FAIL: {test_name}")
            print(f"  异常: {e}")

    def run_all_tests(self):
        """运行所有端到端测试"""
        print("=" * 80)
        print("端到端测试套件")
        print("=" * 80)
        print()

        self.test_complete_workflow_with_real_docs()
        print()
        self.test_error_handling_missing_file()
        print()
        self.test_performance_large_comparison()

        print()
        print("=" * 80)
        print(f"测试结果: {self.results['passed']} 通过, {self.results['failed']} 失败")
        print("=" * 80)

        return self.results


def run_e2e_tests():
    """运行端到端测试"""
    tester = EndToEndTester()
    return tester.run_all_tests()


if __name__ == '__main__':
    results = run_e2e_tests()
    sys.exit(0 if results['failed'] == 0 else 1)
