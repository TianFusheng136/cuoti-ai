from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Completeness = Literal["complete", "partial", "uncertain"]
Confidence = Literal["high", "medium", "low"]


class RecognitionOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recognized_text: str = Field(max_length=50_000)
    question_completeness: Completeness
    confidence: Confidence
    warnings: list[str] = Field(default_factory=list, max_length=20)
    missing_information: list[str] = Field(default_factory=list, max_length=20)
    detected_subject: str | None = Field(default=None, max_length=100)
    detected_grade: str | None = Field(default=None, max_length=100)
    has_formula: bool
    has_diagram: bool

    @field_validator("recognized_text")
    @classmethod
    def strip_recognized_text(cls, value: str) -> str:
        normalized = value
        for command_suffix in ("riangle", "heta", "imes", "an", "ext"):
            normalized = normalized.replace(f"\t{command_suffix}", f"\\t{command_suffix}")
        return normalized.replace("\t", " ").strip()

    @model_validator(mode="after")
    def validate_completeness(self) -> "RecognitionOutput":
        if self.question_completeness != "complete" and not self.missing_information:
            raise ValueError("题目信息不完整时必须说明缺失内容")
        if not self.recognized_text and not self.missing_information:
            raise ValueError("未识别到文字时必须说明缺失内容")
        return self


class RecognitionRequest(BaseModel):
    provider_id: str | None = None


class RecognitionResponse(RecognitionOutput):
    id: str
    provider_config_id: str | None
    model_name: str
    prompt_version: str
    status: Literal["succeeded"]
    duration_ms: int
    created_at: datetime


class ConfirmationCreate(BaseModel):
    confirmed_text: str = Field(min_length=1, max_length=50_000)
    subject: str | None = Field(default=None, max_length=100)
    grade: str | None = Field(default=None, max_length=100)
    user_answer: str | None = Field(default=None, max_length=20_000)
    user_solution: str | None = Field(default=None, max_length=30_000)
    acknowledge_complete: Literal[True]

    @field_validator("confirmed_text")
    @classmethod
    def strip_confirmed_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("确认后的题目文字不能为空")
        return normalized

    @field_validator("subject", "grade", "user_answer", "user_solution")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class ConfirmationResponse(BaseModel):
    id: str
    question_id: str
    recognized_text_snapshot: str | None
    confirmed_text: str
    confirmed_text_hash: str
    subject: str | None
    grade: str | None
    user_answer: str | None
    user_solution: str | None
    confirmed_at: datetime
    updated_at: datetime
