"""文件级共享：单个文件可分享给指定用户，权限为 read（只读/预览）或 download（可下载）"""
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import backref, relationship

from backend.app.db.base import Base


class FileShare(Base):
    """文件共享：用户 A 将某文件分享给用户 B，指定权限"""

    __tablename__ = "file_shares"

    id = Column(Integer, primary_key=True, index=True)
    file_entry_id = Column(Integer, ForeignKey("file_entries.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    # permission: read 只读（可见/预览，不可下载）；download 可下载
    permission = Column(String(20), nullable=False, default="download")

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (UniqueConstraint("file_entry_id", "user_id", name="uq_file_share"),)

    file_entry = relationship("FileEntry", backref=backref("shares", cascade="all, delete-orphan"))
    user = relationship("User", backref="file_shares")
