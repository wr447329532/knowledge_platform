"""分管领导分管部门配置的读写。"""
from __future__ import annotations

from typing import Iterable, List

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.library_access import invalidate_department_access_cache
from backend.app.core.oversight_access import ROLE_DIVISION_LEADER, is_division_leader
from backend.app.models.department import Department
from backend.app.models.user import User
from backend.app.models.user_supervised_department import UserSupervisedDepartment


def list_supervised_department_ids(db: Session, user_id: int) -> List[int]:
    rows = (
        db.query(UserSupervisedDepartment.department_id)
        .filter(UserSupervisedDepartment.user_id == user_id)
        .order_by(UserSupervisedDepartment.department_id.asc())
        .all()
    )
    return [int(r[0]) for r in rows]


def replace_supervised_departments(
    db: Session,
    user: User,
    department_ids: Iterable[int] | None,
) -> List[int]:
    """
    替换用户的分管部门列表（仅 direct 根节点，不含子部门枚举）。
    非分管领导角色传入非空列表时拒绝。
    """
    ids = sorted({int(x) for x in (department_ids or []) if x is not None})

    if ids and not is_division_leader(user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="仅分管领导角色可配置分管部门",
        )

    if ids:
        existing = {
            int(r[0])
            for r in db.query(Department.id).filter(Department.id.in_(ids)).all()
        }
        missing = [i for i in ids if i not in existing]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"部门不存在：{missing}",
            )

    db.query(UserSupervisedDepartment).filter(
        UserSupervisedDepartment.user_id == user.id,
    ).delete(synchronize_session=False)

    for dept_id in ids:
        db.add(UserSupervisedDepartment(user_id=user.id, department_id=dept_id))

    invalidate_department_access_cache()
    return ids


def clear_supervised_departments_if_not_division_leader(db: Session, user: User) -> None:
    """角色从分管领导切换走后，清空分管配置。"""
    if is_division_leader(user):
        return
    db.query(UserSupervisedDepartment).filter(
        UserSupervisedDepartment.user_id == user.id,
    ).delete(synchronize_session=False)
    invalidate_department_access_cache()
