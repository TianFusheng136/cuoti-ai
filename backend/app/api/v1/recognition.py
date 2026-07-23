import hashlib
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from backend.app.api.v1.operations import single_model_operation
from backend.app.db.dependencies import DatabaseSession
from backend.app.db.models import (
    ProviderConfig,
    Question,
    QuestionAsset,
    QuestionConfirmation,
    RecognitionRun,
)
from backend.app.providers.vision import RECOGNITION_PROMPT_VERSION, VisionProviderError
from backend.app.schemas.recognition import (
    ConfirmationCreate,
    ConfirmationResponse,
    RecognitionOutput,
    RecognitionRequest,
    RecognitionResponse,
)
from backend.app.security.secrets import SecretProtectionError

router = APIRouter(prefix="/questions", tags=["题目识别与确认"])


def get_question(session: DatabaseSession, question_id: str) -> Question:
    question = session.get(Question, question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="没有找到这道题目。")
    return question


def latest_recognition(
    session: DatabaseSession, question_id: str, *, succeeded_only: bool = True
) -> RecognitionRun | None:
    statement = select(RecognitionRun).where(RecognitionRun.question_id == question_id)
    if succeeded_only:
        statement = statement.where(RecognitionRun.status == "succeeded")
    return session.scalar(statement.order_by(RecognitionRun.created_at.desc()))


def recognition_response(run: RecognitionRun) -> RecognitionResponse:
    output = RecognitionOutput.model_validate(run.output_json)
    return RecognitionResponse(
        **output.model_dump(),
        id=run.id,
        provider_config_id=run.provider_config_id,
        model_name=run.model_name,
        prompt_version=run.prompt_version,
        status="succeeded",
        duration_ms=run.duration_ms or 0,
        created_at=run.created_at,
    )


def choose_vision_provider(session: DatabaseSession, provider_id: str | None) -> ProviderConfig:
    if provider_id:
        provider = session.get(ProviderConfig, provider_id)
    else:
        provider = session.scalar(
            select(ProviderConfig)
            .where(ProviderConfig.capability == "vision", ProviderConfig.enabled.is_(True))
            .order_by(ProviderConfig.created_at)
        )
    if provider is None or provider.capability != "vision" or not provider.enabled:
        raise HTTPException(
            status_code=409,
            detail="尚未配置可用的视觉模型，请先前往设置页面完成配置。",
        )
    return provider


@router.post("/{question_id}/recognize", response_model=RecognitionResponse)
@single_model_operation("recognition")
async def recognize_question(
    question_id: str,
    payload: RecognitionRequest,
    request: Request,
    session: DatabaseSession,
) -> RecognitionResponse:
    question = get_question(session, question_id)
    if question.input_type not in {"image", "clipboard"}:
        raise HTTPException(status_code=409, detail="文字输入的题目不需要图片识别。")

    asset = session.scalar(select(QuestionAsset).where(QuestionAsset.question_id == question_id))
    if asset is None:
        raise HTTPException(status_code=409, detail="题目没有可识别的原始图片。")

    provider = choose_vision_provider(session, payload.provider_id)
    run = RecognitionRun(
        question_id=question.id,
        provider_config_id=provider.id,
        model_name=provider.model_name,
        prompt_version=RECOGNITION_PROMPT_VERSION,
        status="running",
    )
    session.add(run)
    session.commit()
    session.refresh(run)

    image_path = (request.app.state.paths.data_dir / asset.relative_path).resolve()
    if not image_path.is_relative_to(request.app.state.paths.data_dir) or not image_path.is_file():
        run.status = "failed"
        run.error_code = "image_missing"
        run.completed_at = datetime.now(UTC)
        session.commit()
        raise HTTPException(status_code=404, detail="原始题目图片不存在。")

    try:
        api_key = request.app.state.secret_store.read(provider.secret_ref)
        vision_provider = request.app.state.vision_provider_factory.create(provider.provider_type)
        result = await vision_provider.recognize(
            config=provider,
            api_key=api_key,
            image_data=image_path.read_bytes(),
            mime_type=asset.mime_type,
        )
    except (OSError, UnicodeError, SecretProtectionError) as exc:
        run.status = "failed"
        run.error_code = "secret_unavailable"
        run.completed_at = datetime.now(UTC)
        session.commit()
        raise HTTPException(
            status_code=500, detail="无法读取视觉模型 API Key，请重新保存配置。"
        ) from exc
    except VisionProviderError as exc:
        run.status = "failed"
        run.error_code = exc.code
        run.completed_at = datetime.now(UTC)
        session.commit()
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    output = result.output
    if asset.width < 600 or asset.height < 250:
        warnings = [*output.warnings, "图片分辨率较低，请仔细核对识别文字。"]
        confidence = "medium" if output.confidence == "high" else output.confidence
        output = output.model_copy(update={"warnings": warnings, "confidence": confidence})

    run.status = "succeeded"
    run.recognized_text = output.recognized_text
    run.question_completeness = output.question_completeness
    run.confidence = output.confidence
    run.output_json = output.model_dump(mode="json")
    run.duration_ms = result.duration_ms
    run.completed_at = datetime.now(UTC)
    question.status = "recognition_review"
    session.commit()
    session.refresh(run)
    return recognition_response(run)


@router.get("/{question_id}/recognition", response_model=RecognitionResponse)
def read_latest_recognition(question_id: str, session: DatabaseSession) -> RecognitionResponse:
    get_question(session, question_id)
    run = latest_recognition(session, question_id)
    if run is None:
        raise HTTPException(status_code=404, detail="这道题目还没有成功的识别结果。")
    return recognition_response(run)


@router.post("/{question_id}/confirm", response_model=ConfirmationResponse)
def confirm_question(
    question_id: str,
    payload: ConfirmationCreate,
    session: DatabaseSession,
) -> QuestionConfirmation:
    question = get_question(session, question_id)
    run = latest_recognition(session, question_id)
    confirmed_text = payload.confirmed_text.strip()
    if not confirmed_text:
        raise HTTPException(status_code=422, detail="确认后的题目文字不能为空。")

    confirmation = session.scalar(
        select(QuestionConfirmation).where(QuestionConfirmation.question_id == question_id)
    )
    now = datetime.now(UTC)
    values = {
        "recognized_text_snapshot": run.recognized_text if run else question.source_text,
        "confirmed_text": confirmed_text,
        "confirmed_text_hash": hashlib.sha256(confirmed_text.encode("utf-8")).hexdigest(),
        "subject": payload.subject,
        "grade": payload.grade,
        "user_answer": payload.user_answer,
        "user_solution": payload.user_solution,
        "confirmed_at": now,
        "updated_at": now,
    }
    if confirmation is None:
        confirmation = QuestionConfirmation(question_id=question_id, **values)
        session.add(confirmation)
    else:
        for key, value in values.items():
            setattr(confirmation, key, value)
    question.status = "confirmed"
    session.commit()
    session.refresh(confirmation)
    return confirmation


@router.get("/{question_id}/confirmation", response_model=ConfirmationResponse)
def read_confirmation(question_id: str, session: DatabaseSession) -> QuestionConfirmation:
    get_question(session, question_id)
    confirmation = session.scalar(
        select(QuestionConfirmation).where(QuestionConfirmation.question_id == question_id)
    )
    if confirmation is None:
        raise HTTPException(status_code=404, detail="这道题目尚未完成确认。")
    return confirmation
