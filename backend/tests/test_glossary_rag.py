import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.glossary_rag import retrieve_glossary_terms
from app.models.glossary import GlossaryEntry
from app.constants.languages import SUPPORTED_LANGUAGES, get_language


@pytest.mark.asyncio
async def test_retrieve_keyword_match(db: AsyncSession):
    """Test that substring keyword match finds terms."""
    entry = GlossaryEntry(
        source_term="五位一体",
        term_type="political_discourse",
        translations={"en-GB": {"preferred": "Five-sphere", "alternatives": [], "notes": ""}},
        embedding=None,
    )
    db.add(entry)
    await db.commit()

    # Mock the embed call so we don't need a real API key
    with patch(
        "app.services.glossary_rag.bailian_client.embed",
        new_callable=AsyncMock,
        return_value=[[0.0] * 1024],
    ):
        results = await retrieve_glossary_terms(
            db=db,
            user_id=uuid.UUID("00000000-0000-0000-0000-000000000000"),
            source_text="我们推进五位一体总体布局",
            language="en-GB",
        )

    terms = [r["source_term"] for r in results]
    assert "五位一体" in terms


@pytest.mark.asyncio
async def test_retrieve_with_all_18_languages(db: AsyncSession):
    """Regression guard: 18-language translations dict should not break keyword or vector retrieval."""
    # Clean up any stale entries from previous tests
    await db.execute(delete(GlossaryEntry))
    await db.commit()

    all_translations = {
        lang.code: {"preferred": "translation", "alternatives": [], "notes": ""}
        for lang in SUPPORTED_LANGUAGES
    }
    entry = GlossaryEntry(
        source_term="一带一路",
        term_type="political_discourse",
        translations=all_translations,
        embedding=None,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)

    # Verify all 18 languages persisted
    assert len(entry.translations) == 18, f"got {len(entry.translations)} keys"
    for lang in SUPPORTED_LANGUAGES:
        assert lang.code in entry.translations, f"missing {lang.code} after refresh"

    with patch(
        "app.services.glossary_rag.bailian_client.embed",
        new_callable=AsyncMock,
        return_value=[[0.0] * 1024],
    ):
        results = await retrieve_glossary_terms(
            db=db,
            user_id=uuid.UUID("00000000-0000-0000-0000-000000000000"),
            source_text="我们推动一带一路建设",
            language="ar",
        )

    assert len(results) > 0
    # Verify the target-language preferred translation is present
    term = next(r for r in results if r["source_term"] == "一带一路")
    assert "ar" in term["translations"]
    assert term["translations"]["ar"]["preferred"] == "translation"
