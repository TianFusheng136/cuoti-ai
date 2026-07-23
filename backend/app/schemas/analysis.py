from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SolutionStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step: int = Field(ge=1, le=100)
    content: str = Field(min_length=1, max_length=10_000)
    reason: str = Field(min_length=1, max_length=10_000)
    knowledge_used: str = Field(min_length=1, max_length=500)


class AnalysisOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: str = Field(max_length=100)
    grade: str = Field(max_length=100)
    normalized_question: str = Field(max_length=50_000)
    question_completeness: Literal["complete", "partial", "uncertain"]
    knowledge_points: list[str] = Field(max_length=20)
    difficulty: Literal["basic", "medium", "hard"]
    final_answer: str = Field(max_length=20_000)
    solution_overview: str = Field(max_length=20_000)
    solution_steps: list[SolutionStep] = Field(max_length=50)
    possible_mistakes: list[str] = Field(max_length=20)
    memory_tip: str = Field(max_length=2_000)
    next_time_checklist: list[str] = Field(max_length=3)
    confidence: Literal["high", "medium", "low"]
    missing_information: list[str] = Field(max_length=20)

    @model_validator(mode="after")
    def validate_safe_output(self) -> "AnalysisOutput":
        if self.question_completeness == "complete":
            required_text = [
                self.normalized_question,
                self.final_answer,
                self.solution_overview,
                self.memory_tip,
            ]
            if not all(item.strip() for item in required_text):
                raise ValueError("完整题目必须包含题目、答案、思路和记忆提示")
            if not self.knowledge_points or not self.solution_steps:
                raise ValueError("完整题目必须包含知识点和解题步骤")
            if not self.possible_mistakes:
                raise ValueError("完整题目必须包含可能的错因")
            step_numbers = [item.step for item in self.solution_steps]
            if step_numbers != list(range(1, len(step_numbers) + 1)):
                raise ValueError("解题步骤必须从 1 开始连续编号")
            if len(self.next_time_checklist) != 3:
                raise ValueError("完整题目必须包含三步检查清单")
        else:
            if not self.missing_information:
                raise ValueError("信息不足时必须列出缺失信息")
            forbidden = [self.final_answer, self.solution_overview, self.memory_tip]
            if any(item.strip() for item in forbidden) or self.solution_steps:
                raise ValueError("信息不足时不得生成答案、思路或解题步骤")
            if self.next_time_checklist:
                raise ValueError("信息不足时不得生成检查清单")
        return self


class AnalysisRequest(BaseModel):
    provider_id: str | None = None


class VerificationResult(BaseModel):
    status: Literal["verified", "conflict", "not_applicable", "verification_failed"]
    message: str


class AnalysisResponse(AnalysisOutput):
    id: str
    provider_config_id: str | None
    model_name: str
    prompt_version: str
    schema_version: str
    status: Literal["completed", "needs_more_information"]
    verification: VerificationResult
    duration_ms: int
    created_at: datetime
