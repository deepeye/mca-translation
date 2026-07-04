# Admin User Management Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add user creation, editing, disable/enable, and logical deletion to the admin user management page.

**Architecture:** Three new backend API endpoints + one PATCH + modified login check; frontend extends the existing admin page with a shared UserFormModal, a DeleteConfirmDialog, and an action dropdown menu on each table row.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, Alembic, shadcn/ui, Zustand, Vitest

## Global Constraints

- All new API endpoints protected by `require_admin` (existing pattern)
- `is_active` and `deleted_at` on User model; logical deletion via `deleted_at` timestamp
- Password hashing via existing `get_password_hash()` from `app.core.security`
- Frontend follows existing modal pattern (plain div overlay, not shadcn Dialog)
- Frontend table styled same as current users-table.tsx (plain HTML table)
- Test patterns: httpx AsyncClient + ASGITransport for backend; vitest + @testing-library/react for frontend

---

### Task 1: Database Migration — Add is_active and deleted_at to User model

**Files:**
- Modify: `backend/app/models/user.py`
- Create: auto-generated Alembic migration file
- Test: verify migration applies/rolls back cleanly

**Interfaces:**
- Produces: `User.is_active: Mapped[bool]`, `User.deleted_at: Mapped[datetime | None]` on the model; a new migration revision

- [ ] **Step 1: Add fields to User model**

Edit `backend/app/models/user.py` — add `is_active` after `is_admin`, add `deleted_at` before `created_at`:

```python
class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(128))
    credit_balance: Mapped[int] = mapped_column(Integer, default=1000, server_default="1000")
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # 禁用/启用标记
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    # 逻辑删除时间戳，非空=已删除
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 2: Generate Alembic migration**

```bash
cd backend
alembic revision --autogenerate -m "add is_active and deleted_at to users"
```

Expected: A new file appears in `backend/migrations/versions/`.

- [ ] **Step 3: Apply the migration**

```bash
cd backend
alembic upgrade head
```

Expected: `INFO  [alembic.runtime.migration] Running upgrade ... -> ... (empty message)`

- [ ] **Step 4: Verify migration output**

```bash
cd backend
alembic history
# Should show the new revision at HEAD
alembic current
# Should show the new revision
```

- [ ] **Step 5: Seed existing users with is_active=true**

Since `is_active` has `server_default="true"`, existing rows automatically get `is_active=true`. `deleted_at` defaults to NULL. No manual seed needed.

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/user.py backend/migrations/versions/
git commit -m "feat(db): add is_active and deleted_at to User model"
```

---

### Task 2: Backend Schemas — Create admin.py

**Files:**
- Create: `backend/app/schemas/admin.py`
- Modify: `backend/app/schemas/credit.py` (remove AdminUserItem — replace with import)
- Test: verify schemas import and validate correctly

**Interfaces:**
- Produces: `CreateUserRequest`, `UpdateUserRequest`, `ToggleStatusRequest`, `AdminUserDetail` — all in `app.schemas.admin`

- [ ] **Step 1: Create `backend/app/schemas/admin.py`**

```python
"""管理员用户管理相关 Pydantic schema。"""
from pydantic import BaseModel, Field


class CreateUserRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=6, max_length=128)
    is_admin: bool = False


class UpdateUserRequest(BaseModel):
    username: str | None = Field(None, min_length=1, max_length=64)
    password: str | None = Field(None, min_length=1, max_length=128)
    is_admin: bool | None = None


class ToggleStatusRequest(BaseModel):
    is_active: bool


class AdminUserDetail(BaseModel):
    id: str
    username: str
    is_admin: bool
    is_active: bool
    credit_balance: int
    last_active: str | None = None
    created_at: str
```

Note: `AdminUserDetail.last_active` is computed from the last CreditTransaction timestamp (same pattern as current admin.py). `created_at` is the user's registration timestamp as ISO string.

- [ ] **Step 2: Remove AdminUserItem from credit.py and import from admin.py instead**

Edit `backend/app/schemas/credit.py` — remove the `AdminUserItem` class (it's now in `admin.py`).

```python
"""信用分相关 Pydantic schema。"""
from pydantic import BaseModel, Field


class AdminAdjustRequest(BaseModel):
    delta: int = Field(..., description="正数=充值，负数=扣减")
    reason: str = Field(..., min_length=1, max_length=200)


class CreditTransactionOut(BaseModel):
    id: str
    delta: int
    tx_type: str
    reason: str | None
    job_id: str | None
    review_id: str | None
    created_at: str
```

- [ ] **Step 3: Update admin.py import to use AdminUserDetail**

Edit `backend/app/api/admin.py` — change the import line:

```python
from app.schemas.admin import AdminUserDetail, CreateUserRequest, UpdateUserRequest, ToggleStatusRequest
from app.schemas.credit import AdminAdjustRequest, CreditTransactionOut
```

Also change all uses of `AdminUserItem` → `AdminUserDetail`.

- [ ] **Step 4: Commit**

```bash
git add backend/app/schemas/admin.py backend/app/schemas/credit.py backend/app/api/admin.py
git commit -m "refactor(schemas): move AdminUserItem to admin.py, add user CRUD schemas"
```

---

### Task 3: Backend API — New Endpoints + Login Check

**Files:**
- Modify: `backend/app/api/admin.py` — add 4 new endpoints (create, update, delete, toggle status)
- Modify: `backend/app/api/auth.py` — add is_active/deleted_at checks to login
- Modify: `backend/app/schemas/admin.py` — already done in Task 2

**Interfaces:**
- Consumes: `CreateUserRequest`, `UpdateUserRequest`, `ToggleStatusRequest`, `AdminUserDetail` from `app.schemas.admin`; `get_password_hash` from `app.core.security`
- Produces: 4 new admin-only endpoints; modified `/api/auth/login` response

- [ ] **Step 1: Add create user endpoint**

Add to `backend/app/api/admin.py`:

```python
from datetime import datetime, timezone

from app.core.security import get_password_hash
from app.schemas.admin import AdminUserDetail, CreateUserRequest, UpdateUserRequest, ToggleStatusRequest


@router.post("/users", response_model=AdminUserDetail, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: CreateUserRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """管理员创建新用户。"""
    existing = (await db.execute(select(User).where(User.username == body.username))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="用户名已存在")
    user = User(
        username=body.username,
        hashed_password=get_password_hash(body.password),
        is_admin=body.is_admin,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return AdminUserDetail(
        id=str(user.id),
        username=user.username,
        is_admin=user.is_admin,
        is_active=user.is_active,
        credit_balance=user.credit_balance,
        last_active=None,
        created_at=user.created_at.isoformat(),
    )
```

- [ ] **Step 2: Add update user endpoint**

```python
@router.put("/users/{user_id}", response_model=AdminUserDetail)
async def update_user(
    user_id: uuid.UUID,
    body: UpdateUserRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """管理员更新用户信息。不允许自己降级非管理员。"""
    user = await db.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    # 不允许自降权限
    if user.id == admin.id and body.is_admin is False:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="不能移除自己的管理员权限")

    if body.username is not None:
        existing = (await db.execute(
            select(User).where(User.username == body.username, User.id != user_id)
        )).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="用户名已存在")
        user.username = body.username
    if body.password is not None and body.password != "":
        user.hashed_password = get_password_hash(body.password)
    if body.is_admin is not None:
        user.is_admin = body.is_admin

    await db.commit()
    await db.refresh(user)
    # compute last_active same as list_users
    last_tx = (
        await db.execute(
            select(CreditTransaction.created_at)
            .where(CreditTransaction.user_id == user.id)
            .order_by(CreditTransaction.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return AdminUserDetail(
        id=str(user.id),
        username=user.username,
        is_admin=user.is_admin,
        is_active=user.is_active,
        credit_balance=user.credit_balance,
        last_active=last_tx.isoformat() if last_tx else None,
        created_at=user.created_at.isoformat(),
    )
```

- [ ] **Step 3: Add logical delete endpoint**

```python
@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """逻辑删除用户。不允许删除自己。"""
    if admin.id == user_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="不能删除当前登录的管理员")
    user = await db.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    user.deleted_at = datetime.now(timezone.utc)
    await db.commit()
```

- [ ] **Step 4: Add toggle status endpoint**

```python
@router.patch("/users/{user_id}/status", response_model=AdminUserDetail)
async def toggle_user_status(
    user_id: uuid.UUID,
    body: ToggleStatusRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """禁用或启用用户。不允许禁用自己。"""
    if not body.is_active and admin.id == user_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="不能禁用当前登录的管理员")
    user = await db.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    user.is_active = body.is_active
    await db.commit()
    await db.refresh(user)
    last_tx = (
        await db.execute(
            select(CreditTransaction.created_at)
            .where(CreditTransaction.user_id == user.id)
            .order_by(CreditTransaction.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return AdminUserDetail(
        id=str(user.id),
        username=user.username,
        is_admin=user.is_admin,
        is_active=user.is_active,
        credit_balance=user.credit_balance,
        last_active=last_tx.isoformat() if last_tx else None,
        created_at=user.created_at.isoformat(),
    )
```

- [ ] **Step 5: Update GET /api/admin/users to filter deleted users + return is_active**

Edit `backend/app/api/admin.py` — modify `list_users`:

```python
@router.get("/users", response_model=list[AdminUserDetail])
async def list_users(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    users = (await db.execute(
        select(User).where(User.deleted_at.is_(None)).order_by(User.created_at.desc())
    )).scalars().all()
    out = []
    for u in users:
        last_tx = (
            await db.execute(
                select(CreditTransaction.created_at)
                .where(CreditTransaction.user_id == u.id)
                .order_by(CreditTransaction.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        out.append(AdminUserDetail(
            id=str(u.id),
            username=u.username,
            is_admin=u.is_admin,
            is_active=u.is_active,
            credit_balance=u.credit_balance,
            last_active=last_tx.isoformat() if last_tx else None,
            created_at=u.created_at.isoformat(),
        ))
    return out
```

- [ ] **Step 6: Update login to check is_active and deleted_at**

Edit `backend/app/api/auth.py` — modify `login`:

```python
@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    # 检查逻辑删除 — 与"不存在"返回一致，不泄露账号存在性
    if user.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    # 检查禁用
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已被禁用，请联系管理员")
    access_token = create_access_token(data={"sub": str(user.id)})
    return TokenResponse(access_token=access_token)
```

- [ ] **Step 7: Add missing import for CreditTransaction in admin.py**

If not already imported, add the import at the top of `backend/app/api/admin.py`:

```python
from app.models.credit import CreditTransaction
```

- [ ] **Step 8: Commit**

```bash
git add backend/app/api/admin.py backend/app/api/auth.py
git commit -m "feat(api): add user CRUD endpoints + login status check"
```

---

### Task 4: Backend Tests

**Files:**
- Modify: `backend/tests/test_admin_api.py`

- [ ] **Step 1: Add test for create user**

Add these tests to `backend/tests/test_admin_api.py`:

```python
@pytest.mark.asyncio
async def test_admin_create_user(db: AsyncSession):
    admin = await _make_user(db, admin=True, username="create_admin")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/admin/users",
            headers=_headers(admin.id),
            json={"username": "newuser", "password": "pass123", "is_admin": False},
        )
    assert resp.status_code == 201
    data = resp.json()
    assert data["username"] == "newuser"
    assert data["is_admin"] is False
    assert data["is_active"] is True
    assert data["credit_balance"] == 1000
    assert "id" in data


@pytest.mark.asyncio
async def test_admin_create_user_duplicate(db: AsyncSession):
    admin = await _make_user(db, admin=True, username="dup_admin")
    await _make_user(db, username="existing_user")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/admin/users",
            headers=_headers(admin.id),
            json={"username": "existing_user", "password": "pass123"},
        )
    assert resp.status_code == 409
    assert "用户名已存在" in resp.text


@pytest.mark.asyncio
async def test_admin_create_user_short_password(db: AsyncSession):
    admin = await _make_user(db, admin=True, username="pw_admin")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/admin/users",
            headers=_headers(admin.id),
            json={"username": "newuser2", "password": "ab", "is_admin": False},
        )
    assert resp.status_code == 422
```

- [ ] **Step 2: Run create user tests**

```bash
cd backend
pytest tests/test_admin_api.py::test_admin_create_user tests/test_admin_api.py::test_admin_create_user_duplicate tests/test_admin_api.py::test_admin_create_user_short_password -v
```

Expected: 3 PASS

- [ ] **Step 3: Add test for update user**

```python
@pytest.mark.asyncio
async def test_admin_update_user(db: AsyncSession):
    admin = await _make_user(db, admin=True, username="upd_admin")
    target = await _make_user(db, username="upd_target")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.put(
            f"/api/admin/users/{target.id}",
            headers=_headers(admin.id),
            json={"username": "updated_name", "is_admin": True},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "updated_name"
    assert data["is_admin"] is True


@pytest.mark.asyncio
async def test_admin_update_self_admin_fails(db: AsyncSession):
    admin = await _make_user(db, admin=True, username="self_admin")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.put(
            f"/api/admin/users/{admin.id}",
            headers=_headers(admin.id),
            json={"is_admin": False},
        )
    assert resp.status_code == 409
    assert "不能移除自己的管理员权限" in resp.text


@pytest.mark.asyncio
async def test_admin_update_nonexistent_user(db: AsyncSession):
    admin = await _make_user(db, admin=True, username="nonexist_admin")
    fake_id = uuid.uuid4()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.put(
            f"/api/admin/users/{fake_id}",
            headers=_headers(admin.id),
            json={"username": "ghost"},
        )
    assert resp.status_code == 404
```

- [ ] **Step 4: Run update user tests**

```bash
cd backend
pytest tests/test_admin_api.py::test_admin_update_user tests/test_admin_api.py::test_admin_update_self_admin_fails tests/test_admin_api.py::test_admin_update_nonexistent_user -v
```

Expected: 3 PASS

- [ ] **Step 5: Add test for logical delete**

```python
@pytest.mark.asyncio
async def test_admin_delete_user(db: AsyncSession):
    admin = await _make_user(db, admin=True, username="del_admin")
    target = await _make_user(db, username="del_target")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.delete(
            f"/api/admin/users/{target.id}",
            headers=_headers(admin.id),
        )
    assert resp.status_code == 204
    # 确认逻辑删除 — 用户不在列表中
    resp2 = await client.get("/api/admin/users", headers=_headers(admin.id))
    usernames = [u["username"] for u in resp2.json()]
    assert "del_target" not in usernames


@pytest.mark.asyncio
async def test_admin_delete_self_fails(db: AsyncSession):
    admin = await _make_user(db, admin=True, username="self_del")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.delete(
            f"/api/admin/users/{admin.id}",
            headers=_headers(admin.id),
        )
    assert resp.status_code == 409
    assert "不能删除当前登录的管理员" in resp.text
```

- [ ] **Step 6: Run delete tests**

```bash
cd backend
pytest tests/test_admin_api.py::test_admin_delete_user tests/test_admin_api.py::test_admin_delete_self_fails -v
```

Expected: 2 PASS

- [ ] **Step 7: Add test for toggle status**

```python
@pytest.mark.asyncio
async def test_admin_toggle_status(db: AsyncSession):
    admin = await _make_user(db, admin=True, username="tog_admin")
    target = await _make_user(db, username="tog_target")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 禁用
        resp = await client.patch(
            f"/api/admin/users/{target.id}/status",
            headers=_headers(admin.id),
            json={"is_active": False},
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False
        # 启用
        resp2 = await client.patch(
            f"/api/admin/users/{target.id}/status",
            headers=_headers(admin.id),
            json={"is_active": True},
        )
        assert resp2.status_code == 200
        assert resp2.json()["is_active"] is True


@pytest.mark.asyncio
async def test_admin_toggle_self_fails(db: AsyncSession):
    admin = await _make_user(db, admin=True, username="self_tog")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.patch(
            f"/api/admin/users/{admin.id}/status",
            headers=_headers(admin.id),
            json={"is_active": False},
        )
    assert resp.status_code == 409
    assert "不能禁用当前登录的管理员" in resp.text
```

- [ ] **Step 8: Run toggle tests**

```bash
cd backend
pytest tests/test_admin_api.py::test_admin_toggle_status tests/test_admin_api.py::test_admin_toggle_self_fails -v
```

Expected: 2 PASS

- [ ] **Step 9: Add tests for login status checks**

```python
@pytest.mark.asyncio
async def test_login_disabled_user_returns_403(db: AsyncSession):
    from app.core.security import get_password_hash
    user = User(
        username="disabled_user",
        hashed_password=get_password_hash("pass123"),
        is_active=False,
    )
    db.add(user)
    await db.commit()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/auth/login", json={"username": "disabled_user", "password": "pass123"})
    assert resp.status_code == 403
    assert "账号已被禁用" in resp.text


@pytest.mark.asyncio
async def test_login_deleted_user_returns_401(db: AsyncSession):
    from datetime import datetime, timezone
    from app.core.security import get_password_hash
    user = User(
        username="deleted_user",
        hashed_password=get_password_hash("pass123"),
        deleted_at=datetime.now(timezone.utc),
    )
    db.add(user)
    await db.commit()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/auth/login", json={"username": "deleted_user", "password": "pass123"})
    assert resp.status_code == 401
```

- [ ] **Step 10: Run login status tests**

```bash
cd backend
pytest tests/test_admin_api.py::test_login_disabled_user_returns_403 tests/test_admin_api.py::test_login_deleted_user_returns_401 -v
```

Expected: 2 PASS

- [ ] **Step 11: Run the full suite to confirm nothing regressed**

```bash
cd backend
pytest -v
```

Expected: All tests PASS

- [ ] **Step 12: Commit**

```bash
git add backend/tests/test_admin_api.py
git commit -m "test: admin user CRUD + login status checks"
```

---

### Task 5: Frontend UserFormModal Component

**Files:**
- Create: `frontend/components/admin/user-form-modal.tsx`
- Test: `frontend/components/admin/__tests__/user-form-modal.test.tsx`

**Interfaces:**
- Consumes: `apiClient` from `@/lib/api-client`
- Produces: `<UserFormModal>` component with props `userId?`, `currentIsAdmin?`, `username?`, `open`, `onClose`, `onSubmitted`

- [ ] **Step 1: Create the UserFormModal component**

Create `frontend/components/admin/user-form-modal.tsx`:

```tsx
"use client";

import { useState, useEffect } from "react";
import { apiClient } from "@/lib/api-client";

interface Props {
  userId?: string;        // undefined = create mode, defined = edit mode
  username?: string;      // for display in title
  currentIsAdmin?: boolean; // current admin status (edit mode only)
  open: boolean;
  onClose: () => void;
  onSubmitted: () => void;
}

export function UserFormModal({ userId, username, currentIsAdmin, open, onClose, onSubmitted }: Props) {
  const isEdit = !!userId;
  const [formUsername, setFormUsername] = useState("");
  const [formPassword, setFormPassword] = useState("");
  const [formIsAdmin, setFormIsAdmin] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (open) {
      setFormUsername(username ?? "");
      setFormPassword("");
      setFormIsAdmin(currentIsAdmin ?? false);
      setError(null);
    }
  }, [open, isEdit, username, currentIsAdmin]);

  if (!open) return null;

  async function handleSubmit() {
    if (!formUsername.trim()) {
      setError("请输入用户名");
      return;
    }
    if (!isEdit && !formPassword.trim()) {
      setError("请输入密码");
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      if (isEdit) {
        const body: Record<string, unknown> = {};
        if (formUsername.trim() && formUsername.trim() !== username) body.username = formUsername.trim();
        if (formPassword) body.password = formPassword;
        if (currentIsAdmin !== undefined && formIsAdmin !== currentIsAdmin) body.is_admin = formIsAdmin;
        await apiClient.put(`/api/admin/users/${userId}`, body);
      } else {
        await apiClient.post("/api/admin/users", {
          username: formUsername.trim(),
          password: formPassword,
          is_admin: formIsAdmin,
        });
      }
      onSubmitted();
      setFormUsername("");
      setFormPassword("");
      setFormIsAdmin(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "提交失败");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-lg">
        <h3 className="mb-4 text-lg font-semibold">
          {isEdit ? `编辑用户 — ${username}` : "创建用户"}
        </h3>
        <div className="space-y-3">
          <div>
            <label className="block text-sm text-muted-foreground mb-1" htmlFor="uf-username">
              用户名
            </label>
            <input
              id="uf-username"
              aria-label="用户名"
              type="text"
              value={formUsername}
              onChange={(e) => setFormUsername(e.target.value)}
              className="w-full rounded border border-border px-3 py-2"
              maxLength={64}
            />
          </div>
          <div>
            <label className="block text-sm text-muted-foreground mb-1" htmlFor="uf-password">
              密码{isEdit ? "（留空不修改）" : ""}
            </label>
            <input
              id="uf-password"
              aria-label="密码"
              type="password"
              value={formPassword}
              onChange={(e) => setFormPassword(e.target.value)}
              className="w-full rounded border border-border px-3 py-2"
              minLength={isEdit ? 0 : 6}
            />
          </div>
          <div className="flex items-center gap-2">
            <input
              id="uf-is_admin"
              aria-label="管理员权限"
              type="checkbox"
              checked={formIsAdmin}
              onChange={(e) => setFormIsAdmin(e.target.checked)}
              className="h-4 w-4"
            />
            <label htmlFor="uf-is_admin" className="text-sm text-muted-foreground">
              管理员权限
            </label>
          </div>
          {error && <p className="text-sm text-danger">{error}</p>}
        </div>
        <div className="mt-6 flex justify-end gap-2">
          <button
            onClick={onClose}
            className="rounded px-4 py-2 text-sm bg-muted text-muted-foreground cursor-pointer"
          >
            取消
          </button>
          <button
            onClick={handleSubmit}
            disabled={submitting}
            className="rounded px-4 py-2 text-sm bg-teal text-white cursor-pointer disabled:opacity-50"
          >
            {submitting ? "提交中..." : (isEdit ? "保存" : "创建")}
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create DeleteConfirmDialog component**

Create `frontend/components/admin/delete-confirm-dialog.tsx`:

```tsx
"use client";

import { useState } from "react";
import { apiClient } from "@/lib/api-client";

interface Props {
  userId: string;
  username: string;
  open: boolean;
  onClose: () => void;
  onDeleted: () => void;
}

export function DeleteConfirmDialog({ userId, username, open, onClose, onDeleted }: Props) {
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (!open) return null;

  async function handleDelete() {
    setError(null);
    setSubmitting(true);
    try {
      await apiClient.delete(`/api/admin/users/${userId}`);
      onDeleted();
    } catch (e) {
      setError(e instanceof Error ? e.message : "删除失败");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-sm rounded-lg bg-white p-6 shadow-lg">
        <h3 className="mb-2 text-lg font-semibold">确认删除</h3>
        <p className="text-sm text-muted-foreground mb-4">
          确定要删除用户 <strong>{username}</strong> 吗？此操作不可恢复。
        </p>
        {error && <p className="text-sm text-danger mb-2">{error}</p>}
        <div className="flex justify-end gap-2">
          <button
            onClick={onClose}
            className="rounded px-4 py-2 text-sm bg-muted text-muted-foreground cursor-pointer"
          >
            取消
          </button>
          <button
            onClick={handleDelete}
            disabled={submitting}
            className="rounded px-4 py-2 text-sm bg-danger text-white cursor-pointer disabled:opacity-50"
          >
            {submitting ? "删除中..." : "确认删除"}
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/components/admin/user-form-modal.tsx frontend/components/admin/delete-confirm-dialog.tsx
git commit -m "feat(ui): add UserFormModal and DeleteConfirmDialog components"
```

---

### Task 6: Frontend Table Redesign with Action Menu

**Files:**
- Modify: `frontend/lib/api-client.ts` — add `patch` method
- Modify: `frontend/components/admin/users-table.tsx`
- Modify: `frontend/app/(main)/admin/users/page.tsx`

**Interfaces:**
- Consumes: `AdminUser` with `is_active` from `users-table.tsx`; `apiClient.patch` from `@/lib/api-client`
- Produces: Updated admin users page with action menu, status column, create/edit/delete support

- [ ] **Step 1: Add `patch` method to ApiClient**

Add to `frontend/lib/api-client.ts` before the `get` method:

```typescript
  async patch(path: string, body: unknown) {
    const res = await this.request(path, { method: "PATCH", body: JSON.stringify(body) });
    return res.json();
  }
```

- [ ] **Step 2: Rewrite users-table.tsx with action menu, status column, and integrated modals**

```tsx
"use client";

import { useState } from "react";
import { apiClient } from "@/lib/api-client";
import { AdjustModal } from "./adjust-modal";
import { UserFormModal } from "./user-form-modal";
import { DeleteConfirmDialog } from "./delete-confirm-dialog";

export interface AdminUser {
  id: string;
  username: string;
  is_admin: boolean;
  is_active: boolean;
  credit_balance: number;
  last_active: string | null;
  created_at: string;
}

export function UsersTable({
  users,
  onChanged,
}: {
  users: AdminUser[];
  onChanged: () => void;
}) {
  const [actionUser, setActionUser] = useState<AdminUser | null>(null);
  const [showAdjust, setShowAdjust] = useState(false);
  const [showEdit, setShowEdit] = useState(false);
  const [showDelete, setShowDelete] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);

  function closeAll() {
    setShowAdjust(false);
    setShowEdit(false);
    setShowDelete(false);
    setOpenMenuId(null);
  }

  function handleAction(u: AdminUser) {
    setActionUser(u);
    setOpenMenuId(u.id);
  }

  return (
    <>
      <div className="mb-4 flex items-center justify-between">
        <span className="text-sm text-muted-foreground">
          共 {users.length} 个用户
        </span>
        <button
          onClick={() => { setShowCreate(true); setActionUser(null); }}
          className="rounded bg-teal px-4 py-1.5 text-sm text-white cursor-pointer"
        >
          ＋创建用户
        </button>
      </div>

      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-left text-muted-foreground">
            <th className="py-2">用户名</th>
            <th>角色</th>
            <th>余额</th>
            <th>状态</th>
            <th>最近活跃</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.id} className="border-b">
              <td className="py-2">{u.username}</td>
              <td>{u.is_admin ? "管理员" : "普通用户"}</td>
              <td className={u.credit_balance <= 0 ? "text-danger" : ""}>{u.credit_balance}</td>
              <td>
                <span className={u.is_active ? "text-green-600" : "text-muted-foreground"}>
                  {u.is_active ? "正常" : "已禁用"}
                </span>
              </td>
              <td className="text-muted-foreground">
                {u.last_active ? new Date(u.last_active).toLocaleString("zh-CN") : "-"}
              </td>
              <td className="relative">
                <button
                  onClick={() => handleAction(u)}
                  className="rounded px-2 py-1 text-sm text-muted-foreground hover:bg-muted cursor-pointer"
                >
                  ⋮
                </button>
                {openMenuId === u.id && (
                  <>
                    <div className="fixed inset-0 z-40" onClick={() => setOpenMenuId(null)} />
                    <div className="absolute right-0 z-50 mt-1 w-40 rounded-lg border border-border bg-white py-1 shadow-lg">
                      <button
                        onClick={() => { setShowAdjust(true); setOpenMenuId(null); }}
                        className="block w-full px-4 py-2 text-left text-sm hover:bg-muted cursor-pointer"
                      >
                        调整余额
                      </button>
                      <button
                        onClick={() => { setShowEdit(true); setOpenMenuId(null); }}
                        className="block w-full px-4 py-2 text-left text-sm hover:bg-muted cursor-pointer"
                      >
                        编辑
                      </button>
                      <div className="border-t border-border my-1" />
                      <button
                        onClick={async () => {
                          setOpenMenuId(null);
                          try {
                            await apiClient.patch(`/api/admin/users/${u.id}/status`, {
                              is_active: !u.is_active,
                            });
                            onChanged();
                          } catch (e) {
                            alert(e instanceof Error ? e.message : "操作失败");
                          }
                        }}
                        className="block w-full px-4 py-2 text-left text-sm hover:bg-muted cursor-pointer"
                      >
                        {u.is_active ? "禁用" : "启用"}
                      </button>
                      <button
                        onClick={() => { setShowDelete(true); setOpenMenuId(null); }}
                        className="block w-full px-4 py-2 text-left text-sm text-danger hover:bg-red-50 cursor-pointer"
                      >
                        删除
                      </button>
                    </div>
                  </>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* Modals */}
      {actionUser && showAdjust && (
        <AdjustModal
          userId={actionUser.id}
          username={actionUser.username}
          open={true}
          onClose={() => { setShowAdjust(false); setActionUser(null); }}
          onSubmitted={() => { closeAll(); onChanged(); }}
        />
      )}
      {actionUser && showEdit && (
        <UserFormModal
          userId={actionUser.id}
          username={actionUser.username}
          currentIsAdmin={actionUser.is_admin}
          open={true}
          onClose={() => { closeAll(); setActionUser(null); }}
          onSubmitted={() => { closeAll(); onChanged(); }}
        />
      )}
      {showCreate && (
        <UserFormModal
          open={true}
          onClose={() => { setShowCreate(false); }}
          onSubmitted={() => { setShowCreate(false); onChanged(); }}
        />
      )}
      {actionUser && showDelete && (
        <DeleteConfirmDialog
          userId={actionUser.id}
          username={actionUser.username}
          open={true}
          onClose={() => { closeAll(); setActionUser(null); }}
          onDeleted={() => { closeAll(); onChanged(); }}
        />
      )}
    </>
  );
}
```

- [ ] **Step 3: Update the AdminUser interface import in page.tsx**

The `AdminUser` type now includes `is_active`. The page already imports from `@/components/admin/users-table` — the interface is in the same file, so no import change needed.

Verify the page still works by checking the updated interface:
```tsx
// frontend/app/(main)/admin/users/page.tsx — no changes needed
// The page passes users down to UsersTable which now handles the richer interface
```

- [ ] **Step 4: Commit**

```bash
git add frontend/lib/api-client.ts frontend/components/admin/users-table.tsx
git commit -m "feat(ui): redesign users table with action menu, status column, create/edit/delete modals"
```

---

### Task 7: Frontend Tests

**Files:**
- Create: `frontend/components/admin/__tests__/user-form-modal.test.tsx`
- Create: `frontend/components/admin/__tests__/delete-confirm-dialog.test.tsx`
- Modify: `frontend/components/admin/__tests__/adjust-modal.test.tsx` (if needed)

- [ ] **Step 1: Create UserFormModal test**

Create `frontend/components/admin/__tests__/user-form-modal.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { UserFormModal } from "../user-form-modal";

vi.mock("@/lib/api-client", () => ({
  apiClient: {
    post: vi.fn().mockResolvedValue({ id: "new-id" }),
    put: vi.fn().mockResolvedValue({ id: "edit-id" }),
  },
}));

describe("UserFormModal", () => {
  const onClose = vi.fn();
  const onSubmitted = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("creates a user successfully", async () => {
    const { apiClient } = await import("@/lib/api-client");
    render(
      <UserFormModal open={true} onClose={onClose} onSubmitted={onSubmitted} />
    );

    fireEvent.change(screen.getByLabelText("用户名"), { target: { value: "newuser" } });
    fireEvent.change(screen.getByLabelText("密码"), { target: { value: "pass123" } });
    fireEvent.click(screen.getByText("创建"));

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith("/api/admin/users", {
        username: "newuser",
        password: "pass123",
        is_admin: false,
      });
      expect(onSubmitted).toHaveBeenCalled();
    });
  });

  it("edits a user successfully", async () => {
    const { apiClient } = await import("@/lib/api-client");
    render(
      <UserFormModal
        userId="user-1"
        username="alice"
        currentIsAdmin={false}
        open={true}
        onClose={onClose}
        onSubmitted={onSubmitted}
      />
    );

    fireEvent.change(screen.getByLabelText("用户名"), { target: { value: "alice_updated" } });
    fireEvent.click(screen.getByText("保存"));

    await waitFor(() => {
      expect(apiClient.put).toHaveBeenCalledWith("/api/admin/users/user-1", {
        username: "alice_updated",
      });
      expect(onSubmitted).toHaveBeenCalled();
    });
  });

  it("rejects empty username on create", async () => {
    render(
      <UserFormModal open={true} onClose={onClose} onSubmitted={onSubmitted} />
    );

    fireEvent.change(screen.getByLabelText("密码"), { target: { value: "pass123" } });
    fireEvent.click(screen.getByText("创建"));

    expect(onSubmitted).not.toHaveBeenCalled();
    expect(screen.getByText("请输入用户名")).toBeInTheDocument();
  });

  it("rejects empty password on create", async () => {
    render(
      <UserFormModal open={true} onClose={onClose} onSubmitted={onSubmitted} />
    );

    fireEvent.change(screen.getByLabelText("用户名"), { target: { value: "newuser" } });
    fireEvent.click(screen.getByText("创建"));

    expect(onSubmitted).not.toHaveBeenCalled();
    expect(screen.getByText("请输入密码")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Create DeleteConfirmDialog test**

Create `frontend/components/admin/__tests__/delete-confirm-dialog.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { DeleteConfirmDialog } from "../delete-confirm-dialog";

vi.mock("@/lib/api-client", () => ({
  apiClient: {
    delete: vi.fn().mockResolvedValue(undefined),
  },
}));

describe("DeleteConfirmDialog", () => {
  const onClose = vi.fn();
  const onDeleted = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("confirms deletion", async () => {
    const { apiClient } = await import("@/lib/api-client");
    render(
      <DeleteConfirmDialog
        userId="user-1"
        username="alice"
        open={true}
        onClose={onClose}
        onDeleted={onDeleted}
      />
    );

    expect(screen.getByText(/alice/)).toBeInTheDocument();
    fireEvent.click(screen.getByText("确认删除"));

    await waitFor(() => {
      expect(apiClient.delete).toHaveBeenCalledWith("/api/admin/users/user-1");
      expect(onDeleted).toHaveBeenCalled();
    });
  });

  it("cancels deletion", async () => {
    render(
      <DeleteConfirmDialog
        userId="user-1"
        username="alice"
        open={true}
        onClose={onClose}
        onDeleted={onDeleted}
      />
    );

    fireEvent.click(screen.getByText("取消"));
    expect(onClose).toHaveBeenCalled();
    expect(onDeleted).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 3: Run all frontend tests**

```bash
cd frontend
pnpm test
```

Expected: All tests PASS (existing adjust-modal tests + new tests)

- [ ] **Step 4: Commit**

```bash
git add frontend/components/admin/__tests__/
git commit -m "test: frontend UserFormModal and DeleteConfirmDialog tests"
```

---

### Task 8: Self-Review and End-to-End Verification

- [ ] **Step 1: Run backend full test suite**

```bash
cd backend
pytest -v
```

Expected: All existing + new tests PASS (≈15 tests)

- [ ] **Step 2: Run frontend full test suite**

```bash
cd frontend
pnpm test
```

Expected: All tests PASS

- [ ] **Step 3: Verify the `AdminUserItem` → `AdminUserDetail` migration**

```bash
# Check that AdminUserItem is no longer imported/used anywhere
grep -r "AdminUserItem" backend/app/ --include="*.py"
```

Expected: No references remain (replaced by AdminUserDetail)

- [ ] **Step 4: Verify import consistency for CreditTransaction in admin.py**

```bash
# Check that admin.py imports CreditTransaction for list_users
grep -n "CreditTransaction" backend/app/api/admin.py
```

Expected: Import present and used in `list_users`, `update_user`, `toggle_user_status`

- [ ] **Step 5: Commit any final fixes**

```bash
git add -A
git commit -m "chore: post-implementation cleanup and verification"
```
