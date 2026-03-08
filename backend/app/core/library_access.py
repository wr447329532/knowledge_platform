"""资料库与文件访问权限（文件级共享）"""
from typing import Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.models.file import FileEntry
from backend.app.models.file_share import FileShare
from backend.app.models.library import Library
from backend.app.models.user import User


def has_library_access(db: Session, library_id: int, user: User, require_write: bool = False) -> Tuple[Library, bool]:
    """
    检查用户是否有权访问资料库。
    返回 (library, is_writeable)。
    - 拥有者：读写
    - 被分享者（有 FileShare）：只读，require_write=True 时拒绝
    """
    lib = db.query(Library).filter(Library.id == library_id).first()
    if not lib:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="资料库不存在")

    # 拥有者：完全权限
    if lib.owner_id == user.id:
        return lib, True

    # 被分享者：该库中至少有被分享的文件
    has_share = (
        db.query(FileShare.id)
        .join(FileEntry, FileShare.file_entry_id == FileEntry.id)
        .filter(FileEntry.library_id == library_id, FileShare.user_id == user.id)
        .first()
    )
    if has_share:
        if require_write:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="该资料库为只读，仅可访问分享给您的文件")
        return lib, False

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该资料库")


def get_accessible_library_ids(db: Session, user: User) -> list[int]:
    """获取用户可访问的资料库 ID：拥有 + 有文件被分享给自己"""
    owned = [r[0] for r in db.query(Library.id).filter(Library.owner_id == user.id).all()]
    shared_lib_ids = (
        db.query(FileEntry.library_id)
        .join(FileShare, FileShare.file_entry_id == FileEntry.id)
        .filter(FileShare.user_id == user.id)
        .distinct()
        .all()
    )
    shared = [r[0] for r in shared_lib_ids]
    return list(set(owned) | set(shared))


def check_can_manage_library(lib: Library, user: User, db: Session) -> None:
    """检查用户是否可管理资料库（删除库）。仅拥有者。"""
    if lib.owner_id == user.id:
        return
    if user.is_superuser or user.username == "admin":
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅资料库拥有者可删除资料库")


def get_file_share_permission(db: Session, file_entry_id: int, user_id: int) -> str | None:
    """获取用户对某文件的分享权限。返回 'read'|'download'|None"""
    share = (
        db.query(FileShare)
        .filter(FileShare.file_entry_id == file_entry_id, FileShare.user_id == user_id)
        .first()
    )
    return share.permission if share else None


def can_access_file(db: Session, entry: FileEntry, user: User) -> bool:
    """用户是否可访问该文件（拥有者或被分享）"""
    lib = db.query(Library).filter(Library.id == entry.library_id).first()
    if not lib:
        return False
    if lib.owner_id == user.id:
        return True
    perm = get_file_share_permission(db, entry.id, user.id)
    return perm is not None


def can_download_file(db: Session, entry: FileEntry, user: User) -> bool:
    """用户是否可下载该文件（仅资料库拥有者可下载，被分享者仅可预览）"""
    lib = db.query(Library).filter(Library.id == entry.library_id).first()
    if not lib:
        return False
    return lib.owner_id == user.id
