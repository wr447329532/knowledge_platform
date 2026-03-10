from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.core.audit import log_audit
from backend.app.core.library_access import (
    _get_accessible_department_ids,
    check_can_manage_library,
    get_accessible_library_ids,
    has_library_access,
)
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
    log_audit(db, current_user.id, current_user.username, "create_library", "library", lib.id, f"name={lib_in.name} dept={dept_id}")
    db.commit()
    db.refresh(lib)
    return _lib_to_read(db, lib, current_user.id, is_owner=True, is_write=True, dept_name=dept_name)


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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lib, is_write = has_library_access(db, library_id, current_user, require_write=True)
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
    log_audit(db, current_user.id, current_user.username, "update_library", "library", lib.id, f"name={lib.name}")
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
    log_audit(db, current_user.id, current_user.username, action, "library_member", library_id, f"user_id={user_id} role={role}")


@router.delete("/{library_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_library_member(
    library_id: int,
    user_id: int,
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
    log_audit(db, current_user.id, current_user.username, "remove_library_member", "library_member", library_id, f"user_id={user_id}")


@router.delete("/{library_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_library(
    library_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from sqlalchemy import func

    from backend.app.api.files import _permanent_delete_entry
    from backend.app.models.file import FileEntry

    lib, _ = has_library_access(db, library_id, current_user)
    check_can_manage_library(lib, current_user, db)

    # 级联删除：先彻底删除库内所有文件/目录（含回收站），再删资料库
    entries = (
        db.query(FileEntry)
        .filter(FileEntry.library_id == library_id)
        .order_by(func.length(FileEntry.path).desc())
        .all()
    )
    for entry in entries:
        _permanent_delete_entry(db, entry)

    log_audit(db, current_user.id, current_user.username, "delete_library", "library", lib.id, f"name={lib.name}")
    db.delete(lib)
    db.commit()

