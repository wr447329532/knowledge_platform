from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """全局配置（可从环境变量或 .env 中读取）"""

    PROJECT_NAME: str = "文件共享和知识管理平台后端"
    PROJECT_DESC: str = "从 0 开发的文件共享和知识管理平台后端服务"
    VERSION: str = "0.1.0"

    # 数据库：默认使用本地 SQLite（放在项目根目录，SQLite 可自动创建文件）
    DATABASE_URL: str = f"sqlite:///{Path(__file__).resolve().parents[3] / 'app.db'}"

    # JWT 设置（简单版本）
    JWT_SECRET_KEY: str = "change_this_secret_in_env"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 天
    # CORS 白名单，逗号分隔。生产环境请改为实际前端地址（域名或 IP）。
    CORS_ALLOW_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    # 是否在启动时自动确保默认 admin 存在
    BOOTSTRAP_DEFAULT_ADMIN: bool = True
    # 是否在每次启动时重置默认 admin 密码（生产建议关闭）
    RESET_DEFAULT_ADMIN_PASSWORD_ON_STARTUP: bool = False

    # 文件存储根目录
    STORAGE_ROOT: Path = Path(__file__).resolve().parents[3] / "storage"

    # 系统级总存储配额（字节），用于统计视角的“系统总容量”。
    # 默认 500GB，可通过环境变量 STORAGE_SYSTEM_TOTAL_BYTES 或 STORAGE_SYSTEM_TOTAL_GB 覆盖。
    STORAGE_SYSTEM_TOTAL_BYTES: int = 500 * 1024 * 1024 * 1024
    # 数据库初始化策略（开发默认开启；生产建议关闭，改用 Alembic）
    DB_AUTO_CREATE_TABLES_ON_STARTUP: bool = True
    DB_COMPAT_PATCH_ON_STARTUP: bool = True
    # 启动时是否强制校验数据库 revision 必须等于 Alembic head。
    # 若 DB_AUTO_CREATE_TABLES_ON_STARTUP=false（生产推荐），后端会自动执行该校验。
    REQUIRE_ALEMBIC_HEAD_ON_STARTUP: bool = False

    class Config:
        env_file = ".env"
        case_sensitive = True

    def cors_allow_origins_list(self) -> list[str]:
        raw = (self.CORS_ALLOW_ORIGINS or "").strip()
        if not raw:
            return []
        return [item.strip() for item in raw.split(",") if item.strip()]


@lru_cache()
def get_settings() -> Settings:
    return Settings()

