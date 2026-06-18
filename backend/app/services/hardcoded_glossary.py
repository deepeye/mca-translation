"""硬编码政治术语词典。

提供 15 个中国政治/文化负载词的多语言译法与风险注释，
供主翻译 prompt 注入 `<glossary_terms>` 块使用。

该模块为纯内存静态查表实现，不依赖数据库或 LLM 调用。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GlossaryTerm:
    """单个术语条目。"""

    source_term: str
    translations: dict[str, dict]
    term_type: str
    risk_notes: str = ""
    applicable_genres: list[str] | None = None


_HARDCODED_TERMS: list[GlossaryTerm] = [
    GlossaryTerm(
        source_term="五位一体",
        translations={
            "en-GB": {
                "rendering": "Five-sphere Overall Plan",
                "alternatives": ["integrated five-sphere strategy"],
                "notes": "学术场景可展开解释；大众媒体可简化为 holistic development",
            },
            "de-DE": {
                "rendering": "Fünf-Bereich-Gesamtstrategie",
                "alternatives": [],
                "notes": "",
            },
        },
        term_type="political_discourse",
        risk_notes="直译在大众媒体可读性较低",
        applicable_genres=["political", "policy", "news"],
    ),
    GlossaryTerm(
        source_term="以人民为中心",
        translations={
            "en-GB": {
                "rendering": "people-centered",
                "alternatives": ["people-first"],
                "notes": "政策受众用 people-centered，大众用 people-first",
            },
        },
        term_type="political_discourse",
        risk_notes="部分西方媒体将其与民粹主义关联",
        applicable_genres=["political", "policy", "news", "brand"],
    ),
    GlossaryTerm(
        source_term="新型举国体制",
        translations={
            "en-GB": {
                "rendering": "state-coordinated national mobilization system",
                "alternatives": ["China's centralized innovation model"],
                "notes": "宣示场景用前者，新闻场景用后者",
            },
        },
        term_type="political_discourse",
        applicable_genres=["political", "policy"],
    ),
    GlossaryTerm(
        source_term="四个自信",
        translations={
            "en-GB": {
                "rendering": "Four-sphere Confidence",
                "alternatives": ["confidence in the path, theory, system, and culture"],
                "notes": "首次出现建议展开解释",
            },
        },
        term_type="political_discourse",
        applicable_genres=["political", "policy"],
    ),
    GlossaryTerm(
        source_term="共同富裕",
        translations={
            "en-GB": {
                "rendering": "common prosperity",
                "alternatives": ["shared prosperity"],
                "notes": "common prosperity 为官方标准译法",
            },
        },
        term_type="political_discourse",
        risk_notes="西方媒体可能误读为平均主义",
        applicable_genres=["political", "policy", "news"],
    ),
    GlossaryTerm(
        source_term="全过程人民民主",
        translations={
            "en-GB": {
                "rendering": "whole-process people's democracy",
                "alternatives": [],
                "notes": "固定译法，不宜简化",
            },
        },
        term_type="political_discourse",
        risk_notes="西方受众可能因政治制度差异产生排斥",
        applicable_genres=["political", "policy"],
    ),
    GlossaryTerm(
        source_term="人类命运共同体",
        translations={
            "en-GB": {
                "rendering": "community with a shared future for mankind",
                "alternatives": ["global community of shared future"],
                "notes": "联合国文件标准译法",
            },
        },
        term_type="political_discourse",
        applicable_genres=["political", "policy", "news"],
    ),
    GlossaryTerm(
        source_term="一带一路",
        translations={
            "en-GB": {
                "rendering": "Belt and Road",
                "alternatives": ["Belt and Road Initiative (BRI)"],
                "notes": "首次出现建议全称，后续可用 BRI",
            },
        },
        term_type="political_discourse",
        applicable_genres=["political", "policy", "news", "brand"],
    ),
    GlossaryTerm(
        source_term="高质量发展",
        translations={
            "en-GB": {
                "rendering": "high-quality development",
                "alternatives": [],
                "notes": "",
            },
        },
        term_type="political_discourse",
        applicable_genres=["political", "policy", "news", "brand"],
    ),
    GlossaryTerm(
        source_term="新质生产力",
        translations={
            "en-GB": {
                "rendering": "new quality productive forces",
                "alternatives": ["new productivity forces"],
                "notes": "新兴术语，建议首次出现时加括号解释",
            },
        },
        term_type="political_discourse",
        risk_notes="新出现术语，建议人工审校",
        applicable_genres=["political", "policy", "news"],
    ),
    GlossaryTerm(
        source_term="中国式现代化",
        translations={
            "en-GB": {
                "rendering": "Chinese modernization",
                "alternatives": ["China's path to modernization"],
                "notes": "",
            },
        },
        term_type="political_discourse",
        applicable_genres=["political", "policy", "news"],
    ),
    GlossaryTerm(
        source_term="绿水青山就是金山银山",
        translations={
            "en-GB": {
                "rendering": "lucid waters and lush mountains are invaluable assets",
                "alternatives": ["green mountains are gold mountains"],
                "notes": "前者为官方标准译法",
            },
        },
        term_type="cultural_metaphor",
        applicable_genres=["political", "policy", "news", "brand"],
    ),
    GlossaryTerm(
        source_term="摸着石头过河",
        translations={
            "en-GB": {
                "rendering": "crossing the river by feeling the stones",
                "alternatives": ["feeling the stones while crossing the river"],
                "notes": "",
            },
        },
        term_type="cultural_metaphor",
        applicable_genres=["political", "policy", "news"],
    ),
    GlossaryTerm(
        source_term="撸起袖子加油干",
        translations={
            "en-GB": {
                "rendering": "roll up our sleeves and work hard",
                "alternatives": ["get down to work with added energy"],
                "notes": "",
            },
        },
        term_type="cultural_metaphor",
        applicable_genres=["political", "news"],
    ),
    GlossaryTerm(
        source_term="小康",
        translations={
            "en-GB": {
                "rendering": "moderate prosperity",
                "alternatives": ["xiaokang (moderate prosperity)"],
                "notes": "首次出现建议 xiaokang 加括号解释",
            },
        },
        term_type="cultural_metaphor",
        applicable_genres=["political", "policy", "news"],
    ),
]


_term_by_source: dict[str, GlossaryTerm] = {
    term.source_term: term for term in _HARDCODED_TERMS
}

_all_source_terms: list[str] = [term.source_term for term in _HARDCODED_TERMS]


def find_terms_in_text(text: str) -> list[GlossaryTerm]:
    """对源文本做子串匹配，返回所有命中的术语条目（按术语定义顺序）。

    注意：子串匹配可能在无关上下文中产生误报（例如"小康"可能出现在非政治语境中）。
    """
    if not text:
        return []
    return [
        _term_by_source[source]
        for source in _all_source_terms
        if source in text
    ]


def get_term_translation(
    term: GlossaryTerm,
    language: str,
    strategy: str = "semantic_equivalence",
) -> dict:
    """返回单个术语在指定语言下的译法信息。

    返回结构：{"rendering": str, "notes": str, "alternatives": list[str]}。

    strategy="audience_first" 时，若存在备选译法，则使用最后一个备选作为
    更通俗的版本（用于面向大众读者的简化场景）。
    """
    lang_entry = term.translations.get(language)
    if lang_entry is None:
        return {"preferred": "", "notes": "", "alternatives": []}

    rendering = lang_entry.get("rendering", "")
    notes = lang_entry.get("notes", "")
    alternatives = list(lang_entry.get("alternatives", []))

    if strategy == "audience_first" and alternatives:
        rendering = alternatives[-1]

    return {"preferred": rendering, "notes": notes, "alternatives": alternatives}


def format_glossary_block(
    terms: list[GlossaryTerm],
    language: str,
    genre: str,
    strategy: str,
) -> str:
    """将命中术语格式化为 `<glossary_terms>` prompt 块。

    若术语设置了 applicable_genres 且 genre 不在其中，则跳过该术语。
    没有命中术语时返回空字符串。
    """
    filtered: list[GlossaryTerm] = []
    for term in terms:
        if term.applicable_genres is not None and genre not in term.applicable_genres:
            continue
        filtered.append(term)

    if not filtered:
        return ""

    lines: list[str] = ["<glossary_terms>"]
    for term in filtered:
        info = get_term_translation(term, language, strategy)
        rendering = info["preferred"]
        notes = info["notes"]
        alternatives = info["alternatives"]

        parts: list[str] = [
            f'  <term source="{term.source_term}" rendering="{rendering}" type="{term.term_type}">'
        ]
        if alternatives:
            parts.append("    <alternatives>")
            for alt in alternatives:
                parts.append(f"      <alt>{alt}</alt>")
            parts.append("    </alternatives>")
        if notes:
            parts.append(f"    <notes>{notes}</notes>")
        if term.risk_notes:
            parts.append(f"    <risk>{term.risk_notes}</risk>")
        parts.append("  </term>")
        lines.extend(parts)

    lines.append("</glossary_terms>")
    return "\n".join(lines)
