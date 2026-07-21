#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识库统一管理器

统一管理所有知识库文件的加载和缓存：
- field_synonyms.yaml: 字段同义词库
- table_synonyms.yaml: 表名同义词库
- field_mappings.yaml: 字段映射配置
- numbered_field_groups.yaml: 序号字段组配置
- learned_mappings.yaml: 已学习的表映射
- relations/*.yaml: 表关联关系

特性：
- 统一加载入口，避免分散的 _load_xxx 方法
- MD5 校验缓存，文件未变时直接返回
- 加载失败自动降级，不影响整体流程
- 支持手动刷新
"""

import os
import yaml
import hashlib
from datetime import datetime
from typing import Dict, Optional, Any
from collections import deque


class KnowledgeBaseManager:
    """知识库统一管理器

    使用方式：
        kb = KnowledgeBaseManager(skill_dir)
        print(kb.synonyms)          # 字段同义词
        print(kb.table_synonyms)    # 表名同义词
        print(kb.field_mappings)    # 字段映射
        kb.reload('field_synonyms') # 刷新指定知识库
    """

    def __init__(self, skill_dir: str):
        self.skill_dir = skill_dir
        self.kb_dir = os.path.join(skill_dir, 'knowledge_base')

        # 缓存层
        self._cache: Dict[str, Any] = {}
        self._checksums: Dict[str, str] = {}
        self._load_times: Dict[str, datetime] = {}
        self._parsed_cache: Dict[str, dict] = {}  # 缓存解析后的 YAML 数据

        # 错误日志
        self._errors: Dict[str, str] = {}

        # 初始化所有知识库
        self._init_all()

    def _init_all(self):
        """初始化所有知识库"""
        loaders = [
            ('field_synonyms', self._load_field_synonyms),
            ('table_synonyms', self._load_table_synonyms),
            ('field_mappings', self._load_field_mappings),
            ('numbered_field_groups', self._load_numbered_field_groups),
            ('learned_mappings', self._load_learned_mappings),
            ('relations', self._load_relations),
            ('user_custom_mappings', self._load_user_custom_mappings),
        ]

        for name, loader in loaders:
            try:
                loader()
            except Exception as e:
                self._cache[name] = self._default_for(name)
                self._errors[name] = str(e)

    # ===== 公共属性 =====

    @property
    def synonyms(self) -> Dict[str, list]:
        """字段同义词库"""
        return self._cache.get('field_synonyms', {})

    @property
    def table_synonyms(self) -> Dict[str, list]:
        """表名同义词库"""
        return self._cache.get('table_synonyms', {})

    @property
    def field_mappings(self) -> Dict[str, dict]:
        """字段映射配置（target_field -> mapping）

        合并公共映射和用户自定义映射，用户自定义映射优先级最高
        用户自定义映射使用target_table.target_field作为key
        """
        public_mappings = self._cache.get('field_mappings', {})
        user_mappings = self._cache.get('user_custom_field_mappings', {})
        # 用户自定义映射覆盖公共映射
        merged = {**public_mappings, **user_mappings}
        return merged

    @property
    def numbered_field_groups(self) -> Dict:
        """序号字段组配置"""
        return self._cache.get('numbered_field_groups', {})

    @property
    def learned_mappings(self) -> Dict[str, str]:
        """已学习的表映射（source_name -> target_name）"""
        return self._cache.get('learned_mappings', {})

    @property
    def relations(self) -> Dict:
        """表关联关系"""
        return self._cache.get('relations', {
            'joins': [], 'table_roles': {}, 'key_mappings': {}, 'adjacency': {}
        })

    # ===== 公共方法 =====

    def get(self, name: str, default=None) -> Any:
        """获取知识库数据"""
        return self._cache.get(name, default)

    def reload(self, name: str = None):
        """重新加载指定知识库或全部

        Args:
            name: 知识库名称，None 表示全部重新加载
        """
        if name:
            loader_map = {
                'field_synonyms': self._load_field_synonyms,
                'table_synonyms': self._load_table_synonyms,
                'field_mappings': self._load_field_mappings,
                'numbered_field_groups': self._load_numbered_field_groups,
                'learned_mappings': self._load_learned_mappings,
                'relations': self._load_relations,
            }
            loader = loader_map.get(name)
            if loader:
                try:
                    # 清除缓存校验，强制重新加载
                    path = self._get_kb_path(name)
                    if path in self._checksums:
                        del self._checksums[path]
                    loader()
                    if name in self._errors:
                        del self._errors[name]
                except Exception as e:
                    self._errors[name] = str(e)
        else:
            self._checksums.clear()
            self._init_all()

    def check_for_updates(self) -> list:
        """检查知识库文件是否有变化

        Returns:
            发生变化的知识库名称列表
        """
        changed = []
        name_file_map = {
            'field_synonyms': 'field_synonyms.yaml',
            'table_synonyms': 'table_synonyms.yaml',
            'field_mappings': 'field_mappings.yaml',
            'numbered_field_groups': 'numbered_field_groups.yaml',
            'learned_mappings': 'learned_mappings.yaml',
        }
        for name, filename in name_file_map.items():
            path = os.path.join(self.kb_dir, filename)
            if os.path.exists(path):
                current = self._file_checksum(path)
                if path in self._checksums and current != self._checksums[path]:
                    changed.append(name)
        # relations 目录
        relations_dir = os.path.join(self.kb_dir, 'relations')
        if os.path.isdir(relations_dir):
            for filename in os.listdir(relations_dir):
                if filename.endswith('.yaml'):
                    path = os.path.join(relations_dir, filename)
                    current = self._file_checksum(path)
                    if path in self._checksums and current != self._checksums[path]:
                        if 'relations' not in changed:
                            changed.append('relations')
        return changed

    def get_errors(self) -> Dict[str, str]:
        """获取加载错误"""
        return dict(self._errors)

    def get_stats(self) -> dict:
        """获取知识库统计信息"""
        return {
            'field_synonyms_count': len(self.synonyms),
            'table_synonyms_count': len(self.table_synonyms),
            'field_mappings_count': len(self.field_mappings),
            'learned_mappings_count': len(self.learned_mappings),
            'relations_joins_count': len(self.relations.get('joins', [])),
            'errors': dict(self._errors),
        }

    # ===== 各知识库加载方法 =====

    def _load_field_synonyms(self):
        """加载字段同义词库"""
        path = os.path.join(self.kb_dir, 'field_synonyms.yaml')
        data = self._load_yaml_with_cache(path)

        synonyms = {}
        exclude_list = []
        field_synonyms = data.get('field_synonyms', {})
        for cn_name, info in field_synonyms.items():
            if isinstance(info, dict) and 'synonyms' in info:
                syn_list = list(info['synonyms'])
                synonyms[cn_name] = syn_list
                # 加载exclude列表
                if 'exclude' in info:
                    exclude_list.extend(info['exclude'])
                # 反向映射：同义词 -> 主词
                for syn in syn_list:
                    if syn not in synonyms:
                        synonyms[syn] = []
                    if cn_name not in synonyms[syn]:
                        synonyms[syn].append(cn_name)

        self._cache['field_synonyms'] = synonyms
        self._cache['field_synonyms_exclude'] = list(set(exclude_list))

    def _load_table_synonyms(self):
        """加载表名同义词库"""
        path = os.path.join(self.kb_dir, 'table_synonyms.yaml')
        data = self._load_yaml_with_cache(path)
        self._cache['table_synonyms'] = data.get('table_synonyms', {}) if data else {}

    def _load_field_mappings(self):
        """加载字段映射配置"""
        path = os.path.join(self.kb_dir, 'field_mappings.yaml')
        data = self._load_yaml_with_cache(path)
        mappings = {}
        for mapping in (data.get('field_mappings', []) if data else []):
            for target_field in mapping.get('target_fields', []):
                mappings[target_field] = mapping
        self._cache['field_mappings'] = mappings

    def _load_numbered_field_groups(self):
        """加载序号字段组配置"""
        path = os.path.join(self.kb_dir, 'numbered_field_groups.yaml')
        data = self._load_yaml_with_cache(path)
        self._cache['numbered_field_groups'] = data if data else {}

    def _load_learned_mappings(self):
        """加载已学习的表映射"""
        path = os.path.join(self.kb_dir, 'learned_mappings.yaml')
        data = self._load_yaml_with_cache(path)
        mappings = {}
        if data:
            for source_name, info in data.get('table_mappings', {}).items():
                if isinstance(info, dict) and info.get('target'):
                    mappings[source_name] = info['target']
                    if info.get('target_alt'):
                        mappings[source_name + '_alt'] = info['target_alt']
        self._cache['learned_mappings'] = mappings

    def _load_user_custom_mappings(self):
        """加载用户自定义映射（优先级最高）"""
        path = os.path.join(self.kb_dir, 'user_custom_mappings.yaml')
        data = self._load_yaml_with_cache(path)

        # 保留原始结构，包括mappings和new_tables
        self._cache['user_custom_mappings'] = data if data else {}

        # 同时加载字段映射（用于field_mappings合并）
        # 使用target_table.target_field作为key，避免不同表的同名字段冲突
        mappings = {}
        if data:
            for mapping in data.get('mappings', []):
                target_table = mapping.get('target_table', '')
                target_field = mapping.get('target_field', '')
                key = f"{target_table}.{target_field}"  # 使用表名.字段名作为key
                mappings[key] = {
                    'target_fields': [target_field],
                    'source_field': mapping.get('source_field', ''),
                    'source_field_cn': mapping.get('source_field', ''),
                    'source_table': mapping.get('source_table', ''),
                    'description': f"用户自定义映射: {target_table}.{target_field}",
                    'match_type': 'user_custom'
                }
        self._cache['user_custom_field_mappings'] = mappings

    def _load_relations(self):
        """加载表关联关系（从 relations/ 目录）

        沿用原有的 _load_relations 逻辑。
        """
        relations_dir = os.path.join(self.kb_dir, 'relations')
        if not os.path.isdir(relations_dir):
            self._cache['relations'] = {
                'joins': [], 'table_roles': {}, 'key_mappings': {}, 'adjacency': {}
            }
            return

        result = {'joins': [], 'table_roles': {}, 'key_mappings': {}, 'adjacency': {}}

        for filename in sorted(os.listdir(relations_dir)):
            if not filename.endswith('.yaml'):
                continue
            filepath = os.path.join(relations_dir, filename)

            # 缓存校验
            checksum = self._file_checksum(filepath)
            if filepath in self._checksums and self._checksums[filepath] == checksum:
                continue  # 文件未变，跳过

            self._checksums[filepath] = checksum

            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                if not data:
                    continue

                # 加载 table_roles
                roles = data.get('table_roles', {})
                if roles:
                    result['table_roles'].update(roles)

                # 加载 key_mappings
                keys = data.get('key_mappings', {})
                if keys:
                    result['key_mappings'].update(keys)

                # 加载 joins 列表
                joins = data.get('joins', [])
                for j in joins:
                    if not isinstance(j, dict) or not j.get('join'):
                        continue
                    conditions = []
                    for cond_str in j['join']:
                        clean = cond_str.split('#')[0].strip()
                        if '=' not in clean:
                            continue
                        parts = clean.split('=')
                        if len(parts) == 2:
                            left = parts[0].strip()
                            right = parts[1].strip()
                            if '.' in left and '.' in right:
                                conditions.append({'left': left, 'right': right})

                    if conditions:
                        join_entry = {
                            'from': j['from'],
                            'to': j['to'],
                            'conditions': conditions,
                            'type': j.get('type', ''),
                            'note': j.get('note', '')
                        }
                        result['joins'].append(join_entry)

                        # 构建邻接表（双向）
                        frm = j['from']
                        to = j['to']
                        if frm not in result['adjacency']:
                            result['adjacency'][frm] = []
                        if to not in result['adjacency']:
                            result['adjacency'][to] = []
                        result['adjacency'][frm].append({
                            'to': to, 'conditions': conditions, 'type': j.get('type', '')
                        })
                        result['adjacency'][to].append({
                            'to': frm, 'conditions': conditions, 'type': j.get('type', '')
                        })

            except Exception as e:
                self._errors[f'relations/{filename}'] = str(e)

        self._cache['relations'] = result

    # ===== 内部工具方法 =====

    def _load_yaml_with_cache(self, path: str) -> dict:
        """加载 YAML 文件，带 MD5 缓存校验"""
        if not os.path.exists(path):
            return {}

        checksum = self._file_checksum(path)
        if path in self._checksums and self._checksums[path] == checksum:
            # 文件未变，返回缓存的解析结果
            if path in self._parsed_cache:
                return self._parsed_cache[path]

        self._checksums[path] = checksum
        self._load_times[path] = datetime.now()

        with open(path, 'r', encoding='utf-8') as f:
            parsed = yaml.safe_load(f) or {}
            self._parsed_cache[path] = parsed  # 缓存解析结果
            return parsed

    def _file_checksum(self, path: str) -> str:
        """计算文件 MD5"""
        try:
            with open(path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except (OSError, IOError):
            return ''

    def _get_kb_path(self, name: str) -> str:
        """获取知识库文件路径"""
        file_map = {
            'field_synonyms': 'field_synonyms.yaml',
            'table_synonyms': 'table_synonyms.yaml',
            'field_mappings': 'field_mappings.yaml',
            'numbered_field_groups': 'numbered_field_groups.yaml',
            'learned_mappings': 'learned_mappings.yaml',
        }
        filename = file_map.get(name, '')
        return os.path.join(self.kb_dir, filename) if filename else ''

    def _default_for(self, name: str) -> Any:
        """各知识库的默认空值"""
        defaults = {
            'field_synonyms': {},
            'table_synonyms': {},
            'field_mappings': {},
            'numbered_field_groups': {},
            'learned_mappings': {},
            'relations': {'joins': [], 'table_roles': {}, 'key_mappings': {}, 'adjacency': {}},
        }
        return defaults.get(name, {})
