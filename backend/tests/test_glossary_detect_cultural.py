"""POST /api/glossary/detect-cultural 端点测试。

复用 cultural_preprocess；mock bailian_client 控制返回，验证：
- offset 计算（多次出现全部计入）
- 未知 cultural_sphere / audience 降级返回空
- LLM 异常 / 非法 JSON 降级返回空
- LLM 幻觉词（原文不存在）不计入
"""
import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.main import app
from app.models.user import User


class FakeClient:
    """伪造 bailian client — chat() 返回预设字符串作为 LLM 内容。"""

    def __init__(self, content: str):
        self._content = content

    async def chat(self, *, model: str, messages: list, temperature: float = 0.1) -> dict:
        return {"content": self._content}


class FailingClient:
    """chat() 抛异常，模拟 LLM 调用失败。"""

    async def chat(self, *, model: str, messages: list, temperature: float = 0.1) -> dict:
        raise RuntimeError("LLM unavailable")


@pytest.fixture
def mock_user():
    return User(id=uuid.uuid4(), username="testuser", hashed_password="fakehash")


@pytest.fixture
def auth_client(mock_user):
    """带鉴权绕过的 TestClient。"""
    async def fake_get_current_user():
        return mock_user

    app.dependency_overrides[get_current_user] = fake_get_current_user
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


VALID_PAYLOAD = """{
  "culture_loaded_terms": [
    {
      "term": "人类命运共同体",
      "culture_gap": "high",
      "adaptation_strategy": "explanatory",
      "suggested_rendering": "a community with a shared future for mankind",
      "reason": "该政治话语承载意识形态内涵，直译易引发误读"
    },
    {
      "term": "不存在的幻觉词",
      "culture_gap": "medium",
      "adaptation_strategy": "literal",
      "suggested_rendering": "phantom",
      "reason": "测试用"
    }
  ],
  "cultural_notes": [],
  "taboo_warnings": []
}"""


def _body(text: str) -> dict:
    return {
        "text": text,
        "cultural_sphere": "western_english",
        "audience_type": "general_public",
        "genre": "political",
    }


def test_detect_cultural_offsets_multiple_occurrences(auth_client):
    """同一术语多次出现应全部计入，offset 正确。"""
    text = "构建人类命运共同体，人类命运共同体是核心理念。"
    with patch("app.api.glossary.bailian_client", FakeClient(VALID_PAYLOAD)):
        res = auth_client.post("/api/glossary/detect-cultural", json=_body(text))
    assert res.status_code == 200
    terms = res.json()["terms"]
    # "人类命运共同体" 在文中出现 2 次；"幻觉词" 不在原文 → 0 条
    assert len(terms) == 2
    offsets = sorted(t["offset"] for t in terms)
    assert offsets == [2, 10]
    assert all(t["length"] == len("人类命运共同体") for t in terms)
    assert terms[0]["term_type"] == "cultural_metaphor"
    assert terms[0]["culture_gap"] == "high"
    assert terms[0]["suggested_rendering"].startswith("a community")


def test_detect_cultural_unknown_sphere_returns_empty(auth_client):
    """未知 cultural_sphere → cultural_preprocess 返回 None → 空 terms。"""
    body = _body("人类命运共同体")
    body["cultural_sphere"] = "unknown_sphere"
    with patch("app.api.glossary.bailian_client", FakeClient(VALID_PAYLOAD)):
        res = auth_client.post("/api/glossary/detect-cultural", json=body)
    assert res.status_code == 200
    assert res.json()["terms"] == []


def test_detect_cultural_llm_failure_returns_empty(auth_client):
    """LLM 调用抛异常 → cultural_preprocess 返回 None → 空 terms。"""
    with patch("app.api.glossary.bailian_client", FailingClient()):
        res = auth_client.post("/api/glossary/detect-cultural", json=_body("人类命运共同体"))
    assert res.status_code == 200
    assert res.json()["terms"] == []


def test_detect_cultural_invalid_json_returns_empty(auth_client):
    """LLM 返回非法 JSON → 解析失败 → 空 terms。"""
    with patch("app.api.glossary.bailian_client", FakeClient("not a json")):
        res = auth_client.post("/api/glossary/detect-cultural", json=_body("人类命运共同体"))
    assert res.status_code == 200
    assert res.json()["terms"] == []


def test_detect_cultural_empty_text_returns_empty(auth_client):
    """空 text → 直接返回空 terms，不调用 LLM。"""
    with patch("app.api.glossary.bailian_client", FailingClient()):
        res = auth_client.post(
            "/api/glossary/detect-cultural",
            json={**_body(""), "text": ""},
        )
    assert res.status_code == 200
    assert res.json()["terms"] == []


def test_detect_cultural_unauthorized():
    """未鉴权 → 401。"""
    client = TestClient(app)
    res = client.post("/api/glossary/detect-cultural", json=_body("测试"))
    assert res.status_code == 401
