"""LLM-based per-term translation auto-fill for user glossary entries.

纯工具模块：输入中文 source_term + 目标语言 + 可选英语参考，输出
{preferred, alternatives, notes}。错误处理由调用方负责重试/跳过。
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from app.constants.languages import language_descriptor
from app.llm.bailian import bailian_client

logger = logging.getLogger(__name__)


def _strip_fence(content: str) -> str:
    text = content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        text = text.rsplit("```", 1)[0]
    return text.strip()


def _build_prompt(source_term: str, target_lang: str, english_reference: Optional[str]) -> str:
    descriptor = language_descriptor(target_lang)
    ref_line = f"英语参考译法：{english_reference}\n" if english_reference else ""
    return (
        f"将中文术语「{source_term}」译为 {descriptor}。\n"
        f"{ref_line}"
        '输出 JSON：{"rendering": str, "alternatives": [str], "notes": str}\n'
        "不要输出解释或 Markdown 代码块。"
    )


async def generate_translation(
    source_term: str,
    target_lang: str,
    english_reference: Optional[str] = None,
    *,
    client=None,
) -> Optional[dict]:
    """为单个术语生成单个目标语言的译文。失败返回 None。"""
    prompt = _build_prompt(source_term, target_lang, english_reference)
    c = client or bailian_client
    for attempt in (1, 2):
        try:
            result = await c.chat(
                model="qwen-plus",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
            )
            data = json.loads(_strip_fence(result.get("content") or ""))
            if not isinstance(data, dict):
                continue
            rendering = str(data.get("rendering", "")).strip()
            if not rendering:
                continue
            alternatives = [str(a) for a in data.get("alternatives", []) if a]
            notes = str(data.get("notes", ""))
            return {"preferred": rendering, "alternatives": alternatives, "notes": notes}
        except Exception as e:
            logger.warning(
                "glossary autofill %s for %s attempt %d failed: %s",
                source_term,
                target_lang,
                attempt,
                e,
            )
            if attempt == 2:
                return None
    return None
