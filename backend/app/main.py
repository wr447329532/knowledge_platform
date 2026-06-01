from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import or_

from backend.app.api import audit, auth, departments, division_leader, file_comments, files, libraries, notifications
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


def _ensure_users_has_role() -> None:
    """兼容旧库：若 users 表缺少 role 列则自动添加，默认 staff"""
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    if "users" not in insp.get_table_names():
        return
    cols = [c["name"] for c in insp.get_columns("users")]
    if "role" in cols:
        return
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'staff'"))
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


def _ensure_libraries_has_visibility() -> None:
    """兼容旧库：若 libraries 表缺少 visibility 列则自动添加，默认 private"""
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    if "libraries" not in insp.get_table_names():
        return
    cols = [c["name"] for c in insp.get_columns("libraries")]
    if "visibility" in cols:
        return
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE libraries ADD COLUMN visibility VARCHAR(20) NOT NULL DEFAULT 'private'"))
        conn.commit()


def _ensure_libraries_has_allow_download() -> None:
    """兼容旧库：若 libraries 表缺少 allow_download 列则自动添加；历史行默认 True，新建资料库由接口默认 False"""
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    if "libraries" not in insp.get_table_names():
        return
    cols = [c["name"] for c in insp.get_columns("libraries")]
    if "allow_download" in cols:
        return
    with engine.connect() as conn:
        conn.execute(
            text("ALTER TABLE libraries ADD COLUMN allow_download BOOLEAN NOT NULL DEFAULT 1")
        )
        conn.commit()


def _ensure_libraries_has_deleted_at() -> None:
    """兼容旧库：若 libraries 表缺少 deleted_at 列则自动添加（软删除用）"""
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    if "libraries" not in insp.get_table_names():
        return
    cols = [c["name"] for c in insp.get_columns("libraries")]
    if "deleted_at" in cols:
        return
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE libraries ADD COLUMN deleted_at DATETIME"))
        conn.commit()


def _ensure_departments_has_leader_user_id() -> None:
    """兼容旧库：若 departments 表缺少 leader_user_id 列则自动添加"""
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    if "departments" not in insp.get_table_names():
        return
    cols = [c["name"] for c in insp.get_columns("departments")]
    if "leader_user_id" in cols:
        return
    with engine.connect() as conn:
        conn.execute(
            text("ALTER TABLE departments ADD COLUMN leader_user_id INTEGER REFERENCES users(id)")
        )
        conn.commit()


def _ensure_audit_logs_has_ip_address() -> None:
    """兼容旧库：若 audit_logs 表缺少 ip_address 列则自动添加"""
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    if "audit_logs" not in insp.get_table_names():
        return
    cols = [c["name"] for c in insp.get_columns("audit_logs")]
    if "ip_address" in cols:
        return
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE audit_logs ADD COLUMN ip_address VARCHAR(45)"))
        conn.commit()


def _ensure_notifications_has_resource_fields() -> None:
    """兼容旧库：notifications 表补充评论跳转相关字段"""
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    if "notifications" not in insp.get_table_names():
        return
    cols = [c["name"] for c in insp.get_columns("notifications")]
    with engine.connect() as conn:
        if "resource_type" not in cols:
            conn.execute(text("ALTER TABLE notifications ADD COLUMN resource_type VARCHAR(32)"))
        if "resource_id" not in cols:
            conn.execute(text("ALTER TABLE notifications ADD COLUMN resource_id INTEGER"))
        if "extra_json" not in cols:
            conn.execute(text("ALTER TABLE notifications ADD COLUMN extra_json TEXT"))
        conn.commit()


def _ensure_default_admin(reset_password_on_startup: bool = False) -> None:
    """启动时确保存在默认管理员。默认不重置既有账号密码。"""
    db = SessionLocal()
    try:
        # 兼容：如果已经存在 admin@example.com，则复用该账号并规范为 admin
        user = (
            db.query(User)
            .filter(or_(User.username == DEFAULT_ADMIN_USERNAME, User.email == "admin@example.com"))
            .first()
        )
        if user:
            if reset_password_on_startup:
                user.hashed_password = get_password_hash(DEFAULT_ADMIN_PASSWORD)
            # 仅确保管理员能力，不覆盖用户名/邮箱等用户已维护信息
            user.is_superuser = True
            user.is_active = True
        else:
            user = User(
                username=DEFAULT_ADMIN_USERNAME,
                email="admin@example.com",
                hashed_password=get_password_hash(DEFAULT_ADMIN_PASSWORD),
                is_active=True,
                is_superuser=True,
            )
            db.add(user)
        db.commit()
    finally:
        db.close()


def _ensure_db_at_alembic_head(database_url: str) -> None:
    """校验数据库 revision 必须位于 Alembic head。"""
    from alembic.config import Config
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory

    repo_root = Path(__file__).resolve().parents[2]
    alembic_ini = repo_root / "alembic.ini"
    if not alembic_ini.exists():
        raise RuntimeError("未找到 alembic.ini，无法校验数据库迁移版本。")

    cfg = Config(str(alembic_ini))
    cfg.set_main_option("sqlalchemy.url", database_url)
    script = ScriptDirectory.from_config(cfg)
    heads = set(script.get_heads())
    if not heads:
        return

    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        current = ctx.get_current_revision()

    if current not in heads:
        heads_str = ", ".join(sorted(heads))
        current_str = current or "None"
        raise RuntimeError(
            f"数据库迁移版本不一致：current={current_str}, head={heads_str}。"
            "请先执行 `alembic upgrade head` 后再启动服务。"
        )


def create_app() -> FastAPI:
    """
    创建并配置 FastAPI 应用实例。

    - 初始化数据库（自动创建表，后续可替换为 Alembic 迁移）
    - 确保默认管理员账号存在（admin / admin123）
    - 挂载路由（用户 / 权限 / 文件等）
    """
    settings = get_settings()

    # 强制要求在部署环境中配置真实的 JWT_SECRET_KEY，避免使用默认示例值带来安全风险
    if settings.JWT_SECRET_KEY == "change_this_secret_in_env":
        raise RuntimeError("请在 .env 中设置真实的 JWT_SECRET_KEY（不可使用默认示例值）")

    # 数据库初始化与兼容补丁（开发期默认开启；生产建议关闭并使用 Alembic）
    if settings.DB_AUTO_CREATE_TABLES_ON_STARTUP:
        Base.metadata.create_all(bind=engine)
    if settings.DB_COMPAT_PATCH_ON_STARTUP:
        _ensure_file_entries_has_deleted_at()
        _ensure_users_has_department_id()
        _ensure_users_has_role()
        _ensure_libraries_has_department_id()
        _ensure_libraries_has_visibility()
        _ensure_libraries_has_allow_download()
        _ensure_libraries_has_deleted_at()
        _ensure_departments_has_leader_user_id()
        _ensure_audit_logs_has_ip_address()
        _ensure_notifications_has_resource_fields()
    if settings.BOOTSTRAP_DEFAULT_ADMIN:
        _ensure_default_admin(
            reset_password_on_startup=settings.RESET_DEFAULT_ADMIN_PASSWORD_ON_STARTUP
        )
    # 生产环境（通常关闭自动建表）强制要求 DB revision 与 Alembic head 一致。
    if (not settings.DB_AUTO_CREATE_TABLES_ON_STARTUP) or settings.REQUIRE_ALEMBIC_HEAD_ON_STARTUP:
        _ensure_db_at_alembic_head(settings.DATABASE_URL)

    app = FastAPI(
        title=settings.PROJECT_NAME,
        description=settings.PROJECT_DESC,
        version=settings.VERSION,
    )

    cors_origins = settings.cors_allow_origins_list()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins if cors_origins else [],
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
    app.include_router(file_comments.router)
    app.include_router(audit.router)
    app.include_router(departments.router)
    app.include_router(division_leader.router)
    app.include_router(notifications.router)

    return app


app = create_app()

