from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api import audit, auth, departments, files, libraries
from backend.app.core.config import get_settings
from backend.app.core.security import get_password_hash
from backend.app.db.base import Base
from backend.app.db.session import SessionLocal, engine
from backend.app.models.user import User

# 写死默认管理员账号（首次启动或不存在时自动创建）
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin123"


def _ensure_file_entries_has_deleted_at() -> None:
    """兼容旧库：若 file_entries 表缺少 deleted_at 列则自动添加"""
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    if "file_entries" not in insp.get_table_names():
        return
    cols = [c["name"] for c in insp.get_columns("file_entries")]
    if "deleted_at" in cols:
        return
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE file_entries ADD COLUMN deleted_at DATETIME"))
        conn.commit()


def _ensure_users_has_department_id() -> None:
    """兼容旧库：若 users 表缺少 department_id 列则自动添加"""
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    if "users" not in insp.get_table_names():
        return
    cols = [c["name"] for c in insp.get_columns("users")]
    if "department_id" in cols:
        return
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE users ADD COLUMN department_id INTEGER REFERENCES departments(id)"))
        conn.commit()


def _ensure_libraries_has_department_id() -> None:
    """兼容旧库：若 libraries 表缺少 department_id 列则自动添加"""
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    if "libraries" not in insp.get_table_names():
        return
    cols = [c["name"] for c in insp.get_columns("libraries")]
    if "department_id" in cols:
        return
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE libraries ADD COLUMN department_id INTEGER REFERENCES departments(id)"))
        conn.commit()


def _ensure_default_admin() -> None:
    """启动时确保存在默认管理员：用户名 admin，密码 admin123"""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == DEFAULT_ADMIN_USERNAME).first()
        pwd_hash = get_password_hash(DEFAULT_ADMIN_PASSWORD)
        if user:
            user.hashed_password = pwd_hash
            user.email = "admin@example.com"
            user.is_superuser = True
            user.is_active = True
        else:
            user = User(
                username=DEFAULT_ADMIN_USERNAME,
                email="admin@example.com",
                hashed_password=pwd_hash,
                is_active=True,
                is_superuser=True,
            )
            db.add(user)
        db.commit()
    finally:
        db.close()


def create_app() -> FastAPI:
    """
    创建并配置 FastAPI 应用实例。

    - 初始化数据库（自动创建表，后续可替换为 Alembic 迁移）
    - 确保默认管理员账号存在（admin / admin123）
    - 挂载路由（用户 / 权限 / 文件等）
    """
    settings = get_settings()

    # 初始化数据库表（开发期使用，生产建议使用迁移工具）
    Base.metadata.create_all(bind=engine)
    _ensure_file_entries_has_deleted_at()
    _ensure_users_has_department_id()
    _ensure_libraries_has_department_id()
    _ensure_default_admin()

    app = FastAPI(
        title=settings.PROJECT_NAME,
        description=settings.PROJECT_DESC,
        version=settings.VERSION,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["system"])
    async def health_check():
        return {"status": "ok"}

    # 注册路由
    app.include_router(auth.router)
    app.include_router(libraries.router)
    app.include_router(files.router)
    app.include_router(audit.router)
    app.include_router(departments.router)

    return app


app = create_app()

