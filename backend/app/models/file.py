from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from backend.app.db.base import Base


class FileEntry(Base):
    """库内的文件/目录节点"""

    __tablename__ = "file_entries"

    id = Column(Integer, primary_key=True, index=True)
    library_id = Column(Integer, ForeignKey("libraries.id", ondelete="CASCADE"), nullable=False)

    path = Column(String(1024), nullable=False, index=True)  # 在库内的路径，如 /docs/readme.md
    is_dir = Column(Boolean, default=False, nullable=False)

    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    deleted_at = Column(DateTime, nullable=True)  # 非空表示已进入回收站

    library = relationship("Library", backref="entries")
    created_by = relationship("User")


class FileVersion(Base):
    """文件的某个版本，指向物理存储路径"""

    __tablename__ = "file_versions"

    id = Column(Integer, primary_key=True, index=True)
    file_entry_id = Column(
        Integer, ForeignKey("file_entries.id", ondelete="CASCADE"), nullable=False
    )
    version_no = Column(Integer, nullable=False)  # 版本号，从 1 开始递增

    storage_path = Column(String(2048), nullable=False)  # 磁盘上的真实路径
    size = Column(Integer, nullable=False)
    content_hash = Column(String(128), nullable=True)  # 可选：文件哈希

    uploaded_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    uploaded_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    comment = Column(Text, nullable=True)

    file_entry = relationship("FileEntry", backref="versions")
    uploaded_by = relationship("User")

