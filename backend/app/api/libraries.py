from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
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
from backend.app.models.user import User


class LibraryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="资料库名称")
    description: str | None = None
    department_id: int | None = None  # 指定则创建为部门库


class LibraryRead(BaseModel):
    id: int
    name: str
    description: str | None
    owner_id: int | None = None
    department_id: int | None = None
    department_name: str | None = None
    is_owner: bool | None = None  # 当前用户是否拥有者
    is_writeable: bool | None = None  # 当前用户是否可写

    class Config:
        from_attributes = True


class LibraryUpdate(BaseModel):
    name: str | None = Field(None, max_length=100)
    description: str | None = None


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
    return LibraryRead(
        id=lib.id,
        name=lib.name,
        description=lib.description,
        owner_id=lib.owner_id,
        department_id=getattr(lib, "department_id", None),
        department_name=dept_name,
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
    lib = Library(
        name=lib_in.name,
        description=lib_in.description,
        owner_id=current_user.id,
        department_id=dept_id,
    )
    db.add(lib)
    db.flush()
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
    db.commit()
    db.refresh(lib)
    log_audit(db, current_user.id, current_user.username, "update_library", "library", lib.id, f"name={lib.name}")
    return _lib_to_read(db, lib, current_user.id, is_owner=lib.owner_id == current_user.id, is_write=True)


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

