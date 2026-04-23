from datetime import datetime
from typing import List, Set

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.core.audit import get_client_ip, log_audit
from backend.app.core.library_access import (
    _get_accessible_department_ids,
    check_can_manage_library,
    get_accessible_library_ids,
    has_library_access,
    libraries_accessible_base_query,
    library_depth_from_root,
    resolve_root_library,
    user_can_manage_library,
    write_access_for_listed_library,
)
from backend.app.api.notifications import create_notification
from backend.app.db.session import get_db
from backend.app.models.department import Department
from backend.app.models.library import Library
from backend.app.models.library_member import LibraryMember
from backend.app.models.user import User


class LibraryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="资料库名称")
    description: str | None = None
    # 若指定，则创建为子库（二级/三级），继承根库权限与部门/可见性/下载策略
    parent_id: int | None = None
    department_id: int | None = None  # 指定则创建为部门库
    # 可见性：private=私有；department=部门可见；public=全员可见（仅个人库）
    visibility: str = "private"
    # 是否允许非拥有者下载库中文件（拥有者/超级管理员始终可下载）
    allow_download: bool | None = None
    # 指定成员列表（无论可见性为何，均可用于补充访问权限）
    member_user_ids: list[int] | None = None


class LibraryRead(BaseModel):
    id: int
    name: str
    description: str | None
    owner_id: int | None = None
    owner_username: str | None = None
    department_id: int | None = None
    department_name: str | None = None
    visibility: str | None = None
    allow_download: bool | None = None
    member_count: int | None = None
    is_owner: bool | None = None  # 当前用户是否拥有者
    is_writeable: bool | None = None  # 当前用户是否可写
    parent_id: int | None = None
    root_library_id: int | None = None
    depth: int = 1  # 一级=1，二级=2，三级=3
    can_manage: bool = False  # 是否可编辑/删除资料库（含根拥有者与部门负责人）

    class Config:
        from_attributes = True


class LibraryBreadcrumbItem(BaseModel):
    id: int
    name: str


class LibraryTrashRead(LibraryRead):
    deleted_at: datetime
    owner_username: str | None = None

    class Config:
        from_attributes = True


class SharedLibraryRow(BaseModel):
    """共享文件库列表行"""

    id: int
    name: str
    description: str | None = None
    owner_username: str | None = None
    department_name: str | None = None
    visibility: str
    share_scope: str
    can_write: bool
    created_at: datetime


class LibraryUpdate(BaseModel):
    name: str | None = Field(None, max_length=100)
    description: str | None = None
    visibility: str | None = None
    allow_download: bool | None = None


class MoveLibraryBody(BaseModel):
    """移动资料库：挂到目标父库下（二级/三级），或 parent_id=null 移到一级根目录。"""

    parent_id: int | None = Field(None, description="目标父资料库 id；null 表示作为一级资料库")


class LibraryMoveTarget(BaseModel):
    """可选移动目标（提交 move 时的 parent_id 与此一致）"""

    parent_id: int | None = Field(None, description="父资料库 id；null 表示移到一级根目录")
    label: str


router = APIRouter(prefix="/libraries", tags=["libraries"])

_LIB_READ_AUTO = object()


def _normalize_library_name(name: str) -> str:
    return name.strip()


def _library_name_taken(
    db: Session,
    name: str,
    *,
    department_id: int | None,
    owner_id: int | None,
    parent_id: int | None = None,
    exclude_library_id: int | None = None,
) -> bool:
    """同级范围内名称唯一：子库按 parent_id；否则个人库按拥有者、部门库按部门。"""
    norm = _normalize_library_name(name)
    if not norm:
        return False
    q = db.query(Library.id, Library.name).filter(Library.deleted_at.is_(None))
    if exclude_library_id is not None:
        q = q.filter(Library.id != exclude_library_id)
    if parent_id is not None:
        q = q.filter(Library.parent_id == parent_id)
    elif department_id is not None:
        q = q.filter(Library.department_id == department_id)
    else:
        q = q.filter(Library.department_id.is_(None))
        if owner_id is not None:
            q = q.filter(Library.owner_id == owner_id)
    for row in q.all():
        existing_name = row[1]
        if _normalize_library_name(existing_name or "") == norm:
            return True
    return False


def _collect_descendant_library_ids(db: Session, root_node_id: int) -> Set[int]:
    """包含 root_node_id 及其所有下级资料库 id（未删除）。"""
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
    out: Set[int] = {int(root_node_id)}
    stack = [int(root_node_id)]
    while stack:
        pid = int(stack.pop())
        for cid in children_by_parent.get(pid, []):
            if cid not in out:
                out.add(cid)
                stack.append(cid)
    return out


def _subtree_depth_span(db: Session, mov: Library) -> int:
    """mov 子树内相对 mov 的最大层数差（含自身为 0）。"""
    ids = _collect_descendant_library_ids(db, mov.id)
    base = library_depth_from_root(db, mov)
    span = 0
    for lid in ids:
        lib = db.query(Library).filter(Library.id == lid).first()
        if lib:
            span = max(span, library_depth_from_root(db, lib) - base)
    return span


def _merge_library_members(
    db: Session,
    from_lib_id: int,
    to_lib_id: int,
    *,
    delete_from_source: bool,
) -> None:
    rows = db.query(LibraryMember).filter(LibraryMember.library_id == from_lib_id).all()
    for r in rows:
        existing = (
            db.query(LibraryMember)
            .filter(
                LibraryMember.library_id == to_lib_id,
                LibraryMember.user_id == r.user_id,
            )
            .first()
        )
        if existing:
            if r.role == "write" or existing.role == "write":
                existing.role = "write"
        else:
            db.add(
                LibraryMember(
                    library_id=to_lib_id,
                    user_id=r.user_id,
                    role=r.role,
                )
            )
    if delete_from_source:
        db.query(LibraryMember).filter(LibraryMember.library_id == from_lib_id).delete()


def _sync_subtree_fields_from_acl_root(db: Session, mov: Library) -> None:
    """将 mov 整棵子树的部门/可见性/下载策略与解析后的根库一致。"""
    acl = resolve_root_library(db, mov)
    ids = _collect_descendant_library_ids(db, mov.id)
    dept_id = getattr(acl, "department_id", None)
    vis = str(getattr(acl, "visibility", "private") or "private")
    ad = bool(getattr(acl, "allow_download", False))
    for lid in ids:
        row = db.query(Library).filter(Library.id == lid).first()
        if row:
            row.department_id = dept_id
            row.visibility = vis
            row.allow_download = ad


def _lib_to_read(
    db: Session,
    lib: Library,
    current_user_id: int,
    *,
    current_user_obj: User | None = None,
    is_owner: bool = False,
    is_write: bool = False,
    dept_name: str | None | object = _LIB_READ_AUTO,
    owner_username: str | None | object = _LIB_READ_AUTO,
    member_count: int | None = None,
) -> LibraryRead:
    if dept_name is _LIB_READ_AUTO:
        dept_name = None
        if getattr(lib, "department_id", None) is not None:
            d = db.query(Department).filter(Department.id == lib.department_id).first()
            dept_name = d.name if d else None
    if owner_username is _LIB_READ_AUTO:
        owner_username = None
        if getattr(lib, "owner_id", None):
            owner = db.query(User).filter(User.id == lib.owner_id).first()
            if owner:
                owner_username = owner.username or owner.email or f"用户{owner.id}"
    root = resolve_root_library(db, lib)
    if member_count is None:
        root_members = getattr(root, "members", []) or []
        member_count = len(root_members)
    else:
        member_count = int(member_count)
    depth = library_depth_from_root(db, lib)
    pid = getattr(lib, "parent_id", None)
    can_manage = False
    if current_user_obj is not None:
        can_manage = user_can_manage_library(db, lib, current_user_obj)
    # SQLite 等驱动可能把 BOOLEAN 读成 0/1，Pydantic 对 bool 校验较严时会触发响应校验 500
    _ad = getattr(lib, "allow_download", None)
    if _ad is None:
        allow_download_out = False
    else:
        allow_download_out = bool(_ad)
    return LibraryRead(
        id=int(lib.id),
        name=(lib.name if lib.name is not None else "") or "",
        description=lib.description,
        owner_id=(int(lib.owner_id) if lib.owner_id is not None else None),
        owner_username=owner_username,
        department_id=(
            int(lib.department_id) if getattr(lib, "department_id", None) is not None else None
        ),
        department_name=dept_name,
        visibility=str(getattr(lib, "visibility", "private") or "private"),
        allow_download=allow_download_out,
        member_count=member_count,
        is_owner=bool(is_owner),
        is_writeable=bool(is_write),
        parent_id=int(pid) if pid is not None else None,
        root_library_id=int(root.id),
        depth=int(depth),
        can_manage=bool(can_manage),
    )


@router.post("/", response_model=LibraryRead)
def create_library(
    lib_in: LibraryCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    parent_lib: Library | None = None
    if lib_in.parent_id is not None:
        parent_lib = db.query(Library).filter(Library.id == lib_in.parent_id).first()
        if not parent_lib or getattr(parent_lib, "deleted_at", None) is not None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="上级资料库不存在")
        _, _can_write_parent = has_library_access(
            db, parent_lib.id, current_user, require_write=True
        )
        if not _can_write_parent:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权在上级资料库下创建子库")
        pd = library_depth_from_root(db, parent_lib)
        if pd >= 3:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="最多支持三级资料库，无法在第三级下再创建子库")
        if lib_in.member_user_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="子库继承一级库的访问权限，创建时请勿指定成员",
            )

    dept_id = lib_in.department_id
    dept = None
    # 一级资料库：校验所属部门权限
    if lib_in.parent_id is None and dept_id is not None:
        dept = db.query(Department).filter(Department.id == dept_id).first()
        if not dept:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="部门不存在")
        acc = _get_accessible_department_ids(db, current_user)
        if dept_id not in acc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权在该部门创建资料库")

    visibility = lib_in.visibility or "private"
    allow_dl = False if lib_in.allow_download is None else bool(lib_in.allow_download)

    # 创建子库：字段继承根库（可见性、部门、下载策略与一级库一致）
    if lib_in.parent_id is not None and parent_lib is not None:
        root_acl = resolve_root_library(db, parent_lib)
        dept_id = getattr(root_acl, "department_id", None)
        dept = None
        if dept_id is not None:
            dept = db.query(Department).filter(Department.id == dept_id).first()
        visibility = str(getattr(root_acl, "visibility", "private") or "private")
        allow_dl = bool(getattr(root_acl, "allow_download", False))

    # visibility 校验（一级新建）
    if lib_in.parent_id is None:
        if visibility not in {"private", "department", "public"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="可见性取值非法")
        if visibility == "department" and dept_id is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="部门可见库必须指定所属部门")
        if visibility == "public" and dept_id is not None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="部门库不支持设置为公开库")

    display_name = _normalize_library_name(lib_in.name)
    if not display_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="资料库名称不能为空")
    if lib_in.parent_id is not None and parent_lib is not None:
        taken = _library_name_taken(
            db,
            display_name,
            department_id=None,
            owner_id=None,
            parent_id=parent_lib.id,
        )
    else:
        taken = _library_name_taken(
            db,
            display_name,
            department_id=dept_id,
            owner_id=current_user.id,
        )
    if taken:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="与已有文件库重名，请重新输入其他名称",
        )

    lib = Library(
        name=display_name,
        description=lib_in.description,
        owner_id=current_user.id,
        department_id=dept_id,
        visibility=visibility,
        allow_download=allow_dl,
        parent_id=parent_lib.id if lib_in.parent_id is not None and parent_lib else None,
    )
    db.add(lib)

    member_count_for_read = 0
    dept_name = dept.name if dept_id is not None else None
    audit_username = (current_user.username or "")[:50]
    try:
        db.flush()
        # 指定成员：仅一级资料库支持（成员挂在根库）
        if lib_in.parent_id is None and lib_in.member_user_ids:
            # bool 是 int 子类，需排除，避免 JSON 异常数据导致误解析
            user_ids = {
                int(uid)
                for uid in lib_in.member_user_ids
                if isinstance(uid, int) and not isinstance(uid, bool)
            }
            # 排除自己，避免 Owner 同时作为成员
            user_ids.discard(current_user.id)
            if user_ids:
                users = db.query(User).filter(User.id.in_(user_ids), User.is_active == True).all()
                valid_ids = {u.id for u in users}
                member_count_for_read = len(valid_ids)
                for uid in valid_ids:
                    member = LibraryMember(
                        library_id=lib.id,
                        user_id=uid,
                        role="read",
                    )
                    db.add(member)
        log_audit(
            db,
            current_user.id,
            audit_username,
            "create_library",
            "library",
            lib.id,
            f"name={lib_in.name} dept={dept_id} parent={lib_in.parent_id}",
            ip_address=get_client_ip(request),
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        # flush 阶段也可能因库表唯一约束、并发等触发，与业务层重名同一提示
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="与已有文件库重名，请重新输入其他名称",
        ) from None
    db.refresh(lib)
    return _lib_to_read(
        db,
        lib,
        current_user.id,
        current_user_obj=current_user,
        is_owner=True,
        is_write=True,
        dept_name=dept_name,
        member_count=member_count_for_read,
    )


@router.get("/trash", response_model=List[LibraryTrashRead])
def list_library_trash(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """列出已软删除的资料库（仅拥有者或超级管理员可见）。"""

    q = db.query(Library).filter(Library.deleted_at.isnot(None))
    if not current_user.is_superuser:
        # 拥有者或对应部门负责人可见已删除的资料库
        from sqlalchemy import or_
        from backend.app.models.department import Department

        q = (
            q.outerjoin(Department, Library.department_id == Department.id)
            .filter(
                or_(
                    Library.owner_id == current_user.id,
                    Department.leader_user_id == current_user.id,
                )
            )
        )
    libs = q.order_by(Library.deleted_at.desc()).all()

    result: list[LibraryTrashRead] = []
    for l in libs:
        r = _lib_to_read(
            db,
            l,
            current_user.id,
            current_user_obj=current_user,
            is_owner=l.owner_id == current_user.id,
            is_write=True,
        )
        owner_username: str | None = None
        if getattr(l, "owner", None):
            owner_username = l.owner.username or l.owner.email or f"用户{l.owner.id}"
        result.append(
            LibraryTrashRead(
                **r.model_dump(),
                deleted_at=l.deleted_at,
                owner_username=owner_username,
            )
        )
    return result


@router.get("/", response_model=List[LibraryRead])
def list_libraries(
    limit: int = Query(50, ge=1, le=200, description="每页数量"),
    offset: int = Query(0, ge=0, description="起始偏移量"),
    include_department: bool = Query(True, description="是否包含部门库"),
    roots_only: bool = Query(True, description="仅列出根级（一级）资料库；首页「我的文件库」与部门根列表"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """列出当前用户可访问的资料库（拥有、分享、部门库）。支持简单 limit/offset 分页。"""
    q = libraries_accessible_base_query(db, current_user)
    if roots_only:
        q = q.filter(Library.parent_id.is_(None))
    if not include_department:
        q = q.filter(Library.department_id.is_(None))
    q = q.order_by(Library.created_at.desc())
    libs = q.offset(offset).limit(limit).all()
    if not libs:
        return []

    acc_dept_ids = _get_accessible_department_ids(db, current_user)

    owner_ids = {l.owner_id for l in libs if getattr(l, "owner_id", None)}
    owner_username_by_id: dict[int, str] = {}
    if owner_ids:
        for u in db.query(User).filter(User.id.in_(owner_ids)).all():
            owner_username_by_id[u.id] = u.username or u.email or f"用户{u.id}"

    dept_ids = {l.department_id for l in libs if getattr(l, "department_id", None)}
    dept_name_by_id: dict[int, str] = {}
    if dept_ids:
        for d in db.query(Department).filter(Department.id.in_(dept_ids)).all():
            dept_name_by_id[d.id] = d.name

    root_ids_needed = list({resolve_root_library(db, l).id for l in libs})
    cnt_rows = (
        db.query(LibraryMember.library_id, func.count(LibraryMember.id))
        .filter(LibraryMember.library_id.in_(root_ids_needed))
        .group_by(LibraryMember.library_id)
        .all()
    )
    member_count_by_root: dict[int, int] = {}
    for row in cnt_rows:
        lid_raw, cnt_raw = row[0], row[1]
        if lid_raw is None:
            continue
        member_count_by_root[int(lid_raw)] = int(cnt_raw) if cnt_raw is not None else 0

    result: list[LibraryRead] = []
    for l in libs:
        is_write = write_access_for_listed_library(db, l, current_user, acc_dept_ids)
        dept_name = dept_name_by_id.get(l.department_id) if l.department_id else None
        owner_username = owner_username_by_id.get(l.owner_id) if l.owner_id else None
        rid = resolve_root_library(db, l).id
        mc = member_count_by_root.get(rid, 0)
        result.append(
            _lib_to_read(
                db,
                l,
                current_user.id,
                current_user_obj=current_user,
                is_owner=l.owner_id == current_user.id,
                is_write=is_write,
                dept_name=dept_name,
                owner_username=owner_username,
                member_count=mc,
            )
        )
    return result


def _describe_share_scope_for_owner(lib: Library, dept_name: str | None, member_count: int) -> str:
    """从拥有者视角描述文件库共享范围。"""
    visibility = getattr(lib, "visibility", "private")
    if visibility == "public":
        base = "公开（所有用户）"
    elif visibility == "department":
        base = f"{dept_name or '所属部门'} 部门成员"
    else:
        base = "仅自己"
    if member_count:
        base += f" + {member_count} 位指定成员"
    return base


def _describe_share_scope_for_receiver(
    lib: Library,
    dept_name: str | None,
    is_member: bool,
) -> str:
    """从接收者视角描述为何可以访问该库。"""
    visibility = getattr(lib, "visibility", "private")
    if is_member:
        return "被添加为库成员"
    if visibility == "public":
        return "公开文件库"
    if visibility == "department":
        return f"{dept_name or '所属部门'} 部门文件库"
    return "可访问的文件库"


@router.get("/shared/mine", response_model=List[SharedLibraryRow])
def list_shared_libraries_mine(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    我分享的文件库：
    - 以当前用户为拥有者
    - visibility 为 public/department，或存在指定成员
    """
    from sqlalchemy import func

    rows = (
        db.query(
            Library,
            User.username.label("owner_username"),
            func.count(LibraryMember.user_id).label("member_cnt"),
            Department.name.label("dept_name"),
        )
        .join(User, Library.owner_id == User.id)
        .outerjoin(LibraryMember, LibraryMember.library_id == Library.id)
        .outerjoin(Department, Library.department_id == Department.id)
        .filter(Library.owner_id == current_user.id, Library.deleted_at.is_(None))
        .group_by(Library.id, User.username, Department.name)
        .order_by(Library.created_at.desc())
        .all()
    )
    result: list[SharedLibraryRow] = []
    for lib, owner_username, member_cnt, dept_name in rows:
        member_cnt = int(member_cnt or 0)
        visibility = getattr(lib, "visibility", "private")
        # 仅展示实际对外共享的库
        if visibility == "private" and member_cnt == 0:
            continue
        scope = _describe_share_scope_for_owner(lib, dept_name, member_cnt)
        result.append(
            SharedLibraryRow(
                id=lib.id,
                name=lib.name,
                description=lib.description,
                owner_username=owner_username,
                department_name=dept_name,
                visibility=visibility,
                share_scope=scope,
                can_write=True,
                created_at=lib.created_at,
            )
        )
    return result


@router.get("/shared/to-me", response_model=List[SharedLibraryRow])
def list_shared_libraries_to_me(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    分享给我的文件库：
    - 当前用户不是拥有者
    - 但通过公开库 / 部门库 / 库成员等方式获得访问权限
    """
    from sqlalchemy import func

    lib_ids = get_accessible_library_ids(db, current_user)
    if not lib_ids:
        return []

    # 当前用户作为成员加入的库
    member_lib_ids = {
        lid
        for (lid,) in db.query(LibraryMember.library_id)
        .filter(LibraryMember.user_id == current_user.id, LibraryMember.library_id.in_(lib_ids))
        .all()
    }

    rows = (
        db.query(
            Library,
            User.username.label("owner_username"),
            func.count(LibraryMember.user_id).label("member_cnt"),
            Department.name.label("dept_name"),
        )
        .join(User, Library.owner_id == User.id)
        .outerjoin(LibraryMember, LibraryMember.library_id == Library.id)
        .outerjoin(Department, Library.department_id == Department.id)
        .filter(
            Library.id.in_(lib_ids),
            Library.owner_id != current_user.id,
            Library.deleted_at.is_(None),
        )
        .group_by(Library.id, User.username, Department.name)
        .order_by(Library.created_at.desc())
        .all()
    )

    result: list[SharedLibraryRow] = []
    for lib, owner_username, member_cnt, dept_name in rows:
        visibility = getattr(lib, "visibility", "private")
        is_member = lib.id in member_lib_ids
        scope = _describe_share_scope_for_receiver(lib, dept_name, is_member)
        # 计算写权限
        _, is_write = has_library_access(db, lib.id, current_user)
        result.append(
            SharedLibraryRow(
                id=lib.id,
                name=lib.name,
                description=lib.description,
                owner_username=owner_username,
                department_name=dept_name,
                visibility=visibility,
                share_scope=scope,
                can_write=is_write,
                created_at=lib.created_at,
            )
        )
    return result


@router.get("/{library_id}/children", response_model=List[LibraryRead])
def list_child_libraries(
    library_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """列出指定资料库的直接子库（二级 / 三级）。"""
    lib, _ = has_library_access(db, library_id, current_user)
    children = (
        db.query(Library)
        .filter(Library.parent_id == lib.id, Library.deleted_at.is_(None))
        .order_by(Library.updated_at.desc())
        .all()
    )
    acc_dept_ids = _get_accessible_department_ids(db, current_user)
    rid = resolve_root_library(db, lib).id
    mc_rows = (
        db.query(func.count(LibraryMember.id)).filter(LibraryMember.library_id == rid).scalar()
        or 0
    )
    mc = int(mc_rows)
    out: list[LibraryRead] = []
    for ch in children:
        iw = write_access_for_listed_library(db, ch, current_user, acc_dept_ids)
        out.append(
            _lib_to_read(
                db,
                ch,
                current_user.id,
                current_user_obj=current_user,
                is_owner=ch.owner_id == current_user.id,
                is_write=iw,
                member_count=mc,
            )
        )
    return out


@router.get("/{library_id}/breadcrumb", response_model=List[LibraryBreadcrumbItem])
def library_breadcrumb(
    library_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """从一级根库到当前资料库的面包屑路径。"""
    lib, _ = has_library_access(db, library_id, current_user)
    chain_rev: list[LibraryBreadcrumbItem] = []
    cur: Library | None = lib
    hops = 0
    while cur is not None and hops < 32:
        hops += 1
        chain_rev.append(LibraryBreadcrumbItem(id=int(cur.id), name=(cur.name or "") or ""))
        if cur.parent_id is None:
            break
        cur = db.query(Library).filter(Library.id == cur.parent_id).first()
    return list(reversed(chain_rev))


def _breadcrumb_label_chain(db: Session, lib: Library, max_parts: int = 4) -> str:
    parts: list[str] = []
    cur: Library | None = lib
    hops = 0
    while cur is not None and hops < max_parts + 16:
        hops += 1
        parts.append((cur.name or "").strip() or f"#{cur.id}")
        if cur.parent_id is None:
            break
        cur = db.query(Library).filter(Library.id == cur.parent_id).first()
    chain = list(reversed(parts))
    if len(chain) > max_parts:
        chain = chain[-max_parts:]
        return "… / " + " / ".join(chain)
    return " / ".join(chain)


def _library_move_scope_kind(lib: Library) -> str:
    """资料库所在权限树的类型：仅可挂到同类根树下（部门库 / 个人库 / 公开库）。"""
    if getattr(lib, "department_id", None) is not None:
        return "department"
    vis = str(getattr(lib, "visibility", "private") or "private").lower()
    if vis == "public":
        return "public"
    return "personal"


def _same_department_for_move(mov_root: Library, cand_root: Library) -> bool:
    """部门资料库只能挂到同一 department_id 下的资料库树内（不允许跨部门）。"""
    if _library_move_scope_kind(mov_root) != "department":
        return True
    a = getattr(mov_root, "department_id", None)
    b = getattr(cand_root, "department_id", None)
    if a is None or b is None:
        return False
    return int(a) == int(b)


@router.get("/{library_id}/move-targets", response_model=List[LibraryMoveTarget])
def list_library_move_targets(
    library_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """列出可将当前资料库移动到的父级（含「一级根目录」选项）。用于前端选择。"""
    mov, _ = has_library_access(db, library_id, current_user)
    check_can_manage_library(mov, current_user, db)
    desc = _collect_descendant_library_ids(db, mov.id)
    span = _subtree_depth_span(db, mov)
    mov_root = resolve_root_library(db, mov)
    mov_kind = _library_move_scope_kind(mov_root)

    targets: list[LibraryMoveTarget] = []

    if mov.parent_id is not None:
        if 1 + span <= 3:
            taken_root = _library_name_taken(
                db,
                mov.name or "",
                department_id=mov.department_id,
                owner_id=mov.owner_id,
                parent_id=None,
                exclude_library_id=mov.id,
            )
            if not taken_root:
                targets.append(
                    LibraryMoveTarget(
                        parent_id=None,
                        label="一级资料库（根目录）",
                    )
                )

    base_q = libraries_accessible_base_query(db, current_user).filter(
        Library.deleted_at.is_(None)
    )
    for cand in base_q.all():
        if cand.id in desc or cand.id == mov.id:
            continue
        cand_root = resolve_root_library(db, cand)
        if _library_move_scope_kind(cand_root) != mov_kind:
            continue
        if not _same_department_for_move(mov_root, cand_root):
            continue
        try:
            _, iw = has_library_access(db, cand.id, current_user, require_write=True)
        except HTTPException:
            continue
        if not iw:
            continue
        dp = library_depth_from_root(db, cand)
        if dp >= 3:
            continue
        if dp + 1 + span > 3:
            continue
        taken = _library_name_taken(
            db,
            mov.name or "",
            department_id=None,
            owner_id=None,
            parent_id=cand.id,
            exclude_library_id=mov.id,
        )
        if taken:
            continue
        label = _breadcrumb_label_chain(db, cand)
        targets.append(LibraryMoveTarget(parent_id=int(cand.id), label=label))

    targets.sort(key=lambda t: (t.parent_id is None, (t.label or "").lower()))
    return targets


@router.post("/{library_id}/move", response_model=LibraryRead)
def move_library(
    library_id: int,
    body: MoveLibraryBody,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """移动资料库到新的父级，或设为一级资料库。"""
    mov = db.query(Library).filter(Library.id == library_id).first()
    if not mov or getattr(mov, "deleted_at", None) is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="资料库不存在")
    _, _rw = has_library_access(db, library_id, current_user)
    check_can_manage_library(mov, current_user, db)

    old_root = resolve_root_library(db, mov)
    desc = _collect_descendant_library_ids(db, mov.id)
    span = _subtree_depth_span(db, mov)

    new_parent_id = body.parent_id
    if new_parent_id is not None:
        if int(new_parent_id) == int(mov.id) or int(new_parent_id) in desc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="不能将资料库移动到自身或其下级之下",
            )
        plib = db.query(Library).filter(Library.id == int(new_parent_id)).first()
        if not plib or getattr(plib, "deleted_at", None) is not None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="目标父资料库不存在")
        has_library_access(db, plib.id, current_user, require_write=True)
        mov_root_for_move = resolve_root_library(db, mov)
        parent_root = resolve_root_library(db, plib)
        if _library_move_scope_kind(mov_root_for_move) != _library_move_scope_kind(parent_root):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="只能将资料库移动到同类文件库之下：部门库→部门库，个人库→个人库，公开库→公开库",
            )
        if not _same_department_for_move(mov_root_for_move, parent_root):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="部门文件库仅可在本部门内调整位置，不能挂载到其他部门的资料库下",
            )
        prospective_acl_id = parent_root.id
        d_new = library_depth_from_root(db, plib) + 1
        taken = _library_name_taken(
            db,
            mov.name or "",
            department_id=None,
            owner_id=None,
            parent_id=int(new_parent_id),
            exclude_library_id=mov.id,
        )
    else:
        plib = None
        prospective_acl_id = int(mov.id)
        d_new = 1
        taken = _library_name_taken(
            db,
            mov.name or "",
            department_id=mov.department_id,
            owner_id=mov.owner_id,
            parent_id=None,
            exclude_library_id=mov.id,
        )

    if old_root.id != prospective_acl_id:
        if mov.id != old_root.id and new_parent_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="不能将子资料库移入另一权限树下的资料库；可先移到一级根目录，再移入目标树，或直接移动整棵一级资料库",
            )

    if d_new + span > 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="移动后资料库层级将超过三级，请调整目标位置或先缩短子树",
        )
    if taken:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="目标位置下已存在同名资料库，请先改名",
        )

    old_acl_id = int(old_root.id)

    mov.parent_id = int(new_parent_id) if new_parent_id is not None else None
    db.flush()

    new_acl = resolve_root_library(db, mov)
    new_acl_id = int(new_acl.id)

    _sync_subtree_fields_from_acl_root(db, mov)

    if old_acl_id != new_acl_id:
        if mov.id == old_root.id:
            _merge_library_members(db, mov.id, new_acl_id, delete_from_source=True)
        elif new_parent_id is None:
            _merge_library_members(db, old_acl_id, mov.id, delete_from_source=False)

    log_audit(
        db,
        current_user.id,
        current_user.username,
        "move_library",
        "library",
        mov.id,
        f"parent={new_parent_id}",
        ip_address=get_client_ip(request),
    )
    db.commit()
    db.refresh(mov)

    acc_dept_ids = _get_accessible_department_ids(db, current_user)
    iw = write_access_for_listed_library(db, mov, current_user, acc_dept_ids)
    rid = resolve_root_library(db, mov).id
    mc_rows = (
        db.query(func.count(LibraryMember.id)).filter(LibraryMember.library_id == rid).scalar()
        or 0
    )
    return _lib_to_read(
        db,
        mov,
        current_user.id,
        current_user_obj=current_user,
        is_owner=mov.owner_id == current_user.id,
        is_write=iw,
        member_count=int(mc_rows),
    )


@router.get("/{library_id}", response_model=LibraryRead)
def get_library(
    library_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lib, is_write = has_library_access(db, library_id, current_user)
    return _lib_to_read(
        db,
        lib,
        current_user.id,
        current_user_obj=current_user,
        is_owner=lib.owner_id == current_user.id,
        is_write=is_write,
    )


@router.patch("/{library_id}", response_model=LibraryRead)
def update_library(
    library_id: int,
    lib_in: LibraryUpdate,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lib, _ = has_library_access(db, library_id, current_user)
    check_can_manage_library(lib, current_user, db)
    is_child = getattr(lib, "parent_id", None) is not None
    if is_child and (lib_in.visibility is not None or lib_in.allow_download is not None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="子库的可见性与下载策略继承一级库，请在一级资料库中修改",
        )
    if lib_in.name is not None:
        display_name = _normalize_library_name(lib_in.name)
        if not display_name:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="资料库名称不能为空")
        parent_id_for_name = getattr(lib, "parent_id", None)
        if parent_id_for_name is not None:
            taken = _library_name_taken(
                db,
                display_name,
                department_id=None,
                owner_id=None,
                parent_id=parent_id_for_name,
                exclude_library_id=lib.id,
            )
        else:
            taken = _library_name_taken(
                db,
                display_name,
                department_id=lib.department_id,
                owner_id=lib.owner_id,
                exclude_library_id=lib.id,
            )
        if taken:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="与已有文件库重名，请重新输入其他名称",
            )
        lib.name = display_name
    if lib_in.description is not None:
        lib.description = lib_in.description
    if lib_in.visibility is not None:
        new_visibility = lib_in.visibility or "private"
        if new_visibility not in {"private", "department", "public"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="可见性取值非法")
        # 现有库若为部门库，则不允许改成 public，始终保持 department 语义
        if lib.department_id is not None and new_visibility == "public":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="部门库不支持设置为公开库")
        if new_visibility == "department" and lib.department_id is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="部门可见库必须指定所属部门")
        lib.visibility = new_visibility
    if lib_in.allow_download is not None:
        lib.allow_download = bool(lib_in.allow_download)
    db.commit()
    db.refresh(lib)
    log_audit(
        db,
        current_user.id,
        current_user.username,
        "update_library",
        "library",
        lib.id,
        f"name={lib.name}",
        ip_address=get_client_ip(request),
    )
    return _lib_to_read(
        db,
        lib,
        current_user.id,
        current_user_obj=current_user,
        is_owner=lib.owner_id == current_user.id,
        is_write=True,
    )


@router.get("/{library_id}/members")
def list_library_members(
    library_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """列出资料库成员（仅拥有者或管理员可查看）。子库成员与一级根库相同。"""
    lib, _ = has_library_access(db, library_id, current_user)
    root = resolve_root_library(db, lib)
    if not (current_user.is_superuser or root.owner_id == current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅资料库拥有者或管理员可查看成员")
    rows = (
        db.query(LibraryMember, User)
        .join(User, LibraryMember.user_id == User.id)
        .filter(LibraryMember.library_id == root.id)
        .all()
    )
    return [
        {
            "user_id": m.user_id,
            "username": u.username,
            "role": m.role,
        }
        for m, u in rows
    ]


@router.post("/{library_id}/members", status_code=status.HTTP_204_NO_CONTENT)
def add_or_update_library_member(
    library_id: int,
    user_id: int = Query(..., description="成员用户 ID"),
    role: str = Query("read", description="角色：read 或 write"),
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """添加或更新资料库成员（仅拥有者或管理员），仅一级资料库可改"""
    lib, _ = has_library_access(db, library_id, current_user)
    if getattr(lib, "parent_id", None) is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="子库继承一级库权限，请在一级资料库中管理成员",
        )
    if not (current_user.is_superuser or lib.owner_id == current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅资料库拥有者或管理员可管理成员")
    if role not in {"read", "write"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="角色取值非法")
    if user_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无需将自己添加为成员")
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在或已禁用")
    member = (
        db.query(LibraryMember)
        .filter(LibraryMember.library_id == library_id, LibraryMember.user_id == user_id)
        .first()
    )
    if member:
        member.role = role
        action = "update_library_member"
    else:
        member = LibraryMember(library_id=library_id, user_id=user_id, role=role)
        db.add(member)
        action = "add_library_member"
    db.commit()
    log_audit(
        db,
        current_user.id,
        current_user.username,
        action,
        "library_member",
        library_id,
        f"user_id={user_id} role={role}",
        ip_address=get_client_ip(request),
    )
    # 通知被添加/更新的成员
    try:
        title = "资料库权限更新"
        msg = f"您被授予资料库「{lib.name}」的 {('只读' if role == 'read' else '读写')} 权限"
        create_notification(db, user_id=user_id, type="info", title=title, message=msg)
    except Exception:
        # 通知失败不影响主流程
        pass


@router.delete("/{library_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_library_member(
    library_id: int,
    user_id: int,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """移除资料库成员（仅拥有者或管理员），仅一级资料库可改"""
    lib, _ = has_library_access(db, library_id, current_user)
    if getattr(lib, "parent_id", None) is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="子库继承一级库权限，请在一级资料库中管理成员",
        )
    if not (current_user.is_superuser or lib.owner_id == current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅资料库拥有者或管理员可管理成员")
    member = (
        db.query(LibraryMember)
        .filter(LibraryMember.library_id == library_id, LibraryMember.user_id == user_id)
        .first()
    )
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="成员不存在")
    db.delete(member)
    db.commit()
    log_audit(
        db,
        current_user.id,
        current_user.username,
        "remove_library_member",
        "library_member",
        library_id,
        f"user_id={user_id}",
        ip_address=get_client_ip(request),
    )


@router.delete("/{library_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_library(
    library_id: int,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """软删除：将资料库移入回收站（可恢复）"""
    lib, _ = has_library_access(db, library_id, current_user)
    check_can_manage_library(lib, current_user, db)
    if getattr(lib, "deleted_at", None) is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="资料库已在回收站")

    from datetime import timezone

    now = datetime.now(timezone.utc)
    lib.deleted_at = now
    log_audit(
        db,
        current_user.id,
        current_user.username,
        "delete_library",
        "library",
        lib.id,
        f"name={lib.name} (soft)",
        ip_address=get_client_ip(request),
    )
    db.commit()


@router.post("/{library_id}/restore", response_model=LibraryRead)
def restore_library(
    library_id: int,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """从回收站恢复资料库"""
    lib = db.query(Library).filter(Library.id == library_id).first()
    if not lib:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="资料库不存在")
    if getattr(lib, "deleted_at", None) is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="资料库未在回收站")
    check_can_manage_library(lib, current_user, db)

    if getattr(lib, "parent_id", None) is not None:
        restore_taken = _library_name_taken(
            db,
            lib.name or "",
            department_id=None,
            owner_id=None,
            parent_id=lib.parent_id,
            exclude_library_id=lib.id,
        )
    else:
        restore_taken = _library_name_taken(
            db,
            lib.name or "",
            department_id=lib.department_id,
            owner_id=lib.owner_id,
            exclude_library_id=lib.id,
        )
    if restore_taken:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="已存在同名资料库，请先重命名回收站中的资料库或删除/重命名现有资料库后再恢复",
        )

    lib.deleted_at = None
    db.commit()
    db.refresh(lib)
    log_audit(
        db,
        current_user.id,
        current_user.username,
        "restore_library",
        "library",
        lib.id,
        f"name={lib.name}",
        ip_address=get_client_ip(request),
    )
    return _lib_to_read(
        db,
        lib,
        current_user.id,
        current_user_obj=current_user,
        is_owner=lib.owner_id == current_user.id,
        is_write=True,
    )


@router.delete("/trash/{library_id}", status_code=status.HTTP_204_NO_CONTENT)
def permanent_delete_library(
    library_id: int,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """彻底删除回收站中的资料库（不可恢复）"""
    from sqlalchemy import func

    from backend.app.api.files import _permanent_delete_entry
    from backend.app.models.file import FileEntry

    lib = db.query(Library).filter(Library.id == library_id).first()
    if not lib:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="资料库不存在")
    if getattr(lib, "deleted_at", None) is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="仅可彻底删除回收站中的资料库")
    check_can_manage_library(lib, current_user, db)

    entries = (
        db.query(FileEntry)
        .filter(FileEntry.library_id == library_id)
        .order_by(func.length(FileEntry.path).desc())
        .all()
    )
    for entry in entries:
        _permanent_delete_entry(db, entry)

    log_audit(
        db,
        current_user.id,
        current_user.username,
        "permanent_delete_library",
        "library",
        lib.id,
        f"name={lib.name}",
        ip_address=get_client_ip(request),
    )
    db.delete(lib)
    db.commit()

