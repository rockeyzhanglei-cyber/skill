#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据模型比对 Skill 主程序（新流程）

新流程：
1. 格式转换：将原始文档（Word/Excel/PDF等）转换为MD
2. 标准化解析：从MD文件中提取表结构、字段信息和值域，输出标准化格式
3. 比对：比对两份标准化文档
4. 生成报告：生成HTML和MD报告
"""

import os
import sys
import json
import yaml
import random
from typing import Dict, List

# 添加Skill路径
SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SKILL_DIR)

from parsers.converter import DocumentConverter
from parsers.standard_parser import StandardParser, StandardDocument
from matchers.standard_comparator import StandardComparator
from matchers.self_validator import self_validate
from reporters.html_reporter import HTMLReporter
from reporters.markdown_reporter import MarkdownReporter


class QualityValidator:
    """质量验证器 - 每步完成后自动验证"""

    def __init__(self, config: dict = None):
        self.config = config or {}
        qv = self.config.get('quality_validation', {})
        self.enabled = qv.get('auto_validate', True)
        self.sample_ratio = qv.get('sample_ratio', 0.1)
        self.checks = qv.get('checks', ['table_count', 'field_count', 'field_content', 'key_fields'])
        self.on_failure = qv.get('on_failure', {}).get('strategy', 'warn')
        self.max_retry = qv.get('on_failure', {}).get('max_retry', 3)

    def validate_conversion(self, md_files: List[str], doc_type: str = 'unknown') -> Dict:
        """验证格式转换结果"""
        if not self.enabled:
            return {'passed': True, 'warnings': []}

        issues = []
        warnings = []

        if not md_files:
            issues.append('转换后无MD文件生成')
            return {'passed': False, 'issues': issues, 'warnings': warnings}

        for md_file in md_files:
            if not os.path.exists(md_file):
                issues.append(f'文件不存在: {md_file}')
                continue

            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # 检查表数量（支持多种命名格式）
            import re
            # 格式1: "### 表 N"
            table_count_pattern1 = len(re.findall(r'^###\s+表\s+\d+', content, re.MULTILINE))
            # 格式2: "### 表名 英文名" (如 "### 科室信息 JBKSXXB")
            table_count_pattern2 = len(re.findall(r'^###\s+[^\n]+\s+[A-Z_][A-Z0-9_]+\s*$', content, re.MULTILINE))
            # 格式3: "### 表名(英文名)" (如 "### *患者基本信息(m_patient)")
            table_count_pattern3 = len(re.findall(r'^###\s+.+?\([^)]+\)', content, re.MULTILINE))
            table_count = table_count_pattern1 + table_count_pattern2 + table_count_pattern3

            if table_count == 0:
                issues.append(f'{os.path.basename(md_file)} 未检测到表格')

            # 抽样检查表名质量
            all_headings = re.findall(r'^###\s+(.+)$', content, re.MULTILINE)
            named_headings = [h for h in all_headings
                            if not re.match(r'^表\s+\d+', h)  # 排除 "表 N"
                            and not re.match(r'^.+?\s+[A-Z_][A-Z0-9_]+$', h.strip())  # 排除 "表名 英文名"
                            and '(' not in h]  # 排除含括号的
            if named_headings:
                sample = named_headings[:max(3, int(len(named_headings) * self.sample_ratio))]
                generic_names = [n for n in sample if n.strip() in ['表', '']]
                if generic_names:
                    warnings.append(f'{os.path.basename(md_file)} 部分表名仅为"表 N"，无实际名称')

        passed = len(issues) == 0
        return {'passed': passed, 'issues': issues, 'warnings': warnings}

    def validate_parsing(self, doc: StandardDocument, doc_type: str = 'unknown') -> Dict:
        """验证标准化解析结果"""
        if not self.enabled:
            return {'passed': True, 'warnings': []}

        issues = []
        warnings = []

        # 表数量检查
        if 'table_count' in self.checks:
            if len(doc.tables) == 0:
                issues.append(f'{doc_type} 未解析出任何表')

        # 字段数量检查
        if 'field_count' in self.checks:
            total_fields = sum(len(t.fields) for t in doc.tables)
            if total_fields == 0:
                issues.append(f'{doc_type} 未解析出任何字段')
            elif len(doc.tables) > 0:
                avg_fields = total_fields / len(doc.tables)
                if avg_fields < 2:
                    warnings.append(f'{doc_type} 平均每表仅 {avg_fields:.1f} 个字段，可能解析不完整')

        # 关键字段检查
        if 'key_fields' in self.checks:
            key_fields = ['local_id', 'org_code', 'patient_name', 'id_no', 'gender_code']
            all_field_names = set()
            for table in doc.tables:
                for field in table.fields:
                    all_field_names.add(field.name.lower())

            found_keys = [k for k in key_fields if k.lower() in all_field_names]
            if not found_keys and len(doc.tables) > 3:
                warnings.append(f'{doc_type} 未检测到常见关键字段（local_id, org_code等）')

        # 字段内容抽样检查
        if 'field_content' in self.checks:
            sample_size = max(1, int(len(doc.tables) * self.sample_ratio))
            import random
            sample_tables = random.sample(doc.tables, min(sample_size, len(doc.tables)))
            for table in sample_tables:
                for field in table.fields[:5]:  # 每张表前5个字段
                    if not field.name:
                        issues.append(f'表 {table.name} 存在无名称字段')
                        break
                    # 检查是否错误地使用了数据元标识符作为字段名
                    if field.name.startswith('DE') and '.' in field.name:
                        warnings.append(f'表 {table.name} 的字段 {field.name} 使用了数据元标识符而非字段名')

        passed = len(issues) == 0
        return {'passed': passed, 'issues': issues, 'warnings': warnings}

    def validate_comparison(self, result, target_doc: StandardDocument, source_doc: StandardDocument) -> Dict:
        """验证比对结果"""
        if not self.enabled:
            return {'passed': True, 'warnings': []}

        issues = []
        warnings = []

        target_fields = sum(len(t.fields) for t in target_doc.tables)
        if target_fields == 0:
            issues.append('目标标准无字段可比对')
            return {'passed': False, 'issues': issues, 'warnings': warnings}

        matched_count = len(result.matched)
        modified_count = len(result.modified)
        new_count = len(result.new_fields)

        # 匹配率合理性检查
        match_rate = matched_count / target_fields * 100
        if match_rate < 5:
            warnings.append(f'匹配率极低（{match_rate:.1f}%），可能存在字段命名规范差异过大')
        elif match_rate > 95:
            warnings.append(f'匹配率极高（{match_rate:.1f}%），建议抽查确认匹配质量')

        # 检查是否有空表匹配
        empty_match_tables = [t.name for t in target_doc.tables
                            if t.fields and all(f.name == '' for f in t.fields)]
        if empty_match_tables:
            issues.append(f'存在空字段表: {", ".join(empty_match_tables[:3])}')

        passed = len(issues) == 0
        return {
            'passed': passed,
            'issues': issues,
            'warnings': warnings,
            'stats': {
                'target_fields': target_fields,
                'matched': matched_count,
                'modified': modified_count,
                'new': new_count,
                'match_rate': match_rate
            }
        }

    def print_result(self, step_name: str, result: Dict):
        """打印验证结果"""
        if not self.enabled:
            return

        issues = result.get('issues', [])
        warnings = result.get('warnings', [])

        if not issues and not warnings:
            print(f"  ✓ 质量验证通过")
            return

        if warnings:
            for w in warnings:
                print(f"  ⚠ 警告: {w}")

        if issues:
            for i in issues:
                print(f"  ✗ 问题: {i}")

            if self.on_failure == 'warn':
                print(f"  → 策略: 继续执行（on_failure=warn）")
            elif self.on_failure == 'stop':
                raise RuntimeError(f'{step_name} 质量验证失败，停止执行')


class DataModelCompareV2:
    """数据模型比对主类（新流程）"""

    def __init__(self, config_path: str = None):
        self.config = self._load_config(config_path)
        # 输出根目录优先级：config.yaml(workspace.root) > 环境变量 DATA_STD_OUTPUT > 默认 ~/data-model-compare-docs
        default_workspace = os.environ.get('DATA_STD_OUTPUT') or os.path.join(
            os.path.expanduser('~'), 'data-model-compare-docs')
        self.workspace = self.config.get('workspace', {}).get('root', default_workspace)

        # 初始化组件（按config.yaml中的实际key读取）
        self.converter = DocumentConverter(self.config.get('parsers', {}))
        self.parser = StandardParser(self.config.get('parsers', {}))

        # 构建comparator配置（从config.yaml的多个section合并）
        comparator_config = {
            'field_matching': self.config.get('field_matching', {}),
            'constraint_protection': self.config.get('constraint_protection', {}),
            'length_protection': self.config.get('length_protection', {}),
            'value_domain_matching': self.config.get('value_domain_matching', {}),
            'cross_table_relation': self.config.get('cross_table_relation', {}),
        }
        self.comparator = StandardComparator(comparator_config)

        self.html_reporter = HTMLReporter(self.config.get('reporters', {}).get('html', {}))
        self.md_reporter = MarkdownReporter(self.config.get('reporters', {}).get('markdown', {}))
        self.validator = QualityValidator(self.config)

    def _load_config(self, config_path: str = None) -> Dict:
        """加载配置文件"""
        if not config_path:
            config_path = os.path.join(SKILL_DIR, 'config.yaml')

        if not os.path.exists(config_path):
            return {}

        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def compare(self, source_files: List[str], target_files: List[str],
                output_dir: str = None, title: str = "数据模型比对报告",
                task_name: str = None) -> Dict:
        """执行比对（新流程）

        Args:
            source_files: 原标准文件列表
            target_files: 目标标准文件列表
            output_dir: 输出目录（可选）
            title: 报告标题
            task_name: 任务名称（可选，用于创建任务文件夹）
        """

        print("=" * 80)
        print("数据模型比对（新流程）")
        print("=" * 80)

        # 如果没有指定任务名称，使用标题作为任务名称
        if not task_name:
            task_name = title.replace(' ', '_').replace('/', '_')

        # 创建任务目录（直接在工作目录下）
        task_dir = os.path.join(self.workspace, task_name)
        os.makedirs(task_dir, exist_ok=True)

        # 创建临时目录（在任务目录下）
        temp_dir = os.path.join(task_dir, 'temp')
        os.makedirs(temp_dir, exist_ok=True)

        # ===== 初始化性能监控 =====
        from utils.performance_monitor import PerformanceMonitor
        monitor = PerformanceMonitor(temp_dir)
        monitor.start_task(title)

        # ========== 第一步：格式转换 ==========
        print("\n[第一步] 格式转换（将原始文档转换为MD）")
        monitor.start_step('格式转换')

        # 检查源文件是否存在
        for f in source_files + target_files:
            if not os.path.exists(f):
                print(f"  ✗ 错误: 文件不存在 - {f}")
                return {}

        # 检测原标准版本
        print("  检测原标准版本...")
        from utils.version_detector import detect_version_from_files
        source_version = detect_version_from_files(source_files)
        print(f"  → 原标准版本: {source_version}")

        # 转换原标准
        print("  转换原标准...")
        try:
            source_md_dir = os.path.join(temp_dir, 'source_md')
            source_md_files = self.converter.convert_batch(source_files, source_md_dir)
        except Exception as e:
            print(f"  ✗ 原标准转换失败: {e}")
            return {}

        # 转换目标标准
        print("  转换目标标准...")
        try:
            target_md_dir = os.path.join(temp_dir, 'target_md')
            target_md_files = self.converter.convert_batch(target_files, target_md_dir)
        except Exception as e:
            print(f"  ✗ 目标标准转换失败: {e}")
            return {}

        if not source_md_files or not target_md_files:
            print("✗ 格式转换失败")
            return {}

        # 质量验证：格式转换
        print("  质量验证...")
        conv_result = self.validator.validate_conversion(source_md_files + target_md_files, '格式转换')
        self.validator.print_result('格式转换', conv_result)
        monitor.end_step({'source_files': len(source_md_files), 'target_files': len(target_md_files)})

        # ========== 第二步：标准化解析 ==========
        print("\n[第二步] 标准化解析（提取表结构、字段信息和值域）")
        monitor.start_step('标准化解析')

        # 解析原标准
        print("  解析原标准...")
        try:
            source_std_path = os.path.join(temp_dir, 'source_standard.json')
            source_doc = self._parse_and_standardize(source_md_files, source_std_path)
        except Exception as e:
            print(f"  ✗ 原标准解析失败: {e}")
            return {}

        # 解析目标标准
        print("  解析目标标准...")
        try:
            target_std_path = os.path.join(temp_dir, 'target_standard.json')
            target_doc = self._parse_and_standardize(target_md_files, target_std_path)
        except Exception as e:
            print(f"  ✗ 目标标准解析失败: {e}")
            return {}

        if not source_doc or not target_doc:
            print("  ✗ 解析失败：文档为空")
            return {}

        print(f"  ✓ 原标准：{len(source_doc.tables)} 张表，{sum(len(t.fields) for t in source_doc.tables)} 个字段")
        print(f"  ✓ 目标标准：{len(target_doc.tables)} 张表，{sum(len(t.fields) for t in target_doc.tables)} 个字段")

        # 质量验证：标准化解析
        print("  质量验证...")
        parse_result = self.validator.validate_parsing(source_doc, '原标准')
        self.validator.print_result('原标准解析', parse_result)
        parse_result = self.validator.validate_parsing(target_doc, '目标标准')
        self.validator.print_result('目标标准解析', parse_result)
        monitor.end_step({
            'source_tables': len(source_doc.tables),
            'source_fields': sum(len(t.fields) for t in source_doc.tables),
            'target_tables': len(target_doc.tables),
            'target_fields': sum(len(t.fields) for t in target_doc.tables),
        })

        # ========== 第三步：比对 ==========
        print("\n[第三步] 比对两份标准化文档")
        monitor.start_step('比对')

        try:
            # 传递版本信息到比对器
            self.comparator.source_version = source_version
            compare_result = self.comparator.compare(source_doc, target_doc)
        except Exception as e:
            print(f"  ✗ 比对失败: {e}")
            return {}

        if not compare_result:
            print("  ✗ 比对失败：结果为空")
            return {}

        print(f"  ✓ 比对完成")
        print(f"    - 满足：{len(compare_result.matched)} 个字段")
        print(f"    - 需修改：{len(compare_result.modified)} 个字段")
        print(f"    - 需新增：{len(compare_result.new_fields)} 个字段")
        print(f"    - 需新增表：{len(compare_result.new_tables)} 张表")

        # 质量验证：比对结果
        print("  质量验证...")
        comp_result = self.validator.validate_comparison(compare_result, target_doc, source_doc)
        self.validator.print_result('比对结果', comp_result)

        # 打印匹配方式统计（从最终结果计算，保证与JSON一致）
        match_type_counts = {}
        for item in compare_result.matched:
            mt = item.get('match_type', 'unknown')
            match_type_counts[mt] = match_type_counts.get(mt, 0) + 1
        for item in compare_result.modified:
            mt = item.get('match_type', 'unknown')
            match_type_counts[mt] = match_type_counts.get(mt, 0) + 1
        match_type_labels = {
            'exact_english': '英文名精确匹配',
            'exact_chinese': '中文名精确匹配',
            'synonym': '同义词匹配',
            'semantic': '语义匹配',
            'keyword': '关键词匹配',
            'dictionary': '字典关联匹配',
            'control_field': '控制字段映射',
            'semantic_mapping': '语义映射',
            'standard_reference': '标准引用',
        }
        print(f"  匹配方式统计:")
        for mt, label in match_type_labels.items():
            cnt = match_type_counts.get(mt, 0)
            if cnt > 0:
                print(f"    - {label}: {cnt}")
        print(f"    - 新增字段: {len(compare_result.new_fields)}")

        # 记录匹配统计到监控器
        for item in compare_result.matched:
            mt = item.get('match_type', 'unknown')
            monitor.record_match(mt, item.get('table_name', ''), item.get('target_field', ''))
        for item in compare_result.modified:
            mt = item.get('match_type', 'unknown')
            monitor.record_match(mt + '_modified', item.get('table_name', ''), item.get('field_name', ''))
        for item in compare_result.new_fields:
            monitor.record_match('new_field', item.get('table_name', ''), item.get('name', ''))

        monitor.end_step({
            'matched': len(compare_result.matched),
            'modified': len(compare_result.modified),
            'new_fields': len(compare_result.new_fields),
            'new_tables': len(compare_result.new_tables),
        })

        # 保存比对结果
        compare_result_path = os.path.join(temp_dir, 'compare_result.json')
        self._save_compare_result(compare_result, compare_result_path)

        # 条件式值域约束装配（round6 固化）：读 conditional_constraints.json
        # 的 rules 给 matched/modified 注入 condition_display（地址族/电话族），
        # 同步回写 compare_result.json 与内存对象，三件套展示一致。
        try:
            import sys as _sys
            _sys.path.insert(0, os.path.join(
                os.path.dirname(os.path.abspath(__file__)), 'scripts'))
            from apply_conditional_constraints import apply_condition_display
            merged = apply_condition_display(temp_dir)
            if merged is not None:
                compare_result.matched = merged['matched']
                compare_result.modified = merged['modified']
                compare_result.new_fields = merged['new_fields']
                compare_result.new_tables = merged['new_tables']
        except Exception as e:
            print(f"  ⚠ 条件装配跳过: {e}")

        # 报告目录（任务目录下）；提前创建，供值域字典/自验证等补充步骤写入报告
        output_dir = os.path.join(task_dir, 'reports')
        os.makedirs(output_dir, exist_ok=True)

        # ========== 第三步（补充）：值域字典（代码表）比对 ==========
        # 与字段结构比对并列的独立维度；解析两份"值域字典"并比较代码覆盖。
        try:
            vd_result = self._compare_value_domains_step(
                source_files, target_md_dir, temp_dir, output_dir)
            if vd_result:
                monitor.record_match('value_domain', 'value_domain',
                                     f"matched={vd_result['summary']['matched_count']}")
        except Exception as e:
            print(f"  ⚠ 值域字典比对跳过: {e}")
            import traceback
            traceback.print_exc()

        # ========== 第三步（补充2）：自验证（漏配/误匹配检测 + KB 修复建议）===========
        try:
            sv_result = self._self_validate_step(
                compare_result, source_std_path, target_std_path, temp_dir, output_dir)
            if sv_result:
                monitor.record_match('self_validation', 'self_validation',
                                     f"leaks={sv_result['summary']['leak_count']},"
                                     f"suspects={sv_result['summary']['suspect_count']}")
        except Exception as e:
            print(f"  ⚠ 自验证跳过: {e}")
            import traceback
            traceback.print_exc()

        # ========== 第四步：生成报告 ==========
        print("\n[第四步] 生成报告")
        monitor.start_step('报告生成')

        # 准备报告数据
        report_data = self._prepare_report_data(compare_result)

        # 生成HTML报告
        try:
            html_path = os.path.join(output_dir, 'compare_report.html')
            self.html_reporter.generate(report_data, html_path, title, target_doc, source_doc)
            print(f"  ✓ HTML报告：{html_path}")
        except Exception as e:
            print(f"  ✗ HTML报告生成失败: {e}")

        # 生成MD报告
        try:
            md_path = os.path.join(output_dir, 'compare_report.md')
            self.md_reporter.generate(report_data, md_path, title, target_doc, source_doc)
            print(f"  ✓ MD报告：{md_path}")
        except Exception as e:
            print(f"  ✗ MD报告生成失败: {e}")

        # 生成可编辑的Excel文件
        try:
            import sys
            sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scripts'))
            from generate_excel import generate_excel

            excel_path = os.path.join(output_dir, 'compare_editable.xlsx')
            compare_result_path = os.path.join(task_dir, 'temp', 'compare_result.json')
            target_standard_path = os.path.join(task_dir, 'temp', 'target_standard.json')
            source_standard_path = os.path.join(task_dir, 'temp', 'source_standard.json')

            generate_excel(compare_result_path, target_standard_path, source_standard_path, excel_path)
            print(f"  ✓ Excel文件：{excel_path}")
        except Exception as e:
            print(f"  ✗ Excel文件生成失败: {e}")

        monitor.end_step({'html_path': html_path, 'md_path': md_path, 'excel_path': excel_path})

        # ===== 输出性能报告 =====
        perf_report = monitor.generate_report()
        monitor.print_summary(perf_report)

        print("\n" + "=" * 80)
        print("比对完成！")
        print("=" * 80)

        return compare_result

    def _compare_value_domains_step(self, source_files, target_md_dir, temp_dir, output_dir):
        """值域字典（代码表）比对步骤：解析两份值域字典并比较代码覆盖。

        目标标准的值域字典已从 docx 转换为 markdown（在 target_md_dir 中）；
        源标准的值域字典为 xlsx，直接解析。结果写入 value_domain_result.json
        并生成 value_domain_report.md。
        """
        import glob as _glob
        from parsers.value_domain_parser import (
            parse_value_domains_from_md, parse_value_domains_from_xlsx,
            parse_value_domains_from_flat_md, parse_value_domains_from_sectioned_md)
        from matchers.value_domain_comparator import compare_value_domains

        # 1) 目标标准值域字典（docx 转 MD，扁平宽表格式：# 数据元值域）
        target_md = None
        if target_md_dir:
            for p in _glob.glob(os.path.join(target_md_dir, '*.md')):
                if '值域字典' in os.path.basename(p):
                    target_md = p
                    break
        # 2) 源标准值域字典：优先 source_md_dir 中的 '值域字典' MD（docx 转换，
        #    形如『编号小节 + 代码表』），其次 source_files 中的 .xlsx（兼容旧格式）
        source_md_dir = os.path.join(temp_dir, 'source_md')
        source_md = None
        if os.path.isdir(source_md_dir):
            for p in _glob.glob(os.path.join(source_md_dir, '*.md')):
                if '值域字典' in os.path.basename(p):
                    source_md = p
                    break
        source_xlsx = None
        for f in (source_files or []):
            if '值域字典' in os.path.basename(f) and f.lower().endswith('.xlsx'):
                source_xlsx = f
                break

        if not target_md or (not source_md and not source_xlsx):
            print("  ℹ 未同时检测到目标/源 值域字典文件，跳过值域维度比对")
            return None

        def _parse_vd(path):
            """格式无关的取值域字典解析：依次尝试 小节标题(docx) / 扁平宽表
            (xlsx→md) / 通用MD / 原始xlsx，取首个非空结果。源/目标取值域
            字典的格式与比对方向无关，避免『目标=扁平、源=小节』的硬编码假设。"""
            if path and path.lower().endswith('.xlsx'):
                d = parse_value_domains_from_xlsx(path)
                if d:
                    return d
            for fn in (parse_value_domains_from_sectioned_md,
                       parse_value_domains_from_flat_md,
                       parse_value_domains_from_md):
                d = fn(path)
                if d:
                    return d
            return {}

        print("\n[第三步·补充] 值域字典（代码表）比对")
        td = _parse_vd(target_md)
        sd = _parse_vd(source_md) if source_md else (_parse_vd(source_xlsx) if source_xlsx else {})
        if not td or not sd:
            print("  ℹ 值域字典解析为空，跳过")
            return None
        res = compare_value_domains(td, sd)

        # 保存 JSON
        vd_path = os.path.join(temp_dir, 'value_domain_result.json')
        with open(vd_path, 'w', encoding='utf-8') as f:
            json.dump(res, f, ensure_ascii=False, indent=2)
        # 生成 Markdown 报告
        self._generate_value_domain_report(res, os.path.join(output_dir, 'value_domain_report.md'))

        s = res['summary']
        print(f"  ✓ 目标值域 {s['target_domain_count']} 个 / 源值域 {s['source_domain_count']} 个")
        print(f"    - 可匹配 {s['matched_count']} 个（完全覆盖 {s['fully_covered_count']} / 部分覆盖 {s['partial_covered_count']}）")
        print(f"    - 仅目标有 {s['target_only_count']} 个 / 仅源有 {s['source_only_count']} 个")
        print(f"    - 平均代码覆盖率 {s['avg_coverage']:.1%}")
        print(f"  ✓ 值域比对结果：{vd_path}")
        return res

    def _generate_value_domain_report(self, res: dict, md_path: str):
        """生成值域字典比对 Markdown 报告。"""
        s = res['summary']
        lines = []
        lines.append('# 值域字典（代码表）比对报告\n')
        lines.append('## 概要\n')
        lines.append(f'- 目标标准值域字典：**{s["target_domain_count"]}** 个')
        lines.append(f'- 源标准值域字典：**{s["source_domain_count"]}** 个')
        lines.append(f'- 可匹配：**{s["matched_count"]}** 个（完全覆盖 {s["fully_covered_count"]} / 部分覆盖 {s["partial_covered_count"]}）')
        lines.append(f'- 仅目标标准有：**{s["target_only_count"]}** 个')
        lines.append(f'- 仅源标准有：**{s["source_only_count"]}** 个')
        lines.append(f'- 平均代码覆盖率：**{s["avg_coverage"]:.1%}**\n')

        lines.append('## 一、匹配但部分覆盖（目标代码缺失/名称冲突，需补充）\n')
        partial = [m for m in res['matched'] if not m['fully_covered']]
        if partial:
            lines.append('| 目标值域 | 标准号 | 覆盖率 | 缺失代码数 | 名称冲突数 |')
            lines.append('| --- | --- | --- | --- | --- |')
            for m in sorted(partial, key=lambda x: x['coverage'])[:200]:
                lines.append(
                    f"| {m['target_name']} | {m['target_std_no']} | "
                    f"{m['coverage']:.1%} | {len(m['missing_codes'])} | {len(m['name_conflicts'])} |")
        else:
            lines.append('（无）\n')

        lines.append('\n## 二、仅目标标准有的值域（源标准需补充）\n')
        if res['target_only']:
            lines.append('| 目标值域 | 标准号 | 代码数 |')
            lines.append('| --- | --- | --- |')
            for m in res['target_only'][:300]:
                lines.append(f"| {m['target_name']} | {m['target_std_no']} | {m['code_count']} |")
        else:
            lines.append('（无）\n')

        lines.append('\n## 三、仅源标准有的值域\n')
        if res['source_only']:
            lines.append('| 源值域 | 标准号 | 代码数 |')
            lines.append('| --- | --- | --- |')
            for m in res['source_only'][:300]:
                lines.append(f"| {m['source_name']} | {m['source_std_no']} | {m['code_count']} |")
        else:
            lines.append('（无）\n')

        with open(md_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        print(f"  ✓ 值域比对报告：{md_path}")

    def _self_validate_step(self, compare_result, source_standard_path: str,
                            target_standard_path: str, temp_dir: str, output_dir: str):
        """自验证步骤：在不依赖人工的前提下，对字段比对结果做质量体检，
        自动检测漏配（本应匹配却判为新增）与误匹配（模糊命中但核心概念不一致），
        并产出可供人工复核/回写知识库的修复建议。
        """
        if not compare_result:
            return None
        if not os.path.exists(source_standard_path) or not os.path.exists(target_standard_path):
            print("  ℹ 缺少源/目标标准化文档，跳过自验证")
            return None

        with open(source_standard_path, 'r', encoding='utf-8') as f:
            source_standard = json.load(f)
        with open(target_standard_path, 'r', encoding='utf-8') as f:
            target_standard = json.load(f)

        # self_validate 期望 dict（与 compare_result.json 结构一致），
        # 而 compare_result 是 CompareResult 对象，这里加载落盘的 JSON 传入。
        cr_path = os.path.join(temp_dir, 'compare_result.json')
        if not os.path.exists(cr_path):
            print("  ℹ 缺少 compare_result.json，跳过自验证")
            return None
        with open(cr_path, 'r', encoding='utf-8') as f:
            compare_result_dict = json.load(f)
        sv = self_validate(compare_result_dict, source_standard, target_standard)

        # 保存 JSON
        sv_path = os.path.join(temp_dir, 'self_validation_result.json')
        with open(sv_path, 'w', encoding='utf-8') as f:
            json.dump(sv, f, ensure_ascii=False, indent=2)

        # 生成 Markdown 报告
        self._generate_self_validation_report(sv, os.path.join(output_dir, 'self_validation_report.md'))

        s = sv['summary']
        print("\n[第三步·补充2] 自验证（漏配/误匹配体检）")
        print(f"  ✓ 漏配候选：{s['leak_count']} 个（建议补充字段映射）")
        print(f"  ✓ 误匹配候选：{s['suspect_count']} 个（建议人工复核）")
        print(f"  ✓ 自验证结果：{sv_path}")
        return sv

    def _generate_self_validation_report(self, sv: dict, md_path: str):
        """生成自验证 Markdown 报告（漏配 + 误匹配 + KB 修复建议）。"""
        lines = []
        lines.append('# 自验证报告（漏配 / 误匹配体检）\n')
        s = sv['summary']
        lines.append('## 概要\n')
        lines.append(f'- 漏配候选（建议补充字段映射）：**{s["leak_count"]}** 个')
        lines.append(f'- 误匹配候选（建议人工复核）：**{s["suspect_count"]}** 个')
        lines.append('')
        lines.append('> 说明：本体检由程序自动完成，仅给出"高可信"的可疑项，'
                     '最终仍需人工在 compare_editable.xlsx 中确认或修正。\n')

        # 一、漏配
        lines.append('## 一、漏配候选（目标字段已存在同名源字段，但被判为新增）\n')
        lines.append(f'> 共 {len(sv["leaks"])} 条；"候选源表数"表示该中文名在源标准中的出现次数，'
                     '人工确认后可在 compare_editable.xlsx 中补映射，回写知识库。\n')
        if sv['leaks']:
            lines.append('| 目标表 | 目标字段(中文) | 建议源字段(首选) | 候选源表数 |')
            lines.append('| --- | --- | --- | --- |')
            for lk in sv['leaks'][:400]:
                suggs = lk.get('suggested_source', [])
                first = suggs[0] if suggs else {}
                src_str = f"{first.get('table','')}.{first.get('field','')}" \
                    if first else '—'
                if len(suggs) > 1:
                    src_str += f" 等{len(suggs)}个"
                lines.append(
                    f"| {lk.get('table','')} | {lk.get('chinese_name','')} | {src_str} | {len(suggs)} |")
        else:
            lines.append('（无明显漏配）\n')

        # 二、误匹配
        lines.append('\n## 二、误匹配候选（模糊命中但核心概念不一致）\n')
        if sv['suspects']:
            lines.append('| 目标表 | 目标字段 | 目标(中文) | 命中源字段 | 源(中文) | 匹配方式 |')
            lines.append('| --- | --- | --- | --- | --- | --- |')
            for su in sv['suspects'][:400]:
                lines.append(
                    f"| {su.get('table','')} | {su.get('target_field','')} | {su.get('target_cn','')} | "
                    f"{su.get('source_field','')} | {su.get('source_cn','')} | {su.get('match_type','')} |")
        else:
            lines.append('（无明显误匹配）\n')

        with open(md_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        print(f"  ✓ 自验证报告：{md_path}")

    def _parse_and_standardize(self, md_files: List[str], output_path: str) -> StandardDocument:
        """解析并标准化文档"""
        combined_doc = StandardDocument(source_file='combined')

        for md_file in md_files:
            doc = self.parser.parse(md_file)
            combined_doc.tables.extend(doc.tables)

        # 保存标准化文档
        combined_doc.to_json(output_path)
        print(f"  ✓ 标准化文档已保存：{output_path}")

        return combined_doc

    def _save_compare_result(self, result, output_path: str):
        """保存比对结果"""
        from dataclasses import asdict

        result_dict = {
            'matched': result.matched,
            'modified': result.modified,
            'new_fields': result.new_fields,
            'new_tables': result.new_tables
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result_dict, f, ensure_ascii=False, indent=2)

        print(f"  ✓ 比对结果已保存：{output_path}")

    def _prepare_report_data(self, compare_result) -> Dict:
        """准备报告数据，将比对结果转换为报告格式"""
        # 转换matched字段
        matched = []
        for m in compare_result.matched:
            matched.append({
                'table_name': m['table_name'],
                'target_field': m['target_field'],
                'target_comment': m['target_chinese_name'],
                'source_table': m['source_table'],
                'source_table_comment': m.get('source_table_chinese_name', ''),
                'source_field': m['source_field'],
                'source_comment': m.get('source_field_chinese_name', ''),
                'match_type': m['match_type']
            })

        # 转换modified字段
        modified_fields = []
        for m in compare_result.modified:
            modified_fields.append({
                'table_name': m['table_name'],
                'field_name': m['field_name'],
                'field_comment': m['field_chinese_name'],
                'source_table': m['source_table'],
                'source_table_comment': m.get('source_table_chinese_name', ''),
                'source_field': m['source_field'],
                'source_comment': m.get('source_field_chinese_name', ''),
                'match_type': m.get('match_type', ''),
                'modifications': m['modifications']
            })

        # 转换new_fields
        new_fields = []
        for n in compare_result.new_fields:
            new_field = {
                'table_name': n['table_name'],
                'name': n['name'],
                'comment': n['chinese_name'],
                'type': n.get('data_type', ''),
                'length': n.get('length', 0),
                'constraint': n.get('constraint', 'O'),
                'generated_name': n.get('generated_name', ''),  # 生成的英文字段名
                'chinese_name': n['chinese_name'],  # 保持中文名与目标标准一致
                'new_field_target': n.get('new_field_target', n['table_name']),  # 新增字段的目标表
                'source_table_name': n.get('source_table_name', n.get('new_field_target', n['table_name'])),  # 源标准表名
                'description': n.get('description', '')  # 字段说明
            }
            # 保留去重标记
            if n.get('deduplicated'):
                new_field['deduplicated'] = True
                new_field['dedup_note'] = n.get('dedup_note', '')
                new_field['dedup_source_table'] = n.get('dedup_source_table', '')
            # 保留重定向标记
            if n.get('redirected_from'):
                new_field['redirected_from'] = n['redirected_from']
                new_field['redirect_reason'] = n.get('redirect_reason', '')
            new_fields.append(new_field)

        # 转换new_tables
        new_tables = []
        for t in compare_result.new_tables:
            new_tables.append({
                'table_name': t['table_name'],
                'chinese_name': t.get('chinese_name', ''),
                'generated_name': t.get('generated_name', ''),  # 推荐的英文表名
                'field_count': t.get('field_count', 0),
                'reason': t.get('reason', '')
            })

        return {
            'matched': matched,
            'modified_fields': modified_fields,
            'new_fields': new_fields,
            'new_tables': new_tables
        }


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='数据模型比对工具（新流程）')
    parser.add_argument('--source', '-s', nargs='+', required=True, help='原标准文件路径')
    parser.add_argument('--target', '-t', nargs='+', required=True, help='目标标准文件路径')
    parser.add_argument('--output', '-o', help='输出目录')
    parser.add_argument('--title', default='数据模型比对报告', help='报告标题')
    parser.add_argument('--config', '-c', help='配置文件路径')
    parser.add_argument('--feedback', '-f', help='用户编辑后的 Excel 文件路径（用于回写知识库）')

    args = parser.parse_args()

    # 如果提供了 feedback 参数，先处理 Excel 回写
    if args.feedback:
        print("=" * 80)
        print("检测到 --feedback 参数，开始处理 Excel 回写...")
        print("=" * 80)

        # 推断任务目录（与 DataModelCompareV2 的 workspace 推导保持一致）
        task_name = args.title.replace(' ', '_').replace('/', '_')
        workspace = os.environ.get('DATA_STD_OUTPUT') or os.path.join(
            os.path.expanduser('~'), 'data-model-compare-docs')
        task_dir = os.path.join(workspace, task_name)
        temp_dir = os.path.join(task_dir, 'temp')

        # 检查必要的文件是否存在
        compare_result_path = os.path.join(temp_dir, 'compare_result.json')
        target_standard_path = os.path.join(temp_dir, 'target_standard.json')
        source_standard_path = os.path.join(temp_dir, 'source_standard.json')

        missing_files = []
        if not os.path.exists(args.feedback):
            missing_files.append(f'Excel 文件: {args.feedback}')
        if not os.path.exists(compare_result_path):
            missing_files.append(f'compare_result.json: {compare_result_path}')
        if not os.path.exists(target_standard_path):
            missing_files.append(f'target_standard.json: {target_standard_path}')
        if not os.path.exists(source_standard_path):
            missing_files.append(f'source_standard.json: {source_standard_path}')

        if missing_files:
            print("\n错误: 以下文件不存在:")
            for f in missing_files:
                print(f"  - {f}")
            print("\n请确保已经运行过比对，并且 Excel 文件路径正确。")
            sys.exit(1)

        # 调用 read_excel_feedback.py
        from scripts.read_excel_feedback import process_feedback
        try:
            changes = process_feedback(
                excel_path=args.feedback,
                compare_result_path=compare_result_path,
                target_standard_path=target_standard_path,
                source_standard_path=source_standard_path,
                task_dir=task_dir,
                skill_dir=SKILL_DIR,
            )

            if changes:
                print(f"\n✓ Excel 回写完成，检测到 {len(changes)} 处变更")
                print("  知识库已更新，重新运行比对以应用用户映射...\n")
            else:
                print("\n✓ Excel 回写完成，未检测到变更")
                print("  继续运行比对...\n")
        except Exception as e:
            print(f"\n✗ Excel 回写失败: {e}")
            print("  将继续运行比对，但用户映射可能不会生效...")
            import traceback
            traceback.print_exc()
            print()

    # 创建比对实例
    comparer = DataModelCompareV2(args.config)

    # 执行比对
    comparer.compare(
        source_files=args.source,
        target_files=args.target,
        output_dir=args.output,
        title=args.title
    )


if __name__ == '__main__':
    main()
