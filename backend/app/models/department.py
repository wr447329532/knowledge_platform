"""部门树：树形结构，支持多级"""
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from backend.app.db.base import Base


class Department(Base):
    """部门：树形结构，parent_id 为 null 表示根节点"""

    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    parent_id = Column(Integer, ForeignKey("departments.id", ondelete="CASCADE"), nullable=True, index=True)
    sort_order = Column(Integer, default=0, nullable=False)  # 同级排序，越小越靠前

    # 部门负责人（可选）：指向 users.id，若为空则前端展示时可退化为「取部门第一个用户」
    leader_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    # 可选：部门级存储配额（字节）。为 null 时使用系统默认配额。
    storage_quota_bytes = Column(Integer, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    parent = relationship("Department", remote_side=[id], backref="children")
    leader = relationship("User", foreign_keys=[leader_user_id])
