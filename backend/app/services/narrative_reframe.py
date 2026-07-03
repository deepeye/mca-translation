import hashlib
import json

from pydantic import ValidationError

from app.core.config import settings
from app.llm.bailian import bailian_client
from app.schemas.narrative_reframe import NarrativePreviewMode, NarrativeReframeAnalysis
from app.constants.languages import language_descriptor


def compute_text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _strip_json_fence(content: str) -> str:
    text = content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        text = text.rsplit("```", 1)[0]
    return text.strip()


def parse_analysis_payload(content: str) -> NarrativeReframeAnalysis:
    try:
        data = json.loads(_strip_json_fence(content))
        return NarrativeReframeAnalysis(**data)
    except (json.JSONDecodeError, TypeError, ValidationError) as exc:
        raise ValueError("Invalid narrative analysis JSON") from exc


class NarrativeReframeService:
    def __init__(self, llm_client=None):
        # llm_client=None 时运行时取全局 bailian_client，便于测试替换。
        self._client = llm_client
        self._model = getattr(settings, "BAILIAN_MODEL", None) or "qwen-plus"

    async def analyze(
        self,
        *,
        source_text: str,
        translated_text: str,
        genre: str,
        target_language: str,
        cultural_sphere: str | None = None,
        audience_type: str | None = None,
    ) -> NarrativeReframeAnalysis:
        prompt = self._build_analysis_prompt(
            source_text=source_text,
            translated_text=translated_text,
            genre=genre,
            target_language=target_language,
            cultural_sphere=cultural_sphere,
            audience_type=audience_type,
        )
        client = self._client if self._client is not None else bailian_client
        result = await client.chat(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        return parse_analysis_payload(result.get("content") or "")

    async def preview(
        self,
        *,
        translated_text: str,
        analysis: NarrativeReframeAnalysis,
        target_language: str,
        mode: NarrativePreviewMode = "light_cohesion",
    ) -> str:
        if mode != "light_cohesion":
            raise ValueError("Unsupported narrative preview mode")
        prompt = self._build_preview_prompt(
            translated_text=translated_text,
            analysis=analysis,
            target_language=target_language,
        )
        client = self._client if self._client is not None else bailian_client
        result = await client.chat(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        return (result.get("content") or "").strip()

    def _build_analysis_prompt(
        self,
        *,
        source_text: str,
        translated_text: str,
        genre: str,
        target_language: str,
        cultural_sphere: str | None,
        audience_type: str | None,
    ) -> str:
        target_language = language_descriptor(target_language)
        return f"""请分析以下译文的叙事结构是否适合目标受众，并只输出 JSON。

输出 schema:
{{
  "source_outline": [{{"id": "s1", "order": 1, "summary": "...", "text_span": "..."}}],
  "current_translation_outline": [{{"id": "t1", "order": 1, "summary": "...", "text_span": "..."}}],
  "recommended_outline": [{{
    "id": "r1",
    "target_order": 1,
    "source_ref_ids": ["t1"],
    "summary": "...",
    "reason_label": "audience_habit|cultural_context|communication",
    "reason": "...",
    "expected_effect": "..."
  }}],
  "overall_rationale": "...",
  "confidence": 0.0
}}

约束:
- reason_label 只能是 audience_habit、cultural_context、communication。
- confidence 必须在 0 到 1 之间。
- recommended_outline 可以为空，表示无明显重排价值。
- text_span 只用于展示定位，不要当作稳定 offset。

文体: {genre or "未指定"}
目标语言: {target_language}
文化圈: {cultural_sphere or "未指定"}
受众类型: {audience_type or "未指定"}

原文:
{source_text}

当前译文:
{translated_text}
"""

    def _build_preview_prompt(
        self,
        *,
        translated_text: str,
        analysis: NarrativeReframeAnalysis,
        target_language: str,
    ) -> str:
        target_language = language_descriptor(target_language)
        return f"""请根据叙事结构分析，对当前译文生成 light_cohesion 模式的重排预览。

要求:
- 只做轻量衔接和段落顺序调整，不做全文重写。
- 保留原译文的事实、术语和语气。
- 直接输出预览译文，不要输出解释或 Markdown。
- 目标语言: {target_language}

叙事结构分析 JSON:
{analysis.model_dump_json()}

当前译文:
{translated_text}
"""
