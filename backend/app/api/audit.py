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


class AuditLogRead(BaseModel):
    id: int
    user_id: Optional[int]
    username: Optional[str]
    action: str
    resource_type: Optional[str]
    resource_id: Optional[int]
    detail: Optional[str]
    created_at: datetime

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
    q = db.query(AuditLog)
    if action:
        q = q.filter(AuditLog.action.ilike(f"%{action.strip()}%"))
    if username:
        q = q.filter(AuditLog.username.ilike(f"%{username}%"))
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
    logs = q.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()
    return logs
