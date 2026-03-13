import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


def _validate_strong_password(v: str) -> str:
    """强密码：至少8位，含大小写字母、数字、特殊字符"""
    if len(v) < 8:
        raise ValueError("密码至少8位")
    if not any(c.isupper() for c in v):
        raise ValueError("密码须包含至少1个大写字母")
    if not any(c.islower() for c in v):
        raise ValueError("密码须包含至少1个小写字母")
    if not any(c.isdigit() for c in v):
        raise ValueError("密码须包含至少1个数字")
    special = re.compile(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>/?`~]")
    if not special.search(v):
        raise ValueError("密码须包含至少1个特殊字符（如 !@#$%^&* 等）")
    return v


class UserBase(BaseModel):
    username: str = Field(..., min_length=1, max_length=50, description="用户名，仅用于登录后显示")
    email: Optional[EmailStr] = Field(None, description="邮箱，登录时必填")


class UserCreate(UserBase):
    email: EmailStr = Field(..., description="邮箱，登录时必填")
    password: str = Field(..., min_length=8, max_length=128)
    is_superuser: bool = False  # 仅管理员创建账号时可指定
    department_id: Optional[int] = None

    @field_validator("password")
    @classmethod
    def password_strong(cls, v: str) -> str:
        return _validate_strong_password(v)


class UserRead(UserBase):
    id: int
    is_active: bool
    is_superuser: bool
    created_at: datetime
    department_id: Optional[int] = None
    department_name: Optional[str] = None
    is_department_leader: bool = False

    class Config:
        from_attributes = True


class ChangePassword(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_strong(cls, v: str) -> str:
        return _validate_strong_password(v)


class UserUpdate(BaseModel):
    """管理员更新用户：禁用/启用、重置密码、所属部门"""
    is_active: Optional[bool] = None
    new_password: Optional[str] = Field(None, min_length=8, max_length=128)
    department_id: Optional[int] = None

    @field_validator("new_password")
    @classmethod
    def password_strong(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return v
        return _validate_strong_password(v)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: str  # username
    exp: int

