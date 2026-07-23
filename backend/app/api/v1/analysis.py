import hashlib
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from backend.app.api.v1.operations import single_model_operation
from backend.app.db.dependencies import DatabaseSession
from backend.app.db.models import (
    AnalysisRun,
    ProviderConfig,
    Question,
    QuestionConfirmation,
    QuestionLearning,
)
from backend.app.providers.text import (
    ANALYSIS_PROMPT_VERSION,
    ANALYSIS_SCHEMA_VERSION,
    TextProviderError,
)
from backend.app.schemas.analysis import (
    AnalysisOutput,
    AnalysisRequest,
    AnalysisResponse,
    VerificationResult,
)
from backend.app.security.secrets import SecretProtectionError
from backend.app.verification import verify_simple_arithmetic

router = APIRouter(prefix="/questions", tags=["错题分析"])


def get_question(session: DatabaseSession, question_id: str) -> Question:
    question = session.get(Question, question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="没有找到这道题目。")
    return question


def get_valid_confirmation(session: DatabaseSession, question_id: str) -> QuestionConfirmation:
    confirmation = session.scalar(
        select(QuestionConfirmation).where(QuestionConfirmation.question_id == question_id)
    )
    if confirmation is None:
        raise HTTPException(
            status_code=409,
            detail="题目尚未经过用户确认，不能开始分析。",
        )
    actual_hash = hashlib.sha256(confirmation.confirmed_text.encode("utf-8")).hexdigest()
    if actual_hash != confirmation.confirmed_text_hash:
        raise HTTPException(
            status_code=409,
            detail="确认后的题目文字已经变化，请重新确认后再分析。",
        )
    return confirmation


def choose_text_provider(session: DatabaseSession, provider_id: str | None) -> ProviderConfig:
    if provider_id:
        provider = session.get(ProviderConfig, provider_id)
    else:
        provider = session.scalar(
            select(ProviderConfig)
            .where(ProviderConfig.capability == "text", ProviderConfig.enabled.is_(True))
            .order_by(ProviderConfig.created_at)
        )
    if provider is None or provider.capability != "text" or not provider.enabled:
        raise HTTPException(
            status_code=409,
            detail="尚未配置可用的文本模型，请先前往设置页面完成配置。",
        )
    return provider


def analysis_response(run: AnalysisRun) -> AnalysisResponse:
    output = AnalysisOutput.model_validate(run.output_json)
    verification = VerificationResult.model_validate(run.verification_json)
    response_status = "completed" if run.status == "completed" else "needs_more_information"
    return AnalysisResponse(
        **output.model_dump(),
        id=run.id,
        provider_config_id=run.provider_config_id,
        model_name=run.model_name,
        prompt_version=run.prompt_version,
        schema_version=run.schema_version,
        status=response_status,
        verification=verification,
        duration_ms=run.duration_ms or 0,
        created_at=run.created_at,
    )


@router.post("/{question_id}/analyze", response_model=AnalysisResponse)
@single_model_operation("analysis")
async def analyze_question(
    question_id: str,
    payload: AnalysisRequest,
    request: Request,
    session: DatabaseSession,
) -> AnalysisResponse:
    question = get_question(session, question_id)
    confirmation = get_valid_confirmation(session, question_id)
    provider = choose_text_provider(session, payload.provider_id)

    run = AnalysisRun(
        question_id=question_id,
        confirmation_id=confirmation.id,
        provider_config_id=provider.id,
        confirmed_text_snapshot=confirmation.confirmed_text,
        confirmed_text_hash=confirmation.confirmed_text_hash,
        model_name=provider.model_name,
        prompt_version=ANALYSIS_PROMPT_VERSION,
        schema_version=ANALYSIS_SCHEMA_VERSION,
        status="running",
    )
    session.add(run)
    session.commit()
    session.refresh(run)

    try:
        api_key = request.app.state.secret_store.read(provider.secret_ref)
        text_provider = request.app.state.text_provider_factory.create(provider.provider_type)
        result = await text_provider.analyze(
            config=provider,
            api_key=api_key,
            confirmed_text=confirmation.confirmed_text,
            subject=confirmation.subject,
            grade=confirmation.grade,
            user_answer=confirmation.user_answer,
            user_solution=confirmation.user_solution,
        )
    except (OSError, UnicodeError, SecretProtectionError) as exc:
        run.status = "failed"
        run.error_code = "secret_unavailable"
        run.completed_at = datetime.now(UTC)
        session.commit()
        raise HTTPException(
            status_code=500, detail="无法读取文本模型 API Key，请重新保存配置。"
        ) from exc
    except TextProviderError as exc:
        run.status = "failed"
        run.error_code = exc.code
        run.completed_at = datetime.now(UTC)
        session.commit()
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    output = result.output
    if output.question_completeness == "complete":
        verification = verify_simple_arithmetic(confirmation.confirmed_text, output.final_answer)
        run.status = "completed"
        question.status = "completed"
        if session.get(QuestionLearning, question_id) is None:
            now = datetime.now(UTC)
            session.add(
                QuestionLearning(
                    question_id=question_id,
                    mastery_status="new",
                    starred=False,
                    review_count=0,
                    next_review_at=now,
                    created_at=now,
                    updated_at=now,
                )
            )
    else:
        verification = VerificationResult(
            status="not_applicable",
            message="题目信息不足，未执行答案校验。",
        )
        run.status = "needs_more_information"
        question.status = "needs_more_information"

    run.normalized_question = output.normalized_question
    run.question_completeness = output.question_completeness
    run.confidence = output.confidence
    run.output_json = output.model_dump(mode="json")
    run.verification_json = verification.model_dump(mode="json")
    run.duration_ms = result.duration_ms
    run.completed_at = datetime.now(UTC)
    session.commit()
    session.refresh(run)
    return analysis_response(run)


@router.get("/{question_id}/analysis", response_model=AnalysisResponse)
def read_latest_analysis(question_id: str, session: DatabaseSession) -> AnalysisResponse:
    get_question(session, question_id)
    run = session.scalar(
        select(AnalysisRun)
        .where(
            AnalysisRun.question_id == question_id,
            AnalysisRun.status.in_(["completed", "needs_more_information"]),
        )
        .order_by(AnalysisRun.created_at.desc())
    )
    if run is None:
        raise HTTPException(status_code=404, detail="这道题目还没有可用的分析结果。")
    return analysis_response(run)
