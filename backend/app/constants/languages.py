"""目标语言常量表 — 单一事实来源。

提供 18 个 BCP-47 目标语言的元数据（中文标签、英文名、脚本、书写方向、
亲和文化圈），供 schema 校验、LLM 提示词 descriptor 注入、前端镜像引用。
更新这里时请同步 frontend/lib/languages.ts（手工镜像）。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# ISO 15924 脚本码 → 英文显示名（用于 descriptor 提示）
_SCRIPT_NAMES: dict[str, str] = {
    "Latn": "Latin",
    "Cyrl": "Cyrillic",
    "Arab": "Arabic",
    "Hang": "Hangul",
    "Thai": "Thai",
    "Grek": "Greek",
    "Deva": "Devanagari",
    "Jpan": "Japanese",
}


@dataclass(frozen=True)
class LanguageInfo:
    """单个目标语言元数据。"""

    code: str
    label_zh: str
    name_en: str
    script: str
    direction: str  # "ltr" | "rtl"
    affinity_sphere: Optional[str] = None


SUPPORTED_LANGUAGES: list[LanguageInfo] = [
    LanguageInfo("en-GB", "英语(英)", "English", "Latn", "ltr", "western_english"),
    LanguageInfo("de-DE", "德语", "German", "Latn", "ltr", "european_continental"),
    LanguageInfo("ja-JP", "日语", "Japanese", "Jpan", "ltr", "east_asian_confucian"),
    LanguageInfo("es-ES", "西班牙语", "Spanish", "Latn", "ltr", "latin_american"),
    LanguageInfo("fr-FR", "法语", "French", "Latn", "ltr", "european_continental"),
    LanguageInfo("ru-RU", "俄语", "Russian", "Cyrl", "ltr", "russian_sphere"),
    LanguageInfo("ar", "阿拉伯语", "Arabic", "Arab", "rtl", "islamic_middle_east"),
    LanguageInfo("ko-KR", "韩语", "Korean", "Hang", "ltr", "east_asian_confucian"),
    LanguageInfo("pt-BR", "葡萄牙语(巴)", "Portuguese", "Latn", "ltr", "latin_american"),
    LanguageInfo("sw-KE", "斯瓦希里语", "Swahili", "Latn", "ltr", "african"),
    LanguageInfo("it-IT", "意大利语", "Italian", "Latn", "ltr", "european_continental"),
    LanguageInfo("kk-KZ", "哈萨克语", "Kazakh", "Cyrl", "ltr", "russian_sphere"),
    LanguageInfo("th-TH", "泰语", "Thai", "Thai", "ltr", None),
    LanguageInfo("ms-MY", "马来语", "Malay", "Latn", "ltr", None),
    LanguageInfo("el-GR", "希腊语", "Greek", "Grek", "ltr", "european_continental"),
    LanguageInfo("vi-VN", "越南语", "Vietnamese", "Latn", "ltr", "east_asian_confucian"),
    LanguageInfo("ur-PK", "乌尔都语", "Urdu", "Arab", "rtl", "south_asian"),
    LanguageInfo("hi-IN", "印地语", "Hindi", "Deva", "ltr", "south_asian"),
]

SUPPORTED_LANGUAGE_CODES: frozenset[str] = frozenset(lang.code for lang in SUPPORTED_LANGUAGES)

_LANGUAGE_BY_CODE: dict[str, LanguageInfo] = {lang.code: lang for lang in SUPPORTED_LANGUAGES}


def is_supported_language(code: str) -> bool:
    """判断给定 BCP-47 code 是否在支持列表内。"""
    return code in SUPPORTED_LANGUAGE_CODES


def get_language(code: str) -> Optional[LanguageInfo]:
    """按 code 查询语言元数据，不存在返回 None。"""
    return _LANGUAGE_BY_CODE.get(code)


def language_descriptor(code: str) -> str:
    """返回注入 LLM 提示词的人类可读语言描述串。

    - LTR + 拉丁脚本 → 仅英文名（如 "English"、"Swahili"）
    - 非拉丁或 RTL → 英文名 + 脚本/方向提示
      （如 "Arabic (Arabic script, right-to-left)"、"Kazakh (Cyrillic script)"）
    未知 code 回退返回原值（不阻断流程，仅降级提示质量）。
    """
    lang = _LANGUAGE_BY_CODE.get(code)
    if lang is None:
        return code
    if lang.script == "Latn" and lang.direction == "ltr":
        return lang.name_en
    parts: list[str] = []
    script_name = _SCRIPT_NAMES.get(lang.script, lang.script)
    parts.append(f"{script_name} script")
    if lang.direction == "rtl":
        parts.append("right-to-left")
    return f"{lang.name_en} ({', '.join(parts)})"
