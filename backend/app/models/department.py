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

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    parent = relationship("Department", remote_side=[id], backref="children")
