"""资料库与文件访问权限（文件级共享）"""
from typing import Set, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.models.department import Department
from backend.app.models.file import FileEntry
from backend.app.models.file_share import FileShare
from backend.app.models.library import Library
from backend.app.models.library_member import LibraryMember
from backend.app.models.user import User


def _get_accessible_department_ids(db: Session, user: User) -> Set[int]:
    """用户可访问的部门 ID（本人部门及所有子部门，超级管理员为全部）"""
    all_depts = {d.id: d for d in db.query(Department).all()}
    # 超级管理员：可访问全部部门
    if user.is_superuser:
        return set(all_depts.keys())
    # 普通用户未绑定部门：不自动放宽为全部，按「无部门访问权限」处理
    if user.department_id is None:
        return set()
    if user.department_id not in all_depts:
        # 绑定了无效部门，同样视为无部门访问权限
        return set()
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


def is_dept_leader(db: Session, user: User, dept_id: int | None) -> bool:
    """判断用户是否为指定部门的负责人。

    规则：
    - 若 dept_id 为空，则返回 False
    - 若当前用户为该部门的 leader_user_id，则为负责人
    """
    if dept_id is None:
        return False
    if user.is_superuser:
        return False  # 超管单独判断，不在此函数里重复逻辑
    dept = db.query(Department).filter(Department.id == dept_id).first()
    if not dept:
        return False
    return getattr(dept, "leader_user_id", None) == user.id


def _get_library_member(db: Session, library_id: int, user_id: int) -> LibraryMember | None:
    """查询用户是否为库成员"""
    return (
        db.query(LibraryMember)
        .filter(
            LibraryMember.library_id == library_id,
            LibraryMember.user_id == user_id,
        )
        .first()
    )


def has_library_access(db: Session, library_id: int, user: User, require_write: bool = False) -> Tuple[Library, bool]:
    """
    检查用户是否有权访问资料库。
    返回 (library, is_writeable)。
    权限优先级从高到低：
    1. 超级管理员：完全权限
    2. 拥有者：完全权限
    3. 库成员（LibraryMember）：role=read/write 决定读/写，不受 visibility 限制
    4. public 库：所有人可读
    5. 部门库：部门及子部门成员可读写
    6. 指定成员库（members）：除 Owner/库成员外无访问权限
    7. 文件级分享：只读，require_write=True 时拒绝
    """
    lib = db.query(Library).filter(Library.id == library_id).first()
    if not lib:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="资料库不存在")
    if getattr(lib, "deleted_at", None) is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="资料库已删除")

    # 超级管理员：完全权限
    if user.is_superuser:
        return lib, True

    # 拥有者：完全权限
    if lib.owner_id == user.id:
        return lib, True

    visibility = getattr(lib, "visibility", "private") or "private"

    # 库成员：始终优先于 visibility
    member = _get_library_member(db, library_id, user.id)
    if member:
        can_write = member.role == "write"
        if require_write and not can_write:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="该资料库为只读",
            )
        return lib, can_write

    # 全员可见库：所有登录用户可读
    if visibility == "public":
        if require_write:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="该资料库为只读",
            )
        return lib, False

    # 部门库：用户所在部门或其子部门的成员可读写
    if getattr(lib, "department_id", None) is not None:
        acc_dept_ids = _get_accessible_department_ids(db, user)
        if lib.department_id in acc_dept_ids:
            return lib, True

    # 指定成员库：除 Owner/库成员外无访问权限（库成员已在上方返回）
    if visibility == "members":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该资料库")

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该资料库")


def _library_not_deleted():
    """未软删除的资料库条件"""
    return Library.deleted_at.is_(None)


def get_accessible_library_ids(db: Session, user: User) -> list[int]:
    """获取用户可访问的资料库 ID：拥有 + 部门库 + 库成员 + public 库（排除已软删除）"""
    not_deleted = _library_not_deleted()
    # 拥有的资料库
    owned = [
        r[0]
        for r in db.query(Library.id).filter(Library.owner_id == user.id, not_deleted).all()
    ]

    # 部门库
    acc_dept_ids = _get_accessible_department_ids(db, user)
    dept_lib_ids = [
        r[0]
        for r in db.query(Library.id)
        .filter(Library.department_id.in_(acc_dept_ids), not_deleted)
        .all()
    ]

    # 库成员
    member_lib_ids_raw = [
        r[0]
        for r in db.query(LibraryMember.library_id)
        .filter(LibraryMember.user_id == user.id)
        .all()
    ]
    if member_lib_ids_raw:
        member_lib_ids = [
            r[0]
            for r in db.query(Library.id)
            .filter(Library.id.in_(member_lib_ids_raw), not_deleted)
            .all()
        ]
    else:
        member_lib_ids = []

    # public 库（所有登录用户可见）
    public_lib_ids = [
        r[0]
        for r in db.query(Library.id).filter(Library.visibility == "public", not_deleted).all()
    ]

    return list(set(owned) | set(dept_lib_ids) | set(member_lib_ids) | set(public_lib_ids))


def check_can_manage_library(lib: Library, user: User, db: Session) -> None:
    """
    检查用户是否可管理资料库（删除 / 编辑）。

    允许角色：
    - 超级管理员
    - 资料库拥有者
    - 对应部门的负责人（当库属于某个部门时）
    """
    # 超级管理员
    if user.is_superuser:
        return
    # 库拥有者
    if lib.owner_id == user.id:
        return
    # 部门负责人：仅对部门库生效
    dept_id = getattr(lib, "department_id", None)
    if dept_id is not None and is_dept_leader(db, user, dept_id):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="仅系统管理员、资料库拥有者或部门负责人可管理该资料库",
    )


def can_access_file(db: Session, entry: FileEntry, user: User) -> bool:
    """
    用户是否可访问该文件（预览 / 查看）。
    继承与库级 ACL 一致的优先级：
    1. 超级管理员 / 拥有者
    2. public 库
    3. 部门库成员
    4. LibraryMember 成员（read / write）
    """
    lib = db.query(Library).filter(Library.id == entry.library_id).first()
    if not lib or getattr(lib, "deleted_at", None) is not None:
        return False

    # 超级管理员 / 拥有者
    if user.is_superuser or lib.owner_id == user.id:
        return True

    visibility = getattr(lib, "visibility", "private") or "private"

    # public 库：所有登录用户可访问
    if visibility == "public":
        return True

    # 部门库成员
    if getattr(lib, "department_id", None) is not None:
        acc = _get_accessible_department_ids(db, user)
        if lib.department_id in acc:
            return True

    # 指定成员库 / 其他 visibility：库成员可访问
    member = _get_library_member(db, lib.id, user.id)
    if member is not None:
        return True

    # 文件级分享：即使不是库成员，只要被分享了该文件即可访问（只读）
    share = (
        db.query(FileShare)
        .filter(
            FileShare.file_entry_id == entry.id,
            FileShare.user_id == user.id,
        )
        .first()
    )
    if share is not None:
        return True

    return False


def can_download_file(db: Session, entry: FileEntry, user: User) -> bool:
    """
    用户是否可下载该文件。
    规则：
    - 超级管理员 / 拥有者：始终可下载
    - 其他用户：需先通过库级访问控制，且库 allow_download=True
    """
    lib = db.query(Library).filter(Library.id == entry.library_id).first()
    if not lib or getattr(lib, "deleted_at", None) is not None:
        return False

    # 超级管理员 / 拥有者
    if user.is_superuser or lib.owner_id == user.id:
        return True

    # 文件级分享：permission=download 的用户始终可下载该文件
    share = (
        db.query(FileShare)
        .filter(
            FileShare.file_entry_id == entry.id,
            FileShare.user_id == user.id,
        )
        .first()
    )
    if share is not None and share.permission == "download":
        return True

    visibility = getattr(lib, "visibility", "private") or "private"

    # 部门库成员
    if getattr(lib, "department_id", None) is not None:
        acc = _get_accessible_department_ids(db, user)
        if lib.department_id in acc:
            return True

    # 指定成员库 / public / private / department：只要是库成员、部门成员或 public 访问者且库允许下载，即可下载
    # 复用 can_access_file 进行访问判断
    if not can_access_file(db, entry, user):
        return False

    # 库级访问通过后，再看库是否允许下载
    return getattr(lib, "allow_download", True)
