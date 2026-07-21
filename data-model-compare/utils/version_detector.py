#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
标准版本检测工具
根据原标准文件路径判断是5.X还是6.0版本
"""

import os
import yaml
from typing import Optional


def detect_standard_version(file_path: str, config_path: str = None) -> str:
    """根据文件路径检测标准版本

    Args:
        file_path: 原标准文件路径
        config_path: 配置文件路径（可选，默认使用config.yaml）

    Returns:
        'v5' 或 'v6'
    """
    if not config_path:
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'config.yaml'
        )

    # 加载配置
    if not os.path.exists(config_path):
        # 默认返回v5
        return 'v5'

    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    versions = config.get('standard_versions', {})

    # 检查是否是6.0版本
    v6_config = versions.get('v6', {})
    v6_public_paths = v6_config.get('public_paths', [])
    v6_project_paths = v6_config.get('project_paths', [])

    for path in v6_public_paths + v6_project_paths:
        if path in file_path:
            return 'v6'

    # 检查是否是5.X版本
    v5_config = versions.get('v5', {})
    v5_public_paths = v5_config.get('public_paths', [])
    v5_project_paths = v5_config.get('project_paths', [])

    for path in v5_public_paths + v5_project_paths:
        if path in file_path:
            return 'v5'

    # 默认返回v5
    return 'v5'


def get_naming_convention(version: str, config_path: str = None) -> str:
    """获取指定版本的命名规范

    Args:
        version: 标准版本 ('v5' 或 'v6')
        config_path: 配置文件路径（可选）

    Returns:
        'pinyin_initials' 或 'english'
    """
    if not config_path:
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'config.yaml'
        )

    if not os.path.exists(config_path):
        # 默认返回pinyin_initials
        return 'pinyin_initials'

    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    versions = config.get('standard_versions', {})
    naming_convention = versions.get('naming_convention', {})

    return naming_convention.get(version, 'pinyin_initials')


def detect_version_from_files(file_paths: list, config_path: str = None) -> str:
    """从多个文件路径中检测版本（取第一个检测到的版本）

    Args:
        file_paths: 文件路径列表
        config_path: 配置文件路径（可选）

    Returns:
        'v5' 或 'v6'
    """
    for file_path in file_paths:
        version = detect_standard_version(file_path, config_path)
        if version:
            return version

    # 默认返回v5
    return 'v5'


# 测试
if __name__ == '__main__':
    test_paths = [
        '/Users/zhanglei/winning/tfs2018/RDA-01-标准规范/02 V5.5/01 产品文档/04 标准规范（项目化）/036 云南区域标准规范/区域卫生信息平台数据传输规范260709/区域卫生信息平台数据传输规范 第01部分：医疗服务.docx',
        '/Users/zhanglei/winning/tfs2021/RDA-01-标准规范/03 V6.0/01 产品文档/04 标准规范（项目化）/some_standard.docx',
    ]

    print('版本检测测试:')
    for path in test_paths:
        version = detect_standard_version(path)
        convention = get_naming_convention(version)
        print(f'  {os.path.basename(path)}')
        print(f'    版本: {version}, 命名规范: {convention}')
        print()
