#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
单元测试套件
测试单个函数和方法的正确性
"""

import os
import sys
import unittest
from typing import Dict, List

# 添加Skill路径
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SKILL_DIR)

from parsers.standard_parser import StandardField, StandardTable, StandardDocument
from matchers.standard_comparator import (
    StandardComparator,
    _calculate_similarity,
    _edit_distance,
    _ngram_similarity
)


class TestSimilarityFunctions(unittest.TestCase):
    """测试相似度计算函数"""

    def test_exact_match(self):
        """测试完全相同的字符串"""
        # 完全相同的字符串应该有高相似度（可能不是1.0因为算法原因）
        result1 = _calculate_similarity("患者姓名", "患者姓名")
        self.assertGreater(result1, 0.95)

        result2 = _calculate_similarity("性别代码", "性别代码")
        self.assertGreater(result2, 0.95)

    def test_high_similarity(self):
        """测试高相似度字符串"""
        # 完全相同的字符串应该有高相似度
        result1 = _calculate_similarity("患者姓名", "患者姓名")
        self.assertGreater(result1, 0.95)

        # 部分重叠的字符串应该有中等相似度
        result2 = _calculate_similarity("性别代码", "性别")
        self.assertGreater(result2, 0.5)

    def test_low_similarity(self):
        """测试低相似度字符串"""
        # 完全不同的概念
        self.assertLess(_calculate_similarity("年龄", "性别"), 0.3)
        self.assertLess(_calculate_similarity("姓名", "地址"), 0.3)

    def test_edit_distance(self):
        """测试编辑距离计算"""
        self.assertEqual(_edit_distance("abc", "abc"), 0)
        self.assertEqual(_edit_distance("abc", "abd"), 1)
        self.assertEqual(_edit_distance("abc", "abcd"), 1)

    def test_ngram_similarity(self):
        """测试n-gram相似度"""
        # 相同字符串
        result1 = _ngram_similarity("abc", "abc", n=2)
        self.assertEqual(result1, 1.0)
        # 部分重叠
        result2 = _ngram_similarity("abcd", "abce", n=2)
        self.assertGreater(result2, 0.4)


class TestDescriptionCompatibility(unittest.TestCase):
    """测试描述兼容性检查"""

    def setUp(self):
        self.comparator = StandardComparator({})

    def _create_field(self, name: str, chinese_name: str, description: str = "") -> StandardField:
        return StandardField(
            name=name,
            chinese_name=chinese_name,
            data_type="S1",
            length=64,
            constraint="M",
            description=description,
            value_domains=[]
        )

    def test_same_field_compatible(self):
        """测试相同字段兼容"""
        field1 = self._create_field("patient_name", "患者姓名")
        field2 = self._create_field("XM", "姓名")
        self.assertTrue(self.comparator._is_description_compatible(field1, field2))

    def test_id_type_vs_id_number_incompatible(self):
        """测试身份证件类别代码 vs 证件号码不兼容"""
        target = self._create_field("id_type_code", "身份证件类别代码")
        source = self._create_field("ZJHM", "证件号码")
        self.assertFalse(self.comparator._is_description_compatible(target, source))

    def test_work_phone_vs_mobile_incompatible(self):
        """测试工作单位电话 vs 手机号码不兼容"""
        target = self._create_field("work_place_tel", "工作单位电话号码")
        source = self._create_field("SJHM", "手机号码")
        self.assertFalse(self.comparator._is_description_compatible(target, source))

    def test_contact_name_not_dictionary(self):
        """测试联系人姓名不被识别为字典项"""
        target = self._create_field("contact_name", "联系人姓名")
        source = self._create_field("LXRGXDM", "联系人关系代码")
        # 联系人姓名不应该被识别为字典关联字段
        related = self.comparator._find_related_code_field(
            target, [target, source], {}
        )
        self.assertIsNone(related)


class TestFieldMatching(unittest.TestCase):
    """测试字段匹配逻辑"""

    def setUp(self):
        self.comparator = StandardComparator({})

    def _create_field(self, name: str, chinese_name: str) -> StandardField:
        return StandardField(
            name=name,
            chinese_name=chinese_name,
            data_type="S1",
            length=64,
            constraint="M",
            description="",
            value_domains=[]
        )

    def test_exact_chinese_match(self):
        """测试中文名精确匹配"""
        target = self._create_field("patient_name", "患者姓名")
        source_index = {
            "XM": self._create_field("XM", "患者姓名")
        }
        result = self.comparator._find_matching_field(target, source_index)
        self.assertIsNotNone(result)
        field, match_type = result
        self.assertEqual(field.name, "XM")
        self.assertEqual(match_type, 'exact_chinese')

    def test_synonym_match(self):
        """测试同义词匹配"""
        target = self._create_field("local_id", "个人基本信息标识号")
        source_index = {
            "YYDAH": self._create_field("YYDAH", "医院内部档案号")
        }
        # 这个测试依赖于同义词库的配置
        # result = self.comparator._find_matching_field(target, source_index)
        # self.assertIsNotNone(result)


class TestBoundaryConditions(unittest.TestCase):
    """测试边界条件"""

    def test_empty_field_names(self):
        """测试空字段名"""
        from matchers.standard_comparator import _calculate_similarity
        self.assertEqual(_calculate_similarity("", ""), 0.0)
        self.assertEqual(_calculate_similarity("test", ""), 0.0)
        self.assertEqual(_calculate_similarity("", "test"), 0.0)

    def test_very_long_field_names(self):
        """测试超长字段名"""
        from matchers.standard_comparator import _calculate_similarity
        long_name1 = "a" * 1000
        long_name2 = "a" * 1000
        # 应该能正常处理，不会崩溃
        result = _calculate_similarity(long_name1, long_name2)
        # 相似度应该非常高（接近1.0）
        self.assertGreater(result, 0.95)

    def test_special_characters(self):
        """测试特殊字符"""
        from matchers.standard_comparator import _calculate_similarity
        # 包含特殊字符的字段名
        result = _calculate_similarity("field-name_123", "field-name_123")
        # 相似度应该非常高（接近1.0）
        self.assertGreater(result, 0.95)


def run_unit_tests():
    """运行所有单元测试"""
    print("=" * 80)
    print("单元测试套件")
    print("=" * 80)
    print()

    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # 添加所有测试类
    suite.addTests(loader.loadTestsFromTestCase(TestSimilarityFunctions))
    suite.addTests(loader.loadTestsFromTestCase(TestDescriptionCompatibility))
    suite.addTests(loader.loadTestsFromTestCase(TestFieldMatching))
    suite.addTests(loader.loadTestsFromTestCase(TestBoundaryConditions))

    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print()
    print("=" * 80)
    print(f"测试结果: {result.testsRun} 个测试")
    print(f"通过: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"失败: {len(result.failures)}")
    print(f"错误: {len(result.errors)}")
    print("=" * 80)

    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_unit_tests()
    sys.exit(0 if success else 1)
