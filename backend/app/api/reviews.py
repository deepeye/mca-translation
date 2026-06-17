from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.review import ReviewRequest, ReviewResult
from app.services.review import review_service

router = APIRouter(prefix="/api/reviews", tags=["reviews"])


@router.post("", response_model=ReviewResult, status_code=status.HTTP_200_OK)
async def create_review(
    body: ReviewRequest,
    user: User = Depends(get_current_user),
):
    if body.mode == "dual":
        if not body.source_text:
            raise HTTPException(status_code=400, detail="对照审校模式需要提供原文")
        return await review_service.dual_review(
            source_text=body.source_text,
            translated_text=body.translated_text,
            target_language=body.target_language,
            audience=body.audience_type or "general_public",
            cultural_sphere=body.cultural_sphere or "western_english",
        )
    else:
        return await review_service.single_review(
            translated_text=body.translated_text,
            target_language=body.target_language,
            audience=body.audience_type or "general_public",
            cultural_sphere=body.cultural_sphere or "western_english",
        )
