"""
QQ 爬虫诊断脚本：直接调 NapCat API，绕过所有过滤逻辑，
检查 NapCat 返回了多少消息、分页是否正常、内容长度分布。

用法（在 backend 目录或项目根目录）：
  python diag_qq.py
"""
import asyncio
import httpx
from datetime import datetime

NAPCAT_URL  = "http://127.0.0.1:3000"
ACCESS_TOKEN = ""          # 若有 token 填在这里
GROUP_ID    = 1094791088   # 改成你的群号
PAGE_SIZE   = 20
MAX_PAGES   = 10           # 最多翻多少页

async def main():
    headers = {}
    if ACCESS_TOKEN:
        headers["Authorization"] = f"Bearer {ACCESS_TOKEN}"

    async with httpx.AsyncClient(base_url=NAPCAT_URL, headers=headers, timeout=30) as client:

        # ── 1. 确认连通性 ──────────────────────────────────────────
        print("=== [1] 连通性测试 ===")
        try:
            r = await client.post("/get_group_info", json={"group_id": GROUP_ID})
            d = r.json()
            print(f"  状态: {d.get('status')} / retcode={d.get('retcode')}")
            gdata = d.get("data") or {}
            print(f"  群名: {gdata.get('group_name')}  成员数: {gdata.get('member_count')}")
        except Exception as e:
            print(f"  连接失败: {e}")
            return

        # ── 2. 白名单成员昵称 ──────────────────────────────────────
        print("\n=== [2] 白名单成员昵称 ===")
        for uid in [86114262, 124306381]:
            try:
                r = await client.post("/get_group_member_info",
                                      json={"group_id": GROUP_ID, "user_id": uid})
                d = r.json()
                info = (d.get("data") or {})
                print(f"  QQ {uid}: card={info.get('card')!r}  nickname={info.get('nickname')!r}")
            except Exception as e:
                print(f"  QQ {uid}: 查询失败 {e}")

        # ── 3. 翻页抓消息 ──────────────────────────────────────────
        print(f"\n=== [3] 翻页抓消息（最多 {MAX_PAGES} 页，每页 {PAGE_SIZE} 条）===")
        message_seq = 0
        all_messages = []
        seen_ids: set[str] = set()

        for page in range(1, MAX_PAGES + 1):
            r = await client.post("/get_group_msg_history",
                                  json={"group_id": GROUP_ID,
                                        "message_seq": message_seq,
                                        "count": PAGE_SIZE})
            d = r.json()
            if d.get("status") != "ok" and d.get("retcode") != 0:
                print(f"  第{page}页 API 错误: {d}")
                break

            msgs = (d.get("data") or {}).get("messages") or []
            if not msgs:
                print(f"  第{page}页: 空，停止翻页")
                break

            # 排序：按 time 降序（和爬虫代码一致）
            msgs_sorted = sorted(msgs, key=lambda m: m.get("time", 0), reverse=True)
            new_in_page = 0
            for m in msgs_sorted:
                mid = str(m.get("message_id", ""))
                if mid in seen_ids:
                    continue
                seen_ids.add(mid)
                new_in_page += 1
                all_messages.append(m)

            oldest  = msgs_sorted[-1]
            newest  = msgs_sorted[0]
            old_seq = oldest.get("message_seq") or oldest.get("message_id")
            new_seq = newest.get("message_seq") or newest.get("message_id")

            t_oldest = datetime.fromtimestamp(oldest.get("time", 0)) if oldest.get("time") else "?"
            t_newest = datetime.fromtimestamp(newest.get("time", 0)) if newest.get("time") else "?"

            print(f"  第{page}页: {len(msgs)}条原始 / {new_in_page}条新 "
                  f"| seq {old_seq}~{new_seq} "
                  f"| 时间 {t_oldest} ~ {t_newest}")

            if new_in_page == 0:
                print("  全部重复，停止翻页")
                break

            # 用最旧的 seq 向更早翻页
            next_seq = old_seq
            if not next_seq or next_seq == message_seq:
                print(f"  翻页 seq 未变化 ({next_seq})，停止")
                break
            message_seq = next_seq
            await asyncio.sleep(0.3)

        # ── 4. 统计分析 ──────────────────────────────────────────
        print(f"\n=== [4] 统计：共 {len(all_messages)} 条消息 ===")

        import re
        def extract_text(msg):
            raw = msg.get("message", "")
            if isinstance(raw, str):
                return re.sub(r"\[CQ:[^\]]*\]", "", raw).strip()
            if isinstance(raw, list):
                return "".join(s.get("data", {}).get("text", "") for s in raw if s.get("type") == "text").strip()
            return ""

        short = sum(1 for m in all_messages if len(extract_text(m)) < 5)
        has_at = sum(1 for m in all_messages
                     if "[CQ:at,qq=86114262]" in str(m.get("message", ""))
                     or "[CQ:at,qq=124306381]" in str(m.get("message", "")))
        print(f"  内容 < 5字符（会被过滤）: {short} 条")
        print(f"  含 CQ:at 白名单 @: {has_at} 条")

        print("\n  前 10 条消息内容预览（已过滤 CQ 码）:")
        for m in all_messages[:10]:
            text = extract_text(m)
            sender = m.get("sender", {})
            name = sender.get("card") or sender.get("nickname") or str(sender.get("user_id", "?"))
            ts = datetime.fromtimestamp(m.get("time", 0)) if m.get("time") else "?"
            print(f"    [{ts}] {name}: {text[:60]!r}  (len={len(text)})")

asyncio.run(main())
