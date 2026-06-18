import os
import pytest
from app.llm.bailian import bailian_client


@pytest.mark.asyncio
async def test_embed_dimensions():
    """Test that embedding API returns 1024-dim vectors."""
    if not os.getenv("BAILIAN_API_KEY"):
        pytest.skip("BAILIAN_API_KEY not set")

    embeddings = await bailian_client.embed(["五位一体", "common prosperity"])
    assert len(embeddings) == 2
    assert len(embeddings[0]) == 1024
    assert len(embeddings[1]) == 1024
