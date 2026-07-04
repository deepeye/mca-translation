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
