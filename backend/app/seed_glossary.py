"""Seed the glossary_entries table from the hardcoded political glossary.

Usage:
    python -m app.seed_glossary                    # Dry-run (no write)
    python -m app.seed_glossary --apply             # Actually seed the DB
    python -m app.seed_glossary --apply --force     # Re-seed even existing terms

Requires DATABASE_URL and BAILIAN_API_KEY to be set.
"""

import argparse
import asyncio
import logging
import os
import sys

# Ensure backend/ is on sys.path when run as `python -m app.seed_glossary`
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.config import settings  # noqa: E402
from app.llm.bailian import bailian_client  # noqa: E402
from app.models.glossary import GlossaryEntry  # noqa: E402
from app.services.hardcoded_glossary import GlossaryTerm, _HARDCODED_TERMS  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger("seed_glossary")


def _map_translations(term: GlossaryTerm) -> dict:
    """Map hardcoded GlossaryTerm.translations (``rendering`` key) → DB format (``preferred`` key).

    The hardcoded terms use ``{"en-GB": {"rendering": "...", "alternatives": [...], "notes": "..."}}``
    while the DB stores ``{"en-GB": {"preferred": "...", "alternatives": [...], "notes": "..."}}``.

    The mapped result only includes languages that have a non-empty ``rendering``.
    """
    mapped: dict = {}
    for lang, entry in term.translations.items():
        rendering = entry.get("rendering", "")
        if not rendering:
            continue
        mapped[lang] = {
            "preferred": rendering,
            "alternatives": entry.get("alternatives", []),
            "notes": entry.get("notes", ""),
        }
    return mapped


def _prepare_entries() -> list[dict]:
    """Build a list of dicts ready for DB insert (one per hardcoded term).

    Returns entries sorted by ``source_term`` for deterministic ordering.
    """
    entries = []
    for term in _HARDCODED_TERMS:
        translations = _map_translations(term)
        if not translations:
            logger.warning("Skipping %s — no renderings found for any language", term.source_term)
            continue
        entries.append(
            {
                "source_term": term.source_term,
                "term_type": term.term_type,
                "translations": translations,
                "risk_notes": term.risk_notes,
                "applicable_genres": term.applicable_genres or [],
            }
        )
    entries.sort(key=lambda e: e["source_term"])
    return entries


async def _get_existing_source_terms(db_session_factory) -> set[str]:
    """Return the set of ``source_term`` values already present in glossary_entries."""
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession

    async with db_session_factory() as session:
        result = await session.execute(select(GlossaryEntry.source_term))
        return {row[0] for row in result.all()}


async def _embed_source_terms(
    entries: list[dict],
    session_factory,
    *,
    force: bool = False,
    dry_run: bool = False,
) -> list[dict]:
    """Generate embeddings for entries that need them.

    Bailian's ``text-embedding-v3`` accepts up to 6 texts per call.
    Returns entries with ``embedding`` populated.
    """
    existing = await _get_existing_source_terms(session_factory) if not dry_run else set()

    to_embed: list[dict] = []
    for entry in entries:
        if not force and entry["source_term"] in existing:
            logger.info("  ↺ 跳过（已存在）: %s", entry["source_term"])
            continue
        to_embed.append(entry)

    if not to_embed:
        logger.info("所有术语已在 DB 中，无需更新（使用 --force 可强制重新灌入）")
        return []

    # Bailian batch size
    batch_size = 6
    for i in range(0, len(to_embed), batch_size):
        batch = to_embed[i : i + batch_size]
        texts = [e["source_term"] for e in batch]
        try:
            embeddings = await bailian_client.embed(texts)
        except Exception as exc:
            logger.error("Embedding 调用失败 (batch %d): %s", i // batch_size, exc)
            # Continue without embeddings for this batch
            embeddings = [None] * len(batch)

        for entry, emb in zip(batch, embeddings):
            entry["embedding"] = emb

    return to_embed


async def _upsert_entries(
    entries: list[dict],
    session_factory,
    *,
    apply: bool = False,
    dry_run: bool = False,
) -> None:
    """Upsert entries into the glossary_entries table."""
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession

    async with session_factory() as session:
        for entry in entries:
            # Check if term already exists
            result = await session.execute(
                select(GlossaryEntry).where(GlossaryEntry.source_term == entry["source_term"])
            )
            existing = result.scalar_one_or_none()

            if existing:
                if not apply:
                    logger.info("  ~ 更新（dry-run）: %s", entry["source_term"])
                    continue
                # Update existing
                existing.term_type = entry["term_type"]
                existing.translations = entry["translations"]
                existing.risk_notes = entry["risk_notes"]
                existing.applicable_genres = entry["applicable_genres"]
                if entry.get("embedding"):
                    existing.embedding = entry["embedding"]
            else:
                if not apply:
                    logger.info("  + 新增（dry-run）: %s", entry["source_term"])
                    continue
                entry_obj = GlossaryEntry(
                    source_term=entry["source_term"],
                    term_type=entry["term_type"],
                    translations=entry["translations"],
                    risk_notes=entry["risk_notes"],
                    applicable_genres=entry["applicable_genres"],
                    embedding=entry.get("embedding"),
                )
                session.add(entry_obj)

        if apply:
            await session.commit()
            logger.info("已提交 %d 条变更至 glossary_entries 表", len(entries))
        else:
            logger.info("Dry-run 模式 — 未写入任何数据。使用 --apply 实际写入。")


async def _count_entries(session_factory) -> int:
    """Return the current row count of glossary_entries."""
    from sqlalchemy import func, select
    from sqlalchemy.ext.asyncio import AsyncSession

    async with session_factory() as session:
        result = await session.execute(select(func.count(GlossaryEntry.id)))
        return result.scalar() or 0


def _build_session_factory():
    """Build a disposable async session factory (same pattern as tasks.py)."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return session_factory, engine


async def main():
    parser = argparse.ArgumentParser(description="Seed glossary_entries from hardcoded political glossary")
    parser.add_argument("--apply", action="store_true", help="Actually write to the database")
    parser.add_argument("--force", action="store_true", help="Re-seed even existing terms")
    args = parser.parse_args()

    session_factory, engine = _build_session_factory()

    try:
        # Check pre-seed count
        count_before = await _count_entries(session_factory)
        logger.info("当前 glossary_entries 行数: %d", count_before)

        # Build entries from hardcoded terms
        entries = _prepare_entries()
        logger.info("从硬编码词典读取 %d 条术语", len(entries))

        # Generate embeddings (skip gracefully if no API key — keyword route still works)
        if settings.BAILIAN_API_KEY:
            to_seed = await _embed_source_terms(entries, session_factory, force=args.force, dry_run=not args.apply)
        else:
            logger.warning("BAILIAN_API_KEY 未设置，跳过 embedding 生成（关键字匹配依然可用）")
            existing = set() if args.force or not args.apply else await _get_existing_source_terms(session_factory)
            to_seed = [e for e in entries if args.force or e["source_term"] not in existing]
            for e in to_seed:
                e["embedding"] = None

        if not to_seed:
            logger.info("无事可做。退出。")
            return

        # Upsert
        await _upsert_entries(to_seed, session_factory, apply=args.apply, dry_run=not args.apply)

        if args.apply:
            count_after = await _count_entries(session_factory)
            logger.info("seed 完成。glossary_entries 行数: %d → %d", count_before, count_after)
        else:
            logger.info("使用 --apply 实际写入 %d 条", len(to_seed))

    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
