"""部门树 API：树形列表、增删改、部门库"""
from typing import Dict, List, Optional, Set

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload

from backend.app.api.deps import get_current_active_superuser, get_current_user
from backend.app.api.libraries import LibraryRead, _lib_to_read
from backend.app.db.session import get_db
from backend.app.models.department import Department
from backend.app.models.library import Library
from backend.app.models.user import User

router = APIRouter(prefix="/departments", tags=["departments"])


class DepartmentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    parent_id: Optional[int] = None
    sort_order: int = 0


class DepartmentUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    parent_id: Optional[int] = None
    sort_order: Optional[int] = None
    leader_user_id: Optional[int] = None


class DepartmentNode(BaseModel):
    id: int
    name: str
    parent_id: Optional[int]
    sort_order: int
    user_count: int = 0
    leader_name: Optional[str] = None
    leader_user_id: Optional[int] = None
    has_access: bool = True
    children: List["DepartmentNode"] = []

    class Config:
        from_attributes = True


# 允许递归模型
DepartmentNode.model_rebuild()


class DepartmentInfo(BaseModel):
    """部门详情：名称、路径、当前用户是否有访问权限、直属人数"""

    id: int
    name: str
    path: str
    has_access: bool
    user_count: int


class DepartmentFileRow(BaseModel):
    """部门文件行（当前为示例数据，后续可接入真实文件系统）。"""

    id: int
    name: str
    type: str
    modified: str
    size: str
    owner: str


class DepartmentMemberRow(BaseModel):
    """部门成员行：用于部门负责人下拉列表。"""

    id: int
    username: Optional[str] = None
    email: Optional[str] = None

    class Config:
        from_attributes = True



def _get_leader_name(dept: Department) -> Optional[str]:
    """
    部门负责人显示名称。

    优先使用 leader_user_id 指向的用户（Department.leader 关系）；
    若未设置负责人，则退化为取该部门第一个用户的用户名/邮箱。
    """
    leader = getattr(dept, "leader", None)
    if leader:
        return getattr(leader, "username", None) or getattr(leader, "email", None)
    users = getattr(dept, "users", []) or []
    if users:
        u = users[0]
        return getattr(u, "username", None) or getattr(u, "email", None)
    return None


def _build_tree(
    nodes: List[Department],
    parent_id: Optional[int],
    user_counts: Dict[int, int],
    accessible_ids: Optional[Set[int]],
) -> List[DepartmentNode]:
    """将扁平列表组装为树"""
    result = []
    for d in sorted([n for n in nodes if n.parent_id == parent_id], key=lambda x: (x.sort_order, x.id)):
        dept_id = d.id
        result.append(
            DepartmentNode(
                id=dept_id,
                name=d.name,
                parent_id=d.parent_id,
                sort_order=d.sort_order,
                user_count=user_counts.get(dept_id, 0),
                leader_name=_get_leader_name(d),
                leader_user_id=getattr(d, "leader_user_id", None),
                has_access=True if accessible_ids is None else dept_id in accessible_ids,
                children=_build_tree(nodes, dept_id, user_counts, accessible_ids),
            )
        )
    return result


def _compute_user_counts(departments: List[Department]) -> Dict[int, int]:
    """统计每个部门直属用户数量。"""
    counts: Dict[int, int] = {}
    for d in departments:
        # relationship Department.users 由 User.department_id 建立
        counts[d.id] = len(getattr(d, "users", []) or [])
    return counts


def _compute_accessible_department_ids(
    departments: List[Department],
    current_user: User,
) -> Set[int]:
    """
    计算当前用户可访问的部门 ID 列表。

    规则（简单版本）：
    - 超级管理员：可访问所有部门
    - 其他用户：仅可访问自己的部门及其所有子部门
    """
    all_ids: Set[int] = {d.id for d in departments}
    # 超级管理员：可访问所有部门
    if current_user.is_superuser:
        return all_ids
    # 普通用户未绑定部门：不再回退为全部部门，视为无部门权限
    if current_user.department_id is None:
        return set()

    # 构建 parent -> children 映射
    children_map: Dict[Optional[int], List[int]] = {}
    for d in departments:
        children_map.setdefault(d.parent_id, []).append(d.id)

    start_id = current_user.department_id
    if start_id not in all_ids:
        # 用户没有绑定有效部门：视为无部门权限
        return set()

    accessible: Set[int] = set()
    stack = [start_id]
    while stack:
        did = stack.pop()
        if did in accessible:
            continue
        accessible.add(did)
        for child_id in children_map.get(did, []):
            stack.append(child_id)
    return accessible


@router.get("/tree", response_model=List[DepartmentNode])
def get_department_tree(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取部门树（所有用户可读），包含人员数量与访问权限标记。"""
    all_depts: List[Department] = (
        db.query(Department)
        .options(
            joinedload(Department.children),
            joinedload(Department.users),
            joinedload(Department.leader),
        )
        .order_by(Department.sort_order, Department.id)
        .all()
    )
    user_counts = _compute_user_counts(all_depts)
    accessible_ids = _compute_accessible_department_ids(all_depts, current_user)
    return _build_tree(all_depts, parent_id=None, user_counts=user_counts, accessible_ids=accessible_ids)


@router.post("/", response_model=DepartmentNode)
def create_department(
    body: DepartmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
):
    """创建部门（仅管理员）"""
    if body.parent_id is not None:
        parent = db.query(Department).filter(Department.id == body.parent_id).first()
        if not parent:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="父部门不存在")
    dept = Department(
        name=body.name.strip(),
        parent_id=body.parent_id,
        sort_order=body.sort_order,
    )
    db.add(dept)
    db.commit()
    db.refresh(dept)
    return DepartmentNode(
        id=dept.id,
        name=dept.name,
        parent_id=dept.parent_id,
        sort_order=dept.sort_order,
        children=[],
    )


@router.patch("/{department_id}", response_model=DepartmentNode)
def update_department(
    department_id: int,
    body: DepartmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
):
    """更新部门（仅管理员）"""
    dept = db.query(Department).filter(Department.id == department_id).first()
    if not dept:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="部门不存在")
    if body.name is not None:
        dept.name = body.name.strip()
    if body.parent_id is not None:
        if body.parent_id == dept.id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能将父部门设为自己")
        if body.parent_id == 0:
            dept.parent_id = None
        else:
            parent = db.query(Department).filter(Department.id == body.parent_id).first()
            if not parent:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="父部门不存在")
            dept.parent_id = body.parent_id
    if body.sort_order is not None:
        dept.sort_order = body.sort_order
    if body.leader_user_id is not None:
        # 允许通过传入 0 来清空负责人
        if body.leader_user_id == 0:
            dept.leader_user_id = None
        else:
            leader = (
                db.query(User)
                .filter(User.id == body.leader_user_id, User.department_id == dept.id)
                .first()
            )
            if not leader:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="负责人必须是该部门的成员",
                )
            dept.leader_user_id = leader.id
    db.commit()
    db.refresh(dept)
    all_depts: List[Department] = (
        db.query(Department)
        .options(
            joinedload(Department.users),
            joinedload(Department.leader),
        )
        .order_by(Department.sort_order, Department.id)
        .all()
    )
    user_counts = _compute_user_counts(all_depts)
    accessible_ids = _compute_accessible_department_ids(all_depts, current_user)
    children = _build_tree(all_depts, dept.id, user_counts, accessible_ids)
    return DepartmentNode(
        id=dept.id,
        name=dept.name,
        parent_id=dept.parent_id,
        sort_order=dept.sort_order,
        user_count=user_counts.get(dept.id, 0),
        leader_name=_get_leader_name(dept),
        leader_user_id=getattr(dept, "leader_user_id", None),
        has_access=dept.id in accessible_ids,
        children=children,
    )


@router.delete("/{department_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_department(
    department_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
):
    """删除部门（仅管理员）；若有子部门会一并级联删除"""
    dept = db.query(Department).filter(Department.id == department_id).first()
    if not dept:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="部门不存在")
    db.delete(dept)
    db.commit()


def _build_department_path(dept: Department) -> str:
    """根据父子关系构造路径，例如 总经理办公室/行政部。"""
    parts: List[str] = []
    current: Optional[Department] = dept
    # 由于 parent 关系可能未预加载，这里使用简单的 id 递归
    seen: Set[int] = set()
    while current is not None and current.id not in seen:
        seen.add(current.id)
        parts.append(current.name)
        current = current.parent
    parts.reverse()
    return "/".join(parts)


@router.get("/{department_id}/info", response_model=DepartmentInfo)
def get_department_info(
    department_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """部门详情：用于企业云盘部门文件视图。"""
    dept: Department | None = (
        db.query(Department)
        .options(joinedload(Department.parent), joinedload(Department.users))
        .filter(Department.id == department_id)
        .first()
    )
    if not dept:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="部门不存在")

    # 复用与树接口一致的访问控制规则
    all_depts: List[Department] = db.query(Department).all()
    accessible_ids = _compute_accessible_department_ids(all_depts, current_user)

    return DepartmentInfo(
        id=dept.id,
        name=dept.name,
        path=_build_department_path(dept),
        has_access=dept.id in accessible_ids,
        user_count=len(getattr(dept, "users", []) or []),
    )


@router.get("/{department_id}/members", response_model=List[DepartmentMemberRow])
def list_department_members(
    department_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
):
    """部门成员列表（仅管理员可见），用于选择部门负责人。"""
    dept = db.query(Department).filter(Department.id == department_id).first()
    if not dept:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="部门不存在")
    users = (
        db.query(User)
        .filter(User.department_id == department_id, User.is_active.is_(True))
        .order_by(User.username.asc().nullslast(), User.email.asc().nullslast(), User.id.asc())
        .all()
    )
    return users


@router.get("/{department_id}/libraries", response_model=List[LibraryRead])
def list_department_libraries(
    department_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """列出该部门的资料库（真实数据，非示例）。"""
    dept = db.query(Department).filter(Department.id == department_id).first()
    if not dept:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="部门不存在")
    all_depts = db.query(Department).all()
    accessible_ids = _compute_accessible_department_ids(all_depts, current_user)
    if department_id not in accessible_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该部门")

    from backend.app.core.library_access import has_library_access

    libs = (
        db.query(Library)
        .filter(
            Library.department_id == department_id,
            Library.deleted_at.is_(None),
        )
        .order_by(Library.created_at.desc())
        .all()
    )
    result = []
    for lib in libs:
        _, is_write = has_library_access(db, lib.id, current_user)
        result.append(
            _lib_to_read(db, lib, current_user.id, is_owner=lib.owner_id == current_user.id, is_write=is_write)
        )
    return result


@router.get("/{department_id}/files", response_model=List[DepartmentFileRow])
def list_department_files(
    department_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    部门文件列表（已废弃，请使用 /departments/{id}/libraries 获取部门资料库）。
    为兼容保留，返回空列表。
    """
    dept = db.query(Department).filter(Department.id == department_id).first()
    if not dept:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="部门不存在")
    all_depts = db.query(Department).all()
    accessible_ids = _compute_accessible_department_ids(all_depts, current_user)
    if department_id not in accessible_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该部门文件")
    return []

