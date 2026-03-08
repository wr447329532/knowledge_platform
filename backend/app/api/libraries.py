from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.core.audit import log_audit
from backend.app.core.library_access import (
    check_can_manage_library,
    get_accessible_library_ids,
    has_library_access,
)
from backend.app.db.session import get_db
from backend.app.models.library import Library
from backend.app.models.user import User


class LibraryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="资料库名称")
    description: str | None = None


class LibraryRead(BaseModel):
    id: int
    name: str
    description: str | None
    owner_id: int | None = None
    is_owner: bool | None = None  # 当前用户是否拥有者
    is_writeable: bool | None = None  # 当前用户是否可写（拥有者或 write 成员）

    class Config:
        from_attributes = True


class LibraryUpdate(BaseModel):
    name: str | None = Field(None, max_length=100)
    description: str | None = None


router = APIRouter(prefix="/libraries", tags=["libraries"])


@router.post("/", response_model=LibraryRead)
def create_library(
    lib_in: LibraryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lib = Library(
        name=lib_in.name,
        description=lib_in.description,
        owner_id=current_user.id,
    )
    db.add(lib)
    db.flush()
    log_audit(db, current_user.id, current_user.username, "create_library", "library", lib.id, f"name={lib_in.name}")
    db.commit()
    db.refresh(lib)
    return LibraryRead(
        id=lib.id,
        name=lib.name,
        description=lib.description,
        owner_id=lib.owner_id,
        is_owner=True,
        is_writeable=True,
    )


@router.get("/", response_model=List[LibraryRead])
def list_libraries(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """列出当前用户可访问的资料库（拥有或成员）。"""
    ids = get_accessible_library_ids(db, current_user)
    libs = db.query(Library).filter(Library.id.in_(ids)).order_by(Library.created_at.desc()).all()
    result = []
    for l in libs:
        _, is_write = has_library_access(db, l.id, current_user)
        result.append(LibraryRead(
            id=l.id,
            name=l.name,
            description=l.description,
            owner_id=l.owner_id,
            is_owner=l.owner_id == current_user.id,
            is_writeable=is_write,
        ))
    return result


@router.get("/{library_id}", response_model=LibraryRead)
def get_library(
    library_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lib, is_write = has_library_access(db, library_id, current_user)
    return LibraryRead(
        id=lib.id,
        name=lib.name,
        description=lib.description,
        owner_id=lib.owner_id,
        is_owner=lib.owner_id == current_user.id,
        is_writeable=is_write,
    )


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
    return LibraryRead(
        id=lib.id,
        name=lib.name,
        description=lib.description,
        owner_id=lib.owner_id,
        is_owner=lib.owner_id == current_user.id,
        is_writeable=True,
    )


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

