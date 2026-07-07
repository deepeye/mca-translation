"""文化语境预处理服务。

输入源文本+文化圈+受众+文体；调用 LLM 识别文化负载词并产出本土化约束。
任何失败（白名单不命中、LLM 异常、JSON 解析失败、字段验证失败）都返回 None，
让上层管线降级：主翻译照常进行，不再注入术语级约束（culture_loaded_terms /
cultural_notes / taboo_warnings）。注意：若上层已选定 cultural_sphere，主翻译
prompt 仍会注入文化圈/受众特征段（见 build_translation_system_prompt），只是
缺少术语级约束——这保证译文仍符合目标文化语境，只是没有了逐词适配建议。
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional, Protocol

from pydantic import ValidationError

from app.llm.cultural_profiles import (
    AUDIENCE_TYPE_GUIDELINES,
    CULTURAL_SPHERE_PROFILES,
)
from app.llm.prompts import CULTURAL_PREPROCESS_PROMPT
from app.schemas.job import CulturalPreprocessResult

logger = logging.getLogger(__name__)

# 中性通用政治/社会词汇：不应被 cultural_preprocess 识别为文化负载词，
# 否则模型会把普通词过译为特定国家/政府的特指表达。
_PROTECTED_NEUTRAL_TERMS: frozenset[str] = frozenset({"国家", "政府", "人民"})


class _LLMClient(Protocol):
    async def chat(self, *, model: str, messages: list, temperature: float = ...) -> dict[str, Any]: ...


def _strip_code_fences(text: str) -> str:
    s = text.strip()
    if s.startswith("```"):
        # 去掉首行（``` 或 ```json）和尾部 ```
        s = s.split("\n", 1)[1] if "\n" in s else s[3:]
        if s.endswith("```"):
            s = s[: -3]
    return s.strip()


async def cultural_preprocess(
    *,
    text: str,
    cultural_sphere: str,
    audience_type: str,
    genre: str,
    llm_client: _LLMClient,
    model: str = "qwen-plus",
) -> Optional[CulturalPreprocessResult]:
    """识别源文本中的文化负载词并生成本土化约束。

    任何失败都返回 None，调用方应降级处理（不注入文化约束继续主翻译）。
    """
    if cultural_sphere not in CULTURAL_SPHERE_PROFILES:
        logger.info("cultural_preprocess skipped: unknown cultural_sphere=%s", cultural_sphere)
        return None
    if audience_type not in AUDIENCE_TYPE_GUIDELINES:
        logger.info("cultural_preprocess skipped: unknown audience_type=%s", audience_type)
        return None

    prompt = CULTURAL_PREPROCESS_PROMPT.format(
        source_text=text,
        cultural_sphere_profile=CULTURAL_SPHERE_PROFILES[cultural_sphere],
        audience_type_guideline=AUDIENCE_TYPE_GUIDELINES[audience_type],
        genre=genre,
    )

    try:
        response = await llm_client.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )
    except Exception as e:
        logger.warning("cultural_preprocess LLM call failed: %s", e)
        return None

    raw = response.get("content", "") if isinstance(response, dict) else ""
    cleaned = _strip_code_fences(raw)
    if not cleaned:
        logger.warning("cultural_preprocess got empty content")
        return None

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.warning("cultural_preprocess JSON parse failed: %s; head=%r", e, cleaned[:200])
        return None

    try:
        result = CulturalPreprocessResult(**data)
    except ValidationError as e:
        logger.warning("cultural_preprocess schema validation failed: %s", e)
        return None

    # 过滤中性通用词：这些词不应被识别为文化负载词。
    filtered_terms = [
        t for t in result.culture_loaded_terms
        if t.term not in _PROTECTED_NEUTRAL_TERMS
    ]
    if len(filtered_terms) != len(result.culture_loaded_terms):
        logger.debug(
            "cultural_preprocess filtered protected neutral terms: %s",
            [t.term for t in result.culture_loaded_terms if t.term in _PROTECTED_NEUTRAL_TERMS],
        )
        result = CulturalPreprocessResult(
            culture_loaded_terms=filtered_terms,
            cultural_notes=result.cultural_notes,
            taboo_warnings=result.taboo_warnings,
        )

    return result
