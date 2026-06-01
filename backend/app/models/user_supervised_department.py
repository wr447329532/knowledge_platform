"""分管领导与分管部门的关联（多对多）。"""
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import relationship

from backend.app.db.base import Base


class UserSupervisedDepartment(Base):
    """用户分管的部门根节点；实际文件访问范围含该节点下所有子部门。"""

    __tablename__ = "user_supervised_departments"
    __table_args__ = (
        UniqueConstraint("user_id", "department_id", name="uq_user_supervised_department"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    department_id = Column(
        Integer,
        ForeignKey("departments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user = relationship("User", backref="supervised_department_links")
    department = relationship("Department")
