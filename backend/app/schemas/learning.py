from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ErrorReason = Literal[
    "concept",
    "calculation",
    "reading",
    "method",
    "careless",
    "other",
    "unknown",
]
MasteryStatus = Literal["new", "reviewing", "mastered"]


class LearningUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actual_error_reason: ErrorReason | None = None
    actual_error_note: str | None = Field(default=None, max_length=2_000)
    mastery_status: MasteryStatus | None = None
    starred: bool | None = None


class LearningResponse(BaseModel):
    question_id: str
    actual_error_reason: ErrorReason | None
    actual_error_note: str | None
    mastery_status: MasteryStatus
    starred: bool
    review_count: int
    next_review_at: datetime | None
    last_reviewed_at: datetime | None
    updated_at: datetime


class Variation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["same_point", "new_context", "challenge"]
    title: str = Field(min_length=1, max_length=100)
    question: str = Field(min_length=1, max_length=20_000)
    answer: str = Field(min_length=1, max_length=20_000)
    solution: str = Field(min_length=1, max_length=30_000)
    knowledge_points: list[str] = Field(min_length=1, max_length=10)
    difficulty: Literal["basic", "medium", "hard"]


class VariationDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["same_point", "new_context", "challenge"]
    title: str = Field(min_length=1, max_length=100)
    question: str = Field(min_length=1, max_length=20_000)
    knowledge_points: list[str] = Field(min_length=1, max_length=10)
    difficulty: Literal["basic", "medium", "hard"]


class SingleVariationDraftOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    draft: VariationDraft


class VariationOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    variants: list[Variation] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def validate_types(self) -> "VariationOutput":
        expected = ["same_point", "new_context", "challenge"]
        if [item.type for item in self.variants] != expected:
            raise ValueError("变式题必须依次包含同知识点、换场景和提高难度三种类型")
        return self


class VariationIndependentSolution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["same_point", "new_context", "challenge"]
    solvable: bool
    answer_determined: bool
    answer: str = Field(min_length=1, max_length=20_000)
    reasoning: str = Field(min_length=1, max_length=20_000)
    issues: list[str] = Field(default_factory=list, max_length=10)


class VariationResolvedAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str = Field(min_length=1, max_length=20_000)
    solution: str = Field(min_length=1, max_length=8_000)


class VariationVerificationItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["same_point", "new_context", "challenge"]
    valid: bool
    recomputed_answer: str = Field(min_length=1, max_length=20_000)
    issues: list[str] = Field(default_factory=list, max_length=10)


class VariationVerificationOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overall_valid: bool
    items: list[VariationVerificationItem] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def validate_items(self) -> "VariationVerificationOutput":
        expected = ["same_point", "new_context", "challenge"]
        if [item.type for item in self.items] != expected:
            raise ValueError("校验结果必须依次覆盖三类变式题")
        if self.overall_valid != all(item.valid and not item.issues for item in self.items):
            raise ValueError("总体验证结论与逐题结论不一致")
        return self


class VariationRequest(BaseModel):
    provider_id: str | None = None


class VariationResponse(VariationOutput):
    id: str
    provider_config_id: str | None
    model_name: str
    prompt_version: str
    schema_version: str
    duration_ms: int
    created_at: datetime


class NotebookItem(BaseModel):
    question_id: str
    question: str
    subject: str
    grade: str
    knowledge_points: list[str]
    difficulty: str
    actual_error_reason: ErrorReason | None
    actual_error_note: str | None
    mastery_status: MasteryStatus
    starred: bool
    review_count: int
    next_review_at: datetime | None
    created_at: datetime
    updated_at: datetime


class NotebookFacets(BaseModel):
    subjects: list[str]
    knowledge_points: list[str]
    total: int
    new_count: int
    reviewing_count: int
    mastered_count: int


class NotebookResponse(BaseModel):
    items: list[NotebookItem]
    facets: NotebookFacets


class ReviewRequest(BaseModel):
    result: Literal["remembered", "forgotten"]


class ReviewResponse(LearningResponse):
    scheduled_days: int
