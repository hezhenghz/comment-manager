# -*- coding: utf-8 -*-
"""物品元数据：从 ItemCfg.bytes + LocalizeTable.bytes 两表联查得到
全部 itemId 的「中文名 / 职业物品标志 / 价格」，进程内缓存。

自动重载：当查询遇到缓存里不存在的 itemId 时，认为可能上线了新物品，
触发一次重新解析（带最小间隔节流，避免频繁 IO）。"""
import logging
import threading
import time

from app.config import get_settings
from app.lineup.parser import load_itemcfg, load_localize_cn

logger = logging.getLogger(__name__)

# 缓存（一次性加载，遇未知 itemId 时按节流重载）
_lock = threading.Lock()
_price: dict[int, int] = {}
_career: set[int] = set()
_names: dict[int, str] = {}
_types: dict[int, int] = {}    # itemId → ItemType 枚举值
_ranks: dict[int, int] = {}    # itemId → ItemRankLevel 品质枚举值 1~5
_loaded = False
_last_reload = 0.0
_RELOAD_MIN_INTERVAL = 30.0   # 两次重载最小间隔（秒），防止未知 ID 刷爆重载

# 门派枚举值 → 中文名（静态，不会变）
MENPAI_NAME: dict[int, str] = {
    2: "武当", 3: "华山", 4: "少林", 5: "五毒", 6: "丐帮",
    7: "血刀", 8: "逍遥", 9: "唐门", 10: "六扇门", 11: "峨眉",
}

# 物品类型枚举值 → 中文名（来自游戏 ItemType enum）
ITEMTYPE_NAME: dict[int, str] = {
    0: "无", 1: "背包", 2: "武器", 3: "招式", 4: "内功", 5: "手套",
    6: "鞋子", 7: "宝石", 8: "护甲", 9: "护心镜", 10: "头盔", 11: "配饰",
    12: "食物", 13: "宠物", 14: "丹药", 15: "天赋", 16: "侠客",
}


def _do_load() -> None:
    """实际解析两表，填充全局缓存。失败则保留旧缓存并告警。"""
    global _price, _career, _names, _types, _ranks, _loaded, _last_reload
    s = get_settings()
    try:
        price, career, namekeys, types, ranks = load_itemcfg(s.lineup_itemcfg_path)
        loc = load_localize_cn(s.lineup_localize_path)
        names = {}
        for item_id, nk in namekeys.items():
            cn = loc.get(nk)
            if cn:
                names[item_id] = cn
        _price, _career, _names, _types, _ranks = price, career, names, types, ranks
        _loaded = True
        _last_reload = time.time()
        logger.info(
            f"[lineup] 物品表已加载：价格 {len(price)}，职业物品 {len(career)}，"
            f"中文名 {len(names)}，类型 {len(types)}，品质 {len(ranks)}"
        )
    except Exception as e:
        _last_reload = time.time()
        logger.warning(f"[lineup] 物品表加载失败：{e}；沿用旧缓存（可能为空）")


def _ensure_loaded() -> None:
    if not _loaded:
        with _lock:
            if not _loaded:
                _do_load()


def _maybe_reload_for_unknown() -> None:
    """遇到未知 itemId 时尝试重载（带节流）：应对新增物品上线。"""
    now = time.time()
    if now - _last_reload < _RELOAD_MIN_INTERVAL:
        return
    with _lock:
        if time.time() - _last_reload < _RELOAD_MIN_INTERVAL:
            return
        logger.info("[lineup] 遇到未知 itemId，重新解析物品表（可能有新物品上线）")
        _do_load()


def reload_now() -> dict:
    """强制立即重载（供 API 手动触发）。返回统计。"""
    with _lock:
        _do_load()
    return {"price": len(_price), "career": len(_career), "names": len(_names), "types": len(_types), "ranks": len(_ranks)}


def price_table() -> dict:
    _ensure_loaded()
    return _price


def career_set() -> set:
    _ensure_loaded()
    return _career


def item_name(item_id: int) -> str:
    """itemId → 中文名。未知 itemId 触发一次节流重载；仍查不到则返回 '#itemId'。"""
    _ensure_loaded()
    name = _names.get(item_id)
    if name:
        return name
    # 未知物品：可能是新上线的，尝试重载后再查一次
    _maybe_reload_for_unknown()
    return _names.get(item_id) or f"#{item_id}"


def menpai_name(men_pai: int) -> str:
    return MENPAI_NAME.get(men_pai, str(men_pai))


def is_career(item_id: int) -> bool:
    _ensure_loaded()
    return item_id in _career


def item_type(item_id: int) -> int:
    """itemId → 物品类型枚举值（未知返回 0=无）。"""
    _ensure_loaded()
    return _types.get(item_id, 0)


def item_type_name(t: int) -> str:
    return ITEMTYPE_NAME.get(t, str(t))


def item_rank(item_id: int) -> int:
    """itemId → 品质枚举值（1普通/2精良/3上乘/4传说/5绝世；未知返回 0）。"""
    _ensure_loaded()
    return _ranks.get(item_id, 0)
