# -*- coding: utf-8 -*-
"""阵容大码解析 + ItemCfg 元数据解析（纯函数，无外部依赖）。

数据来源与字段编号均来自游戏 ProtoGenCode / ItemCfg，已在「阵容码工具」中验证：

OfflinePlayerData（大码 = 它的 protobuf 序列化后 base64）:
  field 2 = name(string)
  field 3 = rankLevel(varint)
  field 4 = roundsItems  map<int, ItemInfoList>   每个 entry: field1=回合号, field2=ItemInfoList 字节
  field 6 = failRound(varint)
ItemInfoList:
  field 1 = repeated ItemData
ItemData:
  field 1 = itemId(varint)
  field 7 = backpackType(varint, Main=1, 缺省 None=0)

ItemCfg.bytes（SilentOrbit Protobuf）外层 ItemCfgArray:
  field 2 = Items (repeated ItemCfg, length-delimited)
每条 ItemCfg:
  tag 1  = ID(varint)
  tag 7  = CareerItem(bool/varint)
  tag 12 = BuyPrice(varint)
"""
import base64
import hashlib


# ───────────────────────── 通用 protobuf 原语 ─────────────────────────
def _read_varint(data: bytes, pos: int):
    """读 protobuf varint，返回 (值, 新位置)。"""
    result = 0
    shift = 0
    while True:
        b = data[pos]
        pos += 1
        result |= (b & 0x7F) << shift
        if not (b & 0x80):
            return result, pos
        shift += 7


def _skip_field(data: bytes, pos: int, wire: int) -> int:
    """按 wire type 跳过一个字段，返回新位置。"""
    if wire == 0:          # varint
        _, pos = _read_varint(data, pos)
    elif wire == 1:        # 64-bit
        pos += 8
    elif wire == 2:        # length-delimited
        ln, pos = _read_varint(data, pos)
        pos += ln
    elif wire == 5:        # 32-bit
        pos += 4
    else:
        raise ValueError(f"不支持的 wire type: {wire}")
    return pos


def _b64_to_bytes(b64: str) -> bytes:
    """base64 → bytes，容错补齐 padding。"""
    s = (b64 or "").strip()
    s = s.replace("-", "+").replace("_", "/")
    pad = (-len(s)) % 4
    if pad:
        s += "=" * pad
    return base64.b64decode(s)


def code_hash(big_code: str) -> str:
    """大码内容的 sha1，作为去重键。"""
    return hashlib.sha1((big_code or "").encode("utf-8")).hexdigest()


# ───────────────────────── 大码解析 ─────────────────────────
def _parse_round_items(round_bytes: bytes):
    """解析单回合 ItemInfoList 字节，返回 [(itemId, backpackType), ...]。"""
    items = []
    pos = 0
    n = len(round_bytes)
    while pos < n:
        tag, pos = _read_varint(round_bytes, pos)
        field = tag >> 3
        wire = tag & 7
        if field == 1 and wire == 2:          # 一个 ItemData
            ln, pos = _read_varint(round_bytes, pos)
            end = pos + ln
            item_id = None
            backpack = 0
            p = pos
            while p < end:
                it, p = _read_varint(round_bytes, p)
                f = it >> 3
                w = it & 7
                if f == 1 and w == 0:
                    item_id, p = _read_varint(round_bytes, p)
                elif f == 7 and w == 0:
                    backpack, p = _read_varint(round_bytes, p)
                else:
                    p = _skip_field(round_bytes, p, w)
            pos = end
            if item_id is not None:
                items.append((item_id, backpack))
        else:
            pos = _skip_field(round_bytes, pos, wire)
    return items


def parse_snapshot(big_code: str) -> dict:
    """解析一条大码，返回结构化快照。

    返回 dict:
      player_name: str
      rank_level:  int | None
      fail_round:  int | None
      round_count: int  该局回合数（rounds 条目数）
      rounds:      { round(int): [(itemId, backpackType), ...] }
      item_counts: { itemId(str): count(int) }  所有回合累计（不限背包类型）
    """
    data = _b64_to_bytes(big_code)
    pos = 0
    n = len(data)
    name = ""
    rank_level = None
    fail_round = None
    rounds = {}

    while pos < n:
        tag, pos = _read_varint(data, pos)
        field = tag >> 3
        wire = tag & 7
        if field == 4 and wire == 2:          # roundsItems 的一个 map entry
            entry_len, pos = _read_varint(data, pos)
            entry_end = pos + entry_len
            rnd = None
            value_bytes = b""
            while pos < entry_end:
                et, pos = _read_varint(data, pos)
                ef = et >> 3
                ew = et & 7
                if ef == 1 and ew == 0:
                    rnd, pos = _read_varint(data, pos)
                elif ef == 2 and ew == 2:
                    vlen, pos = _read_varint(data, pos)
                    value_bytes = data[pos:pos + vlen]
                    pos += vlen
                else:
                    pos = _skip_field(data, pos, ew)
            pos = entry_end
            if rnd is not None:
                rounds[rnd] = _parse_round_items(value_bytes)
        elif field == 2 and wire == 2:        # name
            ln, pos = _read_varint(data, pos)
            try:
                name = data[pos:pos + ln].decode("utf-8", "ignore")
            except Exception:
                name = ""
            pos += ln
        elif field == 3 and wire == 0:        # rankLevel
            rank_level, pos = _read_varint(data, pos)
        elif field == 6 and wire == 0:        # failRound
            fail_round, pos = _read_varint(data, pos)
        else:
            pos = _skip_field(data, pos, wire)

    # 所有回合累计的物品出现次数（不限背包类型，符合「所有回合累计」口径）
    item_counts: dict[str, int] = {}
    for _rnd, items in rounds.items():
        for item_id, _bt in items:
            key = str(item_id)
            item_counts[key] = item_counts.get(key, 0) + 1

    return {
        "player_name": name,
        "rank_level": rank_level,
        "fail_round": fail_round,
        "round_count": len(rounds),
        "rounds": rounds,
        "item_counts": item_counts,
    }


# ───────────────────────── ItemCfg.bytes 解析 ─────────────────────────
def _parse_one_itemcfg(data: bytes, start: int, end: int):
    """解析单条 ItemCfg，返回 (itemId, buyPrice, careerItem, nameKey, itemType, rank)。"""
    pos = start
    item_id = None
    buy_price = 0
    career = 0
    name_key = None
    item_type = 0
    rank = 0
    while pos < end:
        tag, pos = _read_varint(data, pos)
        field = tag >> 3
        wire = tag & 7
        if field == 1 and wire == 0:          # ID
            item_id, pos = _read_varint(data, pos)
        elif field == 2 and wire == 0:        # NameKey（本地化 key）
            name_key, pos = _read_varint(data, pos)
        elif field == 5 and wire == 0:        # Type（物品类型枚举：2武器/3招式/4内功/16侠客…）
            item_type, pos = _read_varint(data, pos)
        elif field == 7 and wire == 0:        # CareerItem
            career, pos = _read_varint(data, pos)
        elif field == 9 and wire == 0:        # Rank（品质枚举：1普通/2精良/3上乘/4传说/5绝世）
            rank, pos = _read_varint(data, pos)
        elif field == 12 and wire == 0:       # BuyPrice
            buy_price, pos = _read_varint(data, pos)
        else:
            pos = _skip_field(data, pos, wire)
    return item_id, buy_price, career, name_key, item_type, rank


def load_itemcfg(path: str):
    """解析 ItemCfg.bytes，返回 (price_table, career_set, namekey_table, type_table, rank_table)。
    price_table:   { itemId(int): buyPrice(int) }
    career_set:    set(itemId) CareerItem=true 的物品
    namekey_table: { itemId(int): NameKey(int) }  本地化 key，再去 LocalizeTable 查中文名
    type_table:    { itemId(int): ItemType(int) }  物品类型枚举值
    rank_table:    { itemId(int): ItemRankLevel(int) }  品质枚举值 1~5
    解析失败抛异常，由调用方处理。"""
    with open(path, "rb") as f:
        data = f.read()

    price_table: dict[int, int] = {}
    career_set: set[int] = set()
    namekey_table: dict[int, int] = {}
    type_table: dict[int, int] = {}
    rank_table: dict[int, int] = {}
    pos = 0
    n = len(data)
    while pos < n:
        tag, pos = _read_varint(data, pos)
        field = tag >> 3
        wire = tag & 7
        if field == 2 and wire == 2:          # 一条 ItemCfg
            ln, pos = _read_varint(data, pos)
            item_id, buy_price, career, name_key, item_type, rank = _parse_one_itemcfg(data, pos, pos + ln)
            pos += ln
            if item_id is not None:
                price_table[item_id] = buy_price
                if career:
                    career_set.add(item_id)
                if name_key is not None:
                    namekey_table[item_id] = name_key
                type_table[item_id] = item_type
                rank_table[item_id] = rank
        else:
            pos = _skip_field(data, pos, wire)
    return price_table, career_set, namekey_table, type_table, rank_table


def load_localize_cn(path: str) -> dict:
    """解析 LocalizeTable.bytes，返回 { id(int): 简体中文(str) }。
    外层 LocalizeTableArray field2=Items；每条 tag1=ID(varint), tag3=Cn(string)。"""
    with open(path, "rb") as f:
        data = f.read()
    out: dict[int, str] = {}
    pos = 0
    n = len(data)
    while pos < n:
        tag, pos = _read_varint(data, pos)
        field = tag >> 3
        wire = tag & 7
        if field == 2 and wire == 2:          # 一条 LocalizeTable
            ln, pos = _read_varint(data, pos)
            end = pos + ln
            lid = None
            cn = None
            p = pos
            while p < end:
                t, p = _read_varint(data, p)
                f = t >> 3
                w = t & 7
                if f == 1 and w == 0:          # ID
                    lid, p = _read_varint(data, p)
                elif f == 3 and w == 2:        # Cn 简体中文
                    sl, p = _read_varint(data, p)
                    cn = data[p:p + sl].decode("utf-8", "ignore")
                    p += sl
                else:
                    p = _skip_field(data, p, w)
            pos = end
            if lid is not None:
                out[lid] = cn
        else:
            pos = _skip_field(data, pos, wire)
    return out


def build_item_names(itemcfg_path: str, localize_path: str) -> dict:
    """两表联查：itemId -(ItemCfg.NameKey)-> -(LocalizeTable.Cn)-> 中文名。
    返回 { itemId(int): 中文名(str) }，仅含能查到非空名字的物品。"""
    _, _, namekeys, _, _ = load_itemcfg(itemcfg_path)
    loc = load_localize_cn(localize_path)
    names: dict[int, str] = {}
    for item_id, name_key in namekeys.items():
        cn = loc.get(name_key)
        if cn:
            names[item_id] = cn
    return names
