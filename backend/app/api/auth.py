from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from backend.app.api.deps import get_current_user, get_current_active_superuser
from backend.app.core.audit import log_audit
from backend.app.core.security import create_access_token, get_password_hash, verify_password
from backend.app.db.session import get_db
from backend.app.models.department import Department
from backend.app.models.user import User
from backend.app.schemas.auth import ChangePassword, Token, UserCreate, UserRead, UserUpdate


router = APIRouter(prefix="/auth", tags=["auth"])


class ProfileUpdate(BaseModel):
    """当前用户自助修改的基本资料（仅允许修改用户名用于显示）。"""

    username: Optional[str] = Field(None, min_length=1, max_length=50, description="显示名称")


def _user_to_read(user: User, is_superuser_override: bool | None = None) -> UserRead:
    """将 User ORM 转为 UserRead，兼容邮箱与部门。"""
    is_superuser = is_superuser_override if is_superuser_override is not None else (user.username == "admin" or user.is_superuser)
    email = user.email if user.email and user.email not in ("admin@local", "admin@localhost") else "admin@example.com"
    dept_name = user.department.name if getattr(user, "department", None) and user.department else None
    return UserRead(
        id=user.id,
        username=user.username,
        email=email,
        is_active=user.is_active,
        is_superuser=is_superuser,
        created_at=user.created_at,
        department_id=user.department_id,
        department_name=dept_name,
        is_department_leader=False,
    )


@router.get("/me", response_model=UserRead)
def get_me(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前登录用户信息。用户名 admin 的账号始终视为管理员（与权限校验一致）。"""
    is_super = current_user.username == "admin" or current_user.is_superuser
    # 计算是否为任一部门负责人
    is_leader = (
        db.query(Department)
        .filter(Department.leader_user_id == current_user.id)
        .first()
        is not None
    )
    user_read = _user_to_read(current_user, is_superuser_override=is_super)
    user_read.is_department_leader = is_leader
    return user_read


@router.patch("/me", response_model=Token)
def update_me(
    profile_in: ProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新当前登录用户的基础资料（目前仅支持修改用户名）。"""
    if profile_in.username is not None:
        username = profile_in.username.strip()
        if not username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="姓名不能为空",
            )
        current_user.username = username
    db.commit()
    db.refresh(current_user)
    # 以 user.id 作为 JWT 的 subject，修改用户名不会导致 Token 失效
    access_token = create_access_token(subject=str(current_user.id))
    return Token(access_token=access_token)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    body: ChangePassword,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """修改当前用户密码"""
    if not verify_password(body.old_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="原密码错误",
        )
    current_user.hashed_password = get_password_hash(body.new_password)
    db.commit()
    log_audit(db, current_user.id, current_user.username, "change_password", "user", current_user.id, None)


@router.post("/register", response_model=UserRead)
def register(
    user_in: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
):
    """仅管理员可调用：创建新用户账号（平台不支持开放注册）"""
    existing = (
        db.query(User)
        .filter((User.username == user_in.username) | (User.email == user_in.email))
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名或邮箱已被使用",
        )
    if user_in.department_id is not None:
        dept = db.query(Department).filter(Department.id == user_in.department_id).first()
        if not dept:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="所选部门不存在")
    user = User(
        username=user_in.username,
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        is_active=True,
        is_superuser=user_in.is_superuser,
        department_id=user_in.department_id,
    )
    db.add(user)
    db.flush()
    log_audit(db, current_user.id, current_user.username, "create_user", "user", user.id, f"created={user_in.username}")
    db.commit()
    db.refresh(user)
    return _user_to_read(user)


@router.post("/login", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    # 使用邮箱登录（OAuth2 的 username 字段用于填写邮箱）
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邮箱或密码错误",
        )
    log_audit(db, user.id, user.username, "login", "user", user.id, None)
    db.commit()
    # 以 user.id 作为 JWT 的 subject，避免后续用户名修改导致 Token 失效
    access_token = create_access_token(subject=str(user.id))
    return Token(access_token=access_token)


@router.get("/users", response_model=List[UserRead])
def list_users(
    search: Optional[str] = Query(None, description="按用户名或邮箱模糊搜索"),
    is_active: Optional[bool] = Query(None, description="按状态筛选：true=活跃，false=停用"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
):
    """仅管理员：列出用户，支持按关键词、状态筛选"""
    q = db.query(User).options(joinedload(User.department)).order_by(User.id.asc())
    if search and search.strip():
        term = f"%{search.strip()}%"
        q = q.filter(or_(User.username.ilike(term), User.email.ilike(term)))
    if is_active is not None:
        q = q.filter(User.is_active == is_active)
    users = q.all()
    return [_user_to_read(u) for u in users]


@router.get("/users/active", response_model=List[UserRead])
def list_active_users_for_library(
    search: Optional[str] = Query(None, description="按用户名或邮箱模糊搜索"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    列出当前系统中的活跃用户，用于资料库成员选择。
    所有登录用户均可调用，仅返回活跃账号的基础信息。
    """
    q = (
        db.query(User)
        .options(joinedload(User.department))
        .filter(User.is_active == True)  # noqa: E712
        .order_by(User.id.asc())
    )
    if search and search.strip():
        term = f"%{search.strip()}%"
        q = q.filter(or_(User.username.ilike(term), User.email.ilike(term)))
    users = q.all()
    return [_user_to_read(u) for u in users]


@router.patch("/users/{user_id}", response_model=UserRead)
def update_user(
    user_id: int,
    body: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
):
    """仅管理员：禁用/启用用户、重置密码、修改所属部门。不能禁用自己。"""
    user = db.query(User).options(joinedload(User.department)).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    if body.is_active is False and user.id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能禁用自己")
    if body.is_active is not None:
        user.is_active = body.is_active
        log_audit(db, current_user.id, current_user.username, "update_user", "user", user.id, f"is_active={body.is_active}")
    if body.new_password is not None:
        user.hashed_password = get_password_hash(body.new_password)
        log_audit(db, current_user.id, current_user.username, "reset_password", "user", user.id, f"target={user.username}")
    if body.department_id is not None:
        if body.department_id == 0:
            user.department_id = None
        else:
            dept = db.query(Department).filter(Department.id == body.department_id).first()
            if not dept:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="所选部门不存在")
            user.department_id = body.department_id
        log_audit(db, current_user.id, current_user.username, "update_user", "user", user.id, f"department_id={user.department_id}")
    db.commit()
    db.refresh(user)
    return _user_to_read(user)

