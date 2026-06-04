# -*- coding: utf-8 -*-
"""失衡统计排除名单：BOSS 掉落等稀缺物品，玩家用得少是因为掉得少，
不应计入"选用失衡"。仅影响失衡统计端点，不影响使用率展示。

维护：以后增删稀缺物品，只改这张表（id 必填，name/reason 仅供人读）。
"""

# 排除物品表（name/reason 仅供人读，逻辑只用 id）
EXCLUDED_ITEMS: list[dict] = [
    {"id": 1101039, "name": "九霄惊雷刀法", "reason": "BOSS掉落稀缺"},
    {"id": 1701027, "name": "销魂腰带",     "reason": "BOSS掉落稀缺"},
    {"id": 1701028, "name": "白衣圣令",     "reason": "BOSS掉落稀缺"},
    {"id": 1601004, "name": "踏雪鞋",       "reason": "BOSS掉落稀缺"},
    {"id": 2301017, "name": "三山拳套",     "reason": "BOSS掉落稀缺"},
    {"id": 2301018, "name": "长空剑",       "reason": "BOSS掉落稀缺"},
    {"id": 2101021, "name": "无咎神功",       "reason": "BOSS掉落稀缺"},
]

EXCLUDED_IDS: frozenset[int] = frozenset(x["id"] for x in EXCLUDED_ITEMS)


def is_excluded(item_id: int) -> bool:
    return item_id in EXCLUDED_IDS
