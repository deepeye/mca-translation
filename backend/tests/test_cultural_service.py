"""文化预处理服务的单元测试。

LLM 客户端通过参数注入，便于伪造响应。
"""
from typing import Any

import pytest

from app.schemas.job import CulturalPreprocessResult
from app.services.cultural import cultural_preprocess


class FakeClient:
    """伪造的 bailian client。chat() 返回预设的字符串作为 LLM 内容。"""

    def __init__(self, content: str):
        self._content = content
        self.calls: list[dict[str, Any]] = []

    async def chat(self, *, model: str, messages: list, temperature: float = 0.1) -> dict:
        self.calls.append({"model": model, "messages": messages, "temperature": temperature})
        return {"content": self._content}


@pytest.mark.asyncio
async def test_returns_parsed_result_on_valid_json():
    payload = """{
      "culture_loaded_terms": [
        {
          "term": "共同富裕",
          "culture_gap": "high",
          "adaptation_strategy": "explanatory",
          "suggested_rendering": "a policy initiative for balanced wealth distribution",
          "reason": "西方受众缺少政策语境"
        }
      ],
      "cultural_notes": ["避免国家主导叙事"],
      "taboo_warnings": []
    }"""
    client = FakeClient(payload)
    result = await cultural_preprocess(
        text="共同富裕不是平均主义。",
        cultural_sphere="western_english",
        audience_type="general_public",
        genre="political",
        llm_client=client,
    )
    assert isinstance(result, CulturalPreprocessResult)
    assert len(result.culture_loaded_terms) == 1
    assert result.culture_loaded_terms[0].term == "共同富裕"
    assert result.cultural_notes == ["避免国家主导叙事"]
    assert result.taboo_warnings == []
    # Verify the prompt was assembled with the right inputs
    assert len(client.calls) == 1
    sent_messages = client.calls[0]["messages"]
    assert len(sent_messages) == 1
    sent_prompt = sent_messages[0]["content"]
    assert "共同富裕不是平均主义。" in sent_prompt
    assert "欧美英语圈" in sent_prompt
    assert "公众读者" in sent_prompt
    assert "political" in sent_prompt
    assert client.calls[0]["temperature"] == 0.1


@pytest.mark.asyncio
async def test_strips_markdown_code_fences():
    payload = "```json\n" + '{"culture_loaded_terms": [], "cultural_notes": [], "taboo_warnings": []}' + "\n```"
    client = FakeClient(payload)
    result = await cultural_preprocess(
        text="x",
        cultural_sphere="western_english",
        audience_type="general_public",
        genre="political",
        llm_client=client,
    )
    assert result is not None
    assert result.culture_loaded_terms == []


@pytest.mark.asyncio
async def test_returns_none_on_invalid_json():
    client = FakeClient("not a json")
    result = await cultural_preprocess(
        text="x",
        cultural_sphere="western_english",
        audience_type="general_public",
        genre="political",
        llm_client=client,
    )
    assert result is None


@pytest.mark.asyncio
async def test_returns_none_on_unknown_cultural_sphere():
    client = FakeClient('{"culture_loaded_terms": [], "cultural_notes": [], "taboo_warnings": []}')
    result = await cultural_preprocess(
        text="x",
        cultural_sphere="atlantis",  # 不在白名单
        audience_type="general_public",
        genre="political",
        llm_client=client,
    )
    assert result is None


@pytest.mark.asyncio
async def test_returns_none_on_llm_exception():
    class FailingClient:
        async def chat(self, **_):
            raise RuntimeError("upstream timeout")

    result = await cultural_preprocess(
        text="x",
        cultural_sphere="western_english",
        audience_type="general_public",
        genre="political",
        llm_client=FailingClient(),
    )
    assert result is None


@pytest.mark.asyncio
async def test_filters_protected_neutral_terms():
    """普通政治通用词（如“国家”）不应被识别为文化负载词。"""
    payload = """{
      "culture_loaded_terms": [
        {
          "term": "国家",
          "culture_gap": "high",
          "adaptation_strategy": "reconstruction",
          "suggested_rendering": "the U.S. government and its agencies",
          "reason": "test"
        }
      ],
      "cultural_notes": [],
      "taboo_warnings": []
    }"""
    client = FakeClient(payload)
    result = await cultural_preprocess(
        text="国家",
        cultural_sphere="western_english",
        audience_type="general_public",
        genre="political",
        llm_client=client,
    )
    assert isinstance(result, CulturalPreprocessResult)
    assert result.culture_loaded_terms == []


@pytest.mark.asyncio
async def test_keeps_non_protected_terms_beside_protected_ones():
    """保护列表只过滤通用词，真正的文化负载词应保留。"""
    payload = """{
      "culture_loaded_terms": [
        {
          "term": "国家",
          "culture_gap": "high",
          "adaptation_strategy": "reconstruction",
          "suggested_rendering": "the U.S. government",
          "reason": "test"
        },
        {
          "term": "共同富裕",
          "culture_gap": "high",
          "adaptation_strategy": "explanatory",
          "suggested_rendering": "common prosperity",
          "reason": "test"
        }
      ],
      "cultural_notes": [],
      "taboo_warnings": []
    }"""
    client = FakeClient(payload)
    result = await cultural_preprocess(
        text="国家推动共同富裕。",
        cultural_sphere="western_english",
        audience_type="general_public",
        genre="political",
        llm_client=client,
    )
    assert isinstance(result, CulturalPreprocessResult)
    assert len(result.culture_loaded_terms) == 1
    assert result.culture_loaded_terms[0].term == "共同富裕"


@pytest.mark.asyncio
async def test_returns_none_on_unknown_audience_type():
    client = FakeClient('{"culture_loaded_terms": [], "cultural_notes": [], "taboo_warnings": []}')
    result = await cultural_preprocess(
        text="x",
        cultural_sphere="western_english",
        audience_type="aliens",
        genre="political",
        llm_client=client,
    )
    assert result is None
