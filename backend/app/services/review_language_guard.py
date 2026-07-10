import re


def contains_cjk(text: str) -> bool:
    """Return True if text contains any CJK character."""
    if not text:
        return False
    # CJK Unified Ideographs + Extension A + Extension B ranges (common for Chinese)
    return bool(re.search(r"[一-鿿㐀-䶿\U00020000-\U0002a6df]", text))


def strip_cjk(text: str) -> str:
    """Remove CJK characters from text and collapse extra whitespace."""
    if not text:
        return ""
    cleaned = re.sub(r"[一-鿿㐀-䶿\U00020000-\U0002a6df]", "", text)
    return re.sub(r"\s+", " ", cleaned).strip()
