"""审计日志查询接口（可限制仅管理员可见）"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_active_superuser
from backend.app.db.session import get_db
from backend.app.models.audit import AuditLog
from backend.app.models.user import User
from backend.app.models.department import Department


class AuditLogRead(BaseModel):
    id: int
    user_id: Optional[int]
    username: Optional[str]
    action: str
    resource_type: Optional[str]
    resource_id: Optional[int]
    detail: Optional[str]
    ip_address: Optional[str] = None
    created_at: datetime
    department_name: Optional[str] = None

    class Config:
        from_attributes = True


router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/logs", response_model=List[AuditLogRead])
def list_audit_logs(
    action: Optional[str] = Query(None, description="按操作类型筛选"),
    username: Optional[str] = Query(None, description="按用户名筛选"),
    resource_type: Optional[str] = Query(None, description="按资源类型筛选"),
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
):
    """查询审计日志（仅管理员可查）"""
    # 联合用户和部门信息，便于前端展示
    q = (
        db.query(AuditLog, User.username, Department.name.label("department_name"))
        .outerjoin(User, AuditLog.user_id == User.id)
        .outerjoin(Department, User.department_id == Department.id)
    )
    if action:
        q = q.filter(AuditLog.action.ilike(f"%{action.strip()}%"))
    if username:
        q = q.filter(User.username.ilike(f"%{username}%") | AuditLog.username.ilike(f"%{username}%"))
    if resource_type:
        q = q.filter(AuditLog.resource_type == resource_type)
    if start_date:
        try:
            from datetime import datetime as dt
            start = dt.strptime(start_date, "%Y-%m-%d")
            q = q.filter(AuditLog.created_at >= start)
        except ValueError:
            pass
    if end_date:
        try:
            from datetime import datetime as dt, timedelta
            end = dt.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
            q = q.filter(AuditLog.created_at < end)
        except ValueError:
            pass
    rows = q.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()
    result: list[AuditLogRead] = []
    for log, username_db, dept_name in rows:
        # username 优先使用 AuditLog 冗余的字段，其次使用用户当前用户名
        username_val = log.username or username_db
        result.append(
            AuditLogRead(
                id=log.id,
                user_id=log.user_id,
                username=username_val,
                action=log.action,
                resource_type=log.resource_type,
                resource_id=log.resource_id,
                detail=log.detail,
                ip_address=getattr(log, "ip_address", None),
                created_at=log.created_at,
                department_name=dept_name,
            )
        )
    return result
