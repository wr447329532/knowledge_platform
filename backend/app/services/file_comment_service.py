"""文件评论：权限、@ 候选人、通知

UI 访问模式与后端 visibility 对应关系（@ 候选人须与 can_access_file 一致）：

个人库（6 种）：
  - 仅自己              → private，无成员
  - 仅自己+指定成员      → private + LibraryMember
  - 仅指定成员          → private + LibraryMember（库主始终可访问）
  - 指定部门            → visibility=departments + access_department_ids
  - 指定部门+指定成员    → departments + LibraryMember
  - 公开                → public（全员）

部门库（4 种）：
  - 所属部门            → visibility=department + department_id
  - 所属部门+指定成员    → department + LibraryMember
  - 指定部门            → visibility=departments + access_department_ids（可与所属部门并存）
  - 指定部门+指定成员    → departments + LibraryMember

候选人池 = 库主链 + 根库成员 + 分享/评论参与者 + 部门范围用户 + 监管角色；公开库默认全员；最终以 can_access_file 过滤。
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Iterable, Optional

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.app.core.library_access import can_access_file, resolve_root_library
from backend.app.core.library_department_access import (
    VISIBILITY_DEPARTMENTS,
    list_access_department_ids,
)
from backend.app.core.oversight_access import (
    ROLE_DIVISION_LEADER,
    ROLE_EXECUTIVE,
    expand_department_ids_with_descendants,
    expand_user_department_subtree,
    get_department_parent_map,
    get_expanded_supervised_department_ids,
)
from backend.app.models.file import FileEntry, FileVersion
from backend.app.models.file_comment import FileComment, FileCommentMention
from backend.app.models.file_share import FileShare
from backend.app.models.library import Library
from backend.app.models.library_member import LibraryMember
from backend.app.models.user import User

MAX_COMMENT_BODY_LEN = 2000

logger = logging.getLogger(__name__)


def _display_name(user: User | None) -> str:
    if not user:
        return "未知用户"
    return user.username or user.email or f"用户{user.id}"


def _avatar_letter(user: User | None) -> str:
    name = _display_name(user)
    return (name[0] if name else "?").upper()


def get_file_entry_for_comment(db: Session, entry_id: int, user: User) -> FileEntry:
    entry = db.query(FileEntry).filter(FileEntry.id == entry_id).first()
    if not entry or entry.is_dir or getattr(entry, "deleted_at", None) is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")
    if not can_access_file(db, entry, user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该文件")
    return entry


def get_latest_version(db: Session, entry_id: int) -> FileVersion | None:
    return (
        db.query(FileVersion)
        .filter(FileVersion.file_entry_id == entry_id)
        .order_by(FileVersion.version_no.desc())
        .first()
    )


def user_can_access_entry(db: Session, entry: FileEntry, user_id: int) -> bool:
    u = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not u:
        return False
    return can_access_file(db, entry, u)


def _library_owner_chain_ids(db: Session, entry: FileEntry) -> set[int]:
    """文件所在资料库及其上级子库的 owner（子库创建者亦可能可访问文件）。"""
    ids: set[int] = set()
    lib = db.query(Library).filter(Library.id == entry.library_id).first()
    seen: set[int] = set()
    hops = 0
    while lib and lib.id not in seen and hops < 32:
        hops += 1
        seen.add(int(lib.id))
        if lib.owner_id:
            ids.add(int(lib.owner_id))
        if not getattr(lib, "parent_id", None):
            break
        lib = db.query(Library).filter(Library.id == lib.parent_id).first()
    return ids


def collect_mention_candidate_ids(db: Session, entry: FileEntry) -> set[int]:
    """库主链、根库成员、文件分享、上传者、历史评论参与者。"""
    ids: set[int] = set()
    ids |= _library_owner_chain_ids(db, entry)
    lib = db.query(Library).filter(Library.id == entry.library_id).first()
    if not lib:
        return ids
    root = resolve_root_library(db, lib)
    for (uid,) in db.query(LibraryMember.user_id).filter(LibraryMember.library_id == root.id).all():
        ids.add(int(uid))
    for (uid,) in (
        db.query(FileShare.user_id).filter(FileShare.file_entry_id == entry.id).all()
    ):
        ids.add(int(uid))
    ver = get_latest_version(db, entry.id)
    if ver and ver.uploaded_by_id:
        ids.add(int(ver.uploaded_by_id))
    for (uid,) in (
        db.query(FileComment.user_id)
        .filter(FileComment.file_entry_id == entry.id, FileComment.deleted_at.is_(None))
        .distinct()
        .all()
    ):
        ids.add(int(uid))
    for (uid,) in (
        db.query(FileCommentMention.user_id)
        .join(FileComment, FileCommentMention.comment_id == FileComment.id)
        .filter(FileComment.file_entry_id == entry.id, FileComment.deleted_at.is_(None))
        .distinct()
        .all()
    ):
        ids.add(int(uid))
    return ids


def _root_library_for_entry(db: Session, entry: FileEntry) -> Library | None:
    lib = db.query(Library).filter(Library.id == entry.library_id).first()
    if not lib:
        return None
    return resolve_root_library(db, lib)


def _root_visibility_for_entry(db: Session, entry: FileEntry) -> str:
    root = _root_library_for_entry(db, entry)
    if not root:
        return "private"
    return str(getattr(root, "visibility", "private") or "private")


def _department_scope_ids_for_entry(db: Session, entry: FileEntry) -> set[int]:
    """
    与 can_access_file 的部门分支对齐。

    - visibility=department：所属 department_id 子树
    - visibility=departments：指定部门子树；部门库上若仍有 department_id，所属部门成员也可访问，一并纳入
    - visibility=private/public：若历史数据带 department_id，所属部门成员仍可能通过 ACL 访问，纳入子树
    """
    root = _root_library_for_entry(db, entry)
    if not root:
        return set()
    visibility = str(getattr(root, "visibility", "private") or "private")
    parent_map = get_department_parent_map(db)
    scope: set[int] = set()

    dept_id = getattr(root, "department_id", None)
    if dept_id is not None and visibility in ("department", "private"):
        scope |= expand_department_ids_with_descendants(parent_map, [int(dept_id)])

    if visibility == VISIBILITY_DEPARTMENTS:
        granted = list_access_department_ids(db, root.id)
        if granted:
            scope |= expand_department_ids_with_descendants(parent_map, granted)
        # 部门库「指定部门」模式：所属部门成员仍可读（can_access_file 的 department_id 分支）
        if dept_id is not None:
            scope |= expand_department_ids_with_descendants(parent_map, [int(dept_id)])

    return scope


def _oversight_user_ids_for_dept_scope(db: Session, dept_scope: set[int]) -> set[int]:
    """高管 / 分管领导等监管角色：部门子树有交集即可 @（与只读访问一致）。"""
    if not dept_scope:
        return set()
    ids: set[int] = set()
    for (uid,) in (
        db.query(User.id)
        .filter(User.is_active == True, User.role == ROLE_EXECUTIVE)
        .all()
    ):
        ids.add(int(uid))

    parent_map = get_department_parent_map(db)
    for u in (
        db.query(User)
        .filter(User.is_active == True, User.role == ROLE_DIVISION_LEADER)
        .all()
    ):
        accessible = get_expanded_supervised_department_ids(db, u.id)
        if u.department_id is not None:
            accessible |= expand_user_department_subtree(parent_map, int(u.department_id))
        if accessible & dept_scope:
            ids.add(int(u.id))
    return ids


def expand_library_access_user_ids(db: Session, entry: FileEntry) -> set[int]:
    """通过部门权限可访问该文件的用户（含监管角色，不限于 library_members）。"""
    scope = _department_scope_ids_for_entry(db, entry)
    if not scope:
        return set()

    ids: set[int] = set()
    for (uid,) in (
        db.query(User.id)
        .filter(User.is_active == True, User.department_id.in_(scope))
        .all()
    ):
        ids.add(int(uid))
    ids |= _oversight_user_ids_for_dept_scope(db, scope)
    return ids


def gather_mention_pool_ids(db: Session, entry: FileEntry) -> set[int]:
    """@ 默认列表候选人 ID：库成员/分享/评论参与者 + 部门可见用户。"""
    return collect_mention_candidate_ids(db, entry) | expand_library_access_user_ids(db, entry)


def _prioritize_mention_users(db: Session, entry: FileEntry, users: list[User]) -> list[User]:
    """默认 @ 列表优先展示库主/成员/评论参与者，再展示部门大范围用户。"""
    core_ids = collect_mention_candidate_ids(db, entry)

    def sort_key(u: User) -> tuple[int, str]:
        if int(u.id) in core_ids:
            return (0, (u.username or u.email or "").lower())
        return (1, (u.username or u.email or "").lower())

    return sorted(users, key=sort_key)


def _query_mention_user_rows(db: Session, entry: FileEntry, kw: str) -> list[User]:
    """拉取 @ 候选用户行；最终仍经 can_access_file 过滤。"""
    if kw:
        like = f"%{kw}%"
        return (
            db.query(User)
            .filter(
                User.is_active == True,
                or_(User.username.ilike(like), User.email.ilike(like)),
            )
            .order_by(User.username)
            .limit(80)
            .all()
        )

    if _root_visibility_for_entry(db, entry) == "public":
        return (
            db.query(User)
            .filter(User.is_active == True)
            .order_by(User.username)
            .limit(80)
            .all()
        )

    pool_ids = gather_mention_pool_ids(db, entry)
    if not pool_ids:
        return []
    rows = (
        db.query(User)
        .filter(User.is_active == True, User.id.in_(pool_ids))
        .limit(200)
        .all()
    )
    return _prioritize_mention_users(db, entry, rows)[:80]


def list_mention_candidates(
    db: Session,
    entry: FileEntry,
    current_user: User,
    *,
    search: str = "",
    limit: int = 20,
) -> list[User]:
    limit = max(1, min(int(limit), 30))
    kw = (search or "").strip()
    rows = _query_mention_user_rows(db, entry, kw)

    out: list[User] = []
    seen: set[int] = set()
    for u in rows:
        if u.id in seen or u.id == current_user.id:
            continue
        if not user_can_access_entry(db, entry, u.id):
            continue
        seen.add(u.id)
        out.append(u)
        if len(out) >= limit:
            break
    return out


def validate_mention_ids(
    db: Session,
    entry: FileEntry,
    mention_user_ids: Iterable[int],
    *,
    exclude_user_id: int | None = None,
) -> list[int]:
    normalized = sorted(
        {
            int(uid)
            for uid in mention_user_ids
            if isinstance(uid, int) and not isinstance(uid, bool)
        }
    )
    if exclude_user_id is not None:
        normalized = [i for i in normalized if i != int(exclude_user_id)]
    for uid in normalized:
        if not user_can_access_entry(db, entry, uid):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"用户 {uid} 无权访问该文件，无法 @",
            )
    return normalized


def collect_comment_notification_recipient_ids(
    db: Session, entry: FileEntry, author_id: int
) -> set[int]:
    """评论通知接收人：与 @ 候选人池一致（不含评论作者）。"""
    ids = gather_mention_pool_ids(db, entry)
    ids.discard(int(author_id))
    return ids


def resolve_mention_user_ids(
    db: Session,
    entry: FileEntry,
    body: str,
    explicit_ids: Iterable[int],
    *,
    exclude_user_id: int,
) -> list[int]:
    """合并前端传入的 mention id 与正文 @用户名 解析结果。"""
    ids: set[int] = set(
        validate_mention_ids(
            db,
            entry,
            explicit_ids,
            exclude_user_id=exclude_user_id,
        )
    )
    for token in re.findall(r"@([^\s@]+)", body or ""):
        rows = (
            db.query(User)
            .filter(
                User.is_active == True,
                or_(
                    User.username == token,
                    User.email == token,
                    User.username.ilike(token),
                ),
            )
            .all()
        )
        for u in rows:
            uid = int(u.id)
            if uid == exclude_user_id:
                continue
            if user_can_access_entry(db, entry, uid):
                ids.add(uid)
    return sorted(ids)


def sync_comment_mentions(db: Session, comment_id: int, user_ids: list[int]) -> None:
    existing = {
        int(r.user_id): r
        for r in db.query(FileCommentMention).filter(FileCommentMention.comment_id == comment_id).all()
    }
    target = set(user_ids)
    for uid in existing.keys() - target:
        db.delete(existing[uid])
    for uid in target - existing.keys():
        db.add(FileCommentMention(comment_id=comment_id, user_id=uid))


def send_comment_notifications(
    db: Session,
    *,
    entry: FileEntry,
    comment: FileComment,
    author: User,
    mention_user_ids: list[int],
    parent: FileComment | None,
) -> None:
    from backend.app.api.notifications import create_notification_if_enabled

    filename = entry.path.rsplit("/", 1)[-1] if entry.path else "文件"
    author_name = _display_name(author)
    snippet = (comment.body or "").strip()
    if len(snippet) > 120:
        snippet = snippet[:117] + "…"
    extra = json.dumps(
        {"entry_id": entry.id, "library_id": entry.library_id, "path": entry.path},
        ensure_ascii=False,
    )

    notified: set[int] = {author.id}

    for uid in mention_user_ids:
        if uid in notified:
            continue
        notified.add(uid)
        create_notification_if_enabled(
            db,
            setting_key="mention",
            user_id=uid,
            type="file_comment_mention",
            title="有人在文件中提及了你",
            message=f"{author_name} 在「{filename}」中提及了你：{snippet}",
            resource_type="file_entry",
            resource_id=entry.id,
            extra_json=extra,
            commit=False,
        )

    if parent is not None and parent.user_id not in notified and parent.user_id != author.id:
        if parent.deleted_at is None:
            notified.add(int(parent.user_id))
            create_notification_if_enabled(
                db,
                setting_key="comment",
                user_id=int(parent.user_id),
                type="file_comment_reply",
                title="有人回复了你的评论",
                message=f"{author_name} 回复了你在「{filename}」下的评论：{snippet}",
                resource_type="file_entry",
                resource_id=entry.id,
                extra_json=extra,
                commit=False,
            )

    if parent is None:
        for uid in collect_comment_notification_recipient_ids(db, entry, author.id):
            if uid in notified:
                continue
            notified.add(uid)
            create_notification_if_enabled(
                db,
                setting_key="comment",
                user_id=uid,
                type="file_comment",
                title="文件有新评论",
                message=f"{author_name} 在「{filename}」中发表了评论：{snippet}",
                resource_type="file_entry",
                resource_id=entry.id,
                extra_json=extra,
                commit=False,
            )
    else:
        # 回复时也通知库主/其他相关人（不含已被 @ 或收到回复通知的人）
        for uid in collect_comment_notification_recipient_ids(db, entry, author.id):
            if uid in notified:
                continue
            create_notification_if_enabled(
                db,
                setting_key="comment",
                user_id=uid,
                type="file_comment",
                title="文件有新回复",
                message=f"{author_name} 在「{filename}」中回复了讨论：{snippet}",
                resource_type="file_entry",
                resource_id=entry.id,
                extra_json=extra,
                commit=False,
            )
            notified.add(uid)


def soft_delete_comment(db: Session, comment: FileComment, user: User) -> None:
    if comment.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只能删除自己的评论")
    if comment.deleted_at is not None:
        return
    comment.deleted_at = datetime.now(timezone.utc)


def build_author_dict(user: User | None) -> dict:
    return {
        "id": int(user.id) if user else None,
        "username": _display_name(user),
        "avatar_letter": _avatar_letter(user),
    }
