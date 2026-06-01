"""分管领导分管部门配置（管理员）。"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_active_superuser
from backend.app.core.oversight_access import is_division_leader
from backend.app.db.session import get_db
from backend.app.models.user import User
from backend.app.services.supervised_department_service import (
    list_supervised_department_ids,
    replace_supervised_departments,
)

router = APIRouter(prefix="/division-leader", tags=["division-leader"])


class SupervisedDepartmentsRead(BaseModel):
    user_id: int
    department_ids: List[int] = Field(default_factory=list)


class SupervisedDepartmentsUpdate(BaseModel):
    department_ids: List[int] = Field(default_factory=list, description="分管部门根节点 id 列表（含子部门由系统自动扩展）")


@router.get("/users/{user_id}/departments", response_model=SupervisedDepartmentsRead)
def get_user_supervised_departments(
    user_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_active_superuser),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    return SupervisedDepartmentsRead(
        user_id=user.id,
        department_ids=list_supervised_department_ids(db, user.id),
    )


@router.put("/users/{user_id}/departments", response_model=SupervisedDepartmentsRead)
def set_user_supervised_departments(
    user_id: int,
    body: SupervisedDepartmentsUpdate,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_active_superuser),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    if not is_division_leader(user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该用户不是分管领导，请先在用户权限中设置角色",
        )
    ids = replace_supervised_departments(db, user, body.department_ids)
    db.commit()
    return SupervisedDepartmentsRead(user_id=user.id, department_ids=ids)
