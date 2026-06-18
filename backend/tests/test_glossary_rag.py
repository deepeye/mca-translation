import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.glossary_rag import retrieve_glossary_terms
from app.models.glossary import GlossaryEntry


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
