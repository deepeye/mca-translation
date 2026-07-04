# 管理员用户管理功能增强

## 概述

在现有只支持"信用分调整"的 admin 用户管理页面上，增加用户创建、编辑、禁用/启用、逻辑删除功能。

## 数据模型变更

### User 模型新增字段

```python
# backend/app/models/user.py
class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(128))
    credit_balance: Mapped[int] = mapped_column(Integer, default=1000, server_default="1000")
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")  # 🆕 禁用/启用
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # 🆕 逻辑删除时间
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

- `is_active=False` → 账号被禁用，无法登录，可恢复
- `deleted_at IS NOT NULL` → 账号已被逻辑删除，等同于不存在，登录返回"账号不存在"
- 需生成一次 Alembic migration

## 登录检查变更

`POST /api/auth/login` 增加状态检查逻辑：

| 条件 | 返回 |
|---|---|
| 用户不存在或密码错误 | 401 "Invalid credentials" |
| `deleted_at IS NOT NULL` | 401 "Invalid credentials"（与不存在一致，不泄露账号存在性） |
| `is_active=False` | 403 "账号已被禁用，请联系管理员" |
| 正常 | 200 + JWT |

## 后端 API 端点

全部放在 `backend/app/api/admin.py`，使用 `require_admin` 保护。

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/admin/users` | 列表用户（已有，增加 `is_active` 字段，过滤 `deleted_at IS NULL`） |
| `POST` | `/api/admin/users` | 🆕 创建用户 |
| `PUT` | `/api/admin/users/{user_id}` | 🆕 更新用户信息 |
| `DELETE` | `/api/admin/users/{user_id}` | 🆕 逻辑删除用户 |
| `PATCH` | `/api/admin/users/{user_id}/status` | 🆕 禁用/启用用户 |
| `POST` | `/api/admin/users/{user_id}/credits` | 调整信用分（已有） |
| `GET` | `/api/admin/transactions` | 交易记录（已有） |

### POST /api/admin/users 创建用户

```json
// Request
{ "username": "string", "password": "string", "is_admin": false }
// Response 201
{ "id": "uuid", "username": "string", "is_admin": false, "credit_balance": 1000, "is_active": true, "created_at": "..." }
```

- 校验用户名唯一性，重复返回 409
- 密码用 `get_password_hash` 加密，Pydantic validator 校验 >= 6 位
- `is_admin` 默认 false
- 新用户默认 `credit_balance=1000`，`is_active=true`

### PUT /api/admin/users/{user_id} 更新用户

```json
// Request（全部可选）
{ "username": "string", "password": "string", "is_admin": true }
// Response 200 更新后的 AdminUserDetail
```

- 只传入的字段才更新
- 密码为空串或未传时不更新密码
- 不允许更新自己的 `is_admin` 为 false（防止管理员自降权限）

### DELETE /api/admin/users/{user_id} 逻辑删除

- 设置 `deleted_at = now()`，不清除任何数据
- 不允许删除自己，返回 409
- 返回 204 No Content

### PATCH /api/admin/users/{user_id}/status 禁用/启用

```json
// Request
{ "is_active": false }
// Response 200
{ "id": "...", "is_active": false }
```

- 不允许禁用自己
- 不允许禁用一个已逻辑删除的用户

### 新增 Schema

`backend/app/schemas/admin.py`:

```python
class CreateUserRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=6, max_length=128)
    is_admin: bool = False

class UpdateUserRequest(BaseModel):
    username: str | None = Field(None, min_length=1, max_length=64)
    password: str | None = Field(None, min_length=6, max_length=128)
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

现有 `AdminUserItem` 废弃，统一用 `AdminUserDetail`。

`GET /api/admin/users` 列表查询需增加 `.where(User.deleted_at.is_(None))` 过滤，被逻辑删除的用户不在列表中显示。

## 前端组件设计

### 页面结构变化

```
┌─────────────────────────────────────────────┐
│  用户管理                          [＋创建用户] │
├─────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────┐│
│  │ 用户名 │ 角色  │ 余额  │ 状态  │ 活跃  │ 操作 ││
│  ├─────────────────────────────────────────┤│
│  │ Alice  │ 管理员 │ 1500  │ 正常  │ ...  │ ⋮  ││
│  │ Bob    │ 普通   │ 200   │ 已禁用│ ...  │ ⋮  ││
│  └─────────────────────────────────────────┘│
└─────────────────────────────────────────────┘
```

### 新增组件

| 组件 | 用途 |
|---|---|
| `UserFormModal` | 创建/编辑用户共用一个模态框，创建时所有字段必填，编辑时密码可选 |
| `DeleteConfirmDialog` | 删除确认弹窗，显示"确定要删除用户 XXX 吗？此操作不可恢复" |
| `ActionMenu` | 表格操作列的 DropdownMenu，整合调整/编辑/禁用/删除 |

### 操作列 DropdownMenu

每一行末尾显示 `⋮` 按钮，展开下拉菜单：

```
调整余额    → 打开 AdjustModal（现有）
编辑        → 打开 UserFormModal（编辑模式）
─────────────────
禁用/启用    → 直接调 PATCH 切换状态
删除        → 打开 DeleteConfirmDialog
```

### 状态列

表格新增"状态"列，与操作联动：

| `is_active` | `deleted_at` | 显示 |
|---|---|---|
| true | null | 正常 |
| false | null | 已禁用 |
| — | not null | 已删除（灰色文字） |

### 错误提示

- 权限错误：后端 403 时前端跳转 `/workspace`（已有）
- 后端 409（用户名重复/删除自己/禁用自己）：用 `toast` 显示具体错误信息

## 边界情况处理

| 场景 | 处理 |
|---|---|
| 管理员试图删除自己 | 409 + 提示"不能删除当前登录的管理员" |
| 管理员试图禁用自己 | 409 + 提示"不能禁用当前登录的管理员" |
| 管理员修改自己 is_admin 为 false | 409 + 提示"不能移除自己的管理员权限" |
| 用户名已存在 | 409 + toast 提示 |
| 禁用已禁用的用户 | 幂等，返回成功 |
| 删除已删除的用户 | 404（已逻辑删除的用户无法通过查询找到） |
| 更新/操作已删除的用户 | 404（同上） |
| 禁用已删除的用户 | 404 |
| 密码太短 | 422 + 表单验证错误 |
| 更新用户时传入空用户名 | 422（min_length 校验） |

## 测试

| 范围 | 测试内容 |
|---|---|
| 后端 | 创建用户成功/重复/密码过短 |
| 后端 | 更新用户各字段 |
| 后端 | 删除用户（删除自己/删除他人/重新查询确认 deleted_at） |
| 后端 | 禁用/启用用户（禁用自己/禁用已禁用/启用已启用） |
| 后端 | 登录时 is_active=false 被 403 |
| 后端 | 登录时 deleted 用户被 401 |
| 后端 | 非管理员无法调用新端点（403） |
| 前端 | 创建用户表单提交成功/失败 |
| 前端 | 编辑用户表单提交成功/失败 |
| 前端 | 删除确认→取消/确认 |
| 前端 | 禁用/启用后表格状态列刷新 |
| 前端 | 非管理员看不到"管理"导航链接 |

## 实施顺序

1. 数据库迁移：添加 `is_active` 和 `deleted_at` 字段
2. 后端 Schema：新建 `schemas/admin.py`
3. 后端 API：新增 3 个端点（创建/更新/删除/状态切换）+ 修改登录检查
4. 后端测试
5. 前端组件：`UserFormModal` + `DeleteConfirmDialog` + 操作列改造
6. 前端页面：集成新组件，改造现有表格
7. 自查 + 冒烟测试
