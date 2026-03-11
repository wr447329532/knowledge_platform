from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.db.session import get_db
from backend.app.models.notification import (
    Notification,
    NotificationSendLog,
    NotificationSetting,
    NotificationTemplate,
)
from backend.app.models.user import User


router = APIRouter(prefix="/notifications", tags=["notifications"])


class NotificationRead(BaseModel):
  id: int
  type: str
  title: str
  message: str
  created_at: datetime
  is_read: bool

  class Config:
    from_attributes = True


@router.get("/", response_model=List[NotificationRead])
def list_notifications(
    unread_only: bool = Query(False, description="仅返回未读通知"),
    limit: int = Query(50, ge=1, le=200, description="最多返回条数"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
  """列出当前用户的通知（默认按时间倒序，最多 50 条）。"""
  q = (
      db.query(Notification)
      .filter(Notification.user_id == current_user.id)
      .order_by(Notification.created_at.desc())
  )
  if unread_only:
    q = q.filter(Notification.is_read.is_(False))
  rows = q.limit(limit).all()
  return rows


@router.post("/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
  """标记单条通知为已读。"""
  n: Optional[Notification] = (
      db.query(Notification)
      .filter(Notification.id == notification_id, Notification.user_id == current_user.id)
      .first()
  )
  if not n:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="通知不存在")
  if not n.is_read:
    n.is_read = True
    db.commit()


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
def mark_all_notifications_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
  """将当前用户的所有通知标记为已读。"""
  db.query(Notification).filter(
      Notification.user_id == current_user.id, Notification.is_read.is_(False)
  ).update({Notification.is_read: True}, synchronize_session=False)
  db.commit()


def create_notification(
    db: Session,
    *,
    user_id: int,
    type: str = "info",
    title: str,
    message: str,
) -> Notification:
  """内部辅助函数：为指定用户创建一条通知。"""
  n = Notification(
      user_id=user_id,
      type=type,
      title=title,
      message=message,
  )
  db.add(n)
  db.commit()
  db.refresh(n)
  return n


def _channels_to_list(ch: str | None) -> List[str]:
  if not ch:
    return []
  return [c for c in ch.split(",") if c]


def _channels_from_list(channels: List[str]) -> str:
  return ",".join(sorted(set(channels))) if channels else ""


class TemplateRead(BaseModel):
  id: int
  name: str
  type: str
  title: str
  content: str
  enabled: bool
  channels: List[str]
  icon: Optional[str] = None

  class Config:
    from_attributes = True


class HistoryRead(BaseModel):
  id: int
  title: str
  content: str
  recipients: int
  sentTime: datetime = Field(alias="sent_at")
  status: str
  channels: List[str]

  class Config:
    from_attributes = True
    populate_by_name = True


class SettingRead(BaseModel):
  id: int
  key: str
  category: str
  name: str
  enabled: bool

  class Config:
    from_attributes = True


class SettingUpdate(BaseModel):
  enabled: bool


class AdminSendRequest(BaseModel):
  title: str
  content: str
  target: str = Field("all", description="all | department | custom")
  channels: List[str] = Field(default_factory=lambda: ["system"])


_DEFAULT_TEMPLATES = [
  {
    "name": "文件分享通知",
    "type": "file_share",
    "title": "您收到了新的共享文件",
    "content": "{user} 向您分享了文件 {filename}",
    "enabled": True,
    "channels": "system,email",
    "icon": "file",
  },
  {
    "name": "存储空间警告",
    "type": "storage_warning",
    "title": "存储空间不足提醒",
    "content": "您的存储空间已使用 {percentage}%，建议及时清理",
    "enabled": True,
    "channels": "system,email",
    "icon": "database",
  },
  {
    "name": "权限变更通知",
    "type": "permission_change",
    "title": "权限已更新",
    "content": "管理员已修改您的权限设置",
    "enabled": True,
    "channels": "system",
    "icon": "lock",
  },
  {
    "name": "文件审批提醒",
    "type": "file_approval",
    "title": "待审批文件提醒",
    "content": "您有 {count} 个文件等待审批",
    "enabled": False,
    "channels": "system,email",
    "icon": "check-circle",
  },
  {
    "name": "系统维护通知",
    "type": "system_maintenance",
    "title": "系统维护公告",
    "content": "系统将于 {time} 进行维护，预计持续 {duration}",
    "enabled": True,
    "channels": "system,email",
    "icon": "settings",
  },
]


def _icon_for_type(t: str) -> str:
  if t == "file_share":
    return "file"
  if t == "storage_warning":
    return "database"
  if t == "permission_change":
    return "lock"
  if t == "file_approval":
    return "check-circle"
  if t == "system_maintenance":
    return "settings"
  return "bell"


_DEFAULT_SETTINGS = [
  # 文件操作
  ("file_upload", "文件操作", "文件上传通知", True),
  ("file_share", "文件操作", "文件分享通知", True),
  ("file_download", "文件操作", "文件下载通知", False),
  ("file_delete", "文件操作", "文件删除通知", True),
  # 系统通知
  ("storage_warning", "系统通知", "存储空间警告", True),
  ("login_alert", "系统通知", "异地登录提醒", True),
  ("system_update", "系统通知", "系统更新通知", True),
  ("maintenance", "系统通知", "维护公告", True),
  # 协作通知
  ("comment", "协作通知", "评论通知", True),
  ("mention", "协作通知", "@提及通知", True),
  ("approval", "协作通知", "审批通知", True),
  ("task", "协作通知", "任务分配通知", False),
]


def _ensure_default_templates(db: Session) -> None:
  if db.query(NotificationTemplate).count() > 0:
    return
  for t in _DEFAULT_TEMPLATES:
    db.add(NotificationTemplate(**t))
  db.commit()


def _ensure_default_settings(db: Session) -> None:
  if db.query(NotificationSetting).count() > 0:
    return
  for key, category, name, enabled in _DEFAULT_SETTINGS:
    db.add(
      NotificationSetting(
        key=key,
        category=category,
        name=name,
        enabled=enabled,
      )
    )
  db.commit()


@router.get("/admin/templates", response_model=List[TemplateRead])
def list_templates_admin(
  db: Session = Depends(get_db),
  current_user: User = Depends(get_current_user),
):
  """管理员：通知模板列表。首次访问会初始化默认模板。"""
  if not current_user.is_superuser:
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅管理员可访问")
  _ensure_default_templates(db)
  rows = db.query(NotificationTemplate).order_by(NotificationTemplate.id.asc()).all()
  result: List[TemplateRead] = []
  for r in rows:
    result.append(
      TemplateRead(
        id=r.id,
        name=r.name,
        type=r.type,
        title=r.title,
        content=r.content,
        enabled=r.enabled,
        channels=_channels_to_list(r.channels),
        icon=_icon_for_type(r.type),
      )
    )
  return result


@router.get("/admin/history", response_model=List[HistoryRead])
def list_history_admin(
  limit: int = Query(50, ge=1, le=200),
  db: Session = Depends(get_db),
  current_user: User = Depends(get_current_user),
):
  """管理员：通知发送历史。"""
  if not current_user.is_superuser:
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅管理员可访问")
  rows = (
    db.query(NotificationSendLog)
    .order_by(NotificationSendLog.sent_at.desc())
    .limit(limit)
    .all()
  )
  out: List[HistoryRead] = []
  for r in rows:
    out.append(
      HistoryRead(
        id=r.id,
        title=r.title,
        content=r.content,
        recipients=r.recipients,
        sent_at=r.sent_at,
        status=r.status,
        channels=_channels_to_list(r.channels),
      )
    )
  return out


@router.get("/admin/settings", response_model=List[SettingRead])
def list_settings_admin(
  db: Session = Depends(get_db),
  current_user: User = Depends(get_current_user),
):
  """管理员：通知开关设置（当前为全局开关）。"""
  if not current_user.is_superuser:
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅管理员可访问")
  _ensure_default_settings(db)
  rows = db.query(NotificationSetting).order_by(NotificationSetting.id.asc()).all()
  return rows


@router.patch("/admin/settings/{setting_id}", response_model=SettingRead)
def update_setting_admin(
  setting_id: int,
  payload: SettingUpdate,
  db: Session = Depends(get_db),
  current_user: User = Depends(get_current_user),
):
  """管理员：更新某个通知开关。"""
  if not current_user.is_superuser:
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅管理员可访问")
  s: Optional[NotificationSetting] = (
    db.query(NotificationSetting).filter(NotificationSetting.id == setting_id).first()
  )
  if not s:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="设置不存在")
  s.enabled = payload.enabled
  db.commit()
  db.refresh(s)
  return s


@router.post("/admin/send", status_code=status.HTTP_204_NO_CONTENT)
def send_admin_notification(
  body: AdminSendRequest,
  db: Session = Depends(get_db),
  current_user: User = Depends(get_current_user),
):
  """管理员：从「通知管理」页面发送一条自定义通知给用户。

  当前实现：
  - target = all：发送给所有活跃用户
  - target = department/custom：暂时等同于 all，后续可扩展为精确选择
  """
  if not current_user.is_superuser:
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅管理员可发送通知")

  # 目前按活跃用户统计
  users = db.query(User).filter(User.is_active.is_(True)).all()
  recipients = 0
  for u in users:
    create_notification(
      db,
      user_id=u.id,
      type="info",
      title=body.title,
      message=body.content,
    )
    recipients += 1

  log = NotificationSendLog(
    title=body.title,
    content=body.content,
    target=body.target,
    target_value=None,
    channels=_channels_from_list(body.channels),
    recipients=recipients,
    status="sent",
  )
  db.add(log)
  db.commit()
  return None

