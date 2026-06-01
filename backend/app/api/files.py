import hashlib
import logging
import os
import shutil
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Literal, Optional
from urllib.parse import quote

import aiofiles

from fastapi import APIRouter, BackgroundTasks, Body, Depends, File, HTTPException, UploadFile, Query, Request, status, Path as FPath
from fastapi.responses import Response
from fastapi.responses import FileResponse
from jose import JWTError, jwt
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, Integer, String, cast, literal, not_, or_, select, union_all
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.core.audit import get_client_ip, log_audit
from backend.app.core.config import get_settings
from backend.app.core.library_access import (
    can_download_file,
    can_download_in_library_list_context,
    can_access_file,
    collect_descendant_library_ids,
    get_accessible_library_ids,
    has_library_access,
    libraries_accessible_base_query,
    resolve_root_library,
)
from backend.app.api.notifications import create_notification, create_notification_if_enabled
from backend.app.db.session import get_db
from backend.app.models.department import Department
from backend.app.models.file import FileEntry, FileVersion, FileVersionTrash
from backend.app.models.file_share import FileShare
from backend.app.models.library import Library
from backend.app.models.user import User


logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/files", tags=["files"])


def _max_upload_file_bytes() -> int:
    return int(getattr(settings, "MAX_UPLOAD_FILE_BYTES", 2 * 1024 * 1024 * 1024))


def _upload_size_limit_label() -> str:
    limit = _max_upload_file_bytes()
    gb = 1024 * 1024 * 1024
    if limit >= gb and limit % gb == 0:
        return f"{limit // gb}GB"
    mb = 1024 * 1024
    if limit >= mb and limit % mb == 0:
        return f"{limit // mb}MB"
    return f"{limit} 字节"


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


class LibrarySearchHit(BaseModel):
    """库内树搜索：名称/描述匹配的资料库（含子库）。"""

    id: int
    name: str
    description: Optional[str] = None

    class Config:
        from_attributes = True


class FileSearchResponse(BaseModel):
    files: List[FileRead]
    libraries: List[LibrarySearchHit]


class FileDirMoveTarget(BaseModel):
    """本资料库内可选的目标文件夹（path 为空表示根目录）。"""

    path: str = Field("", description="目标目录 path，空为根")
    label: str = Field("", description="展示用")


class FileMoveTargetLibrary(BaseModel):
    """跨资料库移动时，可选的目标资料库（一级/二级/三级，需当前用户可写）。"""

    library_id: int
    label: str


class FileMoveToLibraryBody(BaseModel):
    target_library_id: int = Field(..., description="目标资料库 ID")
    target_dir_path: str = Field(
        "",
        description="目标资料库内的父目录路径，空字符串表示根目录",
    )


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
    library_breadcrumb: Optional[str] = None  # 一级至当前资料库：如「A / B / C」
    username: Optional[str] = None  # 删除人（若无则回退为文件创建人/库拥有者）
    path: Optional[str] = None
    is_dir: Optional[bool] = None
    deleted_at: datetime
    can_restore: bool = True
    can_delete: bool = True


class GlobalTrashPage(BaseModel):
    items: List[GlobalTrashItem]
    has_more: bool
    limit: int
    offset: int


def _prefetch_library_ancestors_map(db: Session, seed_ids: set[int]) -> dict[int, Library]:
    """自给定资料库 id 起，沿 parent_id 拉齐所有祖先行，用于拼一级/二级/三级名称链。"""
    by_id: dict[int, Library] = {}
    frontier = {int(i) for i in seed_ids if i is not None}
    safety = 0
    while frontier and safety < 200:
        safety += 1
        missing = frontier - set(by_id.keys())
        if not missing:
            break
        rows = db.query(Library).filter(Library.id.in_(missing)).all()
        next_front: set[int] = set()
        for lib in rows:
            by_id[lib.id] = lib
            pid = getattr(lib, "parent_id", None)
            if pid is not None:
                next_front.add(int(pid))
        frontier = next_front
    return by_id


def _library_breadcrumb_from_map(lib_id: int | None, by_id: dict[int, Library]) -> Optional[str]:
    if lib_id is None:
        return None
    names: list[str] = []
    cur_id: int | None = int(lib_id)
    seen: set[int] = set()
    for _ in range(64):
        if cur_id is None or cur_id in seen:
            break
        seen.add(cur_id)
        lib = by_id.get(cur_id)
        if lib is None:
            names.append(f"库#{cur_id}")
            break
        names.append((getattr(lib, "name", None) or "").strip() or f"库#{lib.id}")
        pid = getattr(lib, "parent_id", None)
        cur_id = int(pid) if pid is not None else None
    if not names:
        return None
    names.reverse()
    return " / ".join(names)


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


def _can_manage_personal_trash_library(
    lib: Library | None,
    user: User,
    dept_leader_map: dict[int, Optional[int]],
) -> bool:
    """个人回收站：能否对该库相关条目执行恢复/彻底删除（私人库≈拥有者；部门库≈负责人）。"""
    if lib is None:
        return False
    if user.is_superuser:
        return True
    if getattr(lib, "department_id", None) is None:
        return lib.owner_id == user.id
    leader_id = dept_leader_map.get(int(lib.department_id))
    return leader_id is not None and leader_id == user.id


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
            create_notification_if_enabled(
                db,
                setting_key="file_share",
                user_id=user.id,
                type="file_share_to_me",
                title=title,
                message=msg,
            )
    except Exception:
        logger.warning("通知发送失败，不影响主流程", exc_info=True)

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

    # 安全兜底：禁止上传可执行/脚本类文件（前端也会拦截，但后端必须再校验一次，避免绕过）
    blocked_ext = {
        ".exe",
        ".bat",
        ".cmd",
        ".com",
        ".msi",
        ".dll",
        ".scr",
        ".ps1",
        ".vbs",
        ".js",
        ".jar",
        ".sh",
    }
    ext = ""
    try:
        filename = getattr(file, "filename", None) or ""
        if isinstance(filename, str) and "." in filename:
            ext = "." + filename.rsplit(".", 1)[-1].lower()
    except Exception:
        ext = ""
    if ext in blocked_ext:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持上传此文件类型：{ext}",
        )

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

    max_file_size_bytes = _max_upload_file_bytes()
    size_limit_label = _upload_size_limit_label()

    size = 0
    async with aiofiles.open(dest_path, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > max_file_size_bytes:
                try:
                    dest_path.unlink()
                    dest_dir.rmdir()
                except OSError:
                    pass
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"单个文件大小不能超过 {size_limit_label}",
                )
            await f.write(chunk)

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

    # 通知：库拥有者知晓有新文件/新版本（上传者本人不重复提醒）
    try:
        if next_version_no == 1:
            notif_type = "file_upload"
            title = "文件已上传"
            msg_for_owner = (
                f"用户「{current_user.username or current_user.email}」在文件库「{lib.name}」中上传了新文件："
                f"{relative_path}"
            )
        else:
            notif_type = "file_new_version"
            title = "文件有新版本"
            msg_for_owner = (
                f"用户「{current_user.username or current_user.email}」在文件库「{lib.name}」中上传了文件「{relative_path}」"
                f"的新版本（第 {next_version_no} 个版本）"
            )

        if lib.owner_id and lib.owner_id != current_user.id:
            create_notification_if_enabled(
                db,
                setting_key="file_upload",
                user_id=lib.owner_id,
                type=notif_type,
                title=title,
                message=msg_for_owner,
            )
    except Exception:
        logger.warning("通知发送失败，不影响主流程", exc_info=True)

    db.commit()
    db.refresh(entry)

    if dest_path.suffix.lower() in _OFFICE_EXTS:
        _lo_executor.submit(_preconvert_office, dest_path)

    return entry


def _is_library_owner(db: Session, library_id: int, user: User) -> bool:
    lib = db.query(Library).filter(Library.id == library_id).first()
    return lib and lib.owner_id == user.id


@router.get("/list", response_model=List[FileRead])
def list_files(
    library_id: int,
    path_prefix: Optional[str] = Query(None, description="目录前缀，如 docs/ 只列出 docs/ 下的文件"),
    include_dirs: bool = Query(True, description="是否包含目录"),
    limit: int = Query(50, ge=1, le=500, description="每页数量"),
    offset: int = Query(0, ge=0, description="起始偏移量"),
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
    entries = entries[offset: offset + limit]

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
    bulk_can_dl = can_download_in_library_list_context(db, lib, current_user)
    result = []
    for e in entries:
        can_dl = bulk_can_dl if not e.is_dir else None
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


def _file_move_target_new_path(target_dir: str, source_entry: FileEntry) -> str:
    raw = (source_entry.path or "").strip("/").replace("\\", "/")
    parts = [p for p in raw.split("/") if p]
    if not parts:
        return ""
    name = parts[-1]
    t = (target_dir or "").strip("/").replace("\\", "/")
    if not t:
        return name
    return f"{t}/{name}"


def _library_move_folder_paths(db: Session, library_id: int) -> set[str]:
    """本库内可作为移动目标的文件夹路径集合。

    除显式 mkdir 的目录行外，还从任意条目的 path 解析父级前缀（例如上传 ``a/b/c.pdf``
    时往往没有 ``a``、``a/b`` 的 is_dir 行，列表仍按路径分层展示，移动目标也应包含这些路径）。
    """
    out: set[str] = set()
    rows = (
        db.query(FileEntry.path, FileEntry.is_dir)
        .filter(
            FileEntry.library_id == library_id,
            FileEntry.deleted_at.is_(None),
        )
        .limit(50000)
        .all()
    )
    for path_str, is_dir in rows:
        p = (path_str or "").strip("/").replace("\\", "/")
        if not p:
            continue
        parts = [x for x in p.split("/") if x]
        if not parts:
            continue
        if is_dir:
            for i in range(1, len(parts) + 1):
                out.add("/".join(parts[:i]))
        else:
            for i in range(1, len(parts)):
                out.add("/".join(parts[:i]))
    return out


@router.get("/dir-move-targets", response_model=List[FileDirMoveTarget])
def list_file_dir_move_targets(
    library_id: int = Query(..., description="资料库 ID"),
    exclude_entry_id: Optional[int] = Query(None, description="要移动的条目 id，用于排除自身、子树及无效目标"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """列出本库内可选目标文件夹（含根），与 PATCH /files/{id}/rename 组合实现「移动」。"""
    _get_library_and_check(db, library_id, current_user, require_write=True)

    ex: FileEntry | None = None
    exclude_prefix: str | None = None
    if exclude_entry_id is not None:
        ex = (
            db.query(FileEntry)
            .filter(
                FileEntry.id == exclude_entry_id,
                FileEntry.library_id == library_id,
                FileEntry.deleted_at.is_(None),
            )
            .first()
        )
        if not ex:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="条目不存在")
        sp = (ex.path or "").strip("/").replace("\\", "/")
        if ex.is_dir and sp:
            exclude_prefix = sp + "/"

    folder_paths = _library_move_folder_paths(db, library_id)

    candidates: list[FileDirMoveTarget] = []
    cur_norm = ((ex.path or "").strip("/").replace("\\", "/")) if ex else ""

    root_new = _file_move_target_new_path("", ex) if ex else ""
    if not ex or root_new != cur_norm:
        candidates.append(FileDirMoveTarget(path="", label="根目录"))

    for p in sorted(folder_paths):
        if not p:
            continue
        if ex and ex.is_dir and cur_norm and p == cur_norm:
            continue
        if exclude_prefix and (p == exclude_prefix.rstrip("/") or p.startswith(exclude_prefix)):
            continue
        if ex:
            np = _file_move_target_new_path(p, ex)
            if np == cur_norm:
                continue
        candidates.append(FileDirMoveTarget(path=p, label=p + "/"))

    return candidates


def _normalize_rel_file_path(p: str | None) -> str:
    return (p or "").strip("/").replace("\\", "/")


def _breadcrumb_label_for_file_move(db: Session, lib: Library, max_parts: int = 4) -> str:
    """与资料库「移动」弹窗类似的层级展示（一级 / 二级 / 三级）。"""
    parts: list[str] = []
    cur: Library | None = lib
    hops = 0
    while cur is not None and hops < max_parts + 16:
        hops += 1
        parts.append((cur.name or "").strip() or f"#{cur.id}")
        if cur.parent_id is None:
            break
        cur = db.query(Library).filter(Library.id == cur.parent_id).first()
    chain = list(reversed(parts))
    if len(chain) > max_parts:
        chain = chain[-max_parts:]
        return "… / " + " / ".join(chain)
    return " / ".join(chain)


def _file_move_lib_scope_kind(lib: Library) -> str:
    """与移动资料库一致：部门库 / 个人库 / 公开库，跨库移动不得跨类。"""
    if getattr(lib, "department_id", None) is not None:
        return "department"
    vis = str(getattr(lib, "visibility", "private") or "private").lower()
    if vis == "public":
        return "public"
    return "personal"


def _same_department_for_file_move(mov_root: Library, cand_root: Library) -> bool:
    if _file_move_lib_scope_kind(mov_root) != "department":
        return True
    a = getattr(mov_root, "department_id", None)
    b = getattr(cand_root, "department_id", None)
    if a is None or b is None:
        return False
    return int(a) == int(b)


def _rename_file_entry_core(
    db: Session,
    entry: FileEntry,
    new_path_norm: str,
    current_user: User,
    request: Request | None,
) -> None:
    """同库内修改 path（含目录子树）。new_path_norm 已规范化；与当前路径相同则直接返回。不 commit。"""
    np = _normalize_rel_file_path(new_path_norm)
    if not np:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="路径不能为空")
    if np == _normalize_rel_file_path(entry.path):
        return
    existing = (
        db.query(FileEntry)
        .filter(
            FileEntry.library_id == entry.library_id,
            FileEntry.path == np,
            FileEntry.deleted_at.is_(None),
            FileEntry.id != entry.id,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该路径已存在")
    old_path = entry.path
    if entry.is_dir:
        prefix = old_path.rstrip("/") + "/"
        new_prefix = np.rstrip("/") + "/"
        children = (
            db.query(FileEntry)
            .filter(
                FileEntry.library_id == entry.library_id,
                FileEntry.path.startswith(prefix),
                FileEntry.deleted_at.is_(None),
            )
            .all()
        )
        entry.path = np
        for c in children:
            c.path = new_prefix + c.path[len(prefix) :]
    else:
        entry.path = np
    log_audit(
        db,
        current_user.id,
        current_user.username,
        "rename",
        "file",
        entry.id,
        f"{old_path} -> {np}",
        ip_address=get_client_ip(request),
    )


@router.get("/move-target-libraries", response_model=List[FileMoveTargetLibrary])
def list_file_move_target_libraries(
    source_library_id: int = Query(..., description="当前条目所在资料库 ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """列出可将文件/目录移动到的目标资料库（需可写，且与源库同类：个人/部门/公开；部门库限同部门）。"""
    src_row = db.query(Library).filter(Library.id == source_library_id).first()
    if not src_row or getattr(src_row, "deleted_at", None) is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="资料库不存在")
    _get_library_and_check(db, source_library_id, current_user, require_write=True)
    src_root = resolve_root_library(db, src_row)
    src_kind = _file_move_lib_scope_kind(src_root)

    targets: list[FileMoveTargetLibrary] = []
    base_q = libraries_accessible_base_query(db, current_user)
    for cand in base_q.order_by(Library.id.asc()).all():
        cand_root = resolve_root_library(db, cand)
        if _file_move_lib_scope_kind(cand_root) != src_kind:
            continue
        if not _same_department_for_file_move(src_root, cand_root):
            continue
        try:
            _, iw = has_library_access(db, cand.id, current_user, require_write=True)
        except HTTPException:
            continue
        if not iw:
            continue
        targets.append(
            FileMoveTargetLibrary(
                library_id=int(cand.id),
                label=_breadcrumb_label_for_file_move(db, cand),
            )
        )
    targets.sort(key=lambda t: (t.label or "").lower())
    return targets


@router.post("/{entry_id}/move-to-library", response_model=FileRead)
def move_file_to_library(
    entry_id: int,
    body: FileMoveToLibraryBody,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """将文件或目录（含子树）移动到其他资料库内的指定文件夹；同库时退化为路径重命名。"""
    entry: FileEntry | None = (
        db.query(FileEntry).filter(FileEntry.id == entry_id, FileEntry.deleted_at.is_(None)).first()
    )
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件或目录不存在")

    old_lib_id = int(entry.library_id)
    tgt_lib_id = int(body.target_library_id)

    _get_library_and_check(db, old_lib_id, current_user, require_write=True)
    tgt_lib_row = db.query(Library).filter(Library.id == tgt_lib_id).first()
    if not tgt_lib_row or getattr(tgt_lib_row, "deleted_at", None) is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="目标资料库不存在")
    _get_library_and_check(db, tgt_lib_id, current_user, require_write=True)

    src_lib_row = db.query(Library).filter(Library.id == old_lib_id).first()
    if not src_lib_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="资料库不存在")
    src_root = resolve_root_library(db, src_lib_row)
    tgt_root = resolve_root_library(db, tgt_lib_row)
    if _file_move_lib_scope_kind(src_root) != _file_move_lib_scope_kind(tgt_root):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只能在同类资料库之间移动：部门库↔部门库，个人库↔个人库，公开库↔公开库",
        )
    if not _same_department_for_file_move(src_root, tgt_root):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="部门资料库仅可在本部门内的资料库之间移动",
        )

    td = _normalize_rel_file_path(body.target_dir_path)
    entry_path_norm = _normalize_rel_file_path(entry.path)
    parts = [x for x in entry_path_norm.split("/") if x]
    if not parts:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无效路径")
    name = parts[-1]
    new_root_path = f"{td}/{name}" if td else name

    if tgt_lib_id == old_lib_id:
        _rename_file_entry_core(db, entry, new_root_path, current_user, request)
        db.commit()
        db.refresh(entry)
        return entry

    orig_root_path = entry.path
    old_prefix: str | None = None
    if entry.is_dir and (orig_root_path or "").strip():
        old_prefix = orig_root_path.rstrip("/") + "/"
    subtree: list[FileEntry] = [entry]
    if entry.is_dir and old_prefix:
        subtree.extend(
            db.query(FileEntry)
            .filter(
                FileEntry.library_id == old_lib_id,
                FileEntry.deleted_at.is_(None),
                FileEntry.path.startswith(old_prefix),
            )
            .all()
        )
    moved_ids = [e.id for e in subtree]

    moves: list[tuple[FileEntry, str]] = []
    for e in subtree:
        if e.id == entry.id:
            np = new_root_path
        else:
            if not old_prefix:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="内部错误：目录前缀",
                )
            np = new_root_path.rstrip("/") + "/" + e.path[len(old_prefix) :]
        moves.append((e, np))

    for _e, np in moves:
        hit = (
            db.query(FileEntry)
            .filter(
                FileEntry.library_id == tgt_lib_id,
                FileEntry.path == np,
                FileEntry.deleted_at.is_(None),
                not_(FileEntry.id.in_(moved_ids)),
            )
            .first()
        )
        if hit:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"目标资料库中已存在路径：{np}",
            )

    storage_root = _ensure_storage_root()
    disk_moves: list[tuple[Path, Path]] = []
    try:
        for e, _np in moves:
            if e.is_dir:
                continue
            old_base = storage_root / str(old_lib_id) / str(e.id)
            new_base = storage_root / str(tgt_lib_id) / str(e.id)
            if old_base.exists():
                if new_base.exists():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="目标资料库存储目录冲突，无法完成移动",
                    )
                new_base.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(old_base), str(new_base))
                disk_moves.append((old_base, new_base))
                op = str(old_base)
                npr = str(new_base)
                for v in db.query(FileVersion).filter(FileVersion.file_entry_id == e.id).all():
                    sp = v.storage_path or ""
                    if sp.startswith(op):
                        v.storage_path = npr + sp[len(op) :]
                    else:
                        v.storage_path = str(new_base / str(v.version_no) / Path(sp).name)

        for e, np in moves:
            e.library_id = tgt_lib_id
            e.path = np

        log_audit(
            db,
            current_user.id,
            current_user.username,
            "file_move_library",
            "file",
            entry.id,
            f"library {old_lib_id}->{tgt_lib_id} root_path={new_root_path}",
            ip_address=get_client_ip(request),
        )
        db.commit()
    except HTTPException:
        db.rollback()
        for old_b, new_b in reversed(disk_moves):
            try:
                if new_b.exists() and not old_b.exists():
                    old_b.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(new_b), str(old_b))
            except OSError:
                logger.warning("回滚跨库文件存储移动失败", exc_info=True)
        raise
    except Exception:
        db.rollback()
        for old_b, new_b in reversed(disk_moves):
            try:
                if new_b.exists() and not old_b.exists():
                    old_b.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(new_b), str(old_b))
            except OSError:
                logger.warning("回滚跨库文件存储移动失败", exc_info=True)
        raise

    db.refresh(entry)
    return entry


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

    np = _normalize_rel_file_path(new_path)
    if not np:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="路径不能为空")
    if np == _normalize_rel_file_path(entry.path):
        db.refresh(entry)
        return entry

    _rename_file_entry_core(db, entry, np, current_user, request)
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

    version_rows = (
        db.query(FileVersionTrash)
        .filter(FileVersionTrash.library_id.in_(lib_ids))
        .order_by(FileVersionTrash.deleted_at.desc())
        .all()
        if lib_ids
        else []
    )

    _dept_trash_seed: set[int] = set()
    for lib in deleted_libs:
        _dept_trash_seed.add(lib.id)
    for e in entries:
        _dept_trash_seed.add(e.library_id)
    for r in version_rows:
        _dept_trash_seed.add(r.library_id)
    dept_lib_tree = _prefetch_library_ancestors_map(db, _dept_trash_seed)

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
                library_breadcrumb=_library_breadcrumb_from_map(lib.id, dept_lib_tree),
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
                library_breadcrumb=_library_breadcrumb_from_map(e.library_id, dept_lib_tree),
                path=e.path,
                is_dir=e.is_dir,
                deleted_at=e.deleted_at,
                username=username,
                can_restore=True,
                can_delete=True,
            )
        )

    # 3) 活跃部门库中的“已删历史版本”
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
                library_breadcrumb=_library_breadcrumb_from_map(r.library_id, dept_lib_tree),
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


@router.get("/global-trash", response_model=GlobalTrashPage)
def list_global_trash(
    limit: int = Query(50, ge=1, le=500, description="每页数量"),
    offset: int = Query(0, ge=0, description="起始偏移量"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """全局回收站：统一流分页（文件/库/历史版本）"""
    if not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅系统管理员可查看全局回收站")
    # 统一三类记录为同一数据流后分页
    file_stmt = (
        select(
            literal("file", type_=String).label("type"),
            cast(FileEntry.id, String).label("id"),
            literal(None, type_=String).label("entry_id"),
            literal(None, type_=String).label("version_no"),
            FileEntry.library_id.label("library_id"),
            FileEntry.path.label("path"),
            FileEntry.is_dir.label("is_dir"),
            FileEntry.deleted_at.label("deleted_at"),
            FileEntry.created_by_id.label("actor_user_id"),
        )
        .where(FileEntry.deleted_at.is_not(None))
    )
    library_stmt = (
        select(
            literal("library", type_=String).label("type"),
            cast(Library.id, String).label("id"),
            literal(None, type_=String).label("entry_id"),
            literal(None, type_=String).label("version_no"),
            Library.id.label("library_id"),
            Library.name.label("path"),
            literal(True, type_=Boolean).label("is_dir"),
            Library.deleted_at.label("deleted_at"),
            Library.owner_id.label("actor_user_id"),
        )
        .where(Library.deleted_at.is_not(None))
    )
    version_stmt = (
        select(
            literal("file_version", type_=String).label("type"),
            cast(FileVersionTrash.id, String).label("id"),
            cast(FileVersionTrash.file_entry_id, String).label("entry_id"),
            cast(FileVersionTrash.version_no, String).label("version_no"),
            FileVersionTrash.library_id.label("library_id"),
            literal(None, type_=String).label("path"),
            literal(False, type_=Boolean).label("is_dir"),
            FileVersionTrash.deleted_at.label("deleted_at"),
            FileVersionTrash.deleted_by_id.label("actor_user_id"),
        )
        .where(FileVersionTrash.deleted_at.is_not(None))
    )
    unified = union_all(file_stmt, library_stmt, version_stmt).subquery("global_trash_stream")

    page_stmt = (
        select(unified)
        .order_by(
            unified.c.deleted_at.desc(),
            unified.c.type.asc(),
            unified.c.id.desc(),
        )
        .offset(offset)
        .limit(limit + 1)
    )
    rows = db.execute(page_stmt).all()
    has_more = len(rows) > limit
    rows = rows[:limit]

    if not rows:
        return GlobalTrashPage(items=[], has_more=False, limit=limit, offset=offset)

    mappings = [r._mapping for r in rows]
    lib_ids = {int(m["library_id"]) for m in mappings if m.get("library_id") is not None}
    entry_ids = {int(m["entry_id"]) for m in mappings if m.get("entry_id") is not None}

    lib_tree = _prefetch_library_ancestors_map(db, set(lib_ids)) if lib_ids else {}
    lib_name_map: dict[int, str] = {lid: ((lib.name or "") if lib else "") for lid, lib in lib_tree.items()}
    lib_owner_map: dict[int, Optional[int]] = {
        lid: lib.owner_id for lid, lib in lib_tree.items() if lib is not None
    }

    entries = db.query(FileEntry).filter(FileEntry.id.in_(entry_ids)).all() if entry_ids else []
    entry_map: dict[int, FileEntry] = {e.id: e for e in entries}

    user_ids: set[int] = set()
    for m in mappings:
        actor_id = m.get("actor_user_id")
        if actor_id:
            user_ids.add(int(actor_id))
        lib_id = m.get("library_id")
        if lib_id:
            owner_id = lib_owner_map.get(int(lib_id))
            if owner_id:
                user_ids.add(int(owner_id))
    users = db.query(User).filter(User.id.in_(user_ids)).all() if user_ids else []
    user_name_map: dict[int, str] = {u.id: (u.username or u.email or f"用户{u.id}") for u in users}

    items: list[GlobalTrashItem] = []
    for m in mappings:
        item_type = str(m["type"])
        item_id = int(m["id"])
        lib_id = int(m["library_id"]) if m.get("library_id") is not None else None
        actor_id = int(m["actor_user_id"]) if m.get("actor_user_id") is not None else None
        username: Optional[str] = user_name_map.get(actor_id) if actor_id else None
        if not username and lib_id:
            owner_id = lib_owner_map.get(lib_id)
            if owner_id:
                username = user_name_map.get(owner_id)

        if item_type == "file_version":
            entry_id = int(m["entry_id"]) if m.get("entry_id") is not None else None
            version_no = int(m["version_no"]) if m.get("version_no") is not None else None
            entry = entry_map.get(entry_id) if entry_id else None
            entry_path = entry.path if entry is not None else f"文件#{entry_id}"
            items.append(
                GlobalTrashItem(
                    id=item_id,
                    type="file_version",
                    entry_id=entry_id,
                    version_no=version_no,
                    library_id=lib_id,
                    library_name=lib_name_map.get(lib_id) if lib_id else None,
                    library_breadcrumb=_library_breadcrumb_from_map(lib_id, lib_tree),
                    path=f"{entry_path} (历史版本 v{version_no})" if version_no is not None else entry_path,
                    is_dir=False,
                    deleted_at=m["deleted_at"],
                    username=username,
                    can_restore=bool(entry and entry.deleted_at is None),
                    can_delete=True,
                )
            )
            continue

        if item_type == "library":
            lib_name = lib_name_map.get(lib_id) if lib_id else None
            items.append(
                GlobalTrashItem(
                    id=item_id,
                    type="library",
                    library_id=lib_id,
                    library_name=lib_name,
                    library_breadcrumb=_library_breadcrumb_from_map(lib_id, lib_tree),
                    path=lib_name or None,
                    is_dir=True,
                    deleted_at=m["deleted_at"],
                    username=username,
                    can_restore=True,
                    can_delete=True,
                )
            )
            continue

        # file
        items.append(
            GlobalTrashItem(
                id=item_id,
                type="file",
                library_id=lib_id,
                library_name=lib_name_map.get(lib_id) if lib_id else None,
                library_breadcrumb=_library_breadcrumb_from_map(lib_id, lib_tree),
                path=m["path"],
                is_dir=bool(m["is_dir"]),
                deleted_at=m["deleted_at"],
                username=username,
                can_restore=True,
                can_delete=True,
            )
        )

    return GlobalTrashPage(items=items, has_more=has_more, limit=limit, offset=offset)


@router.get("/my-trash", response_model=GlobalTrashPage)
def list_my_trash(
    limit: int = Query(50, ge=1, le=500, description="每页数量"),
    offset: int = Query(0, ge=0, description="起始偏移量"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    我的回收站视图（主页「回收站」），与全局回收站一致的统一流分页：
    - 库：当前用户拥有的所有已软删资料库
    - 文件：所在库仍存在时，由我创建的已删文件，或位于我拥有的库中的已删文件
    - 历史版本：所在库仍存在时，我拥有的库中的已删版本，或由我删除的版本
    """
    user_id = current_user.id

    file_stmt = (
        select(
            literal("file", type_=String).label("type"),
            cast(FileEntry.id, String).label("id"),
            literal(None, type_=String).label("entry_id"),
            literal(None, type_=String).label("version_no"),
            FileEntry.library_id.label("library_id"),
            FileEntry.path.label("path"),
            FileEntry.is_dir.label("is_dir"),
            FileEntry.deleted_at.label("deleted_at"),
            FileEntry.created_by_id.label("actor_user_id"),
        )
        .select_from(FileEntry)
        .join(Library, Library.id == FileEntry.library_id)
        .where(
            FileEntry.deleted_at.is_not(None),
            Library.deleted_at.is_(None),
            or_(Library.owner_id == user_id, FileEntry.created_by_id == user_id),
        )
    )
    library_stmt = (
        select(
            literal("library", type_=String).label("type"),
            cast(Library.id, String).label("id"),
            literal(None, type_=String).label("entry_id"),
            literal(None, type_=String).label("version_no"),
            Library.id.label("library_id"),
            Library.name.label("path"),
            literal(True, type_=Boolean).label("is_dir"),
            Library.deleted_at.label("deleted_at"),
            Library.owner_id.label("actor_user_id"),
        )
        .where(
            Library.deleted_at.is_not(None),
            Library.owner_id == user_id,
        )
    )
    version_stmt = (
        select(
            literal("file_version", type_=String).label("type"),
            cast(FileVersionTrash.id, String).label("id"),
            cast(FileVersionTrash.file_entry_id, String).label("entry_id"),
            cast(FileVersionTrash.version_no, String).label("version_no"),
            FileVersionTrash.library_id.label("library_id"),
            literal(None, type_=String).label("path"),
            literal(False, type_=Boolean).label("is_dir"),
            FileVersionTrash.deleted_at.label("deleted_at"),
            FileVersionTrash.deleted_by_id.label("actor_user_id"),
        )
        .select_from(FileVersionTrash)
        .join(Library, Library.id == FileVersionTrash.library_id)
        .where(
            Library.deleted_at.is_(None),
            FileVersionTrash.deleted_at.is_not(None),
            or_(Library.owner_id == user_id, FileVersionTrash.deleted_by_id == user_id),
        )
    )

    unified = union_all(file_stmt, library_stmt, version_stmt).subquery("my_trash_stream")

    page_stmt = (
        select(unified)
        .order_by(
            unified.c.deleted_at.desc(),
            unified.c.type.asc(),
            unified.c.id.desc(),
        )
        .offset(offset)
        .limit(limit + 1)
    )
    rows = db.execute(page_stmt).all()
    has_more = len(rows) > limit
    rows = rows[:limit]

    if not rows:
        return GlobalTrashPage(items=[], has_more=False, limit=limit, offset=offset)

    mappings = [r._mapping for r in rows]
    lib_ids = {int(m["library_id"]) for m in mappings if m.get("library_id") is not None}
    entry_ids = {int(m["entry_id"]) for m in mappings if m.get("entry_id") is not None}

    lib_tree = _prefetch_library_ancestors_map(db, set(lib_ids)) if lib_ids else {}
    lib_name_map: dict[int, str] = {lid: ((lib.name or "") if lib else "") for lid, lib in lib_tree.items()}
    lib_by_id: dict[int, Library] = lib_tree
    lib_owner_map: dict[int, Optional[int]] = {
        lid: lib.owner_id for lid, lib in lib_tree.items() if lib is not None
    }

    dept_raw_ids = set()
    for lid in lib_ids:
        lib = lib_tree.get(lid)
        did = getattr(lib, "department_id", None) if lib else None
        if did is not None:
            dept_raw_ids.add(int(did))
    depts = (
        db.query(Department).filter(Department.id.in_(dept_raw_ids)).all() if dept_raw_ids else []
    )
    dept_leader_map: dict[int, Optional[int]] = {
        int(d.id): getattr(d, "leader_user_id", None) for d in depts
    }

    entries = db.query(FileEntry).filter(FileEntry.id.in_(entry_ids)).all() if entry_ids else []
    entry_map: dict[int, FileEntry] = {e.id: e for e in entries}

    user_ids: set[int] = set()
    for m in mappings:
        actor_id = m.get("actor_user_id")
        if actor_id:
            user_ids.add(int(actor_id))
        lib_id_raw = m.get("library_id")
        if lib_id_raw:
            owner_id = lib_owner_map.get(int(lib_id_raw))
            if owner_id:
                user_ids.add(int(owner_id))
    users = db.query(User).filter(User.id.in_(user_ids)).all() if user_ids else []
    user_name_map: dict[int, str] = {
        u.id: (u.username or u.email or f"用户{u.id}") for u in users
    }

    items: list[GlobalTrashItem] = []
    for m in mappings:
        item_type = str(m["type"])
        item_id = int(m["id"])
        lib_id = int(m["library_id"]) if m.get("library_id") is not None else None
        actor_id = int(m["actor_user_id"]) if m.get("actor_user_id") is not None else None
        username: Optional[str] = user_name_map.get(actor_id) if actor_id else None
        if not username and lib_id:
            owner_id = lib_owner_map.get(lib_id)
            if owner_id:
                username = user_name_map.get(owner_id)

        lib_row = lib_by_id.get(lib_id) if lib_id is not None else None
        can_manage_lib = _can_manage_personal_trash_library(lib_row, current_user, dept_leader_map)

        crumb = _library_breadcrumb_from_map(lib_id, lib_tree)

        if item_type == "file_version":
            entry_id = int(m["entry_id"]) if m.get("entry_id") is not None else None
            version_no = int(m["version_no"]) if m.get("version_no") is not None else None
            entry = entry_map.get(entry_id) if entry_id else None
            entry_path = entry.path if entry is not None else f"文件#{entry_id}"
            items.append(
                GlobalTrashItem(
                    id=item_id,
                    type="file_version",
                    entry_id=entry_id,
                    version_no=version_no,
                    library_id=lib_id,
                    library_name=lib_name_map.get(lib_id) if lib_id else None,
                    library_breadcrumb=crumb,
                    path=(
                        f"{entry_path} (历史版本 v{version_no})" if version_no is not None else entry_path
                    ),
                    is_dir=False,
                    deleted_at=m["deleted_at"],
                    username=username,
                    can_restore=can_manage_lib and bool(entry and entry.deleted_at is None),
                    can_delete=can_manage_lib,
                )
            )
            continue

        if item_type == "library":
            lib_name = lib_name_map.get(lib_id) if lib_id else None
            items.append(
                GlobalTrashItem(
                    id=item_id,
                    type="library",
                    library_id=lib_id,
                    library_name=lib_name,
                    library_breadcrumb=crumb,
                    path=lib_name or None,
                    is_dir=True,
                    deleted_at=m["deleted_at"],
                    username=username,
                    can_restore=can_manage_lib,
                    can_delete=can_manage_lib,
                )
            )
            continue

        items.append(
            GlobalTrashItem(
                id=item_id,
                type="file",
                library_id=lib_id,
                library_name=lib_name_map.get(lib_id) if lib_id else None,
                library_breadcrumb=crumb,
                path=m["path"],
                is_dir=bool(m["is_dir"]),
                deleted_at=m["deleted_at"],
                username=username,
                can_restore=can_manage_lib,
                can_delete=can_manage_lib,
            )
        )

    return GlobalTrashPage(items=items, has_more=has_more, limit=limit, offset=offset)


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


@router.get("/search", response_model=FileSearchResponse)
def search_files(
    library_id: int,
    keyword: str = Query(..., min_length=1, description="搜索关键词，匹配路径中的文件名或资料库名称/描述"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """在当前资料库「整棵树」内搜索：子资料库中的文件、名称匹配的下级资料库。

    子资料库拥有独立 storage（不同 library_id），此前仅搜当前 id 会漏掉子库文件。
    """
    lib = _get_library_and_check(db, library_id, current_user)
    kw = keyword.strip()
    if not kw:
        return FileSearchResponse(files=[], libraries=[])
    subtree_ids, _ = collect_descendant_library_ids(db, library_id)
    accessible = set(int(x) for x in get_accessible_library_ids(db, current_user))
    scope_ids = [i for i in subtree_ids if i in accessible]
    if not scope_ids:
        return FileSearchResponse(files=[], libraries=[])
    like = f"%{kw}%"
    lib_hits = (
        db.query(Library)
        .filter(
            Library.id.in_(scope_ids),
            Library.deleted_at.is_(None),
            or_(Library.name.ilike(like), Library.description.ilike(like)),
        )
        .order_by(Library.name.asc())
        .limit(50)
        .all()
    )
    libraries_out = [
        LibrarySearchHit(
            id=int(row.id),
            name=(row.name or "") or "",
            description=row.description,
        )
        for row in lib_hits
    ]
    entries = (
        db.query(FileEntry)
        .filter(
            FileEntry.library_id.in_(scope_ids),
            FileEntry.deleted_at.is_(None),
            FileEntry.path.ilike(like),
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
    entry_lib_ids = {int(e.library_id) for e in entries}
    lib_by_id: dict[int, Library] = {}
    if entry_lib_ids:
        for row in db.query(Library).filter(Library.id.in_(entry_lib_ids)).all():
            lib_by_id[int(row.id)] = row
    result_files: List[FileRead] = []
    for e in entries:
        lib_for_entry = lib_by_id.get(int(e.library_id), lib)
        can_dl = (
            can_download_in_library_list_context(db, lib_for_entry, current_user)
            if not e.is_dir
            else None
        )
        result_files.append(
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
    return FileSearchResponse(files=result_files, libraries=libraries_out)


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

    unique_entry_lib_ids = list({e.library_id for e in entries})
    lib_rows = db.query(Library).filter(Library.id.in_(unique_entry_lib_ids)).all()
    lib_by_id = {L.id: L for L in lib_rows}
    can_dl_by_lib: dict[int, bool] = {
        lid: can_download_in_library_list_context(db, lib_by_id[lid], current_user)
        for lid in unique_entry_lib_ids
        if lid in lib_by_id
    }

    result: list[GlobalSearchFileRead] = []
    for e in entries:
        can_dl = (
            can_dl_by_lib.get(e.library_id, False) if not e.is_dir else None
        )
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


SYSTEM_DEFAULT_TOTAL_QUOTA_BYTES = int(
    getattr(settings, "STORAGE_SYSTEM_TOTAL_BYTES", 2 * 1024 * 1024 * 1024 * 1024)
)
DEPT_RESERVED_RATIO = float(getattr(settings, "STORAGE_DEPT_RESERVED_RATIO", 0.20))
DEPT_BASE_QUOTA_BYTES = int(getattr(settings, "STORAGE_DEPT_BASE_QUOTA_BYTES", 120 * 1024 * 1024 * 1024))
DEPT_WARNING_PCT = float(getattr(settings, "STORAGE_DEPT_WARNING_PCT", 85.0))
DEPT_CRITICAL_PCT = float(getattr(settings, "STORAGE_DEPT_CRITICAL_PCT", 95.0))


class StorageStats(BaseModel):
    used_bytes: int
    used_display: str
    total_bytes: int = SYSTEM_DEFAULT_TOTAL_QUOTA_BYTES
    total_display: str = "0 B"
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
    total_bytes: int | None = None
    total_display: str = "未设置"
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
    # 个人视角总容量：优先使用当前用户的个人配额；未配置时回退到系统默认总配额
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

    # 默认部门配额策略（仅在部门未设置自定义配额时生效）：
    # 1) 从系统总配额中按比例预留缓冲池；
    # 2) 给每个部门发放基础配额；
    # 3) 剩余配额按部门人数占比分配。
    rows_out: list[DepartmentStorageRow] = []
    dept_ids = list(depts.keys())
    dept_count = len(dept_ids)
    safe_reserved_ratio = min(max(DEPT_RESERVED_RATIO, 0.0), 0.9)
    distributable_total = int(SYSTEM_DEFAULT_TOTAL_QUOTA_BYTES * (1.0 - safe_reserved_ratio))
    base_total = DEPT_BASE_QUOTA_BYTES * dept_count
    floating_pool = max(distributable_total - base_total, 0)
    total_users = sum(dept_user_counts.get(did, 0) for did in dept_ids)

    for dept_id, dept in depts.items():
        used = dept_used.get(dept_id, 0)
        users = dept_user_counts.get(dept_id, 0)
        if dept.storage_quota_bytes:
            quota_bytes = int(dept.storage_quota_bytes)
        else:
            if total_users > 0:
                floating_part = int(floating_pool * (users / total_users))
            else:
                floating_part = int(floating_pool / dept_count) if dept_count > 0 else 0
            quota_bytes = DEPT_BASE_QUOTA_BYTES + floating_part

        file_cnt = dept_file_count.get(dept_id, 0)
        pct = (used / quota_bytes * 100) if quota_bytes > 0 else 0.0
        if pct >= DEPT_CRITICAL_PCT:
            status_str = "critical"
        elif pct >= DEPT_WARNING_PCT:
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
    # 展示所有用户（即使未上传文件，也需要在用户存储列表可见）
    for uid, u in users.items():
        used = int(user_used.get(uid, 0))
        quota_bytes = int(u.storage_quota_bytes) if u.storage_quota_bytes else None
        dept_name = None
        if u.department_id is not None:
            d = dept_map.get(u.department_id)
            if d:
                dept_name = d.name
        pct = (used / quota_bytes * 100) if quota_bytes and quota_bytes > 0 else 0.0
        rows_out.append(
            UserStorageRow(
                id=uid,
                name=u.username or u.email or f"用户{uid}",
                department_name=dept_name,
                used_bytes=used,
                used_display=_format_bytes(used),
                total_bytes=quota_bytes,
                total_display=_format_bytes(quota_bytes) if quota_bytes else "未设置",
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
    background_tasks: BackgroundTasks,
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

    # 审计日志在响应发出后异步写入，不阻塞文件处理
    _entry_path = entry.path
    _version_no = version.version_no
    _user_id = current_user.id
    _username = current_user.username
    _ip = get_client_ip(request)
    _entry_id = entry.id

    def _write_audit() -> None:
        try:
            log_audit(db, _user_id, _username, "下载文件", "file", _entry_id,
                      f"path={_entry_path} version={_version_no}", ip_address=_ip)
            db.commit()
        except Exception:
            pass

    background_tasks.add_task(_write_audit)

    # 下载文件名优先使用业务路径中的文件名，确保与前端显示名称一致
    filename = Path(entry.path).name or storage_path.name

    # 凡通过本接口下载：支持水印的类型一律叠当前用户标识（全角色一致，含超管/库主/高管等）
    wm = _watermark_text(current_user)
    ptype = _download_media_kind(filename, storage_path)
    if ptype == "pdf":
        try:
            out_pdf = _apply_vector_watermark_to_pdf(storage_path, wm)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"无法为该 PDF 生成带水印副本：{exc}",
            ) from exc
        h = {**_content_disposition_attachment(filename), **_no_cache_download_headers()}
        h["X-KP-Download-Processed"] = "watermarked-pdf-vector"
        return Response(content=out_pdf, media_type="application/pdf", headers=h)
    if ptype == "image":
        raw = storage_path.read_bytes()
        out_bytes, _ct = _apply_watermark_to_image(
            raw, wm, max_side=2200, quality=88, for_download=True
        )
        stem = Path(filename).stem or "file"
        dl_name = f"{stem}.jpg"
        h = {**_content_disposition_attachment(dl_name), **_no_cache_download_headers()}
        h["X-KP-Download-Processed"] = "watermarked-image"
        return Response(content=out_bytes, media_type="image/jpeg", headers=h)
    if ptype == "text":
        try:
            txt = storage_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            txt = storage_path.read_text(encoding="latin-1", errors="replace")
        sep = "=" * 56
        banner = (
            f"{sep}\n"
            f"【平台下载水印】操作人：{wm}\n"
            f"本文件为可追溯副本，正文见下方。\n"
            f"{sep}\n\n"
        )
        body = (banner + txt).encode("utf-8")
        h = {**_content_disposition_attachment(filename), **_no_cache_download_headers()}
        h["X-KP-Download-Processed"] = "watermarked-text"
        return Response(content=body, media_type="text/plain; charset=utf-8", headers=h)

    h_raw = {**_no_cache_download_headers(), "X-KP-Download-Processed": "original-bytes"}
    return FileResponse(
        path=str(storage_path),
        filename=filename,
        media_type="application/octet-stream",
        headers=h_raw,
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


_OFFICE_EXTS: frozenset[str] = frozenset({".ppt", ".pptx", ".doc", ".docx", ".xls", ".xlsx"})
_lo_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="lo_convert")


def _preconvert_office(path: Path) -> None:
    try:
        _office_to_pdf(path)
    except Exception:
        logger.warning("后台预转换失败 path=%s", path, exc_info=True)


def _preview_type_by_filename(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf" or ext in _OFFICE_EXTS:
        return "pdf"
    if ext in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}:
        return "image"
    if ext in {".txt", ".md", ".json", ".xml", ".html", ".htm", ".css", ".js", ".yaml", ".yml"}:
        return "text"
    return "unsupported"


@lru_cache(maxsize=1)
def _find_libreoffice_bin() -> str:
    """Return path to LibreOffice binary, trying common locations."""
    import shutil
    candidates = [
        "libreoffice",
        "soffice",
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
        "/usr/bin/libreoffice",
        "/usr/bin/soffice",
        "C:\\Program Files\\LibreOffice\\program\\soffice.exe",
    ]
    for c in candidates:
        if shutil.which(c) or Path(c).is_file():
            return c
    raise RuntimeError(
        "未找到 LibreOffice，无法预览 Office 文件。"
        "请安装 LibreOffice：macOS 执行 brew install --cask libreoffice"
    )


def _office_to_pdf(src: Path) -> Path:
    """Convert Office file to PDF via LibreOffice, caching by mtime."""
    import subprocess

    lo_bin = _find_libreoffice_bin()
    cache_dir = src.parent / ".lo_cache"
    cache_dir.mkdir(exist_ok=True)
    mtime = int(src.stat().st_mtime * 1000)
    pdf_path = cache_dir / f"{src.stem}_{mtime}.pdf"
    if pdf_path.is_file():
        return pdf_path
    # Remove stale cache entries for this stem
    for old in cache_dir.glob(f"{src.stem}_*.pdf"):
        try:
            old.unlink()
        except OSError:
            pass
    import shutil as _shutil
    xvfb = _shutil.which("xvfb-run")
    cmd = []
    if xvfb:
        cmd += [xvfb, "--auto-servernum", "--server-args=-screen 0 1024x768x24"]
    cmd += [
        lo_bin,
        "--headless",
        "--norestore",
        "--nofirststartwizard",
        "--convert-to", "pdf",
        "--outdir", str(cache_dir),
        str(src),
    ]
    lo_home = Path("/tmp/lo_home")
    lo_home.mkdir(exist_ok=True)
    result = subprocess.run(
        cmd,
        capture_output=True,
        timeout=120,
        env={**os.environ, "HOME": str(lo_home)},
    )
    if result.returncode != 0:
        raise RuntimeError(f"LibreOffice 转换失败: {result.stderr.decode(errors='replace')[:200]}")
    converted = cache_dir / f"{src.stem}.pdf"
    if converted.is_file():
        converted.rename(pdf_path)
    if not pdf_path.is_file():
        raise RuntimeError("LibreOffice 未生成输出文件")
    return pdf_path


def _resolve_preview_path(storage_path: Path) -> Path:
    """Return PDF path for Office files (converting if needed), or original path."""
    if storage_path.suffix.lower() in _OFFICE_EXTS:
        return _office_to_pdf(storage_path)
    return storage_path


# 水印字体候选（PIL / PyMuPDF 共用）
_WATERMARK_FONT_PATHS: tuple[str, ...] = (
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "NotoSansCJK-Regular.ttc",
    "Arial Unicode.ttf",
    "DejaVuSans.ttf",
    "Arial.ttf",
)


@lru_cache(maxsize=1)
def _find_cjk_font_path() -> str | None:
    """找到第一个可用的 CJK 字体文件路径，结果缓存避免重复遍历。"""
    for fp in _WATERMARK_FONT_PATHS:
        try:
            if Path(fp).is_file():
                return fp
        except Exception:
            pass
    return None


def _build_watermark_xobject_doc(wm: str, w: float, h: float) -> "fitz.Document":
    """
    将水印内容（平铺文字）渲染到一个临时单页 PDF。
    供 show_pdf_page 作为 Form XObject 嵌入，水印数据在最终 PDF 中只存储一次。
    """
    import fitz

    font_path = _find_cjk_font_path()
    wm_doc = fitz.open()
    wm_p = wm_doc.new_page(width=w, height=h)
    step_x = max(160, len(wm) * 9 + 60)
    step_y = 100
    for row, y in enumerate(range(0, int(h) + step_y, step_y)):
        x_offset = (step_x // 2) if row % 2 else 0
        for x in range(-step_x + x_offset, int(w) + step_x, step_x):
            kw: dict = {"fontsize": 12, "color": (0.68, 0.68, 0.68), "rotate": 30, "overlay": True}
            if font_path:
                kw["fontfile"] = font_path
                kw["fontname"] = "wm"
            try:
                wm_p.insert_text(fitz.Point(x, y), wm, **kw)
            except Exception:
                pass
    return wm_doc


def _apply_vector_watermark_to_pdf(pdf_path: Path, wm: str) -> bytes:
    """
    用 Form XObject 把水印嵌入 PDF：水印内容只生成一次，每页仅存一个引用。
    相比逐页 insert_text，100 页 PDF 的处理时间从 O(N) 降到接近 O(1)。
    结果缓存到磁盘，同一用户重复下载直接读缓存。
    """
    import fitz

    cache_path = _dl_cache_path(pdf_path, wm, variant="vec")
    if cache_path.is_file():
        return cache_path.read_bytes()

    font_path = _find_cjk_font_path()
    doc = fitz.open(str(pdf_path))
    # 按页面尺寸分组，同尺寸页共用同一份水印 XObject
    wm_docs: dict[tuple[int, int], "fitz.Document"] = {}
    try:
        for page in doc:
            w, h = page.rect.width, page.rect.height
            key = (round(w), round(h))
            if key not in wm_docs:
                wm_docs[key] = _build_watermark_xobject_doc(wm, w, h)

            # show_pdf_page 将水印页作为 Form XObject 引用，不复制内容
            page.show_pdf_page(page.rect, wm_docs[key], 0, overlay=True)

            # 底部标识条（每页独立，内容轻量）
            bar_h = max(20.0, h * 0.032)
            page.draw_rect(fitz.Rect(0, h - bar_h, w, h), color=None, fill=(0.96, 0.96, 0.97), width=0)
            bar_kw: dict = {"fontsize": min(10.0, bar_h * 0.55), "color": (0.35, 0.35, 0.38), "overlay": True}
            if font_path:
                bar_kw["fontfile"] = font_path
                bar_kw["fontname"] = "wm"
            try:
                page.insert_text(fitz.Point(10, h - bar_h * 0.28), f"下载水印 {wm}", **bar_kw)
            except Exception:
                pass

        # garbage=2 已足够清理新增引用，比 garbage=4 快很多
        result = doc.tobytes(deflate=True, garbage=2)
    finally:
        doc.close()
        for d in wm_docs.values():
            d.close()

    try:
        cache_path.write_bytes(result)
    except OSError:
        pass

    return result


def _content_disposition_attachment(filename: str) -> dict[str, str]:
    """
    同时提供 filename（ASCII 兜底）与 filename*（UTF-8），兼容各浏览器与前端解析。
    """
    quoted = quote(filename, safe="")
    ext = Path(filename).suffix
    ascii_base = filename.encode("ascii", "ignore").decode("ascii").strip()
    if not ascii_base or ascii_base in {".", ext}:
        ascii_base = "download"
    ascii_name = ascii_base if ascii_base.endswith(ext) else f"{ascii_base}{ext}"
    cd = f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quoted}"
    return {"Content-Disposition": cd}


def _no_cache_download_headers() -> dict[str, str]:
    """避免反向代理或浏览器把未水印原文件缓存后反复命中。"""
    return {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
    }


def _bytes_looks_like_pdf(head: bytes) -> bool:
    """兼容 BOM、前导空白、线性化 PDF 等，避免误判成二进制原样下载。"""
    if not head:
        return False
    chunk = head[:8192]
    if chunk.lstrip(b"\xef\xbb\xbf\x00\t\n\r ").startswith(b"%PDF-"):
        return True
    # 部分生成器在 %PDF 前有少量二进制或空白
    return b"%PDF-1." in chunk or b"%PDF-2." in chunk


def _watermark_text(user: User) -> str:
    """
    受控预览与下载水印文本（全角色统一）。

    口径：优先展示用户账户姓名（username）；无角色例外。
    """
    if getattr(user, "username", None):
        return str(user.username)
    # 兜底：用户名缺失时退回邮箱
    if getattr(user, "email", None):
        return str(user.email)
    return f"user-{user.id}"


@lru_cache(maxsize=16)
def _load_watermark_font(size: int):
    """返回与字号匹配的 ImageFont，保证中文可用。结果按字号缓存，避免重复遍历字体路径。"""
    from PIL import ImageFont

    for fp in _WATERMARK_FONT_PATHS:
        try:
            return ImageFont.truetype(fp, size)
        except Exception:
            continue
    try:
        return ImageFont.load_default()
    except Exception:
        return None


def _apply_watermark_to_image(
    img_bytes: bytes,
    wm: str,
    *,
    max_side: int = 1600,
    quality: int = 75,
    text_alpha: int = 75,
    for_download: bool = False,
) -> tuple[bytes, str]:
    """
    将图片加水印并（可选）降清晰，返回 (out_bytes, content_type)。
    for_download=True：斜纹比预览略清晰但仍保持低密度、低不透明度，以免遮挡正文；底部保留窄条标识。
    """
    from io import BytesIO

    from PIL import Image, ImageDraw

    im = Image.open(BytesIO(img_bytes)).convert("RGBA")
    w, h = im.size
    scale = min(1.0, max_side / max(w, h)) if max(w, h) > 0 else 1.0
    if scale < 1.0:
        im = im.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)

    short_side = min(im.size[0], im.size[1])
    if for_download:
        # 略大于预览字号，但远低于「铺满」强度；透明度与预览同量级，保证可读正文
        tile_font_size = max(13, int(short_side * 0.022))
        alpha = max(38, min(72, int(text_alpha)))
        text_color = (40, 40, 40, alpha)
        stroke_fill = (255, 255, 255, max(30, alpha - 8))
        stroke_width = 1
        out_quality = max(quality, 90)
    else:
        tile_font_size = max(12, int(short_side * 0.018))
        alpha = max(40, min(200, int(text_alpha)))
        text_color = (0, 0, 0, alpha)
        stroke_fill = None
        stroke_width = 0
        out_quality = quality

    font = _load_watermark_font(tile_font_size)
    if font is None:
        from PIL import ImageFont as _IF

        try:
            font = _IF.load_default()
        except Exception:
            font = None

    overlay = Image.new("RGBA", im.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)

    try:
        bbox = draw.textbbox((0, 0), wm, font=font)
        tw = max(1, bbox[2] - bbox[0])
        th = max(1, bbox[3] - bbox[1])
    except Exception:
        tw, th = 220, 18

    if for_download:
        # 拉大间距，减少「糊成一片」
        step_x = max(220, int(tw * 2.15))
        step_y = max(170, int(th * 3.4))
    else:
        step_x = max(180, int(tw * 1.6))
        step_y = max(140, int(th * 4.0))

    for y in range(-im.size[1], im.size[1] * 2, step_y):
        for x in range(-im.size[0], im.size[0] * 2, step_x):
            # 下载模式仅单层铺点，不再交错半格加密；预览仍交错增强覆盖感
            offsets = ((0, 0),) if for_download else ((0, 0), (step_x // 2, step_y // 2))
            for ox, oy in offsets:
                tx, ty = x + ox, y + oy
                kw: dict = {"font": font, "fill": text_color}
                if stroke_width and stroke_fill is not None:
                    kw["stroke_width"] = stroke_width
                    kw["stroke_fill"] = stroke_fill
                try:
                    draw.text((tx, ty), wm, **kw)
                except Exception:
                    draw.text((tx, ty), wm, fill=text_color, font=font)

    overlay = overlay.rotate(30, expand=False)
    out = Image.alpha_composite(im, overlay).convert("RGB")

    if for_download and im.size[1] > 64:
        d3 = ImageDraw.Draw(out)
        bar_h = max(28, min(52, int(im.size[1] * 0.038)))
        footer_fs = max(11, min(18, bar_h - 10))
        footer_font = _load_watermark_font(footer_fs) or font
        line = f"下载水印 {wm}"
        d3.rectangle(
            [0, im.size[1] - bar_h, im.size[0], im.size[1]],
            fill=(245, 245, 246),
        )
        try:
            d3.text(
                (10, im.size[1] - bar_h + (bar_h - footer_fs) // 2 - 1),
                line,
                fill=(90, 90, 95),
                font=footer_font,
            )
        except Exception:
            pass

    buf = BytesIO()
    out.save(buf, format="JPEG", quality=out_quality, optimize=True)
    return buf.getvalue(), "image/jpeg"


@lru_cache(maxsize=512)
def _get_pdf_page_count(pdf_path_str: str) -> int:
    """获取 PDF 总页数，结果按路径缓存（同版本文件路径不变，页数不变）。"""
    import fitz

    doc = fitz.open(pdf_path_str)
    try:
        return doc.page_count
    finally:
        doc.close()


@lru_cache(maxsize=256)
def _render_pdf_page_raw(pdf_path_str: str, page: int) -> bytes:
    """栅格化 PDF 单页为 PNG，结果与用户无关，缓存后多用户查看同页只渲染一次。"""
    import fitz

    doc = fitz.open(pdf_path_str)
    try:
        p = doc.load_page(page - 1)
        mat = fitz.Matrix(2.0, 2.0)
        pix = p.get_pixmap(matrix=mat, alpha=False)
        return pix.tobytes("png")
    finally:
        doc.close()


def _render_pdf_page_with_watermark(pdf_path: Path, page: int, wm: str) -> tuple[bytes, str, int]:
    """
    将 PDF 指定页渲染为图片（JPEG），并叠加水印。
    返回 (out_bytes, content_type, page_count)。
    栅格化结果缓存复用，每次只重新叠加用户水印。
    """
    pdf_path_str = str(pdf_path)
    page_count = _get_pdf_page_count(pdf_path_str)
    if page < 1 or page > page_count:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="页码超出范围")
    img_bytes = _render_pdf_page_raw(pdf_path_str, page)
    out_bytes, ct = _apply_watermark_to_image(img_bytes, wm, max_side=1600, quality=75)
    return out_bytes, ct, page_count


def _download_media_kind(filename: str, storage_path: Path) -> str:
    """
    以文件内容魔数为准再回退扩展名，避免：
    - 无后缀 / 错后缀的 PDF 被当成 octet-stream 直接下发原文件；
    - UTF-8 BOM 等导致 %PDF 不在首字节而无法识别。
    """
    try:
        head = storage_path.read_bytes()[:8192]
    except Exception:
        head = b""

    if _bytes_looks_like_pdf(head):
        return "pdf"
    if head.startswith(b"\xff\xd8\xff"):
        return "image"
    if len(head) >= 8 and head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image"
    if head.startswith(b"GIF87a") or head.startswith(b"GIF89a"):
        return "image"
    if head.startswith(b"BM"):
        return "image"
    if len(head) >= 12 and head.startswith(b"RIFF") and head[8:12] == b"WEBP":
        return "image"

    return _preview_type_by_filename(filename)


def _stamp_vector_download_footer_on_pdf(doc, wm: str) -> None:
    """
    在每页最上层叠窄条矢量标识（浅底深灰字），与 JPEG 内嵌条一致，不抢正文。
    """
    import fitz
    from pathlib import Path

    label = f"下载水印 {wm}"
    fontfile = None
    for fp in _WATERMARK_FONT_PATHS:
        try:
            if Path(fp).is_file():
                fontfile = fp
                break
        except Exception:
            continue
    for page in doc:
        rect = page.rect
        h = float(rect.height)
        w = float(rect.width)
        if h < 36 or w < 36:
            continue
        bar_h = max(28.0, h * 0.038)
        bar = fitz.Rect(0, h - bar_h, w, h)
        page.draw_rect(bar, color=None, fill=(0.96, 0.96, 0.97), width=0)
        fs = max(10.0, min(16.0, bar_h * 0.48))
        ty = h - max(12.0, bar_h * 0.35)
        tx = 10.0
        kw: dict = {"fontsize": fs, "color": (0.35, 0.35, 0.38)}
        if fontfile:
            kw["fontfile"] = fontfile
        try:
            page.insert_text((tx, ty), label, **kw)
        except Exception:
            try:
                page.insert_text((tx, ty), f"KP-DL {wm}", fontsize=fs, color=(0.35, 0.35, 0.38))
            except Exception:
                pass


def _dl_cache_path(storage_path: Path, wm: str, variant: str = "vec") -> Path:
    """下载水印 PDF 的磁盘缓存路径，按文件路径 + 修改时间 + 水印文字 + 水印变体索引。
    文件被新版本替换后 mtime 变化，缓存自动失效。"""
    try:
        mtime = int(storage_path.stat().st_mtime)
    except OSError:
        mtime = 0
    h = hashlib.sha1(f"{storage_path}:{wm}:{mtime}:{variant}".encode()).hexdigest()[:20]
    cache_dir = _ensure_storage_root() / ".dl_cache"
    cache_dir.mkdir(exist_ok=True)
    return cache_dir / f"{h}.pdf"


def _pdf_page_watermarked_single_pdf_bytes(pdf_path_str: str, page_index: int, wm: str) -> bytes:
    """单页加水印并转为单页 PDF。复用 _render_pdf_page_raw 已缓存的栅格，避免重复 fitz.open + 渲染。"""
    import fitz

    # page_index 是 0-based，_render_pdf_page_raw 接受 1-based page
    png = _render_pdf_page_raw(pdf_path_str, page_index + 1)
    out_jpg, _ = _apply_watermark_to_image(
        png, wm, max_side=2000, quality=85, for_download=True
    )
    jdoc = fitz.open(stream=out_jpg, filetype="jpeg")
    try:
        return jdoc.convert_to_pdf()
    finally:
        jdoc.close()


def _apply_watermark_to_full_pdf(pdf_path: Path, wm: str) -> bytes:
    """
    逐页栅格化后走 PIL 斜纹水印 + 底栏，再拼回 PDF。
    结果缓存到磁盘：同一用户对同版本文件的重复下载直接读缓存，无需重新处理。
    """
    import fitz

    cache_path = _dl_cache_path(pdf_path, wm)
    if cache_path.is_file():
        return cache_path.read_bytes()

    path_str = str(pdf_path)
    n = _get_pdf_page_count(path_str)
    if n < 1:
        src = fitz.open(path_str)
        try:
            return src.tobytes(deflate=True, garbage=4)
        finally:
            src.close()

    if n == 1:
        page_pdfs = [_pdf_page_watermarked_single_pdf_bytes(path_str, 0, wm)]
    else:
        workers = min(max(2, (os.cpu_count() or 4) // 2), n, 6)
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = [
                ex.submit(_pdf_page_watermarked_single_pdf_bytes, path_str, i, wm) for i in range(n)
            ]
            page_pdfs = [f.result() for f in futures]

    dst = fitz.open()
    try:
        for jpdf in page_pdfs:
            jone = fitz.open(stream=jpdf, filetype="pdf")
            try:
                dst.insert_pdf(jone)
            finally:
                jone.close()
        _stamp_vector_download_footer_on_pdf(dst, wm)
        result = dst.tobytes(deflate=True, garbage=4)
    finally:
        dst.close()

    try:
        cache_path.write_bytes(result)
    except OSError:
        pass

    return result


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
            pdf_path = _resolve_preview_path(storage_path)
            page_count = _get_pdf_page_count(str(pdf_path))
        except Exception:
            logger.warning("Office->PDF 转换失败 path=%s", storage_path, exc_info=True)
            ptype = "unsupported"
            page_count = 1

    # 一次「打开预览」记一条审计，避免按页拉取 blob 时刷爆日志
    try:
        detail = f"path={entry.path} version={version.version_no} type={ptype}"
        if ptype == "pdf":
            detail += f" page_count={page_count}"
        elif ptype == "image":
            detail += " preview=image"
        elif ptype == "text":
            detail += " preview=text"
        else:
            detail += " preview=unsupported"
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
    # 水印结果含用户信息，不可共享缓存；60 秒内浏览器可复用自己的缓存（翻回同一页无需重新请求）
    _cache_headers = {"Cache-Control": "private, max-age=60, no-transform"}

    if ptype == "pdf":
        try:
            pdf_path = _resolve_preview_path(storage_path)
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"文件转换失败：{e}")
        out_bytes, ct, _page_count = _render_pdf_page_with_watermark(pdf_path, page, wm)
        response = Response(content=out_bytes, media_type=ct, headers=_cache_headers)
    elif ptype == "image":
        raw = storage_path.read_bytes()
        out_bytes, ct = _apply_watermark_to_image(raw, wm, max_side=1600, quality=75)
        response = Response(content=out_bytes, media_type=ct, headers=_cache_headers)
    elif ptype == "text":
        MAX_CHARS = 200_000
        try:
            txt = storage_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            txt = storage_path.read_text(encoding="latin-1", errors="replace")
        if len(txt) > MAX_CHARS:
            txt = txt[:MAX_CHARS] + "\n\n...(内容过长，已截断)...\n"
        response = Response(content=txt, media_type="text/plain; charset=utf-8", headers=_cache_headers)
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该文件类型暂不支持受控预览")

    return response



