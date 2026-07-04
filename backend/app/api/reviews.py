from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.review import ReviewRequest, ReviewResult
from app.services.credits import credits_service, DeductResult
from app.services.review import review_service

router = APIRouter(prefix="/api/reviews", tags=["reviews"])


@router.post("", response_model=ReviewResult, status_code=status.HTTP_200_OK)
async def create_review(
    body: ReviewRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # 余额守卫
    if user.credit_balance <= 0:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=402,
            content={"detail": "INSUFFICIENT_CREDITS", "balance": 0},
        )

    # 预先生成 review_id，作为幂等键；扣款发生在 LLM 成功之后
    import uuid as _uuid
    review_id = _uuid.uuid4()
    # 计算扣款长度：dual 用 source_text，single 用 translated_text
    input_text = body.source_text if body.mode == "dual" else body.translated_text
    cost = len(input_text or "")

    if body.mode == "dual":
        if not body.source_text:
            raise HTTPException(status_code=400, detail="对照审校模式需要提供原文")
        try:
            result = await review_service.dual_review(
                source_text=body.source_text,
                translated_text=body.translated_text,
                target_language=body.target_language,
                audience=body.audience_type or "general_public",
                cultural_sphere=body.cultural_sphere or "western_english",
            )
        except Exception:
            # LLM 失败：尚未扣款，无需退还
            raise HTTPException(status_code=500, detail="审校服务暂时不可用")
    else:
        try:
            result = await review_service.single_review(
                translated_text=body.translated_text,
                target_language=body.target_language,
                audience=body.audience_type or "general_public",
                cultural_sphere=body.cultural_sphere or "western_english",
            )
        except Exception:
            raise HTTPException(status_code=500, detail="审校服务暂时不可用")

    # 成功后扣款；用预生成的 review_id 保证幂等
    result.review_id = review_id
    deduct_res, _ = await credits_service.deduct_for_review(
        db, user.id, cost, review_id, body.mode
    )
    if deduct_res is DeductResult.INSUFFICIENT:
        # 极少情况：提交时余额>0 但扣款时已不足 → 退还语义上等价于未扣款
        raise HTTPException(status_code=402, detail="INSUFFICIENT_CREDITS")
    return result
