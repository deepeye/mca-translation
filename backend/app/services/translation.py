import json
import logging

from app.llm.bailian import bailian_client
from app.llm.prompts import RISK_ANNOTATION_PROMPT, STRATEGY_DESCRIPTIONS, TRANSLATION_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class TranslationPipeline:
    """P0 translation pipeline: main translation + basic risk annotation."""

    async def translate(self, source_text: str, genre: str, strategy: str, target_language: str) -> dict:
        """Run the P0 pipeline. Returns {translated_text, risk_annotations}."""
        # Step 3: Main translation
        translated_text = await self._main_translation(source_text, genre, strategy, target_language)

        # Step 5 (simplified): Basic risk annotation
        risk_annotations = await self._risk_annotation(source_text, translated_text, target_language)

        return {
            "translated_text": translated_text,
            "risk_annotations": risk_annotations,
            "acceptance_score": -1,  # P0: not computed
        }

    async def _main_translation(self, source_text: str, genre: str, strategy: str, target_language: str) -> str:
        strategy_desc = STRATEGY_DESCRIPTIONS.get(strategy, STRATEGY_DESCRIPTIONS["semantic_equivalence"])
        system_prompt = TRANSLATION_SYSTEM_PROMPT.format(
            target_language=target_language, genre=genre, strategy_description=strategy_desc
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
