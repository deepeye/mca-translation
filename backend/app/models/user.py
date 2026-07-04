import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(128))
    # 信用分余额：1 字符 = 1 信用分；默认 1000
    credit_balance: Mapped[int] = mapped_column(Integer, default=1000, server_default="1000")
    # 管理员角色标记
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # 禁用/启用标记
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    # 逻辑删除时间戳，非空=已删除
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
