from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import select

from backend.app.api.v1.analysis import choose_text_provider, get_question
from backend.app.api.v1.operations import single_model_operation
from backend.app.db.dependencies import DatabaseSession
from backend.app.db.models import (
    AnalysisRun,
    QuestionLearning,
    ReviewEvent,
    VariationRun,
)
from backend.app.providers.text import TextProviderError
from backend.app.providers.variation import VARIATION_PROMPT_VERSION, VARIATION_SCHEMA_VERSION
from backend.app.schemas.analysis import AnalysisOutput
from backend.app.schemas.learning import (
    LearningResponse,
    LearningUpdate,
    NotebookFacets,
    NotebookItem,
    NotebookResponse,
    ReviewRequest,
    ReviewResponse,
    VariationOutput,
    VariationRequest,
    VariationResponse,
)
from backend.app.security.secrets import SecretProtectionError

router = APIRouter(tags=["学习闭环"])


def latest_completed_analysis(session: DatabaseSession, question_id: str) -> AnalysisRun:
    run = session.scalar(
        select(AnalysisRun)
        .where(AnalysisRun.question_id == question_id, AnalysisRun.status == "completed")
        .order_by(AnalysisRun.created_at.desc())
    )
    if run is None:
        raise HTTPException(status_code=409, detail="请先完成题目分析，再记录错因或生成变式题。")
    return run


def get_or_create_learning(
    session: DatabaseSession, question_id: str, *, due_now: bool = True
) -> QuestionLearning:
    learning = session.get(QuestionLearning, question_id)
    if learning is None:
        now = datetime.now(UTC)
        learning = QuestionLearning(
            question_id=question_id,
            mastery_status="new",
            starred=False,
            review_count=0,
            next_review_at=now if due_now else None,
            created_at=now,
            updated_at=now,
        )
        session.add(learning)
        session.commit()
        session.refresh(learning)
    return learning


def learning_response(learning: QuestionLearning) -> LearningResponse:
    return LearningResponse.model_validate(learning, from_attributes=True)


@router.get("/questions/{question_id}/learning", response_model=LearningResponse)
def read_learning(question_id: str, session: DatabaseSession) -> LearningResponse:
    get_question(session, question_id)
    latest_completed_analysis(session, question_id)
    return learning_response(get_or_create_learning(session, question_id))


@router.put("/questions/{question_id}/learning", response_model=LearningResponse)
def update_learning(
    question_id: str,
    payload: LearningUpdate,
    session: DatabaseSession,
) -> LearningResponse:
    get_question(session, question_id)
    latest_completed_analysis(session, question_id)
    learning = get_or_create_learning(session, question_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(learning, field, value)
    learning.updated_at = datetime.now(UTC)
    session.commit()
    session.refresh(learning)
    return learning_response(learning)


def variation_response(run: VariationRun) -> VariationResponse:
    output = VariationOutput.model_validate(run.output_json)
    return VariationResponse(
        **output.model_dump(),
        id=run.id,
        provider_config_id=run.provider_config_id,
        model_name=run.model_name,
        prompt_version=run.prompt_version,
        schema_version=run.schema_version,
        duration_ms=run.duration_ms or 0,
        created_at=run.created_at,
    )


@router.post("/questions/{question_id}/variations", response_model=VariationResponse)
@single_model_operation("variations")
async def generate_variations(
    question_id: str,
    payload: VariationRequest,
    request: Request,
    session: DatabaseSession,
) -> VariationResponse:
    get_question(session, question_id)
    analysis = latest_completed_analysis(session, question_id)
    provider = choose_text_provider(session, payload.provider_id)
    run = VariationRun(
        question_id=question_id,
        analysis_run_id=analysis.id,
        provider_config_id=provider.id,
        model_name=provider.model_name,
        prompt_version=VARIATION_PROMPT_VERSION,
        schema_version=VARIATION_SCHEMA_VERSION,
        status="running",
    )
    session.add(run)
    session.commit()
    session.refresh(run)

    try:
        api_key = request.app.state.secret_store.read(provider.secret_ref)
        generator = request.app.state.variation_provider_factory.create(provider.provider_type)
        result = await generator.generate(
            config=provider,
            api_key=api_key,
            analysis=AnalysisOutput.model_validate(analysis.output_json).model_dump(mode="json"),
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

    run.status = "completed"
    run.output_json = result.output.model_dump(mode="json")
    run.model_name = result.model_name_override or provider.model_name
    run.duration_ms = result.duration_ms
    run.completed_at = datetime.now(UTC)
    session.commit()
    session.refresh(run)
    return variation_response(run)


@router.get("/questions/{question_id}/variations", response_model=VariationResponse)
def read_variations(question_id: str, session: DatabaseSession) -> VariationResponse:
    get_question(session, question_id)
    analysis = latest_completed_analysis(session, question_id)
    run = session.scalar(
        select(VariationRun)
        .where(
            VariationRun.question_id == question_id,
            VariationRun.analysis_run_id == analysis.id,
            VariationRun.status == "completed",
        )
        .order_by(VariationRun.created_at.desc())
    )
    if run is None:
        raise HTTPException(status_code=404, detail="这道题目还没有可用的变式题。")
    return variation_response(run)


def collect_notebook_items(session: DatabaseSession) -> list[NotebookItem]:
    runs = session.scalars(
        select(AnalysisRun)
        .where(AnalysisRun.status == "completed")
        .order_by(AnalysisRun.created_at.desc())
    ).all()
    latest: dict[str, AnalysisRun] = {}
    for run in runs:
        latest.setdefault(run.question_id, run)

    items: list[NotebookItem] = []
    for question_id, run in latest.items():
        output = AnalysisOutput.model_validate(run.output_json)
        learning = get_or_create_learning(session, question_id)
        items.append(
            NotebookItem(
                question_id=question_id,
                question=output.normalized_question,
                subject=output.subject,
                grade=output.grade,
                knowledge_points=output.knowledge_points,
                difficulty=output.difficulty,
                actual_error_reason=learning.actual_error_reason,
                actual_error_note=learning.actual_error_note,
                mastery_status=learning.mastery_status,
                starred=learning.starred,
                review_count=learning.review_count,
                next_review_at=learning.next_review_at,
                created_at=run.created_at,
                updated_at=learning.updated_at,
            )
        )
    return items


@router.get("/notebook", response_model=NotebookResponse)
def read_notebook(
    session: DatabaseSession,
    search: str = Query(default="", max_length=200),
    subject: str | None = Query(default=None, max_length=100),
    knowledge: str | None = Query(default=None, max_length=200),
    mastery: str | None = Query(default=None, pattern="^(new|reviewing|mastered)$"),
    starred: bool | None = None,
) -> NotebookResponse:
    all_items = collect_notebook_items(session)
    subjects = sorted({item.subject for item in all_items if item.subject})
    knowledge_points = sorted({point for item in all_items for point in item.knowledge_points})
    needle = search.strip().casefold()

    items = all_items
    if needle:
        items = [
            item
            for item in items
            if needle
            in " ".join(
                [item.question, item.subject, item.grade, *item.knowledge_points]
            ).casefold()
        ]
    if subject:
        items = [item for item in items if item.subject == subject]
    if knowledge:
        items = [item for item in items if knowledge in item.knowledge_points]
    if mastery:
        items = [item for item in items if item.mastery_status == mastery]
    if starred is not None:
        items = [item for item in items if item.starred is starred]

    return NotebookResponse(
        items=items,
        facets=NotebookFacets(
            subjects=subjects,
            knowledge_points=knowledge_points,
            total=len(all_items),
            new_count=sum(item.mastery_status == "new" for item in all_items),
            reviewing_count=sum(item.mastery_status == "reviewing" for item in all_items),
            mastered_count=sum(item.mastery_status == "mastered" for item in all_items),
        ),
    )


@router.get("/review/due", response_model=list[NotebookItem])
def read_due_reviews(session: DatabaseSession) -> list[NotebookItem]:
    now = datetime.now(UTC)
    items = collect_notebook_items(session)
    return [
        item
        for item in items
        if item.next_review_at is not None
        and item.next_review_at.replace(tzinfo=UTC) <= now
        and item.mastery_status != "mastered"
    ]


@router.post("/questions/{question_id}/review", response_model=ReviewResponse)
def record_review(
    question_id: str,
    payload: ReviewRequest,
    session: DatabaseSession,
) -> ReviewResponse:
    get_question(session, question_id)
    latest_completed_analysis(session, question_id)
    learning = get_or_create_learning(session, question_id)
    previous_status = learning.mastery_status
    now = datetime.now(UTC)

    if payload.result == "forgotten":
        learning.review_count = 0
        learning.mastery_status = "reviewing"
        scheduled_days = 1
    else:
        learning.review_count += 1
        intervals = [1, 3, 7, 14, 30, 60]
        scheduled_days = intervals[min(learning.review_count - 1, len(intervals) - 1)]
        learning.mastery_status = "mastered" if learning.review_count >= 3 else "reviewing"

    learning.last_reviewed_at = now
    learning.next_review_at = now + timedelta(days=scheduled_days)
    learning.updated_at = now
    session.add(
        ReviewEvent(
            question_id=question_id,
            result=payload.result,
            previous_status=previous_status,
            next_status=learning.mastery_status,
            next_review_at=learning.next_review_at,
        )
    )
    session.commit()
    session.refresh(learning)
    return ReviewResponse(**learning_response(learning).model_dump(), scheduled_days=scheduled_days)
