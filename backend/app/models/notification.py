from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text

from backend.app.db.base import Base


class Notification(Base):
    """站内通知：发送给指定用户的提示消息。"""

    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # info / success / warning / error
    type = Column(String(20), nullable=False, default="info")
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)

    is_read = Column(Boolean, nullable=False, default=False, index=True)

    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )


class NotificationTemplate(Base):
    """通知模板（用于系统级通知配置）。"""

    __tablename__ = "notification_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    type = Column(String(50), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    enabled = Column(Boolean, nullable=False, default=True)
    # 发送渠道：逗号分隔，例如 "system,email"
    channels = Column(String(100), nullable=False, default="system")
    icon = Column(String(10), nullable=True)
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class NotificationSendLog(Base):
    """通知发送历史汇总记录。"""

    __tablename__ = "notification_send_logs"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    target = Column(String(50), nullable=False)  # all | department | custom
    target_value = Column(String(100), nullable=True)  # 如部门 ID 列表 / 用户 ID 列表
    channels = Column(String(100), nullable=False, default="system")
    recipients = Column(Integer, nullable=False, default=0)
    status = Column(String(20), nullable=False, default="sent")
    sent_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True
    )


class NotificationSetting(Base):
    """通知开关设置（当前为全局配置，后续可扩展到用户级）。"""

    __tablename__ = "notification_settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(50), nullable=False, unique=True, index=True)
    category = Column(String(50), nullable=False)
    name = Column(String(100), nullable=False)
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
