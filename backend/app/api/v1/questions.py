from dataclasses import asdict
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Request, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from backend.app.db.dependencies import DatabaseSession
from backend.app.db.models import Question, QuestionAsset
from backend.app.schemas.question import (
    AssetResponse,
    QuestionCreate,
    QuestionListResponse,
    QuestionResponse,
)
from backend.app.services.image_storage import ImageValidationError, store_question_image

router = APIRouter(prefix="/questions", tags=["题目"])


def get_question(session: DatabaseSession, question_id: str) -> Question:
    question = session.scalar(
        select(Question).where(Question.id == question_id).options(selectinload(Question.assets))
    )
    if question is None:
        raise HTTPException(status_code=404, detail="没有找到这道题目。")
    return question


@router.post("", response_model=QuestionResponse, status_code=status.HTTP_201_CREATED)
def create_question(payload: QuestionCreate, session: DatabaseSession) -> Question:
    question = Question(input_type=payload.input_type, source_text=payload.source_text)
    session.add(question)
    session.commit()
    session.refresh(question)
    return question


@router.get("", response_model=QuestionListResponse)
def list_questions(session: DatabaseSession) -> QuestionListResponse:
    questions = session.scalars(
        select(Question)
        .options(selectinload(Question.assets))
        .order_by(Question.created_at.desc(), Question.id.desc())
    ).all()
    total = session.scalar(select(func.count()).select_from(Question)) or 0
    return QuestionListResponse(items=list(questions), total=total)


@router.get("/{question_id}", response_model=QuestionResponse)
def read_question(question_id: str, session: DatabaseSession) -> Question:
    return get_question(session, question_id)


@router.post(
    "/{question_id}/image",
    response_model=AssetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_question_image(
    question_id: str,
    request: Request,
    session: DatabaseSession,
    file: Annotated[UploadFile, File()],
) -> QuestionAsset:
    question = get_question(session, question_id)
    if question.input_type not in {"image", "clipboard"}:
        raise HTTPException(status_code=409, detail="文字题目不能添加原始图片。")
    if question.assets:
        raise HTTPException(status_code=409, detail="这道题目已经有原始图片，请先删除后重试。")

    try:
        stored = await store_question_image(file, request.app.state.paths.uploads)
    except ImageValidationError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    finally:
        await file.close()

    asset = QuestionAsset(question_id=question.id, **asdict(stored))
    session.add(asset)
    try:
        session.commit()
    except Exception:
        session.rollback()
        (request.app.state.paths.data_dir / stored.relative_path).unlink(missing_ok=True)
        raise
    session.refresh(asset)
    return asset


@router.get("/{question_id}/image", response_model=None)
def read_question_image(
    question_id: str, request: Request, session: DatabaseSession
) -> FileResponse:
    question = get_question(session, question_id)
    if not question.assets:
        raise HTTPException(status_code=404, detail="这道题目没有原始图片。")

    asset = question.assets[0]
    data_root: Path = request.app.state.paths.data_dir
    image_path = (data_root / asset.relative_path).resolve()
    if not image_path.is_relative_to(data_root) or not image_path.is_file():
        raise HTTPException(status_code=404, detail="原始图片文件不存在。")
    return FileResponse(image_path, media_type=asset.mime_type)


@router.delete("/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_question(question_id: str, request: Request, session: DatabaseSession) -> Response:
    question = get_question(session, question_id)
    asset_paths = [asset.relative_path for asset in question.assets]
    session.delete(question)
    session.commit()

    data_root: Path = request.app.state.paths.data_dir
    for relative_path in asset_paths:
        candidate = (data_root / relative_path).resolve()
        if candidate.is_relative_to(data_root):
            candidate.unlink(missing_ok=True)

    return Response(status_code=status.HTTP_204_NO_CONTENT)
