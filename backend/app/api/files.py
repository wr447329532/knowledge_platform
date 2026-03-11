from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Literal, Optional

from fastapi import APIRouter, Body, Depends, File, HTTPException, UploadFile, Query, status
from fastapi.responses import FileResponse
from jose import JWTError, jwt
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.core.audit import log_audit
from backend.app.core.config import get_settings
from backend.app.core.library_access import can_download_file, can_access_file, get_accessible_library_ids, has_library_access
from backend.app.api.notifications import create_notification
from backend.app.db.session import get_db
from backend.app.models.department import Department
from backend.app.models.file import FileEntry, FileVersion
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


class FileTrashRead(FileRead):
    deleted_at: datetime


class FileVersionRead(BaseModel):
    id: int
    version_no: int
    size: int
    uploaded_at: datetime

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


@router.post("/upload", response_model=FileRead)
async def upload_file(
    library_id: int,
    relative_path: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lib = _get_library_and_check(db, library_id, current_user, require_write=True)

    # 规范化相对路径，例如 docs/readme.md
    relative_path = relative_path.lstrip("/").replace("\\", "/")
    if not relative_path:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="路径不能为空")

    # 查找或创建 FileEntry（含回收站内同路径的，找到则恢复并追加版本）
    entry: FileEntry | None = (
        db.query(FileEntry)
        .filter(FileEntry.library_id == library_id, FileEntry.path == relative_path)
        .first()
    )
    if entry and entry.deleted_at:
        entry.deleted_at = None  # 从回收站恢复
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

    size = 0
    with open(dest_path, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            f.write(chunk)

    version = FileVersion(
        file_entry_id=entry.id,
        version_no=next_version_no,
        storage_path=str(dest_path),
        size=size,
        uploaded_by_id=current_user.id,
    )
    db.add(version)
    log_audit(db, current_user.id, current_user.username, "upload", "file", entry.id, f"library_id={library_id} path={relative_path}")
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
    log_audit(db, current_user.id, current_user.username, "mkdir", "file", entry.id, f"library_id={library_id} path={path}")
    db.commit()
    db.refresh(entry)
    return entry


@router.patch("/{entry_id}/rename", response_model=FileRead)
def rename_file(
    entry_id: int,
    new_path: str = Query(..., description="新路径，如 docs/readme.txt"),
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

    log_audit(db, current_user.id, current_user.username, "rename", "file", entry.id, f"{old_path} -> {new_path}")
    db.commit()
    db.refresh(entry)
    return entry


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_file(
    entry_id: int,
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
    log_audit(db, current_user.id, current_user.username, "delete", "file", entry.id, f"path={entry.path} -> recycle")
    db.commit()


@router.get("/trash", response_model=List[FileTrashRead])
def list_trash(
    library_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """列出回收站中的文件/目录，并清理超过保留期的记录。"""
    lib = _get_library_and_check(db, library_id, current_user)

    # 自动清理超过 30 天的回收站记录，避免无限占用存储
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=30)
    old_entries = (
        db.query(FileEntry)
        .filter(
            FileEntry.library_id == library_id,
            FileEntry.deleted_at != None,  # noqa: E711
            FileEntry.deleted_at < cutoff,
        )
        .all()
    )
    for e in old_entries:
        _permanent_delete_entry(db, e)
    if old_entries:
        db.commit()

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


@router.post("/{entry_id}/restore", response_model=FileRead)
def restore_file(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """从回收站恢复"""
    entry: FileEntry | None = db.query(FileEntry).filter(FileEntry.id == entry_id).first()
    if not entry or not entry.deleted_at:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="回收站中无此项")
    _get_library_and_check(db, entry.library_id, current_user, require_write=True)
    entry.deleted_at = None
    log_audit(db, current_user.id, current_user.username, "restore", "file", entry.id, f"path={entry.path}")
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
    db.delete(entry)


@router.delete("/trash/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def permanent_delete(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """从回收站彻底删除（不可恢复）；若为目录则递归删除其下所有已在回收站中的项"""
    entry: FileEntry | None = db.query(FileEntry).filter(FileEntry.id == entry_id).first()
    if not entry or not entry.deleted_at:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="回收站中无此项")
    _get_library_and_check(db, entry.library_id, current_user, require_write=True)
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
    log_audit(db, current_user.id, current_user.username, "permanent_delete", "file", entry_id, f"path={path_before_delete}")
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


class StorageStats(BaseModel):
    used_bytes: int
    used_display: str
    total_bytes: int = 500 * 1024 * 1024 * 1024  # 500GB 默认
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
    """获取存储空间使用量"""
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
    total = 500 * 1024 * 1024 * 1024
    pct = (used / total * 100) if total > 0 else 0

    def _fmt(b: int) -> str:
        if b < 1024:
            return f"{b} B"
        if b < 1024 * 1024:
            return f"{b / 1024:.1f} KB"
        if b < 1024 * 1024 * 1024:
            return f"{b / (1024 * 1024):.1f} MB"
        return f"{b / (1024 * 1024 * 1024):.1f} GB"

    return StorageStats(
        used_bytes=used,
        used_display=_fmt(used),
        total_bytes=total,
        total_display="500 GB",
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

    # 文件级别统计
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

    # 最新版本的文件（不含目录）
    latest_rows = _iter_latest_files(db)
    file_count = len(latest_rows)
    total_file_size = sum(int(r[3] or 0) for r in latest_rows)

    # 目录数量（不计入大小）
    dir_count = (
        db.query(FileEntry)
        .join(Library, Library.id == FileEntry.library_id)
        .filter(
            FileEntry.is_dir.is_(True),
            FileEntry.deleted_at.is_(None),
            Library.deleted_at.is_(None),
        )
        .count()
    )

    total_count = (file_count + dir_count) or 1
    total_size = total_file_size or 1

    rows_out: list[FileTypeStat] = []

    # 文件
    rows_out.append(
        FileTypeStat(
            type="文件",
            count=file_count,
            size_bytes=total_file_size,
            size_display=_format_bytes(total_file_size),
            percent_count=round(file_count / total_count * 100, 1),
            percent_size=round(total_file_size / total_size * 100, 1),
        )
    )

    # 文件夹（目录）：只统计数量，大小为 0
    rows_out.append(
        FileTypeStat(
            type="文件夹",
            count=dir_count,
            size_bytes=0,
            size_display=_format_bytes(0),
            percent_count=round(dir_count / total_count * 100, 1),
            percent_size=0.0,
        )
    )

    # 仍按大小占用降序（文件在前，文件夹在后）
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
    return versions


@router.get("/download")
def download_file(
    entry_id: int,
    version_no: Optional[int] = Query(None, description="指定版本号，不填则下载最新版本"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    entry: FileEntry | None = db.query(FileEntry).filter(FileEntry.id == entry_id).first()
    if not entry or entry.is_dir or entry.deleted_at:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")
    if not can_download_file(db, entry, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无下载权限（需被分享且权限为「下载」）")

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

    log_audit(db, current_user.id, current_user.username, "下载文件", "file", entry.id, f"path={entry.path} version={version.version_no}")
    db.commit()

    filename = storage_path.name
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取预览用短期 token（用于 iframe/img 直接加载，无需 Authorization）"""
    entry: FileEntry | None = db.query(FileEntry).filter(FileEntry.id == entry_id).first()
    if not entry or entry.is_dir or entry.deleted_at:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")
    if not can_access_file(db, entry, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问")
    log_audit(db, current_user.id, current_user.username, "预览文件", "file", entry.id, f"path={entry.path}")
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """在线预览文件（需 Bearer 认证，用于 fetch 获取内容）"""
    entry: FileEntry | None = db.query(FileEntry).filter(FileEntry.id == entry_id).first()
    if not entry or entry.is_dir or entry.deleted_at:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")
    if not can_access_file(db, entry, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问")
    log_audit(db, current_user.id, current_user.username, "预览文件", "file", entry.id, f"path={entry.path}")
    db.commit()
    return _serve_preview_file(version_no, db, entry)



