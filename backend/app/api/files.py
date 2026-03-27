from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Literal, Optional

from fastapi import APIRouter, Body, Depends, File, HTTPException, UploadFile, Query, Request, status, Path as FPath
from fastapi.responses import Response
from fastapi.responses import FileResponse
from jose import JWTError, jwt
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.core.audit import get_client_ip, log_audit
from backend.app.core.config import get_settings
from backend.app.core.library_access import (
    can_download_file,
    can_access_file,
    get_accessible_library_ids,
    has_library_access,
)
from backend.app.api.notifications import create_notification
from backend.app.db.session import get_db
from backend.app.models.department import Department
from backend.app.models.file import FileEntry, FileVersion, FileVersionTrash
from backend.app.models.file_share import FileShare
from backend.app.models.library import Library
from backend.app.models.user import User


settings = get_settings()
router = APIRouter(prefix="/files", tags=["files"])


class FileRead(BaseModel):
    id: int
    library_id: int
    path: str
    is_dir: bool
    size: Optional[int] = None  # 文件最新版本大小（字节），目录为 None
    updated_at: Optional[datetime] = None
    can_download: Optional[bool] = None  # 当前用户是否可下载（拥有者或被分享且权限为 download）

    class Config:
        from_attributes = True


class GlobalSearchFileRead(FileRead):
    library_name: Optional[str] = None


class FileTrashRead(FileRead):
    deleted_at: datetime
    library_name: Optional[str] = None
    username: Optional[str] = None  # 删除人（若无则回退为文件创建人/库拥有者）


class GlobalTrashItem(BaseModel):
    """全局回收站条目：既包含文件也包含文件库"""

    id: int
    type: Literal["file", "library", "file_version"]
    entry_id: Optional[int] = None
    version_no: Optional[int] = None
    library_id: Optional[int] = None
    library_name: Optional[str] = None
    username: Optional[str] = None  # 删除人（若无则回退为文件创建人/库拥有者）
    path: Optional[str] = None
    is_dir: Optional[bool] = None
    deleted_at: datetime
    can_restore: bool = True
    can_delete: bool = True


class FileVersionRead(BaseModel):
    id: int
    version_no: int
    size: int
    uploaded_at: datetime
    uploaded_by: Optional[str] = None

    class Config:
        from_attributes = True


class FileShareRead(BaseModel):
    id: int
    file_entry_id: int
    user_id: int
    username: str
    permission: str  # read | download
    created_at: str | None = None

    class Config:
        from_attributes = True


SharePermission = Literal["read", "download"]


class FileShareAdd(BaseModel):
    user_id: int = Field(..., description="被分享用户 ID")
    permission: SharePermission = Field("read", description="read=只读/预览，download=可下载")


class MyShareRow(BaseModel):
    """我发出的分享：文件路径、共享给谁（用户/部门）、权限"""
    id: int
    file_entry_id: int
    file_path: str
    library_id: int
    library_name: str
    user_id: int
    username: str
    department_name: Optional[str] = None
    permission: str  # read | download
    created_at: Optional[str] = None


class SharedToMeRow(BaseModel):
    """分享给我的：文件路径、所属库、分享者、权限"""
    id: int
    file_entry_id: int
    file_path: str
    library_id: int
    library_name: str
    owner_username: str
    permission: str  # read | download
    created_at: Optional[str] = None


def _ensure_storage_root() -> Path:
    root: Path = settings.STORAGE_ROOT
    root.mkdir(parents=True, exist_ok=True)
    return root


def _get_library_and_check(db: Session, library_id: int, user: User, require_write: bool = False) -> Library:
    """获取资料库并校验访问权限。require_write=True 时需读写权限。"""
    lib, _ = has_library_access(db, library_id, user, require_write=require_write)
    return lib


def _check_trash_permission(db: Session, library_id: int, user: User) -> Library:
    """
    回收站权限：仅允许库所有者（私人库）或部门负责人（部门库/公开库）操作。
    用于 list_trash / restore_file / permanent_delete，不替换其他接口的 _get_library_and_check。
    """
    lib = db.query(Library).filter(Library.id == library_id).first()
    if not lib or getattr(lib, "deleted_at", None) is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="资料库不存在")
    if user.is_superuser:
        return lib
    visibility = getattr(lib, "visibility", "private") or "private"
    if visibility in ("private", "members"):
        if lib.owner_id != user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="私人库回收站仅库所有者可操作")
    else:
        if not getattr(lib, "department_id", None):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无回收站操作权限")
        dept = db.query(Department).filter(Department.id == lib.department_id).first()
        if not dept or getattr(dept, "leader_user_id", None) != user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="部门库回收站仅部门负责人可操作")
    return lib


@router.get("/shares", response_model=List[FileShareRead])
def list_file_shares(
    entry_id: int = Query(..., description="文件条目 ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """列出某个文件当前的分享列表（仅拥有者可查看管理）。"""
    entry = (
        db.query(FileEntry)
        .filter(FileEntry.id == entry_id, FileEntry.deleted_at.is_(None))
        .first()
    )
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")
    lib = db.query(Library).filter(Library.id == entry.library_id).first()
    if not lib:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件库不存在")
    if lib.owner_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅文件库拥有者可管理分享")
    rows = (
        db.query(FileShare, User.username)
        .join(User, FileShare.user_id == User.id)
        .filter(FileShare.file_entry_id == entry_id)
        .order_by(FileShare.created_at.desc())
        .all()
    )
    result: list[FileShareRead] = []
    for fs, username in rows:
        result.append(
            FileShareRead(
                id=fs.id,
                file_entry_id=fs.file_entry_id,
                user_id=fs.user_id,
                username=username,
                permission=fs.permission,
                created_at=fs.created_at.isoformat() if getattr(fs, "created_at", None) else None,
            )
        )
    return result


@router.post("/shares", status_code=status.HTTP_204_NO_CONTENT)
def add_file_share(
    entry_id: int = Query(..., description="文件条目 ID"),
    body: FileShareAdd = Body(...),
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """新增或更新文件分享记录（仅拥有者可操作）。"""
    entry = (
        db.query(FileEntry)
        .filter(FileEntry.id == entry_id, FileEntry.deleted_at.is_(None))
        .first()
    )
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")
    lib = db.query(Library).filter(Library.id == entry.library_id).first()
    if not lib:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件库不存在")
    if lib.owner_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅文件库拥有者可管理分享")
    user = db.query(User).filter(User.id == body.user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在或已禁用")
    fs = (
        db.query(FileShare)
        .filter(FileShare.file_entry_id == entry_id, FileShare.user_id == body.user_id)
        .first()
    )
    now = datetime.now(timezone.utc)
    created = False
    if fs:
        fs.permission = body.permission
    else:
        fs = FileShare(
            file_entry_id=entry_id,
            user_id=body.user_id,
            permission=body.permission,
            created_at=now,
        )
        db.add(fs)
        created = True

    # 审计日志：记录文件分享/权限变更
    action = "file_share_add" if created else "file_share_update"
    log_audit(
        db,
        current_user.id,
        current_user.username,
        action,
        "file_share",
        entry.id,
        f"to_user_id={body.user_id} permission={body.permission} path={entry.path}",
        ip_address=get_client_ip(request),
    )

    # 通知：被分享用户收到「文件被分享给你」
    try:
        if user.id != current_user.id:
            title = "文件被分享给你"
            perm_label = "可下载" if body.permission == "download" else "仅预览"
            msg = (
                f"用户「{current_user.username or current_user.email}」向你分享了文件「{entry.path}」，"
                f"权限：{perm_label}"
            )
            create_notification(
                db,
                user_id=user.id,
                type="file_share_to_me",
                title=title,
                message=msg,
            )
    except Exception:
        # 通知失败不影响主流程
        pass

    db.commit()


@router.delete("/shares", status_code=status.HTTP_204_NO_CONTENT)
def remove_file_share(
    entry_id: int = Query(..., description="文件条目 ID"),
    user_id: int = Query(..., description="被分享用户 ID"),
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """移除文件分享记录（仅拥有者可操作）。"""
    entry = (
        db.query(FileEntry)
        .filter(FileEntry.id == entry_id, FileEntry.deleted_at.is_(None))
        .first()
    )
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")
    lib = db.query(Library).filter(Library.id == entry.library_id).first()
    if not lib:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件库不存在")
    if lib.owner_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅文件库拥有者可管理分享")
    fs = (
        db.query(FileShare)
        .filter(FileShare.file_entry_id == entry_id, FileShare.user_id == user_id)
        .first()
    )
    if not fs:
        return
    db.delete(fs)
    log_audit(
        db,
        current_user.id,
        current_user.username,
        "file_share_remove",
        "file_share",
        entry.id,
        f"to_user_id={user_id} path={entry.path}",
        ip_address=get_client_ip(request),
    )
    db.commit()


@router.get("/shares/mine", response_model=List[MyShareRow])
def list_my_shares(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """我分享出去的文件列表。"""
    rows = (
        db.query(
            FileShare,
            FileEntry.path,
            FileEntry.library_id,
            Library.name.label("library_name"),
            User.username,
            Department.name.label("department_name"),
        )
        .join(FileEntry, FileShare.file_entry_id == FileEntry.id)
        .join(Library, FileEntry.library_id == Library.id)
        .join(User, FileShare.user_id == User.id)
        .outerjoin(Department, User.department_id == Department.id)
        .filter(
            Library.owner_id == current_user.id,
            FileEntry.deleted_at.is_(None),
            Library.deleted_at.is_(None),
        )
        .order_by(FileShare.created_at.desc())
        .all()
    )
    result: list[MyShareRow] = []
    for fs, path, lib_id, lib_name, username, dept_name in rows:
        result.append(
            MyShareRow(
                id=fs.id,
                file_entry_id=fs.file_entry_id,
                file_path=path,
                library_id=lib_id,
                library_name=lib_name,
                user_id=fs.user_id,
                username=username,
                department_name=dept_name,
                permission=fs.permission,
                created_at=fs.created_at.isoformat() if getattr(fs, "created_at", None) else None,
            )
        )
    return result


@router.get("/shares/to-me", response_model=List[SharedToMeRow])
def list_shares_to_me(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """分享给我的文件列表。"""
    rows = (
        db.query(
            FileShare,
            FileEntry.path,
            FileEntry.library_id,
            Library.name.label("library_name"),
            User.username.label("owner_username"),
        )
        .join(FileEntry, FileShare.file_entry_id == FileEntry.id)
        .join(Library, FileEntry.library_id == Library.id)
        .join(User, Library.owner_id == User.id)
        .filter(
            FileShare.user_id == current_user.id,
            FileEntry.deleted_at.is_(None),
            Library.deleted_at.is_(None),
        )
        .order_by(FileShare.created_at.desc())
        .all()
    )
    result: list[SharedToMeRow] = []
    for fs, path, lib_id, lib_name, owner_username in rows:
        result.append(
            SharedToMeRow(
                id=fs.id,
                file_entry_id=fs.file_entry_id,
                file_path=path,
                library_id=lib_id,
                library_name=lib_name,
                owner_username=owner_username,
                permission=fs.permission,
                created_at=fs.created_at.isoformat() if getattr(fs, "created_at", None) else None,
            )
        )
    return result


@router.post("/upload", response_model=FileRead)
async def upload_file(
    library_id: int,
    relative_path: str,
    file: UploadFile = File(...),
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lib = _get_library_and_check(db, library_id, current_user, require_write=True)

    # 规范化相对路径，例如 docs/readme.md
    relative_path = relative_path.lstrip("/").replace("\\", "/")
    if not relative_path:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="路径不能为空")

    # 查找或创建 FileEntry
    # 说明：
    # - 若同路径文件尚未删除，则在原记录上追加新版本；
    # - 若同路径文件已在回收站中，则视为“新文件”，保留旧回收站记录，新建一条 FileEntry。
    entry: FileEntry | None = (
        db.query(FileEntry)
        .filter(FileEntry.library_id == library_id, FileEntry.path == relative_path)
        .first()
    )
    if entry and entry.deleted_at:
        # 已在回收站中的旧文件，不复用；保留旧记录，重新创建一条新的 FileEntry
        entry = None
    if not entry:
        entry = FileEntry(
            library_id=library_id,
            path=relative_path,
            is_dir=False,
            created_by_id=current_user.id,
        )
        db.add(entry)
        db.flush()  # 先拿到 entry.id

    # 计算下一个版本号
    last_version: FileVersion | None = (
        db.query(FileVersion)
        .filter(FileVersion.file_entry_id == entry.id)
        .order_by(FileVersion.version_no.desc())
        .first()
    )
    next_version_no = 1 if not last_version else last_version.version_no + 1

    # 磁盘存储路径: <STORAGE_ROOT>/<library_id>/<entry_id>/<version_no>/<filename>
    root = _ensure_storage_root()
    dest_dir = root / str(library_id) / str(entry.id) / str(next_version_no)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / file.filename

    # 单个文件大小限制（500MB）
    MAX_FILE_SIZE_BYTES = 500 * 1024 * 1024

    size = 0
    with open(dest_path, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_FILE_SIZE_BYTES:
                # 删除已写入的临时文件并中止上传
                f.close()
                try:
                    dest_path.unlink()
                except OSError:
                    pass
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="单个文件大小不能超过 500MB",
                )
            f.write(chunk)

    # 记录版本信息
    version = FileVersion(
        file_entry_id=entry.id,
        version_no=next_version_no,
        storage_path=str(dest_path),
        size=size,
        uploaded_by_id=current_user.id,
    )
    db.add(version)

    # 审计日志：上传或新版本
    action = "upload_new_version" if next_version_no > 1 else "upload"
    log_audit(
        db,
        current_user.id,
        current_user.username,
        action,
        "file",
        entry.id,
        f"library_id={library_id} path={relative_path} version={next_version_no}",
        ip_address=get_client_ip(request),
    )

    # 通知：库拥有者 / 上传者 知晓有新文件/新版本
    try:
        if next_version_no == 1:
            notif_type = "file_upload"
            title = "文件已上传"
            msg_for_owner = (
                f"用户「{current_user.username or current_user.email}」在文件库「{lib.name}」中上传了新文件："
                f"{relative_path}"
            )
            msg_for_self = f"你在文件库「{lib.name}」中上传了新文件：{relative_path}"
        else:
            notif_type = "file_new_version"
            title = "文件有新版本"
            msg_for_owner = (
                f"用户「{current_user.username or current_user.email}」在文件库「{lib.name}」中上传了文件「{relative_path}」"
                f"的新版本（第 {next_version_no} 个版本）"
            )
            msg_for_self = (
                f"你在文件库「{lib.name}」中上传了文件「{relative_path}」的新版本（第 {next_version_no} 个版本）"
            )

        # 1）发送给库拥有者（若存在且不是当前用户）
        if lib.owner_id and lib.owner_id != current_user.id:
            create_notification(
                db,
                user_id=lib.owner_id,
                type=notif_type,
                title=title,
                message=msg_for_owner,
            )

        # 2）发送给上传者本人（无论是否为库拥有者）
        create_notification(
            db,
            user_id=current_user.id,
            type=notif_type,
            title=title,
            message=msg_for_self,
        )
    except Exception:
        # 通知失败不影响主流程
        pass

    db.commit()
    db.refresh(entry)

    return entry


def _is_library_owner(db: Session, library_id: int, user: User) -> bool:
    lib = db.query(Library).filter(Library.id == library_id).first()
    return lib and lib.owner_id == user.id


@router.get("/list", response_model=List[FileRead])
def list_files(
    library_id: int,
    path_prefix: Optional[str] = Query(None, description="目录前缀，如 docs/ 只列出 docs/ 下的文件"),
    include_dirs: bool = Query(True, description="是否包含目录"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lib, is_owner = has_library_access(db, library_id, current_user)
    q = db.query(FileEntry).filter(
        FileEntry.library_id == library_id,
        FileEntry.deleted_at.is_(None),
    )
    if not include_dirs:
        q = q.filter(FileEntry.is_dir.is_(False))
    prefix = ""
    if path_prefix:
        prefix = path_prefix.strip("/").replace("\\", "/")
        if prefix and not prefix.endswith("/"):
            prefix += "/"
        if prefix:
            q = q.filter(FileEntry.path.startswith(prefix))
    entries = q.order_by(FileEntry.path.asc()).all()
    # 只返回直接子级：根目录时 path 无 "/"；子目录时 path 在 prefix 后无 "/"
    if prefix:
        entries = [e for e in entries if "/" not in e.path[len(prefix):]]
    else:
        entries = [e for e in entries if "/" not in e.path]
    # 统一采用库级访问控制：只要通过 has_library_access 校验（拥有者 / 库成员 / 部门库 / public），
    # 即可在列表中看到该资料库下的全部文件和目录，不再按文件级分享单独过滤。
    # 文件取最新版本大小；目录无 size
    file_entry_ids = [e.id for e in entries if not e.is_dir]
    latest_size: dict[int, int] = {}
    if file_entry_ids:
        from sqlalchemy import func

        subq = (
            db.query(FileVersion.file_entry_id, func.max(FileVersion.version_no).label("max_ver"))
            .filter(FileVersion.file_entry_id.in_(file_entry_ids))
            .group_by(FileVersion.file_entry_id)
            .subquery()
        )
        rows = (
            db.query(FileVersion.file_entry_id, FileVersion.size)
            .join(subq, (FileVersion.file_entry_id == subq.c.file_entry_id) & (FileVersion.version_no == subq.c.max_ver))
            .all()
        )
        latest_size = {r[0]: r[1] for r in rows}
    result = []
    for e in entries:
        can_dl = can_download_file(db, e, current_user) if not e.is_dir else None
        result.append(
            FileRead(
                id=e.id,
                library_id=e.library_id,
                path=e.path,
                is_dir=e.is_dir,
                size=latest_size.get(e.id) if not e.is_dir else None,
                updated_at=e.updated_at,
                can_download=can_dl,
            )
        )
    return result


@router.post("/mkdir", response_model=FileRead)
def create_directory(
    library_id: int,
    path: str,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建目录（如 docs/reports）"""
    lib = _get_library_and_check(db, library_id, current_user, require_write=True)
    path = path.strip("/").replace("\\", "/")
    if not path:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="路径不能为空")
    existing = (
        db.query(FileEntry)
        .filter(
            FileEntry.library_id == library_id,
            FileEntry.path == path,
            FileEntry.deleted_at.is_(None),
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该路径已存在")
    entry = FileEntry(
        library_id=library_id,
        path=path,
        is_dir=True,
        created_by_id=current_user.id,
    )
    db.add(entry)
    log_audit(
        db,
        current_user.id,
        current_user.username,
        "mkdir",
        "file",
        entry.id,
        f"library_id={library_id} path={path}",
        ip_address=get_client_ip(request),
    )
    db.commit()
    db.refresh(entry)
    return entry


@router.patch("/{entry_id}/rename", response_model=FileRead)
def rename_file(
    entry_id: int,
    new_path: str = Query(..., description="新路径，如 docs/readme.txt"),
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """重命名文件或目录（通过修改 path）"""
    entry: FileEntry | None = db.query(FileEntry).filter(FileEntry.id == entry_id).first()
    if not entry or entry.deleted_at:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件或目录不存在")
    _get_library_and_check(db, entry.library_id, current_user, require_write=True)

    new_path = new_path.strip("/").replace("\\", "/")
    if not new_path:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="路径不能为空")
    if new_path == entry.path:
        db.refresh(entry)
        return entry

    # 检查新路径是否已存在
    existing = (
        db.query(FileEntry)
        .filter(
            FileEntry.library_id == entry.library_id,
            FileEntry.path == new_path,
            FileEntry.deleted_at.is_(None),
            FileEntry.id != entry_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该路径已存在")

    old_path = entry.path
    if entry.is_dir:
        # 目录：需同时更新所有子项路径
        prefix = old_path.rstrip("/") + "/"
        new_prefix = new_path.rstrip("/") + "/"
        children = (
            db.query(FileEntry)
            .filter(
                FileEntry.library_id == entry.library_id,
                FileEntry.path.startswith(prefix),
                FileEntry.deleted_at.is_(None),
            )
            .all()
        )
        entry.path = new_path
        for c in children:
            c.path = new_prefix + c.path[len(prefix) :]
    else:
        entry.path = new_path

    log_audit(
        db,
        current_user.id,
        current_user.username,
        "rename",
        "file",
        entry.id,
        f"{old_path} -> {new_path}",
        ip_address=get_client_ip(request),
    )
    db.commit()
    db.refresh(entry)
    return entry


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_file(
    entry_id: int,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除文件或目录到回收站（目录会连同其下所有项一起进入回收站）"""
    from datetime import datetime as dt

    entry: FileEntry | None = db.query(FileEntry).filter(FileEntry.id == entry_id).first()
    if not entry or entry.deleted_at:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件或目录不存在")
    _get_library_and_check(db, entry.library_id, current_user, require_write=True)
    if entry.is_dir:
        # 仅统计未删除的子项
        children = db.query(FileEntry).filter(
            FileEntry.library_id == entry.library_id,
            FileEntry.path.startswith(entry.path.rstrip("/") + "/"),
            FileEntry.deleted_at.is_(None),
        ).count()
        if children > 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="目录非空，无法删除")
    now = dt.utcnow()
    entry.deleted_at = now
    if entry.is_dir:
        # 目录下所有未删除项一并进回收站
        db.query(FileEntry).filter(
            FileEntry.library_id == entry.library_id,
            FileEntry.path.startswith(entry.path.rstrip("/") + "/"),
            FileEntry.deleted_at.is_(None),
        ).update({FileEntry.deleted_at: now}, synchronize_session=False)
    log_audit(
        db,
        current_user.id,
        current_user.username,
        "delete",
        "file",
        entry.id,
        f"path={entry.path} -> recycle",
        ip_address=get_client_ip(request),
    )
    db.commit()


@router.get("/trash", response_model=List[FileTrashRead])
def list_trash(
    library_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """列出回收站中的文件/目录。"""
    lib = _check_trash_permission(db, library_id, current_user)

    entries = (
        db.query(FileEntry)
        .filter(
            FileEntry.library_id == library_id,
            FileEntry.deleted_at != None,  # noqa: E711
        )
        .order_by(FileEntry.deleted_at.desc())
        .all()
    )
    return entries


@router.get("/dept-trash", response_model=List[GlobalTrashItem])
def list_dept_trash(
    dept_id: int = Query(..., description="部门 ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """部门回收站：该部门下部门库的删除记录（已删文件库 + 已删文件）。仅部门负责人或超级管理员可访问。"""
    dept = db.query(Department).filter(Department.id == dept_id).first()
    if not dept:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="部门不存在")
    if not current_user.is_superuser and getattr(dept, "leader_user_id", None) != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅部门负责人可查看部门回收站")

    # 该部门下所有部门库（含已删除），用于同时汇总“已删文件库 + 已删文件”
    all_dept_libs = (
        db.query(Library)
        .filter(
            Library.department_id == dept_id,
            Library.visibility == "department",
        )
        .all()
    )
    deleted_libs = [lib for lib in all_dept_libs if getattr(lib, "deleted_at", None) is not None]
    active_libs = [lib for lib in all_dept_libs if getattr(lib, "deleted_at", None) is None]
    lib_ids = [lib.id for lib in active_libs]
    lib_names = {lib.id: getattr(lib, "name", "") or "" for lib in active_libs}

    # 预取库拥有者用于「删除人」回退
    owner_ids = {lib.owner_id for lib in all_dept_libs if getattr(lib, "owner_id", None)}
    owners = db.query(User).filter(User.id.in_(owner_ids)).all() if owner_ids else []
    owner_name_map: dict[int, str] = {}
    for u in owners:
        owner_name_map[u.id] = u.username or u.email or f"用户{u.id}"

    entries = (
        db.query(FileEntry)
        .filter(
            FileEntry.library_id.in_(lib_ids),
            FileEntry.deleted_at != None,  # noqa: E711
        )
        .order_by(FileEntry.deleted_at.desc())
        .all()
    )
    # 预取文件创建人
    creator_ids = {e.created_by_id for e in entries if getattr(e, "created_by_id", None)}
    creators = db.query(User).filter(User.id.in_(creator_ids)).all() if creator_ids else []
    creator_name_map: dict[int, str] = {}
    for u in creators:
        creator_name_map[u.id] = u.username or u.email or f"用户{u.id}"

    items: list[GlobalTrashItem] = []

    # 1) 已删除部门库
    for lib in deleted_libs:
        username: Optional[str] = None
        if getattr(lib, "owner_id", None):
            username = owner_name_map.get(lib.owner_id)
        items.append(
            GlobalTrashItem(
                id=lib.id,
                type="library",
                library_id=lib.id,
                library_name=getattr(lib, "name", "") or None,
                path=getattr(lib, "name", "") or None,
                is_dir=True,
                deleted_at=getattr(lib, "deleted_at"),
                username=username,
                can_restore=True,
                can_delete=True,
            )
        )

    # 2) 活跃部门库中的已删文件
    for e in entries:
        # 删除人优先：创建人，其次库拥有者
        username: Optional[str] = None
        if getattr(e, "created_by_id", None):
            username = creator_name_map.get(e.created_by_id)
        if not username:
            lib_owner_id = next((lib.owner_id for lib in active_libs if lib.id == e.library_id), None)
            if lib_owner_id:
                username = owner_name_map.get(lib_owner_id)

        items.append(
            GlobalTrashItem(
                id=e.id,
                type="file",
                library_id=e.library_id,
                library_name=lib_names.get(e.library_id) or None,
                path=e.path,
                is_dir=e.is_dir,
                deleted_at=e.deleted_at,
                username=username,
                can_restore=True,
                can_delete=True,
            )
        )

    # 3) 活跃部门库中的“已删历史版本”
    version_rows = (
        db.query(FileVersionTrash)
        .filter(FileVersionTrash.library_id.in_(lib_ids))
        .order_by(FileVersionTrash.deleted_at.desc())
        .all()
        if lib_ids
        else []
    )
    version_entry_ids = {r.file_entry_id for r in version_rows}
    version_entries = (
        db.query(FileEntry).filter(FileEntry.id.in_(version_entry_ids)).all()
        if version_entry_ids
        else []
    )
    version_entry_map: dict[int, FileEntry] = {e.id: e for e in version_entries}
    deleter_ids = {r.deleted_by_id for r in version_rows if getattr(r, "deleted_by_id", None)}
    deleters = db.query(User).filter(User.id.in_(deleter_ids)).all() if deleter_ids else []
    deleter_name_map: dict[int, str] = {u.id: (u.username or u.email or f"用户{u.id}") for u in deleters}

    for r in version_rows:
        entry = version_entry_map.get(r.file_entry_id)
        entry_path = entry.path if entry else f"文件#{r.file_entry_id}"
        can_restore = bool(entry and entry.deleted_at is None)
        items.append(
            GlobalTrashItem(
                id=r.id,
                type="file_version",
                entry_id=r.file_entry_id,
                version_no=r.version_no,
                library_id=r.library_id,
                library_name=lib_names.get(r.library_id) or None,
                path=f"{entry_path} (历史版本 v{r.version_no})",
                is_dir=False,
                deleted_at=r.deleted_at,
                username=deleter_name_map.get(r.deleted_by_id) if r.deleted_by_id else None,
                can_restore=can_restore,
                can_delete=True,
            )
        )
    items.sort(key=lambda x: x.deleted_at, reverse=True)
    return items


@router.get("/global-trash", response_model=List[GlobalTrashItem])
def list_global_trash(
    limit: int = Query(50, ge=1, le=500, description="每页数量"),
    offset: int = Query(0, ge=0, description="起始偏移量"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """全局回收站：全平台所有库的删除文件与文件库聚合列表。仅超级管理员可访问。

    目前使用简单的 limit/offset 分页，不返回总数，前端通过本页数量是否达到 limit 来判断是否还有下一页。
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅系统管理员可查看全局回收站")

    # 1) 全平台文件级回收站（支持简单分页）
    file_q = (
        db.query(FileEntry)
        .filter(FileEntry.deleted_at != None)  # noqa: E711
        .order_by(FileEntry.deleted_at.desc())
    )
    file_entries = file_q.offset(offset).limit(limit).all()
    lib_ids = list({e.library_id for e in file_entries})
    libs = db.query(Library).filter(Library.id.in_(lib_ids)).all() if lib_ids else []
    lib_names = {lib.id: getattr(lib, "name", "") or "" for lib in libs}
    lib_owner_ids = {lib.owner_id for lib in libs if getattr(lib, "owner_id", None)}

    # 预取文件创建人和库拥有者
    creator_ids = {e.created_by_id for e in file_entries if getattr(e, "created_by_id", None)}
    user_ids = set(creator_ids) | set(lib_owner_ids)
    users = db.query(User).filter(User.id.in_(user_ids)).all() if user_ids else []
    user_name_map: dict[int, str] = {}
    for u in users:
        user_name_map[u.id] = u.username or u.email or f"用户{u.id}"

    # 映射 library_id -> owner_id
    lib_owner_map: dict[int, Optional[int]] = {lib.id: lib.owner_id for lib in libs}

    items: list[GlobalTrashItem] = []
    for e in file_entries:
        username: Optional[str] = None
        if getattr(e, "created_by_id", None):
            username = user_name_map.get(e.created_by_id)
        if not username:
            owner_id = lib_owner_map.get(e.library_id)
            if owner_id:
                username = user_name_map.get(owner_id)

        items.append(
            GlobalTrashItem(
                id=e.id,
                type="file",
                library_id=e.library_id,
                library_name=lib_names.get(e.library_id) or None,
                path=e.path,
                is_dir=e.is_dir,
                deleted_at=e.deleted_at,
                username=username,
                can_restore=True,
                can_delete=True,
            )
        )

    # 2) 全平台文件库回收站（软删除的库）
    deleted_libs = (
        db.query(Library)
        .filter(Library.deleted_at != None)  # noqa: E711
        .all()
    )
    # 预取库拥有者
    lib_owner_ids2 = {lib.owner_id for lib in deleted_libs if getattr(lib, "owner_id", None)}
    owners2 = db.query(User).filter(User.id.in_(lib_owner_ids2)).all() if lib_owner_ids2 else []
    owner2_name_map: dict[int, str] = {}
    for u in owners2:
        owner2_name_map[u.id] = u.username or u.email or f"用户{u.id}"

    for lib in deleted_libs:
        username: Optional[str] = None
        if getattr(lib, "owner_id", None):
            username = owner2_name_map.get(lib.owner_id)

        items.append(
            GlobalTrashItem(
                id=lib.id,
                type="library",
                library_id=lib.id,
                library_name=getattr(lib, "name", "") or None,
                path=getattr(lib, "name", "") or None,
                is_dir=True,
                deleted_at=getattr(lib, "deleted_at"),
                username=username,
                can_restore=True,
                can_delete=True,
            )
        )

    # 3) 全平台“已删历史版本”
    version_rows = (
        db.query(FileVersionTrash)
        .order_by(FileVersionTrash.deleted_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    version_lib_ids = {r.library_id for r in version_rows}
    version_entry_ids = {r.file_entry_id for r in version_rows}
    version_libs = db.query(Library).filter(Library.id.in_(version_lib_ids)).all() if version_lib_ids else []
    version_lib_name_map: dict[int, str] = {lib.id: (lib.name or "") for lib in version_libs}
    version_entries = db.query(FileEntry).filter(FileEntry.id.in_(version_entry_ids)).all() if version_entry_ids else []
    version_entry_map: dict[int, FileEntry] = {e.id: e for e in version_entries}
    deleter_ids = {r.deleted_by_id for r in version_rows if getattr(r, "deleted_by_id", None)}
    deleters = db.query(User).filter(User.id.in_(deleter_ids)).all() if deleter_ids else []
    deleter_name_map: dict[int, str] = {u.id: (u.username or u.email or f"用户{u.id}") for u in deleters}

    for r in version_rows:
        entry = version_entry_map.get(r.file_entry_id)
        entry_path = entry.path if entry else f"文件#{r.file_entry_id}"
        items.append(
            GlobalTrashItem(
                id=r.id,
                type="file_version",
                entry_id=r.file_entry_id,
                version_no=r.version_no,
                library_id=r.library_id,
                library_name=version_lib_name_map.get(r.library_id) or None,
                path=f"{entry_path} (历史版本 v{r.version_no})",
                is_dir=False,
                deleted_at=r.deleted_at,
                username=deleter_name_map.get(r.deleted_by_id) if r.deleted_by_id else None,
                can_restore=bool(entry and entry.deleted_at is None),
                can_delete=True,
            )
        )

    # 4) 统一按删除时间倒序返回
    items.sort(key=lambda x: x.deleted_at, reverse=True)
    return items


@router.get("/my-trash", response_model=List[GlobalTrashItem])
def list_my_trash(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    我的回收站视图（主页「回收站」）：
    - 库：当前用户拥有的所有已软删资料库
    - 文件：任意库中由当前用户创建的已删文件，或位于当前用户拥有的库中的已删文件
    """
    user_id = current_user.id

    items: list[GlobalTrashItem] = []

    # 1) 我拥有的已软删资料库（管理员在这里也只看“自己拥有的库”）
    my_deleted_libs = (
        db.query(Library)
        .filter(
            Library.deleted_at != None,  # noqa: E711
            Library.owner_id == user_id,
        )
        .all()
    )
    owner_username = current_user.username or current_user.email or f"用户{user_id}"
    # 预取部门信息用于权限判断
    dept_ids = {lib.department_id for lib in my_deleted_libs if getattr(lib, "department_id", None)}
    depts = (
        db.query(Department).filter(Department.id.in_(dept_ids)).all() if dept_ids else []
    )
    dept_leader_map: dict[int, Optional[int]] = {
        d.id: getattr(d, "leader_user_id", None) for d in depts
    }

    def _can_manage_library_soft(lib: Library, u: User) -> bool:
        """用于回收站权限判断的轻量版：不抛异常，仅返回布尔值。"""
        if u.is_superuser:
            return True
        # 个人库：仅拥有者
        if getattr(lib, "department_id", None) is None:
            return lib.owner_id == u.id
        # 部门库：仅部门负责人
        leader_id = dept_leader_map.get(lib.department_id)
        return leader_id is not None and leader_id == u.id

    for lib in my_deleted_libs:
        # 仅当当前用户对该库有管理权限时，才允许在个人回收站中对库执行恢复/删除
        can_manage = _can_manage_library_soft(lib, current_user)
        items.append(
            GlobalTrashItem(
                id=lib.id,
                type="library",
                library_id=lib.id,
                library_name=getattr(lib, "name", "") or None,
                path=getattr(lib, "name", "") or None,
                is_dir=True,
                deleted_at=getattr(lib, "deleted_at"),
                username=owner_username,
                can_restore=can_manage,
                can_delete=can_manage,
            )
        )

    # 2) 文件级回收站：
    #    - 我拥有的库中的任意已删文件
    #    - 或由我创建的已删文件（无论库属于谁）
    #
    # 为避免重复（例如「我拥有的库」里也有我创建的文件），下面用 set 去重。
    file_rows = (
        db.query(FileEntry, Library)
        .join(Library, Library.id == FileEntry.library_id)
        .filter(
            FileEntry.deleted_at != None,  # noqa: E711
            Library.deleted_at.is_(None),  # 库仍存在时才列出文件；库已软删的情况以库为主
            or_(
                Library.owner_id == user_id,
                FileEntry.created_by_id == user_id,
            ),
        )
        .all()
    )

    seen_file_ids: set[int] = set()
    for e, lib in file_rows:
        if e.id in seen_file_ids:
            continue
        seen_file_ids.add(e.id)
        # 是否允许当前用户对该文件执行恢复/删除：沿用库级回收站权限
        can_manage = _can_manage_library_soft(lib, current_user)

        items.append(
            GlobalTrashItem(
                id=e.id,
                type="file",
                library_id=e.library_id,
                library_name=getattr(lib, "name", "") or None,
                path=e.path,
                is_dir=e.is_dir,
                deleted_at=e.deleted_at,
                username=owner_username,
                can_restore=can_manage,
                can_delete=can_manage,
            )
        )

    # 3) 版本级回收站：
    #    - 我拥有的库中的任意已删历史版本
    #    - 或由我删除的历史版本（无论库属于谁）
    version_rows = (
        db.query(FileVersionTrash, Library)
        .join(Library, Library.id == FileVersionTrash.library_id)
        .filter(
            Library.deleted_at.is_(None),
            or_(
                Library.owner_id == user_id,
                FileVersionTrash.deleted_by_id == user_id,
            ),
        )
        .all()
    )
    version_entry_ids = {row.file_entry_id for row, _ in version_rows}
    version_entries = (
        db.query(FileEntry).filter(FileEntry.id.in_(version_entry_ids)).all() if version_entry_ids else []
    )
    version_entry_map: dict[int, FileEntry] = {e.id: e for e in version_entries}
    version_deleter_ids = {row.deleted_by_id for row, _ in version_rows if getattr(row, "deleted_by_id", None)}
    version_deleters = (
        db.query(User).filter(User.id.in_(version_deleter_ids)).all() if version_deleter_ids else []
    )
    version_deleter_name_map: dict[int, str] = {
        u.id: (u.username or u.email or f"用户{u.id}") for u in version_deleters
    }
    seen_version_ids: set[int] = set()
    for row, lib in version_rows:
        if row.id in seen_version_ids:
            continue
        seen_version_ids.add(row.id)
        can_manage = _can_manage_library_soft(lib, current_user)
        entry = version_entry_map.get(row.file_entry_id)
        entry_path = entry.path if entry else f"文件#{row.file_entry_id}"
        items.append(
            GlobalTrashItem(
                id=row.id,
                type="file_version",
                entry_id=row.file_entry_id,
                version_no=row.version_no,
                library_id=row.library_id,
                library_name=getattr(lib, "name", "") or None,
                path=f"{entry_path} (历史版本 v{row.version_no})",
                is_dir=False,
                deleted_at=row.deleted_at,
                username=version_deleter_name_map.get(row.deleted_by_id) if row.deleted_by_id else owner_username,
                can_restore=can_manage and bool(entry and entry.deleted_at is None),
                can_delete=can_manage,
            )
        )

    # 4) 统一按删除时间倒序返回
    items.sort(key=lambda x: x.deleted_at, reverse=True)
    return items


@router.post("/{entry_id}/restore", response_model=FileRead)
def restore_file(
    entry_id: int,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """从回收站恢复"""
    entry: FileEntry | None = db.query(FileEntry).filter(FileEntry.id == entry_id).first()
    if not entry or not entry.deleted_at:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="回收站中无此项")
    _check_trash_permission(db, entry.library_id, current_user)
    entry.deleted_at = None
    log_audit(
        db,
        current_user.id,
        current_user.username,
        "restore",
        "file",
        entry.id,
        f"path={entry.path}",
        ip_address=get_client_ip(request),
    )
    db.commit()
    db.refresh(entry)
    # 通知创建者（如存在且不是当前用户）
    try:
        if entry.created_by_id and entry.created_by_id != current_user.id:
            create_notification(
                db,
                user_id=entry.created_by_id,
                type="info",
                title="文件已恢复",
                message=f"文件「{entry.path}」已从回收站恢复",
            )
    except Exception:
        pass
    return entry


def _permanent_delete_entry(db: Session, entry: FileEntry) -> None:
    """彻底删除一条记录及其磁盘文件（不删子项）"""
    versions = db.query(FileVersion).filter(FileVersion.file_entry_id == entry.id).all()
    for v in versions:
        p = Path(v.storage_path)
        if p.is_file():
            try:
                p.unlink()
            except OSError:
                pass
    db.query(FileVersion).filter(FileVersion.file_entry_id == entry.id).delete()

    trashed_versions = db.query(FileVersionTrash).filter(FileVersionTrash.file_entry_id == entry.id).all()
    for tv in trashed_versions:
        p = Path(tv.storage_path)
        if p.is_file():
            try:
                p.unlink()
            except OSError:
                pass
    db.query(FileVersionTrash).filter(FileVersionTrash.file_entry_id == entry.id).delete()
    db.delete(entry)


@router.delete("/trash/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def permanent_delete(
    entry_id: int,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """从回收站彻底删除（不可恢复）；若为目录则递归删除其下所有已在回收站中的项"""
    entry: FileEntry | None = db.query(FileEntry).filter(FileEntry.id == entry_id).first()
    if not entry or not entry.deleted_at:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="回收站中无此项")
    _check_trash_permission(db, entry.library_id, current_user)
    if entry.is_dir:
        # 先彻底删除所有在回收站中的子项（同库、路径在其下）
        prefix = entry.path.rstrip("/") + "/"
        children = (
            db.query(FileEntry)
            .filter(
                FileEntry.library_id == entry.library_id,
                FileEntry.path.startswith(prefix),
                FileEntry.deleted_at != None,  # noqa: E711
            )
            .all()
        )
        for c in children:
            _permanent_delete_entry(db, c)
    path_before_delete = entry.path
    _permanent_delete_entry(db, entry)
    log_audit(
        db,
        current_user.id,
        current_user.username,
        "permanent_delete",
        "file",
        entry_id,
        f"path={path_before_delete}",
        ip_address=get_client_ip(request),
    )
    db.commit()


@router.get("/search", response_model=List[FileRead])
def search_files(
    library_id: int,
    keyword: str = Query(..., min_length=1, description="搜索关键词，匹配路径中的文件名"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """按关键词搜索文件（匹配路径）"""
    _get_library_and_check(db, library_id, current_user)
    kw = keyword.strip()
    if not kw:
        return []
    entries = (
        db.query(FileEntry)
        .filter(
            FileEntry.library_id == library_id,
            FileEntry.deleted_at.is_(None),
            FileEntry.path.ilike(f"%{kw}%"),
        )
        .order_by(FileEntry.path.asc())
        .limit(100)
        .all()
    )
    file_entry_ids = [e.id for e in entries if not e.is_dir]
    latest_size: dict[int, int] = {}
    if file_entry_ids:
        from sqlalchemy import func

        subq = (
            db.query(FileVersion.file_entry_id, func.max(FileVersion.version_no).label("max_ver"))
            .filter(FileVersion.file_entry_id.in_(file_entry_ids))
            .group_by(FileVersion.file_entry_id)
            .subquery()
        )
        rows = (
            db.query(FileVersion.file_entry_id, FileVersion.size)
            .join(subq, (FileVersion.file_entry_id == subq.c.file_entry_id) & (FileVersion.version_no == subq.c.max_ver))
            .all()
        )
        latest_size = {r[0]: r[1] for r in rows}
    result = []
    for e in entries:
        can_dl = can_download_file(db, e, current_user) if not e.is_dir else None
        result.append(
            FileRead(
                id=e.id,
                library_id=e.library_id,
                path=e.path,
                is_dir=e.is_dir,
                size=latest_size.get(e.id) if not e.is_dir else None,
                updated_at=e.updated_at,
                can_download=can_dl,
            )
        )
    return result


@router.get("/search-global", response_model=List[GlobalSearchFileRead])
def search_files_global(
    keyword: str = Query(..., min_length=1, description="搜索关键词，跨可访问资料库匹配路径中的文件名"),
    limit: int = Query(100, ge=1, le=300, description="最大返回条数"),
    include_department: bool = Query(True, description="是否包含部门库中的文件"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """跨资料库搜索文件（按当前用户可访问范围过滤）。"""
    kw = keyword.strip()
    if not kw:
        return []

    lib_ids = get_accessible_library_ids(db, current_user)
    if not lib_ids:
        return []
    if not include_department:
        personal_lib_rows = (
            db.query(Library.id)
            .filter(Library.id.in_(lib_ids), Library.department_id.is_(None), Library.deleted_at.is_(None))
            .all()
        )
        lib_ids = [int(r[0]) for r in personal_lib_rows]
        if not lib_ids:
            return []

    entries = (
        db.query(FileEntry)
        .filter(
            FileEntry.library_id.in_(lib_ids),
            FileEntry.deleted_at.is_(None),
            FileEntry.path.ilike(f"%{kw}%"),
        )
        .order_by(FileEntry.updated_at.desc())
        .limit(limit)
        .all()
    )

    file_entry_ids = [e.id for e in entries if not e.is_dir]
    latest_size: dict[int, int] = {}
    if file_entry_ids:
        from sqlalchemy import func

        subq = (
            db.query(FileVersion.file_entry_id, func.max(FileVersion.version_no).label("max_ver"))
            .filter(FileVersion.file_entry_id.in_(file_entry_ids))
            .group_by(FileVersion.file_entry_id)
            .subquery()
        )
        rows = (
            db.query(FileVersion.file_entry_id, FileVersion.size)
            .join(subq, (FileVersion.file_entry_id == subq.c.file_entry_id) & (FileVersion.version_no == subq.c.max_ver))
            .all()
        )
        latest_size = {r[0]: r[1] for r in rows}

    lib_name_rows = db.query(Library.id, Library.name).filter(Library.id.in_(lib_ids)).all()
    lib_name_map: dict[int, str] = {int(i): n or "" for i, n in lib_name_rows}

    result: list[GlobalSearchFileRead] = []
    for e in entries:
        can_dl = can_download_file(db, e, current_user) if not e.is_dir else None
        result.append(
            GlobalSearchFileRead(
                id=e.id,
                library_id=e.library_id,
                library_name=lib_name_map.get(e.library_id) or None,
                path=e.path,
                is_dir=e.is_dir,
                size=latest_size.get(e.id) if not e.is_dir else None,
                updated_at=e.updated_at,
                can_download=can_dl,
            )
        )
    return result


SYSTEM_DEFAULT_TOTAL_QUOTA_BYTES = int(getattr(settings, "STORAGE_SYSTEM_TOTAL_BYTES", 500 * 1024 * 1024 * 1024))


class StorageStats(BaseModel):
    used_bytes: int
    used_display: str
    total_bytes: int = SYSTEM_DEFAULT_TOTAL_QUOTA_BYTES
    total_display: str = "500 GB"
    percent: float


class DepartmentStorageRow(BaseModel):
    id: int
    name: str
    used_bytes: int
    used_display: str
    total_bytes: int
    total_display: str
    percent: float
    users: int
    file_count: int
    status: str  # normal | warning | critical
    trend: str = "+0.0%"


class UserStorageRow(BaseModel):
    id: int
    name: str
    department_name: str | None = None
    used_bytes: int
    used_display: str
    total_bytes: int
    total_display: str
    percent: float
    file_count: int
    last_upload: datetime | None = None


class FileTypeStat(BaseModel):
    type: str
    count: int
    size_bytes: int
    size_display: str
    percent_count: float
    percent_size: float


@router.get("/storage", response_model=StorageStats)
def get_storage_stats(
    library_id: Optional[int] = Query(None, description="指定资料库，不填则统计当前用户可访问的汇总"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前用户视角下的存储空间使用量（个人配额视角）。"""
    from sqlalchemy import func

    q = (
        db.query(func.sum(FileVersion.size).label("total"))
        .join(FileEntry, FileVersion.file_entry_id == FileEntry.id)
        .filter(FileEntry.deleted_at.is_(None))
    )
    if library_id is not None:
        lib = _get_library_and_check(db, library_id, current_user)
        q = q.filter(FileEntry.library_id == lib.id)
    else:
        # 汇总当前用户可访问的库（拥有者 + 成员）
        lib_ids = get_accessible_library_ids(db, current_user)
        if lib_ids:
            q = q.filter(FileEntry.library_id.in_(lib_ids))
        else:
            q = q.filter(FileEntry.library_id == -1)
    row = q.first()
    used = int(row[0]) if row and row[0] else 0
    # 个人视角总容量：优先使用当前用户的个人配额；未配置时回退到系统默认 500GB
    total = int(getattr(current_user, "storage_quota_bytes", None) or SYSTEM_DEFAULT_TOTAL_QUOTA_BYTES)
    pct = (used / total * 100) if total > 0 else 0

    return StorageStats(
        used_bytes=used,
        used_display=_format_bytes(used),
        total_bytes=total,
        total_display=_format_bytes(total),
        percent=round(pct, 1),
    )


@router.get("/storage/system", response_model=StorageStats)
def get_system_storage_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取系统总存储容量视角的统计数据（与单个用户配额解耦）。

    - used: 全平台所有未删除文件的总占用
    - total: 系统级总配额（当前为固定默认值，可后续改为配置项）
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="仅管理员可查看系统总存储容量"
        )

    from sqlalchemy import func

    row = (
        db.query(func.sum(FileVersion.size).label("total"))
        .join(FileEntry, FileVersion.file_entry_id == FileEntry.id)
        .filter(
            FileEntry.deleted_at.is_(None),
        )
        .first()
    )
    used = int(row[0]) if row and row[0] else 0
    total = SYSTEM_DEFAULT_TOTAL_QUOTA_BYTES
    pct = (used / total * 100) if total > 0 else 0

    return StorageStats(
        used_bytes=used,
        used_display=_format_bytes(used),
        total_bytes=total,
        total_display=_format_bytes(total),
        percent=round(pct, 1),
    )


def _format_bytes(b: int) -> str:
    if b < 1024:
        return f"{b} B"
    if b < 1024 * 1024:
        return f"{b / 1024:.1f} KB"
    if b < 1024 * 1024 * 1024:
        return f"{b / (1024 * 1024):.1f} MB"
    return f"{b / (1024 * 1024 * 1024):.1f} GB"


def _to_utc_naive(dt: datetime | None) -> datetime | None:
    """
    将 datetime 统一为“UTC 下的 naive datetime”用于跨数据库比较。
    SQLite 常见为 naive，PostgreSQL 常见为 aware，统一后可避免比较异常。
    """
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _format_growth_trend(recent_count: int, previous_count: int) -> str:
    """
    计算增长趋势（最近 7 天 vs 前 7 天），并格式化为带符号百分比字符串。
    """
    if previous_count <= 0:
        if recent_count <= 0:
            return "0.0%"
        return "+100.0%"
    delta_pct = ((recent_count - previous_count) / previous_count) * 100.0
    sign = "+" if delta_pct > 0 else ""
    return f"{sign}{delta_pct:.1f}%"


def _iter_latest_files(db: Session):
    """返回所有未删除文件的最新版本行，用于存储统计。"""
    from sqlalchemy import func

    subq = (
        db.query(
            FileVersion.file_entry_id,
            func.max(FileVersion.version_no).label("max_ver"),
        )
        .group_by(FileVersion.file_entry_id)
        .subquery()
    )
    rows = (
        db.query(
            FileEntry.id,
            FileEntry.path,
            FileEntry.library_id,
            FileVersion.size,
            FileVersion.uploaded_at,
            FileVersion.uploaded_by_id,
            Library.department_id,
            Library.owner_id,
        )
        .join(
            subq,
            (FileVersion.file_entry_id == subq.c.file_entry_id)
            & (FileVersion.version_no == subq.c.max_ver),
        )
        .join(FileEntry, FileEntry.id == FileVersion.file_entry_id)
        .join(Library, Library.id == FileEntry.library_id)
        .filter(
            FileEntry.deleted_at.is_(None),
            Library.deleted_at.is_(None),
        )
        .all()
    )
    return rows


@router.get("/storage/departments", response_model=List[DepartmentStorageRow])
def get_storage_by_department(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """按部门统计存储使用情况，仅管理员可见。"""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="仅管理员可查看存储统计"
        )

    # 基础数据
    depts = {d.id: d for d in db.query(Department).all()}

    from sqlalchemy import func

    # 每个部门用户数
    dept_user_counts: dict[int, int] = {
        row[0]: row[1]
        for row in db.query(User.department_id, func.count(User.id))
        .group_by(User.department_id)
        .all()
        if row[0] is not None
    }

    # 文件级别统计（当前使用量、文件总数）
    latest_rows = _iter_latest_files(db)
    dept_used: dict[int, int] = {}
    dept_file_count: dict[int, int] = {}
    for (
        _entry_id,
        _path,
        _lib_id,
        size,
        _uploaded_at,
        _uploaded_by_id,
        dept_id,
        _owner_id,
    ) in latest_rows:
        if dept_id is None:
            continue
        dept_used[dept_id] = dept_used.get(dept_id, 0) + int(size or 0)
        dept_file_count[dept_id] = dept_file_count.get(dept_id, 0) + 1

    # 增长趋势：最近 7 天新增文件数 vs 前 7 天新增文件数
    now_utc_naive = _to_utc_naive(datetime.now(timezone.utc)) or datetime.utcnow()
    recent_start = now_utc_naive - timedelta(days=7)
    previous_start = now_utc_naive - timedelta(days=14)

    active_file_rows = (
        db.query(FileEntry.created_at, Library.department_id)
        .join(Library, Library.id == FileEntry.library_id)
        .filter(
            FileEntry.deleted_at.is_(None),
            FileEntry.is_dir.is_(False),
            Library.deleted_at.is_(None),
            Library.department_id.isnot(None),
        )
        .all()
    )
    dept_recent_new_files: dict[int, int] = {}
    dept_previous_new_files: dict[int, int] = {}
    for created_at, dept_id in active_file_rows:
        if dept_id is None:
            continue
        created_naive = _to_utc_naive(created_at)
        if created_naive is None:
            continue
        if created_naive >= recent_start:
            dept_recent_new_files[dept_id] = dept_recent_new_files.get(dept_id, 0) + 1
        elif created_naive >= previous_start:
            dept_previous_new_files[dept_id] = dept_previous_new_files.get(dept_id, 0) + 1

    rows_out: list[DepartmentStorageRow] = []
    for dept_id, dept in depts.items():
        used = dept_used.get(dept_id, 0)
        # 部门配额：优先使用自定义配额，否则默认 100GB
        quota_bytes = dept.storage_quota_bytes or (100 * 1024 * 1024 * 1024)
        users = dept_user_counts.get(dept_id, 0)
        file_cnt = dept_file_count.get(dept_id, 0)
        pct = (used / quota_bytes * 100) if quota_bytes > 0 else 0.0
        if pct >= 90:
            status_str = "critical"
        elif pct >= 70:
            status_str = "warning"
        else:
            status_str = "normal"
        trend = _format_growth_trend(
            dept_recent_new_files.get(dept_id, 0),
            dept_previous_new_files.get(dept_id, 0),
        )
        rows_out.append(
            DepartmentStorageRow(
                id=dept_id,
                name=dept.name,
                used_bytes=used,
                used_display=_format_bytes(used),
                total_bytes=quota_bytes,
                total_display=_format_bytes(quota_bytes),
                percent=round(pct, 1),
                users=users,
                file_count=file_cnt,
                status=status_str,
                trend=trend,
            )
        )

    # 使用量降序
    rows_out.sort(key=lambda r: r.used_bytes, reverse=True)
    return rows_out


@router.get("/storage/users", response_model=List[UserStorageRow])
def get_storage_by_user(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """按用户统计存储使用情况，仅管理员可见。"""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="仅管理员可查看存储统计"
        )

    users = {u.id: u for u in db.query(User).all()}
    dept_map = {d.id: d for d in db.query(Department).all()}

    latest_rows = _iter_latest_files(db)

    user_used: dict[int, int] = {}
    user_file_count: dict[int, int] = {}
    user_last_upload: dict[int, datetime] = {}

    for (
        _entry_id,
        _path,
        _lib_id,
        size,
        uploaded_at,
        uploaded_by_id,
        _dept_id,
        owner_id,
    ) in latest_rows:
        # 以资料库拥有者作为主要归属人；若缺失则回退到最后上传者
        uid = owner_id or uploaded_by_id
        if uid is None:
            continue
        used_prev = user_used.get(uid, 0)
        user_used[uid] = used_prev + int(size or 0)
        user_file_count[uid] = user_file_count.get(uid, 0) + 1
        if uploaded_at is not None:
            last = user_last_upload.get(uid)
            if last is None or uploaded_at > last:
                user_last_upload[uid] = uploaded_at

    rows_out: list[UserStorageRow] = []
    for uid, used in user_used.items():
        u = users.get(uid)
        if not u:
            continue
        quota_bytes = u.storage_quota_bytes or (100 * 1024 * 1024 * 1024)
        dept_name = None
        if u.department_id is not None:
            d = dept_map.get(u.department_id)
            if d:
                dept_name = d.name
        pct = (used / quota_bytes * 100) if quota_bytes > 0 else 0.0
        rows_out.append(
            UserStorageRow(
                id=uid,
                name=u.username or u.email or f"用户{uid}",
                department_name=dept_name,
                used_bytes=used,
                used_display=_format_bytes(used),
                total_bytes=quota_bytes,
                total_display=_format_bytes(quota_bytes),
                percent=round(pct, 1),
                file_count=user_file_count.get(uid, 0),
                last_upload=user_last_upload.get(uid),
            )
        )

    rows_out.sort(key=lambda r: r.used_bytes, reverse=True)
    return rows_out


class QuotaUpdate(BaseModel):
    quota_gb: float = Field(..., gt=0, le=100000, description="配额大小（GB）")


@router.post("/storage/departments/{dept_id}/quota", status_code=status.HTTP_204_NO_CONTENT)
def update_department_quota(
    dept_id: int,
    payload: QuotaUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """调整部门存储配额（GB），仅管理员可调用。"""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="仅管理员可调整存储配额"
        )
    dept: Department | None = db.query(Department).filter(Department.id == dept_id).first()
    if not dept:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="部门不存在")
    quota_bytes = int(payload.quota_gb * 1024 * 1024 * 1024)
    dept.storage_quota_bytes = quota_bytes
    db.commit()
    return None


@router.post("/storage/users/{user_id}/quota", status_code=status.HTTP_204_NO_CONTENT)
def update_user_quota(
    user_id: int,
    payload: QuotaUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """调整用户存储配额（GB），仅管理员可调用。"""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="仅管理员可调整存储配额"
        )
    u: User | None = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    quota_bytes = int(payload.quota_gb * 1024 * 1024 * 1024)
    u.storage_quota_bytes = quota_bytes
    db.commit()
    return None


@router.get("/storage/filetypes", response_model=List[FileTypeStat])
def get_storage_by_file_type(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """按文件类型统计存储情况，仅管理员可见。"""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="仅管理员可查看存储统计"
        )

    # 最新版本的文件（不含目录），用于按扩展名聚合
    latest_rows = _iter_latest_files(db)

    # 仅统计文件（排除目录），按扩展名聚合
    from collections import defaultdict
    import os

    type_count: dict[str, int] = defaultdict(int)
    type_size: dict[str, int] = defaultdict(int)

    for (
        _entry_id,
        path,
        _lib_id,
        size,
        _uploaded_at,
        _uploaded_by_id,
        _dept_id,
        _owner_id,
    ) in latest_rows:
        # path 为空时跳过
        if not path:
            ext = "other"
        else:
            name = path.split("/")[-1]
            _root, extname = os.path.splitext(name)
            if extname:
                ext = extname.lower().lstrip(".")  # .PDF -> pdf
            else:
                ext = "other"
        b = int(size or 0)
        type_count[ext] += 1
        type_size[ext] += b

    # 若没有任何文件，返回空列表
    if not type_count:
        return []

    total_count = sum(type_count.values()) or 1
    total_size = sum(type_size.values()) or 1

    # 取按大小排序前 N 个类型，其余归为 other
    MAX_TYPES = 8
    # 按 size 降序
    sorted_items = sorted(type_size.items(), key=lambda kv: kv[1], reverse=True)

    top_keys: list[str] = [k for k, _ in sorted_items[:MAX_TYPES]]
    other_keys: list[str] = [k for k in type_count.keys() if k not in top_keys]

    rows_out: list[FileTypeStat] = []

    def _label(key: str) -> str:
        if key == "other":
            return "其他"
        # 展示为大写扩展名，例如 PDF、DOCX
        return key.upper()

    for key in top_keys:
        cnt = type_count.get(key, 0)
        size_b = type_size.get(key, 0)
        rows_out.append(
            FileTypeStat(
                type=_label(key),
                count=cnt,
                size_bytes=size_b,
                size_display=_format_bytes(size_b),
                percent_count=round(cnt / total_count * 100, 1),
                percent_size=round(size_b / total_size * 100, 1),
            )
        )

    if other_keys:
        cnt = sum(type_count[k] for k in other_keys)
        size_b = sum(type_size[k] for k in other_keys)
        rows_out.append(
            FileTypeStat(
                type="其他",
                count=cnt,
                size_bytes=size_b,
                size_display=_format_bytes(size_b),
                percent_count=round(cnt / total_count * 100, 1),
                percent_size=round(size_b / total_size * 100, 1),
            )
        )

    # 按大小占用降序展示
    rows_out.sort(key=lambda r: r.size_bytes, reverse=True)
    return rows_out


@router.get("/versions", response_model=List[FileVersionRead])
def list_versions(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """列出某文件的所有版本（从新到旧）"""
    entry: FileEntry | None = db.query(FileEntry).filter(FileEntry.id == entry_id).first()
    if not entry or entry.is_dir or entry.deleted_at:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")
    if not can_access_file(db, entry, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该文件")
    versions = (
        db.query(FileVersion)
        .filter(FileVersion.file_entry_id == entry.id)
        .order_by(FileVersion.version_no.desc())
        .all()
    )
    user_ids = {int(v.uploaded_by_id) for v in versions if getattr(v, "uploaded_by_id", None)}
    user_map: dict[int, User] = {}
    if user_ids:
        rows = db.query(User).filter(User.id.in_(user_ids)).all()
        user_map = {u.id: u for u in rows}

    out: list[FileVersionRead] = []
    for v in versions:
        uploader_name: Optional[str] = None
        uid = getattr(v, "uploaded_by_id", None)
        if uid is not None:
            u = user_map.get(int(uid))
            if u is not None:
                uploader_name = u.username or u.email or f"用户{u.id}"
        out.append(
            FileVersionRead(
                id=v.id,
                version_no=v.version_no,
                size=v.size,
                uploaded_at=v.uploaded_at,
                uploaded_by=uploader_name,
            )
        )
    return out


@router.delete("/{entry_id}/versions/{version_no}", status_code=status.HTTP_204_NO_CONTENT)
def delete_file_version(
    entry_id: int,
    version_no: int = FPath(..., ge=1, description="要删除的版本号"),
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除指定文件版本到回收站（至少保留一个版本）。"""
    entry: FileEntry | None = db.query(FileEntry).filter(FileEntry.id == entry_id).first()
    if not entry or entry.is_dir or entry.deleted_at:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")
    _get_library_and_check(db, entry.library_id, current_user, require_write=True)

    versions = (
        db.query(FileVersion)
        .filter(FileVersion.file_entry_id == entry.id)
        .order_by(FileVersion.version_no.desc())
        .all()
    )
    if not versions:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件版本不存在")
    if len(versions) <= 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="至少保留一个版本，无法删除")

    target = next((v for v in versions if v.version_no == version_no), None)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件版本不存在")

    trash_row = FileVersionTrash(
        file_entry_id=entry.id,
        library_id=entry.library_id,
        version_no=target.version_no,
        storage_path=target.storage_path,
        size=target.size,
        content_hash=target.content_hash,
        comment=target.comment,
        uploaded_by_id=target.uploaded_by_id,
        uploaded_at=target.uploaded_at,
        deleted_by_id=current_user.id,
        deleted_at=datetime.now(timezone.utc),
    )
    db.add(trash_row)
    db.delete(target)
    log_audit(
        db,
        current_user.id,
        current_user.username,
        "delete_version",
        "file",
        entry.id,
        f"path={entry.path} version={version_no} -> recycle",
        ip_address=get_client_ip(request),
    )
    db.commit()


@router.post("/version-trash/{trash_id}/restore", status_code=status.HTTP_204_NO_CONTENT)
def restore_deleted_file_version(
    trash_id: int,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """恢复回收站中的单个历史版本。"""
    row: FileVersionTrash | None = (
        db.query(FileVersionTrash).filter(FileVersionTrash.id == trash_id).first()
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="回收站中无此版本")

    entry: FileEntry | None = db.query(FileEntry).filter(FileEntry.id == row.file_entry_id).first()
    if not entry or entry.deleted_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="所属文件已在回收站，无法恢复历史版本")
    _get_library_and_check(db, entry.library_id, current_user, require_write=True)

    exists = (
        db.query(FileVersion)
        .filter(
            FileVersion.file_entry_id == row.file_entry_id,
            FileVersion.version_no == row.version_no,
        )
        .first()
    )
    if exists:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="版本号冲突，无法恢复")
    if not Path(row.storage_path).is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="版本物理文件缺失，无法恢复")

    restored = FileVersion(
        file_entry_id=row.file_entry_id,
        version_no=row.version_no,
        storage_path=row.storage_path,
        size=row.size,
        content_hash=row.content_hash,
        uploaded_by_id=row.uploaded_by_id,
        uploaded_at=row.uploaded_at,
        comment=row.comment,
    )
    db.add(restored)
    db.delete(row)
    log_audit(
        db,
        current_user.id,
        current_user.username,
        "restore_version",
        "file",
        entry.id,
        f"path={entry.path} version={restored.version_no}",
        ip_address=get_client_ip(request),
    )
    db.commit()


@router.delete("/version-trash/{trash_id}", status_code=status.HTTP_204_NO_CONTENT)
def permanent_delete_file_version(
    trash_id: int,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """彻底删除回收站中的单个历史版本。"""
    row: FileVersionTrash | None = (
        db.query(FileVersionTrash).filter(FileVersionTrash.id == trash_id).first()
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="回收站中无此版本")
    _get_library_and_check(db, row.library_id, current_user, require_write=True)

    p = Path(row.storage_path)
    if p.is_file():
        try:
            p.unlink()
        except OSError:
            pass
    try:
        version_dir = p.parent
        if version_dir.is_dir():
            version_dir.rmdir()
    except OSError:
        pass

    entry: FileEntry | None = db.query(FileEntry).filter(FileEntry.id == row.file_entry_id).first()
    entry_path = getattr(entry, "path", None) or f"entry_id={row.file_entry_id}"
    db.delete(row)
    log_audit(
        db,
        current_user.id,
        current_user.username,
        "permanent_delete_version",
        "file",
        row.file_entry_id,
        f"path={entry_path} version={row.version_no}",
        ip_address=get_client_ip(request),
    )
    db.commit()


@router.get("/download")
def download_file(
    entry_id: int,
    version_no: Optional[int] = Query(None, description="指定版本号，不填则下载最新版本"),
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    entry: FileEntry | None = db.query(FileEntry).filter(FileEntry.id == entry_id).first()
    if not entry or entry.is_dir or entry.deleted_at:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")
    if not can_download_file(db, entry, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无下载权限（该文件库已禁止下载或未被授予下载权限）")

    q = db.query(FileVersion).filter(FileVersion.file_entry_id == entry.id)
    if version_no is not None:
        q = q.filter(FileVersion.version_no == version_no)
    else:
        q = q.order_by(FileVersion.version_no.desc())
    version: FileVersion | None = q.first()
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件版本不存在")

    storage_path = Path(version.storage_path)
    if not storage_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件物理数据缺失")

    log_audit(
        db,
        current_user.id,
        current_user.username,
        "下载文件",
        "file",
        entry.id,
        f"path={entry.path} version={version.version_no}",
        ip_address=get_client_ip(request),
    )
    db.commit()

    # 下载文件名优先使用业务路径中的文件名，确保与前端显示名称一致
    filename = Path(entry.path).name or storage_path.name
    return FileResponse(
        path=str(storage_path),
        filename=filename,
        media_type="application/octet-stream",
    )


def _media_type_by_ext(path: str) -> str:
    """根据扩展名返回合适的 media_type，用于预览""" 
    ext = Path(path).suffix.lower()
    _map = {
        ".pdf": "application/pdf",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".svg": "image/svg+xml",
        ".bmp": "image/bmp",
        ".txt": "text/plain; charset=utf-8",
        ".md": "text/markdown; charset=utf-8",
        ".json": "application/json; charset=utf-8",
        ".xml": "application/xml; charset=utf-8",
        ".html": "text/html; charset=utf-8",
        ".htm": "text/html; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".js": "text/javascript; charset=utf-8",
        ".yaml": "text/yaml; charset=utf-8",
        ".yml": "text/yaml; charset=utf-8",
    }
    return _map.get(ext, "application/octet-stream")


def _create_preview_token(entry_id: int, user_id: int) -> str:
    """生成短期预览 token，10 分钟有效（含 user_id 用于审计）"""
    expire = datetime.now(timezone.utc) + timedelta(minutes=10)
    payload = {"entry_id": entry_id, "user_id": user_id, "exp": expire}
    return jwt.encode(
        payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )


def _verify_preview_token(token: str) -> Optional[tuple[int, Optional[int]]]:
    """验证预览 token，返回 (entry_id, user_id)"""
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        eid = payload.get("entry_id")
        uid = payload.get("user_id")
        return (eid, uid) if eid is not None else None
    except JWTError:
        return None


class PreviewTokenRead(BaseModel):
    token: str


@router.get("/preview-token", response_model=PreviewTokenRead)
def get_preview_token(
    entry_id: int,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取预览用短期 token（用于 iframe/img 直接加载，无需 Authorization）"""
    entry: FileEntry | None = db.query(FileEntry).filter(FileEntry.id == entry_id).first()
    if not entry or entry.is_dir or entry.deleted_at:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")
    if not can_access_file(db, entry, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问")
    log_audit(
        db,
        current_user.id,
        current_user.username,
        "预览文件",
        "file",
        entry.id,
        f"path={entry.path}",
        ip_address=get_client_ip(request),
    )
    db.commit()
    return PreviewTokenRead(token=_create_preview_token(entry_id, current_user.id))


def _serve_preview_file(version_no: Optional[int], db: Session, entry: FileEntry):
    """共用：根据 entry 读取并返回文件内容"""
    q = db.query(FileVersion).filter(FileVersion.file_entry_id == entry.id)
    if version_no is not None:
        q = q.filter(FileVersion.version_no == version_no)
    else:
        q = q.order_by(FileVersion.version_no.desc())
    version: FileVersion | None = q.first()
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件版本不存在")

    storage_path = Path(version.storage_path)
    if not storage_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件物理数据缺失")

    filename = storage_path.name
    media_type = _media_type_by_ext(filename)
    return FileResponse(
        path=str(storage_path),
        filename=filename,
        media_type=media_type,
        content_disposition_type="inline",
    )


@router.get("/preview-by-token")
def preview_by_token(
    entry_id: int,
    token: str = Query(..., description="预览 token"),
    version_no: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """通过 token 预览文件（用于 iframe/img 直接加载，无需 Bearer）"""
    verified = _verify_preview_token(token)
    if verified is None or verified[0] != entry_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="token 无效或已过期")
    entry: FileEntry | None = db.query(FileEntry).filter(FileEntry.id == entry_id).first()
    if not entry or entry.is_dir or entry.deleted_at:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")
    uid = verified[1]
    if uid is not None:
        u = db.query(User).filter(User.id == uid).first()
        if u:
            log_audit(db, uid, u.username, "下载文件", "file", entry.id, f"path={entry.path} (通过预览)")
            db.commit()
    return _serve_preview_file(version_no, db, entry)


@router.get("/preview")
def preview_file(
    entry_id: int,
    version_no: Optional[int] = Query(None),
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """在线预览文件（需 Bearer 认证，用于 fetch 获取内容）"""
    entry: FileEntry | None = db.query(FileEntry).filter(FileEntry.id == entry_id).first()
    if not entry or entry.is_dir or entry.deleted_at:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")
    if not can_access_file(db, entry, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问")
    log_audit(
        db,
        current_user.id,
        current_user.username,
        "预览文件",
        "file",
        entry.id,
        f"path={entry.path}",
        ip_address=get_client_ip(request),
    )
    db.commit()
    return _serve_preview_file(version_no, db, entry)


# -----------------------------
# Rendered preview (controlled)
# -----------------------------

class RenderedPreviewMeta(BaseModel):
    entry_id: int
    version_no: int
    filename: str
    preview_type: Literal["pdf", "image", "text", "unsupported"]
    page_count: int = 1  # pdf only
    can_download: bool = False


def _get_version_storage_path(db: Session, entry_id: int, version_no: Optional[int]) -> tuple[FileEntry, FileVersion, Path]:
    entry: FileEntry | None = db.query(FileEntry).filter(FileEntry.id == entry_id).first()
    if not entry or entry.is_dir or entry.deleted_at:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")
    # 访问权限：预览 = 可访问即可（不等于可下载）
    # 受控预览不直接返回原文件，仅返回渲染产物
    # 因此这里统一走 can_access_file
    # 调用处会传 current_user 并校验
    q = db.query(FileVersion).filter(FileVersion.file_entry_id == entry.id)
    if version_no is not None:
        q = q.filter(FileVersion.version_no == version_no)
    else:
        q = q.order_by(FileVersion.version_no.desc())
    version: FileVersion | None = q.first()
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件版本不存在")
    storage_path = Path(version.storage_path)
    if not storage_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件物理数据缺失")
    return entry, version, storage_path


def _preview_type_by_filename(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return "pdf"
    if ext in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}:
        return "image"
    if ext in {".txt", ".md", ".json", ".xml", ".html", ".htm", ".css", ".js", ".yaml", ".yml"}:
        return "text"
    return "unsupported"


def _watermark_text(user: User) -> str:
    """
    受控预览水印文本（MVP 版本）。

    口径：仅展示用户邮箱（作为后续“唯一标识”的基础），避免中文字体兼容问题。
    """
    if getattr(user, "email", None):
        return str(user.email)
    # 兜底：邮箱缺失时退回 username
    return user.username or f"user-{user.id}"


def _apply_watermark_to_image(img_bytes: bytes, wm: str, *, max_side: int = 1600, quality: int = 75) -> tuple[bytes, str]:
    """
    将图片加水印并（可选）降清晰，返回 (out_bytes, content_type)。
    说明：MVP 版本使用简单半透明斜纹文字水印，避免引入复杂渲染依赖。
    """
    from io import BytesIO

    from PIL import Image, ImageDraw, ImageFont

    im = Image.open(BytesIO(img_bytes)).convert("RGBA")
    w, h = im.size
    scale = min(1.0, max_side / max(w, h)) if max(w, h) > 0 else 1.0
    if scale < 1.0:
        im = im.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)

    # 受控预览水印：满屏铺斜纹（小字号、低透明度），用于可追溯且不直接下发原文件
    overlay = Image.new("RGBA", im.size, (255, 255, 255, 0))
    short_side = min(im.size[0], im.size[1])
    font_size = max(12, int(short_side * 0.018))
    font = None
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", font_size)
    except Exception:
        try:
            font = ImageFont.truetype("Arial.ttf", font_size)
        except Exception:
            try:
                font = ImageFont.load_default()
            except Exception:
                font = None

    draw = ImageDraw.Draw(overlay)
    # 半透明斜纹水印（不遮挡正文）
    text_color = (0, 0, 0, 75)
    try:
        bbox = draw.textbbox((0, 0), wm, font=font)
        tw = max(1, bbox[2] - bbox[0])
        th = max(1, bbox[3] - bbox[1])
    except Exception:
        tw, th = 220, 18

    # 按文字尺寸决定铺设密度
    step_x = max(180, int(tw * 1.6))
    step_y = max(140, int(th * 4.0))

    for y in range(-im.size[1], im.size[1] * 2, step_y):
        for x in range(-im.size[0], im.size[0] * 2, step_x):
            draw.text((x, y), wm, fill=text_color, font=font)
            # 交错一层填补空隙
            draw.text((x + step_x // 2, y + step_y // 2), wm, fill=text_color, font=font)

    overlay = overlay.rotate(30, expand=False)
    out = Image.alpha_composite(im, overlay).convert("RGB")
    buf = BytesIO()
    out.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue(), "image/jpeg"


def _render_pdf_page_with_watermark(pdf_path: Path, page: int, wm: str) -> tuple[bytes, str, int]:
    """
    将 PDF 指定页渲染为图片（JPEG），并叠加水印。
    返回 (out_bytes, content_type, page_count)。
    """
    import fitz  # PyMuPDF

    doc = fitz.open(str(pdf_path))
    try:
        page_count = doc.page_count
        if page < 1 or page > page_count:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="页码超出范围")
        p = doc.load_page(page - 1)
        # 适度清晰度（约 144dpi），MVP 不做缓存先控制 CPU
        mat = fitz.Matrix(2.0, 2.0)
        pix = p.get_pixmap(matrix=mat, alpha=False)
        img_bytes = pix.tobytes("png")
        out_bytes, ct = _apply_watermark_to_image(img_bytes, wm, max_side=1600, quality=75)
        return out_bytes, ct, page_count
    finally:
        doc.close()


@router.get("/rendered-preview/meta", response_model=RenderedPreviewMeta)
def get_rendered_preview_meta(
    entry_id: int,
    version_no: Optional[int] = Query(None),
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    受控预览 meta：用于前端判断类型、PDF 页数、是否支持预览，以及是否允许下载。
    注意：该接口不会返回原文件内容。
    """
    entry, version, storage_path = _get_version_storage_path(db, entry_id, version_no)
    if not can_access_file(db, entry, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问")

    filename = storage_path.name
    ptype = _preview_type_by_filename(filename)
    page_count = 1
    if ptype == "pdf":
        try:
            import fitz  # PyMuPDF

            doc = fitz.open(str(storage_path))
            page_count = doc.page_count
            doc.close()
        except Exception:
            ptype = "unsupported"
            page_count = 1

    return RenderedPreviewMeta(
        entry_id=entry.id,
        version_no=version.version_no,
        filename=filename,
        preview_type=ptype,  # type: ignore[arg-type]
        page_count=page_count,
        can_download=can_download_file(db, entry, current_user),
    )


@router.get("/rendered-preview")
def get_rendered_preview(
    entry_id: int,
    version_no: Optional[int] = Query(None),
    page: int = Query(1, ge=1, description="PDF 页码（从 1 开始），非 PDF 忽略"),
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    受控预览内容：返回“渲染产物”（图片或文本），用于只读预览与权限控制。
    - PDF：按页渲染为 JPEG（含水印）
    - 图片：返回降清晰 + 水印后的 JPEG
    - 文本：返回截断后的 text/plain（含水印抬头）
    """
    entry, version, storage_path = _get_version_storage_path(db, entry_id, version_no)
    if not can_access_file(db, entry, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问")

    wm = _watermark_text(current_user)
    ptype = _preview_type_by_filename(storage_path.name)

    # 记录审计：受控预览
    try:
        detail = f"path={entry.path} version={version.version_no} type={ptype}"
        if ptype == "pdf":
            detail += f" page={page}"
        log_audit(
            db,
            current_user.id,
            current_user.username,
            "preview_rendered",
            "file",
            entry.id,
            detail,
            ip_address=get_client_ip(request),
        )
        db.commit()
    except Exception:
        pass

    if ptype == "pdf":
        out_bytes, ct, _page_count = _render_pdf_page_with_watermark(storage_path, page, wm)
        return Response(content=out_bytes, media_type=ct)

    if ptype == "image":
        raw = storage_path.read_bytes()
        out_bytes, ct = _apply_watermark_to_image(raw, wm, max_side=1600, quality=75)
        return Response(content=out_bytes, media_type=ct)

    if ptype == "text":
        # 只读预览不返回原文件：截断（不在内容中注入水印，水印由前端叠加层实现）
        MAX_CHARS = 200_000
        try:
            txt = storage_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            # 二进制或其他编码：回退为 latin-1 近似
            txt = storage_path.read_text(encoding="latin-1", errors="replace")
        if len(txt) > MAX_CHARS:
            txt = txt[:MAX_CHARS] + "\n\n...(内容过长，已截断)...\n"
        return Response(content=txt, media_type="text/plain; charset=utf-8")

    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该文件类型暂不支持受控预览")



