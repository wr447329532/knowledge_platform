"""
只读监管角色（高管 / 分管领导）的部门范围与写权限判定。

- executive（高管）：全公司部门库只读，可浏览与下载，不可修改。
- division_leader（分管领导）：管理员指定分管部门（含子部门）内部门库只读。
"""
from __future__ import annotations

from typing import Iterable, Set

from sqlalchemy.orm import Session

from backend.app.models.user import User

ROLE_EXECUTIVE = "executive"
ROLE_DIVISION_LEADER = "division_leader"

READ_ONLY_OVERSIGHT_ROLES = frozenset({ROLE_EXECUTIVE, ROLE_DIVISION_LEADER})


def is_executive(user: User) -> bool:
    return getattr(user, "role", "staff") == ROLE_EXECUTIVE


def is_division_leader(user: User) -> bool:
    return getattr(user, "role", "staff") == ROLE_DIVISION_LEADER


def is_read_only_oversight(user: User) -> bool:
    """高管或分管领导：对部门库具备只读监管权限（浏览 + 下载，不可写）。"""
    return getattr(user, "role", "staff") in READ_ONLY_OVERSIGHT_ROLES


def expand_department_ids_with_descendants(
    parent_map: dict[int, int | None],
    root_ids: Iterable[int],
) -> Set[int]:
    """将部门根 id 扩展为含所有下级子部门的集合。"""
    children_map: dict[int | None, list[int]] = {}
    for did, pid in parent_map.items():
        children_map.setdefault(pid, []).append(int(did))

    out: Set[int] = set()
    for root in root_ids:
        rid = int(root)
        if rid not in parent_map:
            continue
        stack = [rid]
        while stack:
            cur = stack.pop()
            if cur in out:
                continue
            out.add(cur)
            for child in children_map.get(cur, []):
                stack.append(child)
    return out


def expand_user_department_subtree(
    parent_map: dict[int, int | None],
    department_id: int | None,
) -> Set[int]:
    if department_id is None or int(department_id) not in parent_map:
        return set()
    return expand_department_ids_with_descendants(parent_map, [int(department_id)])


def get_department_parent_map(db: Session) -> dict[int, int | None]:
    from backend.app.models.department import Department

    rows = db.query(Department.id, Department.parent_id).all()
    return {int(r[0]): (int(r[1]) if r[1] is not None else None) for r in rows}


def get_all_department_ids(db: Session) -> Set[int]:
    return set(get_department_parent_map(db).keys())


def get_direct_supervised_department_ids(db: Session, user_id: int) -> Set[int]:
    from backend.app.models.user_supervised_department import UserSupervisedDepartment

    rows = (
        db.query(UserSupervisedDepartment.department_id)
        .filter(UserSupervisedDepartment.user_id == user_id)
        .all()
    )
    return {int(r[0]) for r in rows}


def get_expanded_supervised_department_ids(db: Session, user_id: int) -> Set[int]:
    direct = get_direct_supervised_department_ids(db, user_id)
    if not direct:
        return set()
    parent_map = get_department_parent_map(db)
    return expand_department_ids_with_descendants(parent_map, direct)


def compute_accessible_department_ids_for_user(db: Session, user: User) -> Set[int]:
    """
    用户可进入并浏览部门文件库的部门 ID 集合（不含跨库共享补充，由调用方合并）。

    - 超级管理员：全部
    - 高管：全部
    - 分管领导：分管部门（含子部门）；若绑定所属部门则并集其部门子树
    - 其他：所属部门及其子部门
    """
    parent_map = get_department_parent_map(db)
    all_ids = set(parent_map.keys())

    if user.is_superuser:
        return all_ids
    if is_executive(user):
        return all_ids
    if is_division_leader(user):
        accessible = get_expanded_supervised_department_ids(db, user.id)
        if user.department_id is not None:
            accessible |= expand_user_department_subtree(parent_map, user.department_id)
        return accessible

    if user.department_id is None:
        return set()
    return expand_user_department_subtree(parent_map, user.department_id)
