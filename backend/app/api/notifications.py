from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.core.audit import get_client_ip, log_audit
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
  resource_type: Optional[str] = None
  resource_id: Optional[int] = None
  extra_json: Optional[str] = None

  class Config:
    from_attributes = True


class UnreadCountRead(BaseModel):
  count: int


@router.get("/unread-count", response_model=UnreadCountRead)
def unread_notification_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
  """当前用户未读通知数量（用于铃铛角标轮询，比拉全量列表更轻）。"""
  count = (
      db.query(Notification)
      .filter(Notification.user_id == current_user.id, Notification.is_read.is_(False))
      .count()
  )
  return UnreadCountRead(count=count)


@router.get("", response_model=List[NotificationRead])
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
    resource_type: Optional[str] = None,
    resource_id: Optional[int] = None,
    extra_json: Optional[str] = None,
    commit: bool = True,
) -> Notification:
  """内部辅助函数：为指定用户创建一条通知。"""
  n = Notification(
      user_id=user_id,
      type=type,
      title=title,
      message=message,
      resource_type=resource_type,
      resource_id=resource_id,
      extra_json=extra_json,
  )
  db.add(n)
  if commit:
    db.commit()
    db.refresh(n)
  else:
    db.flush()
    db.refresh(n)
  return n


def is_notification_enabled(db: Session, setting_key: str) -> bool:
  row = db.query(NotificationSetting).filter(NotificationSetting.key == setting_key).first()
  if row is None:
    return True
  return bool(row.enabled)


def create_notification_if_enabled(
    db: Session,
    *,
    setting_key: str,
    user_id: int,
    type: str,
    title: str,
    message: str,
    resource_type: Optional[str] = None,
    resource_id: Optional[int] = None,
    extra_json: Optional[str] = None,
    commit: bool = True,
) -> Optional[Notification]:
  if not is_notification_enabled(db, setting_key):
    return None
  return create_notification(
      db,
      user_id=user_id,
      type=type,
      title=title,
      message=message,
      resource_type=resource_type,
      resource_id=resource_id,
      extra_json=extra_json,
      commit=commit,
  )


SYSTEM_CHANNEL = "system"


def _channels_to_list(ch: str | None) -> List[str]:
  if not ch:
    return []
  return [c.strip() for c in ch.split(",") if c.strip()]


def _normalize_channels_list(channels: List[str] | None) -> List[str]:
  """平台仅支持站内通知，过滤掉未实现的 email 等渠道。"""
  normalized = [c for c in (channels or []) if c and c != "email"]
  return [SYSTEM_CHANNEL] if SYSTEM_CHANNEL in normalized or not normalized else normalized


def _channels_from_list(channels: List[str]) -> str:
  normalized = _normalize_channels_list(channels)
  return ",".join(sorted(set(normalized))) if normalized else SYSTEM_CHANNEL


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


_DEFAULT_TEMPLATES = [
  {
    "name": "文件分享通知",
    "type": "file_share",
    "title": "您收到了新的共享文件",
    "content": "{user} 向您分享了文件 {filename}",
    "enabled": True,
    "channels": "system",
    "icon": "file",
  },
  {
    "name": "文件上传通知",
    "type": "file_upload",
    "title": "文件库有新文件",
    "content": "{user} 在文件库 {library} 中上传了 {filename}",
    "enabled": True,
    "channels": "system",
    "icon": "file",
  },
  {
    "name": "评论与回复",
    "type": "comment",
    "title": "文件有新评论",
    "content": "{user} 在「{filename}」中发表了评论",
    "enabled": True,
    "channels": "system",
    "icon": "file-text",
  },
  {
    "name": "@提及通知",
    "type": "mention",
    "title": "有人在文件中提及了你",
    "content": "{user} 在「{filename}」中提及了你",
    "enabled": True,
    "channels": "system",
    "icon": "file-text",
  },
  {
    "name": "系统公告",
    "type": "maintenance",
    "title": "系统公告",
    "content": "管理员发布了新的系统通知",
    "enabled": True,
    "channels": "system",
    "icon": "settings",
  },
]


def _icon_for_type(t: str) -> str:
  if t in ("file_share", "file_upload"):
    return "file"
  if t in ("comment", "mention"):
    return "file-text"
  if t == "maintenance":
    return "settings"
  return "bell"


_DEFAULT_SETTINGS = [
  ("file_upload", "文件操作", "新文件/新版本上传", True),
  ("file_share", "文件操作", "文件被分享给我", True),
  ("comment", "协作", "文件评论与回复", True),
  ("mention", "协作", "@提及我", True),
  ("maintenance", "系统", "管理员公告", True),
]


def _ensure_default_templates(db: Session) -> None:
  if db.query(NotificationTemplate).count() == 0:
    for t in _DEFAULT_TEMPLATES:
      db.add(NotificationTemplate(**t))
    db.commit()
  _strip_email_channels_from_templates(db)


def _strip_email_channels_from_templates(db: Session) -> None:
  """历史数据可能含 email 渠道，统一归一为站内通知。"""
  changed = False
  for row in db.query(NotificationTemplate).all():
    normalized = _channels_from_list(_channels_to_list(row.channels))
    if row.channels != normalized:
      row.channels = normalized
      changed = True
  if changed:
    db.commit()


def _ensure_default_settings(db: Session) -> None:
  existing = {s.key: s for s in db.query(NotificationSetting).all()}
  changed = False
  for key, category, name, enabled in _DEFAULT_SETTINGS:
    if key not in existing:
      db.add(
        NotificationSetting(
          key=key,
          category=category,
          name=name,
          enabled=enabled,
        )
      )
      changed = True
  if changed:
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
  _ensure_default_settings(db)
  rows = db.query(NotificationTemplate).order_by(NotificationTemplate.id.asc()).all()
  # 当前所有通知开关，用于动态计算模板是否启用
  settings = db.query(NotificationSetting).all()
  settings_enabled = {s.key: bool(s.enabled) for s in settings}
  result: List[TemplateRead] = []
  for r in rows:
    # 模板是否启用：优先看是否存在同名 key 的 NotificationSetting
    enabled_by_setting = settings_enabled.get(r.type)
    effective_enabled = enabled_by_setting if enabled_by_setting is not None else r.enabled
    result.append(
      TemplateRead(
        id=r.id,
        name=r.name,
        type=r.type,
        title=r.title,
        content=r.content,
        enabled=effective_enabled,
        channels=_normalize_channels_list(_channels_to_list(r.channels)),
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
        channels=_normalize_channels_list(_channels_to_list(r.channels)),
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
  request: Request,
  db: Session = Depends(get_db),
  current_user: User = Depends(get_current_user),
):
  """管理员：发送站内公告给活跃用户（仅站内通知，无邮件）。"""
  if not current_user.is_superuser:
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅管理员可发送通知")

  title = (body.title or "").strip()
  content = (body.content or "").strip()
  if not title or not content:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="标题和内容不能为空")

  users = db.query(User).filter(User.is_active.is_(True)).all()
  recipients = 0
  for u in users:
    if u.id == current_user.id:
      continue
    create_notification(
      db,
      user_id=u.id,
      type="maintenance",
      title=title,
      message=content,
      commit=False,
    )
    recipients += 1

  log = NotificationSendLog(
    title=title,
    content=content,
    target=body.target,
    target_value=None,
    channels=SYSTEM_CHANNEL,
    recipients=recipients,
    status="sent",
  )
  db.add(log)
  log_audit(
    db,
    current_user.id,
    current_user.username,
    "notification",
    "notification",
    None,
    f"recipients={recipients} target={body.target} title={title[:80]}",
    ip_address=get_client_ip(request),
  )
  db.commit()
  return None

