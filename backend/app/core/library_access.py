"""资料库与文件访问权限（文件级共享）"""
import threading
import time
from typing import Set, Tuple

from fastapi import HTTPException, status
from sqlalchemy import false
from sqlalchemy.orm import Session

from backend.app.models.department import Department
from backend.app.models.file import FileEntry
from backend.app.models.file_share import FileShare
from backend.app.models.library import Library
from backend.app.models.library_member import LibraryMember
from backend.app.models.user import User


def resolve_root_library(db: Session, lib: Library) -> Library:
    """沿 parent_id 解析一级资料库；无 parent 时自身即为根。"""
    cur = lib
    seen: Set[int] = set()
    max_hops = 32
    hops = 0
    while getattr(cur, "parent_id", None) is not None and hops < max_hops:
        hops += 1
        if cur.id in seen:
            break
        seen.add(cur.id)
        parent = db.query(Library).filter(Library.id == cur.parent_id).first()
        if not parent:
            break
        cur = parent
    return cur


def library_depth_from_root(db: Session, lib: Library) -> int:
    """一级=1，二级=2，三级=3。"""
    depth = 1
    cur = lib
    seen: Set[int] = set()
    while getattr(cur, "parent_id", None) is not None:
        if cur.id in seen:
            break
        seen.add(cur.id)
        parent = db.query(Library).filter(Library.id == cur.parent_id).first()
        if not parent:
            break
        cur = parent
        depth += 1
    return depth


def _expand_descendants_from_roots(db: Session, root_ids: Set[int]) -> Set[int]:
    """在给定父库 id 集合下，收集所有下级资料库 id（含多级）。"""
    if not root_ids:
        return set()
    rows = (
        db.query(Library.id, Library.parent_id)
        .filter(Library.deleted_at.is_(None))
        .all()
    )
    children_by_parent: dict[int, list[int]] = {}
    for lid, pid in rows:
        if pid is None:
            continue
        children_by_parent.setdefault(int(pid), []).append(int(lid))
    out: Set[int] = set()
    stack = list(root_ids)
    while stack:
        rid = int(stack.pop())
        for cid in children_by_parent.get(rid, []):
            if cid not in out:
                out.add(cid)
                stack.append(cid)
    return out


def user_can_manage_library(db: Session, lib: Library, user: User) -> bool:
    """是否可管理该资料库（编辑/删除）：与一级库一致，含一级拥有者、根库拥有者、部门负责人。"""
    if user.is_superuser:
        return True
    if lib.owner_id == user.id:
        return True
    root = resolve_root_library(db, lib)
    if root.owner_id == user.id:
        return True
    dept_id = getattr(root, "department_id", None)
    if dept_id is not None and _is_leader_of_department(db, user, dept_id):
        return True
    return False


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
    db: Session,
    lib: Library,
    user: User,
    acc_dept_ids: Set[int],
) -> bool:
    """
    在「资料库已在用户可访问列表中」的前提下，推断是否可写。
    子库成员与继承自根库；在根上查 LibraryMember。
    """
    if user.is_superuser or lib.owner_id == user.id:
        return True
    acl = resolve_root_library(db, lib)
    if acl.owner_id == user.id:
        return True
    member = _get_library_member(db, acl.id, user.id)
    if member is not None:
        return member.role == "write" and not is_executive(user)
    visibility = getattr(acl, "visibility", "private") or "private"
    if visibility == "public":
        return False
    dept_id = getattr(acl, "department_id", None)
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
    返回 (当前资料库行, is_writeable)。
    二级/三级子库继承一级（根）库的 ACL：成员、可见性、部门范围均在根库上判定。
    """
    lib = db.query(Library).filter(Library.id == library_id).first()
    if not lib:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="资料库不存在")
    if getattr(lib, "deleted_at", None) is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="资料库已删除")

    acl = resolve_root_library(db, lib)

    # 超级管理员：完全权限
    if user.is_superuser:
        return lib, True

    # 当前库创建者（含子库创建者）：完全权限
    if lib.owner_id == user.id:
        return lib, True

    # 根库拥有者：对整棵子树具备完全权限
    if acl.owner_id == user.id:
        return lib, True

    visibility = getattr(acl, "visibility", "private") or "private"

    # 库成员：绑定在根库 id 上（高管恒为只读）
    member = _get_library_member(db, acl.id, user.id)
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
    if getattr(acl, "department_id", None) is not None:
        acc_dept_ids = _get_accessible_department_ids(db, user)
        if acl.department_id in acc_dept_ids:
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


def libraries_accessible_base_query(db: Session, user: User):
    """
    当前用户可访问的未删除 Library 查询对象（与 get_accessible_library_ids 集合语义一致）。
    """
    not_deleted = _library_not_deleted()
    if user.is_superuser:
        return db.query(Library).filter(not_deleted)

    ids = get_accessible_library_ids(db, user)
    if not ids:
        return db.query(Library).filter(false())
    return db.query(Library).filter(Library.id.in_(ids), not_deleted)


def get_accessible_library_ids(db: Session, user: User) -> list[int]:
    """获取用户可访问的资料库 ID：拥有 + 部门库 + 库成员 + public + 成员根下的所有子库（排除已软删除）"""
    not_deleted = _library_not_deleted()

    # 超级管理员：返回所有库
    if user.is_superuser:
        return [r[0] for r in db.query(Library.id).filter(not_deleted).all()]

    # 拥有的资料库（任意层级）
    owned = [
        r[0]
        for r in db.query(Library.id).filter(Library.owner_id == user.id, not_deleted).all()
    ]

    acc_dept_ids = _get_accessible_department_ids(db, user)
    dept_lib_ids = [
        r[0]
        for r in db.query(Library.id)
        .filter(Library.department_id.in_(acc_dept_ids), not_deleted)
        .all()
    ]

    member_lib_ids_raw = [
        r[0]
        for r in db.query(LibraryMember.library_id)
        .filter(LibraryMember.user_id == user.id)
        .all()
    ]
    member_lib_ids: list[int] = []
    member_root_ids: Set[int] = set()
    if member_lib_ids_raw:
        rows = (
            db.query(Library.id, Library.parent_id)
            .filter(Library.id.in_(member_lib_ids_raw), not_deleted)
            .all()
        )
        for lid, _pid in rows:
            lid = int(lid)
            member_lib_ids.append(lid)
            lw = db.query(Library).filter(Library.id == lid).first()
            if lw:
                member_root_ids.add(resolve_root_library(db, lw).id)

    public_lib_ids = [
        r[0]
        for r in db.query(Library.id).filter(Library.visibility == "public", not_deleted).all()
    ]

    inherited_from_member = _expand_descendants_from_roots(db, member_root_ids)

    return list(
        set(owned)
        | set(dept_lib_ids)
        | set(member_lib_ids)
        | set(public_lib_ids)
        | inherited_from_member
    )


def check_can_manage_library(lib: Library, user: User, db: Session) -> None:
    """检查用户是否可管理资料库（删除 / 编辑）：含根拥有者、子库创建者、部门负责人（按根库部门）。"""
    if user_can_manage_library(db, lib, user):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="仅系统管理员、资料库拥有者或部门负责人可管理该资料库",
    )


def can_access_file(db: Session, entry: FileEntry, user: User) -> bool:
    """
    用户是否可访问该文件（预览 / 查看）。
    子库文件继承根库 ACL。
    """
    lib = db.query(Library).filter(Library.id == entry.library_id).first()
    if not lib or getattr(lib, "deleted_at", None) is not None:
        return False

    acl = resolve_root_library(db, lib)

    # 超级管理员 / 当前库创建者 / 根库拥有者
    if user.is_superuser or lib.owner_id == user.id:
        return True
    if acl.owner_id == user.id:
        return True

    visibility = getattr(acl, "visibility", "private") or "private"

    # public 库：所有登录用户可访问
    if visibility == "public":
        return True

    # 部门库成员（含高管：_get_accessible_department_ids 对高管返回全部部门）
    if getattr(acl, "department_id", None) is not None:
        acc = _get_accessible_department_ids(db, user)
        if acl.department_id in acc:
            return True

    # 指定成员库 / 其他 visibility：库成员可访问（根库成员表）
    member = _get_library_member(db, acl.id, user.id)
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
    allow_download 以根库为准。
    """
    lib = db.query(Library).filter(Library.id == entry.library_id).first()
    if not lib or getattr(lib, "deleted_at", None) is not None:
        return False

    acl = resolve_root_library(db, lib)

    # 超级管理员 / 当前库创建者 / 根拥有者
    if user.is_superuser or lib.owner_id == user.id:
        return True
    if acl.owner_id == user.id:
        return True

    # 高管：默认可下载（以可访问为前提），不受 allow_download 限制
    if is_executive(user):
        return can_access_file(db, entry, user)

    # 库级禁下载：仅 Owner/管理员可下载原文件（看根库）
    if getattr(acl, "allow_download", True) is False:
        return False

    # 必须先具备访问权限（库级/部门库/public/成员/文件分享）
    if not can_access_file(db, entry, user):
        return False
    return True


def can_download_in_library_list_context(db: Session, lib: Library, user: User) -> bool:
    """
    仅用于「已校验库级列表权限」的 /files/list 场景：同一资料库下所有可见条目的
    「是否可下载原文件」与具体 path 无关。
    allow_download 以根库为准。
    """
    if getattr(lib, "deleted_at", None) is not None:
        return False
    acl = resolve_root_library(db, lib)
    if user.is_superuser or lib.owner_id == user.id:
        return True
    if acl.owner_id == user.id:
        return True
    if is_executive(user):
        return True
    if getattr(acl, "allow_download", True) is False:
        return False
    return True
