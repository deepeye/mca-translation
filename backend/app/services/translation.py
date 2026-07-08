import json
import logging
import uuid
from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.bailian import bailian_client
from app.llm.cultural_profiles import AUDIENCE_TYPE_GUIDELINES, CULTURAL_SPHERE_PROFILES
from app.llm.prompts import RISK_ANNOTATION_PROMPT, STRATEGY_DESCRIPTIONS, TRANSLATION_SYSTEM_PROMPT
from app.schemas.job import CulturalPreprocessResult
from app.services.cultural import cultural_preprocess
from app.services.glossary_rag import retrieve_glossary_terms
from app.constants.languages import language_descriptor

logger = logging.getLogger(__name__)

# Sentinel distinguishing "caller did not pass cultural_constraints" (→ run
# preprocess internally) from "caller passed None" (→ preprocess already ran
# upstream and returned nothing). Lets multi-language jobs run preprocess once.
_CULTURAL_CONSTRAINTS_NOT_PROVIDED = object()


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
        target_language=language_descriptor(target_language),
        genre=genre,
        strategy_description=strategy_desc,
    )

    if cultural_sphere is None or cultural_sphere not in CULTURAL_SPHERE_PROFILES:
        # 没有文化圈 → 不注入文化段，行为与现有完全一致
        result = base
    else:
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
        if strategy == "semantic_equivalence":
            parts.append(
                "[翻译策略约束]\n"
                "当前为信息等值模式：普通政治/国家类通用词汇（如“国家”“政府”“人民”）应保持中性译法，"
                "仅在原文明确指向特定国家、政府或机构时才具体化。"
            )
        parts.append("</cultural_constraints>")

        cultural_block = "\n".join(parts)
        result = f"{base}\n\n{cultural_block}\n"

    return result


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
        db: AsyncSession | None = None,
        user_id: uuid.UUID | None = None,
        cultural_constraints: object = _CULTURAL_CONSTRAINTS_NOT_PROVIDED,
        on_chunk: Callable[[str], Awaitable[None]] | None = None,
    ) -> dict:
        """Run the pipeline. Returns {translated_text, risk_annotations,
        cultural_adaptation, acceptance_score, decision_entries}.

        ``cultural_constraints`` may be a pre-computed ``CulturalPreprocessResult`` or
        ``None``. When the caller passes it (even ``None``), the internal preprocess
        step is skipped — use this to run preprocess once for a multi-language job
        and reuse the result across languages. When omitted, preprocess runs here.

        ``on_chunk``: optional async callback ``(accumulated: str) -> Awaitable[None]``.
        When provided, the main translation streams via ``chat_stream`` and the callback
        receives the accumulated translated text after each chunk — used by the Celery
        task to persist partial translations during streaming. When omitted, streaming
        still runs but no callback is invoked.

        ``decision_entries`` 收集各阶段决策条目，由调用方持久化。
        """
        # 新增：收集决策条目
        decision_entries: list[dict] = []

        # Step 1: cultural preprocessing (optional, graceful fallback to None).
        # Skipped when the caller already ran it and passed the result in.
        if cultural_constraints is _CULTURAL_CONSTRAINTS_NOT_PROVIDED:
            cultural_result = None
            if cultural_sphere:
                cultural_result = await cultural_preprocess(
                    text=source_text,
                    cultural_sphere=cultural_sphere,
                    audience_type=audience_type or "general_public",
                    genre=genre,
                    llm_client=bailian_client,
                )
        else:
            cultural_result = cultural_constraints  # type: ignore[assignment]

        # 决策提取：文化预处理阶段 — 记录识别的文化负载词适配
        if cultural_result is not None:
            for term in cultural_result.culture_loaded_terms:
                decision_entries.append({
                    "stage": "preprocess",
                    "decision_type": "culture_term_adaptation",
                    "source_phrase": term.term,
                    "target_phrase": term.suggested_rendering,
                    "decision": f"采用 {term.adaptation_strategy} 策略翻译「{term.term}」",
                    "reasoning": term.reason,
                    "confidence": term.culture_gap,
                    "metadata": {"adaptation_strategy": term.adaptation_strategy},
                })

        # RAG glossary retrieval (Phase 2)
        glossary_block = ""
        if db and user_id:
            rag_terms = await retrieve_glossary_terms(
                db=db,
                user_id=user_id,
                source_text=source_text,
                language=target_language,
                genre=genre,
                top_k=5,
            )
            if rag_terms:
                glossary_block = self._format_rag_glossary_block(rag_terms, target_language, strategy)
                # 决策提取：术语检索阶段 — 记录命中的知识库术语
                for t in rag_terms:
                    trans = t.get("translations", {}).get(target_language, {})
                    target_phrase = trans.get("preferred") if trans else None
                    decision_entries.append({
                        "stage": "glossary",
                        "decision_type": "term_retrieved",
                        "source_phrase": t.get("source_term"),
                        "target_phrase": target_phrase,
                        "decision": f"从知识库检索到术语「{t.get('source_term', '')}」",
                        "reasoning": t.get("risk_notes") or "知识库匹配",
                        "confidence": None,
                        "metadata": {
                            "glossary_id": str(t["id"]) if t.get("id") else None,
                            "source": t.get("source"),
                            "term_type": t.get("term_type"),
                        },
                    })
        else:
            # Fallback to hardcoded (Phase 1)
            from app.services.hardcoded_glossary import find_terms_in_text, format_glossary_block
            matched_terms = find_terms_in_text(source_text)
            if matched_terms:
                glossary_block = format_glossary_block(matched_terms, target_language, genre, strategy)

        # Step 2: main translation
        translated_text = await self._main_translation(
            source_text=source_text,
            genre=genre,
            strategy=strategy,
            target_language=target_language,
            cultural_constraints=cultural_result,
            cultural_sphere=cultural_sphere,
            audience_type=audience_type,
            glossary_block=glossary_block,
            on_chunk=on_chunk,
        )

        # 决策提取：翻译阶段 — 记录注入 prompt 的文化约束（high/medium）
        if cultural_result is not None:
            for term in cultural_result.culture_loaded_terms:
                if term.culture_gap in ("high", "medium"):
                    decision_entries.append({
                        "stage": "translate",
                        "decision_type": "cultural_constraint_applied",
                        "source_phrase": term.term,
                        "target_phrase": term.suggested_rendering,
                        "decision": f"翻译时必须遵守：「{term.term}」→ {term.suggested_rendering}",
                        "reasoning": term.reason,
                        "confidence": term.culture_gap,
                        "metadata": {"adaptation_strategy": term.adaptation_strategy},
                    })

        # Step 3: risk annotation
        risk_annotations = await self._risk_annotation(source_text, translated_text, target_language)

        # 决策提取：风险标注阶段 — 记录每条识别的风险
        for risk in risk_annotations:
            decision_entries.append({
                "stage": "risk",
                "decision_type": "risk_identified",
                "source_phrase": None,
                "target_phrase": risk.get("phrase"),
                "decision": f"标记为 {risk.get('risk_level', 'unknown')} 风险：{risk.get('risk_type', '')}",
                "reasoning": risk.get("explanation", ""),
                "confidence": risk.get("risk_level"),
                "metadata": {
                    "risk_level": risk.get("risk_level"),
                    "risk_type": risk.get("risk_type"),
                },
            })

        return {
            "translated_text": translated_text,
            "risk_annotations": risk_annotations,
            "cultural_adaptation": cultural_result.model_dump() if cultural_result else None,
            "acceptance_score": -1,
            "decision_entries": decision_entries,
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
        glossary_block: str = "",
        on_chunk: Callable[[str], Awaitable[None]] | None = None,
    ) -> str:
        system_prompt = build_translation_system_prompt(
            target_language=target_language,
            genre=genre,
            strategy=strategy,
            cultural_constraints=cultural_constraints,
            cultural_sphere=cultural_sphere,
            audience_type=audience_type,
        )
        if glossary_block:
            system_prompt += f"\n\n{glossary_block}\n"
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": source_text},
        ]
        # 流式累积：qwen-max 边生成边回调部分译文
        accumulated = ""
        async for chunk in bailian_client.chat_stream(model="qwen-max", messages=messages):
            accumulated += chunk
            if on_chunk:
                await on_chunk(accumulated)
        return accumulated

    def _format_rag_glossary_block(self, terms: list[dict], language: str, strategy: str) -> str:
        if not terms:
            return ""
        lines = ["<glossary_terms>"]
        lines.append("以下政治话语/文化隐喻有标准译法参考，请优先使用：")
        for t in terms:
            trans = t.get("translations", {}).get(language, {})
            if not trans:
                continue
            rendering = trans.get("preferred", "")
            alternatives = trans.get("alternatives", [])
            notes = trans.get("notes", "")
            if strategy == "audience_first" and alternatives:
                rendering = alternatives[-1]
            lines.append(f'\n  「{t["source_term"]}」({t["term_type"]})')
            lines.append(f'    推荐译法："{rendering}"')
            if alternatives:
                lines.append(f'    备选：{", ".join(f"\"{a}\"" for a in alternatives)}')
            if notes:
                lines.append(f'    备注：{notes}')
            if t.get("risk_notes"):
                lines.append(f'    ⚠ 风险：{t["risk_notes"]}')
            lines.append(f'    来源：{"用户术语库" if t["source"] == "user_glossary" else "系统知识库"}')
        lines.append("</glossary_terms>")
        return "\n".join(lines)

    async def _risk_annotation(self, source_text: str, translated_text: str, target_language: str) -> list:
        prompt = RISK_ANNOTATION_PROMPT.format(
            source_text=source_text, translated_text=translated_text, target_language=language_descriptor(target_language)
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


pipeline = TranslationPipeline()
