import csv
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from backend.app.api.v1.learning import collect_notebook_items
from backend.app.db.dependencies import DatabaseSession
from backend.app.services.backup import (
    BackupValidationError,
    create_backup,
    stage_restore,
)

router = APIRouter(prefix="/data", tags=["本地数据"])
MAX_UPLOAD_BYTES = 2 * 1024 * 1024 * 1024


@router.get("/backup", response_model=None)
def download_backup(request: Request) -> FileResponse:
    backup = create_backup(request.app.state.paths)
    return FileResponse(
        backup,
        media_type="application/zip",
        filename=backup.name,
        background=BackgroundTask(backup.unlink, missing_ok=True),
    )


@router.post("/restore")
async def upload_restore(
    request: Request,
    file: Annotated[UploadFile, File()],
) -> dict[str, object]:
    suffix = Path(file.filename or "backup.zip").suffix.lower()
    if suffix != ".zip":
        await file.close()
        raise HTTPException(status_code=415, detail="请选择工作台导出的 ZIP 备份文件。")

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=request.app.state.paths.runtime, suffix=".upload", delete=False
        ) as temporary:
            temporary_path = Path(temporary.name)
            total = 0
            while chunk := await file.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="备份文件不能超过 2GB。")
                temporary.write(chunk)
        try:
            manifest = stage_restore(temporary_path, request.app.state.paths)
        except BackupValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        await file.close()
        if temporary_path:
            temporary_path.unlink(missing_ok=True)

    return {
        "accepted": True,
        "requires_restart": True,
        "message": "备份已验证。请停止并重新启动工作台以完成恢复；API Key 不会恢复。",
        "pending_file": manifest.name,
    }


@router.get("/export", response_model=None)
def export_notebook(
    request: Request,
    session: DatabaseSession,
    format: Literal["json", "csv"] = "json",
) -> FileResponse:
    items = collect_notebook_items(session)
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    suffix = ".json" if format == "json" else ".csv"
    with tempfile.NamedTemporaryFile(
        dir=request.app.state.paths.exports, suffix=suffix, delete=False
    ) as temporary:
        output = Path(temporary.name)

    if format == "json":
        payload = {
            "format": "ai-error-review-notebook-export",
            "format_version": 1,
            "created_at": datetime.now(UTC).isoformat(),
            "items": [item.model_dump(mode="json") for item in items],
        }
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        media_type = "application/json"
    else:
        with output.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(
                stream,
                extrasaction="ignore",
                fieldnames=[
                    "question_id",
                    "question",
                    "subject",
                    "grade",
                    "knowledge_points",
                    "difficulty",
                    "actual_error_reason",
                    "actual_error_note",
                    "mastery_status",
                    "starred",
                    "review_count",
                    "next_review_at",
                    "created_at",
                ],
            )
            writer.writeheader()
            for item in items:
                row = item.model_dump(mode="json")
                row["knowledge_points"] = "；".join(item.knowledge_points)
                row.pop("updated_at", None)
                writer.writerow(row)
        media_type = "text/csv"

    filename = f"ai-error-review-notebook-{timestamp}{suffix}"
    return FileResponse(
        output,
        media_type=media_type,
        filename=filename,
        background=BackgroundTask(output.unlink, missing_ok=True),
    )
