import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.glossary import GlossaryEntry, UserGlossaryEntry
from app.llm.bailian import bailian_client


async def retrieve_glossary_terms(
    db: AsyncSession,
    user_id: uuid.UUID,
    source_text: str,
    language: str,
    genre: str | None = None,
    top_k: int = 5,
) -> list[dict]:
    """Dual-route retrieval: keyword exact match + vector semantic similarity.

    Priority: user glossary > system glossary. Deduplicate by source_term.
    """
    results = []
    seen_terms = set()

    # Route A: Keyword exact match (substring search)
    # User glossary keyword match
    user_stmt = select(UserGlossaryEntry).where(UserGlossaryEntry.user_id == user_id)
    user_rows = (await db.execute(user_stmt)).scalars().all()
    for row in user_rows:
        if row.source_term in source_text:
            if row.source_term not in seen_terms:
                seen_terms.add(row.source_term)
                results.append(_to_result_dict(row, "user_glossary", score=1.0))

    # System glossary keyword match
    system_stmt = select(GlossaryEntry)
    system_rows = (await db.execute(system_stmt)).scalars().all()
    for row in system_rows:
        if row.source_term in source_text:
            if row.source_term not in seen_terms:
                seen_terms.add(row.source_term)
                results.append(_to_result_dict(row, "system_kb", score=1.0))

    # Route B: Vector semantic similarity (for terms not substring-matched)
    if len(results) < top_k:
        embeddings = await bailian_client.embed([source_text])
        query_vec = embeddings[0] if embeddings else None
        if query_vec:
            remaining = top_k - len(results)

            # User glossary vector search
            user_vec_stmt = (
                select(UserGlossaryEntry)
                .where(UserGlossaryEntry.user_id == user_id)
                .where(UserGlossaryEntry.embedding.is_not(None))
                .order_by(UserGlossaryEntry.embedding.l2_distance(query_vec))
                .limit(remaining)
            )
            user_vec_rows = (await db.execute(user_vec_stmt)).scalars().all()
            for row in user_vec_rows:
                if row.source_term not in seen_terms:
                    seen_terms.add(row.source_term)
                    dist = await _l2_distance(db, "user_glossary_entries", row.id, query_vec)
                    score = 1.0 / (1.0 + dist) if dist is not None else 0.5
                    results.append(_to_result_dict(row, "user_glossary", score=score))

            # System glossary vector search (fill remaining slots)
            remaining = top_k - len(results)
            if remaining > 0:
                sys_vec_stmt = (
                    select(GlossaryEntry)
                    .where(GlossaryEntry.embedding.is_not(None))
                    .order_by(GlossaryEntry.embedding.l2_distance(query_vec))
                    .limit(remaining)
                )
                sys_vec_rows = (await db.execute(sys_vec_stmt)).scalars().all()
                for row in sys_vec_rows:
                    if row.source_term not in seen_terms:
                        seen_terms.add(row.source_term)
                        dist = await _l2_distance(db, "glossary_entries", row.id, query_vec)
                        score = 1.0 / (1.0 + dist) if dist is not None else 0.5
                        results.append(_to_result_dict(row, "system_kb", score=score))

    # Genre filtering (post-retrieval)
    if genre:
        results = [r for r in results if not r.get("applicable_genres") or genre in r["applicable_genres"]]

    # Sort by score desc, limit to top_k
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]


def _to_result_dict(row, source: str, score: float) -> dict:
    return {
        "id": row.id,
        "source_term": row.source_term,
        "term_type": row.term_type,
        "translations": row.translations,
        "risk_notes": row.risk_notes or "",
        "applicable_genres": row.applicable_genres or [],
        "score": round(score, 4),
        "source": source,
    }


async def _l2_distance(db: AsyncSession, table: str, row_id: uuid.UUID, query_vec: list[float]) -> float | None:
    """Get L2 distance for a specific row."""
    vec_str = "[" + ",".join(str(v) for v in query_vec) + "]"
    sql = text(f"SELECT embedding <-> :vec FROM {table} WHERE id = :id")
    result = await db.execute(sql, {"vec": vec_str, "id": str(row_id)})
    row = result.scalar_one_or_none()
    return float(row) if row is not None else None
