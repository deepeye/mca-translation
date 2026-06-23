import argparse
import asyncio
import os
import sys
from collections import Counter

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import select, update

from app.constants.glossary_categories import LEGACY_SYSTEM_GLOSSARY_TERM_TYPES
from app.core.database import async_session
from app.models.glossary import GlossaryEntry
from app.services.glossary_classification import classify_system_glossary_term


async def main(apply: bool, limit: int | None, sample: int, rewrite_all: bool):
    async with async_session() as db:
        stmt = select(GlossaryEntry.id, GlossaryEntry.source_term, GlossaryEntry.term_type, GlossaryEntry.translations)
        if not rewrite_all:
            stmt = stmt.where(GlossaryEntry.term_type.in_(LEGACY_SYSTEM_GLOSSARY_TERM_TYPES))
        if limit is not None:
            stmt = stmt.limit(limit)
        rows = (await db.execute(stmt)).all()

        counts = Counter()
        changes: list[tuple[str, str, str]] = []
        for row in rows:
            preferred_translation = (row.translations or {}).get("en-GB", {}).get("preferred", "")
            new_type = classify_system_glossary_term(row.source_term, preferred_translation)
            counts[new_type] += 1
            if row.term_type != new_type:
                changes.append((row.source_term, row.term_type, new_type))
                if apply:
                    await db.execute(
                        update(GlossaryEntry)
                        .where(GlossaryEntry.id == row.id)
                        .values(term_type=new_type)
                    )

        print(f"Scanned: {len(rows)}")
        print(f"Would change: {len(changes)}")
        print("Counts:")
        for key, value in sorted(counts.items()):
            print(f"  {key}: {value}")

        if sample > 0:
            print("Sample changes:")
            for source_term, old_type, new_type in changes[:sample]:
                print(f"  {source_term} :: {old_type} -> {new_type}")

        if apply:
            await db.commit()
            print("Applied changes")
        else:
            print("Dry run only")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--sample", type=int, default=20)
    args = parser.parse_args()
    asyncio.run(main(apply=args.apply, limit=args.limit, sample=args.sample, rewrite_all=args.all))
