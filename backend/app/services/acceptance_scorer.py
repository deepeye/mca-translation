# backend/app/services/acceptance_scorer.py
"""接受度评分器：LLM-Judge + 3 次采样取中位数 + schema 校验。

对单句调用 LLM，3 次采样（T=0.3）取每维中位数，方差大则 confidence 低。
delta 重算走单次采样。所有 LLM 调用经信号量节流。
"""

import asyncio
import json
import logging
import statistics

from app.core.config import settings
from app.llm.bailian import bailian_client
from app.llm.prompts import ACCEPTANCE_SCORE_PROMPT
from app.schemas.acceptance import DimensionScores, SentenceScore

logger = logging.getLogger(__name__)

_DIM_KEYS = ("audience", "cultural", "naturalness", "risk")
_SINGLE_SAMPLE_CONFIDENCE = 0.5


class AcceptanceScorer:
    def __init__(self, llm_client=None, semaphore_limit: int = 5):
        # llm_client=None → 运行时从模块全局 bailian_client 取（便于测试 monkeypatch）
        self._client = llm_client
        self._sem = asyncio.Semaphore(semaphore_limit)

    async def score_sentence(
        self,
        sentence_text: str,
        lang: str,
        audience_baseline: str,
        genre: str = "",
        cultural_sphere: str = "",
        n_samples: int = 3,
    ) -> SentenceScore:
        # 并发采样
        samples = await asyncio.gather(*[
            self._one_sample(sentence_text, lang, audience_baseline, genre, cultural_sphere)
            for _ in range(n_samples)
        ])
        valid = [s for s in samples if s is not None]
        if not valid:
            return SentenceScore(
                sentence_id="",  # 调用方在编排时回填
                dimensions=DimensionScores(audience=0, cultural=0, naturalness=0, risk=0),
                confidence=0.0,
                failed=True,
                rationale="该句评分失败：3 次采样均不合规",
            )

        # 每维中位数
        dim_medians = {}
        for k in _DIM_KEYS:
            vals = [getattr(s["dims"], k) for s in valid]
            dim_medians[k] = statistics.median(vals)

        # 置信度：基于各样本总分 range
        totals = [sum(getattr(s["dims"], k) for k in _DIM_KEYS) for s in valid]
        rng = max(totals) - min(totals)
        confidence = max(0.0, 1.0 - rng / 20.0)

        # 取最接近中位数总分的样本作为 rationale / offsets / affects_neighbors 来源
        median_total = statistics.median(totals)
        representative = min(valid, key=lambda s: abs(sum(getattr(s["dims"], k) for k in _DIM_KEYS) - median_total))

        # affects_neighbors 多数表决
        neighbor_votes = [s["affects_neighbors"] for s in valid]
        affects_neighbors = sum(neighbor_votes) > len(neighbor_votes) / 2

        dims = DimensionScores(**dim_medians)
        return SentenceScore(
            sentence_id="",  # 编排时回填
            dimensions=dims,
            confidence=confidence,
            risk_phrase_offsets=representative["offsets"],
            affects_neighbors=affects_neighbors,
            rationale=representative["rationale"],
        )

    async def score_sentence_single(
        self,
        sentence_text: str,
        lang: str,
        audience_baseline: str,
        genre: str = "",
        cultural_sphere: str = "",
    ) -> SentenceScore:
        s = await self._one_sample(sentence_text, lang, audience_baseline, genre, cultural_sphere)
        if s is None:
            return SentenceScore(
                sentence_id="",
                dimensions=DimensionScores(audience=0, cultural=0, naturalness=0, risk=0),
                confidence=0.0,
                failed=True,
                rationale="该句评分失败：采样不合规",
            )
        return SentenceScore(
            sentence_id="",
            dimensions=s["dims"],
            confidence=_SINGLE_SAMPLE_CONFIDENCE,
            risk_phrase_offsets=s["offsets"],
            affects_neighbors=s["affects_neighbors"],
            rationale=s["rationale"],
        )

    async def _one_sample(self, sentence_text, lang, audience_baseline, genre, cultural_sphere):
        prompt = ACCEPTANCE_SCORE_PROMPT.format(
            target_language=lang,
            audience_baseline=audience_baseline,
            genre=genre or "未指定",
            cultural_sphere=cultural_sphere or "未指定",
            sentence_text=sentence_text,
        )
        async with self._sem:
            client = self._client if self._client is not None else bailian_client
            try:
                result = await client.chat(
                    model=settings.BAILIAN_MODEL_PLUS,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                )
            except Exception as e:
                logger.warning("acceptance scoring LLM call failed: %s", e)
                return None

        content = (result.get("content") or "").strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0]
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            # 重试 1 次（schema 不合规重试）
            async with self._sem:
                try:
                    result = await client.chat(
                        model=settings.BAILIAN_MODEL_PLUS,
                        messages=[{"role": "user", "content": prompt + "\n\n上次输出格式错误，请严格按 JSON schema 输出。"}],
                        temperature=0.3,
                    )
                except Exception:
                    return None
            content = (result.get("content") or "").strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0]
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                return None

        try:
            dims = DimensionScores(
                audience=float(data["audience"]),
                cultural=float(data["cultural"]),
                naturalness=float(data["naturalness"]),
                risk=float(data["risk"]),
            )
        except (KeyError, ValueError, TypeError):
            return None

        offsets = [(int(s), int(e)) for s, e in data.get("risk_phrase_offsets", [])]
        return {
            "dims": dims,
            "offsets": offsets,
            "affects_neighbors": bool(data.get("affects_neighbors", False)),
            "rationale": str(data.get("rationale", "")),
        }
