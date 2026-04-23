from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from backend.app.db.base import Base


class Library(Base):
    """资料库（类似 Seafile 的 Library）"""

    __tablename__ = "libraries"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)

    # 一级资料库 parent_id 为空；二级、三级子库指向上一级资料库（删除上级级联删除下级）
    parent_id = Column(
        Integer,
        ForeignKey("libraries.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    owner_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    department_id = Column(
        Integer,
        ForeignKey("departments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # 可见性：private=私有；members=指定成员；department=部门可见；public=全员可见
    visibility = Column(String(20), nullable=False, default="private")

    # 是否允许非拥有者下载库中文件（拥有者和超级管理员始终可下载）；新建默认关闭，需手动开启
    allow_download = Column(Boolean, nullable=False, default=False)

    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    deleted_at = Column(DateTime, nullable=True)  # 软删除：非空表示已移入回收站

    owner = relationship("User")
    department = relationship("Department", backref="libraries")
    parent = relationship(
        "Library",
        remote_side=[id],
        foreign_keys=[parent_id],
        backref="child_libraries",
    )

