# -*- coding: utf-8 -*-
"""系列物品合并：把"同一物品的不同等级"折叠成一个系列条目统计。

命名规律不统一（前缀/后缀混合）且有同名干扰项（如"巡捕·缉凶"是侠客），
故用显式 itemId 映射表，而非名字正则。以后加系列只需改 SERIES_DEFS。
"""
from app.lineup import meta

# 系列定义：系列名 -> 成员 itemId 列表
SERIES_DEFS: dict[str, list[int]] = {
    "野球拳系列": [1101003, 1101043, 1101044, 1101045, 1101046, 1101047, 1101048, 1101049, 1101050],
    "修罗印系列": [1706004, 1706005, 1706006, 1706007],
    "巡捕令系列": [1710003, 1710004, 1710005, 1710006, 1710007],
}

# 反查：成员 itemId -> 系列名
_MEMBER_TO_SERIES: dict[int, str] = {
    iid: name for name, ids in SERIES_DEFS.items() for iid in ids
}


def series_of(item_id: int) -> str | None:
    return _MEMBER_TO_SERIES.get(item_id)


def series_meta(name: str) -> dict:
    """系列代表属性：
    repId=最小成员 id（前端 key）；rank=成员最高；
    isCareer=任一成员职业；type=成员类型（同系列一致）。"""
    ids = SERIES_DEFS[name]
    return {
        "repId": min(ids),
        "name": name,
        "rank": max((meta.item_rank(i) for i in ids), default=0),
        "isCareer": any(meta.is_career(i) for i in ids),
        "type": meta.item_type(ids[0]),
    }


def fold_counter(counter) -> tuple[dict, dict]:
    """把 Counter 里属于系列的成员折叠为单一系列条目。

    返回 (folded_counts, key_meta)：
      folded_counts: { key(int): count }   普通物品 key=itemId，系列 key=repId
      key_meta:      { repId(int): {repId,name,rank,isCareer,type,isSeries} }
                     仅含出现过的系列；普通物品不在其中（用 meta.* 取属性）。
    """
    folded: dict[int, int] = {}
    seen_series: set[str] = set()
    for iid, cnt in counter.items():
        sname = series_of(iid)
        if sname:
            rep = min(SERIES_DEFS[sname])
            folded[rep] = folded.get(rep, 0) + cnt
            seen_series.add(sname)
        else:
            folded[iid] = folded.get(iid, 0) + cnt
    key_meta: dict[int, dict] = {}
    for name in seen_series:
        sm = series_meta(name)
        key_meta[sm["repId"]] = {**sm, "isSeries": True}
    return folded, key_meta
