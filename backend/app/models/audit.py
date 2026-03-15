from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from backend.app.db.base import Base


class AuditLog(Base):
    """操作审计日志：谁、何时、对何资源、执行了何种操作"""

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    username = Column(String(50), nullable=True)  # 冗余，便于用户改名后仍可追溯

    action = Column(String(32), nullable=False, index=True)  # upload, download, delete, restore, permanent_delete, create_library, mkdir, login, register
    resource_type = Column(String(32), nullable=True)  # file, library
    resource_id = Column(Integer, nullable=True)
    detail = Column(Text, nullable=True)  # 如 path, library_id 等简要信息
    ip_address = Column(String(45), nullable=True)  # 支持 IPv4 和 IPv6

    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
