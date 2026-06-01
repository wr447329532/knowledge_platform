"""文件讨论评论（与 FileVersion.comment 上传备注无关）"""
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from backend.app.db.base import Base


class FileComment(Base):
    __tablename__ = "file_comments"

    id = Column(Integer, primary_key=True, index=True)
    file_entry_id = Column(
        Integer, ForeignKey("file_entries.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_id = Column(Integer, ForeignKey("file_comments.id", ondelete="CASCADE"), nullable=True, index=True)
    body = Column(Text, nullable=False)
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True
    )
    deleted_at = Column(DateTime, nullable=True)

    file_entry = relationship("FileEntry", backref="comments")
    user = relationship("User")
    parent = relationship("FileComment", remote_side="FileComment.id", backref="replies")
    mentions = relationship(
        "FileCommentMention",
        back_populates="comment",
        cascade="all, delete-orphan",
    )


class FileCommentMention(Base):
    __tablename__ = "file_comment_mentions"

    id = Column(Integer, primary_key=True, index=True)
    comment_id = Column(
        Integer, ForeignKey("file_comments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    __table_args__ = (UniqueConstraint("comment_id", "user_id", name="uq_file_comment_mention"),)

    comment = relationship("FileComment", back_populates="mentions")
    user = relationship("User")
