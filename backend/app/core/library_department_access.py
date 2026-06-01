"""
资料库「指定部门」访问权限（visibility=departments）。

指定部门及其子部门内的成员可访问；与 library.department_id（所属部门）解耦。
"""
from __future__ import annotations

from typing import Iterable, Set

from sqlalchemy.orm import Session

from backend.app.core.oversight_access import (
    expand_department_ids_with_descendants,
    get_department_parent_map,
)
from backend.app.models.department import Department
from backend.app.models.library import Library
from backend.app.models.library_access_department import LibraryAccessDepartment
from backend.app.models.user import User

VISIBILITY_DEPARTMENTS = "departments"


def list_access_department_ids(db: Session, root_library_id: int) -> list[int]:
    rows = (
        db.query(LibraryAccessDepartment.department_id)
        .filter(LibraryAccessDepartment.library_id == root_library_id)
        .order_by(LibraryAccessDepartment.department_id)
        .all()
    )
    return [int(r[0]) for r in rows]


def list_access_department_names(db: Session, root_library_id: int) -> list[str]:
    ids = list_access_department_ids(db, root_library_id)
    if not ids:
        return []
    rows = db.query(Department.id, Department.name).filter(Department.id.in_(ids)).all()
    name_map = {int(r[0]): r[1] for r in rows}
    return [name_map[i] for i in ids if i in name_map]


def expand_granted_department_ids(db: Session, dept_ids: Iterable[int]) -> Set[int]:
    parent_map = get_department_parent_map(db)
    return expand_department_ids_with_descendants(parent_map, dept_ids)


def user_matches_granted_departments(
    db: Session,
    user: User,
    granted_dept_ids: Iterable[int],
    *,
    acc_dept_ids: Set[int] | None = None,
) -> bool:
    """用户所属部门子树与任一指定部门子树有交集即可访问。"""
    from backend.app.core.library_access import _get_accessible_department_ids

    if acc_dept_ids is None:
        acc_dept_ids = _get_accessible_department_ids(db, user)
    if not acc_dept_ids:
        return False
    grant_set = expand_granted_department_ids(db, granted_dept_ids)
    return bool(acc_dept_ids & grant_set)


def replace_library_access_departments(
    db: Session,
    root_library_id: int,
    dept_ids: Iterable[int],
) -> None:
    """同步根库的指定部门列表（全量替换）。"""
    normalized = sorted({int(d) for d in dept_ids if isinstance(d, int) and not isinstance(d, bool)})
    existing = {
        int(r.department_id): r
        for r in db.query(LibraryAccessDepartment)
        .filter(LibraryAccessDepartment.library_id == root_library_id)
        .all()
    }
    target = set(normalized)
    for did in existing.keys() - target:
        db.delete(existing[did])
    for did in target - existing.keys():
        db.add(LibraryAccessDepartment(library_id=root_library_id, department_id=did))


def clear_library_access_departments(db: Session, root_library_id: int) -> None:
    db.query(LibraryAccessDepartment).filter(
        LibraryAccessDepartment.library_id == root_library_id
    ).delete()


def get_library_ids_accessible_via_department_grants(db: Session, user: User) -> list[int]:
    """用户通过指定部门权限可访问的根库 id（含其子库由 get_accessible_library_ids 扩展）。"""
    from backend.app.core.library_access import (
        _expand_descendants_from_roots,
        _get_accessible_department_ids,
        _library_not_deleted,
    )

    acc_dept_ids = _get_accessible_department_ids(db, user)
    if not acc_dept_ids:
        return []

    not_deleted = _library_not_deleted()
    root_rows = (
        db.query(Library.id)
        .filter(Library.visibility == VISIBILITY_DEPARTMENTS, not_deleted, Library.parent_id.is_(None))
        .all()
    )
    root_ids = [int(r[0]) for r in root_rows]
    if not root_ids:
        return []

    grant_rows = (
        db.query(LibraryAccessDepartment.library_id, LibraryAccessDepartment.department_id)
        .filter(LibraryAccessDepartment.library_id.in_(root_ids))
        .all()
    )
    grants_by_lib: dict[int, list[int]] = {}
    for lid, did in grant_rows:
        grants_by_lib.setdefault(int(lid), []).append(int(did))

    parent_map = get_department_parent_map(db)
    matched_roots: set[int] = set()
    for lid, dept_ids in grants_by_lib.items():
        grant_set = expand_department_ids_with_descendants(parent_map, dept_ids)
        if acc_dept_ids & grant_set:
            matched_roots.add(lid)

    if not matched_roots:
        return []
    desc = _expand_descendants_from_roots(db, matched_roots)
    return list(matched_roots | desc)


def get_granted_department_ids_for_accessible_libraries(db: Session, user: User) -> Set[int]:
    """用户可访问的资料库所关联的指定部门 id（用于部门树补充入口）。"""
    from backend.app.core.library_access import get_accessible_library_ids, resolve_root_library

    lib_ids = get_accessible_library_ids(db, user)
    if not lib_ids:
        return set()
    libs = db.query(Library).filter(Library.id.in_(lib_ids), Library.deleted_at.is_(None)).all()
    root_ids: set[int] = set()
    for lib in libs:
        root_ids.add(resolve_root_library(db, lib).id)
    if not root_ids:
        return set()
    rows = (
        db.query(LibraryAccessDepartment.department_id)
        .filter(LibraryAccessDepartment.library_id.in_(root_ids))
        .distinct()
        .all()
    )
    return {int(r[0]) for r in rows if r and r[0] is not None}
