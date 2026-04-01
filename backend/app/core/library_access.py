"""资料库与文件访问权限（文件级共享）"""
import threading
import time
from typing import Set, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.models.department import Department
from backend.app.models.file import FileEntry
from backend.app.models.file_share import FileShare
from backend.app.models.library import Library
from backend.app.models.library_member import LibraryMember
from backend.app.models.user import User


def is_executive(user: User) -> bool:
    """高管角色：只读访问所有部门库 + 公开库 + 自己拥有的 + 自己作为成员的库（不能访问他人私人库、仅指定成员库）"""
    return getattr(user, "role", "staff") == "executive"


def is_dept_leader(user: User, db: Session, dept_id: int) -> bool:
    """判断用户是否是指定部门的部长（role=dept_leader 且为该部门负责人）"""
    if getattr(user, "role", "staff") != "dept_leader":
        return False
    dept = db.query(Department).filter(Department.id == dept_id).first()
    if not dept:
        return False
    return getattr(dept, "leader_user_id", None) == user.id


def _is_leader_of_department(db: Session, user: User, dept_id: int | None) -> bool:
    """判断用户是否为指定部门的负责人（由 leader_user_id 指定，与 role 无关）"""
    if dept_id is None:
        return False
    if user.is_superuser:
        return False
    dept = db.query(Department).filter(Department.id == dept_id).first()
    if not dept:
        return False
    return getattr(dept, "leader_user_id", None) == user.id


_dept_snap_lock = threading.Lock()
_dept_snap_ts: float = 0.0
_dept_parent_map: dict[int, int | None] = {}
_dept_all_ids: frozenset[int] = frozenset()
# 部门树快照 TTL：减少每条权限判断都全表扫描 Department；部门变更后最多延迟该秒数生效
DEPT_SNAPSHOT_TTL_SEC = 25.0


def invalidate_department_access_cache() -> None:
    """部门增删改后调用，使部门树快照立即失效。"""
    global _dept_snap_ts
    with _dept_snap_lock:
        _dept_snap_ts = 0.0


def _ensure_department_parent_snapshot(db: Session) -> None:
    global _dept_snap_ts, _dept_parent_map, _dept_all_ids
    now = time.monotonic()
    with _dept_snap_lock:
        stale = (now - _dept_snap_ts >= DEPT_SNAPSHOT_TTL_SEC) or not _dept_parent_map
    if not stale:
        return
    rows = db.query(Department.id, Department.parent_id).all()
    parent_map = {int(r[0]): (int(r[1]) if r[1] is not None else None) for r in rows}
    all_ids = frozenset(parent_map.keys())
    with _dept_snap_lock:
        _dept_snap_ts = time.monotonic()
        _dept_parent_map = parent_map
        _dept_all_ids = all_ids


def _get_accessible_department_ids(db: Session, user: User) -> Set[int]:
    """用户可访问的部门 ID（本人部门及所有子部门，超级管理员/高管为全部）"""
    _ensure_department_parent_snapshot(db)
    with _dept_snap_lock:
        parent_map = _dept_parent_map
        all_ids = _dept_all_ids
    # 超级管理员：可访问全部部门
    if user.is_superuser:
        return set(all_ids)
    # 高管：可访问全部部门（用于只读查看所有部门文件库）
    if is_executive(user):
        return set(all_ids)
    # 普通用户未绑定部门：不自动放宽为全部，按「无部门访问权限」处理
    if user.department_id is None:
        return set()
    if user.department_id not in parent_map:
        return set()
    children_map: dict[int | None, list[int]] = {}
    for did, pid in parent_map.items():
        children_map.setdefault(pid, []).append(did)
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


def write_access_for_listed_library(
    lib: Library,
    user: User,
    member: LibraryMember | None,
    acc_dept_ids: Set[int],
) -> bool:
    """
    在「资料库已在用户可访问列表中」的前提下，推断是否可写。
    避免 list_libraries 对每行调用 has_library_access（重复查库）。
    """
    if user.is_superuser or lib.owner_id == user.id:
        return True
    if member is not None:
        return member.role == "write" and not is_executive(user)
    visibility = getattr(lib, "visibility", "private") or "private"
    if visibility == "public":
        return False
    dept_id = getattr(lib, "department_id", None)
    if dept_id is not None and dept_id in acc_dept_ids:
        if is_executive(user):
            return False
        return True
    return False


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

    # 库成员：始终优先于 visibility（高管恒为只读，不随成员 role 提升为写）
    member = _get_library_member(db, library_id, user.id)
    if member:
        can_write = member.role == "write" and not is_executive(user)
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

    # 部门库：用户所在部门或其子部门的成员可读写；高管可访问全部部门库（只读）
    if getattr(lib, "department_id", None) is not None:
        acc_dept_ids = _get_accessible_department_ids(db, user)
        if lib.department_id in acc_dept_ids:
            if is_executive(user):
                if require_write:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="高管角色仅有只读权限",
                    )
                return lib, False
            return lib, True

    # 指定成员库 / 私人库：除 Owner/库成员外无访问权限（库成员已在上方返回）；高管也不得访问
    if visibility == "members":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该资料库")

    # 私人库（private）且非拥有者、非库成员：拒绝；高管也不得访问
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该资料库")


def _library_not_deleted():
    """未软删除的资料库条件"""
    return Library.deleted_at.is_(None)


def get_accessible_library_ids(db: Session, user: User) -> list[int]:
    """获取用户可访问的资料库 ID：拥有 + 部门库 + 库成员 + public 库（排除已软删除）"""
    not_deleted = _library_not_deleted()

    # 超级管理员：返回所有库
    if user.is_superuser:
        return [r[0] for r in db.query(Library.id).filter(not_deleted).all()]

    # 高管：仅返回 部门库 + 公开库 + 自己拥有的 + 自己作为成员的（不包含他人私人库、仅指定成员库）
    # 通过下方 owned + dept_lib_ids + member_lib_ids + public_lib_ids 实现，其中 dept_lib_ids 依赖 _get_accessible_department_ids（高管已为全部部门）

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
    if dept_id is not None and _is_leader_of_department(db, user, dept_id):
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

    # 部门库成员（含高管：_get_accessible_department_ids 对高管返回全部部门）
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
    - 高管：只要可访问该文件（可预览）即默认可下载
    - 其他用户：必须可访问该文件，且资料库 allow_download=True

    说明：
    - “受控预览（rendered-preview）”与“下载原文件”分离：即使可预览，也不等于可下载原文件。
    - allow_download=false 视为“硬禁下载”（仅 Owner/管理员可下载原文件），避免通过部门成员/文件分享绕过。
    """
    lib = db.query(Library).filter(Library.id == entry.library_id).first()
    if not lib or getattr(lib, "deleted_at", None) is not None:
        return False

    # 超级管理员 / 拥有者
    if user.is_superuser or lib.owner_id == user.id:
        return True

    # 高管：默认可下载（以可访问为前提），不受 allow_download 限制
    if is_executive(user):
        return can_access_file(db, entry, user)

    # 库级禁下载：仅 Owner/管理员可下载原文件
    if getattr(lib, "allow_download", True) is False:
        return False

    # 必须先具备访问权限（库级/部门库/public/成员/文件分享）
    if not can_access_file(db, entry, user):
        return False
    return True


def can_download_in_library_list_context(lib: Library, user: User) -> bool:
    """
    仅用于「已校验库级列表权限」的 /files/list 场景：同一资料库下所有可见条目的
    「是否可下载原文件」与具体 path 无关，避免对每条 FileEntry 重复调用 can_download_file
    （否则会触发大量 Library / Department 全表扫描与 FileShare 查询，目录文件多时极慢）。
    """
    if getattr(lib, "deleted_at", None) is not None:
        return False
    if user.is_superuser or lib.owner_id == user.id:
        return True
    if is_executive(user):
        return True
    if getattr(lib, "allow_download", True) is False:
        return False
    return True
