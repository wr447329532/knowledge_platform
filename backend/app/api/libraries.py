from datetime import datetime, timedelta, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.core.audit import get_client_ip, log_audit
from backend.app.core.library_access import (
    _get_accessible_department_ids,
    check_can_manage_library,
    get_accessible_library_ids,
    has_library_access,
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
    department_id: int | None = None  # 指定则创建为部门库
    # 可见性：private=私有；department=部门可见；public=全员可见（仅个人库）
    visibility: str = "private"
    # 指定成员列表（无论可见性为何，均可用于补充访问权限）
    member_user_ids: list[int] | None = None


class LibraryRead(BaseModel):
    id: int
    name: str
    description: str | None
    owner_id: int | None = None
    department_id: int | None = None
    department_name: str | None = None
    visibility: str | None = None
    allow_download: bool | None = None
    member_count: int | None = None
    is_owner: bool | None = None  # 当前用户是否拥有者
    is_writeable: bool | None = None  # 当前用户是否可写

    class Config:
        from_attributes = True


class LibraryTrashRead(LibraryRead):
    deleted_at: datetime

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


router = APIRouter(prefix="/libraries", tags=["libraries"])


def _lib_to_read(
    db: Session,
    lib: Library,
    current_user_id: int,
    *,
    is_owner: bool = False,
    is_write: bool = False,
    dept_name: str | None = None,
) -> LibraryRead:
    if dept_name is None and getattr(lib, "department_id", None) is not None:
        d = db.query(Department).filter(Department.id == lib.department_id).first()
        dept_name = d.name if d else None
    member_count = len(getattr(lib, "members", []) or [])
    return LibraryRead(
        id=lib.id,
        name=lib.name,
        description=lib.description,
        owner_id=lib.owner_id,
        department_id=getattr(lib, "department_id", None),
        department_name=dept_name,
        visibility=getattr(lib, "visibility", "private"),
        allow_download=getattr(lib, "allow_download", True),
        member_count=member_count,
        is_owner=is_owner,
        is_writeable=is_write,
    )


@router.post("/", response_model=LibraryRead)
def create_library(
    lib_in: LibraryCreate,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dept_id = lib_in.department_id
    dept = None
    if dept_id is not None:
        dept = db.query(Department).filter(Department.id == dept_id).first()
        if not dept:
            from fastapi import HTTPException, status
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="部门不存在")
        acc = _get_accessible_department_ids(db, current_user)
        if dept_id not in acc:
            from fastapi import HTTPException, status
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权在该部门创建资料库")

    # visibility 校验
    visibility = lib_in.visibility or "private"
    if visibility not in {"private", "department", "public"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="可见性取值非法")
    # 部门可见库必须指定所属部门
    if visibility == "department" and dept_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="部门可见库必须指定所属部门")
    # 部门库不允许设置为 public，避免「部门库但全员可见」的混淆语义
    if visibility == "public" and dept_id is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="部门库不支持设置为公开库")

    lib = Library(
        name=lib_in.name,
        description=lib_in.description,
        owner_id=current_user.id,
        department_id=dept_id,
        visibility=visibility,
        allow_download=True,
    )
    db.add(lib)
    db.flush()

    # 指定成员：创建初始成员（默认 role=read）
    if lib_in.member_user_ids:
        user_ids = set(int(uid) for uid in lib_in.member_user_ids if isinstance(uid, int))
        # 排除自己，避免 Owner 同时作为成员
        user_ids.discard(current_user.id)
        if user_ids:
            users = db.query(User).filter(User.id.in_(user_ids), User.is_active == True).all()
            valid_ids = {u.id for u in users}
            for uid in valid_ids:
                member = LibraryMember(
                    library_id=lib.id,
                    user_id=uid,
                    role="read",
                )
                db.add(member)

    dept_name = dept.name if dept_id is not None else None
    log_audit(
        db,
        current_user.id,
        current_user.username,
        "create_library",
        "library",
        lib.id,
        f"name={lib_in.name} dept={dept_id}",
        ip_address=get_client_ip(request),
    )
    db.commit()
    db.refresh(lib)
    return _lib_to_read(db, lib, current_user.id, is_owner=True, is_write=True, dept_name=dept_name)


@router.get("/trash", response_model=List[LibraryTrashRead])
def list_library_trash(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """列出已软删除的资料库（仅拥有者或超级管理员可见），超过 30 天自动彻底删除"""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=30)
    # 自动彻底删除超过 30 天的已删除资料库
    old_libs = (
        db.query(Library)
        .filter(Library.deleted_at.isnot(None), Library.deleted_at < cutoff)
        .all()
    )
    for lib in old_libs:
        if current_user.is_superuser or lib.owner_id == current_user.id:
            from sqlalchemy import func
            from backend.app.api.files import _permanent_delete_entry
            from backend.app.models.file import FileEntry
            entries = (
                db.query(FileEntry)
                .filter(FileEntry.library_id == lib.id)
                .order_by(func.length(FileEntry.path).desc())
                .all()
            )
            for entry in entries:
                _permanent_delete_entry(db, entry)
            db.delete(lib)
    if old_libs:
        db.commit()

    q = db.query(Library).filter(Library.deleted_at.isnot(None))
    if not current_user.is_superuser:
        q = q.filter(Library.owner_id == current_user.id)
    libs = q.order_by(Library.deleted_at.desc()).all()
    result = []
    for l in libs:
        r = _lib_to_read(db, l, current_user.id, is_owner=l.owner_id == current_user.id, is_write=True)
        result.append(LibraryTrashRead(**r.model_dump(), deleted_at=l.deleted_at))
    return result


@router.get("/", response_model=List[LibraryRead])
def list_libraries(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """列出当前用户可访问的资料库（拥有、分享、部门库）。"""
    ids = get_accessible_library_ids(db, current_user)
    libs = db.query(Library).filter(Library.id.in_(ids)).order_by(Library.created_at.desc()).all()
    result = []
    for l in libs:
        _, is_write = has_library_access(db, l.id, current_user)
        result.append(_lib_to_read(db, l, current_user.id, is_owner=l.owner_id == current_user.id, is_write=is_write))
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


@router.get("/{library_id}", response_model=LibraryRead)
def get_library(
    library_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lib, is_write = has_library_access(db, library_id, current_user)
    return _lib_to_read(db, lib, current_user.id, is_owner=lib.owner_id == current_user.id, is_write=is_write)


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
    if lib_in.name is not None:
        lib.name = lib_in.name
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
    return _lib_to_read(db, lib, current_user.id, is_owner=lib.owner_id == current_user.id, is_write=True)


@router.get("/{library_id}/members")
def list_library_members(
    library_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """列出资料库成员（仅拥有者或管理员可查看）"""
    lib, _ = has_library_access(db, library_id, current_user)
    if not (current_user.is_superuser or lib.owner_id == current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅资料库拥有者或管理员可查看成员")
    rows = (
        db.query(LibraryMember, User)
        .join(User, LibraryMember.user_id == User.id)
        .filter(LibraryMember.library_id == library_id)
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
    """添加或更新资料库成员（仅拥有者或管理员）"""
    lib, _ = has_library_access(db, library_id, current_user)
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
    """移除资料库成员（仅拥有者或管理员）"""
    lib, _ = has_library_access(db, library_id, current_user)
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
    return _lib_to_read(db, lib, current_user.id, is_owner=lib.owner_id == current_user.id, is_write=True)


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

