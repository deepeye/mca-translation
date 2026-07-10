import json
from unittest.mock import AsyncMock, patch
import pytest
from app.services.review import ReviewService


@pytest.mark.asyncio
async def test_review_service_strips_cjk_from_suggestion():
    raw_response = {
        "content": json.dumps({
            "overall_score": 80,
            "summary": "简要",
            "categories": [
                {
                    "name": "术语准确性",
                    "score": 75,
                    "issues": [
                        {
                            "category": "terminology",
                            "severity": "medium",
                            "span": {"start": 0, "end": 10, "text": "侥幸心理"},
                            "original": "侥幸心理",
                            "suggestion": "侥幸 psychology",
                            "explanation": "不对",
                            "source_reference": "侥幸心理",
                        }
                    ],
                }
            ],
        })
    }
    service = ReviewService()
    with patch("app.services.review.bailian_client") as mock_client:
        mock_client.chat = AsyncMock(return_value=raw_response)
        result = await service.dual_review(
            source_text="坚决克服麻痹思想和侥幸心理",
            translated_text="resolutely overcome complacency and lucky psychology",
            target_language="en",
            audience="general_public",
            cultural_sphere="western_english",
        )
    assert len(result.categories) == 1
    issue = result.categories[0].issues[0]
    assert issue.suggestion == "psychology"
    assert issue.original == ""
    assert issue.span["text"] == ""


@pytest.mark.asyncio
async def test_review_service_drops_issue_when_suggestion_empty_after_stripping():
    raw_response = {
        "content": json.dumps({
            "overall_score": 80,
            "summary": "简要",
            "categories": [
                {
                    "name": "术语准确性",
                    "score": 75,
                    "issues": [
                        {
                            "category": "terminology",
                            "severity": "medium",
                            "span": {"start": 0, "end": 10, "text": "侥幸心理"},
                            "original": "侥幸心理",
                            "suggestion": "侥幸心理",
                            "explanation": "不对",
                            "source_reference": "侥幸心理",
                        }
                    ],
                }
            ],
        })
    }
    service = ReviewService()
    with patch("app.services.review.bailian_client") as mock_client:
        mock_client.chat = AsyncMock(return_value=raw_response)
        result = await service.dual_review(
            source_text="坚决克服麻痹思想和侥幸心理",
            translated_text="resolutely overcome complacency and lucky psychology",
            target_language="en",
            audience="general_public",
            cultural_sphere="western_english",
        )
    assert len(result.categories) == 1
    assert result.categories[0].issue_count == 0


@pytest.mark.asyncio
async def test_review_service_falls_back_original_to_span_text_when_original_empty():
    raw_response = {
        "content": json.dumps({
            "overall_score": 80,
            "summary": "简要",
            "categories": [
                {
                    "name": "术语准确性",
                    "score": 75,
                    "issues": [
                        {
                            "category": "terminology",
                            "severity": "medium",
                            "span": {"start": 0, "end": 10, "text": "lucky psychology"},
                            "original": "侥幸心理",
                            "suggestion": "great psychology",
                            "explanation": "不对",
                            "source_reference": "侥幸心理",
                        }
                    ],
                }
            ],
        })
    }
    service = ReviewService()
    with patch("app.services.review.bailian_client") as mock_client:
        mock_client.chat = AsyncMock(return_value=raw_response)
        result = await service.dual_review(
            source_text="坚决克服麻痹思想和侥幸心理",
            translated_text="resolutely overcome complacency and lucky psychology",
            target_language="en",
            audience="general_public",
            cultural_sphere="western_english",
        )
    assert len(result.categories) == 1
    issue = result.categories[0].issues[0]
    assert issue.suggestion == "great psychology"
    assert issue.original == "lucky psychology"
    assert issue.span["text"] == "lucky psychology"
