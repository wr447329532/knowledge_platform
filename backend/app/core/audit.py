"""审计日志：记录谁在何时对何资源执行了何种操作"""

from typing import Optional

from sqlalchemy.orm import Session

from backend.app.models.audit import AuditLog


def log_audit(
    db: Session,
    user_id: Optional[int],
    username: Optional[str],
    action: str,
    resource_type: Optional[str] = None,
    resource_id: Optional[int] = None,
    detail: Optional[str] = None,
) -> None:
    """写入一条审计日志（调用方在业务提交后 commit）"""
    entry = AuditLog(
        user_id=user_id,
        username=username or None,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        detail=detail,
    )
    db.add(entry)
