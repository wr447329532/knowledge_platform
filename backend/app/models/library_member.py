"""资料库成员（共享）"""
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from backend.app.db.base import Base


class LibraryMember(Base):
    """资料库成员：用户被共享后可访问资料库"""

    __tablename__ = "library_members"

    id = Column(Integer, primary_key=True, index=True)
    library_id = Column(Integer, ForeignKey("libraries.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    # role: read 只读（列表、下载）；write 读写（上传、删除、重命名等）
    role = Column(String(20), nullable=False, default="read")

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (UniqueConstraint("library_id", "user_id", name="uq_library_member"),)

    library = relationship("Library", backref="members")
    user = relationship("User", backref="library_memberships")
