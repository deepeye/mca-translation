import json
import logging
import uuid
from datetime import datetime

from app.llm.bailian import bailian_client
from app.llm.prompts import DUAL_REVIEW_PROMPT, SINGLE_REVIEW_PROMPT
from app.schemas.review import ReviewCategory, ReviewIssue, ReviewResult
from app.constants.languages import language_descriptor
from app.services.review_han_guard import contains_han, strip_han

logger = logging.getLogger(__name__)


class ReviewService:
    """Generate review analysis for published translation content."""

    async def dual_review(
        self,
        source_text: str,
        translated_text: str,
        target_language: str,
        audience: str,
        cultural_sphere: str,
    ) -> ReviewResult:
        prompt = DUAL_REVIEW_PROMPT.format(
            source_text=source_text,
            translated_text=translated_text,
            target_language=language_descriptor(target_language),
            audience=audience,
            cultural_sphere=cultural_sphere,
        )
        return await self._call_llm(
            prompt, "dual", target_language, translated_text,
            f"{cultural_sphere}_{audience}"
        )

    async def single_review(
        self,
        translated_text: str,
        target_language: str,
        audience: str,
        cultural_sphere: str,
    ) -> ReviewResult:
        prompt = SINGLE_REVIEW_PROMPT.format(
            translated_text=translated_text,
            target_language=language_descriptor(target_language),
            audience=audience,
            cultural_sphere=cultural_sphere,
        )
        return await self._call_llm(
            prompt, "single", target_language, translated_text,
            f"{cultural_sphere}_{audience}"
        )

    async def _call_llm(
        self,
        prompt: str,
        mode: str,
        target_language: str,
        translated_text: str,
        audience_baseline: str,
    ) -> ReviewResult:
        messages = [{"role": "user", "content": prompt}]
        try:
            result = await bailian_client.chat(model="qwen-plus", messages=messages, temperature=0.1)
            content = result["content"].strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0]
            data = json.loads(content)

            categories = []
            for cat_data in data.get("categories", []):
                issues = []
                for issue_data in cat_data.get("issues", []):
                    span_raw = issue_data.get("span")
                    start = end = 0
                    if span_raw and isinstance(span_raw, dict):
                        start = span_raw.get("start", 0)
                        end = span_raw.get("end", 0)

                    # Clean target-language fields of Han characters as a safety net
                    cleaned_suggestion = strip_han(issue_data.get("suggestion", ""))
                    cleaned_original = strip_han(issue_data.get("original", ""))
                    cleaned_span_text = strip_han(span_raw.get("text", "")) if span_raw and isinstance(span_raw, dict) else ""

                    if not cleaned_suggestion:
                        logger.warning("Dropping review issue: suggestion is empty after Han stripping")
                        continue

                    if contains_han(cleaned_suggestion) or contains_han(cleaned_original) or contains_han(cleaned_span_text):
                        logger.warning("Dropping review issue: target-language fields still contain Han after stripping")
                        continue

                    # Fallback to span text if original is empty after stripping
                    if not cleaned_original:
                        cleaned_original = cleaned_span_text


                    issues.append(
                        ReviewIssue(
                            category=issue_data.get("category", "clarity"),
                            severity=issue_data.get("severity", "low"),
                            span={"start": start, "end": end, "text": cleaned_span_text} if span_raw and isinstance(span_raw, dict) else None,
                            original=cleaned_original,
                            suggestion=cleaned_suggestion,
                            explanation=issue_data.get("explanation", ""),
                            source_reference=issue_data.get("source_reference"),
                        )
                    )
                categories.append(
                    ReviewCategory(
                        name=cat_data.get("name", "未分类"),
                        score=min(100, max(0, int(cat_data.get("score", 0)))),
                        issue_count=len(issues),
                        issues=issues,
                    )
                )

            # Validate spans: clamp to translated_text length
            for cat in categories:
                for issue in cat.issues:
                    if issue.span:
                        issue.span["start"] = max(0, min(issue.span["start"], len(translated_text)))
                        issue.span["end"] = max(issue.span["start"], min(issue.span["end"], len(translated_text)))

            return ReviewResult(
                review_id=uuid.uuid4(),
                mode=mode,
                overall_score=min(100, max(0, int(data.get("overall_score", 0)))),
                translated_text=translated_text,
                target_language=target_language,
                audience_baseline=audience_baseline,
                categories=categories,
                summary=data.get("summary", ""),
                created_at=datetime.utcnow(),
            )
        except Exception as e:
            logger.warning(f"Review parsing failed: {e}")
            return ReviewResult(
                review_id=uuid.uuid4(),
                mode=mode,
                overall_score=0,
                translated_text=translated_text,
                target_language=target_language,
                audience_baseline=audience_baseline,
                categories=[],
                summary="审校分析失败，请重试。",
                created_at=datetime.utcnow(),
            )


review_service = ReviewService()
