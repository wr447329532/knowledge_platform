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

    # 文件存储根目录
    STORAGE_ROOT: Path = Path(__file__).resolve().parents[3] / "storage"

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()

