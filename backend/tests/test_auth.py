"""JWT 安全工具的单元测试。

只覆盖 app.core.security 中 create_access_token / decode_access_token 的纯逻辑，
不触碰数据库，因此无需 Postgres 即可运行。

密码哈希（get_password_hash / verify_password）未覆盖：当前环境 passlib 1.7.4
与 bcrypt 5.0.0 不兼容，哈希调用本身会抛错（影响真实登录），待依赖修复后补测。
端点级登录测试（需 DB + client/test_user fixture）待 conftest 补齐后再加。
"""
from datetime import timedelta

from app.core import security
from app.core.config import settings


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
