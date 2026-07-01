import asyncio
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.job import TranslationJob, TranslationResult
from app.models.user import User
from app.schemas.job import (
    AcceptAllRequest, AcceptRiskRequest, AcceptanceScoreDeltaRequest,
    AcceptanceScoreRequest, AcceptanceScoreResponse, CreateJobRequest,
    DismissRiskRequest, JobListItem, JobResponse, RevertRiskRequest,
    SuggestionResponse, TranslationResultResponse,
)
from app.services.acceptance_aggregator import aggregate
from app.services.acceptance_segmenter import segment
from app.services.acceptance_scorer import AcceptanceScorer
from app.services.decision_log import save_decision_logs
from app.services.risk_phrase_mapper import map_risk_phrases
from app.services.suggestion import suggestion_service
from app.tasks import run_translation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    body: CreateJobRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = TranslationJob(
        user_id=user.id,
        source_text=body.source_text,
        genre=body.genre,
        strategy=body.strategy,
        target_languages=body.target_languages,
        cultural_sphere=body.cultural_sphere,
        audience_type=body.audience_type,
        status="pending",
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Create empty result rows for each language
    for lang in body.target_languages:
        result = TranslationResult(job_id=job.id, language=lang, status="idle")
        db.add(result)
    await db.commit()

    # Dispatch Celery task
    run_translation.delay(str(job.id))

    # Reload with results
    results = (
        await db.execute(select(TranslationResult).where(TranslationResult.job_id == job.id))
    ).scalars().all()
    return _build_job_response(job, results)


@router.get("", response_model=list[JobListItem])
async def list_jobs(
    genre: str | None = Query(None),
    status: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(TranslationJob).where(TranslationJob.user_id == user.id)
    if genre:
        query = query.where(TranslationJob.genre == genre)
    if status:
        query = query.where(TranslationJob.status == status)
    query = query.order_by(TranslationJob.created_at.desc()).limit(50)
    result = await db.execute(query)
    jobs = result.scalars().all()
    return [
        JobListItem(
            id=j.id,
            status=j.status,
            genre=j.genre,
            target_languages=j.target_languages,
            source_text=j.source_text[:200] if j.source_text else None,
            created_at=j.created_at,
        )
        for j in jobs
    ]


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await _get_user_job(job_id, user, db)
    results = (
        await db.execute(select(TranslationResult).where(TranslationResult.job_id == job.id))
    ).scalars().all()
    return _build_job_response(job, results)


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await _get_user_job(job_id, user, db)
    results = (
        await db.execute(select(TranslationResult).where(TranslationResult.job_id == job.id))
    ).scalars().all()
    for r in results:
        await db.delete(r)
    await db.delete(job)
    await db.commit()


@router.get("/{job_id}/suggestions", response_model=SuggestionResponse)
async def get_suggestions(
    job_id: uuid.UUID,
    lang: str,
    risk_index: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await _get_user_job(job_id, user, db)
    result = await _get_lang_result(job.id, lang, db)
    annotations = result.risk_annotations or []
    if risk_index < 0 or risk_index >= len(annotations):
        raise HTTPException(status_code=400, detail="Invalid risk_index")
    ann = annotations[risk_index]
    suggestions = await suggestion_service.generate(
        source_text=job.source_text,
        translated_text=result.translated_text,
        target_language=lang,
        phrase=ann.get("phrase") or ann.get("span_text", ""),
        risk_type=ann.get("risk_type", ""),
        explanation=ann.get("explanation", ""),
    )

    # 决策提取：建议阶段 — 记录每个替换建议（尽力而为）
    if suggestions:
        suggestion_entries = [
            {
                "stage": "suggestion",
                "decision_type": "alternative_suggested",
                "source_phrase": ann.get("phrase"),
                "target_phrase": s.get("text"),
                "decision": f"建议替换为「{s.get('text', '')}」",
                "reasoning": s.get("reason", ""),
                "confidence": None,
                "metadata": {"risk_index": risk_index, "risk_type": ann.get("risk_type")},
            }
            for s in suggestions
        ]
        try:
            log_ids = await save_decision_logs(
                db, job_id=job.id, result_id=result.id, entries=suggestion_entries
            )
            existing = list(result.decision_log_ids or [])
            existing.extend(log_ids)
            result.decision_log_ids = existing
            await db.commit()
        except Exception as e:
            logger.warning(f"Suggestion decision log save failed: {e}")

    return SuggestionResponse(suggestions=suggestions)


@router.post("/{job_id}/risks/{risk_index}/accept")
async def accept_risk(
    job_id: uuid.UUID,
    risk_index: int,
    body: AcceptRiskRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await _get_user_job(job_id, user, db)
    result = await _get_lang_result(job.id, body.lang, db)
    annotations = result.risk_annotations or []
    if risk_index < 0 or risk_index >= len(annotations):
        raise HTTPException(status_code=400, detail="Invalid risk_index")
    ann = annotations[risk_index]
    if ann.get("status", "open") != "open":
        raise HTTPException(status_code=400, detail="Risk is not in open state")

    offset = ann.get("offset")
    text = result.translated_text or ""
    if offset is not None and offset >= 0 and text[offset:offset + len(ann["phrase"])] == ann["phrase"]:
        text = text[:offset] + body.suggestion + text[offset + len(ann["phrase"]):]
    else:
        text = text.replace(ann["phrase"], body.suggestion, 1)

    ann["status"] = "accepted"
    ann["accepted_suggestion"] = body.suggestion
    result.translated_text = text
    result.risk_annotations = _recalculate_offsets(text, annotations)
    flag_modified(result, "risk_annotations")
    await db.commit()
    await db.refresh(result)
    return _build_job_response(job, [result])


@router.post("/{job_id}/risks/{risk_index}/dismiss")
async def dismiss_risk(
    job_id: uuid.UUID,
    risk_index: int,
    body: DismissRiskRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await _get_user_job(job_id, user, db)
    result = await _get_lang_result(job.id, body.lang, db)
    annotations = result.risk_annotations or []
    if risk_index < 0 or risk_index >= len(annotations):
        raise HTTPException(status_code=400, detail="Invalid risk_index")
    # Toggle: if already dismissed, restore to open (undo dismiss)
    current_status = annotations[risk_index].get("status", "open")
    annotations[risk_index]["status"] = "dismissed" if current_status != "dismissed" else "open"
    result.risk_annotations = annotations
    flag_modified(result, "risk_annotations")
    await db.commit()
    await db.refresh(result)
    return _build_job_response(job, [result])


@router.post("/{job_id}/risks/{risk_index}/revert")
async def revert_risk(
    job_id: uuid.UUID,
    risk_index: int,
    body: RevertRiskRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await _get_user_job(job_id, user, db)
    result = await _get_lang_result(job.id, body.lang, db)
    annotations = result.risk_annotations or []
    if risk_index < 0 or risk_index >= len(annotations):
        raise HTTPException(status_code=400, detail="Invalid risk_index")
    ann = annotations[risk_index]
    if ann.get("status") != "accepted":
        raise HTTPException(status_code=400, detail="Risk is not in accepted state")

    suggestion = ann["accepted_suggestion"]
    phrase = ann["phrase"]
    text = result.translated_text or ""
    text = text.replace(suggestion, phrase, 1)

    ann["status"] = "open"
    del ann["accepted_suggestion"]
    result.translated_text = text
    result.risk_annotations = _recalculate_offsets(text, annotations)
    flag_modified(result, "risk_annotations")
    await db.commit()
    await db.refresh(result)
    return _build_job_response(job, [result])


_accept_all_locks: dict[str, asyncio.Lock] = {}


@router.post("/{job_id}/risks/accept-all")
async def accept_all_risks(
    job_id: uuid.UUID,
    body: AcceptAllRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    lock_key = f"{job_id}:{body.lang}"
    if lock_key not in _accept_all_locks:
        _accept_all_locks[lock_key] = asyncio.Lock()
    if _accept_all_locks[lock_key].locked():
        raise HTTPException(status_code=409, detail="Batch processing in progress")

    async with _accept_all_locks[lock_key]:
        job = await _get_user_job(job_id, user, db)
        result = await _get_lang_result(job.id, body.lang, db)
        annotations = result.risk_annotations or []
        skipped = []

        for i, ann in enumerate(annotations):
            if ann.get("status", "open") != "open":
                continue
            suggestions = await suggestion_service.generate(
                source_text=job.source_text,
                translated_text=result.translated_text,
                target_language=body.lang,
                phrase=ann["phrase"],
                risk_type=ann.get("risk_type", ""),
                explanation=ann.get("explanation", ""),
            )
            if not suggestions:
                skipped.append(i)
                continue

            suggestion = suggestions[0]["text"]
            offset = ann.get("offset")
            text = result.translated_text or ""
            if offset is not None and offset >= 0 and text[offset:offset + len(ann["phrase"])] == ann["phrase"]:
                text = text[:offset] + suggestion + text[offset + len(ann["phrase"]):]
            else:
                text = text.replace(ann["phrase"], suggestion, 1)

            ann["status"] = "accepted"
            ann["accepted_suggestion"] = suggestion
            result.translated_text = text
            result.risk_annotations = _recalculate_offsets(text, annotations)
            flag_modified(result, "risk_annotations")

        await db.commit()
        await db.refresh(result)

    response = _build_job_response(job, [result])
    if skipped:
        response["skipped_risk_indices"] = skipped
    return response


async def _get_user_job(job_id: uuid.UUID, user: User, db: AsyncSession) -> TranslationJob:
    job = (
        await db.execute(
            select(TranslationJob).where(
                TranslationJob.id == job_id,
                TranslationJob.user_id == user.id,
            )
        )
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


async def _get_lang_result(job_id: uuid.UUID, lang: str, db: AsyncSession) -> TranslationResult:
    result = (
        await db.execute(
            select(TranslationResult).where(
                TranslationResult.job_id == job_id,
                TranslationResult.language == lang,
            )
        )
    ).scalar_one_or_none()
    if result is None:
        raise HTTPException(status_code=404, detail="Translation result not found")
    return result


# 接受度评分器单例（llm_client=None → 运行时惰性取模块全局 bailian_client，便于测试 monkeypatch）
_acceptance_scorer = AcceptanceScorer()


async def _run_acceptance_scoring(
    result: TranslationResult,
    audience_baseline: str,
    db: AsyncSession,
    job_id: uuid.UUID,
    genre: str = "",
    cultural_sphere: str = "",
) -> dict:
    """编排：切句 → 逐句评分 → 映射 → 聚合 → 写 DB + decision_log。"""
    text = result.translated_text or ""
    lang = result.language
    sents = segment(text, lang)
    sent_index = {s.id: s for s in sents}

    # 逐句并发评分（scorer 内部信号量节流；gather 保持与 sents 同序）
    async def _score_one(s):
        ss = await _acceptance_scorer.score_sentence(
            s.text, lang, audience_baseline,
            genre=genre, cultural_sphere=cultural_sphere,
        )
        ss.sentence_id = s.id  # 回填 id
        return ss

    sentence_scores = await asyncio.gather(*[_score_one(s) for s in sents])

    risk_annotations = result.risk_annotations or []
    mapped = map_risk_phrases(sentence_scores, sent_index, risk_annotations)
    agg = aggregate(sentence_scores, risk_annotations)

    # 写回 TranslationResult
    result.acceptance_score = agg["total_score"]
    result.audience_baseline = audience_baseline
    result.acceptance_confidence = agg["confidence"]
    result.acceptance_dimensions = agg["dimensions"]
    result.acceptance_sentence_scores = [s.model_dump() for s in sentence_scores]
    flag_modified(result, "acceptance_dimensions")
    flag_modified(result, "acceptance_sentence_scores")

    # 写 decision_log（阶段=acceptance）
    entries = [{
        "stage": "acceptance",
        "decision_type": "acceptance_scoring",
        "decision": f"接受度评分 {agg['total_score']}/100（受众基准 {audience_baseline}）",
        "reasoning": " | ".join(s.rationale for s in sentence_scores if s.rationale),
        "confidence": "low" if agg["confidence"] < 0.7 else "high",
        "metadata": {
            "audience_baseline": audience_baseline,
            "total_score": agg["total_score"],
            "dimensions": agg["dimensions"],
            "unmapped_phrases": mapped["unmapped_phrases"],
            "trigger": "initial",
        },
    }]
    log_ids = await save_decision_logs(db, job_id, result.id, entries)
    if result.decision_log_ids is None:
        result.decision_log_ids = []
    result.decision_log_ids.extend(log_ids)
    flag_modified(result, "decision_log_ids")
    await db.commit()
    await db.refresh(result)

    return {
        "total_score": agg["total_score"],
        "dimensions": agg["dimensions"],
        "confidence": agg["confidence"],
        "top3_risk_indices": mapped["top3_risk_indices"],
        "audience_baseline": audience_baseline,
    }


def _recalculate_offsets(text: str, annotations: list[dict]) -> list[dict]:
    """Recalculate offsets for all open risk annotations after text change."""
    used_offsets = set()
    for ann in annotations:
        if ann.get("status", "open") != "open":
            continue
        offset = text.find(ann["phrase"])
        if offset == -1 or offset in used_offsets:
            offset = -1
        else:
            used_offsets.add(offset)
        ann["offset"] = offset
    return annotations


def _build_job_response(job: TranslationJob, results: list[TranslationResult]) -> JobResponse:
    return JobResponse(
        id=job.id,
        status=job.status,
        source_text=job.source_text,
        genre=job.genre,
        strategy=job.strategy,
        target_languages=job.target_languages,
        results=[
            TranslationResultResponse(
                id=r.id,
                language=r.language,
                status=r.status,
                translated_text=r.translated_text,
                acceptance_score=r.acceptance_score,
                risk_annotations=r.risk_annotations,
                cultural_adaptation=r.cultural_adaptation,
                created_at=r.created_at,
            )
            for r in results
        ],
        created_at=job.created_at,
    )


@router.post("/{job_id}/acceptance-score", response_model=AcceptanceScoreResponse)
async def score_acceptance(
    job_id: uuid.UUID,
    body: AcceptanceScoreRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """首次接受度评分（转译完成后调用）。"""
    job = await _get_user_job(job_id, user, db)
    result = await _get_lang_result(job.id, body.lang, db)
    if not result.translated_text:
        raise HTTPException(status_code=400, detail="Translation not ready")
    return await _run_acceptance_scoring(
        result, body.audience_baseline, db, job.id,
        genre=job.genre, cultural_sphere=job.cultural_sphere or "",
    )


async def _run_acceptance_delta(
    result: TranslationResult,
    sentence_id: str,
    new_text: str,
    db: AsyncSession,
    job_id: uuid.UUID,
    genre: str = "",
    cultural_sphere: str = "",
) -> dict:
    """delta 重算：仅重算指定句（单次采样）+ 受影响邻接句，再聚合缓存。"""
    cached = result.acceptance_sentence_scores or []
    if not cached:
        raise HTTPException(status_code=400, detail="No cached sentence scores; run initial scoring first")

    # 重建 SentenceScore 列表（从缓存反序列化）
    from app.schemas.acceptance import SentenceScore, DimensionScores
    scores = [SentenceScore(**c) for c in cached]
    by_id = {s.sentence_id: s for s in scores}
    if sentence_id not in by_id:
        raise HTTPException(status_code=400, detail=f"Unknown sentence_id {sentence_id}")

    audience = result.audience_baseline or "policy_media"
    lang = result.language

    # 重算目标句
    new_ss = await _acceptance_scorer.score_sentence_single(
        new_text, lang, audience, genre=genre, cultural_sphere=cultural_sphere)
    new_ss.sentence_id = sentence_id
    by_id[sentence_id] = new_ss

    # 邻接句：若目标句 affects_neighbors，重算前后句（重切全文以拿邻接句文本）
    if new_ss.affects_neighbors:
        idx = next(i for i, s in enumerate(scores) if s.sentence_id == sentence_id)
        sents = segment(result.translated_text or "", lang)
        sent_by_id = {s.id: s for s in sents}
        for neighbor_idx in (idx - 1, idx + 1):
            if 0 <= neighbor_idx < len(scores):
                nsid = scores[neighbor_idx].sentence_id
                sent = sent_by_id.get(nsid)
                if sent:
                    nss = await _acceptance_scorer.score_sentence_single(
                        sent.text, lang, audience, genre=genre, cultural_sphere=cultural_sphere)
                    nss.sentence_id = nsid
                    by_id[nsid] = nss

    new_scores = [by_id[s.sentence_id] for s in scores]
    risk_annotations = result.risk_annotations or []
    agg = aggregate(new_scores, risk_annotations)

    # 写回
    result.acceptance_score = agg["total_score"]
    result.acceptance_confidence = agg["confidence"]
    result.acceptance_dimensions = agg["dimensions"]
    result.acceptance_sentence_scores = [s.model_dump() for s in new_scores]
    flag_modified(result, "acceptance_dimensions")
    flag_modified(result, "acceptance_sentence_scores")

    affected_ids = [sentence_id]
    entries = [{
        "stage": "acceptance",
        "decision_type": "acceptance_delta",
        "decision": f"delta 重算：句 {sentence_id} → {new_ss.score}",
        "reasoning": new_ss.rationale,
        "confidence": "low" if agg["confidence"] < 0.7 else "high",
        "metadata": {
            "trigger": "sentence_replace",
            "affected_sentence_ids": affected_ids,
            "total_score": agg["total_score"],
        },
    }]
    log_ids = await save_decision_logs(db, job_id, result.id, entries)
    if result.decision_log_ids is None:
        result.decision_log_ids = []
    result.decision_log_ids.extend(log_ids)
    flag_modified(result, "decision_log_ids")
    await db.commit()
    await db.refresh(result)

    # top3 only；delta 后句内 offsets 已失效，传空 sentence_index 仅取 top3
    mapped = map_risk_phrases(new_scores, {}, risk_annotations)
    return {
        "total_score": agg["total_score"],
        "dimensions": agg["dimensions"],
        "confidence": agg["confidence"],
        "top3_risk_indices": mapped["top3_risk_indices"],
        "audience_baseline": audience,
    }


@router.post("/{job_id}/acceptance-score/delta", response_model=AcceptanceScoreResponse)
async def score_acceptance_delta(
    job_id: uuid.UUID,
    body: AcceptanceScoreDeltaRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """替换风险词后句级 delta 重算（<1s 目标）。"""
    job = await _get_user_job(job_id, user, db)
    result = await _get_lang_result(job.id, body.lang, db)
    return await _run_acceptance_delta(
        result, body.sentence_id, body.new_text, db, job.id,
        genre=job.genre, cultural_sphere=job.cultural_sphere or "",
    )
