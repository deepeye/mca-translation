import json
import logging

from app.llm.bailian import bailian_client
from app.llm.cultural_profiles import AUDIENCE_TYPE_GUIDELINES, CULTURAL_SPHERE_PROFILES
from app.llm.prompts import RISK_ANNOTATION_PROMPT, STRATEGY_DESCRIPTIONS, TRANSLATION_SYSTEM_PROMPT
from app.schemas.job import CulturalPreprocessResult
from app.services.cultural import cultural_preprocess

logger = logging.getLogger(__name__)


def build_translation_system_prompt(
    *,
    target_language: str,
    genre: str,
    strategy: str,
    cultural_constraints: CulturalPreprocessResult | None = None,
    cultural_sphere: str | None = None,
    audience_type: str | None = None,
) -> str:
    """构建主翻译的 system prompt。可选注入 <cultural_constraints> 段。"""
    strategy_desc = STRATEGY_DESCRIPTIONS.get(strategy, STRATEGY_DESCRIPTIONS["semantic_equivalence"])
    base = TRANSLATION_SYSTEM_PROMPT.format(
        target_language=target_language,
        genre=genre,
        strategy_description=strategy_desc,
    )

    if cultural_sphere is None or cultural_sphere not in CULTURAL_SPHERE_PROFILES:
        # 没有文化圈 → 不注入文化段，行为与现有完全一致
        return base

    sphere_profile = CULTURAL_SPHERE_PROFILES[cultural_sphere]
    audience_guideline = AUDIENCE_TYPE_GUIDELINES.get(audience_type or "", "")

    must_lines: list[str] = []
    suggest_lines: list[str] = []
    notes: list[str] = []
    taboos: list[str] = []
    if cultural_constraints is not None:
        for t in cultural_constraints.culture_loaded_terms:
            if t.culture_gap == "high":
                must_lines.append(
                    f'- "{t.term}" → MUST_USE {t.adaptation_strategy} 翻译: "{t.suggested_rendering}"\n  原因: {t.reason}'
                )
            elif t.culture_gap == "medium":
                suggest_lines.append(
                    f'- "{t.term}" → SUGGEST {t.adaptation_strategy} 翻译: "{t.suggested_rendering}"\n  原因: {t.reason}'
                )
            # low: 不生成约束
        notes = list(cultural_constraints.cultural_notes)
        taboos = list(cultural_constraints.taboo_warnings)

    parts = ["<cultural_constraints>"]
    parts.append(f"[文化圈特征] {sphere_profile}")
    if audience_guideline:
        parts.append(f"[受众类型] {audience_guideline}")
    if must_lines:
        parts.append("[术语约束 - 必须遵守]")
        parts.extend(must_lines)
    if suggest_lines:
        parts.append("[术语约束 - 建议遵守]")
        parts.extend(suggest_lines)
    if notes:
        parts.append("[文化注意事项]")
        parts.extend(f"- {n}" for n in notes)
    if taboos:
        parts.append("[禁忌提醒]")
        parts.extend(f"- {t}" for t in taboos)
    parts.append("</cultural_constraints>")

    cultural_block = "\n".join(parts)
    return f"{base}\n\n{cultural_block}\n"


class TranslationPipeline:
    """P0 translation pipeline: main translation + basic risk annotation."""

    async def translate(
        self,
        source_text: str,
        genre: str,
        strategy: str,
        target_language: str,
        cultural_sphere: str | None = None,
        audience_type: str | None = None,
    ) -> dict:
        """Run the pipeline. Returns {translated_text, risk_annotations, cultural_adaptation, acceptance_score}."""
        # Step 1: cultural preprocessing (optional, graceful fallback to None)
        cultural_result = None
        if cultural_sphere:
            cultural_result = await cultural_preprocess(
                text=source_text,
                cultural_sphere=cultural_sphere,
                audience_type=audience_type or "general_public",
                genre=genre,
                llm_client=bailian_client,
            )

        # Step 2: main translation
        translated_text = await self._main_translation(
            source_text=source_text,
            genre=genre,
            strategy=strategy,
            target_language=target_language,
            cultural_constraints=cultural_result,
            cultural_sphere=cultural_sphere,
            audience_type=audience_type,
        )

        # Step 3: risk annotation (unchanged)
        risk_annotations = await self._risk_annotation(source_text, translated_text, target_language)

        return {
            "translated_text": translated_text,
            "risk_annotations": risk_annotations,
            "cultural_adaptation": cultural_result.model_dump() if cultural_result else None,
            "acceptance_score": -1,
        }

    async def _main_translation(
        self,
        source_text: str,
        genre: str,
        strategy: str,
        target_language: str,
        cultural_constraints: CulturalPreprocessResult | None = None,
        cultural_sphere: str | None = None,
        audience_type: str | None = None,
    ) -> str:
        system_prompt = build_translation_system_prompt(
            target_language=target_language,
            genre=genre,
            strategy=strategy,
            cultural_constraints=cultural_constraints,
            cultural_sphere=cultural_sphere,
            audience_type=audience_type,
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": source_text},
        ]
        result = await bailian_client.chat(model="qwen-max", messages=messages)
        return result["content"]

    async def _risk_annotation(self, source_text: str, translated_text: str, target_language: str) -> list:
        prompt = RISK_ANNOTATION_PROMPT.format(
            source_text=source_text, translated_text=translated_text, target_language=target_language
        )
        messages = [{"role": "user", "content": prompt}]
        try:
            result = await bailian_client.chat(model="qwen-plus", messages=messages, temperature=0.1)
            content = result["content"].strip()
            # Strip markdown code fences if present
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0]
            annotations = json.loads(content)
            if isinstance(annotations, list):
                # Add offset and status fields
                used_offsets = set()
                for ann in annotations:
                    # Normalize: ensure "phrase" key exists (LLM may output "span_text")
                    if "phrase" not in ann and "span_text" in ann:
                        ann["phrase"] = ann.pop("span_text")
                    offset = translated_text.find(ann.get("phrase", ""))
                    if offset == -1 or offset in used_offsets:
                        ann["offset"] = -1
                    else:
                        used_offsets.add(offset)
                        ann["offset"] = offset
                    ann.setdefault("status", "open")
                return annotations
            return []
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Risk annotation parsing failed: {e}")
            return []

    async def translate_stream(self, source_text: str, genre: str, strategy: str, target_language: str):
        """Stream main translation. Yields text chunks."""
        strategy_desc = STRATEGY_DESCRIPTIONS.get(strategy, STRATEGY_DESCRIPTIONS["semantic_equivalence"])
        system_prompt = TRANSLATION_SYSTEM_PROMPT.format(
            target_language=target_language, genre=genre, strategy_description=strategy_desc
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": source_text},
        ]
        async for chunk in bailian_client.chat_stream(model="qwen-max", messages=messages):
            yield chunk


pipeline = TranslationPipeline()
