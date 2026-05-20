"""Language detection with CJK character-based pre-detection for reliability."""


def detect_lang(text: str) -> str:
    if not text or not text.strip():
        return "unknown"

    # ── 1. 基于字符集直接判断 CJK 语言（比 langdetect 准确得多）──────────────
    hiragana_katakana = sum(
        1 for c in text if '぀' <= c <= 'ヿ' or 'ㇰ' <= c <= 'ㇿ'
    )
    hangul = sum(1 for c in text if '가' <= c <= '힣' or 'ㄱ' <= c <= 'ㆎ')
    cjk = sum(1 for c in text if '一' <= c <= '鿿' or '㐀' <= c <= '䶿')

    if hiragana_katakana >= 2:
        return "ja"
    if hangul >= 2:
        return "ko"
    if cjk >= 4:
        # 区分简体/繁体中文（常见繁体字特征码位）
        traditional_chars = sum(
            1 for c in text
            if c in '們來說時國會對學實現發這樣當個問題面還點動種讓頁數據體歡'
        )
        return "zh-tw" if traditional_chars >= 2 else "zh-cn"

    # ── 2. 非 CJK 文本交给 langdetect ──────────────────────────────────────
    try:
        from langdetect import detect, DetectorFactory
        DetectorFactory.seed = 0
        return detect(text)
    except Exception:
        return "unknown"
