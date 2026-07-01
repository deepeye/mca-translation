"""句子切分器 — 按目标语言句末标点切句，供接受度评分与 delta 重算共用。"""

import re
from dataclasses import dataclass


@dataclass
class Sentence:
    """切分后的句子。char_offset 为句首在全文中的字符偏移。"""
    id: str
    text: str
    char_offset: int
    length: int


# 各语言句末标点正则：英文 .!?、中文 。！？、日文 。！？
_TERMINATORS = {
    "en": r"[.!?]+",
    "de": r"[.!?]+",
    "fr": r"[.!?]+",
    "es": r"[.!?]+",
    "zh": r"[。！？]+",
    "ja": r"[。！？]+",
}

# 英文缩写（不视为句末）：Dr. Nr. Mr. Mrs. Ms. Prof. vs. etc. e.g. i.e.
_ABBREVIATIONS = re.compile(
    r"\b(Dr|Nr|Mr|Mrs|Ms|Prof|vs|etc|e\.g|i\.e|St|Jr|Sr)\."
)


def segment(text: str, lang: str) -> list[Sentence]:
    """按语言切句。返回句子列表，每个含 id/char_offset。

    对英文系语言（en/de/fr/es）保护常见缩写，避免 Dr. 误切。
    """
    if not text:
        return []

    lang = lang.lower()
    pattern = _TERMINATORS.get(lang, _TERMINATORS["en"])

    if lang in ("en", "de", "fr", "es"):
        # 用占位符保护缩写，切完再还原
        protected = _ABBREVIATIONS.sub(lambda m: m.group(0).replace(".", "\x00"), text)
        parts = re.split(f"({pattern})", protected)
        parts = [p.replace("\x00", ".") for p in parts]
    else:
        parts = re.split(f"({pattern})", text)

    # 重新拼接句末标点回句子
    sentences: list[Sentence] = []
    buf = ""
    offset = 0
    idx = 0
    for part in parts:
        buf += part
        if re.fullmatch(pattern, part):
            stripped = buf.lstrip()
            if stripped:
                leading_ws = len(buf) - len(stripped)
                sentences.append(Sentence(
                    id=f"s{idx}",
                    text=stripped,
                    char_offset=offset + leading_ws,
                    length=len(stripped),
                ))
                offset += len(buf)
                idx += 1
            buf = ""
    if buf:
        stripped = buf.lstrip()
        leading_ws = len(buf) - len(stripped)
        sentences.append(Sentence(
            id=f"s{idx}",
            text=stripped,
            char_offset=offset + leading_ws,
            length=len(stripped),
        ))
    return sentences
