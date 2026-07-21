#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LRU 缓存实现

提供带 LRU（最近最少使用）淘汰策略的缓存，用于：
- 字段匹配结果缓存（避免重复调用 _find_matching_field）
- 相似度计算缓存（避免重复计算编辑距离）
"""

from collections import OrderedDict
from typing import Any, Optional


class LRUCache:
    """带 LRU 淘汰策略的缓存

    用于缓存字段匹配结果、相似度计算结果等，避免重复计算。

    使用方式：
        cache = LRUCache(maxsize=10000)
        cache.put('key', 'value')
        value = cache.get('key', default=None)
        print(cache.hit_rate)  # 缓存命中率
    """

    def __init__(self, maxsize: int = 10000):
        """初始化缓存

        Args:
            maxsize: 最大缓存条目数，超过后淘汰最久未使用的条目
        """
        self.maxsize = maxsize
        self.cache = OrderedDict()
        self.hits = 0
        self.misses = 0

    def get(self, key: Any, default: Any = None) -> Any:
        """获取缓存值

        Args:
            key: 缓存键
            default: 未命中时的默认值

        Returns:
            缓存值或默认值
        """
        if key in self.cache:
            self.hits += 1
            self.cache.move_to_end(key)  # 标记为最近使用
            return self.cache[key]
        self.misses += 1
        return default

    def put(self, key: Any, value: Any):
        """添加或更新缓存值

        Args:
            key: 缓存键
            value: 缓存值
        """
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = value
        # 超过容量时淘汰最久未使用的
        if len(self.cache) > self.maxsize:
            self.cache.popitem(last=False)

    def clear(self):
        """清空缓存"""
        self.cache.clear()
        self.hits = 0
        self.misses = 0

    @property
    def hit_rate(self) -> float:
        """缓存命中率"""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    @property
    def size(self) -> int:
        """当前缓存大小"""
        return len(self.cache)

    def stats(self) -> dict:
        """获取缓存统计信息"""
        return {
            'size': self.size,
            'maxsize': self.maxsize,
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': f"{self.hit_rate:.2%}"
        }


# ===== 全局缓存实例 =====

# 相似度缓存（模块级，所有实例共享）
# 10万条目足够覆盖大部分场景
similarity_cache = LRUCache(maxsize=100000)


def get_similarity_from_cache(name1: str, name2: str) -> Optional[float]:
    """从缓存获取相似度

    Args:
        name1: 字段名1
        name2: 字段名2

    Returns:
        相似度值，未命中返回 None
    """
    # 排序保证 (a, b) 和 (b, a) 使用同一个缓存键
    cache_key = (name1, name2) if name1 <= name2 else (name2, name1)
    return similarity_cache.get(cache_key)


def put_similarity_to_cache(name1: str, name2: str, similarity: float):
    """将相似度存入缓存

    Args:
        name1: 字段名1
        name2: 字段名2
        similarity: 相似度值
    """
    cache_key = (name1, name2) if name1 <= name2 else (name2, name1)
    similarity_cache.put(cache_key, similarity)
