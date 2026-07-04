"""Tests for glossary auto-fill endpoint (LLM-based per-term translation)."""
import random
import string
import uuid
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.languages import SUPPORTED_LANGUAGES
from app.core.database import get_db
from app.core.security import create_access_token, get_password_hash
from app.main import app
from app.models.glossary import UserGlossaryEntry
from app.models.user import User


def _random_user(suffix: str) -> User:
    return User(
        username=f"test_autofill_{suffix}_{''.join(random.choices(string.ascii_lowercase, k=6))}",
        hashed_password=get_password_hash("test_password"),
    )


@pytest.mark.asyncio
async def test_autofill_fills_missing_languages(db: AsyncSession, monkeypatch):
    """Happy path: auto-fill should call LLM for every missing language and return results."""
    # Arrange
    async def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    try:
        user = _random_user("happy")
        db.add(user)
        await db.commit()
        await db.refresh(user)

        token = create_access_token({"sub": str(user.id)})

        entry = UserGlossaryEntry(
            user_id=user.id,
            source_term="共同富裕",
            term_type="user_defined",
            translations={
                "en-GB": {
                    "preferred": "common prosperity",
                    "alternatives": [],
                    "notes": "",
                }
            },
        )
        db.add(entry)
        await db.commit()
        await db.refresh(entry)

        fake_client = AsyncMock()
        fake_client.chat = AsyncMock(
            return_value={
                "content": '{"rendering": "prosperidad común", "alternatives": [], "notes": ""}'
            }
        )
        monkeypatch.setattr("app.services.glossary_autofill.bailian_client", fake_client)

        # Act
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                f"/api/glossary/user-entries/{entry.id}/auto-fill",
                headers={"Authorization": f"Bearer {token}"},
            )

        # Assert
        assert resp.status_code == 200
        data = resp.json()
        assert data["entry"]["source_term"] == "共同富裕"
        assert "en-GB" in data["entry"]["translations"]
        assert len(data["filled_languages"]) > 0
        assert data["skipped"] == []
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_autofill_404_for_other_users_entry(db: AsyncSession, monkeypatch):
    """Auto-fill should return 404 when entry belongs to another user."""
    # Arrange
    async def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    try:
        owner = _random_user("owner")
        db.add(owner)
        await db.commit()
        await db.refresh(owner)

        other = _random_user("other")
        db.add(other)
        await db.commit()
        await db.refresh(other)

        token = create_access_token({"sub": str(other.id)})

        entry = UserGlossaryEntry(
            user_id=owner.id,
            source_term="共同富裕",
            term_type="user_defined",
            translations={
                "en-GB": {"preferred": "common prosperity", "alternatives": [], "notes": ""}
            },
        )
        db.add(entry)
        await db.commit()
        await db.refresh(entry)

        fake_client = AsyncMock()
        fake_client.chat = AsyncMock(return_value={"content": "{}"})
        monkeypatch.setattr("app.services.glossary_autofill.bailian_client", fake_client)

        # Act
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                f"/api/glossary/user-entries/{entry.id}/auto-fill",
                headers={"Authorization": f"Bearer {token}"},
            )

        # Assert
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_autofill_404_for_nonexistent_entry(db: AsyncSession, monkeypatch):
    """Auto-fill should return 404 when entry does not exist."""
    # Arrange
    async def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    try:
        user = _random_user("nonexist")
        db.add(user)
        await db.commit()
        await db.refresh(user)

        token = create_access_token({"sub": str(user.id)})

        fake_client = AsyncMock()
        fake_client.chat = AsyncMock(return_value={"content": "{}"})
        monkeypatch.setattr("app.services.glossary_autofill.bailian_client", fake_client)

        # Act
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                f"/api/glossary/user-entries/{uuid.uuid4()}/auto-fill",
                headers={"Authorization": f"Bearer {token}"},
            )

        # Assert
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_autofill_noop_when_all_languages_filled(db: AsyncSession, monkeypatch):
    """Auto-fill should return empty filled_languages when all languages already exist."""
    # Arrange
    async def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    try:
        user = _random_user("full")
        db.add(user)
        await db.commit()
        await db.refresh(user)

        token = create_access_token({"sub": str(user.id)})

        all_translations = {
            lang.code: {"preferred": "test", "alternatives": [], "notes": ""}
            for lang in SUPPORTED_LANGUAGES
        }
        entry = UserGlossaryEntry(
            user_id=user.id,
            source_term="共同富裕",
            term_type="user_defined",
            translations=all_translations,
        )
        db.add(entry)
        await db.commit()
        await db.refresh(entry)

        fake_client = AsyncMock()
        fake_client.chat = AsyncMock(return_value={"content": "{}"})
        monkeypatch.setattr("app.services.glossary_autofill.bailian_client", fake_client)

        # Act
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                f"/api/glossary/user-entries/{entry.id}/auto-fill",
                headers={"Authorization": f"Bearer {token}"},
            )

        # Assert
        assert resp.status_code == 200
        data = resp.json()
        assert data["filled_languages"] == []
        assert data["skipped"] == []
    finally:
        app.dependency_overrides.pop(get_db, None)
