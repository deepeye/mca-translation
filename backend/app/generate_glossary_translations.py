"""一次性脚本：用 LLM 为 13 个新目标语言生成 15 个硬编码政治术语的译文。

输出 backend/app/data/glossary_translations_generated.json，供
hardcoded_glossary.py 合并加载。译文为 LLM 生成基线，待人工校对。

运行：cd backend && python -m app.generate_glossary_translations
"""
import asyncio
import json
import logging
import pathlib

from app.constants.languages import SUPPORTED_LANGUAGES, language_descriptor
from app.llm.bailian import bailian_client
from app.services.hardcoded_glossary import _HARDCODED_TERMS

logger = logging.getLogger(__name__)

# 仅生成「现有硬编码译文未覆盖」的语言（en-GB/de-DE 已有手编）。
_EXISTING_CODES = {"en-GB", "de-DE"}
NEW_LANGUAGE_CODES = [lang.code for lang in SUPPORTED_LANGUAGES if lang.code not in _EXISTING_CODES]

OUTPUT_FILE = (
    pathlib.Path(__file__).resolve().parent / "data" / "glossary_translations_generated.json"
)


def _build_prompt(lang_code: str) -> str:
    descriptor = language_descriptor(lang_code)
    term_lines = []
    for term in _HARDCODED_TERMS:
        en_ref = term.translations.get("en-GB", {}).get("rendering", "")
        ref = f"（英译参考：{en_ref}）" if en_ref else ""
        term_lines.append(f"- {term.source_term}{ref}")
    return (
        f"将以下中文政治/文化术语译为 {descriptor}。\n\n"
        "要求：\n"
        "- 每个术语给出 rendering（首选译法）、alternatives（0-2 个备选）、"
        'notes（中文风险备注，说明敏感点/转译建议，可空字符串）。\n'
        "- 只输出 JSON 对象，key 为中文术语原文，"
        'value 为 {"rendering": str, "alternatives": [str], "notes": str}。\n'
        "- 不要输出任何解释或 Markdown 代码块。\n\n"
        "术语列表：\n"
        + "\n".join(term_lines)
    )


def _strip_fence(content: str) -> str:
    text = content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        text = text.rsplit("```", 1)[0]
    return text.strip()


async def _generate_for_language(client, lang_code: str) -> dict:
    """为单个语言生成全部 15 词译文。返回 {source_term: {rendering, alternatives, notes}}。"""
    prompt = _build_prompt(lang_code)
    data = {}
    for attempt in (1, 2):
        try:
            result = await client.chat(
                model="qwen-plus",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
            )
            data = json.loads(_strip_fence(result.get("content") or ""))
            break
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning("generate for %s attempt %d failed: %s", lang_code, attempt, e)
            if attempt == 2:
                return {}
    valid = {t.source_term for t in _HARDCODED_TERMS}
    out: dict = {}
    for source_term, entry in data.items():
        if source_term not in valid or not isinstance(entry, dict):
            continue
        rendering = str(entry.get("rendering", "")).strip()
        if not rendering:
            continue
        alternatives = [str(a) for a in entry.get("alternatives", []) if a]
        notes = str(entry.get("notes", ""))
        out[source_term] = {"rendering": rendering, "alternatives": alternatives, "notes": notes}
    return out


async def run(client=None, languages=None) -> dict:
    """生成全部语言的译文。返回 {source_term: {lang_code: {...}}}。client 可注入用于测试。"""
    client = client or bailian_client
    codes = languages or NEW_LANGUAGE_CODES
    result: dict = {}
    for lang_code in codes:
        lang_translations = await _generate_for_language(client, lang_code)
        for source_term, entry in lang_translations.items():
            result.setdefault(source_term, {})[lang_code] = entry
        logger.info("generated %d terms for %s", len(lang_translations), lang_code)
    return result


def write_output(data: dict) -> None:
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "_comment": "LLM 生成的政治术语译文基线，待人工校对。"
        "结构：{source_term: {lang_code: {rendering, alternatives, notes}}}。手编译文优先。",
        "translations": data,
    }
    OUTPUT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


async def _cli():
    logging.basicConfig(level=logging.INFO)
    data = await run()
    write_output(data)
    total = sum(len(v) for v in data.values())
    print(f"wrote {total} entries to {OUTPUT_FILE}")


if __name__ == "__main__":
    asyncio.run(_cli())
