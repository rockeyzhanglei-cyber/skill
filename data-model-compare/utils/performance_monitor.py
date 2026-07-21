#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
性能监控器

记录每个步骤的耗时、内存使用、匹配统计。
生成性能报告供分析和优化。

使用方式：
    monitor = PerformanceMonitor(output_dir)
    monitor.start_task('比对任务')

    monitor.start_step('格式转换')
    # ... 执行转换 ...
    monitor.end_step({'file_count': 5})

    monitor.record_match('exact_chinese', '表A', 'field1', '表B', 'field2')

    report = monitor.generate_report()
"""

import time
import json
import os
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional


class PerformanceMonitor:
    """性能监控器"""

    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        self.task_name = ''
        self.start_time = None
        self.steps: List[dict] = []
        self.current_step: Optional[dict] = None
        self.match_details: Dict[str, list] = defaultdict(list)

        # 内存跟踪（不强制依赖 psutil）
        self._has_psutil = self._check_psutil()

    def _check_psutil(self) -> bool:
        try:
            import psutil
            return True
        except ImportError:
            return False

    def _current_memory(self) -> float:
        """获取当前内存使用（MB）"""
        if self._has_psutil:
            import psutil
            return psutil.Process().memory_info().rss / 1024 / 1024
        return 0.0

    def start_task(self, task_name: str):
        """开始一个比对任务"""
        self.task_name = task_name
        self.start_time = time.time()
        self.steps = []
        self.match_details = defaultdict(list)
        self.initial_memory = self._current_memory()

    def start_step(self, step_name: str):
        """开始一个步骤"""
        self.current_step = {
            'name': step_name,
            'start_time': time.time(),
            'start_memory': self._current_memory()
        }

    def end_step(self, extra_data: dict = None):
        """结束一个步骤"""
        if self.current_step:
            self.current_step['end_time'] = time.time()
            self.current_step['duration'] = self.current_step['end_time'] - self.current_step['start_time']
            self.current_step['end_memory'] = self._current_memory()
            self.current_step['memory_delta'] = (
                self.current_step['end_memory'] - self.current_step['start_memory']
            )
            if extra_data:
                self.current_step.update(extra_data)
            self.steps.append(dict(self.current_step))
            self.current_step = None

    def record_match(self, match_type: str, target_table: str, target_field: str,
                     source_table: str = '', source_field: str = '',
                     confidence: float = 1.0):
        """记录一次匹配详情"""
        self.match_details[match_type].append({
            'target_table': target_table,
            'target_field': target_field,
            'source_table': source_table,
            'source_field': source_field,
            'confidence': confidence,
            'timestamp': time.time()
        })

    def record_matches_batch(self, match_type: str, matches: list):
        """批量记录匹配"""
        for m in matches:
            self.match_details[match_type].append({
                'target_table': m.get('table_name', ''),
                'target_field': m.get('target_field', m.get('field_name', m.get('name', ''))),
                'source_table': m.get('source_table', ''),
                'source_field': m.get('source_field', ''),
                'confidence': m.get('confidence', 1.0),
                'timestamp': time.time()
            })

    def generate_report(self) -> dict:
        """生成性能报告"""
        total_time = time.time() - self.start_time if self.start_time else 0

        # 匹配统计
        match_summary = {}
        for mt, details in self.match_details.items():
            confidences = [d['confidence'] for d in details]
            avg_conf = sum(confidences) / len(confidences) if confidences else 0
            # 找出匹配最多的表
            table_counts = defaultdict(int)
            for d in details:
                table_counts[d['target_table']] += 1
            top_tables = sorted(table_counts.items(), key=lambda x: -x[1])[:5]

            match_summary[mt] = {
                'count': len(details),
                'avg_confidence': round(avg_conf, 3),
                'top_tables': [{'table': t, 'count': c} for t, c in top_tables]
            }

        report = {
            'task_name': self.task_name,
            'timestamp': datetime.now().isoformat(),
            'total_duration_seconds': round(total_time, 2),
            'peak_memory_mb': round(self._current_memory(), 2),
            'initial_memory_mb': round(getattr(self, 'initial_memory', 0), 2),
            'steps': [
                {
                    'name': s['name'],
                    'duration_seconds': round(s['duration'], 2),
                    'duration_pct': round(s['duration'] / total_time * 100, 1) if total_time > 0 else 0,
                    'memory_delta_mb': round(s.get('memory_delta', 0), 2),
                    'extras': {k: v for k, v in s.items()
                              if k not in ('name', 'start_time', 'end_time', 'duration',
                                           'start_memory', 'end_memory', 'memory_delta')}
                }
                for s in self.steps
            ],
            'match_summary': match_summary,
            'total_matches': sum(len(d) for d in self.match_details.values()),
        }

        # 保存到文件
        os.makedirs(self.output_dir, exist_ok=True)
        report_path = os.path.join(self.output_dir, 'performance_report.json')
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        return report

    def print_summary(self, report: dict = None):
        """打印性能摘要到控制台"""
        if report is None:
            report = self.generate_report()

        print("\n" + "=" * 60)
        print("性能报告")
        print("=" * 60)
        print(f"任务: {report['task_name']}")
        print(f"总耗时: {report['total_duration_seconds']}s")
        print(f"内存: {report['initial_memory_mb']}MB → {report['peak_memory_mb']}MB")
        print()

        if report['steps']:
            print("步骤耗时:")
            for step in report['steps']:
                extras = step.get('extras', {})
                extra_str = '  ' + str(extras) if extras else ''
                print(f"  {step['name']:12s}  {step['duration_seconds']:6.2f}s "
                      f"({step['duration_pct']:4.1f}%)"
                      f"  内存 {step['memory_delta_mb']:+.1f}MB{extra_str}")
            print()

        if report['match_summary']:
            print("匹配分布:")
            for mt, info in sorted(report['match_summary'].items(),
                                    key=lambda x: -x[1]['count']):
                print(f"  {mt:25s}  {info['count']:5d}  "
                      f"(avg confidence {info['avg_confidence']:.3f})")
            print(f"  {'总计':25s}  {report['total_matches']:5d}")

        print("=" * 60)
