"""资料库与文件访问权限（文件级共享）"""
from typing import Set, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.models.department import Department
from backend.app.models.file import FileEntry
from backend.app.models.file_share import FileShare
from backend.app.models.library import Library
from backend.app.models.user import User


def _get_accessible_department_ids(db: Session, user: User) -> Set[int]:
    """用户可访问的部门 ID（本人部门及所有子部门，超级管理员为全部）"""
    all_depts = {d.id: d for d in db.query(Department).all()}
    if user.is_superuser or user.department_id is None:
        return set(all_depts.keys())
    if user.department_id not in all_depts:
        return set(all_depts.keys())
    children_map: dict = {}
    for d in all_depts.values():
        children_map.setdefault(d.parent_id, []).append(d.id)
    accessible: Set[int] = set()
    stack = [user.department_id]
    while stack:
        did = stack.pop()
        if did in accessible:
            continue
        accessible.add(did)
        for cid in children_map.get(did, []):
            stack.append(cid)
    return accessible


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

    # 部门库：用户所在部门或其子部门的成员可读写
    if getattr(lib, "department_id", None) is not None:
        acc_dept_ids = _get_accessible_department_ids(db, user)
        if lib.department_id in acc_dept_ids:
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
    """获取用户可访问的资料库 ID：拥有 + 有文件被分享给自己 + 所属部门库"""
    owned = [r[0] for r in db.query(Library.id).filter(Library.owner_id == user.id).all()]
    shared_lib_ids = (
        db.query(FileEntry.library_id)
        .join(FileShare, FileShare.file_entry_id == FileEntry.id)
        .filter(FileShare.user_id == user.id)
        .distinct()
        .all()
    )
    shared = [r[0] for r in shared_lib_ids]
    acc_dept_ids = _get_accessible_department_ids(db, user)
    dept_lib_ids = [
        r[0]
        for r in db.query(Library.id).filter(Library.department_id.in_(acc_dept_ids)).all()
    ]
    return list(set(owned) | set(shared) | set(dept_lib_ids))


def check_can_manage_library(lib: Library, user: User, db: Session) -> None:
    """检查用户是否可管理资料库（删除库）。拥有者或超级管理员。"""
    if lib.owner_id == user.id:
        return
    if user.is_superuser:
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
    """用户是否可访问该文件（拥有者、部门库成员或被分享）"""
    lib = db.query(Library).filter(Library.id == entry.library_id).first()
    if not lib:
        return False
    if lib.owner_id == user.id:
        return True
    if getattr(lib, "department_id", None) is not None:
        acc = _get_accessible_department_ids(db, user)
        if lib.department_id in acc:
            return True
    perm = get_file_share_permission(db, entry.id, user.id)
    return perm is not None


def can_download_file(db: Session, entry: FileEntry, user: User) -> bool:
    """用户是否可下载该文件（拥有者、部门库成员可下载，被分享者需 permission=download）"""
    lib = db.query(Library).filter(Library.id == entry.library_id).first()
    if not lib:
        return False
    if lib.owner_id == user.id:
        return True
    if getattr(lib, "department_id", None) is not None:
        acc = _get_accessible_department_ids(db, user)
        if lib.department_id in acc:
            return True
    perm = get_file_share_permission(db, entry.id, user.id)
    return perm == "download"
