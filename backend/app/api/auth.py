from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user, get_current_active_superuser
from backend.app.core.audit import log_audit
from backend.app.core.security import create_access_token, get_password_hash, verify_password
from backend.app.db.session import get_db
from backend.app.models.user import User
from backend.app.schemas.auth import ChangePassword, Token, UserCreate, UserRead, UserUpdate


router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=UserRead)
def get_me(current_user: User = Depends(get_current_user)):
    """获取当前登录用户信息。用户名 admin 的账号始终视为管理员（与权限校验一致）。"""
    # 保证前端拿到的 is_superuser 与后端权限一致，写死的 admin 账号恒为管理员
    is_superuser = current_user.username == "admin" or current_user.is_superuser
    # 兼容旧数据：admin@local 不符合 EmailStr，统一返回合法邮箱
    email = current_user.email if current_user.email not in ("admin@local", "admin@localhost") else "admin@example.com"
    return UserRead(
        id=current_user.id,
        username=current_user.username,
        email=email,
        is_active=current_user.is_active,
        is_superuser=is_superuser,
        created_at=current_user.created_at,
    )


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
    user = User(
        username=user_in.username,
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        is_active=True,
        is_superuser=user_in.is_superuser,
    )
    db.add(user)
    db.flush()
    log_audit(db, current_user.id, current_user.username, "create_user", "user", user.id, f"created={user_in.username}")
    db.commit()
    db.refresh(user)
    return user


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
    access_token = create_access_token(subject=user.username)
    return Token(access_token=access_token)


@router.get("/users", response_model=List[UserRead])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
):
    """仅管理员：列出所有用户"""
    users = db.query(User).order_by(User.id.asc()).all()
    return users


@router.patch("/users/{user_id}", response_model=UserRead)
def update_user(
    user_id: int,
    body: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
):
    """仅管理员：禁用/启用用户、重置密码。不能禁用自己。"""
    user = db.query(User).filter(User.id == user_id).first()
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
    db.commit()
    db.refresh(user)
    return user

