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
    ip_address: Optional[str] = None,
) -> None:
    """写入一条审计日志（调用方在业务提交后 commit）"""
    entry = AuditLog(
        user_id=user_id,
        username=username or None,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        detail=detail,
        ip_address=ip_address,
    )
    db.add(entry)


def get_client_ip(request) -> Optional[str]:
    """
    从请求中提取客户端 IP 地址。

    优先级：
    1. X-Forwarded-For（取逗号分隔列表中的第一个）
    2. X-Real-IP
    3. request.client.host
    """
    if request is None:
        return None

    # 可能由反向代理设置
    xff = request.headers.get("X-Forwarded-For") or request.headers.get("x-forwarded-for")
    if xff:
        # 取第一个 IP
        first = xff.split(",")[0].strip()
        if first:
            return first

    x_real_ip = request.headers.get("X-Real-IP") or request.headers.get("x-real-ip")
    if x_real_ip:
        return x_real_ip.strip() or None

    client = getattr(request, "client", None)
    host = getattr(client, "host", None) if client else None
    return host
