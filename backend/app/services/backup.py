import json
import os
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from backend.app.core.config import AppPaths

BACKUP_FORMAT = "ai-error-review-backup"
BACKUP_FORMAT_VERSION = 1
MAX_BACKUP_BYTES = 4 * 1024 * 1024 * 1024
MAX_BACKUP_FILES = 20_000
PENDING_RESTORE_NAME = "restore-pending.zip"


class BackupValidationError(ValueError):
    pass


def _database_revision(database: Path) -> str | None:
    connection = sqlite3.connect(database)
    try:
        row = connection.execute("SELECT version_num FROM alembic_version").fetchone()
        return str(row[0]) if row else None
    except sqlite3.DatabaseError:
        return None
    finally:
        connection.close()


def create_backup(paths: AppPaths) -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")
    destination = paths.exports / f"ai-error-review-backup-{timestamp}.zip"
    with tempfile.TemporaryDirectory(dir=paths.exports) as temporary_dir:
        snapshot = Path(temporary_dir) / "app.db"
        source = sqlite3.connect(paths.database)
        target = sqlite3.connect(snapshot)
        try:
            source.backup(target)
        finally:
            target.close()
            source.close()

        manifest = {
            "format": BACKUP_FORMAT,
            "format_version": BACKUP_FORMAT_VERSION,
            "created_at": datetime.now(UTC).isoformat(),
            "database_revision": _database_revision(snapshot),
            "includes_api_keys": False,
        }
        temporary_zip = destination.with_suffix(".zip.tmp")
        with zipfile.ZipFile(
            temporary_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
        ) as archive:
            archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
            archive.write(snapshot, "backup/app.db")
            for file in sorted(paths.uploads.rglob("*")):
                if not file.is_file() or file.is_symlink():
                    continue
                resolved = file.resolve()
                if not resolved.is_relative_to(paths.uploads):
                    continue
                relative = resolved.relative_to(paths.uploads).as_posix()
                archive.write(resolved, f"uploads/{relative}")
        temporary_zip.replace(destination)
    return destination


def validate_backup(path: Path) -> dict[str, object]:
    try:
        with zipfile.ZipFile(path) as archive:
            members = archive.infolist()
            if len(members) > MAX_BACKUP_FILES:
                raise BackupValidationError("备份文件包含的项目过多。")
            names: set[str] = set()
            total_size = 0
            for member in members:
                pure = PurePosixPath(member.filename)
                if pure.is_absolute() or ".." in pure.parts or "\\" in member.filename:
                    raise BackupValidationError("备份文件包含不安全路径。")
                if member.filename in names:
                    raise BackupValidationError("备份文件包含重复项目。")
                names.add(member.filename)
                allowed = member.filename in {"manifest.json", "backup/app.db"} or (
                    len(pure.parts) > 1 and pure.parts[0] == "uploads"
                )
                if not allowed:
                    raise BackupValidationError("备份文件包含未知项目。")
                mode = member.external_attr >> 16
                if mode and (mode & 0o170000) == 0o120000:
                    raise BackupValidationError("备份文件不能包含符号链接。")
                total_size += member.file_size
                if total_size > MAX_BACKUP_BYTES:
                    raise BackupValidationError("备份解压后的数据超过 4GB 限制。")
            if "manifest.json" not in names or "backup/app.db" not in names:
                raise BackupValidationError("备份缺少清单或数据库。")
            if archive.getinfo("manifest.json").file_size > 1024 * 1024:
                raise BackupValidationError("备份清单异常。")
            manifest = json.loads(archive.read("manifest.json"))
            if not isinstance(manifest, dict):
                raise BackupValidationError("备份清单格式无效。")
            if manifest.get("format") != BACKUP_FORMAT:
                raise BackupValidationError("这不是 AI 错题复盘工作台备份。")
            if manifest.get("format_version") != BACKUP_FORMAT_VERSION:
                raise BackupValidationError("暂不支持该备份版本。")
            if manifest.get("includes_api_keys") is not False:
                raise BackupValidationError("不接受包含 API Key 的备份。")
            if manifest.get("database_revision") not in {"0001", "0002"}:
                raise BackupValidationError("备份数据库版本无法恢复。")

            with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temporary:
                temporary_database = Path(temporary.name)
                with archive.open("backup/app.db") as source:
                    shutil.copyfileobj(source, temporary)
            try:
                connection = sqlite3.connect(temporary_database)
                try:
                    integrity = connection.execute("PRAGMA integrity_check").fetchone()
                    tables = {
                        row[0]
                        for row in connection.execute(
                            "SELECT name FROM sqlite_master WHERE type='table'"
                        ).fetchall()
                    }
                finally:
                    connection.close()
                required = {"questions", "provider_configs", "analysis_runs"}
                if integrity != ("ok",) or not required <= tables:
                    raise BackupValidationError("备份数据库损坏或缺少必要数据表。")
            finally:
                temporary_database.unlink(missing_ok=True)
            return manifest
    except (OSError, zipfile.BadZipFile, KeyError, json.JSONDecodeError) as exc:
        raise BackupValidationError("备份文件损坏或格式无效。") from exc


def stage_restore(uploaded: Path, paths: AppPaths) -> Path:
    validate_backup(uploaded)
    destination = paths.runtime / PENDING_RESTORE_NAME
    temporary = destination.with_suffix(".tmp")
    shutil.copyfile(uploaded, temporary)
    temporary.replace(destination)
    return destination


def apply_pending_restore(paths: AppPaths) -> bool:
    pending = paths.runtime / PENDING_RESTORE_NAME
    if not pending.is_file():
        return False
    applying = pending.with_name("restore-applying.zip")
    pending.replace(applying)
    try:
        validate_backup(applying)
        with tempfile.TemporaryDirectory(dir=paths.runtime) as temporary_dir:
            extracted = Path(temporary_dir)
            restored_uploads = extracted / "uploads"
            restored_uploads.mkdir()
            with zipfile.ZipFile(applying) as archive:
                with (
                    archive.open("backup/app.db") as source,
                    (extracted / "app.db").open("wb") as target,
                ):
                    shutil.copyfileobj(source, target)
                for member in archive.infolist():
                    pure = PurePosixPath(member.filename)
                    if len(pure.parts) <= 1 or pure.parts[0] != "uploads" or member.is_dir():
                        continue
                    destination = restored_uploads.joinpath(*pure.parts[1:])
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(member) as source, destination.open("wb") as target:
                        shutil.copyfileobj(source, target)

            restored_database = extracted / "app.db"
            connection = sqlite3.connect(restored_database)
            try:
                connection.execute(
                    """
                    UPDATE provider_configs
                    SET enabled = 0,
                        secret_ref = 'restore-missing-' || id,
                        last_test_status = NULL,
                        last_tested_at = NULL
                    """
                )
                connection.commit()
                connection.execute("PRAGMA integrity_check").fetchone()
            finally:
                connection.close()

            rollback = Path(tempfile.mkdtemp(dir=paths.runtime, prefix="restore-rollback-"))
            try:
                if paths.database.exists():
                    shutil.copy2(paths.database, rollback / "app.db")
                if paths.uploads.exists():
                    shutil.copytree(paths.uploads, rollback / "uploads")
                for suffix in ("-wal", "-shm"):
                    Path(f"{paths.database}{suffix}").unlink(missing_ok=True)
                os.replace(restored_database, paths.database)
                shutil.rmtree(paths.uploads, ignore_errors=True)
                os.replace(restored_uploads, paths.uploads)
            except Exception:
                if (rollback / "app.db").exists():
                    shutil.copy2(rollback / "app.db", paths.database)
                if (rollback / "uploads").exists():
                    shutil.rmtree(paths.uploads, ignore_errors=True)
                    shutil.copytree(rollback / "uploads", paths.uploads)
                raise
            finally:
                shutil.rmtree(rollback, ignore_errors=True)
        applying.unlink(missing_ok=True)
        return True
    except Exception:
        failed = paths.runtime / "restore-failed.zip"
        applying.replace(failed)
        return False
