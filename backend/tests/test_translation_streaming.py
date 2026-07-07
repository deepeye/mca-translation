"""流式翻译单元测试：_main_translation 流式累积 + on_chunk 回调 + 质量对齐 + 错误传播。"""
import pytest
from unittest.mock import AsyncMock, patch

from app.llm.bailian import bailian_client
from app.services.translation import TranslationPipeline


def _streaming(chunks):
    """构造伪 chat_stream：依次 yield chunks。"""
    async def fake_chat_stream(*, model, messages, temperature=0.3):
        for c in chunks:
            yield c
    return fake_chat_stream


@pytest.mark.asyncio
async def test_main_translation_streams_and_calls_on_chunk():
    pipeline = TranslationPipeline()
    received = []

    async def on_chunk(accumulated):
        received.append(accumulated)

    with patch.object(bailian_client, "chat_stream", _streaming(["Hello", " world"])):
        result = await pipeline._main_translation(
            source_text="原文",
            genre="news",
            strategy="semantic_equivalence",
            target_language="en-GB",
            on_chunk=on_chunk,
        )

    assert result == "Hello world"
    assert received == ["Hello", "Hello world"]


@pytest.mark.asyncio
async def test_main_translation_injects_glossary_block_into_stream_prompt():
    pipeline = TranslationPipeline()
    captured = {}

    async def fake_chat_stream(*, model, messages, temperature=0.3):
        captured["system"] = messages[0]["content"]
        yield ""

    with patch.object(bailian_client, "chat_stream", fake_chat_stream):
        await pipeline._main_translation(
            source_text="原文",
            genre="news",
            strategy="semantic_equivalence",
            target_language="en-GB",
            glossary_block="<glossary_terms>TERM</glossary_terms>",
        )

    assert "<glossary_terms>" in captured["system"]


@pytest.mark.asyncio
async def test_main_translation_propagates_stream_error():
    pipeline = TranslationPipeline()

    async def failing_stream(*, model, messages, temperature=0.3):
        raise RuntimeError("stream broke")
        yield ""  # noqa - 使其成为 async generator（raise 先于 yield 执行）

    with patch.object(bailian_client, "chat_stream", failing_stream):
        with pytest.raises(RuntimeError, match="stream broke"):
            await pipeline._main_translation(
                source_text="原文",
                genre="news",
                strategy="semantic_equivalence",
                target_language="en-GB",
            )


@pytest.mark.asyncio
async def test_translate_passes_on_chunk_to_main_translation():
    pipeline = TranslationPipeline()
    received = []

    async def on_chunk(accumulated):
        received.append(accumulated)

    with patch.object(bailian_client, "chat_stream", _streaming(["Hi", " there"])), \
         patch.object(pipeline, "_risk_annotation", AsyncMock(return_value=[])):
        output = await pipeline.translate(
            source_text="原文",
            genre="news",
            strategy="semantic_equivalence",
            target_language="en-GB",
            on_chunk=on_chunk,
        )

    assert output["translated_text"] == "Hi there"
    assert received == ["Hi", "Hi there"]
