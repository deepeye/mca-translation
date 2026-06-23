"""JWT 与密码哈希安全工具的单元测试。

只覆盖 app.core.security 中的纯函数，不触碰数据库，因此无需 Postgres 即可运行。
端点级登录测试（需 DB + client/test_user fixture）待 conftest 补齐后再加。
"""
from datetime import timedelta

from app.core import security
from app.core.config import settings


def test_password_hash_roundtrip():
    password = "s3cret-pwd-123"
    hashed = security.get_password_hash(password)

    assert hashed != password
    assert security.verify_password(password, hashed) is True


def test_verify_password_rejects_wrong_password():
    hashed = security.get_password_hash("correct-password")

    assert security.verify_password("wrong-password", hashed) is False


def test_create_and_decode_access_token_roundtrip():
    token = security.create_access_token(data={"sub": "user-abc"})

    payload = security.decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == "user-abc"
    assert "exp" in payload


def test_decode_access_token_rejects_garbage():
    assert security.decode_access_token("not.a.valid.jwt") is None


def test_decode_access_token_rejects_expired_token():
    token = security.create_access_token(
        data={"sub": "user-abc"}, expires_delta=timedelta(seconds=-1)
    )

    assert security.decode_access_token(token) is None


def test_decode_access_token_rejects_wrong_signature(monkeypatch):
    token = security.create_access_token(data={"sub": "user-abc"})

    # 用不同密钥解码应失败
    monkeypatch.setattr(settings, "SECRET_KEY", "a-different-secret")
    assert security.decode_access_token(token) is None
