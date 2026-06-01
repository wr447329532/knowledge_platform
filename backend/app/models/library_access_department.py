"""资料库指定部门访问（visibility=departments）"""
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import relationship, backref

from backend.app.db.base import Base


class LibraryAccessDepartment(Base):
    """资料库可访问的指定部门（含该部门子树内成员）"""

    __tablename__ = "library_access_departments"

    id = Column(Integer, primary_key=True, index=True)
    library_id = Column(Integer, ForeignKey("libraries.id", ondelete="CASCADE"), nullable=False)
    department_id = Column(Integer, ForeignKey("departments.id", ondelete="CASCADE"), nullable=False)

    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("library_id", "department_id", name="uq_library_access_department"),
    )

    library = relationship(
        "Library",
        backref=backref("access_departments", cascade="all, delete-orphan"),
    )
    department = relationship("Department")
