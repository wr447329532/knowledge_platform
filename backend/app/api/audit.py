"""审计日志查询接口（可限制仅管理员可见）"""

from datetime import datetime, timedelta
from typing import Any, Callable, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_active_superuser, get_current_user
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


class AuditLogStatsRead(BaseModel):
    total: int
    distinct_user_count: int
    file_resource_count: int
    library_resource_count: int


router = APIRouter(prefix="/audit", tags=["audit"])


def _audit_logs_base_query(db: Session):
    return (
        db.query(AuditLog, User.username, Department.name.label("department_name"))
        .outerjoin(User, AuditLog.user_id == User.id)
        .outerjoin(Department, User.department_id == Department.id)
    )


def _parse_dates(
    start_date: Optional[str], end_date: Optional[str]
) -> tuple[Optional[datetime], Optional[datetime]]:
    start_dt: Optional[datetime] = None
    end_dt: Optional[datetime] = None
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        except ValueError:
            pass
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        except ValueError:
            pass
    return start_dt, end_dt


def _apply_audit_filters(
    query,
    *,
    action: Optional[str] = None,
    username: Optional[str] = None,
    resource_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    search: Optional[str] = None,
):
    if action:
        query = query.filter(AuditLog.action.ilike(f"%{action.strip()}%"))
    if username:
        query = query.filter(
            User.username.ilike(f"%{username}%") | AuditLog.username.ilike(f"%{username}%")
        )
    if resource_type:
        query = query.filter(AuditLog.resource_type == resource_type)
    start_dt, end_dt = _parse_dates(start_date, end_date)
    if start_dt is not None:
        query = query.filter(AuditLog.created_at >= start_dt)
    if end_dt is not None:
        query = query.filter(AuditLog.created_at < end_dt)
    if search and search.strip():
        sk = f"%{search.strip()}%"
        query = query.filter(
            or_(
                User.username.ilike(sk),
                AuditLog.username.ilike(sk),
                AuditLog.action.ilike(sk),
                AuditLog.detail.ilike(sk),
            )
        )
    return query


def _filtered_audit_rows_query(
    db: Session,
    *,
    action: Optional[str] = None,
    username: Optional[str] = None,
    resource_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    search: Optional[str] = None,
    extra_filter: Optional[Callable] = None,
):
    q = _apply_audit_filters(
        _audit_logs_base_query(db),
        action=action,
        username=username,
        resource_type=resource_type,
        start_date=start_date,
        end_date=end_date,
        search=search,
    )
    if extra_filter:
        q = extra_filter(q)
    return q


def _audit_stats_for_query(db: Session, base_query_builder: Callable[[], Any]) -> AuditLogStatsRead:
    total = base_query_builder().count()
    distinct_user_count = (
        base_query_builder().with_entities(func.count(func.distinct(AuditLog.user_id))).scalar()
    )
    file_resource_count = base_query_builder().filter(AuditLog.resource_type == "file").count()
    library_resource_count = (
        base_query_builder().filter(AuditLog.resource_type == "library").count()
    )
    return AuditLogStatsRead(
        total=total or 0,
        distinct_user_count=int(distinct_user_count or 0),
        file_resource_count=file_resource_count or 0,
        library_resource_count=library_resource_count or 0,
    )


@router.get("/logs", response_model=List[AuditLogRead])
def list_audit_logs(
    action: Optional[str] = Query(None, description="按操作类型筛选"),
    username: Optional[str] = Query(None, description="按用户名筛选"),
    resource_type: Optional[str] = Query(None, description="按资源类型筛选"),
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    search: Optional[str] = Query(None, description="关键词：匹配用户、操作、详情"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
):
    """查询审计日志（仅管理员可查）"""
    q = _filtered_audit_rows_query(
        db,
        action=action,
        username=username,
        resource_type=resource_type,
        start_date=start_date,
        end_date=end_date,
        search=search,
    )
    rows = q.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()
    result: list[AuditLogRead] = []
    for log, username_db, dept_name in rows:
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


@router.get("/logs/stats", response_model=AuditLogStatsRead)
def audit_logs_stats(
    action: Optional[str] = Query(None),
    username: Optional[str] = Query(None),
    resource_type: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
):
    """与列表接口相同的筛选条件下的汇总统计"""

    def _builder():
        return _filtered_audit_rows_query(
            db,
            action=action,
            username=username,
            resource_type=resource_type,
            start_date=start_date,
            end_date=end_date,
            search=search,
        )

    return _audit_stats_for_query(db, _builder)


@router.get("/dept-logs", response_model=List[AuditLogRead])
def list_department_audit_logs(
    action: Optional[str] = Query(None, description="按操作类型筛选"),
    username: Optional[str] = Query(None, description="按用户名筛选"),
    resource_type: Optional[str] = Query(None, description="按资源类型筛选"),
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    search: Optional[str] = Query(None, description="关键词：匹配用户、操作、详情"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    部门系统日志：仅返回某个部门内用户产生的操作记录。
    部门范围判定规则：
    - 若当前用户有 department_id，则以该部门为准；
    - 否则，若其为某部门负责人（Department.leader_user_id），则以该部门为准；
    - 否则返回 403。
    """
    dept_id = current_user.department_id
    if dept_id is None:
        lead_dept = (
            db.query(Department).filter(Department.leader_user_id == current_user.id).first()
        )
        if not lead_dept:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="当前账号未绑定部门，无法查看部门日志",
            )
        dept_id = lead_dept.id

    user_ids = [u.id for u in db.query(User.id).filter(User.department_id == dept_id).all()]
    if not user_ids:
        return []

    def _dept_scope(q):
        return q.filter(AuditLog.user_id.in_(user_ids))

    q = _filtered_audit_rows_query(
        db,
        action=action,
        username=username,
        resource_type=resource_type,
        start_date=start_date,
        end_date=end_date,
        search=search,
        extra_filter=_dept_scope,
    )
    rows = q.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()
    result: list[AuditLogRead] = []
    for log, username_db, dept_name in rows:
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


@router.get("/dept-logs/stats", response_model=AuditLogStatsRead)
def department_audit_logs_stats(
    action: Optional[str] = Query(None),
    username: Optional[str] = Query(None),
    resource_type: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dept_id = current_user.department_id
    if dept_id is None:
        lead_dept = (
            db.query(Department).filter(Department.leader_user_id == current_user.id).first()
        )
        if not lead_dept:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="当前账号未绑定部门，无法查看部门日志",
            )
        dept_id = lead_dept.id

    user_ids = [u.id for u in db.query(User.id).filter(User.department_id == dept_id).all()]
    if not user_ids:
        return AuditLogStatsRead(
            total=0, distinct_user_count=0, file_resource_count=0, library_resource_count=0
        )

    def _dept_scope(q):
        return q.filter(AuditLog.user_id.in_(user_ids))

    def _builder():
        return _filtered_audit_rows_query(
            db,
            action=action,
            username=username,
            resource_type=resource_type,
            start_date=start_date,
            end_date=end_date,
            search=search,
            extra_filter=_dept_scope,
        )

    return _audit_stats_for_query(db, _builder)
