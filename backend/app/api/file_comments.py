"""文件评论 API"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.core.audit import get_client_ip, log_audit
from backend.app.core.library_access import can_access_file
from backend.app.db.session import get_db
from backend.app.models.file import FileEntry
from backend.app.models.file_comment import FileComment, FileCommentMention
from backend.app.models.library import Library
from backend.app.models.user import User
from backend.app.services.file_comment_service import (
    MAX_COMMENT_BODY_LEN,
    build_author_dict,
    get_file_entry_for_comment,
    get_latest_version,
    list_mention_candidates,
    resolve_mention_user_ids,
    send_comment_notifications,
    soft_delete_comment,
    sync_comment_mentions,
    _display_name,
)

router = APIRouter(tags=["file-comments"])
logger = logging.getLogger(__name__)


class CommentAuthorRead(BaseModel):
    id: int
    username: str
    avatar_letter: str


class CommentMentionRead(BaseModel):
    id: int
    username: str


class FileCommentRead(BaseModel):
    id: int
    body: str
    parent_id: Optional[int] = None
    author: CommentAuthorRead
    mentions: List[CommentMentionRead] = Field(default_factory=list)
    created_at: datetime
    can_delete: bool = False
    replies: List["FileCommentRead"] = Field(default_factory=list)


class FileCommentCreate(BaseModel):
    body: str = Field(..., min_length=1, max_length=MAX_COMMENT_BODY_LEN)
    parent_id: Optional[int] = None
    mention_user_ids: List[int] = Field(default_factory=list)


class MentionCandidateRead(BaseModel):
    id: int
    username: str
    email: Optional[str] = None
    avatar_letter: str


class FileCommentContextRead(BaseModel):
    entry_id: int
    library_id: int
    library_name: Optional[str] = None
    path: str
    filename: str
    version_no: Optional[int] = None
    uploaded_by: Optional[str] = None
    uploaded_at: Optional[datetime] = None
    size: Optional[int] = None


def _load_users_map(db: Session, user_ids: set[int]) -> dict[int, User]:
    if not user_ids:
        return {}
    rows = db.query(User).filter(User.id.in_(user_ids)).all()
    return {int(u.id): u for u in rows}


def _comment_to_read(
    comment: FileComment,
    users: dict[int, User],
    mention_rows: dict[int, list[int]],
    current_user_id: int,
    replies_map: dict[int, list[FileComment]],
) -> FileCommentRead:
    author = users.get(int(comment.user_id))
    m_ids = mention_rows.get(int(comment.id), [])
    mentions = [
        CommentMentionRead(id=uid, username=_display_name(users.get(uid)))
        for uid in m_ids
    ]
    replies = [
        _comment_to_read(r, users, mention_rows, current_user_id, replies_map)
        for r in replies_map.get(int(comment.id), [])
    ]
    return FileCommentRead(
        id=int(comment.id),
        body=comment.body,
        parent_id=int(comment.parent_id) if comment.parent_id is not None else None,
        author=CommentAuthorRead(**build_author_dict(author)),
        mentions=mentions,
        created_at=comment.created_at,
        can_delete=comment.user_id == current_user_id and comment.deleted_at is None,
        replies=replies,
    )


@router.get("/files/{entry_id}/comment-context", response_model=FileCommentContextRead)
def get_file_comment_context(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    entry = get_file_entry_for_comment(db, entry_id, current_user)
    lib = db.query(Library).filter(Library.id == entry.library_id).first()
    ver = get_latest_version(db, entry.id)
    uploader_name = None
    if ver and ver.uploaded_by_id:
        u = db.query(User).filter(User.id == ver.uploaded_by_id).first()
        uploader_name = _display_name(u) if u else None
    filename = entry.path.rsplit("/", 1)[-1] if entry.path else ""
    return FileCommentContextRead(
        entry_id=int(entry.id),
        library_id=int(entry.library_id),
        library_name=lib.name if lib else None,
        path=entry.path,
        filename=filename,
        version_no=int(ver.version_no) if ver else None,
        uploaded_by=uploader_name,
        uploaded_at=ver.uploaded_at if ver else None,
        size=int(ver.size) if ver else None,
    )


@router.get("/files/{entry_id}/comments", response_model=List[FileCommentRead])
def list_file_comments(
    entry_id: int,
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    entry = get_file_entry_for_comment(db, entry_id, current_user)
    rows = (
        db.query(FileComment)
        .filter(
            FileComment.file_entry_id == entry.id,
            FileComment.deleted_at.is_(None),
        )
        .order_by(FileComment.created_at.asc())
        .all()
    )
    if not rows:
        return []

    comment_ids = [int(c.id) for c in rows]
    mention_rows: dict[int, list[int]] = {cid: [] for cid in comment_ids}
    for cid, uid in (
        db.query(FileCommentMention.comment_id, FileCommentMention.user_id)
        .filter(FileCommentMention.comment_id.in_(comment_ids))
        .all()
    ):
        mention_rows.setdefault(int(cid), []).append(int(uid))

    user_ids: set[int] = {int(c.user_id) for c in rows}
    for ids in mention_rows.values():
        user_ids.update(ids)
    users = _load_users_map(db, user_ids)

    replies_map: dict[int, list[FileComment]] = {}
    roots: list[FileComment] = []
    by_id = {int(c.id): c for c in rows}
    for c in rows:
        if c.parent_id is None:
            roots.append(c)
            continue
        cur = c
        while cur.parent_id is not None:
            parent = by_id.get(int(cur.parent_id))
            if parent is None:
                break
            cur = parent
        replies_map.setdefault(int(cur.id), []).append(c)
    for rid in replies_map:
        replies_map[rid].sort(key=lambda x: x.created_at)

    sliced = roots[offset : offset + limit]
    return [
        _comment_to_read(c, users, mention_rows, current_user.id, replies_map)
        for c in sliced
    ]


@router.post("/files/{entry_id}/comments", response_model=FileCommentRead, status_code=status.HTTP_201_CREATED)
def create_file_comment(
    entry_id: int,
    body_in: FileCommentCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    entry = get_file_entry_for_comment(db, entry_id, current_user)
    text = (body_in.body or "").strip()
    if not text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="评论内容不能为空")

    parent: FileComment | None = None
    if body_in.parent_id is not None:
        parent = (
            db.query(FileComment)
            .filter(
                FileComment.id == body_in.parent_id,
                FileComment.file_entry_id == entry.id,
                FileComment.deleted_at.is_(None),
            )
            .first()
        )
        if not parent:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="回复的评论不存在")

    mention_ids = resolve_mention_user_ids(
        db,
        entry,
        text,
        body_in.mention_user_ids,
        exclude_user_id=current_user.id,
    )

    comment = FileComment(
        file_entry_id=entry.id,
        user_id=current_user.id,
        parent_id=body_in.parent_id,
        body=text,
    )
    db.add(comment)
    db.flush()
    sync_comment_mentions(db, comment.id, mention_ids)

    try:
        send_comment_notifications(
            db,
            entry=entry,
            comment=comment,
            author=current_user,
            mention_user_ids=mention_ids,
            parent=parent,
        )
    except Exception:
        logger.warning("评论通知发送失败", exc_info=True)

    audit_action = "file_comment_reply" if parent else "file_comment_create"
    detail = f"path={entry.path} comment_id={comment.id}"
    if parent:
        detail += f" parent_id={parent.id}"
    log_audit(
        db,
        current_user.id,
        current_user.username,
        audit_action,
        "file",
        entry.id,
        detail,
        ip_address=get_client_ip(request),
    )

    db.commit()
    db.refresh(comment)

    users = _load_users_map(db, {current_user.id, *mention_ids})
    mention_rows = {int(comment.id): mention_ids}
    return _comment_to_read(comment, users, mention_rows, current_user.id, {})


@router.delete("/files/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_file_comment(
    comment_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    comment = db.query(FileComment).filter(FileComment.id == comment_id).first()
    if not comment or comment.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="评论不存在")
    entry = db.query(FileEntry).filter(FileEntry.id == comment.file_entry_id).first()
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")
    if not can_access_file(db, entry, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该文件")
    soft_delete_comment(db, comment, current_user)
    log_audit(
        db,
        current_user.id,
        current_user.username,
        "file_comment_delete",
        "file",
        entry.id,
        f"path={entry.path} comment_id={comment.id}",
        ip_address=get_client_ip(request),
    )
    db.commit()


@router.get("/files/{entry_id}/mention-candidates", response_model=List[MentionCandidateRead])
def get_mention_candidates(
    entry_id: int,
    search: str = Query("", max_length=100),
    limit: int = Query(20, ge=1, le=30),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from backend.app.services.file_comment_service import _avatar_letter

    entry = get_file_entry_for_comment(db, entry_id, current_user)
    users = list_mention_candidates(db, entry, current_user, search=search, limit=limit)
    return [
        MentionCandidateRead(
            id=int(u.id),
            username=_display_name(u),
            email=u.email,
            avatar_letter=_avatar_letter(u),
        )
        for u in users
    ]


FileCommentRead.model_rebuild()
