"""Steam 公告 BBCode → HTML 转换。

设计：
- 先对原始文本做 HTML 转义（防 XSS），再把白名单 BBCode 标签替换成固定 HTML 标签。
- 只输出下列白名单标签，未识别的残留 [xx] 标签兜底去除。
- {STEAM_CLAN_IMAGE} 占位符替换为 Steam CDN 地址。

支持标签（取自实测公告）：
  [h1][h2][h3] [p] [b][i][u] [olist][list][*] [url] [img] [table][tr][td][th]
  [dynamiclink href="..."]
"""
import html
import re

# Steam 公告图片 CDN（{STEAM_CLAN_IMAGE} 占位符指向 clan 图片库）
_STEAM_CLAN_IMAGE = "https://clan.cloudflare.steamstatic.com/images/clans"


def _esc(s: str) -> str:
    return html.escape(s, quote=True)


def _convert_links(text: str) -> str:
    """[url=x]/[url="x"]文字[/url] 与 [dynamiclink href="x"]文字[/dynamiclink] → <a>。
    text 已是 HTML 转义后的字符串，故属性里的引号是 &quot;。"""
    quote = r'(?:&quot;|&#x27;|\'|")?'

    def url_repl(m: re.Match) -> str:
        href = m.group("href").strip()
        label = m.group("label").strip() or href
        return f'<a href="{href}" target="_blank" rel="noopener">{label}</a>'

    # [url=href]label[/url]
    text = re.sub(
        rf'\[url={quote}(?P<href>[^\]"&\']+){quote}\](?P<label>.*?)\[/url\]',
        url_repl, text, flags=re.DOTALL | re.IGNORECASE,
    )
    # [dynamiclink href="x"]label[/dynamiclink]（label 常为空 → 用 href）
    text = re.sub(
        rf'\[dynamiclink\s+href={quote}(?P<href>[^\]"&\']+){quote}\](?P<label>.*?)\[/dynamiclink\]',
        url_repl, text, flags=re.DOTALL | re.IGNORECASE,
    )
    # 兜底：未闭合的 [dynamiclink href="x"]
    text = re.sub(
        rf'\[dynamiclink\s+href={quote}(?P<href>[^\]"&\']+){quote}\]',
        lambda m: f'<a href="{m.group("href").strip()}" target="_blank" rel="noopener">{m.group("href").strip()}</a>',
        text, flags=re.IGNORECASE,
    )
    return text


def _convert_images(text: str) -> str:
    """[img]src[/img] → <img>；替换 {STEAM_CLAN_IMAGE} 占位符。"""
    def img_repl(m: re.Match) -> str:
        src = m.group(1).strip()
        src = src.replace("{STEAM_CLAN_IMAGE}", _STEAM_CLAN_IMAGE)
        # 去掉可能包裹的引号
        src = src.strip('"\'')
        return f'<img src="{src}" loading="lazy">'

    return re.sub(r'\[img\](.*?)\[/img\]', img_repl, text,
                  flags=re.DOTALL | re.IGNORECASE)


def _convert_lists(text: str) -> str:
    """把 [*] 项转成 <li>…</li>。
    [*]item[/*] 或 [*]item（到下一个 [*] / [/olist] / [/list] 结束）。"""
    # 先处理显式 [/*] 闭合
    text = re.sub(r'\[\*\](.*?)\[/\*\]',
                  lambda m: f'<li>{m.group(1).strip()}</li>',
                  text, flags=re.DOTALL | re.IGNORECASE)
    # 再处理裸 [*]：内容到下一个 [*] 或列表结束标记前
    text = re.sub(r'\[\*\](.*?)(?=\[\*\]|\[/olist\]|\[/list\]|$)',
                  lambda m: f'<li>{m.group(1).strip()}</li>',
                  text, flags=re.DOTALL | re.IGNORECASE)
    return text


# 简单成对标签映射：BBCode → HTML
_SIMPLE_PAIRS = {
    "h1": "h1", "h2": "h2", "h3": "h3",
    "p": "p",
    "b": "strong", "i": "em", "u": "u",
    "table": "table", "tr": "tr", "td": "td", "th": "th",
}


def bbcode_to_html(text: str) -> str:
    if not text:
        return ""

    # 1. HTML 转义，杜绝原文里的 <script> 等
    out = _esc(text)

    # 2. 链接 / 图片（含占位符替换）
    out = _convert_links(out)
    out = _convert_images(out)

    # 3. 列表：先转 [*] 项（前瞻依赖 [/olist]/[/list] 仍在），再转容器标签
    out = _convert_lists(out)
    out = re.sub(r'\[olist\]', '<ol>', out, flags=re.IGNORECASE)
    out = re.sub(r'\[/olist\]', '</ol>', out, flags=re.IGNORECASE)
    out = re.sub(r'\[list\]', '<ul>', out, flags=re.IGNORECASE)
    out = re.sub(r'\[/list\]', '</ul>', out, flags=re.IGNORECASE)

    # 4. 简单成对标签
    for bb, htag in _SIMPLE_PAIRS.items():
        out = re.sub(rf'\[{bb}\]', f'<{htag}>', out, flags=re.IGNORECASE)
        out = re.sub(rf'\[/{bb}\]', f'</{htag}>', out, flags=re.IGNORECASE)
        # 带属性的开标签（如 [table equalcells="1" ...]）一并转为无属性开标签
        out = re.sub(rf'\[{bb}\s+[^\]]*\]', f'<{htag}>', out, flags=re.IGNORECASE)

    # 5. 兜底：去除所有未识别的残留 [xx] / [/xx] 标签
    out = re.sub(r'\[/?[a-zA-Z][^\]]*\]', '', out)

    # 6. 裸换行转 <br>（仅在没有块级标签包裹的纯文本行间，简单处理：连续换行压缩）
    out = re.sub(r'\n{2,}', '\n', out)
    out = out.replace('\n', '')

    return out.strip()
